# jupyther-labsman
Jupyter Lab management tool

## Dateien suchen und entpacken

Der Workspace-Prompt [Dateien suchen und entpacken](.github/prompts/dateien-suchen-und-entpacken.prompt.md) findet passende Dateien und Archive im Workspace. Starte ihn im Copilot-Chat mit `/Dateien suchen und entpacken` und gib Suchkriterien sowie bei Bedarf einen Zielordner an.

Beispiel: `/Dateien suchen und entpacken ZIP-Archive im Workspace, Zielordner: extracted/`

Wird kein Zielordner angegeben, fragt der Prompt vor dem Entpacken danach. Vorhandene Dateien werden nicht überschrieben; Archive mit Einträgen außerhalb des Zielordners werden übersprungen.

## Python-CLI

Installiere das Kommando im Workspace:

```bash
python -m pip install .
```

Die Vorschau sucht im aktuellen Verzeichnis nach passenden Dateipfaden und zeigt gefundene ZIP- und TAR-Archive samt Inhalt an:

```bash
find-and-extract daten --root .
```

Mit `--content` werden zusätzlich lesbare UTF-8-Textdateien nach dem Suchbegriff durchsucht. Zum Entpacken gib `--extract` und einen Zielordner an; pro Archiv wird darin ein neuer Unterordner angelegt:

```bash
find-and-extract daten --root . --extract --destination extracted/
```

Das Tool verwendet nur die Python-Standardbibliothek. Es überschreibt keine bestehenden Dateien und überspringt Archive mit unsicheren Pfaden oder nicht unterstützten Eintragstypen.

## JupyterLab Desktop-App

Die Tkinter-App kann unter Linux und Windows gestartet werden. Installiere das Paket zusammen mit JupyterLab:

```bash
python -m pip install '.[desktop]'
jupyter-lab-manager
```

Die App startet JupyterLab mit demselben Python-Interpreter, zeigt die Serverausgabe an und öffnet die URL samt Anmeldetoken im Browser. Unter Linux muss Tkinter verfügbar sein; bei Debian/Ubuntu installiere es bei Bedarf mit `sudo apt install python3-tk`. Wine wird für die native Windows-Version nicht benötigt.
