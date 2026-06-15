import os
import csv
from pathlib import Path
from dotenv import load_dotenv

# Charge le .env depuis la racine du projet
load_dotenv(Path(__file__).resolve().parents[2] / '.env')

# Chemins
base_dir = Path(__file__).resolve().parents[2]
LOG_ROOT = Path(os.environ.get('LOG_ROOT', str(base_dir / 'Logs')))
LOG_ROOT.mkdir(parents=True, exist_ok=True)

# Init temp.csv
with open(LOG_ROOT / 'temp.csv', "w", newline='', encoding="utf-8") as f:
    writer = csv.writer(f, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["date T heure", "temperature", "° C"])

# Init Cpu.csv
with open(LOG_ROOT / 'Cpu.csv', "w", newline='', encoding="utf-8") as f:
    writer = csv.writer(f, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["date T heure", "CPU", "RAM Mb", "RAM %"])

print(f"Fichiers initialisés dans : {LOG_ROOT}")