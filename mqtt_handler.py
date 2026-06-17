import json
import os
import sqlite3
import threading
from collections import deque
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from Main import group_anomalies, init_db, notify_new_groups, save_anomaly_groups_db

load_dotenv(Path(__file__).resolve().parent / '.env')

THRESHOLD_MULTIPLIER = float(os.getenv('THRESHOLD_MULTIPLIER', '2.0'))

_lock = threading.Lock()
_open_group: list = []
_cpu_buffer: deque = deque(maxlen=10)
_threshold: float | None = None


def _compute_threshold(db_path: str) -> float | None:
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute('SELECT AVG(temperature) FROM historical_temps').fetchone()
        conn.close()
        if row and row[0]:
            return row[0] * THRESHOLD_MULTIPLIER
    except Exception:
        pass
    return None


def refresh_threshold(db_path: str) -> None:
    global _threshold
    with _lock:
        value = _compute_threshold(db_path)
        if value is not None:
            _threshold = value


def _find_cpu_for_ts(ts: datetime):
    if not _cpu_buffer:
        return 0.0, 0.0
    closest = min(_cpu_buffer, key=lambda x: abs((x[0] - ts).total_seconds()))
    if abs((closest[0] - ts).total_seconds()) <= 60:
        return closest[1], closest[2]
    return 0.0, 0.0


def _close_group(db_path: str) -> None:
    global _open_group
    if not _open_group:
        return
    groups = group_anomalies([dict(a) for a in _open_group])
    if groups:
        save_anomaly_groups_db(db_path, groups)
        notify_new_groups(db_path)
    _open_group = []


def close_stale_group(db_path: str, max_gap_seconds: int = 120) -> None:
    with _lock:
        if not _open_group:
            return
        last_ts = datetime.fromisoformat(_open_group[-1]['timestamp'])
        if (datetime.now() - last_ts).total_seconds() > max_gap_seconds:
            _close_group(db_path)


def _on_connect(client, userdata, flags, reason_code, properties):
    client.subscribe(userdata['topic_temp'], qos=1)
    client.subscribe(userdata['topic_cpu'], qos=1)
    print(f"[mqtt] Connecté au broker (rc={reason_code})")


def _handle_temp(db_path: str, ts: datetime, temp: float) -> None:
    global _open_group, _threshold
    if _threshold is None:
        _threshold = _compute_threshold(db_path)
    if _threshold is None:
        return

    if temp > _threshold:
        cpu, ram = _find_cpu_for_ts(ts)
        _open_group.append({
            'source': 'mqtt',
            'timestamp': ts.isoformat(),
            'temperature': temp,
            'threshold': _threshold,
            'cpu': cpu,
            'ram': ram,
        })
    elif _open_group:
        last_ts = datetime.fromisoformat(_open_group[-1]['timestamp'])
        if (ts - last_ts).total_seconds() > 120:
            _close_group(db_path)


def _on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
    except Exception:
        return

    db_path = userdata['db_path']

    with _lock:
        if msg.topic == userdata['topic_temp']:
            ts = datetime.fromisoformat(data['timestamp'])
            _handle_temp(db_path, ts, float(data['temperature']))

        elif msg.topic == userdata['topic_cpu']:
            ts = datetime.fromisoformat(data['timestamp'])
            _cpu_buffer.append((
                ts,
                float(data.get('cpu', 0.0)),
                float(data.get('ram_pct', 0.0)),
            ))


def start_mqtt(db_path: str) -> mqtt.Client:
    init_db(db_path)
    refresh_threshold(db_path)

    broker = os.getenv('MQTT_BROKER', 'mosquitto')
    port = int(os.getenv('MQTT_PORT', '1883'))
    topic_temp = os.getenv('MQTT_TOPIC_TEMP', 'piloganalyzer/temp')
    topic_cpu = os.getenv('MQTT_TOPIC_CPU', 'piloganalyzer/cpu')

    userdata = {'db_path': db_path, 'topic_temp': topic_temp, 'topic_cpu': topic_cpu}

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, userdata=userdata)
    client.on_connect = _on_connect
    client.on_message = _on_message

    try:
        client.connect(broker, port, keepalive=60)
    except Exception as exc:
        print(f"[mqtt] Connexion impossible ({exc}) — démarrage sans MQTT")
        return client

    thread = threading.Thread(target=client.loop_forever, daemon=True, name='mqtt-loop')
    thread.start()
    print(f"[mqtt] Client démarré → {broker}:{port}")
    return client
