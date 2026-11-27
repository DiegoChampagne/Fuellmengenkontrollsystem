#!/bin/bash
# Legt feste Geraetenamen fuer Waage und Bondrucker an, damit sich die
# Einstellungen im Programm nicht aendern, wenn ein Geraet in eine andere
# USB-Buchse gesteckt oder neu angeschlossen wird:
#
#     /dev/waage        (Sartorius-Waage, serielle USB-Schnittstelle)
#     /dev/bondrucker   (USB-Thermodrucker)
#
# Die Geraete werden an ihrer USB-Kennung (Hersteller-/Produkt-ID) erkannt,
# nicht an der Buchse. Gilt also an jedem Anschluss und fuer jeden Neustart.
# (Zwei baugleiche Geraete gleichzeitig lassen sich so nicht unterscheiden.)
#
# Aufruf: Waage und Drucker anschliessen, einschalten, dann
#     sudo ./usb_regeln_einrichten.sh
# Kann jederzeit wiederholt werden, z.B. nach Austausch eines Geraets.
# Ein uebersprungenes Geraet behaelt seine bisherige Regel.
#
# Zum Testen ueberschreibbar: REGELDATEI, UDEVADM, GERAETE_MUSTER,
# NUR_REGELDATEI=1 (nur Regeldatei schreiben, nichts am System aendern).

set -uo pipefail

REGELDATEI="${REGELDATEI:-/etc/udev/rules.d/99-fuellmengenkontrolle.rules}"
UDEVADM="${UDEVADM:-udevadm}"
GERAETE_MUSTER="${GERAETE_MUSTER:-/dev/ttyACM* /dev/ttyUSB* /dev/usb/lp*}"
NUR_REGELDATEI="${NUR_REGELDATEI:-0}"
SCHUELER="${SCHUELER_NAME:-schueler}"

fehler() { echo "FEHLER: $*" >&2; exit 1; }

if [ "$NUR_REGELDATEI" != "1" ]; then
    [ "$(id -u)" -eq 0 ] || fehler "Bitte mit sudo starten:  sudo ./usb_regeln_einrichten.sh"
    command -v "$UDEVADM" >/dev/null 2>&1 || fehler "'udevadm' nicht gefunden."
fi

eigenschaft() {  # $1 = Geraetedatei, $2 = Schluessel
    "$UDEVADM" info -q property -n "$1" 2>/dev/null | sed -n "s/^$2=//p" | head -n 1
}

attribut() {  # $1 = Geraetedatei, $2 = USB-Attribut (Ersatz, falls udev keine ID_*-Werte liefert)
    "$UDEVADM" info -a -n "$1" 2>/dev/null \
        | sed -n "s/^[[:space:]]*ATTRS{$2}==\"\(.*\)\"/\1/p" | head -n 1
}

# Treiber fuer USB-Drucker (erzeugt /dev/usb/lp*) laden, falls noch nicht geschehen
if [ "$NUR_REGELDATEI" != "1" ]; then
    modprobe usblp 2>/dev/null || true
    sleep 1
fi

# Gruppe der seriellen Schnittstellen unterscheidet sich je nach Distribution
if getent group dialout >/dev/null 2>&1; then GRUPPE_SERIELL=dialout; else GRUPPE_SERIELL=uucp; fi
GRUPPE_DRUCKER=lp

# --- Geraete suchen ------------------------------------------------------------
NODES=(); VIDS=(); PIDS=(); NAMEN=()
for n in $GERAETE_MUSTER; do
    [ -e "$n" ] || continue
    vid="$(eigenschaft "$n" ID_VENDOR_ID)"
    pid="$(eigenschaft "$n" ID_MODEL_ID)"
    [ -n "$vid" ] || vid="$(attribut "$n" idVendor)"
    [ -n "$pid" ] || pid="$(attribut "$n" idProduct)"
    [ -n "$vid" ] && [ -n "$pid" ] || continue
    name="$(eigenschaft "$n" ID_MODEL_FROM_DATABASE)"
    [ -n "$name" ] || name="$(eigenschaft "$n" ID_MODEL)"
    [ -n "$name" ] || name="$(attribut "$n" product)"
    hersteller="$(eigenschaft "$n" ID_VENDOR_FROM_DATABASE)"
    [ -n "$hersteller" ] || hersteller="$(eigenschaft "$n" ID_VENDOR)"
    [ -n "$hersteller" ] || hersteller="$(attribut "$n" manufacturer)"
    NODES+=("$n"); VIDS+=("$vid"); PIDS+=("$pid"); NAMEN+=("$hersteller $name")
done

if [ "${#NODES[@]}" -eq 0 ]; then
    echo "Keine passenden USB-Geraete gefunden."
    echo "Waage und Drucker anschliessen, einschalten und das Skript erneut starten."
    echo "(Falls der Drucker fehlt:  sudo modprobe usblp  - dann nochmal.)"
    exit 1
fi

# Hinweis, wenn kein Drucker (/dev/usb/lp*) dabei ist
HAT_DRUCKER=0
for n in "${NODES[@]}"; do case "$n" in */lp[0-9]*) HAT_DRUCKER=1;; esac; done
if [ "$HAT_DRUCKER" -eq 0 ]; then
    echo "Hinweis: Es wurde KEIN Drucker unter /dev/usb/ gefunden. Moegliche Ursachen:"
    echo "  - Drucker aus oder nicht per USB verbunden (Kabel, direkter Anschluss ohne Hub testen)"
    echo "  - Drucker erscheint nicht in 'lsusb' -> Hardware/Kabel pruefen"
    echo "  - Treiber 'usblp' nicht geladen oder gesperrt: lsmod | grep usblp ; dmesg | tail"
    echo "  Danach dieses Skript erneut starten (die Waagen-Regel bleibt erhalten)."
    echo
fi

echo "Gefundene Geraete:"
for i in "${!NODES[@]}"; do
    printf '  %d) %-16s %s:%s  %s\n' "$((i+1))" "${NODES[$i]}" "${VIDS[$i]}" "${PIDS[$i]}" "${NAMEN[$i]}"
done
echo

waehle() {  # $1 = Bezeichnung -> Index oder -1 (ueberspringen)
    local eingabe
    while true; do
        read -r -p "Nummer der $1 (Enter = ueberspringen): " eingabe
        if [ -z "$eingabe" ]; then printf '%s\n' -1; return; fi
        if [[ "$eingabe" =~ ^[0-9]+$ ]] && [ "$eingabe" -ge 1 ] && [ "$eingabe" -le "${#NODES[@]}" ]; then
            echo "$((eingabe-1))"; return
        fi
        echo "Bitte eine Zahl zwischen 1 und ${#NODES[@]} eingeben." >&2
    done
}

W="$(waehle WAAGE)"
D="$(waehle DRUCKER)"
if [ "$W" -ge 0 ] && [ "$W" = "$D" ]; then fehler "Waage und Drucker duerfen nicht dasselbe Geraet sein."; fi

# --- Regeln zusammenstellen (uebersprungene behalten ihre alte Regel) -----------------
alte_regel() {  # $1 = Symlink-Name
    [ -f "$REGELDATEI" ] && grep -F "SYMLINK+=\"$1\"" "$REGELDATEI" || true
}

if [ "$W" -ge 0 ]; then
    REGEL_WAAGE="SUBSYSTEM==\"tty\", ATTRS{idVendor}==\"${VIDS[$W]}\", ATTRS{idProduct}==\"${PIDS[$W]}\", SYMLINK+=\"waage\", GROUP=\"$GRUPPE_SERIELL\", MODE=\"0660\", TAG+=\"uaccess\""
else
    REGEL_WAAGE="$(alte_regel waage)"
fi
if [ "$D" -ge 0 ]; then
    REGEL_DRUCKER="SUBSYSTEM==\"usbmisc\", KERNEL==\"lp*\", ATTRS{idVendor}==\"${VIDS[$D]}\", ATTRS{idProduct}==\"${PIDS[$D]}\", SYMLINK+=\"bondrucker\", GROUP=\"$GRUPPE_DRUCKER\", MODE=\"0660\", TAG+=\"uaccess\""
else
    REGEL_DRUCKER="$(alte_regel bondrucker)"
fi

if [ -z "$REGEL_WAAGE" ] && [ -z "$REGEL_DRUCKER" ]; then
    echo "Nichts ausgewaehlt - keine Aenderung."; exit 0
fi

TMP="$(mktemp)"
{
    echo "# Erzeugt von usb_regeln_einrichten.sh - feste Namen fuer Waage und Bondrucker"
    [ -n "$REGEL_WAAGE" ] && echo "$REGEL_WAAGE"
    [ -n "$REGEL_DRUCKER" ] && echo "$REGEL_DRUCKER"
} > "$TMP"
install -m 644 "$TMP" "$REGELDATEI"
rm -f "$TMP"
echo "Regeln geschrieben nach $REGELDATEI:"
sed 's/^/    /' "$REGELDATEI"

[ "$NUR_REGELDATEI" = "1" ] && exit 0

# --- Aktivieren ------------------------------------------------------------------------
# Treiber fuer USB-Drucker (erzeugt /dev/usb/lp*) bei jedem Start laden
modprobe usblp 2>/dev/null || true
echo usblp > /etc/modules-load.d/usblp.conf

# Zugriff: Lehrkraft-Konto und Schueler-Konto in die Geraetegruppen
for u in "${SUDO_USER:-}" "$SCHUELER"; do
    [ -n "$u" ] && id "$u" >/dev/null 2>&1 || continue
    usermod -aG "$GRUPPE_SERIELL" "$u"
    usermod -aG "$GRUPPE_DRUCKER" "$u"
done

"$UDEVADM" control --reload
"$UDEVADM" trigger --action=change --subsystem-match=tty --subsystem-match=usbmisc
"$UDEVADM" settle 2>/dev/null || sleep 2

echo
echo "Ergebnis:"
ls -l /dev/waage /dev/bondrucker 2>&1 | sed 's/^/    /'
cat <<EOF

In den Programm-Einstellungen eintragen:
    Waage Port ........... /dev/waage
    Drucker-Backend ...... file
    Geraetedatei ......... /dev/bondrucker

Hinweis: Gruppenrechte gelten erst nach erneuter Anmeldung (ab-/anmelden).
EOF
