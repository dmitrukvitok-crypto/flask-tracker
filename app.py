from flask import Flask, request, render_template_string
from user_agents import parse
import sqlite3
from datetime import datetime, timedelta
import requests
import hashlib
import threading
import time

app = Flask(__name__)

DB = "visitors.db"


# ---------- Автопінг Render ----------
def keep_alive():
    while True:
        try:
            requests.get(
                "https://flask-tracker-hn13.onrender.com/ping",
                timeout=10
            )
        except:
            pass

        time.sleep(600)


threading.Thread(
    target=keep_alive,
    daemon=True
).start()


# ---------- Ініціалізація БД ----------
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

        country TEXT,
        city TEXT,
        region TEXT,
        latitude REAL,
        longitude REAL,

        referrer TEXT,
        languages TEXT,
        full_path TEXT,

        fingerprint TEXT,

        screen_width INTEGER,
        screen_height INTEGER,
        screen_color_depth INTEGER,

        avail_width INTEGER,
        avail_height INTEGER,

        pixel_ratio REAL,
        screen_orientation TEXT,

        hardware_concurrency INTEGER,

        gpu_vendor TEXT,
        gpu_renderer TEXT,

        ua_model TEXT,
        ua_full_version TEXT,
        platform TEXT,
        platform_version TEXT,
        architecture TEXT,
        mobile INTEGER
    )
    """)

    conn.commit()
    conn.close()


init_db()


# ---------- Геолокація ----------
def get_geolocation(ip):
    if ip in ["127.0.0.1", "::1"]:
        return {}

    try:
        r = requests.get(
            f"http://ip-api.com/json/{ip}?fields=status,country,regionName,city,lat,lon",
            timeout=5
        )

        if r.status_code == 200:
            data = r.json()

            if data.get("status") == "success":
                return data

    except:
        pass

    return {}


# ---------- Fingerprint ----------
def generate_fingerprint(ip, ua_string):
    text = (
        ip
        + ua_string
        + request.headers.get("Accept-Language", "")
    )

    return hashlib.md5(
        text.encode("utf-8")
    ).hexdigest()[:16]


# ---------- Ping ----------
@app.route("/ping")
def ping():
    return "ok", 200
# ---------- Головна сторінка ----------
@app.route("/")
def index():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Welcome</title>
</head>
<body>

<img src="{{ url_for('static', filename='welcome.jpg.png') }}">
     alt="Welcome"
     style="max-width:100%; height:auto;">

<script>
async function collectData() {

    let data = {

        screen_width: screen.width,
        screen_height: screen.height,
        screen_color_depth: screen.colorDepth,

        avail_width: screen.availWidth,
        avail_height: screen.availHeight,

        pixel_ratio: window.devicePixelRatio,

        screen_orientation:
            screen.orientation
            ? screen.orientation.type
            : "unknown",

        hardware_concurrency:
            navigator.hardwareConcurrency || null,

        gpu_vendor: null,
        gpu_renderer: null,

        ua_model: null,
        ua_full_version: null,
        platform: navigator.platform,
        platform_version: null,
        architecture: null,
        mobile: null
    };


    // ---------- User-Agent Client Hints ----------
    if (navigator.userAgentData) {

        try {

            const info =
                await navigator.userAgentData.getHighEntropyValues([
                    "architecture",
                    "model",
                    "platformVersion",
                    "uaFullVersion"
                ]);

            data.ua_model = info.model;
            data.ua_full_version = info.uaFullVersion;
            data.platform_version = info.platformVersion;
            data.architecture = info.architecture;

            data.mobile =
                navigator.userAgentData.mobile;

        }
        catch (e) {
            console.log(e);
        }
    }


    // ---------- GPU ----------
    try {

        const canvas =
            document.createElement("canvas");

        const gl =
            canvas.getContext("webgl")
            || canvas.getContext("experimental-webgl");

        if (gl) {

            const debugInfo =
                gl.getExtension(
                    "WEBGL_debug_renderer_info"
                );

            if (debugInfo) {

                data.gpu_vendor =
                    gl.getParameter(
                        debugInfo.UNMASKED_VENDOR_WEBGL
                    );

                data.gpu_renderer =
                    gl.getParameter(
                        debugInfo.UNMASKED_RENDERER_WEBGL
                    );
            }
        }

    }
    catch (e) {
        console.log(e);
    }


    // ---------- Надсилання ----------
    fetch("/track", {
        method: "POST",

        headers: {
            "Content-Type": "application/json"
        },

        body: JSON.stringify(data)

    }).catch(() => {});
}

collectData();

</script>

</body>
</html>
""")
# ---------- Track ----------
@app.route("/track", methods=["POST"])
def track():

    try:
        client_data = request.get_json() or {}

        ip = request.headers.get(
            "X-Forwarded-For",
            request.remote_addr
        )

        if "," in ip:
            ip = ip.split(",")[0].strip()

        ua_string = request.headers.get(
            "User-Agent",
            ""
        )

        ua = parse(ua_string)

        geo_data = get_geolocation(ip)

        fingerprint = generate_fingerprint(
            ip,
            ua_string
        )

        kyiv_time = (
            datetime.utcnow()
            + timedelta(hours=3)
        )

        visit_time = kyiv_time.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        conn = sqlite3.connect(DB)
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO visitors (

            visit_time,
            ip,

            browser,
            os,
            device,

            user_agent,

            country,
            city,
            region,
            latitude,
            longitude,

            referrer,
            languages,
            full_path,

            fingerprint,

            screen_width,
            screen_height,
            screen_color_depth,

            avail_width,
            avail_height,

            pixel_ratio,
            screen_orientation,

            hardware_concurrency,

            gpu_vendor,
            gpu_renderer,

            ua_model,
            ua_full_version,
            platform,
            platform_version,
            architecture,
            mobile

        )
      VALUES (
    ?,?,?,?,?,?,
    ?,?,?,?,?,
    ?,?,?,?,
    ?,?,?,
    ?,?,
    ?,?,
    ?,?,
    ?,?,?,?,?,
    ?,?
)
        """, (

            visit_time,
            ip,

            ua.browser.family or "Unknown",
            ua.os.family or "Unknown",
            ua.device.family or "Unknown",

            ua_string,

            geo_data.get("country"),
            geo_data.get("city"),
            geo_data.get("regionName"),
            geo_data.get("lat"),
            geo_data.get("lon"),

            request.referrer,

            str(request.accept_languages),

            request.url,

            fingerprint,

            client_data.get("screen_width"),
            client_data.get("screen_height"),
            client_data.get("screen_color_depth"),

            client_data.get("avail_width"),
            client_data.get("avail_height"),

            client_data.get("pixel_ratio"),
            client_data.get("screen_orientation"),

            client_data.get("hardware_concurrency"),

            client_data.get("gpu_vendor"),
            client_data.get("gpu_renderer"),

            client_data.get("ua_model"),
            client_data.get("ua_full_version"),
            client_data.get("platform"),
            client_data.get("platform_version"),
            client_data.get("architecture"),
            int(client_data.get("mobile"))
            if client_data.get("mobile") is not None
            else None

        ))

        conn.commit()
        conn.close()

        return "ok", 200

    except Exception as e:
        print("Track error:", e)
        return "error", 500
# ---------- Admin ----------
@app.route("/admin")
def admin():

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("""
    SELECT

        visit_time,
        ip,

        country,
        city,

        browser,
        os,
        device,

        ua_model,

        screen_width,
        screen_height,

        hardware_concurrency,

        gpu_vendor,
        gpu_renderer,

        fingerprint,

        user_agent

    FROM visitors

    ORDER BY id DESC
    """)

    rows = cur.fetchall()

    conn.close()

    html = """
    <h1>Відвідувачі</h1>

    <p>
        <a href="/admin/export">
            📥 Завантажити CSV
        </a>
    </p>

    <table border="1"
           cellpadding="6"
           style="border-collapse:collapse;font-size:14px;">

        <tr style="background:#eeeeee">

            <th>Час (Київ)</th>
            <th>IP</th>

            <th>Країна</th>
            <th>Місто</th>

            <th>Браузер</th>
            <th>ОС</th>
            <th>Пристрій</th>

            <th>Модель</th>

            <th>Екран</th>

            <th>CPU ядер</th>

            <th>GPU Vendor</th>
            <th>GPU Renderer</th>

            <th>Fingerprint</th>

            <th>User-Agent</th>

        </tr>
    """

    for row in rows:

        screen = "-"

        if row[8] and row[9]:
            screen = f"{row[8]}×{row[9]}"

        html += f"""

        <tr>

            <td>{row[0]}</td>

            <td>{row[1]}</td>

            <td>{row[2] or "-"}</td>
            <td>{row[3] or "-"}</td>

            <td>{row[4]}</td>
            <td>{row[5]}</td>
            <td>{row[6]}</td>

            <td>{row[7] or "-"}</td>

            <td>{screen}</td>

            <td>{row[10] or "-"}</td>

            <td>{row[11] or "-"}</td>
            <td>{row[12] or "-"}</td>

            <td>{row[13]}</td>

            <td style="max-width:700px;word-break:break-all;">
                {row[14]}
            </td>

        </tr>
        """

    html += "</table>"

    return render_template_string(html)
# ---------- Export CSV ----------
@app.route("/admin/export")
def export_csv():

    import csv
    from io import StringIO

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("""
    SELECT *
    FROM visitors
    ORDER BY id DESC
    """)

    rows = cur.fetchall()

    columns = [
        description[0]
        for description in cur.description
    ]

    conn.close()

    si = StringIO()

    writer = csv.writer(si)

    writer.writerow(columns)

    for row in rows:
        writer.writerow(row)

    return (
        si.getvalue(),
        200,
        {
            "Content-Type": "text/csv",
            "Content-Disposition":
                "attachment; filename=visitors.csv"
        }
    )


# ---------- Запуск ----------
if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
