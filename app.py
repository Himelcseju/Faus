from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.utils import secure_filename
import os
import uuid
import zipfile
import shutil
from openpyxl import load_workbook

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
# Database configuration - use environment variable for production, sqlite for local
database_url = os.environ.get('DATABASE_URL', 'sqlite:///football_auction.db')
# Render uses postgres:// but SQLAlchemy needs postgresql://
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads/team_logos'
app.config['PLAYER_PHOTO_FOLDER'] = 'static/uploads/player_photos'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size (for bulk uploads)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}

db = SQLAlchemy(app)

# Database Models
class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    owner = db.Column(db.String(100), nullable=False)
    coowner_name = db.Column(db.String(100), nullable=True)
    batch = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, default=0.0, nullable=False)
    number_of_members = db.Column(db.Integer, default=12, nullable=False)
    logo_filename = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AuctionSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    auction_start_time = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

class TeamUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    team = db.relationship('Team', backref=db.backref('users', lazy=True))

class SlotManagement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    total_slots = db.Column(db.Integer, default=12, nullable=False)
    filled_slots = db.Column(db.Integer, default=0, nullable=False)
    remaining_slots = db.Column(db.Integer, default=12, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    batch = db.Column(db.String(50), nullable=False)
    position = db.Column(db.String(50), nullable=False)
    base_price = db.Column(db.Float, default=0.0, nullable=False)
    photo_filename = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Authentication decorators
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            flash('Please login as admin first', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def team_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'team_logged_in' not in session:
            flash('Please login as team first', 'error')
            return redirect(url_for('team_login'))
        return f(*args, **kwargs)
    return decorated_function

# Helper function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Helper function to save uploaded file
def save_team_logo(file):
    if file and allowed_file(file.filename):
        # Generate unique filename
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        
        # Create upload directory if it doesn't exist
        upload_folder = app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        
        # Save file
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        return unique_filename
    return None

# Helper function to save player photo
def save_player_photo(file):
    if file and allowed_file(file.filename):
        # Generate unique filename
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        
        # Create upload directory if it doesn't exist
        upload_folder = app.config['PLAYER_PHOTO_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        
        # Save file
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        return unique_filename
    return None

# Football positions list
FOOTBALL_POSITIONS = [
    'Goalkeeper (GK)',
    'Right Back (RB)',
    'Left Back (LB)',
    'Center Back (CB)',
    'Defensive Midfielder (CDM)',
    'Right Midfielder (RM)',
    'Left Midfielder (LM)',
    'Central Midfielder (CM)',
    'Attacking Midfielder (CAM)',
    'Right Winger (RW)',
    'Left Winger (LW)',
    'Striker (ST)',
    'Center Forward (CF)',
    'Second Striker (SS)'
]

# Routes
@app.route('/')
def home():
    teams = Team.query.all()
    team_count = len(teams)
    players = Player.query.all()
    player_count = len(players)
    
    # Get slot information
    slot_info = SlotManagement.query.first()
    if not slot_info:
        slot_info = SlotManagement(total_slots=12, filled_slots=0, remaining_slots=12)
        db.session.add(slot_info)
        db.session.commit()
    
    # Update filled slots based on actual teams
    slot_info.filled_slots = team_count
    slot_info.remaining_slots = slot_info.total_slots - team_count
    db.session.commit()
    
    # Get auction countdown time - Set to Saturday Dec 14, 2025
    auction_setting = AuctionSetting.query.first()
    if auction_setting:
        countdown_time = auction_setting.auction_start_time
    else:
        # Default: Saturday December 14, 2025 at 10:00 AM
        countdown_time = datetime(2025, 12, 14, 10, 0, 0)
        auction_setting = AuctionSetting(auction_start_time=countdown_time)
        db.session.add(auction_setting)
        db.session.commit()
    
    return render_template('index.html', teams=teams, team_count=team_count, 
                         countdown_time=countdown_time, slot_info=slot_info,
                         players=players, player_count=player_count)

@app.route('/api/countdown')
def get_countdown():
    auction_setting = AuctionSetting.query.first()
    if auction_setting:
        countdown_time = auction_setting.auction_start_time
        now = datetime.utcnow()
        if countdown_time > now:
            time_left = countdown_time - now
            return jsonify({
                'days': time_left.days,
                'hours': time_left.seconds // 3600,
                'minutes': (time_left.seconds % 3600) // 60,
                'seconds': time_left.seconds % 60,
                'total_seconds': int(time_left.total_seconds())
            })
    return jsonify({'error': 'No auction time set'}), 404

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.password == password:
            session['admin_logged_in'] = True
            session['admin_username'] = username
            flash('Admin login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials', 'error')
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
@admin_required
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    flash('Admin logged out successfully', 'success')
    return redirect(url_for('home'))

@app.route('/team/login', methods=['GET', 'POST'])
def team_login():
    if request.method == 'POST':
        team_name = request.form.get('team_name')
        password = request.form.get('password')
        
        # Find team by name
        team = Team.query.filter_by(name=team_name).first()
        if team:
            # Check if team has a user account
            team_user = TeamUser.query.filter_by(team_id=team.id).first()
            if team_user and team_user.password == password:
                session['team_logged_in'] = True
                session['team_id'] = team.id
                session['team_name'] = team.name
                flash('Team login successful!', 'success')
                return redirect(url_for('team_dashboard', team_id=team.id))
            elif not team_user:
                # Create default password for team if no user exists
                # Default password is team name in lowercase + "123"
                default_password = team_name.lower().replace(' ', '') + '123'
                if password == default_password:
                    # Create team user
                    new_team_user = TeamUser(team_id=team.id, username=team_name.lower().replace(' ', ''), password=default_password)
                    db.session.add(new_team_user)
                    db.session.commit()
                    session['team_logged_in'] = True
                    session['team_id'] = team.id
                    session['team_name'] = team.name
                    flash('Team login successful!', 'success')
                    return redirect(url_for('team_dashboard', team_id=team.id))
        
        flash('Invalid team name or password', 'error')
    
    return render_template('team_login.html')

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    teams = Team.query.all()
    players = Player.query.all()
    auction_setting = AuctionSetting.query.first()
    slot_info = SlotManagement.query.first()
    if not slot_info:
        slot_info = SlotManagement(total_slots=12, filled_slots=len(teams), remaining_slots=12-len(teams))
        db.session.add(slot_info)
        db.session.commit()
    else:
        slot_info.filled_slots = len(teams)
        slot_info.remaining_slots = slot_info.total_slots - len(teams)
        db.session.commit()
    return render_template('admin_dashboard.html', teams=teams, players=players, auction_setting=auction_setting, slot_info=slot_info)

@app.route('/team/dashboard/<int:team_id>')
@team_required
def team_dashboard(team_id):
    # Verify team belongs to logged in user
    if session.get('team_id') != team_id:
        flash('Unauthorized access', 'error')
        return redirect(url_for('team_login'))
    team = Team.query.get_or_404(team_id)
    return render_template('team_dashboard.html', team=team)

@app.route('/team/logout')
@team_required
def team_logout():
    session.pop('team_logged_in', None)
    session.pop('team_id', None)
    session.pop('team_name', None)
    flash('Team logged out successfully', 'success')
    return redirect(url_for('home'))

@app.route('/admin/team/add', methods=['GET', 'POST'])
@admin_required
def add_team():
    if request.method == 'POST':
        name = request.form.get('name')
        owner = request.form.get('owner')
        coowner_name = request.form.get('coowner_name', '')
        batch = request.form.get('batch')
        price = request.form.get('price', 0.0)
        number_of_members = request.form.get('number_of_members', 12)
        
        # Handle logo upload
        logo_filename = None
        if 'logo' in request.files:
            logo_file = request.files['logo']
            if logo_file and logo_file.filename:
                logo_filename = save_team_logo(logo_file)
                if not logo_filename:
                    flash('Invalid logo file. Allowed formats: PNG, JPG, JPEG, GIF, WEBP, SVG', 'error')
        
        # Validate required fields
        if not name or not owner or not batch:
            flash('Team name, owner name, and batch are required', 'error')
            return redirect(url_for('add_team'))
        
        # Check if team name already exists
        existing_team = Team.query.filter_by(name=name).first()
        if existing_team:
            flash('Team name already exists', 'error')
            return redirect(url_for('add_team'))
        
        try:
            price = float(price) if price else 0.0
        except ValueError:
            price = 0.0
        
        try:
            number_of_members = int(number_of_members) if number_of_members else 12
        except ValueError:
            number_of_members = 12
        
        # Create new team
        new_team = Team(
            name=name,
            owner=owner,
            coowner_name=coowner_name,
            batch=batch,
            price=price,
            number_of_members=number_of_members,
            logo_filename=logo_filename
        )
        db.session.add(new_team)
        db.session.commit()
        
        # Update slot management
        slot_info = SlotManagement.query.first()
        if slot_info:
            slot_info.filled_slots = Team.query.count()
            slot_info.remaining_slots = slot_info.total_slots - slot_info.filled_slots
            db.session.commit()
        
        flash('Team added successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('add_team.html')

@app.route('/admin/team/edit/<int:team_id>', methods=['GET', 'POST'])
@admin_required
def edit_team(team_id):
    team = Team.query.get_or_404(team_id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        owner = request.form.get('owner')
        coowner_name = request.form.get('coowner_name', '')
        batch = request.form.get('batch')
        price = request.form.get('price', 0.0)
        number_of_members = request.form.get('number_of_members', 12)
        delete_logo = request.form.get('delete_logo') == 'true'
        
        # Handle logo upload
        if 'logo' in request.files:
            logo_file = request.files['logo']
            if logo_file and logo_file.filename:
                # Delete old logo if exists
                if team.logo_filename:
                    old_logo_path = os.path.join(app.config['UPLOAD_FOLDER'], team.logo_filename)
                    if os.path.exists(old_logo_path):
                        os.remove(old_logo_path)
                
                # Save new logo
                logo_filename = save_team_logo(logo_file)
                if logo_filename:
                    team.logo_filename = logo_filename
                elif not logo_filename:
                    flash('Invalid logo file. Allowed formats: PNG, JPG, JPEG, GIF, WEBP, SVG', 'error')
        
        # Handle logo deletion
        if delete_logo and team.logo_filename:
            old_logo_path = os.path.join(app.config['UPLOAD_FOLDER'], team.logo_filename)
            if os.path.exists(old_logo_path):
                os.remove(old_logo_path)
            team.logo_filename = None
        
        # Validate required fields
        if not name or not owner or not batch:
            flash('Team name, owner name, and batch are required', 'error')
            return redirect(url_for('edit_team', team_id=team_id))
        
        # Check if team name already exists (excluding current team)
        existing_team = Team.query.filter_by(name=name).first()
        if existing_team and existing_team.id != team_id:
            flash('Team name already exists', 'error')
            return redirect(url_for('edit_team', team_id=team_id))
        
        try:
            price = float(price) if price else 0.0
        except ValueError:
            price = 0.0
        
        try:
            number_of_members = int(number_of_members) if number_of_members else 12
        except ValueError:
            number_of_members = 12
        
        # Update team
        team.name = name
        team.owner = owner
        team.coowner_name = coowner_name
        team.batch = batch
        team.price = price
        team.number_of_members = number_of_members
        db.session.commit()
        
        flash('Team updated successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('edit_team.html', team=team)

@app.route('/admin/team/delete/<int:team_id>', methods=['POST'])
@admin_required
def delete_team(team_id):
    team = Team.query.get_or_404(team_id)
    
    # Delete team logo if exists
    if team.logo_filename:
        logo_path = os.path.join(app.config['UPLOAD_FOLDER'], team.logo_filename)
        if os.path.exists(logo_path):
            try:
                os.remove(logo_path)
            except:
                pass
    
    # Delete associated team users
    TeamUser.query.filter_by(team_id=team_id).delete()
    
    # Delete team
    db.session.delete(team)
    db.session.commit()
    
    # Update slot management
    slot_info = SlotManagement.query.first()
    if slot_info:
        slot_info.filled_slots = Team.query.count()
        slot_info.remaining_slots = slot_info.total_slots - slot_info.filled_slots
        db.session.commit()
    
    flash('Team deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/api/teams')
def get_teams():
    teams = Team.query.all()
    return jsonify([{
        'id': team.id,
        'name': team.name,
        'owner': team.owner,
        'batch': team.batch
    } for team in teams])

# Player Management Routes
@app.route('/admin/player/add', methods=['GET', 'POST'])
@admin_required
def add_player():
    if request.method == 'POST':
        name = request.form.get('name')
        batch = request.form.get('batch')
        position = request.form.get('position')
        base_price = request.form.get('base_price', 0.0)
        
        # Handle photo upload
        photo_filename = None
        if 'photo' in request.files:
            photo_file = request.files['photo']
            if photo_file and photo_file.filename:
                photo_filename = save_player_photo(photo_file)
                if not photo_filename:
                    flash('Invalid photo file. Allowed formats: PNG, JPG, JPEG, GIF, WEBP, SVG', 'error')
        
        # Validate required fields
        if not name or not batch or not position:
            flash('Player name, batch, and position are required', 'error')
            return redirect(url_for('add_player'))
        
        try:
            base_price = float(base_price) if base_price else 0.0
        except ValueError:
            base_price = 0.0
        
        # Create new player
        new_player = Player(
            name=name,
            batch=batch,
            position=position,
            base_price=base_price,
            photo_filename=photo_filename
        )
        db.session.add(new_player)
        db.session.commit()
        
        flash('Player added successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('add_player.html', positions=FOOTBALL_POSITIONS)

@app.route('/admin/player/edit/<int:player_id>', methods=['GET', 'POST'])
@admin_required
def edit_player(player_id):
    player = Player.query.get_or_404(player_id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        batch = request.form.get('batch')
        position = request.form.get('position')
        base_price = request.form.get('base_price', 0.0)
        delete_photo = request.form.get('delete_photo') == 'true'
        
        # Handle photo upload
        if 'photo' in request.files:
            photo_file = request.files['photo']
            if photo_file and photo_file.filename:
                # Delete old photo if exists
                if player.photo_filename:
                    old_photo_path = os.path.join(app.config['PLAYER_PHOTO_FOLDER'], player.photo_filename)
                    if os.path.exists(old_photo_path):
                        os.remove(old_photo_path)
                
                # Save new photo
                photo_filename = save_player_photo(photo_file)
                if photo_filename:
                    player.photo_filename = photo_filename
                elif not photo_filename:
                    flash('Invalid photo file. Allowed formats: PNG, JPG, JPEG, GIF, WEBP, SVG', 'error')
        
        # Handle photo deletion
        if delete_photo and player.photo_filename:
            old_photo_path = os.path.join(app.config['PLAYER_PHOTO_FOLDER'], player.photo_filename)
            if os.path.exists(old_photo_path):
                os.remove(old_photo_path)
            player.photo_filename = None
        
        # Validate required fields
        if not name or not batch or not position:
            flash('Player name, batch, and position are required', 'error')
            return redirect(url_for('edit_player', player_id=player_id))
        
        try:
            base_price = float(base_price) if base_price else 0.0
        except ValueError:
            base_price = 0.0
        
        # Update player
        player.name = name
        player.batch = batch
        player.position = position
        player.base_price = base_price
        db.session.commit()
        
        flash('Player updated successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('edit_player.html', player=player, positions=FOOTBALL_POSITIONS)

@app.route('/admin/player/delete/<int:player_id>', methods=['POST'])
@admin_required
def delete_player(player_id):
    player = Player.query.get_or_404(player_id)
    
    # Delete player photo if exists
    if player.photo_filename:
        photo_path = os.path.join(app.config['PLAYER_PHOTO_FOLDER'], player.photo_filename)
        if os.path.exists(photo_path):
            try:
                os.remove(photo_path)
            except:
                pass
    
    # Delete player
    db.session.delete(player)
    db.session.commit()
    
    flash('Player deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/player/bulk-upload', methods=['GET', 'POST'])
@admin_required
def bulk_upload_players():
    if request.method == 'POST':
        excel_file = request.files.get('excel_file')
        photos_folder = request.files.getlist('photos_folder')
        photos_zip = request.files.get('photos_zip')
        
        if not excel_file or excel_file.filename == '':
            flash('Please upload an Excel file', 'error')
            return redirect(url_for('bulk_upload_players'))
        
        # Create temporary directory for photos
        temp_photos_dir = os.path.join('static', 'temp_photos', uuid.uuid4().hex)
        os.makedirs(temp_photos_dir, exist_ok=True)
        
        try:
            # Handle zip file upload
            if photos_zip and photos_zip.filename:
                if photos_zip.filename.endswith('.zip'):
                    zip_path = os.path.join(temp_photos_dir, 'photos.zip')
                    photos_zip.save(zip_path)
                    
                    # Extract zip file
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_photos_dir)
                    os.remove(zip_path)
            
            # Handle multiple file uploads
            if photos_folder:
                for photo_file in photos_folder:
                    if photo_file and photo_file.filename:
                        filename = secure_filename(photo_file.filename)
                        photo_path = os.path.join(temp_photos_dir, filename)
                        photo_file.save(photo_path)
            
            # Read Excel file
            try:
                workbook = load_workbook(excel_file, data_only=True)
                sheet = workbook.active
            except Exception as e:
                flash(f'Error reading Excel file: {str(e)}', 'error')
                shutil.rmtree(temp_photos_dir, ignore_errors=True)
                return redirect(url_for('bulk_upload_players'))
            
            # Get header row (first row)
            headers = []
            for cell in sheet[1]:
                headers.append(str(cell.value).lower().strip() if cell.value else '')
            
            # Validate required columns
            required_columns = ['player_name', 'batch', 'position']
            missing_columns = [col for col in required_columns if col.lower() not in headers]
            if missing_columns:
                flash(f'Missing required columns in Excel: {", ".join(missing_columns)}', 'error')
                shutil.rmtree(temp_photos_dir, ignore_errors=True)
                return redirect(url_for('bulk_upload_players'))
            
            # Get column indices
            player_name_idx = headers.index('player_name') if 'player_name' in headers else -1
            batch_idx = headers.index('batch') if 'batch' in headers else -1
            position_idx = headers.index('position') if 'position' in headers else -1
            base_price_idx = headers.index('base_price') if 'base_price' in headers else -1
            photo_name_idx = headers.index('photo_name') if 'photo_name' in headers else -1
            
            # Process each row
            success_count = 0
            error_count = 0
            errors = []
            
            for index, row in enumerate(sheet.iter_rows(min_row=2, values_only=False), start=2):
                try:
                    # Get cell values
                    player_name = str(row[player_name_idx].value).strip() if player_name_idx >= 0 and row[player_name_idx].value else ''
                    batch = str(row[batch_idx].value).strip() if batch_idx >= 0 and row[batch_idx].value else ''
                    position = str(row[position_idx].value).strip() if position_idx >= 0 and row[position_idx].value else ''
                    base_price = row[base_price_idx].value if base_price_idx >= 0 and row[base_price_idx].value else 0.0
                    photo_name = str(row[photo_name_idx].value).strip() if photo_name_idx >= 0 and row[photo_name_idx].value else None
                    
                    # Validate required fields
                    if not player_name or not batch or not position:
                        error_count += 1
                        errors.append(f'Row {index}: Missing required fields')
                        continue
                    
                    # Convert base_price to float
                    try:
                        base_price = float(base_price) if base_price else 0.0
                    except (ValueError, TypeError):
                        base_price = 0.0
                    
                    # Handle photo upload
                    photo_filename = None
                    if photo_name and photo_name.strip():
                        photo_name_clean = photo_name.strip()
                        # Look for photo in temp directory (case-insensitive matching)
                        photo_path = None
                        
                        # First try exact match (case-insensitive)
                        for root, dirs, files in os.walk(temp_photos_dir):
                            for file in files:
                                if file.lower() == photo_name_clean.lower():
                                    photo_path = os.path.join(root, file)
                                    break
                            if photo_path:
                                break
                        
                        # If not found, try partial match (filename without extension)
                        if not photo_path:
                            photo_name_base = os.path.splitext(photo_name_clean)[0].lower()
                            for root, dirs, files in os.walk(temp_photos_dir):
                                for file in files:
                                    file_base = os.path.splitext(file)[0].lower()
                                    if file_base == photo_name_base:
                                        photo_path = os.path.join(root, file)
                                        break
                                if photo_path:
                                    break
                        
                        # If still not found, try contains match
                        if not photo_path:
                            for root, dirs, files in os.walk(temp_photos_dir):
                                for file in files:
                                    if photo_name_base in file.lower() or file.lower() in photo_name_base:
                                        photo_path = os.path.join(root, file)
                                        break
                                if photo_path:
                                    break
                        
                        if photo_path and os.path.exists(photo_path):
                            # Validate it's an image file
                            if allowed_file(photo_path):
                                # Save photo to permanent location
                                file_ext = os.path.splitext(photo_path)[1]
                                unique_filename = f"{uuid.uuid4().hex}{file_ext}"
                                dest_path = os.path.join(app.config['PLAYER_PHOTO_FOLDER'], unique_filename)
                                os.makedirs(app.config['PLAYER_PHOTO_FOLDER'], exist_ok=True)
                                shutil.copy2(photo_path, dest_path)
                                photo_filename = unique_filename
                            else:
                                errors.append(f'Row {index}: Invalid photo format for {photo_name}')
                        else:
                            # Photo not found, but continue without photo
                            pass
                    
                    # Create player
                    new_player = Player(
                        name=player_name,
                        batch=batch,
                        position=position,
                        base_price=base_price,
                        photo_filename=photo_filename
                    )
                    db.session.add(new_player)
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    errors.append(f'Row {index}: {str(e)}')
                    continue
            
            # Commit all players
            db.session.commit()
            
            # Clean up temp directory
            shutil.rmtree(temp_photos_dir, ignore_errors=True)
            
            # Show results
            if success_count > 0:
                flash(f'Successfully uploaded {success_count} player(s)!', 'success')
            if error_count > 0:
                error_msg = f'Failed to upload {error_count} player(s).'
                if errors:
                    error_msg += ' Errors: ' + '; '.join(errors[:5])  # Show first 5 errors
                    if len(errors) > 5:
                        error_msg += f' ... and {len(errors) - 5} more'
                flash(error_msg, 'error')
            
            return redirect(url_for('admin_dashboard'))
            
        except Exception as e:
            shutil.rmtree(temp_photos_dir, ignore_errors=True)
            flash(f'Error processing bulk upload: {str(e)}', 'error')
            return redirect(url_for('bulk_upload_players'))
    
    return render_template('bulk_upload_players.html', positions=FOOTBALL_POSITIONS)

if __name__ == '__main__':
    with app.app_context():
        # Create all tables first
        db.create_all()
        
        # Migrate existing database: Add new columns if they don't exist
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            
            # Check if team table exists
            if 'team' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('team')]
                
                # Add coowner_name column if it doesn't exist
                if 'coowner_name' not in columns:
                    db.session.execute(text('ALTER TABLE team ADD COLUMN coowner_name VARCHAR(100)'))
                    db.session.commit()
                    print("✓ Added coowner_name column to team table")
                
                # Add price column if it doesn't exist
                if 'price' not in columns:
                    db.session.execute(text('ALTER TABLE team ADD COLUMN price FLOAT DEFAULT 0.0'))
                    db.session.commit()
                    print("✓ Added price column to team table")
                
                # Add number_of_members column if it doesn't exist
                if 'number_of_members' not in columns:
                    db.session.execute(text('ALTER TABLE team ADD COLUMN number_of_members INTEGER DEFAULT 12'))
                    db.session.commit()
                    print("✓ Added number_of_members column to team table")
                
                # Add logo_filename column if it doesn't exist
                if 'logo_filename' not in columns:
                    db.session.execute(text('ALTER TABLE team ADD COLUMN logo_filename VARCHAR(255)'))
                    db.session.commit()
                    print("✓ Added logo_filename column to team table")
        except Exception as e:
            print(f"Migration check: {e}")
        
        # Create player_photos directory
        os.makedirs(app.config['PLAYER_PHOTO_FOLDER'], exist_ok=True)
        
        # Create temp_photos directory for bulk uploads
        os.makedirs('static/temp_photos', exist_ok=True)
        
        # Initialize default admin if not exists
        if not Admin.query.first():
            admin = Admin(username='admin', password='admin123')
            db.session.add(admin)
        
        # Initialize slot management
        if not SlotManagement.query.first():
            slot_mgmt = SlotManagement(total_slots=12, filled_slots=0, remaining_slots=12)
            db.session.add(slot_mgmt)
        
        # Initialize default auction time - Saturday Dec 14, 2025 at 10:00 AM
        if not AuctionSetting.query.first():
            default_time = datetime(2025, 12, 14, 10, 0, 0)
            auction_setting = AuctionSetting(auction_start_time=default_time)
            db.session.add(auction_setting)
        
        # Add sample teams if database is empty
        if not Team.query.first():
            sample_teams = [
                Team(name='Team Alpha', owner='John Doe', coowner_name='Jane Doe', batch='CSE 1', price=50000.00, number_of_members=12),
                Team(name='Team Beta', owner='Jane Smith', batch='CSE 2', price=45000.00, number_of_members=12),
                Team(name='Team Gamma', owner='Mike Johnson', coowner_name='Lisa Johnson', batch='CSE 1', price=55000.00, number_of_members=12),
                Team(name='Team Delta', owner='Sarah Williams', batch='CSE 3', price=48000.00, number_of_members=12),
            ]
            for team in sample_teams:
                db.session.add(team)
            
            # Add sample team users
            team1 = Team.query.filter_by(name='Team Alpha').first()
            if team1:
                team_user = TeamUser(team_id=team1.id, username='team1', password='team123')
                db.session.add(team_user)
        
        db.session.commit()
    
    # Only run with Flask dev server if not in production
    if os.environ.get('FLASK_ENV') != 'production':
        app.run(debug=True, host='0.0.0.0', port=5000)

