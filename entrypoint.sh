#!/bin/sh
echo "Running initial anomaly detection..."
python /app/Main.py

echo "Starting Flask app with scheduled checks..."
exec python -u /app/app.py
\n
