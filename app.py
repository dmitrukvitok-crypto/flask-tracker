from flask import Flask, request, render_template_string
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
        user_agent TEXT
    )
    """)

    conn.commit()
    conn.close()


init_db()


@app.route("/")
def index():

    forwarded = request.headers.get("X-Forwarded-For")

    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.remote_addr

    ua_string = request.headers.get("User-Agent", "")
    ua = parse(ua_string)

    browser = ua.browser.family
    os_name = ua.os.family
    device = ua.device.family

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO visitors
    (visit_time, ip, browser, os, device, user_agent)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ip,
        browser,
        os_name,
        device,
        ua_string
    ))

    conn.commit()
    conn.close()

    return """
    <h1>Ласкаво просимо!</h1>
    <p>Ваш візит зареєстровано.</p>
    """


@app.route("/admin")
def admin():

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("""
    SELECT visit_time, ip, browser, os, device
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
        </tr>
        """

    html += "</table>"

    return render_template_string(html)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
