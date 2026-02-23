#!/usr/bin/env python3
import requests
import re

session = requests.Session()

# Get signup page
print('=== GETTING SIGNUP PAGE ===')
r = session.get('http://127.0.0.1:5000/signup')
print(f'Status: {r.status_code}')

# Look for csrf_token in HTML
if 'csrf_token' in r.text:
    # Find the input with csrf_token
    idx = r.text.find('csrf_token')
    snippet = r.text[max(0, idx-50):idx+300]
    print(f'\nFound csrf_token in HTML:')
    print(snippet)
    print('\n')
    
    # Try to extract value
    match = re.search(r'value=["\']([^"\']+)["\']', snippet)
    if match:
        csrf_token = match.group(1)
        print(f'Extracted CSRF token: {csrf_token[:40]}...')
    else:
        print('Could not extract value from csrf_token input')
else:
    print('\nERROR: csrf_token NOT found in HTML')
    print(f'\nFirst 500 chars of page:')
    print(r.text[:500])
    print('\n...\n')
    print(f'Last 500 chars of page:')
    print(r.text[-500:])

print('\n=== CHECKING TEMPLATES ===')
import os
signup_template = '/root/flask_templates/signup.html' if os.path.exists('/root/flask_templates/signup.html') else 'C:\\cmrhackthon\\templates\\signup.html'
if os.path.exists(signup_template):
    with open(signup_template, 'r') as f:
        content = f.read()
        if 'csrf_token' in content:
            print(f'signup.html contains csrf_token reference')
        else:
            print(f'signup.html DOES NOT contain csrf_token!')
