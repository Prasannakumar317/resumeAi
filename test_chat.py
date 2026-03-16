import requests
import json

url = "http://127.0.0.1:5000/chat"
headers = {"Content-Type": "application/json"}
data = {
    "message": "can you give me a professional summary?",
    "context": "builder",
    "resume": "Software engineer with 5 years of experience in Python and JavaScript."
}

try:
    response = requests.post(url, headers=headers, json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
