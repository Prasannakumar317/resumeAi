import requests
from bs4 import BeautifulSoup

url = "http://127.0.0.1:5000/analyzer"

session = requests.Session()

# 1. Get the page to grab the CSRF token
response_get = session.get(url)
soup = BeautifulSoup(response_get.text, 'html.parser')
csrf_token = soup.find('input', {'name': 'csrf_token'})
if csrf_token:
    token = csrf_token['value']
else:
    print("Could not find CSRF token on the page.")
    exit(1)

# 2. Post the form
files = {
    'resume': ('dummy_resume.txt', b'Experienced Python developer with 5 years of Django, Flask, HTML, CSS. Also know some Docker and AWS. Looking for a Backend Developer role.', 'text/plain')
}
data = {
    'role': 'Backend Developer',
    'csrf_token': token
}

print("Sending POST request to /analyzer with CSRF token...")
try:
    response = session.post(url, files=files, data=data)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        html = response.text
        if "Keyword Analysis" in html or "Analysis Results" in html:
            print("Success! Found expected UI elements in the HTML response.")
        else:
            print("Did NOT find expected UI elements. Might have failed early or fallen back.")
            
        if "Sorry, something went wrong" in html or "class=\"alert alert-danger" in html:
            print("WARNING: Found error alert in HTML.")
            
    else:
        print("Error in response.")
except Exception as e:
    print(f"Failed to connect or test: {e}")
