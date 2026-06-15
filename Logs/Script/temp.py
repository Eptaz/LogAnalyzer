import os
import csv
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

# Écriture
timestamp = dt.datetime.now().isoformat(timespec="seconds")

with open(chemin, "a", newline="", encoding="utf-8") as f:
    writer = csv.writer(f, delimiter=";")
    writer.writerow([timestamp, current_temp])