from flask import Flask, request, render_template_string
from user_agents import parse
import sqlite3
from datetime import datetime
import requests
import hashlib

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
        user_agent TEXT,
        referrer TEXT,
        languages TEXT,
        full_path TEXT,
        country TEXT,
        city TEXT,
        region TEXT,
        latitude REAL,
        longitude REAL,
        fingerprint TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

def get_geolocation(ip):
    """Безкоштовний geo lookup"""
    if not ip or ip in ['127.0.0.1', '::1']:
        return {}, None
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,regionName,city,lat,lon", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                return data, None
            return {}, data.get("message")
    except Exception as e:
        return {}, str(e)
    return {}, None

def generate_fingerprint(ip, ua_string):
    """Простий fingerprint"""
    data = f"{ip}{ua_string}{request.headers.get('Accept-Language', '')}"
    return hashlib.md5(data.encode()).hexdigest()[:16]

@app.route("/")
def index():
    # IP
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ',' in ip:
        ip = ip.split(',')[0].strip()

    ua_string = request.headers.get("User-Agent", "")
    ua = parse(ua_string)

    # Geo
    geo_data, geo_error = get_geolocation(ip)

    # Fingerprint
    fingerprint = generate_fingerprint(ip, ua_string)

    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO visitors 
    (visit_time, ip, browser, os, device, user_agent, referrer, languages, 
     full_path, country, city, region, latitude, longitude, fingerprint)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        ip,
        ua.browser.family,
        ua.os.family,
        ua.device.family,
        ua_string,
        request.referrer,
        request.accept_languages,
        request.url,
        geo_data.get("country"),
        geo_data.get("city"),
        geo_data.get("regionName"),
        geo_data.get("lat"),
        geo_data.get("lon"),
        fingerprint
    ))
    conn.commit()
    conn.close()

    return """
    <h1>Ласкаво просимо!</h1>
    <p>Ваш візит детально зареєстровано.</p>
    """

@app.route("/admin")
def admin():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
    SELECT 
        visit_time, ip, country, city, browser, os, device, 
        referrer, languages, fingerprint
    FROM visitors 
    ORDER BY id DESC
    """)
    rows = cur.fetchall()
    conn.close()

    html = """
    <h1>Відвідувачі — Розширена аналітика</h1>
    <p><a href="/admin/export">Завантажити CSV</a></p>
    <table border="1" cellpadding="8" style="border-collapse: collapse; width: 100%;">
        <tr style="background: #f0f0f0;">
            <th>Час (UTC)</th>
            <th>IP</th>
            <th>Країна</th>
            <th>Місто</th>
            <th>Браузер</th>
            <th>ОС</th>
            <th>Пристрій</th>
            <th>Referrer</th>
            <th>Мови</th>
            <th>Fingerprint</th>
        </tr>
    """
    for row in rows:
        html += f"""
        <tr>
            <td>{row[0]}</td>
            <td>{row[1]}</td>
            <td>{row[2] or '-'}</td>
            <td>{row[3] or '-'}</td>
            <td>{row[4]}</td>
            <td>{row[5]}</td>
            <td>{row[6]}</td>
            <td>{row[7] or '-'}</td>
            <td>{row[8] or '-'}</td>
            <td>{row[9]}</td>
        </tr>
        """
    html += "</table>"
    return render_template_string(html)

@app.route("/admin/export")
def export_csv():
    import csv
    from io import StringIO

    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT * FROM visitors ORDER BY id DESC")
    rows = cur.fetchall()
    columns = [description[0] for description in cur.description]
    conn.close()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(columns)
    cw.writerows(rows)

    return si.getvalue(), 200, {
        'Content-Type': 'text/csv',
        'Content-Disposition': 'attachment; filename=visitors_export.csv'
    }

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
