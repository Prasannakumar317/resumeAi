#!/usr/bin/env python3
"""Direct database connection test - output to file"""
import sys
import os

output_file = 'c:\\cmrhackthon\\test_db_output.txt'

with open(output_file, 'w') as log:
	try:
		log.write("[TEST] Importing Flask app...\n")
		log.flush()
		
		sys.path.insert(0, 'c:\\cmrhackthon')
		from app import app, db, User
		log.write("[TEST] Flask app imported successfully\n")
		log.flush()
		
		log.write("[TEST] Creating app context...\n")
		log.flush()
		
		with app.app_context():
			db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
			log.write(f"[TEST] Database URI: {db_uri}\n")
			log.flush()
			
			log.write("[TEST] Querying users...\n")
			log.flush()
			
			try:
				user_count = User.query.count()
				log.write(f"[TEST] SUCCESS: Database connection OK. Users in DB: {user_count}\n")
			except Exception as e:
				log.write(f"[TEST] ERROR in query: {type(e).__name__}: {e}\n")
				import traceback
				log.write(traceback.format_exc())
			log.flush()
				
	except Exception as e:
		log.write(f"[TEST] CRITICAL ERROR: {type(e).__name__}: {e}\n")
		import traceback
		log.write(traceback.format_exc())
		log.flush()

print(f"Test output written to {output_file}")
