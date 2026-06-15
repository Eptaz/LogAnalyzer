# log.sh
#!/bin/bash

echo "Lancement du Script..."
python3 "$SCRIPT_DIR/Moyenne.py" >> "$DEBUG_DIR/script_output.log" 2>> "$DEBUG_DIR/script_error.log"
echo "$(date) - Script shell exécuté" >> "$DEBUG_DIR/stat.log"
echo "Script Moyenne terminé"