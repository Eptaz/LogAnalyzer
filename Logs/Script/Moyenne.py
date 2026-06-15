import os
import csv
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Charge le .env depuis la racine du projet
load_dotenv(Path(__file__).resolve().parents[2] / '.env')

# Chemins
base_dir = Path(__file__).resolve().parents[2]
LOG_ROOT = Path(os.environ.get('LOG_ROOT', str(base_dir / 'Logs')))

chemin = LOG_ROOT / 'temp.csv'
output_dir = LOG_ROOT / 'Historique' / 'Moyennes'
output_dir.mkdir(parents=True, exist_ok=True)

# Lecture
temperatures = []

with open(chemin, "r", encoding="utf-8") as f:
    reader = csv.reader(f, delimiter=";")
    for row in reader:
        try:
            timestamp = datetime.fromisoformat(row[0])
            temp = float(row[1])
            temperatures.append((timestamp, temp))
        except (ValueError, IndexError):
            continue

if not temperatures:
    raise RuntimeError("Aucune donnée exploitable")

# Calculs
min_entry = min(temperatures, key=lambda x: x[1])
max_entry = max(temperatures, key=lambda x: x[1])
avg_temp  = sum(t[1] for t in temperatures) / len(temperatures)

# Écriture
date_str    = temperatures[0][0].date().isoformat()
output_file = output_dir / f"moyenne-{date_str}.csv"

with open(output_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f, delimiter=";")
    writer.writerow(["type", "temperature", "heure"])
    writer.writerow(["min", f"{min_entry[1]:.2f}", min_entry[0].time().isoformat()])
    writer.writerow(["max", f"{max_entry[1]:.2f}", max_entry[0].time().isoformat()])
    writer.writerow(["avg", f"{avg_temp:.2f}", ""])

print(f"Résumé sauvegardé dans : {output_file}")