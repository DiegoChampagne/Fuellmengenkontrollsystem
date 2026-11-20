"""
Druckausgabe auf einem Bonrollendrucker - oder testweise auf einem ganz
normalen (nicht ESC/POS-fähigen) Drucker über die Windows-Textdruck-Pipeline.

Der Bon-Text wird zunächst einmalig über python-escpos' "Dummy"-Drucker in
eine reine ESC/POS-Byte-Sequenz umgewandelt (Text + Papierschnitt). Diese
Bytes werden danach je nach Backend unterschiedlich an den Drucker
geschickt - das ist der einzige Teil, der sich zwischen Windows und Linux
unterscheidet:

  - "win32raw"    (Windows, ESC/POS-Drucker): über die Windows-Druckerwarte-
                   schlange (Treiber), als rohe ESC/POS-Bytes.
  - "windows_text" (Windows, JEDER normal installierte Drucker - Laser,
                   Tintenstrahl, Netzwerkdrucker): schickt den Bon-Text als
                   reinen Text-Druckauftrag (Datentyp "TEXT"), den der
                   Windows-Druckspooler selbst in eine druckbare Seite
                   umwandelt - unabhängig vom Druckertreiber/-hersteller.
                   ESC/POS-Steuerzeichen (Fettdruck, Papierschnitt) werden
                   dabei NICHT verstanden, es wird reiner Text gedruckt.
  - "cups"        (Linux/macOS): über die CUPS-Druckerwarteschlange, Befehl
                   "lp -o raw" (CUPS ist auf praktisch jeder Linux-Distribution
                   Standard, auch für USB-Thermodrucker)
  - "file"        (Linux): schreibt die ESC/POS-Bytes direkt in die Geräte-
                   datei des USB-Bondruckers (meist /dev/usb/lp0) - ohne CUPS.
                   Oft die einfachste und robusteste Lösung unter Linux.
  - "network"     (beide, plattformunabhängig): direkt per TCP an einen
                   Netzwerkdrucker (Standardport 9100) - klappt nur, wenn der
                   Drucker rohe ESC/POS- oder Text-Daten auf diesem Port
                   akzeptiert (viele normale Netzwerkdrucker tun das nicht).
  - "dummy"       (beide): nur zum Testen, kein echter Ausdruck
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass


@dataclass
class PrinterConfig:
    backend: str = "dummy"  # "win32raw" | "windows_text" | "cups" | "file" | "network" | "dummy"
    windows_printer_name: str | None = None  # Windows: exakter Druckername (leer = Standarddrucker)
    cups_printer_name: str | None = None  # Linux/macOS: Warteschlangenname ("lpstat -p")
    device_path: str | None = None  # Linux: Geräte-Datei, z.B. "/dev/usb/lp0"
    network_host: str | None = None
    network_port: int = 9100
    cut: bool = True


def _build_escpos_bytes(text: str, cut: bool) -> bytes:
    from escpos.printer import Dummy

    # Das kombinierte "x̄" (x + Überstrich) gibt es in keiner Druckerzeichen-
    # tabelle - es würde als "x?" gedruckt. Deshalb wie beim Textdruck
    # ersetzen. Umlaute und ß werden von python-escpos korrekt (CP437) kodiert.
    text = text.replace("x̄", "x-quer")

    p = Dummy()
    for line in text.split("\n"):
        p.text(line + "\n")
    if cut:
        try:
            p.cut()
        except Exception:
            pass
    return p.output


def _text_fuer_normalen_drucker(text: str) -> bytes:
    """Ersetzt Zeichen, die auf einem gewöhnlichen Textdruckweg (ANSI-
    Codepage, kein Unicode) Probleme machen können - z.B. das kombinierte
    "x̄" (x + Überstrich) aus den Bon-Texten - und kodiert den Rest in der
    Windows-ANSI-Codepage (cp1252), mit Ersatzzeichen für alles andere."""
    ersetzt = text.replace("x\u0304", "x-quer")
    return ersetzt.encode("cp1252", errors="replace")


def print_receipt(text: str, config: PrinterConfig) -> bytes | None:
    if config.backend == "dummy":
        return _build_escpos_bytes(text, config.cut)

    if config.backend == "win32raw":
        from escpos.printer import Win32Raw

        p = Win32Raw(config.windows_printer_name)
        p._raw(_build_escpos_bytes(text, config.cut))
        return None

    if config.backend == "windows_text":
        import win32print

        druckername = config.windows_printer_name or win32print.GetDefaultPrinter()
        daten = _text_fuer_normalen_drucker(text)
        h = win32print.OpenPrinter(druckername)
        try:
            job = win32print.StartDocPrinter(h, 1, ("Fuellmengenkontrolle", None, "TEXT"))
            try:
                win32print.StartPagePrinter(h)
                win32print.WritePrinter(h, daten)
                win32print.EndPagePrinter(h)
            finally:
                win32print.EndDocPrinter(h)
        finally:
            win32print.ClosePrinter(h)
        return None

    if config.backend == "cups":
        if not config.cups_printer_name:
            raise ValueError(
                "cups_printer_name muss gesetzt sein. Verfügbare Warteschlangen "
                "mit 'lpstat -p' im Terminal anzeigen lassen."
            )
        try:
            ergebnis = subprocess.run(
                ["lp", "-d", config.cups_printer_name, "-o", "raw"],
                input=_build_escpos_bytes(text, config.cut),
                capture_output=True,
            )
        except FileNotFoundError:
            raise RuntimeError("Der Befehl 'lp' (CUPS) ist nicht installiert.")
        if ergebnis.returncode != 0:
            meldung = (ergebnis.stderr or ergebnis.stdout).decode("utf-8", "replace").strip()
            raise RuntimeError(
                f"CUPS-Druck fehlgeschlagen (Warteschlange '{config.cups_printer_name}'): "
                f"{meldung or 'keine Meldung'}\n\n"
                "Tipp: Namen mit 'lpstat -p' pruefen, oder das Backend 'file' "
                "(z.B. /dev/usb/lp0) verwenden."
            )
        return None

    if config.backend == "file":
        pfad = config.device_path or "/dev/usb/lp0"
        try:
            # O_WRONLY ohne O_CREAT: legt keine neue (falsche) Datei an,
            # falls der Drucker nicht verbunden ist.
            fd = os.open(pfad, os.O_WRONLY)
            try:
                os.write(fd, _build_escpos_bytes(text, config.cut))
            finally:
                os.close(fd)
        except PermissionError:
            raise RuntimeError(
                f"Keine Berechtigung fuer {pfad}. Gruppe der Datei mit "
                f"'ls -l {pfad}' pruefen (meist 'lp') und den Benutzer dort "
                "hinzufuegen: sudo usermod -aG lp $USER - danach neu anmelden."
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"Geraetedatei {pfad} nicht gefunden. Drucker eingeschaltet "
                "und per USB verbunden? Mit 'ls /dev/usb/' pruefen."
            )
        return None

    if config.backend == "network":
        from escpos.printer import Network

        p = Network(config.network_host, port=config.network_port)
        p._raw(_build_escpos_bytes(text, config.cut))
        return None

    raise ValueError(f"Unbekanntes Drucker-Backend: {config.backend}")
