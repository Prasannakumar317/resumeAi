#!/usr/bin/env python3
"""Direct database connection test"""
import sys
import os

# Add project to path
sys.path.insert(0, 'c:\\cmrhackthon')

try:
	print("[TEST] Importing Flask app...")
	from app import app, db, User
	print("[TEST] Flask app imported successfully")
	
	print("[TEST] Creating app context...")
	with app.app_context():
		print(f"[TEST] Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
		print("[TEST] Querying users...")
		try:
			user_count = User.query.count()
			print(f"[TEST] SUCCESS: Database connection OK. Users in DB: {user_count}")
		except Exception as e:
			print(f"[TEST] ERROR in query: {type(e).__name__}: {e}")
			import traceback
			traceback.print_exc()
			
except Exception as e:
	print(f"[TEST] CRITICAL ERROR: {type(e).__name__}: {e}")
	import traceback
	traceback.print_exc()
