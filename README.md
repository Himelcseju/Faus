# Football Auction Web Application

A professional Flask-based web application for managing football auctions with SQLite database.

## Features

- **Home Page** with navigation bar (Admin Login & Team Login)
- **Dashboard** showing team count with clickable card to view all teams
- **Teams Display** in beautiful cards showing owner and batch information
- **Auction Countdown Timer** that fetches countdown time from database
- **Admin Login** and **Team Login** functionality
- **Professional UI** with modern design and responsive layout

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python app.py
```

3. Open your browser and navigate to:
```
http://localhost:5000
```

## Default Credentials

### Admin Login
- Username: `admin`
- Password: `admin123`

### Team Login
- Username: `team1`
- Password: `team123`

## Database

The application uses SQLite database (`football_auction.db`) which will be created automatically on first run.

### Database Models

- **Team**: Stores team information (name, owner, batch)
- **AuctionSetting**: Stores auction countdown time
- **Admin**: Admin user credentials
- **TeamUser**: Team user credentials

## Project Structure

```
python_footbal_auction/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── templates/            # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── admin_login.html
│   ├── team_login.html
│   ├── admin_dashboard.html
│   └── team_dashboard.html
├── static/
│   └── css/
│       └── style.css     # Custom styles
└── football_auction.db   # SQLite database (created automatically)
```

## Features in Detail

### Home Page
- Navigation bar with Admin and Team login links
- Auction countdown timer (updates every second)
- Dashboard cards showing statistics
- Clickable teams card that reveals all teams
- Professional gradient background

### Teams Display
- Cards showing team name, owner, and batch
- Hover effects and smooth animations
- Responsive grid layout

### Countdown Timer
- Fetches countdown time from database
- Updates in real-time (every second)
- Shows days, hours, minutes, and seconds
- Beautiful gradient card design

## Customization

You can modify the default auction countdown time by updating the `AuctionSetting` table in the database or modifying the initialization code in `app.py`.

## License

This project is open source and available for use.

