import os
import sqlite3
import subprocess
from pathlib import Path
from flask import Flask, jsonify, render_template
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

# Charge le .env depuis la racine du projet
load_dotenv(Path(__file__).resolve().parent / '.env')

app = Flask(__name__)

# Config
DB_PATH     = os.getenv("DB_PATH",     str(Path(__file__).resolve().parent))
SCRIPT_DIR  = os.getenv("SCRIPT_DIR",  str(Path(__file__).resolve().parent))
MAIN_SCRIPT = os.getenv("MAIN_SCRIPT", str(Path(SCRIPT_DIR) / "Main.py"))


def run_main_script():
    try:
        subprocess.run(["python3", MAIN_SCRIPT], check=True, cwd=SCRIPT_DIR)
        print(f"[scheduler] Main.py exécuté avec succès")
    except Exception as e:
        print(f"[scheduler] Erreur : {e}")


scheduler = BackgroundScheduler()
scheduler.add_job(run_main_script, "interval", minutes=5, id="main_job", name="Run anomaly detection")
if not scheduler.running:
    scheduler.start()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn, name):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/anomalies")
def api_anomalies():
    conn = get_conn()
    if not table_exists(conn, "anomaly_groups"):
        conn.close()
        return jsonify([])
    rows = conn.execute("""
        SELECT
            group_id,
            source,
            group_start  AS timestamp,
            action,
            max_temp     AS temperature,
            threshold,
            avg_cpu      AS cpu,
            avg_ram      AS ram,
            duration
        FROM anomaly_groups
        ORDER BY group_start DESC
        LIMIT 100
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/groups")
def api_groups():
    conn = get_conn()
    if not table_exists(conn, "anomaly_groups"):
        conn.close()
        return jsonify([])
    rows = conn.execute("""
        SELECT group_id, source, group_start, group_end, count,
               action AS max_action, max_temp, avg_cpu, avg_ram, notified, created_at
        FROM anomaly_groups
        ORDER BY group_start DESC
        LIMIT 50
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/stats")
def api_stats():
    conn = get_conn()
    stats = {
        "total_anomalies": 0,
        "total_groups":    0,
        "critical_groups": 0,
        "last_seen":       None,
    }
    if table_exists(conn, "anomaly_groups"):
        stats["total_groups"]    = conn.execute("SELECT COUNT(*) FROM anomaly_groups").fetchone()[0]
        stats["critical_groups"] = conn.execute(
            "SELECT COUNT(*) FROM anomaly_groups WHERE action = 'critical'"
        ).fetchone()[0]
        stats["total_anomalies"] = conn.execute("SELECT SUM(count) FROM anomaly_groups").fetchone()[0] or 0
        row = conn.execute("SELECT MAX(group_start) FROM anomaly_groups").fetchone()
        stats["last_seen"] = row[0] if row else None
    conn.close()
    return jsonify(stats)


@app.route("/api/metadata")
def api_metadata():
    conn = get_conn()
    if not table_exists(conn, "metadata"):
        conn.close()
        return jsonify({})
    rows = conn.execute("SELECT key, value FROM metadata").fetchall()
    conn.close()
    return jsonify({r["key"]: r["value"] for r in rows})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)