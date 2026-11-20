"""
Generische Anbindung an eine Laborwaage über eine serielle Schnittstelle
(RS232 oder USB-seriell/virtueller COM-Port).

WICHTIG: Das genaue Protokoll hängt vom Waagenhersteller/-modell ab.
Viele einfache/mittlere Laborwaagen senden bei jedem stabilen Wert (oder auf
Tastendruck "Print"/"Data") eine Textzeile wie z.B.:

    "+   12.345 g\r\n"
    "ST,GS,+00.262,g\r\n"
    "S S      0.262 g\r\n"   (Mettler-Toledo MT-SICS Antwort auf Befehl "S")

Dieses Modul liest kontinuierlich Zeilen und extrahiert die erste Zahl vor
einer Gewichtseinheit über einen konfigurierbaren regulären Ausdruck
(WEIGHT_REGEX). Sobald das konkrete Waagenmodell bekannt ist, muss ggf. nur
dieser Regex (und bei Bedarf ein Anfrage-Kommando REQUEST_COMMAND) angepasst
werden - der Rest des Programms bleibt unverändert.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass

try:
    import serial  # pyserial
except ImportError:  # pragma: no cover
    serial = None

# Passt auf "+12.345 g", "-0.262g", "  0,262 g", "+00.262,g" (komma-getrennte
# Formate), etc. - robust gegenüber den meisten gängigen Waagen-Telegrammen.
DEFAULT_WEIGHT_REGEX = re.compile(r"([+-]?\s*\d+[.,]\d+)[,\s]*g", re.IGNORECASE)


@dataclass
class BalanceConfig:
    port: str = "COM3"
    baudrate: int = 9600
    bytesize: int = 8
    parity: str = "N"  # Sartorius Entris Werkseinstellung ist "O" (odd) - siehe README
    stopbits: int = 1
    timeout: float = 1.0
    weight_regex: re.Pattern = DEFAULT_WEIGHT_REGEX
    request_command: bytes | None = None  # z.B. b"P\r\n", falls die Waage nur auf Anfrage sendet


class BalanceReader:
    def __init__(self, config: BalanceConfig):
        if serial is None:
            raise RuntimeError("pyserial ist nicht installiert (pip install pyserial)")
        self.config = config
        self._ser: "serial.Serial | None" = None
        self._lock = threading.Lock()
        self._latest_value: float | None = None
        self._new_values: list[float] = []
        self._reader_thread: threading.Thread | None = None
        self._stop = False

    def connect(self) -> None:
        c = self.config
        self._ser = serial.Serial(
            port=c.port,
            baudrate=c.baudrate,
            bytesize=c.bytesize,
            parity=c.parity,
            stopbits=c.stopbits,
            timeout=c.timeout,
        )
        self._stop = False
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()

    def _read_loop(self) -> None:
        # Bei der Sartorius Entris BCE (Menü DATA.OUT./COM.SBI: COM.OUTP.=IND.AFTR)
        # sendet die Waage genau eine Zeile pro Tastendruck auf die physische
        # [Print]-Taste, und nur wenn der Wert stabil ist. Jede hier erfolgreich
        # geparste Zeile entspricht also direkt einer bewussten Erfassung durch
        # die Person an der Waage - kein zusätzlicher Klick im Programm nötig.
        letzter_wert: float | None = None
        letzte_zeit: float = 0.0
        while not self._stop:
            try:
                raw = self._ser.readline()
                if not raw:
                    continue
                text = raw.decode(errors="ignore")
                match = self.config.weight_regex.search(text)
                if match:
                    value_str = match.group(1).replace(",", ".").replace(" ", "")
                    value = float(value_str)
                    jetzt = time.time()
                    # Schutz gegen doppelt gesendete/empfangene Telegramme:
                    # derselbe Wert innerhalb von 1 Sekunde wird ignoriert
                    # (ein Mensch braucht für den Kapselwechsel deutlich länger).
                    ist_duplikat = (
                        letzter_wert is not None
                        and abs(value - letzter_wert) < 1e-9
                        and (jetzt - letzte_zeit) < 1.0
                    )
                    with self._lock:
                        self._latest_value = value
                        if not ist_duplikat:
                            self._new_values.append(value)
                    letzter_wert = value
                    letzte_zeit = jetzt
            except Exception:
                time.sleep(0.2)

    def pop_new_values(self) -> list[float]:
        """Gibt alle seit dem letzten Aufruf neu von der Waage empfangenen
        (stabilen) Werte zurück und leert die Warteschlange. Dient der
        automatischen Erfassung ohne Nutzer-Klick im Programm."""
        with self._lock:
            values = self._new_values[:]
            self._new_values.clear()
        return values

    def request_value(self, timeout: float = 3.0) -> float | None:
        """Fordert (falls konfiguriert) aktiv einen Wert an und liefert den
        zuletzt empfangenen Messwert zurück."""
        if self.config.request_command and self._ser is not None:
            self._ser.write(self.config.request_command)
        time.sleep(0.3)
        with self._lock:
            return self._latest_value

    def latest_value(self) -> float | None:
        with self._lock:
            return self._latest_value

    def close(self) -> None:
        self._stop = True
        if self._ser and self._ser.is_open:
            self._ser.close()


class ManualBalance:
    """Nur für den Testmodus (siehe config.test_modus): Werte werden manuell
    eingegeben statt von echter Hardware gelesen. Im Produktivbetrieb (Prüfung
    durch Schüler:innen) darf diese Klasse nicht ohne Testmodus nutzbar sein."""

    def __init__(self):
        self._value: float | None = None

    def set_value(self, value: float) -> None:
        self._value = value

    def latest_value(self) -> float | None:
        return self._value

    def pop_new_values(self) -> list[float]:
        return []

    def connect(self) -> None:
        pass

    def close(self) -> None:
        pass
