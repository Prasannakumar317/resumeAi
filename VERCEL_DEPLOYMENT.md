# Vercel Deployment Instructions

## Prerequisites
1. Vercel account (https://vercel.com)
2. GitHub repository with this code
3. PostgreSQL database (e.g., from Render.com, Railway.app, or Vercel's own Postgres)

## Step 1: Push code to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git branch -M main
git push -u origin main
```

## Step 2: Set up PostgreSQL Database

**Option A: Using Vercel Postgres (Recommended)**
1. Go to Vercel Dashboard → Storage
2. Click "Create Database" → "Postgres"
3. Follow the setup wizard
4. Copy the connection string

**Option B: Using External Provider (Railway, Render, etc.)**
1. Create a PostgreSQL database
2. Get the connection string (DATABASE_URL format)

## Step 3: Deploy on Vercel

1. Go to https://vercel.com/dashboard
2. Click "Add New Project"
3. Select your GitHub repository
4. Click "Import"
5. In Environment Variables, add:
   - `SECRET_KEY`: Generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`
   - `DATABASE_URL`: Paste your PostgreSQL connection string
   - `ENVIRONMENT`: `production`

6. Click "Deploy"

## Step 4: Initialize Database

After deployment, initialize the database by visiting:
```
https://your-vercel-url.vercel.app/status
```

Then visit:
```
https://your-vercel-url.vercel.app/debug
```

To verify all settings are correct.

## Step 5: Test Authentication

1. Go to `https://your-vercel-url.vercel.app/signup`
2. Create an account
3. Go to `https://your-vercel-url.vercel.app/login`
4. Login with your credentials

## Troubleshooting

### Check /debug endpoint
Visit `https://your-vercel-url.vercel.app/debug` to see:
- Environment settings
- Database connection status
- CSRF settings

### Database Connection Issues
- Verify DATABASE_URL is set correctly
- Check PostgreSQL credentials
- Ensure database is publicly accessible (if needed)

### CSRF Token Issues
- Clear browser cookies
- Hard refresh (Ctrl+Shift+R)
- Try incognito/private window

### Session Issues
- Ensure SECRET_KEY is set
- Check HTTPS is enabled (Vercel auto-enables this)

## Notes
- Do NOT use SQLite on Vercel (files are ephemeral)
- Use PostgreSQL or MySQL for production
- SECRET_KEY must be a long random string
- DATABASE_URL format: `postgresql://user:password@host:port/database`
