#!/usr/bin/env python3
"""Quick script to get Gemini's description of an image."""
from PIL import Image
import google.generativeai as genai
import sys

api_key = sys.argv[2] if len(sys.argv) > 2 else 'AIzaSyBLvR_ZZ3scSldj_LX-Oax6ycG26U3rQ0A'
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.0-flash-exp')

img = Image.open(sys.argv[1])
response = model.generate_content([
    'Describe this Clash of Clans screenshot in detail. List all UI elements you can see, especially at the bottom of the screen. Be specific about button positions and any text you see. Focus on the rightmost buttons.',
    img
])
print(response.text)
