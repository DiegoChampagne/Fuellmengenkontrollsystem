#!/bin/bash
# Einmalige Einrichtung unter Linux: legt die virtuelle Umgebung an und
# installiert alle Pakete. Danach mit ./start.sh starten.
set -e
cd "$(dirname "$0")"

# PySide6 unterstützt nicht jede ganz neue Python-Version - bevorzugt 3.12/3.13/3.11.
PY=""
for kandidat in python3.12 python3.13 python3.11 python3; do
    if command -v "$kandidat" >/dev/null 2>&1; then PY="$kandidat"; break; fi
done
if [ -z "$PY" ]; then
    echo "Python 3 wurde nicht gefunden. Bitte python3 und python3-venv installieren."
    exit 1
fi
echo "Verwende $($PY --version)"

$PY -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Zugriff auf die serielle Schnittstelle der Waage (einmalig, danach neu einloggen)
if ! id -nG "$USER" | grep -qw dialout; then
    echo
    echo "Hinweis: Fuer die Waage muss $USER in der Gruppe 'dialout' sein:"
    echo "    sudo usermod -aG dialout $USER"
    echo "Danach einmal ab- und wieder anmelden."
fi

chmod +x start.sh
echo
echo "Fertig. Starten mit: ./start.sh"
