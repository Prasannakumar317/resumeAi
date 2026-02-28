#!/usr/bin/env python3
"""Simple test for template tracking in PDF filenames"""
import os
import glob
import re
from app import app

def test_template_filenames():
    """Test that PDFs are generated with template names in filenames"""
    
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    
    client = app.test_client()
    uploads_dir = app.config['UPLOAD_FOLDER']
    
    # Clear old test files
    old_files = glob.glob(os.path.join(uploads_dir, 'SimpleTest_*'))
    for f in old_files:
        try:
            os.remove(f)
            print(f"  Cleaned: {os.path.basename(f)}")
        except:
            pass
    
    # Test different templates
    templates_to_test = ['modern', 'executive', 'creative', 'academic', 'minimal']
    results = []
    
    print("\n" + "="*70)
    print("🧪 TESTING TEMPLATE TRACKING IN PDF FILENAMES")
    print("="*70)
    
    for template in templates_to_test:
        form_data = {
            'name': 'SimpleTest',
            'email': 'test@test.com',
            'phone': '555-0000',
            'summary': 'Test summary for template tracking',
            'declaration': 'Declaration',
            'template': template,
            'experience': ['Test experience entry'],
            'education': ['Test education entry'],
            'achievements': ['Test achievement'],
            'skills': ['Python', 'Testing']
        }
        
        print(f"\n📝 Submitting form with template: {template.upper()}")
        response = client.post('/builder', data=form_data)
        
        if response.status_code == 200:
            print(f"   ✅ Form submission successful (HTTP 200)")
            
            # Find the most recently created file
            import time
            time.sleep(0.3)  # Give filesystem a moment
            
            recent_files = sorted(
                glob.glob(os.path.join(uploads_dir, 'SimpleTest_*')),
                key=os.path.getctime,
                reverse=True
            )
            
            if recent_files:
                latest_file = recent_files[0]
                filename = os.path.basename(latest_file)
                file_size = os.path.getsize(latest_file)
                
                # Extract template name from filename
                # Format should be: SimpleTest_<template>_<timestamp>.pdf
                match = re.search(r'SimpleTest_([a-z]+)_\d+\.pdf', filename)
                
                if match:
                    filename_template = match.group(1)
                    if filename_template == template:
                        print(f"   ✅ Correct template in filename: {filename}")
                        print(f"      Size: {file_size} bytes")
                        results.append({
                            'template': template,
                            'filename': filename,
                            'size': file_size,
                            'success': True
                        })
                    else:
                        print(f"   ❌ Wrong template in filename!")
                        print(f"      Expected: {template}, Got: {filename_template}")
                        print(f"      Filename: {filename}")
                        results.append({
                            'template': template,
                            'filename': filename,
                            'success': False
                        })
                else:
                    print(f"   ❌ Unexpected filename format: {filename}")
                    results.append({
                        'template': template,
                        'filename': filename,
                        'success': False
                    })
            else:
                print(f"   ❌ No file created!")
                results.append({'template': template, 'success': False})
        else:
            print(f"   ❌ Form submission failed (HTTP {response.status_code})")
            results.append({'template': template, 'success': False})
    
    # Summary
    print("\n" + "="*70)
    print("📊 TEST RESULTS SUMMARY")
    print("="*70)
    
    successful = sum(1 for r in results if r.get('success', False))
    total = len(results)
    
    print(f"\n✅ Successful: {successful}/{total}")
    
    for result in results:
        status = "✅" if result.get('success') else "❌"
        print(f"{status} {result['template'].upper():10} - {result.get('filename', 'FILE NOT CREATED')}")
    
    if successful == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("   Templates are correctly tracked in PDF filenames.")
    else:
        print(f"\n⚠️  {total - successful} test(s) failed!")
    
    print("\n" + "="*70)
    print("📌 NEXT: Test form field visibility in browser")
    print("   - Open http://127.0.0.1:5000/builder in your browser")
    print("   - Fill in form fields and verify text is visible")
    print("   - Check text color in light/dark/colorful themes")
    print("="*70 + "\n")


if __name__ == '__main__':
    test_template_filenames()
