from flask import Flask, request, render_template_string
from user_agents import parse
import sqlite3
from datetime import datetime
import requests
import hashlib
import pytz  # ← Додаємо для правильного часу

app = Flask(__name__)
DB = "visitors.db"

# Часовий пояс України
KYIV_TZ = pytz.timezone('Europe/Kiev')

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
    
    new_columns = [
        ("referrer", "TEXT"), ("languages", "TEXT"), ("full_path", "TEXT"),
        ("country", "TEXT"), ("city", "TEXT"), ("region", "TEXT"),
        ("latitude", "REAL"), ("longitude", "REAL"), ("fingerprint", "TEXT"),
        ("screen_width", "INTEGER"), ("screen_height", "INTEGER"),
        ("screen_color_depth", "INTEGER"), ("pixel_ratio", "REAL"),
        ("avail_width", "INTEGER"), ("avail_height", "INTEGER"),
        ("screen_orientation", "TEXT"), ("hardware_concurrency", "INTEGER"),
        ("gpu_vendor", "TEXT"), ("gpu_renderer", "TEXT")
    ]
    
    for col_name, col_type in new_columns:
        try:
            cur.execute(f"ALTER TABLE visitors ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass
    
    conn.commit()
    conn.close()

init_db()

def get_geolocation(ip):
    if not ip or ip in ['127.0.0.1', '::1']:
        return {}, None
    try:
        r = requests.get(f"http://ip-api.com/json/{ip}?fields=status,message,country,regionName,city,lat,lon", timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "success":
                return data, None
    except:
        pass
    return {}, None

def generate_fingerprint(ip, ua_string):
    try:
        data = f"{ip}{ua_string}{request.headers.get('Accept-Language', '')}"
        return hashlib.md5(data.encode('utf-8')).hexdigest()[:16]
    except:
        return "unknown"

@app.route("/")
def index():
    return render_template_string("""
    <h1>Ласкаво просимо!</h1>
    <p>Ваш візит детально зареєстровано.</p>
    
    <script>
    const data = {
        screen_width: screen.width,
        screen_height: screen.height,
        screen_color_depth: screen.colorDepth,
        pixel_ratio: window.devicePixelRatio,
        avail_width: screen.availWidth,
        avail_height: screen.availHeight,
        screen_orientation: screen.orientation ? screen.orientation.type : 'unknown',
        hardware_concurrency: navigator.hardwareConcurrency || null,
        gpu_vendor: null,
        gpu_renderer: null
    };

    try {
        const canvas = document.createElement('canvas');
        const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
        if (gl) {
            const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
            if (debugInfo) {
                data.gpu_vendor = gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL);
                data.gpu_renderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
            }
        }
    } catch(e) {}

    fetch('/track', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    }).catch(() => {});
    </script>
    """)

@app.route("/track", methods=["POST"])
def track():
    try:
        client_data = request.get_json() or {}
        
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        if ',' in ip: 
            ip = ip.split(',')[0].strip()

        ua_string = request.headers.get("User-Agent", "")
        ua = parse(ua_string)

        geo_data, _ = get_geolocation(ip)
        fingerprint = generate_fingerprint(ip, ua_string)

        # Правильний час для України
        visit_time = datetime.now(KYIV_TZ).strftime("%Y-%m-%d %H:%M:%S")

        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        
        cur.execute("""
        INSERT INTO visitors 
        (visit_time, ip, browser, os, device, user_agent, referrer, languages, full_path,
         country, city, region, latitude, longitude, fingerprint,
         screen_width, screen_height, screen_color_depth, pixel_ratio,
         avail_width, avail_height, screen_orientation, hardware_concurrency,
         gpu_vendor, gpu_renderer)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            visit_time,
            ip,
            ua.browser.family or "Unknown",
            ua.os.family or "Unknown",
            ua.device.family or "Unknown",
            ua_string,
            request.referrer,
            str(request.accept_languages),
            request.url,
            geo_data.get("country"),
            geo_data.get("city"),
            geo_data.get("regionName"),
            geo_data.get("lat"),
            geo_data.get("lon"),
            fingerprint,
            client_data.get("screen_width"),
            client_data.get("screen_height"),
            client_data.get("screen_color_depth"),
            client_data.get("pixel_ratio"),
            client_data.get("avail_width"),
            client_data.get("avail_height"),
            client_data.get("screen_orientation"),
            client_data.get("hardware_concurrency"),
            client_data.get("gpu_vendor"),
            client_data.get("gpu_renderer")
        ))
        conn.commit()
        conn.close()
        
        return "ok", 200
    except Exception as e:
        print("Track error:", e)
        return "error", 500

@app.route("/admin")
def admin():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
    SELECT 
        visit_time, ip, country, city, browser, os, device,
        screen_width, screen_height, hardware_concurrency,
        gpu_vendor, gpu_renderer, referrer, fingerprint
    FROM visitors 
    ORDER BY id DESC
    """)
    rows = cur.fetchall()
    conn.close()

    html = """
    <h1>Відвідувачі — Розширена аналітика</h1>
    <p><a href="/admin/export">📥 Завантажити CSV</a></p>
    <table border="1" cellpadding="8" style="border-collapse: collapse; width: 100%; font-size: 14px;">
        <tr style="background: #f0f0f0;">
            <th>Час (Київ)</th><th>IP</th><th>Країна</th><th>Місто</th>
            <th>Браузер</th><th>ОС</th><th>Пристрій</th>
            <th>Екран</th><th>CPU ядер</th><th>GPU Vendor</th><th>GPU Renderer</th>
            <th>Referrer</th><th>Fingerprint</th>
        </tr>
    """
    for row in rows:
        screen = f"{row[7]}×{row[8]}" if row[7] and row[8] else "-"
        html += f"""
        <tr>
            <td>{row[0]}</td><td>{row[1]}</td><td>{row[2] or '-'}</td><td>{row[3] or '-'}</td>
            <td>{row[4]}</td><td>{row[5]}</td><td>{row[6]}</td>
            <td>{screen}</td><td>{row[9] or '-'}</td>
            <td>{row[10] or '-'}</td><td>{row[11] or '-'}</td>
            <td>{row[12] or '-'}</td><td>{row[13]}</td>
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
    csv.writer(si).writerows([columns] + rows)
    return si.getvalue(), 200, {
        'Content-Type': 'text/csv',
        'Content-Disposition': f'attachment; filename=visitors_{datetime.now(KYIV_TZ).strftime("%Y%m%d_%H%M")}.csv'
    }

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
