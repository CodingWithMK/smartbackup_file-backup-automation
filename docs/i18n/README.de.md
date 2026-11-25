<!-- Source: README.md | Version: 0.9.0 | Language: de (Deutsch) | Synced: 2026-11-25 -->

<div align="center">

# 🔄 SmartBackup

**Intelligentes Backup-System für Entwickler**

Sichere deine wichtigen Dateien automatisch und überspringe dabei `node_modules`, virtuelle Umgebungen und andere Build-Artefakte.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/CodingWithMK/smartbackup_file-backup-automation/actions/workflows/ci.yml/badge.svg)](https://github.com/CodingWithMK/smartbackup_file-backup-automation/actions)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)](/)

🌐 [English](../../README.md) · [Türkçe](README.tr.md) · **Deutsch**

[Funktionen](#-funktionen) •
[Schnellstart](#-schnellstart) •
[📖 Benutzerhandbuch (Englisch)](../USER_GUIDE.md) •
[Mitwirken](#-mitwirken)

</div>

---

> # 📖 **Vollständige Dokumentation: [SmartBackup Benutzerhandbuch (Englisch)](../USER_GUIDE.md)**
> Installation (`pip` / `uv` / Entwicklung), **alle CLI-Befehle und Optionen**, inkrementelle
> Manifeste, Auto-Detect-Watcher & Hintergrunddienst, Wiederherstellung, Konfiguration und
> plattformübergreifende Fehlerbehebung — alles an einem Ort.

---

## 🤔 Warum SmartBackup?

Schon einmal versucht, den Ordner `Documents` zu sichern, und dann stundenlang auf riesige
`node_modules`-Verzeichnisse oder Python-Virtual-Environments gewartet?

**SmartBackup löst dieses Problem.** Entwicklungsartefakte werden automatisch erkannt und
übersprungen — dadurch sind deine Backups:

- ⚡ **10x schneller** — gigabytegroße Abhängigkeitsordner überspringen
- 💾 **10x kleiner** — nur das sichern, was wirklich zählt
- 🧠 **Intelligent** — inkrementelle, manifestbasierte Backups kopieren nur geänderte Dateien
- 💻 **Mehrgerätefähig** — mehrere Rechner teilen sich sicher ein Laufwerk (Ordner pro Hostname)
- 🔌 **Ohne Konfiguration** — sofort einsatzbereit unter Windows, macOS und Linux

---

## ✨ Funktionen

| Funktion | Beschreibung |
|----------|--------------|
| 🚀 **Plattformübergreifend** | Läuft unter Windows, macOS und Linux |
| 🔍 **Intelligentes Filtern** | Überspringt automatisch `node_modules`, `venv`, `.git`, `__pycache__`, Build-Ausgaben und Caches |
| 📂 **Selektives Backup** | Interaktive Ordnerauswahl (`--select`) mit Tastatur-Checkboxen, Schutz nicht ausgewählter Ordner und Prüfverlauf |
| 📊 **Inkrementelles Backup** | JSON- oder SQLite-Manifest (`--manifest-format json\|sqlite`) mit automatischer Erkennung, eigener SQLite-Tabelle `selective_backups` & nahtloser Migration |
| 🔐 **SHA-256-Hashing** | Optionale gestufte Hash-Prüfung (`--hash` ≤ 50 MB, `--hash-all` für alle Dateien) |
| 🔄 **Wiederherstellung** | Konfliktstrategien (`skip`, `overwrite`, `newer`, `rename`), Musterfilterung, `--manifest-info`, Trockenlauf-Vorschau |
| 💻 **Mehrgeräte-Support** | Eigene Backup-Ordner pro Gerät — mehrere Maschinen teilen sich ein Laufwerk |
| 📦 **Komprimierung** | `zip` / `tar.gz` — direkt beim Backup oder nachträglich über `compress` |
| 🔌 **Automatische Erkennung** | Findet externe Laufwerke; optionaler Watcher-Daemon fragt beim Anschließen automatisch nach |
| ⚙️ **Konfigurations-CLI** | Dauerhafte Einstellungen & Ausschlüsse per `smartbackup config` verwalten (kein manuelles JSON-Editieren) |
| 🔔 **Desktop-Benachrichtigungen** | Optionale Abschlussmeldungen (`--notify`) über `osascript`, `notify-send` oder PowerShell |
| 🗓️ **Zeitplan-Assistent** | Gibt betriebssystemspezifische `schtasks`-, `launchd`-, `cron`- und `systemd`-Vorlagen über `smartbackup schedule` aus |
| 📝 **Detaillierte Protokollierung** | Durchgehende einzeilige Rich-Fortschrittsanzeige + Protokolldatei pro Lauf auf dem Backup-Medium |
| 🎯 **Minimale Abhängigkeiten** | Nur `rich` + `typer` — alles Weitere stammt aus der Python-Standardbibliothek |

---

## 🚀 Schnellstart

### Option 1 — Einzeilige Standalone-Installation (Kein Python erforderlich)

Installiere die vorgefertigte eigenständige Binärdatei direkt aus den [GitHub Releases](https://github.com/CodingWithMK/smartbackup_file-backup-automation/releases) auf einem frischen System — kein Python, `pip` oder `uv` nötig:

**macOS & Linux (`curl`):**
```bash
curl -fsSL https://raw.githubusercontent.com/CodingWithMK/smartbackup_file-backup-automation/main/scripts/install.sh | sh
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/CodingWithMK/smartbackup_file-backup-automation/main/scripts/install.ps1 | iex
```

<details>
<summary>Bestimmte Release-Version festlegen</summary>

```bash
# macOS / Linux
SMARTBACKUP_VERSION=v0.9.0 curl -fsSL https://raw.githubusercontent.com/CodingWithMK/smartbackup_file-backup-automation/main/scripts/install.sh | sh
```

```powershell
# Windows (PowerShell)
$env:SMARTBACKUP_VERSION = "v0.9.0"; irm https://raw.githubusercontent.com/CodingWithMK/smartbackup_file-backup-automation/main/scripts/install.ps1 | iex
```

</details>

---

### Option 2 — Aus dem Quellcode / mit Python ausführen (Entwickler)

**Voraussetzungen:** Python 3.9+ · Windows / macOS / Linux

#### Direkt ausführen (ohne Installation)

```bash
git clone https://github.com/CodingWithMK/smartbackup_file-backup-automation.git
cd smartbackup_file-backup-automation

python main.py            # sichert Documents → automatisch erkanntes externes Laufwerk
```

#### Installation mit pip

```bash
pip install .
smartbackup
```

#### Installation mit uv (empfohlen für Entwickler)

```bash
uv venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
uv pip install -e ".[dev]"
smartbackup
```

**Das war's schon!** Schließe ein externes Laufwerk an und starte SmartBackup — es erkennt das
Laufwerk automatisch, überspringt Build-Artefakte und kopiert nur Dateien, die sich seit dem
letzten Lauf geändert haben. Wird kein Laufwerk gefunden, wird stattdessen ein lokales temporäres
Backup angeboten.

```bash
smartbackup --version     # prüfen: smartbackup 0.9.0
smartbackup --help        # alle Befehle und Optionen
```

---

## 💡 Häufige Befehle

```bash
smartbackup                                   # Documents auf das automatisch erkannte Laufwerk sichern
smartbackup --select                          # bestimmte Ordner interaktiv für das Backup auswählen
smartbackup --select --dry-run                # Ordner auswählen und simulieren (keine Schreibvorgänge)
smartbackup --source ~/Projects               # einen benutzerdefinierten Ordner sichern
smartbackup --target /media/USB_DRIVE         # in einen expliziten Zielpfad sichern
smartbackup --dry-run                         # Backup simulieren (keine Kopien, kein Manifest, keine Logs)
smartbackup --manifest-format sqlite          # Manifest in SQLite (.smartbackup_manifest.db) speichern
smartbackup --notify                          # Desktop-Benachrichtigung nach Abschluss senden
smartbackup --list-drives                     # verfügbare externe Laufwerke anzeigen
smartbackup --hash                            # SHA-256-Änderungserkennung (Dateien ≤ 50 MB)
smartbackup --target /media/USB --verify      # Backup-Integrität anhand des Manifests prüfen
smartbackup --compress zip                    # sichern und anschließend als ZIP archivieren

smartbackup restore --source /media/USB_DRIVE --list                  # Backup-Inhalt anzeigen
smartbackup restore --source /media/USB_DRIVE --manifest-info         # Manifest-Zusammenfassung anzeigen
smartbackup restore --source /media/USB_DRIVE --conflict rename       # bei Konflikten beide Dateien behalten

smartbackup config list                       # dauerhafte Konfiguration anzeigen
smartbackup config set manifest_format sqlite # SQLite dauerhaft als Standard-Manifestformat setzen

smartbackup watch                             # Laufwerksüberwachung im Vordergrund
smartbackup daemon install                    # Hintergrunddienst installieren (status/uninstall/clear-state)
smartbackup schedule --hours 24               # OS-spezifische Anleitung für geplante Backups ausgeben
```

Alle Erklärungen, Optionen und Praxisbeispiele: **[Benutzerhandbuch (Englisch) →](../USER_GUIDE.md)**

<details>
<summary><b>Was wird standardmäßig ausgeschlossen?</b></summary>

`node_modules`, `venv`/`.venv`/`.env`, `__pycache__`, `.git`/`.svn`/`.hg`, `dist`/`build`,
`target`, `bin`/`obj`, `.idea`/`.vscode`, `.next`/`.nuxt`, `.gradle`/`.m2`, Caches
(`.cache`, `.pytest_cache`, `.mypy_cache`, `.sass-cache`), temporäre Dateien (`*.tmp`, `*.log`,
`*.bak`, `~*`), Binärdateien (`*.pyc`, `*.exe`, `*.dll`, `*.so`, `*.dylib`, …), Systemdateien
(`.DS_Store`, `Thumbs.db`, `desktop.ini`) — sowie jedes Verzeichnis, das strukturell wie eine
virtuelle Python-Umgebung aussieht.

Vollständige Liste: [Benutzerhandbuch → Appendix B (Englisch)](../USER_GUIDE.md#b-default-exclusions)

</details>

---

## 🤝 Mitwirken

Beiträge sind jederzeit willkommen! So geht's:

1. Repository forken
2. Neuen Branch erstellen: `git checkout -b feature/amazing-feature`
3. Änderungen umsetzen
4. Tests & Linter ausführen: `pytest` · `ruff check .`
5. Änderungen committen: `git commit -m 'Add amazing feature'`
6. Branch pushen: `git push origin feature/amazing-feature`
7. Einen Pull Request öffnen

Weitere Details findest du in [CONTRIBUTING.md (Englisch)](../CONTRIBUTING.md) und die Versionshistorie in [CHANGELOG.md (Englisch)](../CHANGELOG.md).

---

## 📜 Lizenz

Dieses Projekt steht unter der MIT-Lizenz — siehe die Datei [LICENSE](../../LICENSE) für Details.

---

## 🙏 Danksagung

- Mit ❤️ entwickelt für Entwickler, die keine Lust mehr haben, `node_modules` zu sichern
- Inspiriert von der Frustration über langsame Backups

---

<div align="center">

**Wenn dir dieses Tool Zeit gespart hat, gib dem Projekt gerne einen ⭐**

[Fehler melden](https://github.com/CodingWithMK/smartbackup_file-backup-automation/issues) •
[Funktion vorschlagen](https://github.com/CodingWithMK/smartbackup_file-backup-automation/issues)

</div>
