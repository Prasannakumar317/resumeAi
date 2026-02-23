#!/usr/bin/env python
"""
Database migration script to add new authentication columns to existing User table.
This safely migrates the database without losing data.
"""

import os
from app import app, db, User
from sqlalchemy import text
from datetime import datetime

def migrate_database():
	"""Migrate existing database to include new authentication columns"""
	with app.app_context():
		print("🔄 Starting database migration...")
		
		try:
			# Get database type
			db_url = app.config['SQLALCHEMY_DATABASE_URI']
			is_sqlite = 'sqlite' in db_url
			
			if is_sqlite:
				print("📦 Detected SQLite database")
				migrate_sqlite()
			else:
				print("📦 Detected PostgreSQL/Other database")
				migrate_other()
			
			print("✅ Migration completed successfully!")
			return True
			
		except Exception as e:
			print(f"❌ Migration failed: {e}")
			import traceback
			traceback.print_exc()
			return False

def migrate_sqlite():
	"""Migrate SQLite database"""
	engine = db.engine
	
	# Check which columns exist
	inspector = db.inspect(engine)
	existing_columns = [col['name'] for col in inspector.get_columns('user')]
	print(f"✓ Existing columns in user table: {existing_columns}")
	
	new_columns = {
		'last_login': 'DATETIME',
		'is_active': 'BOOLEAN DEFAULT 1',
		'failed_attempts': 'INTEGER DEFAULT 0',
		'locked_until': 'DATETIME'
	}
	
	# SQLite: Add missing columns
	for col_name, col_type in new_columns.items():
		if col_name not in existing_columns:
			try:
				sql = f'ALTER TABLE user ADD COLUMN {col_name} {col_type}'
				print(f"  Adding column: {col_name}")
				with engine.begin() as connection:
					connection.execute(text(sql))
				print(f"  ✓ {col_name} added successfully")
			except Exception as e:
				print(f"  ⚠️  Could not add {col_name}: {e}")
	
	# Create LoginHistory table if it doesn't exist
	try:
		print("  Creating LoginHistory table...")
		with engine.begin() as connection:
			connection.execute(text('''
				CREATE TABLE IF NOT EXISTS login_history (
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					user_id INTEGER NOT NULL,
					login_time DATETIME DEFAULT CURRENT_TIMESTAMP,
					ip_address VARCHAR(45),
					user_agent VARCHAR(255),
					success BOOLEAN DEFAULT 1,
					FOREIGN KEY(user_id) REFERENCES user(id)
				)
			'''))
		print("  ✓ LoginHistory table created")
	except Exception as e:
		print(f"  ⚠️  LoginHistory table exists or error: {e}")
	
	# Update existing users to have is_active = True if NULL
	try:
		with engine.begin() as connection:
			connection.execute(text('UPDATE user SET is_active = 1 WHERE is_active IS NULL'))
		print("  ✓ Set is_active=1 for existing users")
	except Exception as e:
		print(f"  ℹ️  {e}")

def migrate_other():
	"""Migrate PostgreSQL or other databases"""
	engine = db.engine
	
	# Check which columns exist
	inspector = db.inspect(engine)
	existing_columns = [col['name'] for col in inspector.get_columns('user')]
	print(f"✓ Existing columns in user table: {existing_columns}")
	
	new_columns = {
		'last_login': 'TIMESTAMP',
		'is_active': 'BOOLEAN DEFAULT TRUE',
		'failed_attempts': 'INTEGER DEFAULT 0',
		'locked_until': 'TIMESTAMP'
	}
	
	# PostgreSQL: Add missing columns
	for col_name, col_type in new_columns.items():
		if col_name not in existing_columns:
			try:
				sql = f'ALTER TABLE "user" ADD COLUMN {col_name} {col_type}'
				print(f"  Adding column: {col_name}")
				with engine.begin() as connection:
					connection.execute(text(sql))
				print(f"  ✓ {col_name} added successfully")
			except Exception as e:
				print(f"  ⚠️  Could not add {col_name}: {e}")
	
	# Create LoginHistory table if it doesn't exist
	try:
		print("  Creating LoginHistory table...")
		with engine.begin() as connection:
			connection.execute(text('''
				CREATE TABLE IF NOT EXISTS login_history (
					id SERIAL PRIMARY KEY,
					user_id INTEGER NOT NULL,
					login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
					ip_address VARCHAR(45),
					user_agent VARCHAR(255),
					success BOOLEAN DEFAULT TRUE,
					FOREIGN KEY(user_id) REFERENCES "user"(id)
				)
			'''))
		print("  ✓ LoginHistory table created")
	except Exception as e:
		print(f"  ⚠️  LoginHistory table exists or error: {e}")
	
	# Update existing users to have is_active = TRUE if NULL
	try:
		with engine.begin() as connection:
			connection.execute(text('UPDATE "user" SET is_active = TRUE WHERE is_active IS NULL'))
		print("  ✓ Set is_active=TRUE for existing users")
	except Exception as e:
		print(f"  ℹ️  {e}")

if __name__ == '__main__':
	import sys
	success = migrate_database()
	sys.exit(0 if success else 1)
