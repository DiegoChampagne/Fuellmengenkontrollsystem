#!/bin/bash
# Holt die neueste Version von GitHub und installiert bei Bedarf neue Pakete.
# Voraussetzung: Der Ordner wurde mit "git clone" angelegt und es gibt
# Internetzugang (WLAN ggf. vorher mit "nmcli radio wifi on" einschalten).
cd "$(dirname "$0")" || exit 1

if ! command -v git >/dev/null 2>&1; then
    echo "Git ist nicht installiert (z.B. sudo apt install git)."; exit 1
fi
if [ ! -d .git ]; then
    echo "Dieser Ordner ist kein Git-Klon - Update nicht moeglich."
    echo "Einmalig: git clone <Repository-URL> und config.json/Datenbank dorthin kopieren."
    exit 1
fi

vorher=$(git rev-parse HEAD)
req_vorher=$(sha256sum requirements.txt 2>/dev/null)

if ! git pull --ff-only; then
    echo
    echo "Update fehlgeschlagen. Moegliche Ursachen: kein Internet oder von Hand"
    echo "geaenderte Programmdateien (mit 'git status' pruefen)."
    exit 1
fi

if [ "$vorher" = "$(git rev-parse HEAD)" ]; then
    echo "Bereits auf dem neuesten Stand."
else
    echo "Aktualisiert auf Version: $(git log -1 --format='%h %s')"
    if [ "$req_vorher" != "$(sha256sum requirements.txt 2>/dev/null)" ]; then
        echo "Pakete haben sich geaendert - installiere..."
        if [ -d venv ]; then
            venv/bin/python -m pip install -r requirements.txt || exit 1
        else
            echo "Kein venv gefunden - bitte ./install_linux.sh ausfuehren."
        fi
    fi
fi
chmod +x start.sh install_linux.sh update.sh 2>/dev/null
echo "Fertig."
