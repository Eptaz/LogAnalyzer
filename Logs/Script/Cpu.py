import os
import psutil
import time
import datetime as dt
import csv
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


with open(chemin, "a", newline="", encoding="utf-8") as f:
    writer = csv.writer(f, delimiter=";")
    cpu_percent = psutil.cpu_percent(interval=1)
    print(f"CPU total : {cpu_percent:.1f} %")
    writer.writerow([timestamp, cpu_percent, round(mem.used/1024**2.0,1), mem.percent])

