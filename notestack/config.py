import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev_secret_key_change_in_production'
    FIREBASE_CREDENTIALS_PATH = os.environ.get('FIREBASE_CREDENTIALS_PATH') or 'firebase_credentials.json'
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    UPLOAD_FOLDER = 'uploads' 
