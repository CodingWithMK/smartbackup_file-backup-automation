<!-- Source: docs/USER_GUIDE.md | Version: 0.9.0 | Language: de (Deutsch) | Synced: 2026-11-25 -->

# SmartBackup Benutzerhandbuch

**Getestet mit Version: `smartbackup 0.9.0`** · Plattformen: Windows · macOS · Linux · Python 3.9+

🌐 [English](../USER_GUIDE.md) · [Türkçe](USER_GUIDE.tr.md) · **Deutsch**

Dieses Handbuch ist die verbindliche Referenz für die Nutzung von SmartBackup. Jeder hier
dokumentierte Befehl, jede Option, jeder Standardwert, jeder Dateipfad und jedes Verhalten wurde
direkt aus dem Quellcode des Projekts übernommen und verifiziert.

---

## Inhaltsverzeichnis

1. [Überblick & Philosophie](#1-überblick--philosophie)
2. [Installation & Voraussetzungen](#2-installation--voraussetzungen)
3. [Kernkonzepte](#3-kernkonzepte)
4. [CLI-Befehlsreferenz & Praxisbeispiele](#4-cli-befehlsreferenz--praxisbeispiele)
5. [Auto-Detect-Daemon & Watcher-Anleitung](#5-auto-detect-daemon--watcher-anleitung)
6. [Datenwiederherstellung & Restore-Anleitung](#6-datenwiederherstellung--restore-anleitung)
7. [Konfiguration & eigene Ausschlüsse](#7-konfiguration--eigene-ausschlüsse)
8. [Plattform-Besonderheiten & Fehlerbehebung](#8-plattform-besonderheiten--fehlerbehebung)
9. [Anhang](#9-anhang)

---

## 1. Überblick & Philosophie

**SmartBackup** sichert Arbeitsdaten von Entwicklern (standardmäßig den Ordner `Documents`) auf ein
externes Laufwerk und überspringt dabei automatisch Entwicklungsartefakte wie `node_modules`,
virtuelle Umgebungen, Build-Ausgaben, Versionskontroll-Metadaten und Caches.

### Zentrale Highlights

| Highlight | Bedeutung in der Praxis |
|---|---|
| **Intelligentes Filtern** | Eine vierstufige Ausschluss-Engine (exakte Namen, Dateiendungen, Glob-Muster, Strukturerkennung virtueller Umgebungen) überspringt Gigabyte an regenerierbaren Artefakten, noch bevor sie kopiert werden. |
| **Minimale Abhängigkeiten** | Zur Laufzeit werden nur [`rich`](https://github.com/Textualize/rich) und [`typer`](https://github.com/tiangolo/typer) benötigt. Komprimierung, Hashing, Manifeste und Wiederherstellung nutzen ausschließlich die Python-Standardbibliothek — keine externen Binärprogramme. |
| **Manifestbasierte Änderungserkennung** | Ein JSON-Manifest (`.smartbackup_manifest.json`) oder SQLite-Manifest (`.smartbackup_manifest.db`) direkt *auf dem Backup-Laufwerk* speichert Größe, Änderungszeitpunkt (`mtime`) und optional den SHA-256-Hash jeder Datei, sodass spätere Läufe nur neue/geänderte Dateien kopieren und in der Quelle gelöschte Dateien entfernen. |
| **Geräte-Isolation per Hostname** | Jeder Rechner sichert in `Documents-Backup/<hostname>/`, sodass mehrere Computer sicher ein gemeinsames externes Laufwerk nutzen können, ohne sich gegenseitig zu überschreiben. |
| **Plattformübergreifend, ohne Konfiguration** | Windows, macOS und Linux werden vollständig unterstützt — mit automatischer Erkennung des `Documents`-Ordners, externer Laufwerke sowie nativer Terminal-/OS-Integration. |

### Was SmartBackup *nicht* ist

- **Kein Archivierungs- oder Versionierungssystem.** Löschungen in der Quelle **werden ins Backup
  übernommen** (die Quelle wird gespiegelt). Alte Versionen geänderter Dateien werden nicht
  aufbewahrt.
- **Nicht verschlüsselt.** Derzeit gibt es noch keine Verschlüsselung (auf der Roadmap geplant).
- **Kein Deduplizierungs- oder Remote-Backup-Tool.** Kein SSH, keine Cloud-Backends, keine
  Block-Deduplizierung, keine Aufbewahrungsrichtlinien.

Nutze SmartBackup für schnelle, lokale „kopiere meine Arbeitsdateien auf einen USB-Stick“-Backups.
Für Point-in-Time-Notfallwiederherstellung kombiniere SmartBackup mit einer entsprechenden
Speziallösung.

### Voraussetzungen

- Python **3.9 oder neuer** (`requires-python = ">=3.9"`) — oder kein Python bei Nutzung der eigenständigen Binärdatei
- Ein beschreibbares Ziel: externes Laufwerk, USB-Stick oder ein beliebiges Verzeichnis
- Mindestens ~100 MB freier Speicherplatz auf dem Ziel (Mindestwert der automatischen Erkennung)

---

## 2. Installation & Voraussetzungen

Alle Beispiele in diesem Handbuch verwenden den Befehl `smartbackup`. Ohne Installation funktioniert
jedes Beispiel identisch über `python main.py` (aus dem Repository-Wurzelverzeichnis) oder
`python -m smartbackup`.

### Option 1 — Direkt ausführen (ohne Installation)

```bash
git clone https://github.com/CodingWithMK/smartbackup_file-backup-automation.git
cd smartbackup_file-backup-automation

python main.py            # Backups funktionieren ganz ohne Installationsschritt
```

`main.py` fügt `src/` automatisch zu `sys.path` hinzu, sodass keine Installation erforderlich ist.

### Option 2 — Installation mit pip

```bash
git clone https://github.com/CodingWithMK/smartbackup_file-backup-automation.git
cd smartbackup_file-backup-automation

pip install .             # reguläre Installation → stellt den Befehl `smartbackup` bereit
```

Editierbare (Entwicklungs-)Installation:

```bash
pip install -e ".[dev]"   # -e = live-editierbar, [dev] installiert pytest, pytest-cov, ruff
```

### Option 3 — Installation mit uv (empfohlen für Entwickler)

```bash
git clone https://github.com/CodingWithMK/smartbackup_file-backup-automation.git
cd smartbackup_file-backup-automation

uv venv
source .venv/bin/activate          # Windows (PowerShell): .venv\Scripts\Activate.ps1
                                   # Windows (CMD):        .venv\Scripts\activate.bat
uv pip install -e ".[dev]"
```

### Installation überprüfen

```bash
smartbackup --version
# smartbackup 0.9.0

smartbackup --help          # vollständige Optionsliste (auch für jeden Unterbefehl verfügbar)
```

### Deinstallieren / Aktualisieren

```bash
pip uninstall smartbackup
pip install . --upgrade      # aus einem aktuellen Klon zum Aktualisieren
```

### Übersicht der Einstiegspunkte

| Einstiegspunkt | Installation nötig? | Hinweise |
|---|---|---|
| `smartbackup` | Ja (`pip install .` oder Standalone-Installer) | Konsolen-Skript definiert als `smartbackup = smartbackup:main` |
| `python -m smartbackup` | Ja (Paket muss importierbar sein) | Identischer Codepfad wie das Konsolen-Skript |
| `python main.py` | Nein | Komfort-Starter im Repo-Root; fügt `src/` zu `sys.path` hinzu |

---

## 3. Kernkonzepte

### 3.1 Inkrementelles Manifest-Tracking

Nach jedem Backup-Lauf schreibt SmartBackup ein Manifest auf das Backup-Laufwerk:

```
<backup>/Documents-Backup/<Device>/.smartbackup_manifest.json
```

*(Oder `.smartbackup_manifest.db` bei Verwendung von `--manifest-format sqlite`.)*

Das Manifest speichert pro Datei: `hash` (SHA-256, optional), `size`, `mtime`, `permissions`,
`backed_up_at` — sowie Kopf-Metadaten: `source` (ursprünglicher Quellpfad), `hostname`,
`hash_algorithm`, `backup_count`, `total_files`, `total_size`, `created`, `updated`.

**So entscheidet ein Lauf, was kopiert wird:**

1. Quellbaum scannen und Ausschlüsse anwenden (siehe [3.5](#35-was-wird-ausgeschlossen)).
2. Jede Quelldatei in dieser Reihenfolge mit dem Manifest-Eintrag vergleichen:
   - **Größe (`size`)** unterscheidet sich → geändert (`modified`)
   - **Änderungszeit (`mtime`)** unterscheidet sich → geändert (`modified`)
   - beide Seiten haben einen **Hash** und er unterscheidet sich → geändert (`modified`)
   - nicht im Manifest vorhanden → neu (`new`)
   - Manifest-Eintrag ohne Quelldatei → **gelöscht (`deleted`)** (wird aus dem Backup entfernt)
3. Neue Dateien kopieren, geänderte aktualisieren, veraltete löschen (multithreaded, bis zu
   `min(8, CPU-Kerne)` Worker).
4. Manifest atomar neu schreiben (temporäre Datei + Umbenennen, damit ein Stromausfall es nicht
   beschädigen kann).

**Wichtige Auswirkungen:**

- **Löschungen werden ins Backup gespiegelt.** Wenn du eine Datei lokal löschst, entfernt das
  nächste Backup sie ebenfalls vom Laufwerk. Das ist gewollt — SmartBackup spiegelt deinen
  Arbeitsstand.
- **Das Manifest liegt auf dem Ziellaufwerk**, sodass der inkrementelle Zustand auch nach einer
  Neuinstallation von SmartBackup erhalten bleibt.
- **`--no-manifest`** deaktiviert das Manifest-Tracking und fällt auf einen klassischen
  Quelle-gegen-Backup-Vergleich (`ChangeDetector`: Größe + mtime, plus Hash bei `--hash`) zurück.
- **Ein beschädigtes oder fehlendes Manifest** ist unkritisch: es wird eine Warnung ausgegeben und
  das Manifest neu aufgebaut (dabei werden alle Dateien einmalig neu kopiert — sicher, nur langsamer).

**Der Trockenlauf (`--dry-run`) schreibt garantiert nichts.** `--dry-run` (sowohl vollständig als
auch `--select --dry-run`) simuliert Scan und Diff und gibt aus, was *passieren würde* — ohne
Zielordner anzulegen, Dateien zu kopieren oder zu löschen, Manifeste (`.smartbackup_manifest.json`
/ `.smartbackup_manifest.db`) zu erstellen oder zu ändern, Legacy-Layouts zu migrieren,
Komprimierungsarchive zu erzeugen oder `.log`-Dateien zu schreiben. Du kannst unmittelbar vor einem
echten Backup gefahrlos einen Trockenlauf ausführen: das Zielmedium bleibt vollkommen unberührt und
der anschließende echte Lauf sieht jede ausstehende Änderung.

### 3.2 Automatische Erkennung externer Laufwerke

Ohne `--target` ermittelt SmartBackup potenzielle Ziellaufwerke plattformspezifisch:

| OS | Methode | Was wird erkannt? |
|---|---|---|
| **Windows** | Win32 `GetLogicalDrives` + `GetDriveTypeW` | Laufwerksbuchstaben **D:**–**Z:** vom Typ *Removable* oder *Fixed*, die existieren (Fallback: einfaches Buchstaben-Scanning) |
| **macOS** | `/Volumes`-Scan | Alle gemounteten Volumes außer `Macintosh HD`, `Macintosh HD - Data`, `Macbook`, `Macbook - Data` sowie versteckte `.…`-Volumes (inkl. `.timemachine`) |
| **Linux** | Mountpoint-Scan | Unterverzeichnisse unter `/media/$USER`, `/run/media/$USER`, `/mnt` |

Auswahlregeln (`DeviceDetector.find_backup_device`):

1. Laufwerke mit **weniger als 100 MB freiem Speicher** werden ausgeschlossen.
2. Stimmt `--label` (oder `preferred_target` in der Konfiguration) — unabhängig von Groß-/Kleinschreibung —
   mit einem Laufwerksnamen überein, gewinnt dieses Laufwerk sofort.
3. Bleibt genau ein Kandidat übrig, wird dieser verwendet.
4. Bleiben mehrere Kandidaten übrig, werden sie aufgelistet und der **erste automatisch gewählt**.
   Verwende `--label` oder `--target`, um ein bestimmtes Laufwerk festzulegen.

> **Achtung:** Unter Windows und Linux zählen auch *Fixed*-Laufwerke (zweite interne Festplatten)
> als Kandidaten. Wenn mehrere Laufwerke verbunden sind, lege das Ziel immer mit `--target PATH`
> oder `--label NAME` (bzw. `preferred_target` in der Konfiguration) fest.

**Wird kein Laufwerk gefunden**, bietet SmartBackup folgende Optionen:

```
Options:
  [1] Create local temporary backup   → schreibt nach ~/.local_backup_temp
  [2] Wait and try again              → Laufwerk anschließen und Enter drücken (bis zu 3 Versuche)
  [3] Cancel                          → ohne Backup beenden
```

Verfügbare Laufwerke anzeigen:

```bash
smartbackup --list-drives
# Tabelle: No. | Label | Path | Free
```

### 3.3 Mehrgeräte-Unterstützung (Hostname-Isolation)

Der Geräteordnername wird aus `platform.node()` abgeleitet:

1. Domain-Endungen werden entfernt (z. B. `.local` unter macOS mDNS, Firmen-FQDNs).
2. Alle Zeichen außer Buchstaben, Ziffern, `-` und `_` werden durch `-` ersetzt, doppelte `-`
   zusammengefasst und Ränder getrimmt.
3. Bleibt nichts übrig, gilt `unknown-device`.

Beispiel: `Musabs-MacBook-Pro.local` → `Musabs-MacBook-Pro`.

```
YOUR_EXTERNAL_DRIVE/
└── Documents-Backup/
    ├── Musabs-MacBook-Pro/          ← dieser Rechner (hostname-basiert)
    │   ├── .smartbackup_manifest.json
    │   ├── _backup_logs/
    │   │   └── backup_20260924_093022.log
    │   └── ... deine Dateien ...
    ├── Office-Desktop/              ← ein weiterer Rechner auf demselben Laufwerk
    │   └── ...
    └── Musabs-MacBook-Pro_20260228_093022.zip   ← Archive liegen hier (siehe §4)
```

- **Gerätenamen für einen Lauf überschreiben:** `--device-name "Work-Laptop"`.
- **Legacy-Flachlayouts** (Dateien direkt unter `Documents-Backup/`) werden beim nächsten Backup
  automatisch nach `Documents-Backup/<hostname>/` migriert.
- **Geräte auf einem Laufwerk auflisten:**
  `smartbackup --list-devices --target /path/to/drive` (Tabelle: Device | Files | Size | Last Backup).

### 3.4 Verzeichnisstruktur auf dem Backup-Medium

```
<target>/
└── Documents-Backup/                     # fester Ordnername (interne Option: --backup-folder)
    ├── <Device>/                         # ein Ordner pro Rechner
    │   ├── .smartbackup_manifest.json    # inkrementeller Zustand (oder .smartbackup_manifest.db bei --manifest-format sqlite)
    │   ├── _backup_logs/                 # eine Protokolldatei pro Lauf
    │   │   └── backup_YYYYMMDD_HHMMSS.log
    │   └── <gespiegelter Quellbaum>
    ├── <Device>_YYYYMMDD_HHMMSS.zip      # optionale Archive (--compress / `compress`)
    └── <Device>_YYYYMMDD_HHMMSS.tar.gz
```

Jeder echte Lauf schreibt eine Protokolldatei mit Konfiguration, Zusammenfassung
(Dateien/Größe/Dauer/Geschwindigkeit) und einer Liste aller Dateiaktionen (`[COPIED]`, `[UPDATED]`,
`[SKIPPED]`, `[DELETED]`, `[ERROR]`).

### 3.5 Was wird ausgeschlossen?

Jeder gescannte Eintrag durchläuft vier Stufen (erster Treffer gewinnt), verglichen gegen den
**Datei-/Ordnernamen** (unabhängig von Groß-/Kleinschreibung):

1. **Exakter Name** — z. B. `node_modules`, `.git`, `venv`, `__pycache__`, `dist`, …
2. **Ausgeschlossene Dateiendung** — `.pyc .pyo .pyd .class .o .obj .exe .dll .so .dylib .log .tmp .temp`
3. **Glob-Muster** — Einträge mit `*`/`?`: `*.egg-info`, `*.swp`, `*.swo`, `*.tmp`, `*.temp`,
   `*.log`, `*.bak`, `~*`
4. **Strukturerkennung virtueller Umgebungen** — Verzeichnisse mit `pyvenv.cfg`, `Scripts/activate`,
   `bin/activate`, `Scripts/python.exe`, `bin/python` oder `lib/python3` werden unabhängig vom Namen
   als Python-venv übersprungen.

Die vollständige Standardliste steht in [Anhang B](#b-standard-ausschlüsse). Eigene Regeln sind in
[§7](#7-konfiguration--eigene-ausschlüsse) beschrieben.

### 3.6 Interaktive selektive Ordner-Sicherung (`--select`)

Wenn du nur bestimmte Hauptordner aus `Documents` (oder `--source`) sichern möchtest, verwende
`--select`:

```bash
smartbackup --select
smartbackup --select --source ~/Documents --target /media/USB_DRIVE
smartbackup --select --dry-run                 # Ordner auswählen und ohne Schreibvorgänge simulieren
smartbackup --select --manifest-format sqlite  # selektiven Verlauf in SQLite protokollieren
```

**Interaktive Tastatursteuerung** (ohne zusätzliche Abhängigkeiten — nur `rich` + Standardbibliothek):

| Taste | Aktion |
|---|---|
| `↑` / `↓` (oder `k` / `j`) | Cursor bewegen (Viewport scrollt bei großen Ordnerlisten automatisch) |
| `Space` | Checkbox für den markierten Ordner umschalten |
| `a` | Alle auswählen / abwählen |
| `Enter` | Auswahl bestätigen (mindestens 1 Ordner muss markiert sein) |
| `Esc` / `q` / `Ctrl+C` | Sauber abbrechen (Exit-Code `0`, kein Backup-Lauf) |

**Garantien und Prüfprotokoll:**

- **Nur Ordner, wurzelrelative Pfade:** `--select` listet nicht versteckte, nicht ausgeschlossene
  Top-Level-Ordner auf und spiegelt sie unter `Documents-Backup/<Device>/<Ordner>/...`
  (wurzelrelativ), sodass selektive Backups zu 100 % mit Vollbackups und `smartbackup restore`
  kompatibel bleiben.
- **Schutz nicht ausgewählter Ordner & loser Wurzeldateien:** Dateien in *nicht* ausgewählten
  Ordnern (sowie lose Dateien direkt im Quellverzeichnis) werden niemals als gelöscht markiert und
  niemals auf dem Backup-Laufwerk verändert oder entfernt — bei JSON-Manifesten, SQLite-Manifesten
  und `--no-manifest`.
- **Eigene Log- und Manifest-Abschnitte:**
  - Backup-Logs enthalten `Mode: Selective (--select)` sowie einen eigenen Block
    `SELECTIVE BACKUP (--select)` mit nummeriertem `SELECTIVE WORKFLOW TRACE` direkt vor `SUMMARY:`.
  - JSON-Manifeste speichern `last_backup_mode`, `last_selected_folders` und `selective_backups`;
    SQLite-Manifeste speichern den selektiven Verlauf in einer eigenen **`selective_backups`-Tabelle**,
    sauber getrennt von `files` und `metadata` (bleibt bei JSON ↔ SQLite-Migrationen erhalten).
  - `smartbackup --show-manifest --target <path>` zeigt `Last Backup Mode` und die Tabelle
    `Selective Backup History (--select)`.
- **Interaktives TTY erforderlich:** Wird `--select` in einer nicht-interaktiven/gepipeten Umgebung
  aufgerufen, bricht der Befehl sofort mit Exit-Code `1` ab.

---

## 4. CLI-Befehlsreferenz & Praxisbeispiele

### Befehlsbaum

```
smartbackup [OPTIONS]                    # Standardaktion = Backup ausführen
├── restore [OPTIONS]                    # Dateien aus einem Backup wiederherstellen
├── compress [OPTIONS]                   # bestehendes Backup archivieren
├── watch [OPTIONS]                      # Laufwerksüberwachung im Vordergrund
├── schedule [OPTIONS]                   # OS-spezifische Zeitplan-Anleitung ausgeben
├── config                               # dauerhafte Konfiguration anzeigen/ändern
│   ├── list / get / set / unset
│   └── exclude / unexclude
└── daemon                               # Hintergrunddienst verwalten
    ├── install
    ├── status
    ├── uninstall
    └── clear-state
```

Jeder Befehl unterstützt `--help` (`smartbackup restore --help`, …).

### 4.1 Optionen des Hauptbefehls (`smartbackup`)

| Option | Kurz | Argument | Standard | Beschreibung |
|---|---|---|---|---|
| `--source` | `-s` | PATH | Ordner `Documents` | Zu sicherndes Quellverzeichnis |
| `--target` | `-t` | PATH | externe Erkennung | Zielverzeichnis / Ziellaufwerk |
| `--label` | `-l` | TEXT | — | Bevorzugter Laufwerksname (Groß-/Kleinschreibung ignoriert) |
| `--prompt` | | | aus | Interaktive `[Y/n/d]`-Abfrage für ein erkanntes Laufwerk starten |
| `--select` | | | aus | Interaktives Tastaturmenü zur Auswahl einzelner Hauptordner öffnen (TTY nötig; siehe [§3.6](#36-interaktive-selektive-ordner-sicherung---select)) |
| `--dry-run` | | | aus | Backup ohne Schreibvorgänge simulieren (keine Ordner, Dateien, Manifeste oder Logs; siehe [§3.1](#31-inkrementelles-manifest-tracking)) |
| `--quiet` | `-q` | | aus | Minimale Ausgabe (Banner + Zusammenfassung bleiben sichtbar; Einzeldatei-Logs unterdrückt) |
| `--exclude` | | TEXT (wiederholbar) | — | Ausschlussmuster hinzufügen. **Wird dauerhaft in `config.json` gespeichert und sofort angewendet** — siehe [§7.3](#73-eigene-ausschlüsse-hinzufügen) |
| `--list-drives` | | | — | Verfügbare externe Laufwerke auflisten und beenden |
| `--device-name` | | TEXT | erkannter Hostname | Gerätename für den Backup-Unterordner |
| `--list-devices` | | | — | Geräte mit Backups auf dem Ziellaufwerk auflisten (`--target` erforderlich) |
| `--no-manifest` | | | aus | Manifest-Tracking deaktivieren (klassischer Größe/mtime-Vergleich) |
| `--manifest-format` | | FORMAT | Konfig `manifest_format`, sonst `json` | Manifest-Backend: `json` (`.smartbackup_manifest.json`) oder `sqlite` (`.smartbackup_manifest.db`) |
| `--show-manifest` | | | — | Manifest-Inhalt & selektiven Verlauf anzeigen (`--target` erforderlich) |
| `--verify` | | | — | Backup gegen Manifest prüfen (inkl. gespeicherter Hashes) (`--target` erforderlich) |
| `--notify` | | | aus | OS-Desktop-Benachrichtigung nach Abschluss senden |
| `--compress` | | FORMAT | — | Backup nach dem Kopieren komprimieren: `zip` oder `tar.gz` |
| `--hash` | | | aus | SHA-256-Änderungserkennung für Dateien **bis 50 MB** |
| `--hash-all` | | | aus | SHA-256 für **alle** Dateien unabhängig von der Größe (impliziert `--hash`; langsamer) |
| `--version` | `-v` | | — | `smartbackup 0.9.0` ausgeben und beenden |
| `--help` | `-h` | | — | Hilfe anzeigen und beenden |

### 4.2 Praxisbeispiele für den Alltag

**Basis-Backups**

```bash
smartbackup                                   # Documents → automatisch erkanntes externes Laufwerk
python main.py                                # dasselbe ohne Installation

smartbackup --source ~/Projects               # benutzerdefinierten Ordner sichern
smartbackup --target /media/USB_DRIVE         # in einen expliziten Zielpfad sichern
smartbackup --target E:\                      # Windows-Beispiel
smartbackup --label "MY_BACKUP_DISK"          # Laufwerk anhand des Volume-Labels finden
smartbackup --device-name "Work-Laptop"       # eigener Geräte-Unterordner
smartbackup --quiet                           # minimale Ausgabe (Skripte/CI)
```

**Vorschau vor dem Start**

```bash
smartbackup --dry-run                         # Backup simulieren (keine Schreibvorgänge)
smartbackup --select                          # bestimmte Ordner interaktiv auswählen
smartbackup --select --dry-run                # Ordner auswählen und ohne Schreibvorgänge testen
smartbackup --list-drives                     # welche Laufwerke sind sichtbar?
smartbackup --target /media/USB --list-devices      # welche Geräte sind hier gesichert?
smartbackup --target /media/USB --show-manifest     # Manifest-Zusammenfassung anzeigen
```

**Integritätsprüfung (gestuftes SHA-256-Hashing)**

```bash
smartbackup --hash                            # SHA-256 für Dateien ≤ 50 MB beim Backup speichern
smartbackup --hash-all                        # SHA-256 für alle Dateien speichern (gründlich)
smartbackup --target /media/USB --verify      # Existenz + Größe + gespeicherte Hashes prüfen
```

So arbeiten die Stufen:

- **Standard (kein Flag):** Änderungserkennung per Größe + `mtime`.
- **`--hash`:** Dateien ≤ 50 MB werden in 64-KB-Blöcken gehasht und im Manifest gespeichert; bei
  späteren Läufen deckt ein Hash-Unterschied Änderungen selbst bei identischer Größe/`mtime` auf.
- **`--hash-all`:** Jede Datei wird gehasht — ideal für Bit-Rot-Erkennung oder Netzlaufwerke mit
  unzuverlässiger `mtime`.
- **`--verify`:** Liest das Backup unabhängig neu ein und meldet `Missing:`, `Size mismatch:` und
  `Hash mismatch:`. Exit-Code `0` = fehlerfrei, `1` = Probleme gefunden.

**Komprimierung**

```bash
smartbackup --compress zip                    # sichern und als ZIP archivieren
smartbackup --compress tar.gz                 # sichern und als tar.gz archivieren

# Ein bestehendes Backup nachträglich archivieren:
smartbackup compress --target /media/USB --format zip
smartbackup compress --target /media/USB --format tar.gz --device-name "Office-Desktop"
smartbackup compress --target /media/USB --format zip --remove-source   # Ordner nach Erfolg löschen
```

- Archive werden unter `Documents-Backup/` als `<Device>_<YYYYMMDD_HHMMSS>.zip|tar.gz` abgelegt.
- Die Komprimierung nutzt atomares Schreiben über temporäre Dateien + Umbenennen.
- `--compress` am Hauptbefehl löscht den unkomprimierten Ordner **nicht** — nur
  `compress --remove-source` entfernt ihn.

**Manifest-Verwaltung**

```bash
smartbackup --target /media/USB --show-manifest    # Version, Format, Quelle, Hostname, Summen
smartbackup --target /media/USB --verify           # inkl. Hash-Prüfung
smartbackup --no-manifest                          # Manifest-Tracking deaktivieren
```

### 4.3 Optionen für `smartbackup restore`

| Option | Kurz | Argument | Beschreibung |
|---|---|---|---|
| `--source` | `-s` | PATH | **Erforderlich.** Laufwerk/Verzeichnis, das `Documents-Backup/` *enthält* |
| `--target` | `-t` | PATH | Wiederherstellungsziel (Standard: ursprünglicher Quellpfad aus dem Manifest) |
| `--pattern` | `-p` | TEXT (wiederholbar) | Glob-Filter auf den relativen Pfad (`fnmatch`), z. B. `"*.py"` |
| `--overwrite` | | | Vorhandene Dateien überschreiben (Legacy-Alias für `--conflict overwrite`) |
| `--conflict` | | TEXT | Konfliktstrategie: `skip` (Standard), `overwrite`, `newer`, `rename`. Hat Vorrang vor `--overwrite` |
| `--dry-run` | | | Wiederherstellung ohne Kopieren simulieren |
| `--list` | | | Dateien im Backup auflisten und beenden |
| `--manifest-info` | | | Manifest-Metadaten als Tabelle anzeigen und beenden |
| `--device-name` | | TEXT | Geräte-Unterordner für die Wiederherstellung (Standard: Hostname, sonst Legacy-Layout) |

### 4.4 Optionen für `smartbackup compress`

| Option | Kurz | Argument | Standard | Beschreibung |
|---|---|---|---|---|
| `--target` | `-t` | PATH | *erforderlich* | Backup-Laufwerk/-Verzeichnis mit `Documents-Backup/` |
| `--format` | `-f` | TEXT | `zip` | `zip` oder `tar.gz` (alles andere → Fehler, Exit `1`) |
| `--device-name` | | TEXT | Hostname | Zu komprimierender Geräteordner |
| `--remove-source` | | | aus | Unkomprimierten Ordner nach erfolgreicher Archivierung löschen |
| `--backup-folder` | | TEXT | `Documents-Backup` | *Versteckte/interne* Option für den Backup-Ordnernamen |

### 4.5 Optionen für `smartbackup watch`

| Option | Kurz | Argument | Standard | Beschreibung |
|---|---|---|---|---|
| `--interval` | `-i` | FLOAT | `2.5` | Prüfintervall in Sekunden |
| `--cooldown` | `-c` | INTEGER | Konfig `auto_watch_cooldown`, sonst `300` | Sperrzeit (Sekunden) zwischen Rückfragen für dasselbe Laufwerk |

### 4.6 Unterbefehle für `smartbackup config`

| Befehl | Beschreibung |
|---|---|
| `smartbackup config list` | Alle Schlüssel, ihre Werte (oder `(not set)`) und den Pfad zur Konfigurationsdatei anzeigen |
| `smartbackup config get <key>` | Einzelnen Wert ausgeben |
| `smartbackup config set <key> <value>` | Wert validieren und dauerhaft speichern |
| `smartbackup config unset <key>` | Schlüssel entfernen (Standardwert greift wieder) |
| `smartbackup config exclude <pattern>...` | Eigene Ausschlussmuster hinzufügen |
| `smartbackup config unexclude <pattern>...` | Eigene Ausschlussmuster entfernen |

Unterstützte Schlüssel: `preferred_target`, `device_name` (wird auf einen dateisystemsicheren
Ordnernamen bereinigt), `auto_watch_cooldown` (Ganzzahl ≥ 0), `preferred_terminal`,
`manifest_format` (`json` oder `sqlite`) und `exclusions` (ausschließlich über `exclude`/`unexclude`).

```bash
smartbackup config set auto_watch_cooldown 60
smartbackup config set device_name "Work Laptop"    # gespeichert als Work-Laptop
smartbackup config set preferred_target MY_BACKUP_DISK
smartbackup config set manifest_format sqlite
smartbackup config exclude "*.iso" "LargeDatasets"
smartbackup config unexclude "*.iso"
smartbackup config list
```

### 4.7 Unterbefehle für `smartbackup daemon`

| Befehl | Beschreibung |
|---|---|
| `smartbackup daemon install` | OS-Hintergrunddienst registrieren **und starten** |
| `smartbackup daemon status` | Status (Installiert / Läuft mit PID / Dienstpfad / Details) anzeigen |
| `smartbackup daemon uninstall` | Hintergrunddienst stoppen und entfernen |
| `smartbackup daemon clear-state` | Debounce-Status des Watchers (`watcher_state.json`) zurücksetzen |

Details siehe [§5](#5-auto-detect-daemon--watcher-anleitung).

### 4.8 Exit-Codes

| Code | Bedeutung |
|---|---|
| `0` | Erfolg (auch bei Dry-Run/List/Manifest-Befehlen, Abbruch von `--select`/`--prompt` durch den Nutzer, Stoppen des Watchers mit Ctrl+C) |
| `1` | Fehler: Backup-Fehler, Verifizierungsfehler, `--select` ohne interaktives TTY, ungültiges `--compress`/`--manifest-format`, fehlende Verzeichnisse oder fehlendes `--target`/`--source` |
| `130` | Mit Ctrl+C während eines Backups unterbrochen |

---

## 5. Auto-Detect-Daemon & Watcher-Anleitung

SmartBackup kann als *Laufwerks-Watcher* laufen: es überwacht neu angeschlossene Laufwerke und
öffnet bei einem bekannten Backup-Laufwerk automatisch ein natives Terminalfenster mit der Frage,
ob jetzt gesichert werden soll.

### 5.1 Wann ein Laufwerk als „SmartBackup-Ziel“ erkannt wird

Ein Laufwerk löst den Watcher nur aus, wenn **mindestens eine** Bedingung zutrifft (`DriveMatcher`):

1. Sein Label stimmt mit `preferred_target` aus der Konfiguration überein, oder
2. `Documents-Backup/<hostname>/.smartbackup_manifest.json` (bzw. `.db`) existiert, oder
3. der Ordner `Documents-Backup/<hostname>/` existiert, oder
4. Legacy-Layout: `Documents-Backup/.smartbackup_manifest.json` (bzw. `.db`) existiert.

> **Wichtig:** Ein fabrikneues, leeres Laufwerk wird nie automatisch erkannt. Initialisiere es
> einmal manuell mit `smartbackup --target /path/to/drive` — ab dann erkennt der Watcher es
> automatisch.

Gesperrte/unlesbare Laufwerke (z. B. BitLocker unter Windows) werden sicher abgefangen: der Watcher
stürzt nicht ab, sondern überspringt sie.

### 5.2 Testen im Vordergrund: `smartbackup watch`

```bash
smartbackup watch                          # Intervall 2,5 s, Cooldown 300 s
smartbackup watch --interval 1.0           # jede Sekunde prüfen
smartbackup watch --cooldown 60            # maximal eine Rückfrage pro Minute je Laufwerk
```

Stoppen mit **Ctrl+C** (Exit-Code `0`). Beim Start erstellt der Watcher eine **Basis-Momentaufnahme**
bereits angeschlossener Laufwerke — nur *neu erscheinende* Laufwerke lösen eine Rückfrage aus.

### 5.3 Die interaktive Rückfrage `[Y/n/d]`

Bei Erkennung öffnet SmartBackup ein natives Terminalfenster mit:

```
python -m smartbackup --target <drive-path> --prompt
```

*(Bei eigenständigen Binärdateien wird direkt `<smartbackup-binary> --target <drive-path> --prompt` aufgerufen.)*

```
Start backup now? (Y/n/d) [y]:
```

| Eingabe | Akzeptierte Formen | Ergebnis |
|---|---|---|
| **Ja** | `y`, `yes`, *(Enter)* | Normales Backup läuft |
| **Nein** | `n`, `no` | „Backup skipped by user.“ — Exit `0` |
| **Trockenlauf** | `d`, `dry-run`, `dryrun` | Simulation ohne Schreibvorgänge |
| Sonstiges | — | Warnung, danach **Standard-Backup** |
| Ctrl+C | — | „Backup cancelled by user.“ — Exit `0` |

Nach Abschluss zeigt das Fenster `Window will close automatically in 5 seconds...`.

**Debounce-Schutz gegen Mehrfach-Popups:**
- **3 Sekunden globale Unterdrückung** für Laufwerke mit mehreren Partitionen.
- **Laufwerks-Cooldown** (Standard `300` s / 5 Minuten).
- Gespeichert in `<config dir>/watcher_state.json`. Zum sofortigen Zurücksetzen:
  `smartbackup daemon clear-state`.

**Verwendeter Terminal-Emulator:**

| OS | Reihenfolge |
|---|---|
| Windows | Windows Terminal (`wt.exe --title …`) → `cmd.exe` `start` → PowerShell `-NoExit` |
| macOS | iTerm2 (wenn `preferred_terminal` = `iterm`/`iterm2`) → Terminal.app per AppleScript → `open -a Terminal.app` |
| Linux | `preferred_terminal` aus Konfig → `x-terminal-emulator` → `gnome-terminal` → `kitty` → `alacritty` → `konsole` → `xfce4-terminal` → `xterm` |

**Headless-Umgebungen** (Linux ohne `DISPLAY`/`WAYLAND_DISPLAY` oder SSH) öffnen kein GUI-Fenster.
Starte die Abfrage dort manuell: `smartbackup --target /path/to/drive --prompt`.

### 5.4 Hintergrunddienst: `smartbackup daemon`

```bash
smartbackup daemon install      # Watcher-Dienst registrieren + starten
smartbackup daemon status       # Installiert? Aktiv (PID)? Dienstpfad?
smartbackup daemon clear-state  # Debounce-Status löschen
smartbackup daemon uninstall    # stoppen + entfernen
```

| OS | Artefakt | Details |
|---|---|---|
| **Windows** | Geplante Aufgabe `SmartBackupWatcher` | Auslöser: *bei Anmeldung* (`/sc onlogon /rl highest`); startet sofort bei Installation |
| **macOS** | LaunchAgent `~/Library/LaunchAgents/com.smartbackup.watcher.plist` | `RunAtLoad` + `KeepAlive`; Logs unter `~/.config/smartbackup/logs/watcher.log` & `watcher.err.log` |
| **Linux** | systemd **User**-Unit `~/.config/systemd/user/smartbackup-watcher.service` | `Type=simple`, `Restart=always`, `RestartSec=5s` |

Hinweise:
- Der bei `daemon install` aktive Python-Interpreter (bzw. das Standalone-Binary) wird im Dienst
  eingetragen — nicht aus einer temporären venv installieren, die später gelöscht wird.
- **Linux:** Für Start vor dem Login `loginctl enable-linger $USER` aktivieren.
- `daemon uninstall` ist idempotent.

### 5.5 Regelmäßige Backups über das Betriebssystem planen

Mit `smartbackup schedule [--hours N]` (Standard: 24 Stunden) gibt SmartBackup passende Vorlagen
für Windows-Aufgabenplanung, macOS `launchd` oder Linux `cron`/`systemd` aus. Manuelle Beispiele:

**Windows (Aufgabenplanung — als *Administrator*):**

```powershell
schtasks /create /tn "SmartBackup" /tr "smartbackup" /sc daily /st 09:00
```

**macOS (`~/Library/LaunchAgents/com.smartbackup.plist`, danach `launchctl load`):**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.smartbackup</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/python</string><string>-m</string><string>smartbackup</string>
    </array>
    <key>StartInterval</key><integer>86400</integer>
    <key>RunAtLoad</key><true/>
</dict>
</plist>
```

**Linux (cron):**

```cron
0 9 * * * /path/to/python -m smartbackup
```

**Linux (systemd User-Timer):** `~/.config/systemd/user/smartbackup.service` +
`~/.config/systemd/user/smartbackup.timer`, danach `systemctl --user enable --now smartbackup.timer`.

> Ein zeitgesteuertes *Backup* unterscheidet sich vom *Watcher-Daemon* (§5.4): der Daemon erkennt
> nur angeschlossene Laufwerke, führt aber keine zeitgesteuerten Backups aus.

---

## 6. Datenwiederherstellung & Restore-Anleitung

### 6.1 Grundprinzip

Bei `restore` ist `--source` immer das **Laufwerk (oder Verzeichnis), das `Documents-Backup/`
enthält** — derselbe Pfad wie `--target` beim Backup — *nicht* der Geräteordner selbst:

```
smartbackup restore --source /media/USB_DRIVE             # ✅  Laufwerkswurzel
smartbackup restore --source /media/USB_DRIVE/My-Laptop   # ❌  falsch: Documents-Backup/ wird automatisch angehängt
```

Auflösungsreihenfolge in `--source/Documents-Backup/`:

1. `--device-name` (falls angegeben), sonst
2. Legacy-Layout (Manifest direkt in `Documents-Backup/`), sonst
3. `Documents-Backup/<aktueller-hostname>/` (falls vorhanden), sonst
4. der Stammordner selbst.

**Ziel:** `--target` falls angegeben, ansonsten der **ursprüngliche Quellpfad aus dem Manifest**.
Fehlt beides, bricht der Vorgang mit `No target path specified and no manifest source found` ab.

### 6.2 Schritt 1 — Vor dem Wiederherstellen prüfen

```bash
# Inhalt auflisten (aus dem Manifest oder per Verzeichnisscan)
smartbackup restore --source /media/USB_DRIVE --list

# Manifest-Zusammenfassung anzeigen
smartbackup --target /media/USB_DRIVE --show-manifest
smartbackup restore --source /media/USB_DRIVE --manifest-info

# Integritätsprüfung: Existenz + Größe + gespeicherte Hashes
smartbackup --target /media/USB_DRIVE --verify

# Protokolldateien einsehen
cat /media/USB_DRIVE/Documents-Backup/<Device>/_backup_logs/backup_*.log
```

### 6.3 Schritt 2 — Wiederherstellen

```bash
# Vollständige Wiederherstellung an den ursprünglichen Ort (manifest.source)
smartbackup restore --source /media/USB_DRIVE

# In einen eigenen Zielordner wiederherstellen (ideal für Tests oder einen neuen Rechner)
smartbackup restore --source /media/USB_DRIVE --target ~/Restored

# Backup eines bestimmten Geräts auf einem gemeinsam genutzten Laufwerk
smartbackup restore --source /media/USB_DRIVE --device-name "Office-Desktop"

# Mit Glob-Mustern filtern (relativer Pfad; wiederholbar)
smartbackup restore --source /media/USB_DRIVE --pattern "*.py" --pattern "*.md"

# Vorschau — es wird nichts kopiert
smartbackup restore --source /media/USB_DRIVE --dry-run

# Lokal vorhandene Dateien überschreiben
smartbackup restore --source /media/USB_DRIVE --overwrite
```

Wichtige Details:
- Dateien werden mit Metadaten (`copy2`) über **atomare temporäre Dateien + Umbenennen** kopiert.
- Läuft multithreaded (4 Worker).
- Interne Dateien unter `_backup_logs/` sowie `.smartbackup*` werden niemals wiederhergestellt.
- Am Ende erscheint eine `RESTORE SUMMARY`-Tabelle (Exit `0` bei `errors == 0`, sonst `1`).

### 6.4 Konfliktstrategien

Wenn die Zieldatei lokal bereits existiert:

| Strategie | Verhalten | Verfügbarkeit |
|---|---|---|
| **SKIP** | Bestehende lokale Datei behalten; als `Skipped ("File exists")` zählen | ✅ **Standard** (kein Flag oder `--conflict skip`) |
| **OVERWRITE** | Lokale Datei durch Backup-Version ersetzen | ✅ `--conflict overwrite` (oder Legacy `--overwrite`) |
| **NEWER** | Nur überschreiben, wenn `mtime` im Backup neuer ist als lokal; sonst überspringen | ✅ `--conflict newer` |
| **RENAME** | Beide behalten: die wiederhergestellte Kopie wird daneben als `<name>.restored-<YYYYmmdd-HHMMSS>.<ext>` gespeichert (bei Kollisionen `-1`, `-2`, …) | ✅ `--conflict rename` |

> Werden sowohl `--conflict` als auch `--overwrite` angegeben, gewinnt `--conflict`. Unbekannte
> Werte beenden mit Exit `1` und listen alle gültigen Strategien auf.

### 6.5 Aus einem komprimierten Archiv wiederherstellen

`restore` liest **Verzeichnisse**, keine `.zip`/`.tar.gz`-Dateien direkt. Entpacke das Archiv
zuerst in die erwartete Struktur:

```bash
# 1. In den Geräteordner entpacken
mkdir -p /media/USB_DRIVE/Documents-Backup/<Device>
unzip <Device>_<timestamp>.zip -d /media/USB_DRIVE/Documents-Backup/<Device>       # zip
tar -xzf <Device>_<timestamp>.tar.gz -C /media/USB_DRIVE/Documents-Backup/<Device> # tar.gz

# 2. Regulär wiederherstellen
smartbackup restore --source /media/USB_DRIVE --device-name "<Device>"
```

### 6.6 Auf einem anderen Rechner wiederherstellen

Da Geräteordner nach dem Hostnamen benannt sind, gib auf einem anderen Rechner explizit den
ursprünglichen Namen an:

```bash
smartbackup restore --source /media/USB_DRIVE --device-name "Old-Machine-Name"
```

…oder ergänze `--target` für ein explizites Zielverzeichnis. Mit `--list` vorab prüfen.

### 6.7 Häufige Restore-Fehler

| Meldung | Ursache | Lösung |
|---|---|---|
| `Backup directory not found: …` | `--source` zeigt auf `Documents-Backup/` oder den Geräteordner | **Laufwerkswurzel** übergeben |
| `No manifest found` + Scan listet alles auf | Falscher Geräteordner oder Legacy-Layout | `--device-name` angeben oder mit `--list` prüfen |
| `No target path specified and no manifest source found` | Kein `--target` und kein `source` im Manifest | `--target <dir>` übergeben |
| Nichts wiederhergestellt, `No files to restore!` | Muster zu eng oder nur interne Dateien vorhanden | `--pattern` lockern, mit `--list` prüfen |
| `Permission denied` pro Datei | OS-Berechtigungen / geschützte Ordner | In ein eigenes Verzeichnis wiederherstellen (`--target ~/Restored`) |

---

## 7. Konfiguration & eigene Ausschlüsse

### 7.1 Speicherort der Konfiguration

| OS | Pfad |
|---|---|
| **Windows** | `%APPDATA%\SmartBackup\config.json` (typisch `C:\Users\<du>\AppData\Roaming\SmartBackup\config.json`) |
| **macOS** | `~/.config/smartbackup/config.json` |
| **Linux** | `~/.config/smartbackup/config.json` |

Die Datei wird beim ersten Schreiben erstellt. Im selben Verzeichnis liegen `watcher_state.json`
und unter macOS die Daemon-Logs (`logs/watcher.log`, `logs/watcher.err.log`).

### 7.2 Konfigurationsschlüssel

| Schlüssel | Typ | Standard | Wirkung | Per CLI setzbar? |
|---|---|---|---|---|
| `exclusions` | String-Liste | `[]` (mit Standardliste zusammengeführt) | Eigene Ausschlussmuster | ✅ `--exclude` fügt hinzu & wendet an; `config exclude`/`unexclude` |
| `preferred_target` | String | keiner | Bevorzugtes Laufwerkslabel für Backups & Watcher (Groß-/Kleinschreibung ignoriert) | ✅ `config set preferred_target` |
| `device_name` | String | keiner (Hostname) | Überschreibt den erkannten Gerätenamen | ✅ `config set device_name` (bereinigt); `--device-name` gilt nur für einen Lauf |
| `auto_watch_cooldown` | Integer (s) | `300` | Debounce-Sperrzeit des Watchers | ✅ `config set auto_watch_cooldown`; `watch --cooldown` überschreibt pro Lauf |
| `preferred_terminal` | String | keiner | Terminal für Prompt-Fenster (`iterm`/`iterm2` unter macOS, Binärname unter Linux) | ✅ `config set preferred_terminal` |
| `manifest_format` | String | `json` | Manifest-Backend (`json` oder `sqlite`) | ✅ `config set manifest_format`; `--manifest-format` überschreibt pro Lauf |

Beispiel-`config.json`:

```json
{
  "exclusions": ["*.iso", "Downloads", "LargeDatasets"],
  "preferred_target": "MY_BACKUP_DISK",
  "device_name": "Work-Laptop",
  "auto_watch_cooldown": 300,
  "preferred_terminal": "iTerm2",
  "manifest_format": "sqlite"
}
```

### 7.3 Eigene Ausschlüsse hinzufügen

**Über die CLI:**

```bash
smartbackup --exclude "*.iso" "Downloads" "LargeDatasets"
```

Jeder `--exclude`-Wert wird **dauerhaft in `config.json` gespeichert** und **sofort im aktuellen
Lauf angewendet** (`ConfigManager.get_exclusions()` = Standardausschlüsse + eigene Muster). Spätere
Läufe berücksichtigen diese Muster automatisch, ohne dass das Flag wiederholt werden muss.

**Gespeichertes Muster entfernen:** `smartbackup config unexclude "*.iso"` (oder direkt im
`exclusions`-Array der `config.json`).

### 7.4 Bevorzugtes Backup-Laufwerk festlegen (`preferred_target`)

Damit du nicht bei jedem Lauf `--target` angeben musst (und der Watcher das Laufwerk erkennt):

1. Label ermitteln: `smartbackup --list-drives` (Spalte **Label**).
2. Speichern: `smartbackup config set preferred_target MY_BACKUP_DISK`.
3. Der Abgleich ignoriert Groß-/Kleinschreibung und versteht sowohl Windows-Laufwerksbuchstaben
   (`E:` / `E:\`) als auch Volume-/Ordnernamen unter macOS und Linux.

Einmalige (nicht gespeicherte) Entsprechung: `smartbackup --label "MY_BACKUP_DISK"`.

---

## 8. Plattform-Besonderheiten & Fehlerbehebung

### 8.1 Windows

- **BitLocker-gesperrte Laufwerke:** Gesperrte Volumes lösen `PermissionError`/`OSError` aus.
  `DriveMatcher` fängt diese sauber ab — der Watcher stürzt nicht ab, aber es erscheint **erst nach
  dem Entsperren eine Abfrage** (`manage-bde -unlock D: -password` oder über den Explorer).
- **Terminal-Fallback-Kette:** Windows Terminal (`wt.exe`) → `cmd.exe` `start` → PowerShell
  `-NoExit`. Öffnet sich keines, manuell starten: `python -m smartbackup --target E:\ --prompt`.
- **Laufwerksbuchstaben:** Die Erkennung prüft **D:**–**Z:**; das Systemlaufwerk (`C:`) wird nie
  als automatisches Backup-Ziel gewählt.
- **Alte Konsolen-Codierung:** SmartBackup aktiviert UTF-8 automatisch (`ensure_utf8_console()`).
  Bei sehr alten Konsolen hilft Windows Terminal oder `$env:PYTHONUTF8="1"; smartbackup`.

### 8.2 macOS

- **Terminal-Emulation:** Öffnet standardmäßig **Terminal.app** per AppleScript. Für **iTerm2**:
  `smartbackup config set preferred_terminal iterm2`.
- **System-/Time-Machine-Ausschlüsse:** Der `/Volumes`-Scan überspringt `Macintosh HD`,
  `Macintosh HD - Data`, `Macbook`, `Macbook - Data`, versteckte Volumes sowie `.timemachine`.
- **Berechtigungen (TCC):** Bei `Permission denied` dem Terminal (Terminal.app/iTerm2) unter
  *Systemeinstellungen → Datenschutz & Sicherheit → Festplattenvollzugriff* Zugriff gewähren und das
  Terminal neu starten.
- **Automatisierungsabfrage:** Beim ersten `osascript`-Aufruf kann macOS eine Zustimmung anfordern.

### 8.3 Linux

- **Mountpoints:** Externe Medien werden unter `/media/$USER`, `/run/media/$USER` und `/mnt` gesucht.
  Bei abweichenden Mountpoints explizit `--target /dein/mount` angeben.
- **systemd User-Units:** `daemon install` erstellt `~/.config/systemd/user/smartbackup-watcher.service`
  und führt `systemctl --user daemon-reload` + `enable --now` aus. Ohne User-D-Bus stattdessen
  `smartbackup watch` im Terminal nutzen.
- **Headless / SSH:** Ohne `DISPLAY`/`WAYLAND_DISPLAY` öffnet der Watcher keine GUI-Fenster.
- **Berechtigungen:** Vor dem Start wird ein Schreibtest durchgeführt; `No write permissions on backup medium`
  deutet auf ein schreibgeschütztes Mount oder fehlende Eigentümerrechte hin.

### 8.4 Fehlerbehebungs-Matrix

| Symptom | Wahrscheinliche Ursache | Lösung |
|---|---|---|
| `EXTERNAL STORAGE MEDIUM NOT FOUND` | Kein geeignetes Laufwerk mit ≥ 100 MB frei / nicht gemountet | `--list-drives`; Mount prüfen; `--target` nutzen oder Option `[1]` für lokales Temp-Backup wählen |
| Backup landete auf unerwartetem Laufwerk | Mehrere Kandidaten, erster wurde automatisch gewählt | Mit `--target` oder `--label` / `preferred_target` fixieren |
| `Please specify backup directory with --target` | `--list-devices`, `--show-manifest` oder `--verify` ohne `--target` | `--target <Laufwerkswurzel>` ergänzen |
| Watcher läuft, **fragt aber nie nach** | Neues Laufwerk (§5.1 trifft nicht zu), Cooldown aktiv oder Headless | Einmal manuell sichern; `smartbackup daemon clear-state` ausführen; `daemon status` prüfen |
| Zweites Backup kopiert *alles* neu | Manifest fehlt/beschädigt oder `--no-manifest` genutzt | Normale Wiederherstellung — Manifest wird neu erstellt; bei Wiederholung Laufwerk prüfen |
| `Full metadata copy failed … Falling back to basic copy` | ExFAT/FAT32 unterstützt keine vollständigen POSIX-Metadaten | Normal; `mtime` wird manuell erhalten |
| `The --select option requires an interactive terminal (TTY)` | `--select` in nicht-interaktiver/gepipeter Shell oder CI gestartet | In interaktivem Terminal ausführen oder `--select` weglassen |
| `Storage medium error (drive may have been disconnected)` | Laufwerk während des Laufs getrennt | Neu anschließen und erneut starten; bereits kopierte Dateien stehen im Manifest |
| Restore findet nichts | `--source` zeigt auf Geräteordner statt Laufwerkswurzel | Laufwerkswurzel angeben (§6.1) |
| Daemon stoppte nach Python-/venv-Neuinstallation | Dienst verweist auf alten Interpreter-Pfad | In der aktiven Umgebung `smartbackup daemon uninstall` und danach `install` ausführen |

### 8.5 Bekannte Einschränkungen (aktueller Stand)

1. `restore` verarbeitet nur Verzeichnisse — Archive vorher entpacken (§6.5).
2. Keine Verschlüsselung, Deduplizierung, Versionierung oder Remote-Ziele (§1).
3. `--select` arbeitet derzeit ausschließlich auf Top-Level-Ordnern (nicht auf einzelnen Wurzeldateien).

---

## 9. Anhang

### A. Schnellübersicht der Optionen

```text
smartbackup [OPTIONS]
  -s, --source PATH        Quellverzeichnis (Standard: Documents)
  -t, --target PATH        Ziellaufwerk/-verzeichnis (Standard: automatisch erkennen)
  -l, --label TEXT         Bevorzugtes Ziellaufwerk-Label
      --prompt             Interaktiver [Y/n/d]-Abfragemodus
      --select             Interaktive Ordnerauswahl (Top-Level-Ordner, TTY erforderlich)
      --dry-run            Simulieren (keine Schreibvorgänge: keine Ordner, Dateien, Manifeste, Logs)
  -q, --quiet              Minimale Ausgabe
      --exclude TEXT       Zusätzliche Ausschlussmuster dauerhaft in config.json speichern
      --list-drives        Verfügbare Laufwerke anzeigen und beenden
      --list-devices       Geräte auf --target anzeigen und beenden
      --device-name TEXT   Geräte-Unterordner (Standard: Hostname)
      --show-manifest      Manifest-Statistiken für --target anzeigen und beenden
      --verify             Backup gegen Manifest prüfen und beenden
      --no-manifest        Manifest-Tracking deaktivieren
      --manifest-format    json | sqlite (Standard: Konfig manifest_format, sonst json)
      --notify             Desktop-Benachrichtigung bei Abschluss senden
      --compress FORMAT    zip | tar.gz nach dem Kopieren
      --hash               SHA-256 für Dateien ≤ 50 MB
      --hash-all           SHA-256 für alle Dateien
  -v, --version            Version ausgeben und beenden

smartbackup restore  -s PATH [-t PATH] [-p GLOB]... [--conflict skip|overwrite|newer|rename] [--overwrite] [--dry-run] [--list] [--manifest-info] [--device-name TEXT]
smartbackup compress -t PATH [-f zip|tar.gz] [--device-name TEXT] [--remove-source]
smartbackup watch    [-i SECONDS] [-c SECONDS]
smartbackup schedule [--hours N]
smartbackup config   list | get KEY | set KEY VALUE | unset KEY | exclude PATTERN... | unexclude PATTERN...
smartbackup daemon   install | status | uninstall | clear-state
```

### B. Standard-Ausschlüsse

**Ordner-/Dateinamen** (exakter Abgleich, Groß-/Kleinschreibung ignoriert):

<details>
<summary><code>DEFAULT_EXCLUSIONS</code> (zum Aufklappen klicken)</summary>

- **Node.js / JavaScript:** `node_modules`, `.npm`, `.yarn`, `bower_components`, `.next`,
  `.nuxt`, `dist`, `build`, `.parcel-cache`
- **Python:** `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.tox`, `.nox`, `venv`,
  `.venv`, `env`, `.env`, `ENV`, `.eggs`, `.Python`, `pip-wheel-metadata`, `.pytype`
- **Python-Packaging/venvs:** `*.egg-info`, `virtualenv`, `.virtualenv`, `pipenv`,
  `.pipenv`, `conda-env`, `.conda`
- **JVM:** `target`, `.gradle`, `.m2`
- **.NET:** `bin`, `obj`, `packages`
- **Go:** `vendor`
- **IDE/Editor:** `.idea`, `.vscode`, `*.swp`, `*.swo`, `.project`, `.settings`, `.classpath`
- **Versionskontrolle:** `.git`, `.svn`, `.hg`
- **OS-Dateien:** `.DS_Store`, `Thumbs.db`, `desktop.ini`
- **Temporäre Dateien:** `*.tmp`, `*.temp`, `*.log`, `*.bak`, `~*`
- **Caches:** `.cache`, `cache`, `.sass-cache`
- **Docker:** `.docker`

</details>

**Ausgeschlossene Dateiendungen** (immer übersprungen):
`.pyc` `.pyo` `.pyd` `.class` `.o` `.obj` `.exe` `.dll` `.so` `.dylib` `.log` `.tmp` `.temp`

**Zusätzlich:** Jedes Verzeichnis, das strukturell wie eine virtuelle Python-Umgebung aussieht (§3.5, Stufe 4).

### C. Wichtige Dateipfade

| Was | Pfad |
|---|---|
| Konfiguration (Windows) | `%APPDATA%\SmartBackup\config.json` |
| Konfiguration (macOS/Linux) | `~/.config/smartbackup/config.json` |
| Watcher-Debounce-Status | `<config dir>/watcher_state.json` |
| Watcher-Daemon-Logs (macOS) | `~/.config/smartbackup/logs/watcher.log`, `watcher.err.log` |
| Backup-Manifest | `<target>/Documents-Backup/<Device>/.smartbackup_manifest.json` (oder `.db`) |
| Backup-Logs | `<target>/Documents-Backup/<Device>/_backup_logs/backup_YYYYMMDD_HHMMSS.log` |
| Archive | `<target>/Documents-Backup/<Device>_<YYYYMMDD_HHMMSS>.zip\|tar.gz` |
| Lokales Temp-Backup | `~/.local_backup_temp` |
| Windows-Watcher-Aufgabe | Geplante Aufgabe `SmartBackupWatcher` |
| macOS-Watcher-Agent | `~/Library/LaunchAgents/com.smartbackup.watcher.plist` |
| Linux-Watcher-Unit | `~/.config/systemd/user/smartbackup-watcher.service` |

### D. Weiterführende Dokumentation

- [`README.de.md`](README.de.md) — Überblick und Schnellstart (Deutsch)
- [`docs/CONTRIBUTING.md`](../CONTRIBUTING.md) — Entwicklungsumgebung, Tests, Linting (Englisch)
- [`docs/CHANGELOG.md`](../CHANGELOG.md) — Versionshistorie (Englisch)
