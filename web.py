import os
from flask import Flask

app = Flask(__name__)

@app.get('/')
def home():
    return 'Drive to Telegram bot is running.'

@app.get('/health')
def health():
    return {'status': 'ok'}
