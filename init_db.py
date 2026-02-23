#!/usr/bin/env python
"""
Database initialization and migration script.
This script safely initializes or updates the database schema with new authentication features.
"""

import os
import sys
from app import app, db, User, LoginHistory

def init_database():
	"""Initialize or upgrade the database schema"""
	with app.app_context():
		print("🔄 Initializing database schema...")
		
		try:
			# Create all tables
			db.create_all()
			print("✓ Database tables created/updated successfully")
			
			# Verify User table has all new columns
			inspector = db.inspect(db.engine)
			user_columns = [col['name'] for col in inspector.get_columns('user')]
			
			required_columns = [
				'id', 'name', 'email', 'password_hash', 'created_at',
				'last_login', 'is_active', 'failed_attempts', 'locked_until'
			]
			
			missing_columns = [col for col in required_columns if col not in user_columns]
			
			if missing_columns:
				print(f"⚠️  Some columns are missing: {missing_columns}")
				print("ℹ️  Please run database migrations or recreate the database")
				return False
			
			print("✓ User table has all required columns")
			print("✓ LoginHistory table created/updated")
			
			# Check if we need to set default values for existing users
			existing_users = User.query.filter_by(is_active=None).count()
			if existing_users > 0:
				print(f"⚠️  Found {existing_users} users with null is_active status")
				User.query.filter_by(is_active=None).update({'is_active': True})
				db.session.commit()
				print("✓ Updated existing users")
			
			print("\n✅ Database initialization completed successfully!")
			return True
			
		except Exception as e:
			print(f"❌ Error during database initialization: {e}")
			return False

if __name__ == '__main__':
	success = init_database()
	sys.exit(0 if success else 1)
