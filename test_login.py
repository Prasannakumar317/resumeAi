#!/usr/bin/env python3
import requests
import re

# Test login endpoint
session = requests.Session()

# First, get login page to get the CSRF token
print('Step 1: Getting login page...')
r = session.get('http://127.0.0.1:5000/login')
print(f'Status: {r.status_code}')

# Extract CSRF token from response
match = re.search(r'name=["\'"]csrf_token["\'"].*?value=["\'"]([^"\']+)["\'"]', r.text)
if match:
    csrf_token = match.group(1)
    print(f'CSRF token extracted: {csrf_token[:30]}...')
    
    # Now try login with CSRF token
    print('\nStep 2: Submitting login form...')
    data = {
        'email': 'testuser@example.com',
        'password': 'SecurePass123!',
        'csrf_token': csrf_token
    }
    r = session.post('http://127.0.0.1:5000/login', data=data, allow_redirects=False)
    print(f'Status: {r.status_code}')
    if r.status_code == 302:
        print(f'Redirect to: {r.headers.get("Location")}')
        print('SUCCESS: Login worked!')
    elif r.status_code == 400:
        print(f'ERROR 400: {r.text[:300]}')
    else:
        print(f'Response status: {r.status_code}')
        if 'wrong' in r.text.lower() or 'invalid' in r.text.lower():
            print('Credentials invalid or account locked')
        else:
            print(f'Unexpected response: {r.text[:300]}')
else:
    print('ERROR: Could not find CSRF token in login page')
    print(f'Page content (first 500 chars): {r.text[:500]}')
