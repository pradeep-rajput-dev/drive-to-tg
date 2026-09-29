import os
import threading
from web import app as web_app
from bot import app as telegram_app

def run_web():
    web_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), use_reloader=False)

if __name__ == '__main__':
    threading.Thread(target=run_web, daemon=True).start()
    telegram_app.run()
