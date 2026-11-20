"""
Speichert jede Stichprobe in einer lokalen SQLite-Datenbank (eine einzelne
Datei, kein Server nötig) - für Dokumentation/Nachvollziehbarkeit im
Unterricht. Unterstützt beide Auswertungsmethoden (Massenabweichung und
Akzeptanzwert): methodenspezifische Zusatzwerte landen in `extra_json`.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS stichproben (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zeitstempel TEXT NOT NULL,
    proben_id TEXT,
    name TEXT,
    nr INTEGER,
    methode TEXT,
    nennfuellm_g REAL,
    tara_g REAL,
    werte_json TEXT,
    mittelwert_g REAL,
    stdabw_g REAL,
    min_g REAL,
    max_g REAL,
    spannweite_g REAL,
    n_unter_t2 INTEGER,
    n_unter_t1 INTEGER,
    n_ueber_t1 INTEGER,
    n_ueber_t2 INTEGER,
    extra_json TEXT,
    bestanden INTEGER
);
"""


@contextmanager
def get_connection(db_path: str = "fuellmengenkontrolle.db"):
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_sample(
    db_path: str,
    proben_id: str,
    nr: int,
    nominal_fill_g: float,
    tara_g: float,
    net_values: list[float],
    result,
    methode: str = "Massenabweichung (Ph. Eur. 2.9.5)",
    name: str = "",
) -> None:
    """`result` ist entweder ein calculations.SampleStats (Massenabweichung)
    oder ein acceptance_value.AcceptanceValueResult (Akzeptanzwert) - beide
    haben eine `.passed`-Eigenschaft, der Rest wird je nach Typ behandelt."""
    is_av = hasattr(result, "av")  # nur AcceptanceValueResult hat dieses Feld

    if is_av:
        mittelwert = stdabw = min_g = max_g = spannweite = None
        n_unter_t2 = n_unter_t1 = n_ueber_t1 = n_ueber_t2 = None
        extra = {
            "x_quer_prozent": result.x_quer_prozent,
            "s_prozent": result.s_prozent,
            "m": result.m,
            "av": result.av,
            "k": result.k,
            "l1": result.l1,
            "l2": result.l2,
            "stufe_offiziell": result.stufe_offiziell,
            "n_ausserhalb_l2": len(result.werte_ausserhalb_l2),
        }
    else:
        mittelwert = result.mean
        stdabw = result.stdev
        min_g = result.minimum
        max_g = result.maximum
        spannweite = result.range_
        n_unter_t2 = result.n_below_t2_minus
        n_unter_t1 = result.n_below_t1_minus
        n_ueber_t1 = result.n_above_t1_plus
        n_ueber_t2 = result.n_above_t2_plus
        extra = {}

    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO stichproben (
                zeitstempel, proben_id, name, nr, methode, nennfuellm_g, tara_g, werte_json,
                mittelwert_g, stdabw_g, min_g, max_g, spannweite_g,
                n_unter_t2, n_unter_t1, n_ueber_t1, n_ueber_t2, extra_json, bestanden
            ) VALUES (datetime('now','localtime'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                proben_id,
                name,
                nr,
                methode,
                nominal_fill_g,
                tara_g,
                json.dumps(net_values),
                mittelwert,
                stdabw,
                min_g,
                max_g,
                spannweite,
                n_unter_t2,
                n_unter_t1,
                n_ueber_t1,
                n_ueber_t2,
                json.dumps(extra, ensure_ascii=False),
                int(result.passed),
            ),
        )


def export_csv(db_path: str, csv_path: str) -> None:
    import csv

    with get_connection(db_path) as conn:
        cur = conn.execute("SELECT * FROM stichproben ORDER BY id")
        rows = cur.fetchall()
        headers = [d[0] for d in cur.description]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(headers)
        writer.writerows(rows)
