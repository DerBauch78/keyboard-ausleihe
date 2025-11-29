# Keyboard-Ausleihe

Web-Anwendung zur Verwaltung der jährlichen Keyboard-Ausleihe an Schulen.

## Features

- 📋 **Klassenverwaltung** – Jahrgang 5 (Ausleihe) und 6 (Rückgabe)
- 🎹 **Keyboard-Inventar** – Verwaltung aller Keyboards mit Status und Zustand
- 👥 **Schülerverwaltung** – Import per CSV, Teilnahme-Erfassung
- 💶 **Gebührenverwaltung** – Bezahlstatus tracken (auch vor Keyboard-Vergabe)
- 📊 **Excel-Export** – Backup, Klassenlisten, Gebührenübersicht
- 🔄 **Schuljahreswechsel** – Automatische Übernahme 5er → 6er
- 👤 **Mehrbenutzerfähig** – Admin, Lehrer, Readonly-Rollen

## Installation

### Voraussetzungen

- Docker & Docker Compose
- Git

### Quick Start

```bash
# Repository klonen
git clone https://github.com/DEINUSER/keyboard-ausleihe.git
cd keyboard-ausleihe

# Environment-Datei erstellen
cp .env.example .env
nano .env  # SECRET_KEY anpassen!

# Starten
docker compose up -d --build
```

Die Anwendung läuft dann unter: **http://localhost:5000**

### Erster Login

- **Benutzer:** `admin`
- **Passwort:** `admin`

⚠️ **Wichtig:** Passwort nach dem ersten Login ändern!

## Updates

```bash
cd /opt/keyboard-ausleihe
git pull
docker compose up -d --build
```

## Backup

### Datenbank sichern

```bash
# Backup erstellen
docker cp keyboard-ausleihe:/app/data/keyboards.db ./backup_$(date +%Y%m%d).db

# Oder über die Web-Oberfläche:
# Dashboard → "Komplettes Backup" (ZIP mit Excel + JSON)
```

### Datenbank wiederherstellen

```bash
docker cp backup.db keyboard-ausleihe:/app/data/keyboards.db
docker compose restart
```

## Konfiguration

Umgebungsvariablen in `.env`:

| Variable | Beschreibung | Default |
|----------|--------------|---------|
| `SECRET_KEY` | Flask Secret Key | (muss gesetzt werden!) |
| `DATABASE_URL` | SQLite Pfad | `sqlite:////app/data/keyboards.db` |
| `FLASK_ENV` | Umgebung | `production` |

## Entwicklung

```bash
# Lokale Entwicklung ohne Docker
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# .env erstellen
cp .env.example .env

# Starten
python run.py
```

## Lizenz

MIT

## Autor

Für den internen Schulgebrauch entwickelt.
