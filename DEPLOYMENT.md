# Deployment Guide for Render

## Files Created for Render Deployment

1. **`render.yaml`** - Render configuration file
2. **`Procfile`** - Process file for gunicorn
3. **`runtime.txt`** - Python version specification
4. **Updated `requirements.txt`** - Added gunicorn
5. **Updated `app.py`** - Production-ready configuration

## Step-by-Step Deployment Instructions

### 1. Go to Render Dashboard
- Visit [https://render.com](https://render.com)
- Sign up or log in

### 2. Create New Web Service
- Click **"New +"** → **"Web Service"**
- Connect your GitHub account if not already connected
- Select your repository: **Himelcseju/Faus**

### 3. Configure the Service

**Basic Settings:**
- **Name:** `football-auction` (or any name you prefer)
- **Region:** Choose closest to you
- **Branch:** `main`
- **Root Directory:** (leave empty)

**Build & Deploy:**
- **Environment:** `Python 3`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn app:app`

**Plan:**
- Select **Free** plan (or upgrade if needed)

### 4. Environment Variables (Optional but Recommended)

Click **"Advanced"** → **"Add Environment Variable"**:

- **Key:** `FLASK_ENV` | **Value:** `production`
- **Key:** `SECRET_KEY` | **Value:** (Generate a random string, or Render will auto-generate)
- **Key:** `DATABASE_URL` | **Value:** (Leave empty - Render will provide if you add PostgreSQL)

### 5. Add PostgreSQL Database (Optional but Recommended)

For production, it's better to use PostgreSQL:

1. Go to **"New +"** → **"PostgreSQL"**
2. Create a new database
3. Copy the **Internal Database URL**
4. Add it as environment variable `DATABASE_URL` in your web service

### 6. Deploy!

Click **"Create Web Service"** and wait for deployment.

## Important Notes

### File Uploads
- On Render's free tier, file uploads are stored in the filesystem
- Files will be lost if the service restarts
- For production, consider using cloud storage (AWS S3, Cloudinary, etc.)

### Database
- The app will use SQLite locally
- On Render, it will use PostgreSQL if `DATABASE_URL` is provided
- Otherwise, it will use SQLite (data may be lost on restart)

### Static Files
- Static files (CSS, images) are served automatically
- Uploaded files go to `static/uploads/` directory

## Post-Deployment

1. **Access your app:** You'll get a URL like `https://football-auction.onrender.com`
2. **First login:** Use default admin credentials:
   - Username: `admin`
   - Password: `admin123`
3. **Change default password:** Go to admin panel and update credentials

## Troubleshooting

### If deployment fails:
1. Check build logs in Render dashboard
2. Verify all dependencies in `requirements.txt`
3. Ensure `gunicorn` is installed
4. Check that `app.py` doesn't have syntax errors

### If app crashes:
1. Check logs in Render dashboard
2. Verify environment variables are set correctly
3. Ensure database connection is working

## Updating Your App

After making changes:
```bash
git add .
git commit -m "Your commit message"
git push
```

Render will automatically detect changes and redeploy!

