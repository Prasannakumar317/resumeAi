import google.generativeai as genai
import sys

# use the API key from app.py
genai.configure(api_key='AIzaSyD8jU1qowhNywKs8AzJ_J_ACkVpdU3MUaA')

try:
    print("Available Models supporting generateContent:")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
except Exception as e:
    print(f"Error: {e}")
