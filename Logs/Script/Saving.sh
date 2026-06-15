# daily.sh
#!/bin/bash
set -euo pipefail

# Charge les variables d'environnement
if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
fi

suffixe=$(date +%Y-%m-%d)

# Archivage
cat "$LOG_ROOT/temp.csv" > "$LOG_ROOT/Historique/Temps/temperature-$suffixe.csv"
echo "Enregistrement fichier températures OK"

cat "$LOG_ROOT/Cpu.csv" > "$LOG_ROOT/Historique/CPU/CPU-$suffixe.csv"
echo "Enregistrement fichier CPU OK"

# Moyenne
echo "Execution Moyenne :"
bash "$SCRIPT_DIR/log.sh"

# Reset
echo "Suppression de temp.csv"
rm "$LOG_ROOT/temp.csv"

echo "Ecriture du nouveau fichier..."
python3 "$SCRIPT_DIR/header.py"
echo "Opération terminée"

# Nettoyage > 30 jours
echo "Nettoyage des fichiers anciens (>30 jours)..."
find "$LOG_ROOT/Historique/Temps"    -type f -name "*.csv" -mtime +30 -delete
find "$LOG_ROOT/Historique/Moyennes" -type f -name "*.csv" -mtime +30 -delete
find "$LOG_ROOT/Historique/CPU"      -type f -name "*.csv" -mtime +30 -delete
echo "Nettoyage terminé"