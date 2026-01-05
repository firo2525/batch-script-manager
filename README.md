# Batch Script Manager

Ein leistungsstarker, Python-basierter Manager mit grafischer Benutzeroberfläche (GUI) zur Verwaltung, Überwachung und Automatisierung von Windows-Batch-Skripten.

## Features

- **Zentralisierte Steuerung**: Starten, Stoppen und Neustarten mehrerer Batch-Skripte über eine einzige Oberfläche.
- **Echtzeit-Monitoring**: Live-Anzeige der Konsolenausgaben (Logs) für jedes Skript in eigenen Tabs.
- **Autostart-System**: Automatisches Starten von Skripten beim Programmstart mit konfigurierbarer Verzögerung (`global_start_delay_seconds`).
- **Ressourcen-Überwachung**: Anzeige von Prozess-IDs (PID) und CPU-Auslastung (erfordert `psutil`).
- **Benachrichtigungen**: Desktop-Benachrichtigungen bei Statusänderungen (erfordert `plyer`).
- **Silent Mode**: Möglichkeit, den Manager im Hintergrund ohne Konsolenfenster zu starten.
- **Log-Management**: Automatische Protokollierung der Manager-Aktivitäten.

## Installation

1. **Python installieren**: Stellen Sie sicher, dass Python 3.x auf Ihrem System installiert ist.
2. **Abhängigkeiten installieren (optional, aber empfohlen)**:
   Öffnen Sie ein Terminal im Projektordner und führen Sie aus:
   ```bash
   pip install psutil plyer
   ```

## Konfiguration

Die Konfiguration erfolgt über die Datei [config.json](config.json). Hier können Sie Ihre Skripte definieren:

```json
{
    "scripts": {
        "Mein Skript": {
            "path": "C:\\Pfad\\zu\\deinem\\skript.bat",
            "autostart": true
        }
    },
    "global_start_delay_seconds": 5,
    "autostart_enabled": true
}
```

- `path`: Absoluter Pfad zur `.bat` Datei.
- `autostart`: Ob dieses spezifische Skript automatisch starten soll.
- `global_start_delay_seconds`: Zeit in Sekunden zwischen den automatischen Starts der Skripte.
- `autostart_enabled`: Globaler Schalter für die Autostart-Funktion.

## Starten des Programms

Es gibt drei Möglichkeiten, den Manager zu starten:

1. **Normaler Start**: Doppelklick auf [start_manager.bat](start_manager.bat).
2. **Silent Start (Hintergrund)**: Doppelklick auf [start_silent.vbs](start_silent.vbs). Dies startet das Programm ohne sichtbares Konsolenfenster.
3. **Über die Kommandozeile**:
   ```bash
   python batch_manager.py
   ```

## Projektstruktur

- [batch_manager.py](batch_manager.py): Die Hauptanwendung (Python/Tkinter).
- [config.json](config.json): Konfigurationsdatei für die zu verwaltenden Skripte.
- [start_manager.bat](start_manager.bat): Batch-Datei zum einfachen Starten.
- [start_silent.vbs](start_silent.vbs): VBScript für den lautlosen Start im Hintergrund.

## Lizenz

Dieses Projekt ist unter der MIT-Lizenz lizenziert.
