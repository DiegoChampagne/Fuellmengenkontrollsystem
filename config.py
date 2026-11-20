"""
Zentrale, editierbare Einstellungen. Werden aus config.json geladen, falls
vorhanden, sonst gelten die Standardwerte unten. So können Lehrkräfte ohne
Python-Kenntnisse z.B. den COM-Port oder Druckernamen anpassen.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sys
from dataclasses import dataclass, asdict, field

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

IS_WINDOWS = sys.platform == "win32"

# Passwortschutz der Einstellungen: Das Passwort steht NICHT im Quellcode,
# sondern wird als gesalzener Hash (PBKDF2) in config.json gespeichert. Beim
# ersten Öffnen der Einstellungen wird ein Passwort festgelegt; ändern kann
# man es später im Einstellungsdialog.
_PBKDF2_RUNDEN = 200_000


def hash_passwort(passwort: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", passwort.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_RUNDEN)
    return f"pbkdf2${salt}${h.hex()}"


def pruefe_passwort(passwort: str, gespeichert: str) -> bool:
    try:
        _, salt, erwartet = gespeichert.split("$")
        h = hashlib.pbkdf2_hmac("sha256", passwort.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_RUNDEN)
        return hmac.compare_digest(h.hex(), erwartet)
    except ValueError:
        return False

# Auswählbare Darreichungsformen im Dropdown. "Zäpfchen"/"Tabletten" -> Tara 0.
# "Kapsel Größe N" -> Tara aus config.kapsel_leergewichte_g["N"], Nennfüllmenge-
# Default aus config.kapsel_nennfuellmengen_g["N"].
# "Einzeldosierte Pulver (Pulverbriefchen)" -> Tara aus config.pulverbriefchen_leergewicht_g.
KAPSELGROESSEN = ["000", "00", "0", "1", "2", "3", "4"]

DARREICHUNGSFORMEN = [
    "Zäpfchen",
    "Tabletten",
    *[f"Kapsel Größe {g}" for g in KAPSELGROESSEN],
    "Einzeldosierte Pulver (Pulverbriefchen)",
]


def tara_fuer_darreichungsform(config: "AppConfig", darreichungsform: str) -> float:
    if darreichungsform in ("Zäpfchen", "Tabletten"):
        return 0.0
    if darreichungsform.startswith("Kapsel Größe "):
        groesse = darreichungsform.replace("Kapsel Größe ", "").strip()
        return config.kapsel_leergewichte_g.get(groesse, 0.0)
    if darreichungsform == "Einzeldosierte Pulver (Pulverbriefchen)":
        return config.pulverbriefchen_leergewicht_g
    return 0.0


def nennfuellmenge_fuer_darreichungsform(config: "AppConfig", darreichungsform: str) -> float | None:
    """Default-Nennfüllmenge (g) für die aktuelle Darreichungsform, aus der
    schulinternen Kapselgrößen-Tabelle. Gibt None zurück, wenn es dafür
    keinen Tabellenwert gibt (z.B. Zäpfchen, Tabletten, Benutzerdefiniert) -
    dann bleibt das Nennfüllmengen-Feld unverändert stehen."""
    if darreichungsform.startswith("Kapsel Größe "):
        groesse = darreichungsform.replace("Kapsel Größe ", "").strip()
        return config.kapsel_nennfuellmengen_g.get(groesse)
    return None


def t1_prozent_tabelle_2_9_5(darreichungsform: str, durchschnittsmasse_mg: float) -> float | None:
    """Zulässige Abweichung T1 (%) je Einzelwert nach Ph. Eur. Tabelle 2.9.5-1
    ("Gleichförmigkeit der Masse einzeldosierter Arzneiformen"), abhängig von
    Arzneiform und Durchschnittsmasse (mg). T2 (Grenzwert, den keine Einheit
    überschreiten darf) ist per Konvention immer das Doppelte von T1 - siehe
    Originalausdruck des alten Geräts (T1=±10%, T2=±20% bei Kapseln <300 mg).

    Gibt None zurück, wenn die Arzneiform nicht in der Tabelle abgebildet ist
    (z.B. "Benutzerdefiniert") - dann sollte auf einen konfigurierten
    Alternativwert zurückgefallen werden.

    Tabelle 2.9.5-1 (Auszug, die hier relevanten Zeilen):
      Nicht überzogene Tabletten/Filmtabletten:
        ≤ 80 mg -> 10%  |  > 80 und < 250 mg -> 7,5%  |  ≥ 250 mg -> 5%
      Kapseln, nicht überzogene Granulate und Pulver (Einzeldosisbehältnisse):
        < 300 mg -> 10%  |  ≥ 300 mg -> 7,5%
      Suppositorien und Vaginalzäpfchen:
        ohne Unterscheidung der Massen -> 5%
    """
    if darreichungsform == "Zäpfchen":
        return 5.0

    if darreichungsform == "Tabletten":
        if durchschnittsmasse_mg <= 80:
            return 10.0
        elif durchschnittsmasse_mg < 250:
            return 7.5
        else:
            return 5.0

    if darreichungsform.startswith("Kapsel Größe ") or darreichungsform == "Einzeldosierte Pulver (Pulverbriefchen)":
        return 10.0 if durchschnittsmasse_mg < 300 else 7.5

    return None


def _default_waage_port() -> str:
    # Windows: "COM3", "COM4", ... ; Linux: "/dev/ttyUSB0" (USB-Serial-Adapter)
    # oder "/dev/ttyACM0" (manche Waagen melden sich so). Über "dmesg | grep tty"
    # bzw. "ls /dev/tty*" nach dem Anschließen der Waage herausfinden.
    return "COM3" if IS_WINDOWS else "/dev/ttyUSB0"


def _default_drucker_backend() -> str:
    # Windows: Drucker über Windows-Treiber installiert -> "win32raw"
    # Linux: Drucker über CUPS installiert (auch bei USB-Thermodruckern üblich) -> "cups"
    return "win32raw" if IS_WINDOWS else "cups"


def _default_kapsel_leergewichte_g() -> dict:
    # Typische/durchschnittliche Leerkapselgewichte für Hartgelatinekapseln
    # nach gängigen Herstellerangaben. Diese Werte schwanken je nach
    # Hersteller/Charge/Material (Gelatine vs. HPMC) durchaus um mehrere mg -
    # UNBEDINGT mit den an der Schule tatsächlich verwendeten Kapseln
    # kalibrieren (z.B. 20 Leerkapseln wiegen und den Mittelwert eintragen)
    # und in den Einstellungen anpassen! Werte für 000/00 sind grobe
    # Schätzungen (keine belastbare Herstellerquelle gefunden) - hier
    # besonders wichtig, selbst nachzumessen.
    return {
        "000": 0.150,
        "00": 0.120,
        "0": 0.096,
        "1": 0.076,
        "2": 0.063,
        "3": 0.049,
        "4": 0.040,
    }


def _default_kapsel_nennfuellmengen_g() -> dict:
    # Schulinterne Vorgabe (von der Lehrkraft bereitgestellte Tabelle):
    # Standard-Nennfüllmenge pro Kapselgröße, wird beim Auswählen der
    # jeweiligen Kapselgröße automatisch ins Nennfüllmengen-Feld
    # eingetragen (bleibt danach normal editierbar, falls eine konkrete
    # Rezeptur einen anderen Sollwert vorgibt).
    return {
        "000": 0.754,
        "00": 0.523,
        "0": 0.374,
        "1": 0.275,
        "2": 0.204,
        "3": 0.165,
        "4": 0.116,
    }


@dataclass
class AppConfig:
    schulname: str = "PTA Schule"
    einstellungen_passwort_hash: str = ""  # leer = noch kein Passwort gesetzt
    stichprobenumfang: int = 30
    nennfuellm_g: float = 0.300
    toleranz_t1_prozent: float = 10.0
    toleranz_t2_prozent: float = 20.0
    kapsel_leergewichte_g: dict = field(default_factory=_default_kapsel_leergewichte_g)
    kapsel_nennfuellmengen_g: dict = field(default_factory=_default_kapsel_nennfuellmengen_g)

    # Leergewicht eines leeren Pulverbriefchens - anders als bei Kapseln gibt
    # es hierfür keine standardisierten Größen/Richtwerte (Material und
    # Größe sind je Apotheke/Schule unterschiedlich) - MUSS vor der ersten
    # echten Prüfung durch Wiegen leerer Briefchen selbst ermittelt werden!
    pulverbriefchen_leergewicht_g: float = 0.0

    # Grafische Live-Vorschau (siehe chart.LivePreviewWidget) grundsätzlich
    # sperren - z.B. wenn sie im Unterricht nicht gezeigt werden soll.
    vorschau_gesperrt: bool = False

    # Testmodus: erlaubt manuelle Werteingabe (zum Testen ohne Waage).
    # WICHTIG: Vor dem echten Einsatz durch Schüler:innen in den
    # Einstellungen auf False setzen, damit keine Werte "erfunden" werden
    # können!
    test_modus: bool = True

    # Waage
    waage_port: str = field(default_factory=_default_waage_port)
    waage_baudrate: int = 9600
    waage_modus: str = "manuell"  # "seriell" oder "manuell" (nur mit test_modus=True nutzbar)

    # Drucker
    drucker_backend: str = field(default_factory=_default_drucker_backend)  # "dummy" | "win32raw" | "cups" | "file" | "network"
    drucker_windows_name: str | None = None   # Windows: exakter Druckername aus "Drucker & Scanner"
    drucker_cups_name: str | None = None      # Linux/macOS: Warteschlangenname aus "lpstat -p"
    drucker_geraetedatei: str | None = "/dev/usb/lp0"  # Linux: Backend "file"
    drucker_netzwerk_host: str | None = None
    bon_zeichen_breite: int = 42

    # Speicherung
    datenbank_pfad: str = "fuellmengenkontrolle.db"


def load_config() -> AppConfig:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return AppConfig(**data)
    return AppConfig()


def save_config(config: AppConfig) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(asdict(config), f, indent=2, ensure_ascii=False)
