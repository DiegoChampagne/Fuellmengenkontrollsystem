#!/bin/bash
# Richtet auf einem Linux-PC (z.B. Kubuntu/KDE) einen eingeschraenkten
# Schueler-Zugang fuer das Fuellmengenkontrollsystem ein:
#
#   * Programm (neueste Version von GitHub) nach /opt/fuellmengenkontrolle
#   * Benutzer "schueler": Anmeldung ohne Passwort, keine Administratorrechte,
#     kein Schreibzugriff auf Programm und Einstellungen, KEIN Internetzugang
#     (Netzsperre fuer genau dieses Konto per nftables, dauerhaft nach Neustart)
#   * Messdaten in /var/lib/fuellmengenkontrolle (Programmordner bleibt gesperrt)
#   * Programmstart im Anwendungsmenue und automatisch beim Anmelden
#
# Aufruf aus dem Lehrkraft-Konto (Administrator), im Ordner des Skripts:
#     sudo ./schueler_einrichten.sh
# Erneutes Ausfuehren ist ungefaehrlich und holt zugleich die neueste Version.
#
# Optionale Umgebungsvariablen (Beispiel: sudo SCHUELER_NAME=pruefling ./...):
#   SCHUELER_NAME   Benutzername des Schueler-Kontos (Standard: schueler)
#   ALT_ORDNER      alter Programmordner, aus dem config.json und die
#                   Datenbank uebernommen werden
#   REPO_URL, INSTALL_ORDNER, DATEN_ORDNER  (fuer Tests)

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/DiegoChampagne/Fuellmengenkontrollsystem.git}"
INSTALL="${INSTALL_ORDNER:-/opt/fuellmengenkontrolle}"
DATEN="${DATEN_ORDNER:-/var/lib/fuellmengenkontrolle}"
SCHUELER="${SCHUELER_NAME:-schueler}"
ADMIN="${SUDO_USER:-}"
ALT="${ALT_ORDNER:-}"

info()   { echo; echo "==> $*"; }
warnung(){ echo "WARNUNG: $*" >&2; }
fehler() { echo "FEHLER: $*" >&2; exit 1; }

# --- Voraussetzungen ---------------------------------------------------------
[ "$(id -u)" -eq 0 ] || fehler "Bitte mit sudo starten:  sudo ./schueler_einrichten.sh"
[ -n "$ADMIN" ] && [ "$ADMIN" != "root" ] \
    || fehler "Bitte aus dem Lehrkraft-Konto per 'sudo' starten (nicht direkt als root)."
[ "$SCHUELER" != "$ADMIN" ] || fehler "Das Schueler-Konto darf nicht das Lehrkraft-Konto sein."
ADMIN_GRUPPE="$(id -gn "$ADMIN")"

for b in git python3 nft useradd; do
    command -v "$b" >/dev/null 2>&1 \
        || fehler "'$b' fehlt. Unter Debian/Ubuntu:  sudo apt install git python3 python3-venv python3-pip nftables"
done
python3 -c "import venv, ensurepip" 2>/dev/null \
    || fehler "Python-Modul 'venv' fehlt.  Unter Debian/Ubuntu:  sudo apt install python3-venv"

# --- 1. Programm von GitHub ----------------------------------------------------
info "Programm von GitHub nach $INSTALL"
if [ -d "$INSTALL/.git" ]; then
    sudo -H -u "$ADMIN" git -C "$INSTALL" pull --ff-only
else
    if [ -e "$INSTALL" ] && [ -n "$(ls -A "$INSTALL" 2>/dev/null)" ]; then
        fehler "$INSTALL existiert bereits und ist kein Git-Ordner."
    fi
    mkdir -p "$INSTALL"
    chown "$ADMIN:$ADMIN_GRUPPE" "$INSTALL"
    sudo -H -u "$ADMIN" git clone "$REPO_URL" "$INSTALL"
fi

# Skripte ausfuehrbar machen, ohne dass Git das als Aenderung zaehlt
sudo -H -u "$ADMIN" git -C "$INSTALL" config core.fileMode false
chmod +x "$INSTALL"/*.sh

if [ -n "$ALT" ] && [ -f "$ALT/config.json" ] && [ ! -e "$INSTALL/config.json" ]; then
    info "Einstellungen aus $ALT uebernehmen"
    cp "$ALT/config.json" "$INSTALL/config.json"
    chown "$ADMIN:$ADMIN_GRUPPE" "$INSTALL/config.json"
fi

info "Python-Pakete installieren (Internetzugang noetig, dauert einige Minuten)"
sudo -H -u "$ADMIN" bash "$INSTALL/install_linux.sh"
sudo -H -u "$ADMIN" "$INSTALL/venv/bin/python" -m compileall -q "$INSTALL"/*.py

# --- 2. Datenordner ------------------------------------------------------------
info "Datenordner $DATEN"
install -d -m 1777 "$DATEN"
DB="$DATEN/fuellmengenkontrolle.db"
if [ -n "$ALT" ] && [ -f "$ALT/fuellmengenkontrolle.db" ] && [ ! -e "$DB" ]; then
    cp "$ALT/fuellmengenkontrolle.db" "$DB"
fi
# Datenbank (mit Tabellen) vorab anlegen und fuer beide Konten beschreibbar machen
sudo -H -u "$ADMIN" env FUELLMENGEN_DATEN="$DATEN" bash -c 'cd "$1" && exec venv/bin/python -' _ "$INSTALL" <<'PY'
import config, storage
with storage.get_connection(config.datenbank_pfad_aufloesen("fuellmengenkontrolle.db")):
    pass
PY
chmod 666 "$DB"

# --- 3. Programmordner schuetzen ------------------------------------------------
info "Programmordner schreibgeschuetzt (Eigentuemer: $ADMIN)"
chown -R "$ADMIN:$ADMIN_GRUPPE" "$INSTALL"
chmod -R go-w,o+rX "$INSTALL"

# --- 4. Schueler-Konto ------------------------------------------------------------
info "Schueler-Konto '$SCHUELER'"
if id "$SCHUELER" >/dev/null 2>&1; then
    echo "Benutzer existiert bereits - wird angepasst."
else
    useradd -m -s /bin/bash -c "Schueler (ohne Passwort)" "$SCHUELER"
fi
passwd -d "$SCHUELER" >/dev/null
for g in sudo wheel admin adm lpadmin; do
    gpasswd -d "$SCHUELER" "$g" >/dev/null 2>&1 || true
done
# Zugriff auf Waage (serielle Schnittstelle) und Drucker
for g in dialout uucp lp; do
    if getent group "$g" >/dev/null; then
        usermod -aG "$g" "$SCHUELER"
        usermod -aG "$g" "$ADMIN"
    fi
done
if ! grep -rqs nullok /etc/pam.d/; then
    warnung "In /etc/pam.d wurde kein 'nullok' gefunden - die Anmeldung ohne Passwort"
    warnung "wird moeglicherweise abgelehnt (SDDM-Anmeldung testen)."
fi

# --- 5. Internetsperre nur fuer das Schueler-Konto --------------------------------
info "Netzsperre fuer '$SCHUELER'"
SCHUELER_UID="$(id -u "$SCHUELER")"
NFT="$(command -v nft)"
cat > /etc/nftables-schueler.conf <<EOF
# Erzeugt von schueler_einrichten.sh - sperrt jeden Netzverkehr (ausser
# Loopback) fuer das Schueler-Konto. Betrifft keine anderen Benutzer.
table inet schueler_sperre
delete table inet schueler_sperre
table inet schueler_sperre {
	chain output {
		type filter hook output priority 0; policy accept;
		oifname "lo" accept
		meta skuid $SCHUELER_UID reject
	}
}
EOF
if [ -d /run/systemd/system ]; then
    cat > /etc/systemd/system/schueler-netzsperre.service <<EOF
[Unit]
Description=Netzsperre fuer das Schueler-Konto (Fuellmengenkontrolle)
After=network-pre.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=$NFT -f /etc/nftables-schueler.conf
ExecStop=$NFT delete table inet schueler_sperre

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable schueler-netzsperre.service >/dev/null 2>&1
    systemctl restart schueler-netzsperre.service
else
    "$NFT" -f /etc/nftables-schueler.conf
    warnung "systemd laeuft nicht - die Sperre gilt nur bis zum Neustart."
fi

# Funktionstest: Administrator darf ins Netz, Schueler nicht
verbinde() { timeout 4 bash -c 'exec 3<>/dev/tcp/1.1.1.1/443' >/dev/null 2>&1; }
if verbinde; then
    if runuser -u "$SCHUELER" -- bash -c 'timeout 4 bash -c "exec 3<>/dev/tcp/1.1.1.1/443"' >/dev/null 2>&1; then
        warnung "Das Schueler-Konto hat noch Netzzugang - Sperre pruefen: sudo nft list ruleset"
    else
        echo "Test bestanden: '$SCHUELER' kommt nicht ins Internet, andere Konten schon."
    fi
else
    echo "Test nicht aussagekraeftig (dieser PC hat gerade selbst kein Internet)."
fi

# --- 6. Starter und Konto-Einstellungen --------------------------------------------
info "Starter und Anmelde-Verhalten"
STARTER="[Desktop Entry]
Type=Application
Name=Füllmengenkontrolle
Comment=Gleichförmigkeit der Masse einzeldosierter Arzneiformen
Exec=env FUELLMENGEN_DATEN=$DATEN $INSTALL/start.sh
Path=$INSTALL
Terminal=false
Categories=Education;Science;"
printf '%s\n' "$STARTER" > /usr/share/applications/fuellmengenkontrolle.desktop

HOME_S="$(getent passwd "$SCHUELER" | cut -d: -f6)"
SCHUELER_GRUPPE="$(id -gn "$SCHUELER")"
install -d -o "$SCHUELER" -g "$SCHUELER_GRUPPE" "$HOME_S/.config" "$HOME_S/.config/autostart"
printf '%s\n' "$STARTER" > "$HOME_S/.config/autostart/fuellmengenkontrolle.desktop"
# Kein Bildschirmsperre-Dialog (sonst muesste man nach Pausen erneut anmelden)
printf '[Daemon]\nAutolock=false\nLockOnResume=false\n' > "$HOME_S/.config/kscreenlockerrc"
chown "$SCHUELER:$SCHUELER_GRUPPE" "$HOME_S/.config/autostart/fuellmengenkontrolle.desktop" \
    "$HOME_S/.config/kscreenlockerrc"

# --- 7. Abschlusstest als Schueler ---------------------------------------------------
info "Test: Programm im Schueler-Konto ladbar?"
if runuser -u "$SCHUELER" -- env FUELLMENGEN_DATEN="$DATEN" QT_QPA_PLATFORM=offscreen \
        bash -c 'cd "$1" && venv/bin/python -c "import gui; print(\"OK - Programm laesst sich laden\")"' _ "$INSTALL"; then
    :
else
    warnung "Das Programm liess sich im Schueler-Konto nicht laden (siehe Meldung oben)."
fi

cat <<EOF

========================================================================
Fertig. Naechste Schritte (im Lehrkraft-Konto '$ADMIN'):

 1. Programm starten (Anwendungsmenue: "Füllmengenkontrolle"),
    "Einstellungen" oeffnen und EIN LEHRKRAFT-PASSWORT FESTLEGEN.
    Danach: Testmodus AUS, Waagen-Modus 'seriell'. Gespeichert wird in
    $INSTALL/config.json - nur dieses Konto darf dort schreiben.
    (Ohne Passwort koennte das Schueler-Konto Einstellungen nur fluechtig
    aendern; speichern kann es sie nicht.)
 2. USB-Geraete einrichten (feste Namen /dev/waage, /dev/bondrucker):
    sudo $INSTALL/usb_regeln_einrichten.sh
 3. Beim Anmelden im Anmeldebildschirm das Konto '$SCHUELER' waehlen und
    das Passwortfeld leer lassen (Enter).
 4. Updates spaeter: cd $INSTALL && ./update.sh
    (oder dieses Skript erneut ausfuehren).
========================================================================
EOF
