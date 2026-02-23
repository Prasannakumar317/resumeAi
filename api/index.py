"""
Vercel WSGI wrapper for Flask app
This file allows Flask to run on Vercel's serverless platform
"""
import sys
import os

# Add the parent directory to the path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Export the app for Vercel
app_for_vercel = app
