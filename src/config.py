from dotenv import load_dotenv
import os

load_dotenv()

API_KEY = os.getenv('BYBIT_API_KEY')
API_SECRET = os.getenv('BYBIT_API_SECRET')

print("Configuration loaded successfully.")
if not API_KEY or not API_SECRET:
    print("Warning: API_KEY and API_SECRET are not set. Please check your .env file.")
else:
    print("API_KEY and API_SECRET are set.")
    print(API_KEY)  # For debugging purposes, remove in production
    print(API_SECRET)  # For debugging purposes, remove in production