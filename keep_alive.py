import os
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/', methods=['GET', 'HEAD'])
def home():
    return "Bot is alive!", 200

@app.route('/ping', methods=['GET', 'HEAD'])
def ping():
    return "pong", 200

def run():
    # Render inject PORT; Replit thường dùng 8080; fallback 8080
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True   # ← quan trọng: thread tự chết khi main exit
    t.start()