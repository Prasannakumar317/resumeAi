#!/usr/bin/env python3
"""Test script to verify form visibility and template tracking fixes"""
import os
import time
import glob
from werkzeug.security import generate_password_hash
from app import app, db, User

def test_resume_generation():
    """Test that different templates generate different PDFs with template in filename"""
    
    with app.app_context():
        # Create test user
        test_user = User.query.filter_by(email='test@example.com').first()
        if not test_user:
            test_user = User(
                name='TestUser',
                email='test@example.com',
                password_hash=generate_password_hash('testpass')
            )
            db.session.add(test_user)
            db.session.commit()
        
        # Clear old test files
        uploads_dir = app.config['UPLOAD_FOLDER']
        old_files = glob.glob(os.path.join(uploads_dir, 'TestUser_*'))
        for f in old_files:
            try:
                os.remove(f)
            except:
                pass
        
        # Test form data
        test_cases = [
            {
                'template': 'modern',
                'name': 'TestUser',
                'email': 'test@example.com',
                'phone': '555-1234',
                'summary': 'Professional resume builder tester',
                'declaration': 'Declaration text goes here'
            },
            {
                'template': 'executive',
                'name': 'TestUser',
                'email': 'test@example.com',
                'phone': '555-1234',
                'summary': 'Professional resume builder tester',
                'declaration': 'Declaration text goes here'
            },
            {
                'template': 'creative',
                'name': 'TestUser',
                'email': 'test@example.com',
                'phone': '555-1234',
                'summary': 'Professional resume builder tester',
                'declaration': 'Declaration text goes here'
            }
        ]
        
        client = app.test_client()
        generated_files = []
        
        # First, get CSRF token from the builder page
        response = client.get('/builder')
        csrf_token = None
        if response.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.data, 'html.parser')
            csrf_input = soup.find('input', {'name': 'csrf_token'})
            if csrf_input:
                csrf_token = csrf_input.get('value')
        
        if not csrf_token:
            print("❌ Could not retrieve CSRF token")
            return
        
        for test_case in test_cases:
            form_data = {
                'name': test_case['name'],
                'email': test_case['email'],
                'phone': test_case['phone'],
                'summary': test_case['summary'],
                'declaration': test_case['declaration'],
                'template': test_case['template'],
                'experience': ['Worked at Company A', 'Led development team'],
                'education': ['Bachelor of Science in Computer Science'],
                'achievements': ['Achieved 40% performance improvement'],
                'skills': ['Python', 'JavaScript', 'Flask', 'React'],
                'csrf_token': csrf_token
            }
            
            print(f"\n📝 Testing template: {test_case['template'].upper()}")
            response = client.post('/builder', data=form_data)
            
            if response.status_code == 200:
                print(f"✅ Form submission successful (HTTP 200)")
                
                # Check if file was created with template in name
                time.sleep(0.5)  # Give filesystem a moment
                
                recent_files = sorted(
                    glob.glob(os.path.join(uploads_dir, 'TestUser_*')),
                    key=os.path.getctime,
                    reverse=True
                )
                
                if recent_files:
                    latest_file = recent_files[0]
                    filename = os.path.basename(latest_file)
                    file_size = os.path.getsize(latest_file)
                    
                    # Check if template name is in filename
                    if test_case['template'].lower() in filename.lower():
                        print(f"✅ Template name in filename: {filename}")
                        print(f"   File size: {file_size} bytes")
                        generated_files.append({
                            'template': test_case['template'],
                            'filename': filename,
                            'size': file_size
                        })
                    else:
                        print(f"❌ Template name NOT in filename: {filename}")
                else:
                    print(f"❌ No file created after submission")
            else:
                print(f"❌ Form submission failed (HTTP {response.status_code})")
        
        # Verify different templates have different file sizes (content is different)
        print("\n" + "="*60)
        print("📊 GENERATED FILES SUMMARY")
        print("="*60)
        
        if len(generated_files) >= 2:
            for i, file_info in enumerate(generated_files, 1):
                print(f"{i}. {file_info['filename']}")
                print(f"   Template: {file_info['template'].upper()}")
                print(f"   Size: {file_info['size']} bytes")
            
            # Check if all files have different sizes (indicating different content)
            sizes = [f['size'] for f in generated_files]
            unique_sizes = len(set(sizes))
            
            print("\n" + "="*60)
            if unique_sizes == len(generated_files):
                print("✅ All templates generated different PDFs (different file sizes)")
            else:
                print("⚠️  Some templates generated similar file sizes")
                print("   (This could indicate template stylings are not being applied)")
        else:
            print("❌ Not enough files generated for comparison")
        
        print("\n✅ TEST COMPLETE")
        print("\nTo verify form field visibility, fill out the form in the browser")
        print("and confirm you can see the text as you type.")


if __name__ == '__main__':
    test_resume_generation()
