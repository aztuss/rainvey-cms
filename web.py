import os
import sys
import subprocess
from flask import Flask, request, render_template_string, redirect, url_for, session

app = Flask(__name__)
# Gizli acar, sessiya tehlukesizliyi ucun
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super_gizli_acar_12345")

# Sizin teyin etdiyiniz shifre. Railway-de env variable kimi de vere bilersiniz
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

bot_process = None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="az">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SMC Bot Dashboard</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #121212; color: #ffffff; text-align: center; padding: 50px; }
        .container { max-width: 600px; margin: 0 auto; background: #1e1e1e; padding: 40px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        h1 { color: #00d2ff; }
        .status { margin: 20px 0; padding: 15px; border-radius: 8px; font-weight: bold; font-size: 1.2em; }
        .status.running { background-color: rgba(0, 255, 0, 0.1); color: #00ff00; border: 1px solid #00ff00; }
        .status.stopped { background-color: rgba(255, 0, 0, 0.1); color: #ff0000; border: 1px solid #ff0000; }
        .btn { display: inline-block; padding: 15px 30px; margin: 10px; font-size: 16px; font-weight: bold; cursor: pointer; border: none; border-radius: 8px; transition: 0.3s; text-decoration: none; }
        .btn-start { background-color: #28a745; color: white; }
        .btn-start:hover { background-color: #218838; }
        .btn-stop { background-color: #dc3545; color: white; }
        .btn-stop:hover { background-color: #c82333; }
        .btn-logout { background-color: #6c757d; color: white; padding: 10px 20px; font-size: 14px; }
        input[type="password"] { padding: 10px; border-radius: 5px; border: 1px solid #333; background: #222; color: white; margin-bottom: 20px; width: 80%; }
        input[type="submit"] { padding: 10px 20px; border-radius: 5px; border: none; background: #007bff; color: white; cursor: pointer; }
    </style>
</head>
<body>
    <div class="container">
        <h1>SMC Trading Bot</h1>
        
        {% if not logged_in %}
            <p>Daxil olmaq uçun şifrəni yazın:</p>
            <form method="POST" action="/login">
                <input type="password" name="password" placeholder="Şifrə" required><br>
                <input type="submit" value="Daxil Ol">
            </form>
            {% if error %}<p style="color:red">{{ error }}</p>{% endif %}
        {% else %}
            {% if is_running %}
                <div class="status running">Status: BOT İŞLƏYİR 🟢</div>
                <form method="POST" action="/stop"><button class="btn btn-stop" type="submit">Botu Dayandır</button></form>
            {% else %}
                <div class="status stopped">Status: DAYANIB 🔴</div>
                <form method="POST" action="/start"><button class="btn btn-start" type="submit">Botu Başlat</button></form>
            {% endif %}
            
            <br><br>
            <form method="POST" action="/logout"><button class="btn btn-logout" type="submit">Çıxış Et</button></form>
        {% endif %}
    </div>
</body>
</html>
"""

def is_bot_running():
    global bot_process
    if bot_process is None:
        return False
    return bot_process.poll() is None

@app.route("/")
def index():
    logged_in = session.get("logged_in", False)
    return render_template_string(HTML_TEMPLATE, logged_in=logged_in, is_running=is_bot_running())

@app.route("/login", methods=["POST"])
def login():
    if request.form.get("password") == ADMIN_PASSWORD:
        session["logged_in"] = True
        return redirect(url_for("index"))
    return render_template_string(HTML_TEMPLATE, logged_in=False, error="Səhv şifrə!")

@app.route("/logout", methods=["POST"])
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("index"))

@app.route("/start", methods=["POST"])
def start_bot():
    if not session.get("logged_in"):
        return redirect(url_for("index"))
    
    global bot_process
    if not is_bot_running():
        # Start main.py non-blocking
        bot_process = subprocess.Popen([sys.executable, "main.py"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return redirect(url_for("index"))

@app.route("/stop", methods=["POST"])
def stop_bot():
    if not session.get("logged_in"):
        return redirect(url_for("index"))
    
    global bot_process
    if is_bot_running():
        bot_process.terminate()
        try:
            bot_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            bot_process.kill()
        bot_process = None
    return redirect(url_for("index"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
