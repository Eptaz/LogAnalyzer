# LogAnalyzer

A lightweight anomaly detection and monitoring tool for Raspberry Pi, built around CSV temperature and CPU/RAM logs. Detects anomalies, groups them by incident, stores results in SQLite, sends push notifications via [ntfy](https://ntfy.sh), and exposes a web dashboard.

Built because existing monitoring solutions (Prometheus, Grafana, InfluxDB…) are too heavy to run comfortably on a Raspberry Pi 5 2 GB. LogAnalyzer is designed from the ground up to stay lean — no bloated stack, just what's needed to detect and report anomalies without taxing a constrained device.

---

## Features

- Parses temperature (`temp.csv`) and CPU/RAM (`Cpu.csv`) logs collected on a Raspberry Pi
- Detects anomalies based on a configurable multiplier over the historical average
- Groups consecutive anomalies into incidents with duration, severity, and aggregated stats
- Persists results to a SQLite database (`anomaly_groups`, `metadata`, `processed_files`)
- Sends push notifications via ntfy when new anomaly groups are detected
- Flask web dashboard showing recent anomalies and group summaries
- Scheduler runs anomaly detection every 5 minutes inside the dashboard process
- Fully configurable via environment variables — no hardcoded paths
- Lightweight footprint: ~43 MB RAM in operation (measured via VmRSS on Raspberry Pi 5 2 GB)

---

# Interface

<img width="1888" height="915" alt="image" src="https://github.com/user-attachments/assets/9e864ea8-8675-41f3-ae06-2b929a882d9b" />


## Project Structure

```
LogAnalyzer/
├── Main.py                  # Core detection engine
├── app.py                   # Flask dashboard + APScheduler
├── templates/
│   └── index.html           # Dashboard UI
├── Logs/
│   ├── temp.csv             # Live temperature readings (written by temp.py)
│   ├── Cpu.csv              # Live CPU/RAM readings (written by Cpu.py)
│   ├── anomalies.db         # SQLite database (generated at runtime)
│   ├── Historique/
│   │   ├── Temps/           # Archived daily temperature CSVs
│   │   ├── CPU/             # Archived daily CPU/RAM CSVs
│   │   └── Moyennes/        # Archived daily average CSVs
│   └── Script/
│       ├── debug/           # Debug and error logs
│       ├── temp.py          # Records CPU temperature to temp.csv
│       ├── Cpu.py           # Records CPU/RAM usage to Cpu.csv
│       ├── Moyenne.py       # Computes daily averages
│       ├── header.py        # Reinitializes CSV headers after daily rotation
│       ├── log.sh           # Runs Moyenne.py with logging
│       └── Saving.sh        # Archives CSVs, rotates logs, cleans files > 30 days
├── .env.example             # Environment variable template
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## Requirements

- Python 3.10+
- Raspberry Pi (or any Linux system with `/sys/class/thermal/thermal_zone0/temp`)
- [ntfy](https://ntfy.sh) account or self-hosted instance for notifications (optional)

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/Eptaz/LogAnalyzer.git
cd LogAnalyzer
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your paths:

```env
PROJECT_ROOT=/path/to/project
LOG_ROOT=/path/to/Logs
SCRIPT_DIR=/path/to/Logs/Script
DEBUG_DIR=/path/to/Logs/Script/debug

DB_PATH=Logs/anomalies.db
MAIN_SCRIPT=/path/to/Main.py

NTFY_TOPIC=your-topic
NTFY_URL=https://ntfy.sh
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the detection engine

```bash
python Main.py
```

### 5. Start the dashboard

```bash
python app.py
```

Open `http://localhost:5000` in your browser.

---

## Docker

```bash
docker compose up -d
```

The dashboard will be available at `http://localhost:5000`. The anomaly detection engine runs automatically every 5 minutes inside the container.

Make sure your `.env` is configured before starting.

---

## How Detection Works

1. **Data collection** — `temp.py` and `Cpu.py` append timestamped readings to CSV files every minute via cron.
2. **Daily rotation** — `Saving.sh` archives the current CSV to `Logs/Historique/`, resets the header, and deletes files older than 30 days.
3. **Anomaly detection** — `Main.py` reads current and historical CSVs, computes the average temperature, and flags any reading above `average × threshold_multiplier` (default: `2.0`).
4. **Grouping** — Consecutive anomalies from the same source within 2 minutes are grouped into a single incident with aggregated stats (max temp, avg CPU/RAM, duration, severity).
5. **Persistence** — Groups are upserted into `anomaly_groups` in SQLite. Already-processed files are tracked in `processed_files` to avoid reprocessing.
6. **Notifications** — New unnotified groups trigger a push notification via ntfy. Once sent, the group is marked `notified = 1`.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LOG_ROOT` | `./Logs` | Root directory for CSV log files |
| `DB_PATH` | `Logs/anomalies.db` | Path to the SQLite database |
| `SCRIPT_DIR` | script directory | Directory containing Python scripts |
| `MAIN_SCRIPT` | `Main.py` | Path to the detection script |
| `NTFY_TOPIC` | `loganalyzer` | ntfy topic for push notifications |
| `NTFY_URL` | `https://ntfy.sh` | ntfy server URL |

---

## Cron Setup (Raspberry Pi)

Example crontab for automated data collection and daily rotation:

```cron
# Record temperature every minute
* * * * * python3 /path/to/Logs/Script/temp.py

# Record CPU/RAM every minute
* * * * * python3 /path/to/Logs/Script/Cpu.py

# Daily rotation at midnight
0 0 * * * bash /path/to/Logs/Script/Saving.sh
```

---

## Roadmap

- [x] Anomaly detection from CSV logs
- [x] Incident grouping with severity levels
- [x] SQLite persistence with deduplication
- [x] Push notifications via ntfy
- [x] Web dashboard (Flask)
- [x] Docker support
- [ ] Alert thresholds configurable per source
- [ ] Email notification support
- [ ] Grafana integration

---

## License

MIT
