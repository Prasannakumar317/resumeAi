#!/usr/bin/env python
"""
QUICK START GUIDE - Authentication Security Fix
Run this to verify everything is installed and ready!
"""

import sys
import os

def check_environment():
    """Check if everything is ready to go"""
    
    print("=" * 60)
    print("🔐 AUTHENTICATION SECURITY FIX - QUICK START")
    print("=" * 60)
    print()
    
    checks_passed = 0
    checks_total = 0
    
    # Check Python version
    print("1️⃣  Python Version")
    checks_total += 1
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 7):
        print(f"   ✅ Python {py_version}")
        checks_passed += 1
    else:
        print(f"   ❌ Python {py_version} (Need 3.7+)")
    print()
    
    # Check required packages
    print("2️⃣  Required Packages")
    required_packages = {
        'flask': 'Flask',
        'flask_sqlalchemy': 'Flask-SQLAlchemy',
        'flask_wtf': 'Flask-WTF (NEW)',
        'werkzeug': 'Werkzeug',
    }
    
    for package, name in required_packages.items():
        checks_total += 1
        try:
            __import__(package)
            print(f"   ✅ {name}")
            checks_passed += 1
        except ImportError:
            print(f"   ❌ {name} - Run: pip install -r requirements.txt")
    print()
    
    # Check database
    print("3️⃣  Database")
    checks_total += 1
    if os.path.exists('site.db'):
        print(f"   ✅ Database exists (site.db)")
        checks_passed += 1
    else:
        print(f"   ⚠️  No database found - Run: python migrate_db.py")
    print()
    
    # Check key files
    print("4️⃣  Implementation Files")
    key_files = {
        'app.py': 'Main application',
        'migrate_db.py': 'Database migration (NEW)',
        'init_db.py': 'Database initialization (NEW)',
    }
    
    for filename, description in key_files.items():
        checks_total += 1
        if os.path.exists(filename):
            print(f"   ✅ {filename}")
            checks_passed += 1
        else:
            print(f"   ❌ {filename} - Missing!")
    print()
    
    # Check documentation
    print("5️⃣  Documentation Files")
    doc_files = {
        'README_AUTH_FIX.md': 'Complete guide',
        'QUICK_REFERENCE.md': 'Developer reference',
        'AUTH_INDEX.md': 'Documentation index',
    }
    
    for filename, description in doc_files.items():
        checks_total += 1
        if os.path.exists(filename):
            print(f"   ✅ {filename}")
            checks_passed += 1
        else:
            print(f"   ⚠️  {filename}")
    print()
    
    # Summary
    print("=" * 60)
    print(f"✅ Status: {checks_passed}/{checks_total} checks passed")
    print("=" * 60)
    print()
    
    if checks_passed == checks_total:
        print("🎉 EVERYTHING LOOKS GOOD! Ready to start!")
        print()
        print("NEXT STEPS:")
        print("1. Run:    python migrate_db.py")
        print("2. Test:   python app.py")
        print("3. Read:   README_AUTH_FIX.md")
        print()
        return True
    else:
        print("⚠️  Please fix the issues above before continuing")
        print()
        print("TROUBLESHOOTING:")
        print("1. Install packages:  pip install -r requirements.txt")
        print("2. Run migration:     python migrate_db.py")
        print("3. Check Python:      python --version (need 3.7+)")
        print()
        return False

if __name__ == '__main__':
    success = check_environment()
    sys.exit(0 if success else 1)
