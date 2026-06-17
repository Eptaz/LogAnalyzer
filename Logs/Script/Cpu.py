import os
import psutil
import time
import datetime as dt
import csv
import json
from pathlib import Path

# Determine LOG_ROOT from environment (.env in project root) or fallback to repo Logs
base_dir = Path(__file__).resolve().parents[2]
LOG_ROOT = Path(os.environ.get('LOG_ROOT', str(base_dir / 'Logs')))

chemin = LOG_ROOT / 'Cpu.csv'
timestamp = dt.datetime.now().isoformat(timespec="seconds")

# Première mesure (initialisation)
psutil.cpu_percent(interval=None)
mem = psutil.virtual_memory()
time.sleep(1)

cpu_percent = psutil.cpu_percent(interval=1)
ram_mb = round(mem.used / 1024**2.0, 1)
ram_pct = mem.percent

# Écriture CSV (historique)
with open(chemin, "a", newline="", encoding="utf-8") as f:
    writer = csv.writer(f, delimiter=";")
    print(f"CPU total : {cpu_percent:.1f} %")
    writer.writerow([timestamp, cpu_percent, ram_mb, ram_pct])

# Publish MQTT (temps réel)
try:
    import paho.mqtt.publish as publish
    payload = json.dumps({
        "timestamp": timestamp,
        "cpu": cpu_percent,
        "ram_mb": ram_mb,
        "ram_pct": ram_pct,
    })
    publish.single(
        os.environ.get('MQTT_TOPIC_CPU', 'piloganalyzer/cpu'),
        payload=payload,
        hostname=os.environ.get('MQTT_BROKER', 'localhost'),
        port=int(os.environ.get('MQTT_PORT', '1883')),
        qos=1,
    )
except Exception as e:
    print(f"[mqtt] Publish échoué : {e}")
