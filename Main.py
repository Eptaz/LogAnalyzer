import csv
import json
import os
import sqlite3
import urllib.error
import urllib.request
from datetime import timezone
import math
import re
from datetime import datetime
from pathlib import Path
import hashlib
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent / '.env')



Chemin= "Logs/temp.csv"
pattern = r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2});(\d+(?:\.\d+)?)"
Liste = []

Old_temps = []





def read_temps(file_path):
    temps = []
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        for line in lines[1:]:
            line = line.strip()
            m = re.search(pattern, line)
            if m:
                timestamp = f"{m.group(1)}T{m.group(2)}"
                temps.append((timestamp, float(m.group(3))))
    return temps
    

def Set_average():
    Old_temps.clear()
    repertoire = Path('./Logs/Historique/Temps') # Mettre le chemin de votre dossier ici
    for element in repertoire.iterdir():
        if element.is_file():
            temps = read_temps(element)
            print(f"Fichier : {element.name}")
            Old_temps.extend(temps)
    Average = sum(temp for _, temp in Old_temps) / len(Old_temps)
    return Average

def read_cpu_ram(file_path):
    records = []
    with open(file_path, "r", encoding="utf-8", newline='') as f:
        reader = csv.reader(f, delimiter=';')
        next(reader, None)
        for row in reader:
            if len(row) < 4:
                continue
            ts = row[0].strip()
            try:
                timestamp = datetime.fromisoformat(ts)
                cpu = float(row[1].strip().replace(',', '.'))
                ram_pct = float(row[3].strip().replace(',', '.'))
            except ValueError:
                continue
            records.append((timestamp, cpu, ram_pct))
    return records


def read_cpu_history(directory='./Logs/Historique/CPU'):
    records = []
    for element in Path(directory).iterdir():
        if element.is_file():
            records.extend(read_cpu_ram(element))
    return records


def read_cpu_ram_map(file_path='Logs/Cpu.csv', history_dir='./Logs/Historique/CPU'):
    cpu_ram_map = {}
    # read historical CPU logs first, then current file to allow current values to override if timestamps overlap
    for timestamp, cpu, ram_pct in read_cpu_history(history_dir):
        cpu_ram_map[timestamp] = (cpu, ram_pct)
    for timestamp, cpu, ram_pct in read_cpu_ram(file_path):
        cpu_ram_map[timestamp] = (cpu, ram_pct)
    return cpu_ram_map


def find_cpu_ram(timestamp, cpu_ram_map, max_diff_seconds=3):
    if timestamp in cpu_ram_map:
        return cpu_ram_map[timestamp]
    closest = None
    closest_diff = None
    for ts, vals in cpu_ram_map.items():
        diff = abs((ts - timestamp).total_seconds())
        if closest_diff is None or diff < closest_diff:
            closest_diff = diff
            closest = vals
    if closest_diff is not None and closest_diff <= max_diff_seconds:
        return closest
    return (None, None)


def format_duration(duration_seconds):
    minutes, seconds = divmod(int(duration_seconds), 60)
    if minutes:
        return f"{minutes}m{seconds}s"
    return f"{seconds}s"


def get_action_level(temperature, threshold, cpu, ram, duration_seconds=0):
    # Température très élevée sur le Raspberry Pi : devenir critique si elle dure longtemps
    if temperature >= 90 and duration_seconds >= 120:
        return 'critical'
    if temperature >= threshold * 1.3 or cpu >= 95 or ram >= 90:
        return 'critical'
    if temperature >= threshold * 1.1 or cpu >= 90 or ram >= 80:
        return 'warning'
    return 'normal'


def group_anomalies(anomalies, max_gap_seconds=120, interval_seconds=60):
    for anomaly in anomalies:
        anomaly['_dt'] = datetime.fromisoformat(anomaly['timestamp'])
        anomaly['cpu'] = anomaly.get('cpu') or 0.0
        anomaly['ram'] = anomaly.get('ram') or 0.0
        anomaly['threshold'] = anomaly.get('threshold') or 0.0

    anomalies.sort(key=lambda item: (item['source'], item['_dt']))

    groups = []
    current_group = []
    previous = None

    for anomaly in anomalies:
        if not current_group:
            current_group = [anomaly]
        else:
            delta = (anomaly['_dt'] - previous['_dt']).total_seconds()
            if anomaly['source'] == previous['source'] and delta <= max_gap_seconds:
                current_group.append(anomaly)
            else:
                groups.append(current_group)
                current_group = [anomaly]
        previous = anomaly

    if current_group:
        groups.append(current_group)

    grouped = []
    for group in groups:
        start = group[0]['_dt']
        end = group[-1]['_dt']
        duration_seconds = (end - start).total_seconds() + interval_seconds
        duration_text = format_duration(duration_seconds)
        group_id = hashlib.md5(f"{group[0]['source']}{start.isoformat()}".encode()).hexdigest()[:8]
        temperatures = [item['temperature'] for item in group]
        cpus = [item['cpu'] for item in group]
        rams = [item['ram'] for item in group]
        thresholds = [item['threshold'] for item in group if item['threshold'] is not None]
        threshold = max(thresholds) if thresholds else 0.0
        avg_cpu = sum(cpus) / len(cpus) if cpus else 0.0
        avg_ram = sum(rams) / len(rams) if rams else 0.0
        max_temp = max(temperatures)
        action = get_action_level(max_temp, threshold, avg_cpu, avg_ram, duration_seconds)

        grouped.append({
            'group_id': group_id,
            'source': group[0]['source'],
            'start': start.isoformat(),
            'end': end.isoformat(),
            'duration': duration_text,
            'count': len(group),
            'threshold': threshold,
            'max_temp': max_temp,
            'avg_cpu': avg_cpu,
            'avg_ram': avg_ram,
            'action': action,
            'notified': False,
        })

    return grouped


def init_db(db_path):
    parent = Path(db_path).parent
    parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS anomaly_groups (
        group_id    TEXT PRIMARY KEY,
        source      TEXT NOT NULL,
        group_start TEXT NOT NULL,
        group_end   TEXT NOT NULL,
        duration    TEXT NOT NULL,
        count       INTEGER NOT NULL,
        threshold   REAL,
        max_temp    REAL,
        avg_cpu     REAL,
        avg_ram     REAL,
        action      TEXT,
        notified    INTEGER DEFAULT 0,
        created_at  TEXT DEFAULT (datetime('now')),
        updated_at  TEXT DEFAULT (datetime('now'))
    )
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS metadata (
        key   TEXT PRIMARY KEY,
        value TEXT
    )
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS processed_files (
        path          TEXT PRIMARY KEY,
        last_modified REAL NOT NULL,
        file_size     INTEGER NOT NULL,
        processed_at  TEXT NOT NULL
    )
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS historical_temps (
        source_file TEXT NOT NULL,
        timestamp   TEXT NOT NULL,
        temperature REAL NOT NULL,
        PRIMARY KEY(source_file, timestamp)
    )
    ''')
    conn.commit()
    conn.close()


def get_file_signature(path):
    stat = Path(path).stat()
    return stat.st_mtime, stat.st_size


def get_unprocessed_history_files(history_dir='./Logs/Historique/Temps', db_path='Logs/anomalies.db'):
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    unprocessed = []
    history_path = Path(history_dir)
    if not history_path.exists():
        conn.close()
        return []

    for element in history_path.iterdir():
        if not element.is_file():
            continue
        path = str(element.resolve())
        mtime, size = get_file_signature(path)
        cur.execute('SELECT last_modified, file_size FROM processed_files WHERE path=?', (path,))
        row = cur.fetchone()
        if row is None or row[0] != mtime or row[1] != size:
            unprocessed.append((element, mtime, size))
    conn.close()
    return unprocessed


def mark_file_processed(db_path, path, last_modified, file_size):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO processed_files (path, last_modified, file_size, processed_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            last_modified=excluded.last_modified,
            file_size=excluded.file_size,
            processed_at=excluded.processed_at
    ''', (path, last_modified, file_size, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()


def save_temp_records_to_db(db_path, file_path, records):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('DELETE FROM historical_temps WHERE source_file=?', (file_path,))
    cur.executemany(
        'INSERT OR REPLACE INTO historical_temps (source_file, timestamp, temperature) VALUES (?, ?, ?)',
        [(file_path, timestamp, temperature) for timestamp, temperature in records]
    )
    conn.commit()
    conn.close()


def get_historical_temp_records(db_path='Logs/anomalies.db'):
    if not Path(db_path).exists():
        return []
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('SELECT timestamp, temperature FROM historical_temps')
    rows = cur.fetchall()
    conn.close()
    return [(datetime.fromisoformat(ts), temp) for ts, temp in rows]


def load_existing_anomaly_groups(file_path):
    if Path(file_path).exists():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data.get('anomaly_groups', [])
        except Exception:
            pass
    return []


def save_anomaly_groups_db(db_path, groups):
    parent = Path(db_path).parent
    parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    for group in groups:
        cur.execute('''
        INSERT INTO anomaly_groups (
            group_id, source, group_start, group_end, duration, count,
            threshold, max_temp, avg_cpu, avg_ram, action, notified, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(group_id) DO UPDATE SET
            source=excluded.source,
            group_start=excluded.group_start,
            group_end=excluded.group_end,
            duration=excluded.duration,
            count=excluded.count,
            threshold=excluded.threshold,
            max_temp=excluded.max_temp,
            avg_cpu=excluded.avg_cpu,
            avg_ram=excluded.avg_ram,
            action=excluded.action,
            notified=CASE WHEN excluded.notified = 1 THEN 1 ELSE anomaly_groups.notified END,
            updated_at=excluded.updated_at
        ''', (
            group['group_id'], group['source'], group['start'], group['end'], group['duration'], group['count'],
            group['threshold'], group['max_temp'], group['avg_cpu'], group['avg_ram'], group['action'],
            int(group.get('notified', False)), now, now
        ))

    conn.commit()
    conn.close()


def fetch_unnotified_groups(db_path, limit=10):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('''
        SELECT group_id, source, group_start, group_end, duration, count,
               threshold, max_temp, avg_cpu, avg_ram, action
        FROM anomaly_groups
        WHERE notified = 0
        ORDER BY group_start ASC
        LIMIT ?
    ''', (limit,))
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def mark_group_notified(db_path, group_id):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''
        UPDATE anomaly_groups
        SET notified = 1,
            updated_at = ?
        WHERE group_id = ?
    ''', (datetime.now(timezone.utc).isoformat(), group_id))
    conn.commit()
    conn.close()


def send_ntfy_notification(topic, title, message, priority='high', tags=None, url=None):
    url_base = os.environ.get('NTFY_URL', 'https://ntfy.sh/')
    target = f"{url_base.rstrip('/')}/{topic}"
    data = message.encode('utf-8')
    headers = {
        'Title': title,
        'Priority': priority,
        'Content-Type': 'text/plain; charset=utf-8'
    }
    if tags:
        headers['Tags'] = ','.join(tags)
    if url:
        headers['Url'] = url

    request = urllib.request.Request(target, data=data, headers=headers, method='PUT')
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status == 200 or response.status == 201
    except urllib.error.URLError as exc:
        print(f"Notification failed: {exc}")
        return False


def notify_new_groups(db_path, topic=None, limit=10):
    if topic is None:
        topic = os.environ.get('NTFY_TOPIC', 'loganalyzer')
    groups = fetch_unnotified_groups(db_path, limit=limit)
    if not groups:
        return []

    sent = []
    for group in groups:
        title = f"Anomaly group {group['group_id']}"
        message = (
            f"Source: {group['source']}\n"
            f"Start: {group['group_start']}\n"
            f"End: {group['group_end']}\n"
            f"Duration: {group['duration']}\n"
            f"Count: {group['count']}\n"
            f"Max temp: {group['max_temp']}°C\n"
            f"Avg CPU: {group['avg_cpu']:.1f}%\n"
            f"Avg RAM: {group['avg_ram']:.1f}%\n"
            f"Action: {group['action']}"
        )
        if send_ntfy_notification(topic, title, message):
            mark_group_notified(db_path, group['group_id'])
            sent.append(group['group_id'])

    return sent


def pearson_correlation(records):
    if len(records) < 2:
        return 0.0
    xs = [cpu for _, cpu, _ in records]
    ys = [ram for _, _, ram in records]
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    denom = math.sqrt(var_x * var_y)
    return cov / denom if denom else 0.0


def cpu_ram_correlation(file_path='Logs/Cpu.csv', history=False):
    records = read_cpu_history() if history else read_cpu_ram(file_path)
    corr = pearson_correlation(records)
    source = 'historique' if history else file_path
    print(f"Corrélation CPU/RAM ({source}) : {corr:.3f}")
    return corr


def read_temp_records(file_path='Logs/temp.csv'):
    records = []
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for line in lines[1:]:
            line = line.strip()
            m = re.search(pattern, line)
            if not m:
                continue
            timestamp = datetime.fromisoformat(f"{m.group(1)}T{m.group(2)}")
            records.append((timestamp, float(m.group(3))))
    return records


def summarize_incident(incident_id, segment):
    start = segment[0][0]
    end = segment[-1][0]
    duration = end - start
    temps = [temp for _, temp, _, _ in segment]
    cpus = [cpu for _, _, cpu, _ in segment]
    rams = [ram for _, _, _, ram in segment]
    incident = {
        'id': incident_id,
        'start': start,
        'end': end,
        'duration': duration,
        'cpu_avg': sum(cpus) / len(cpus),
        'ram_avg': sum(rams) / len(rams),
        'temp_max': max(temps),
    }
    if incident['cpu_avg'] > 95 or incident['temp_max'] > 70:
        incident['severity'] = 'High'
    else:
        incident['severity'] = 'Medium'
    return incident


def format_incident(incident):
    return (
        f"INCIDENT #{incident['id']}\n"
        f"Début :\n{incident['start'].strftime('%Y-%m-%d %H:%M')}\n\n"
        f"Fin :\n{incident['end'].strftime('%Y-%m-%d %H:%M')}\n\n"
        f"Durée :\n{int(incident['duration'].total_seconds() // 60)} minutes\n\n"
        f"CPU moyen :\n{incident['cpu_avg']:.1f}%\n\n"
        f"RAM moyenne :\n{incident['ram_avg']:.1f}%\n\n"
        f"Température max :\n{incident['temp_max']:.1f}°C\n\n"
        f"Gravité :\n{incident['severity']}\n"
    )


def detect_incidents(temp_file='Logs/temp.csv', min_duration_minutes=5, threshold_multiplier=2.0, db_path='Logs/anomalies.db'):
    temp_records = read_temp_records(temp_file)
    historical_records = get_historical_temp_records(db_path)
    if historical_records:
        temp_records.extend(historical_records)
    else:
        history_temps_dir = './Logs/Historique/Temps'
        for element in Path(history_temps_dir).iterdir():
            if element.is_file():
                temp_records.extend(read_temp_records(str(element)))

    temp_records = sorted(set(temp_records))

    if not temp_records:
        print('Aucune donnée de température trouvée.')
        return []

    average_temp = sum(temp for _, temp in temp_records) / len(temp_records)
    threshold = average_temp * threshold_multiplier

    incidents = []
    segment = []

    for timestamp, temperature in temp_records:
        if temperature > threshold:
            segment.append((timestamp, temperature))
            continue

        if segment:
            duration = segment[-1][0] - segment[0][0]
            if duration.total_seconds() >= min_duration_minutes * 60:
                cpu_ram_map = read_cpu_ram_map()
                enriched_segment = []
                for ts, temp in segment:
                    cpu, ram = find_cpu_ram(ts, cpu_ram_map)
                    if cpu is None:
                        cpu = 0.0
                    if ram is None:
                        ram = 0.0
                    enriched_segment.append((ts, temp, cpu, ram))
                incidents.append(enriched_segment)
            segment = []

    if segment:
        duration = segment[-1][0] - segment[0][0]
        if duration.total_seconds() >= min_duration_minutes * 60:
            cpu_ram_map = read_cpu_ram_map()
            enriched_segment = []
            for ts, temp in segment:
                cpu, ram = find_cpu_ram(ts, cpu_ram_map)
                if cpu is None:
                    cpu = 0.0
                if ram is None:
                    ram = 0.0
                enriched_segment.append((ts, temp, cpu, ram))
            incidents.append(enriched_segment)

    summaries = []
    for index, segment in enumerate(incidents, start=1):
        incident = summarize_incident(index, segment)
        summaries.append(incident)
        print(format_incident(incident))

    if not summaries:
        print('Aucun incident détecté.')
    else:
        print(f'\nRésumé: {len(summaries)} incident(s) détecté(s) (Température > {threshold:.1f}°C pendant > {min_duration_minutes} min)')

    return summaries


def save_anomalies_json(file_path, anomalies):
    groups = group_anomalies(anomalies)
    existing_groups = load_existing_anomaly_groups(file_path)
    grouped = {group['group_id']: group for group in existing_groups}
    for group in groups:
        grouped[group['group_id']] = group

    all_groups = list(grouped.values())
    parent = Path(file_path).parent
    parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump({"anomaly_groups": all_groups}, f, ensure_ascii=False, indent=2)

    db_path = os.environ.get('DB_PATH', 'Logs/anomalies.db')
    db_path = os.getenv("DB_PATH",     str(Path(__file__).resolve().parent))

    try:
        init_db(db_path)
        save_anomaly_groups_db(db_path, groups)
    except Exception:
        print('Warning: could not persist anomaly groups to DB')


def Old_Anomaly_detection(seuil, db_path='Logs/anomalies.db'):
    cpu_ram_map = read_cpu_ram_map()
    anomalies = []
    new_files = get_unprocessed_history_files(db_path=db_path)

    for element, mtime, size in new_files:
        temps = read_temps(str(element))
        save_temp_records_to_db(db_path, str(element.resolve()), temps)
        mark_file_processed(db_path, str(element.resolve()), mtime, size)

    historical_records = get_historical_temp_records(db_path)
    if not historical_records:
        print('Aucune donnée historique de température disponible pour la détection.')
        return []

    average = sum(temp for _, temp in historical_records) / len(historical_records)
    threshold = average * seuil
    for timestamp, temp in historical_records:
        if temp > threshold:
            ts = timestamp if isinstance(timestamp, datetime) else datetime.fromisoformat(timestamp)
            cpu, ram_pct = find_cpu_ram(ts, cpu_ram_map)
            anomaly = {
                "source": "historical",
                "timestamp": timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
                "temperature": temp,
                "threshold": threshold,
                "cpu": cpu,
                "ram": ram_pct,
            }
            anomalies.append(anomaly)
            line = f"Anomalie détectée : {timestamp} -> {temp}°C dépasse le seuil de {threshold:.2f}°C"
            if cpu is not None and ram_pct is not None:
                line += f" | CPU: {cpu:.1f}% | RAM: {ram_pct:.1f}%"
            print(line)

    if new_files:
        print(f"Traitement de {len(new_files)} fichier(s) historique nouveau(x) ou modifié(s).")
    else:
        print('Aucun fichier historique nouveau ou modifié à analyser.')

    return anomalies


def Actual_Anomaly_detection(seuil):
    cpu_ram_map = read_cpu_ram_map()
    temps = read_temps(Chemin)
    anomalies = []
    if len(temps) > 0:
        Average = sum(temp for _, temp in temps) / len(temps)
        for timestamp, temp in temps:
            if temp > Average * seuil:  # Seuil d'anomalie (par exemple, 50% au-dessus de la moyenne)
                ts = datetime.fromisoformat(timestamp)
                cpu, ram_pct = find_cpu_ram(ts, cpu_ram_map)
                anomaly = {
                    "source": "current",
                    "timestamp": timestamp,
                    "temperature": temp,
                    "threshold": Average * seuil,
                    "cpu": cpu,
                    "ram": ram_pct,
                }
                anomalies.append(anomaly)
                line = f"Anomalie détectée : {timestamp} -> {temp}°C dépasse le seuil de {Average * seuil:.2f}°C"
                if cpu is not None and ram_pct is not None:
                    line += f" | CPU: {cpu:.1f}% | RAM: {ram_pct:.1f}%"
                print(line)
    return anomalies


def main():
    db_path = os.environ.get('DB_PATH', 'Logs/anomalies.db')
    init_db(db_path)
    old_anomalies = Old_Anomaly_detection(2, db_path=db_path)
    actual_anomalies = Actual_Anomaly_detection(2)
    all_anomalies = old_anomalies + actual_anomalies
    save_anomalies_json('Logs/anomalies.json', all_anomalies)
    print('\n--- Incident report ---')
    detect_incidents(db_path=db_path)

    sent = notify_new_groups(db_path)
    if sent:
        print(f"Notifications envoyées pour {len(sent)} groupe(s) : {', '.join(sent)}")
    else:
        print('Aucune nouvelle anomalie non notifiée.')


if __name__ == '__main__':
    main()
