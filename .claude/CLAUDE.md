# PiLogAnalyzer — CLAUDE.md

## Vue d'ensemble

Outil de surveillance et d'analyse de logs pour Raspberry Pi. Architecture en deux couches :
- **Couche collecte (Pi)** : scripts cron Python/bash qui écrivent les métriques (température, CPU, RAM) dans des CSV locaux.
- **Couche analyse (Docker)** : Flask + APScheduler qui lit les CSV, détecte les anomalies, persiste en SQLite, expose un dashboard web et envoie des notifications ntfy.

## Architecture

```
PiLogAnalyzer/
├── Main.py              # Moteur de détection d'anomalies (CLI + bibliothèque)
├── app.py               # Serveur Flask + scheduler (toutes les 5 min → Main.py)
├── entrypoint.sh        # Lancement Docker : Main.py puis app.py
├── Dockerfile           # Image python:3.12-slim (ARM64)
├── docker-compose.yml   # Service unique, volumes Logs/ et data/
├── requirements.txt     # Flask, APScheduler, python-dotenv
├── templates/
│   └── index.html       # Dashboard dark-mode (vanilla JS, pas de framework)
└── Logs/
    ├── temp.csv          # Températures courantes (écrit par temp.py sur le Pi)
    ├── Cpu.csv           # CPU/RAM courants (écrit par Cpu.py sur le Pi)
    ├── anomalies.db      # SQLite (développement local)
    ├── anomalies.json    # Export JSON des groupes d'anomalies
    ├── Historique/
    │   ├── Temps/        # Archives quotidiennes de temp.csv
    │   ├── CPU/          # Archives quotidiennes de Cpu.csv
    │   └── Moyennes/     # Résumés journaliers min/max/avg
    └── Script/           # Scripts déployés SUR le Raspberry Pi
        ├── temp.py       # Lit /sys/class/thermal/thermal_zone0/temp → temp.csv
        ├── Cpu.py        # Lit psutil → Cpu.csv
        ├── Moyenne.py    # Calcule min/max/avg journalier → Historique/Moyennes/
        ├── header.py     # Réinitialise temp.csv et Cpu.csv après archivage
        ├── log.sh        # Appelle Moyenne.py (via cron)
        └── Saving.sh     # Archivage quotidien + nettoyage >30 jours (via cron)
```

## Stack réelle

| Composant | Version | Usage |
|-----------|---------|-------|
| Python | 3.11+ | Runtime principal |
| Flask | >=3.0.0 | Serveur web / API REST |
| APScheduler | >=3.10.0 | Exécution périodique de Main.py (toutes les 5 min) |
| python-dotenv | latest | Chargement `.env` |
| psutil | (Pi only) | Lecture CPU/RAM dans Cpu.py |
| SQLite | stdlib | Persistance anomalies, fichiers traités, données historiques |
| Docker | 3.9+ compose | Déploiement sur Pi ou serveur ARM64 |
| ntfy.sh | API HTTP | Notifications push (PUT vers topic) |

> Pas de Prometheus dans le code actuel. Si tu l'ajoutes, expose `/metrics` depuis app.py avec `prometheus_flask_exporter`.

## Format des données

### temp.csv / archives Historique/Temps/
```
date T heure;temperature;° C
2024-01-15T12:00:00;45.5
```
Séparateur `;`, timestamp ISO 8601, température en °C (float).

### Cpu.csv / archives Historique/CPU/
```
date T heure;CPU;RAM Mb;RAM %
2024-01-15T12:00:00;23.5;512.3;45.2
```
Séparateur `;`, colonnes : timestamp, cpu%, ram_mb, ram_pct.

### SQLite — tables principales
- `anomaly_groups` : groupes d'anomalies agrégés avec action (normal/warning/critical)
- `historical_temps` : données de température historiques dédupliquées
- `processed_files` : signature (mtime + size) des fichiers déjà traités
- `metadata` : paires clé/valeur génériques

## Variables d'environnement (.env)

| Variable | Défaut Docker | Usage |
|----------|--------------|-------|
| `DB_PATH` | `/data/anomalies.db` | Chemin SQLite |
| `SCRIPT_DIR` | répertoire de app.py | Répertoire où se trouve Main.py |
| `MAIN_SCRIPT` | `SCRIPT_DIR/Main.py` | Chemin absolu de Main.py |
| `NTFY_TOPIC` | `loganalyzer` | Topic ntfy pour les notifications |
| `NTFY_URL` | `https://ntfy.sh` | URL base du serveur ntfy (auto-hébergé possible) |
| `LOG_ROOT` | `<projet>/Logs` | Racine des logs CSV (Pi scripts) |
| `PROJECT_ROOT` | — | Racine projet (Saving.sh) |
| `DEBUG_DIR` | — | Répertoire logs debug shell |

## Commandes utiles

### Développement local
```bash
# Installer les dépendances
pip install -r requirements.txt

# Lancer le dashboard Flask (debug)
python app.py
# → http://localhost:5000

# Lancer la détection d'anomalies manuellement
python Main.py

# Initialiser les fichiers CSV vides
python Logs/Script/header.py
```

### Docker (développement)
```bash
# Build et démarrage
docker compose up --build

# Rebuild sans cache (après modif requirements.txt)
docker compose build --no-cache && docker compose up

# Voir les logs
docker compose logs -f loganalyzer

# Exécuter Main.py dans le conteneur
docker compose exec loganalyzer python /app/Main.py
```

### Docker ARM64 (Raspberry Pi)
```bash
# Build cross-platform depuis x86 (sur la machine de dev)
docker buildx build --platform linux/arm64 -t piloganalyzer:latest .

# Sur le Pi directement
docker compose up -d
```

### Scripts Pi (via cron)
```bash
# Exemple crontab sur le Pi
# Toutes les minutes : collecte température et CPU
* * * * * python3 /opt/piloganalyzer/Logs/Script/temp.py
* * * * * python3 /opt/piloganalyzer/Logs/Script/Cpu.py

# Tous les jours à 23h59 : archivage
59 23 * * * bash /opt/piloganalyzer/Logs/Script/Saving.sh
```

## Conventions de code observées

- **Nommage** : majoritairement `snake_case` pour les fonctions et variables. Quelques fonctions en `PascalCase` à harmoniser (`Old_Anomaly_detection`, `Actual_Anomaly_detection`, `Set_average`).
- **Pathlib** : `Path` utilisé partout pour les chemins — ne pas utiliser `os.path.join`.
- **Encodage** : tous les fichiers CSV en UTF-8, `encoding="utf-8"` explicite.
- **Séparateur CSV** : point-virgule `;` (pas la virgule).
- **Timestamps** : ISO 8601 (`datetime.isoformat(timespec="seconds")`), sans timezone pour les données Pi, UTC pour les métadonnées DB.
- **SQLite** : `ON CONFLICT ... DO UPDATE` (upsert) pour l'idempotence. Toujours fermer la connexion explicitement (`conn.close()`).
- **Dotenv** : chaque script charge `.env` depuis la racine du projet via `Path(__file__).resolve().parents[N] / '.env'`.
- **Pas de framework de test** actuellement — à ajouter avec pytest.

## API REST (app.py)

| Endpoint | Retour |
|----------|--------|
| `GET /` | Dashboard HTML |
| `GET /api/anomalies` | 100 derniers groupes (vue simplifiée) |
| `GET /api/groups` | 50 derniers groupes complets |
| `GET /api/stats` | Compteurs globaux (total, critiques, last_seen) |
| `GET /api/metadata` | Paires clé/valeur de la table metadata |

## Logique de détection

1. **Seuil** = moyenne de toutes les températures × multiplicateur (défaut : 2.0).
2. Un point est une **anomalie** si `temp > seuil`.
3. Les anomalies consécutives (gap ≤ 120 s) sont **groupées**.
4. Chaque groupe reçoit un niveau : `normal` / `warning` / `critical` selon temp max, CPU moyen, RAM moyenne, et durée.
5. Les groupes non notifiés sont envoyés via ntfy, puis marqués `notified=1`.

## Contraintes ARM64 / Raspberry Pi

- L'image Docker doit utiliser `python:3.12-slim` (pas `3.14-slim` qui n'existe pas).
- Ajouter `--platform linux/arm64` au build cross-platform depuis x86.
- `temp.py` lit `/sys/class/thermal/thermal_zone0/temp` — disponible uniquement sur Linux/Pi, ne tourne pas sous Windows/macOS.
- `psutil` (`Cpu.py`) nécessite une installation séparée sur le Pi : `pip install psutil`.
- Le volume `/data` dans Docker doit être persistant (ne pas utiliser `tmpfs`).
- Éviter les dépendances compilées non disponibles en wheel ARM64 (ex : numpy, pandas) sauf si strictement nécessaire.

## Problèmes connus

- **Dockerfile** : `python:3.14-slim` n'existe pas — utiliser `python:3.12-slim`.
- **`DB_PATH` dans app.py** : le défaut pointe sur le répertoire parent (pas un fichier `.db`) — bug latent si `DB_PATH` n'est pas défini dans `.env`.
- **`Set_average()`** dans Main.py : lit les fichiers historiques mais n'est jamais appelée dans `main()` — vestige à nettoyer ou à intégrer.
- **Pas de tests** : la couverture est à 0%. Priorité : tester `group_anomalies`, `get_action_level`, `pearson_correlation`, et les routes Flask.

## Tests (à implémenter)

```bash
# Lancer les tests
pytest tests/ -v --cov=. --cov-report=term-missing

# Cible : coverage > 80%
```

Modules prioritaires à couvrir :
- `Main.py` : `group_anomalies`, `get_action_level`, `pearson_correlation`, `format_duration`, `read_temps`, `read_cpu_ram`
- `app.py` : routes `/api/*` avec une DB SQLite en mémoire