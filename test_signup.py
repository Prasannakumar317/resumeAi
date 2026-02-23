#!/usr/bin/env python3
import requests
import re

# Test signup endpoint with correct flow
session = requests.Session()

# First, get signup page to get the CSRF token
print('Step 1: Getting signup page...')
r = session.get('http://127.0.0.1:5000/signup')
print(f'Status: {r.status_code}')

# Extract CSRF token from response
match = re.search(r'name=["\'"]csrf_token["\'"].*?value=["\'"]([^"\']+)["\'"]', r.text)
if match:
    csrf_token = match.group(1)
    print(f'CSRF token extracted: {csrf_token[:30]}...')
    
    # Now try signup with CSRF token
    print('\nStep 2: Submitting signup form...')
    data = {
        'name': 'Test User',
        'email': 'testuser@example.com',
        'password': 'SecurePass123!',
        'confirm_password': 'SecurePass123!',
        'csrf_token': csrf_token
    }
    r = session.post('http://127.0.0.1:5000/signup', data=data, allow_redirects=False)
    print(f'Status: {r.status_code}')
    if r.status_code == 302:
        print(f'Redirect to: {r.headers.get("Location")}')
        print('SUCCESS: Signup worked!')
    elif r.status_code == 400:
        print(f'ERROR 400: {r.text[:300]}')
    else:
        print(f'Unexpected status. Response: {r.text[:300]}')
else:
    print('ERROR: Could not find CSRF token in signup page')
    print(f'Page content (first 500 chars): {r.text[:500]}')
