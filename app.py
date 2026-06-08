from flask import Flask, request, render_template_string, jsonify
from user_agents import parse
import sqlite3
from datetime import datetime

app = Flask(__name__)

DB = "visitors.db"


def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS visitors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        visit_time TEXT,
        ip TEXT,
        browser TEXT,
        os TEXT,
        device TEXT,
        screen TEXT,
        language TEXT,
        timezone TEXT,
        cpu TEXT,
        memory TEXT
    )
    """)

    conn.commit()
    conn.close()


init_db()


@app.route("/")
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Visitor Tracker</title>
    </head>
    <body>

    <h1>Ласкаво просимо!</h1>
    <p>Ваш візит зареєстровано.</p>

    <script>
    fetch("/track", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            screen: screen.width + "x" + screen.height,
            language: navigator.language,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            cpu: navigator.hardwareConcurrency,
            memory: navigator.deviceMemory || "невідомо"
        })
    });
    </script>

    </body>
    </html>
    """


@app.route("/track", methods=["POST"])
def track():

    data = request.get_json()

    forwarded = request.headers.get("X-Forwarded-For")

    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.remote_addr

    ua_string = request.headers.get("User-Agent", "")
    ua = parse(ua_string)

    browser = f"{ua.browser.family} {ua.browser.version_string}"
    os_name = f"{ua.os.family} {ua.os.version_string}"
    device = ua.device.family

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO visitors (
        visit_time,
        ip,
        browser,
        os,
        device,
        screen,
        language,
        timezone,
        cpu,
        memory
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ip,
        browser,
        os_name,
        device,
        data.get("screen"),
        data.get("language"),
        data.get("timezone"),
        str(data.get("cpu")),
        str(data.get("memory"))
    ))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@app.route("/admin")
def admin():

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("""
    SELECT
        visit_time,
        ip,
        browser,
        os,
        device,
        screen,
        language,
        timezone,
        cpu,
        memory
    FROM visitors
    ORDER BY id DESC
    """)

    rows = cur.fetchall()
    conn.close()

    html = """
    <h1>Відвідувачі</h1>

    <table border="1" cellpadding="5">
        <tr>
            <th>Час</th>
            <th>IP</th>
            <th>Браузер</th>
            <th>ОС</th>
            <th>Пристрій</th>
            <th>Екран</th>
            <th>Мова</th>
            <th>Часовий пояс</th>
            <th>CPU</th>
            <th>RAM</th>
        </tr>
    """

    for row in rows:
        html += f"""
        <tr>
            <td>{row[0]}</td>
            <td>{row[1]}</td>
            <td>{row[2]}</td>
            <td>{row[3]}</td>
            <td>{row[4]}</td>
            <td>{row[5]}</td>
            <td>{row[6]}</td>
            <td>{row[7]}</td>
            <td>{row[8]}</td>
            <td>{row[9]}</td>
        </tr>
        """

    html += "</table>"

    return render_template_string(html)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
