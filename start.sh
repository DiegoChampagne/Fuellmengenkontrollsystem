#!/bin/bash
cd "$(dirname "$0")"
if [ -d venv ]; then
    source venv/bin/activate
else
    echo "Noch nicht eingerichtet - bitte zuerst ./install_linux.sh ausfuehren."
    exit 1
fi
# KDE Plasma unter Wayland: natives Wayland, bei Problemen automatisch X11 (XWayland)
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-wayland;xcb}"
exec python main.py
