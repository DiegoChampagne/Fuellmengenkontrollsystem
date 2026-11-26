# Füllmengenkontrolle

Plattformunabhängiges Programm (Windows/Linux) zur **Gleichförmigkeit der
Masse einzeldosierter Arzneiformen** (Kapseln, Zäpfchen, Tabletten,
Pulverbriefchen) für den Unterricht. Es liest die Einzelwägungen direkt von
einer Waage, wertet sie statistisch aus, zeigt eine grafische Vorschau und
druckt einen Bon auf einem Thermodrucker. Entstanden als Ersatz für ein
defektes System an einer PTA-Schule.

> **Wichtiger Hinweis:** Dies ist ein **Lehrmittel**, kein validiertes
> Prüfmittel und kein Qualitätssicherungssystem nach GMP. Die Auswertungen
> sind eine Umsetzung nach bestem Wissen, **ohne Gewähr**. Für amtliche oder
> betriebliche Prüfungen gilt allein der Wortlaut des Europäischen
> Arzneibuchs (Ph. Eur.) in der aktuellen Ausgabe.

## Funktionen

- **Automatische Erfassung:** Kapsel auflegen, Waage sendet den stabilen Wert
  – kein Klick im Programm nötig. Getestet mit der Sartorius Entris® BCE
  (SBI-Protokoll über USB-Seriell).
- **Additive Wägung mit softwareseitiger Tarierung:** Die Einheiten bleiben
  nacheinander auf der Waage liegen, das Programm bildet die Differenzen.
  Plausibilitätsprüfung gegen doppelt gesendete Werte, gegen Wegnehmen und
  gegen Ausreißer.
- **Zwei Auswertungsmethoden:**
  - *Massenabweichung* nach Ph. Eur. 2.9.5 (Grenzen T1/T2 um den
    Stichproben-Mittelwert, T1 automatisch nach Tabelle 2.9.5-1 je
    Darreichungsform und Masse, T2 = 2 × T1)
  - *Akzeptanzwert* nach Ph. Eur. 2.9.40 (n = 10 / n = 30; andere
    Stichprobenumfänge werden als „nicht amtlich" gekennzeichnet)
- **Grafische Vorschau** während der Messung und ein Diagramm bei der
  Auswertung (abschaltbar in den Einstellungen).
- **Bondruck** über ESC/POS (Epson TM-T20IV getestet), Windows, Linux/CUPS,
  direkte USB-Gerätedatei oder Netzwerk; reiner Textdruck auf normalen
  Druckern zum Testen.
- **Speicherung** jeder Auswertung in einer SQLite-Datenbank.
- Vollbildbetrieb (F11/Esc), Passwortschutz der Einstellungen, Testmodus mit
  manueller Werteingabe (nur zur Entwicklung/Demonstration).

## Installation

Voraussetzung: **Python 3.11 – 3.13** (PySide6 unterstützt ganz neue
Versionen oft noch nicht).

### Windows

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Danach starten per Doppelklick auf `start.bat`.

### Linux

```bash
chmod +x install_linux.sh start.sh
./install_linux.sh
./start.sh
```

`start.sh` setzt `QT_QPA_PLATFORM=wayland;xcb` (natives Wayland, sonst X11).
Autostart und Schreibtisch-Verknüpfung: `Fuellmengenkontrolle.desktop` nach
`~/.config/autostart/` bzw. auf den Schreibtisch kopieren (Pfad anpassen).

**Waage:** USB-Waagen melden sich meist als `/dev/ttyACM0` oder
`/dev/ttyUSB0`. Der Benutzer muss in die Gruppe `dialout` (Arch/Manjaro:
`uucp`): `sudo usermod -aG dialout $USER`, danach neu anmelden.
Blockiert der ModemManager den Port: `sudo systemctl stop ModemManager`.

**Drucker:** Am robustesten ist das Backend `file` mit der Gerätedatei des
USB-Druckers (z. B. `/dev/usb/lp3`, siehe `ls -l /dev/usb/`; Benutzer in die
Gruppe `lp`). Alternativ `cups` (Warteschlangenname aus `lpstat -p`, Raw-
Queue) oder `network` (IP, Port 9100). Die Nummer der Gerätedatei kann sich
ändern; ein fester Name lässt sich mit einer udev-Regel vergeben.

## Schüler-Konto einrichten (Linux/KDE)

Für den Einsatz mit Schüler:innen (auch bei Leistungsnachweisen) richtet ein
Skript ein eingeschränktes Konto ein. Aus dem Lehrkraft-Konto (Administrator):

```bash
git clone https://github.com/DiegoChampagne/Fuellmengenkontrollsystem.git
cd Fuellmengenkontrollsystem
sudo bash schueler_einrichten.sh
```

Das Skript installiert die neueste Version nach `/opt/fuellmengenkontrolle`
und legt das Konto `schueler` an:

- Anmeldung **ohne Passwort** (Konto wählen, Eingabetaste),
- **keine Administratorrechte**, kein Schreibzugriff auf Programm und
  Einstellungen (`config.json` darf nur das Lehrkraft-Konto ändern),
- **kein Netzzugang** nur für dieses Konto (nftables-Regel, bleibt nach einem
  Neustart bestehen; andere Konten sind nicht betroffen),
- Messdaten landen in `/var/lib/fuellmengenkontrolle` (über die Umgebungs-
  variable `FUELLMENGEN_DATEN` einstellbar),
- Programmstart im Anwendungsmenü und automatisch bei der Anmeldung.

Danach im Lehrkraft-Konto das Programm öffnen, die Einstellungen aufrufen und
ein **Passwort festlegen**, den Testmodus ausschalten und die Waage auf
`seriell` stellen. Das Skript kann jederzeit erneut ausgeführt werden und
holt dabei die neueste Version; Updates gehen auch mit `./update.sh` im
Ordner `/opt/fuellmengenkontrolle`. Einstellungen und Messdaten eines alten
Ordners übernimmt `sudo ALT_ORDNER=/pfad/zum/alten/ordner bash schueler_einrichten.sh`.

### Feste USB-Namen für Waage und Drucker

Damit sich die Einstellungen nicht ändern, wenn ein Gerät in eine andere
Buchse gesteckt wird, vergibt `usb_regeln_einrichten.sh` feste Namen
(`/dev/waage`, `/dev/bondrucker`) anhand der USB-Kennung der Geräte:

```bash
sudo bash usb_regeln_einrichten.sh
```

Waage und Drucker vorher anschließen und einschalten, dann die Nummern der
Geräte aus der Liste wählen (Enter überspringt ein Gerät). In den
Einstellungen trägt man danach `/dev/waage` als Port sowie das Backend `file`
mit der Gerätedatei `/dev/bondrucker` ein.

## Erste Schritte

1. Programm starten, **Einstellungen** öffnen. Beim ersten Mal wird ein
   Passwort festgelegt (gespeichert wird nur ein Hash in `config.json`).
2. Waagen-Modus `seriell` und Port eintragen, Drucker-Backend wählen,
   **Testmodus ausschalten** (sonst können Werte frei eingegeben werden).
3. Im Hauptfenster Darreichungsform, Nennfüllmenge und Stichprobenumfang
   wählen, **Start** drücken, wiegen. Bei Erreichen des Stichprobenumfangs
   wird automatisch ausgewertet und gedruckt; „Ende“ beendet früher.

Alle Einstellungen liegen in `config.json` (wird beim ersten Speichern
angelegt und ist von Git ausgeschlossen).

## Aktualisieren

Ist der Ordner mit `git clone` angelegt, holt `update.sh` (Linux) bzw.
`update.bat` (Windows, Doppelklick) die neueste Version von GitHub und
installiert bei geänderter `requirements.txt` die Pakete nach. `config.json`
und die Datenbank bleiben unberührt. Der Rechner braucht dafür kurz
Internetzugang. Von Hand geänderte Programmdateien verhindern das Update
(`git status` zeigt sie an).

## Waage einrichten (Sartorius Entris® BCE)

Im Menü der Waage:

- `DEVICE` = `USB`, `DAT.REC.` = `SBI`, `BAUD` = `9600`, `DATABIT` = `8 BITS`,
  `HANDSHK.` = `NONE`
- `DATA.OUT.` → `COM. SBI` → `COM.OUTP.` = `AUTO.W/` (automatische Ausgabe
  nach Stillstand) oder `IND.AFTR` (Ausgabe per **[Print]**)
- `AUTO.TAR.` und `TAR./PRT.` bleiben `OFF` – die Tarierung übernimmt das
  Programm.

Das Programm erkennt jede Zeile mit „Zahl + g“ (Regex in `balance.py`).
Andere Waagen mit seriellem Ausgang lassen sich so oft ohne Änderung
anbinden, ansonsten den Regex anpassen.

## Auswertung

### Massenabweichung (Ph. Eur. 2.9.5)

Grenzen T1 und T2 um den **Mittelwert der Stichprobe**; T1 nach Tabelle
2.9.5-1 (Tabletten 10 / 7,5 / 5 %, Kapseln und Pulver 10 bzw. 7,5 %,
Zäpfchen 5 %), T2 = 2 × T1. Die Nennfüllmenge dient als Näherung der
Durchschnittsmasse. Berechnung geprüft gegen den Ausdruck des Originalgeräts
(`calculations.py`).

### Akzeptanzwert (Ph. Eur. 2.9.40)

Bewertet die Einzelwerte relativ zur **Nennfüllmenge** (`x_i = Netto / Nenn
× 100 %`). Mit Mittelwert x̄ und Standardabweichung s:

```
98,5 % ≤ x̄ ≤ 101,5 %:  M = x̄          AV = k·s
x̄ < 98,5 %:            M = 98,5 %      AV = (98,5 − x̄) + k·s
x̄ > 101,5 %:           M = 101,5 %     AV = (x̄ − 101,5) + k·s
```

Stufe 1 (n = 10, k = 2,4): bestanden bei AV ≤ L1 (15,0). Stufe 2 (n = 30,
k = 2,0): AV ≤ L1 und kein Einzelwert außerhalb von M·(1 ± 0,01·L2),
L2 = 25,0. Siehe `acceptance_value.py`.

## Kapselgrößen

Voreingestellt sind Nennfüllmengen und Leergewichte für die Größen 000–4.
**Die Leergewichte sind grobe Herstellerrichtwerte** (000 und 00 sogar nur
Schätzungen) und schwanken je nach Hersteller, Charge und Material. Bitte
etwa 20 Leerkapseln der verwendeten Charge wiegen und den Mittelwert in den
Einstellungen eintragen. Für Pulverbriefchen gibt es keinen Standardwert
(0 g) – ebenfalls selbst messen.

## Projektstruktur

```
main.py              Programmstart
gui.py               Oberfläche (PySide6)
balance.py           Waagenanbindung (seriell / manuell)
calculations.py      Massenabweichung (2.9.5)
acceptance_value.py  Akzeptanzwert (2.9.40)
receipt.py           Bon-Text
chart.py             Diagramme und Live-Vorschau (matplotlib)
printer.py           Druck-Backends (win32raw, windows_text, cups, file, network)
storage.py           SQLite-Speicherung, CSV-Export
config.py            Einstellungen, Tabellen, Passwort-Hash
update.sh/.bat       Update von GitHub (git pull + Pakete)
schueler_einrichten.sh   Schüler-Konto ohne Passwort, ohne Internet (Linux)
usb_regeln_einrichten.sh Feste USB-Namen für Waage und Drucker (Linux)
```

## Datenschutz und Sicherheit

`config.json` (Einstellungen, Passwort-Hash) und die Datenbank
(`*.db`, enthält Probenbezeichnungen und Messwerte) liegen lokal und sind
per `.gitignore` von Git ausgeschlossen – bitte nicht einchecken. Der
Passwortschutz hält Schüler:innen vom Einstellungsdialog fern, ist aber
keine Sicherheitsfunktion gegen Personen mit Dateizugriff auf den Rechner.

## Lizenz

[MIT](LICENSE). Verwendete Bibliotheken (PySide6, matplotlib, pyserial,
python-escpos) stehen unter eigenen freien Lizenzen und werden per `pip`
installiert, nicht mitgeliefert. Hersteller- und Produktnamen (Sartorius,
Mettler-Toledo, Epson) dienen nur der Kompatibilitätsangabe und sind Marken
ihrer jeweiligen Inhaber. Dieses Projekt steht in keiner Verbindung zu
diesen Firmen.
