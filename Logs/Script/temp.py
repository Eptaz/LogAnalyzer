import os
import csv
import json
import datetime as dt
from pathlib import Path
from dotenv import load_dotenv

# Charge le .env depuis la racine du projet
load_dotenv(Path(__file__).resolve().parents[2] / '.env')

# Chemins
base_dir = Path(__file__).resolve().parents[2]
LOG_ROOT = Path(os.environ.get('LOG_ROOT', str(base_dir / 'Logs')))
LOG_ROOT.mkdir(parents=True, exist_ok=True)

chemin = LOG_ROOT / 'temp.csv'

# Lecture température CPU (Raspberry Pi)
with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
    current_temp = int(f.read()) / 1000

timestamp = dt.datetime.now().isoformat(timespec="seconds")

# Écriture CSV (historique)
with open(chemin, "a", newline="", encoding="utf-8") as f:
    writer = csv.writer(f, delimiter=";")
    writer.writerow([timestamp, current_temp])

# Publish MQTT (temps réel)
try:
    import paho.mqtt.publish as publish
    payload = json.dumps({"timestamp": timestamp, "temperature": current_temp})
    publish.single(
        os.environ.get('MQTT_TOPIC_TEMP', 'piloganalyzer/temp'),
        payload=payload,
        hostname=os.environ.get('MQTT_BROKER', 'localhost'),
        port=int(os.environ.get('MQTT_PORT', '1883')),
        qos=1,
    )
except Exception as e:
    print(f"[mqtt] Publish échoué : {e}")
