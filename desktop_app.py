# desktop_app.py - PyWebView Entry Point for MailerX Pro

import webview
import threading
import time
import sys
import os

# Import Flask app from main.py
from main import app as flask_app

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and bundled .exe"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def start_flask():
    """Start Flask server in background thread"""
    try:
        flask_app.run(
            host='127.0.0.1',
            port=5000,
            threaded=True,
            debug=False,
            use_reloader=False
        )
    except Exception as e:
        print(f"Flask server failed to start: {e}")


if __name__ == '__main__':
    print("🚀 Starting MailerX Pro Desktop...")

    # Start Flask in background
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    print("⏳ Waiting for web server to start...")
    time.sleep(2.0)

    # Create native window
    window = webview.create_window(
        title='MailerX Pro | Enterprise Email Campaigns',
        url='http://127.0.0.1:5000',
        width=1450,
        height=920,
        min_size=(1100, 700),
        text_select=False,
        confirm_close=True,
        background_color='#f8fafc'
    )

    print("✅ Launching MailerX Pro window...")
    webview.start(debug=False)   # Set to True only when debugging