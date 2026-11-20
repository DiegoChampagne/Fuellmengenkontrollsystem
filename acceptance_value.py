"""
Akzeptanzwert-Methode (Acceptance Value, AV) nach Ph. Eur. 2.9.40
"Gleichförmigkeit der Masse einzeldosierter Arzneiformen" - hier in der
harmonisierten Fassung mit USP <905> und JP, als Alternative zur klassischen
Massenabweichungsprüfung (Ph. Eur. 2.9.5, siehe calculations.py).

Quelle der Formel/Tabelle: harmonisiertes Kapitel USP <905> "Uniformity of
Dosage Units" (inhaltsgleich mit Ph. Eur. 2.9.40 Tabelle 2.9.40.-2), geprüft
gegen den offiziellen Wortlaut.

WICHTIGER METHODISCHER HINWEIS: Die Originalmethode bestimmt den
Wirkstoffgehalt jeder Einheit per Gehaltsbestimmung (Assay). Da an der
Schule nur die MASSE bestimmt wird, wird - wie in Ph. Eur./USP für die
Methode "Weight/Mass Variation" ausdrücklich vorgesehen - die Einzelmasse
als Stellvertreter (Surrogat) für den Gehalt verwendet, unter der Annahme
gleichmäßiger Wirkstoffkonzentration:

    x_i (%) = (Nettomasse_i / Nennfüllmenge) * 100

Der Zielwert T wird dabei auf 100 % gesetzt (Nennfüllmenge = 100 % Soll).

Berechnung des Akzeptanzwerts AV (Fall T ≤ 101,5 %, Standardfall T=100%):
    Wenn 98,5 % ≤ x̄ ≤ 101,5 %:  M = x̄            AV = k·s
    Wenn x̄ < 98,5 %:            M = 98,5 %        AV = (98,5 - x̄) + k·s
    Wenn x̄ > 101,5 %:           M = 101,5 %       AV = (x̄ - 101,5) + k·s

mit x̄ = Mittelwert der Einzelwerte (%), s = Stichproben-Standardabweichung (%).

Kriterien:
    - Stufe 1 (n=10): erfüllt, wenn AV ≤ L1 (Standard: 15,0).
      Falls nicht: 20 weitere Einheiten prüfen (-> n=30 gesamt).
    - Stufe 2 (n=30, k=2,0 statt 2,4): erfüllt, wenn AV ≤ L1 UND kein
      Einzelwert außerhalb [1-0,01·L2]·M bis [1+0,01·L2]·M (Standard: L2=25,0).

Offizielle Tabellenwerte für den Akzeptabilitätsfaktor k gibt es nur für
n=10 (k=2,4) und n=30 (k=2,0). Bei anderen Stichprobengrößen (z.B. durch
vorzeitiges Beenden) wird ersatzweise der näherliegende der beiden Werte
verwendet und das Ergebnis als "nicht amtliche Stufe" gekennzeichnet.
"""

from __future__ import annotations

from dataclasses import dataclass
import statistics


@dataclass
class AcceptanceValueResult:
    n: int
    k: float
    stufe_offiziell: bool  # True nur bei n=10 oder n=30
    x_quer_prozent: float
    s_prozent: float
    m: float
    av: float
    l1: float
    l2: float
    untere_grenze_prozent: float
    obere_grenze_prozent: float
    werte_ausserhalb_l2: list  # Liste der (Index, Nettomasse_g) außerhalb L2
    l2_pruefung_relevant: bool  # L2-Grenzwertprüfung ist nur ab n=30 gefordert
    erfuellt_l1: bool
    erfuellt_l2: bool

    @property
    def passed(self) -> bool:
        return self.erfuellt_l1 and self.erfuellt_l2


def compute_acceptance_value(
    net_values: list[float],
    nominal_fill_g: float,
    t_prozent: float = 100.0,
    l1: float = 15.0,
    l2: float = 25.0,
) -> AcceptanceValueResult:
    n = len(net_values)
    if n < 2:
        raise ValueError("Mindestens 2 Werte für die Berechnung nötig.")
    if t_prozent > 101.5:
        raise ValueError(
            "Zielwert T > 101,5% wird hier nicht unterstützt (Fall 2 der "
            "Ph.Eur.-Tabelle, in der Praxis unüblich für diese Anwendung)."
        )

    prozentwerte = [(v / nominal_fill_g) * t_prozent for v in net_values]
    x_quer = statistics.mean(prozentwerte)
    s = statistics.stdev(prozentwerte)

    if n == 10:
        k = 2.4
        stufe_offiziell = True
    elif n == 30:
        k = 2.0
        stufe_offiziell = True
    else:
        k = 2.4 if n < 20 else 2.0
        stufe_offiziell = False

    if 98.5 <= x_quer <= 101.5:
        m = x_quer
        av = k * s
    elif x_quer < 98.5:
        m = 98.5
        av = (98.5 - x_quer) + k * s
    else:
        m = 101.5
        av = (x_quer - 101.5) + k * s

    untere_grenze = (1 - 0.01 * l2) * m
    obere_grenze = (1 + 0.01 * l2) * m
    ausserhalb = [
        (i + 1, v)
        for i, (v, p) in enumerate(zip(net_values, prozentwerte))
        if p < untere_grenze or p > obere_grenze
    ]

    l2_relevant = n >= 30
    erfuellt_l1 = av <= l1
    erfuellt_l2 = (len(ausserhalb) == 0) if l2_relevant else True

    return AcceptanceValueResult(
        n=n,
        k=k,
        stufe_offiziell=stufe_offiziell,
        x_quer_prozent=x_quer,
        s_prozent=s,
        m=m,
        av=av,
        l1=l1,
        l2=l2,
        untere_grenze_prozent=untere_grenze,
        obere_grenze_prozent=obere_grenze,
        werte_ausserhalb_l2=ausserhalb,
        l2_pruefung_relevant=l2_relevant,
        erfuellt_l1=erfuellt_l1,
        erfuellt_l2=erfuellt_l2,
    )
