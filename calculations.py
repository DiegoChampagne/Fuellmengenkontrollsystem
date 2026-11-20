"""
Berechnungslogik für die Füllmengenkontrolle (Gleichförmigkeit der Masse,
angelehnt an Ph. Eur. 2.9.5).

Die Formeln wurden anhand eines echten Ausdrucks des alten Mettler-Toledo
SQC14-D Systems zurückgerechnet und stimmen auf die letzte gedruckte Stelle:

  - x̄ (Mittelwert) wird aus den n Nettoeinzelwerten gebildet.
  - Die Prozentangabe NEBEN x̄ bezieht sich auf die Nennfüllmenge.
  - Alle anderen Prozentangaben (s, Min, Max, R, T1-/T1+/T2-/T2+) beziehen
    sich auf den Stichproben-Mittelwert x̄ (NICHT auf die Nennfüllmenge!).
  - s ist die Stichproben-Standardabweichung (n-1, Bessel-Korrektur).
  - T1 = ±10 %, T2 = ±20 % um x̄ (Standard-Toleranzen, hier fix wie gewünscht).
"""

from dataclasses import dataclass
import statistics


@dataclass
class SampleStats:
    n: int
    mean: float
    mean_pct_nominal: float
    stdev: float
    stdev_pct_mean: float
    minimum: float
    minimum_pct_mean: float
    maximum: float
    maximum_pct_mean: float
    range_: float
    range_pct_mean: float
    t2_minus: float
    t1_minus: float
    t1_plus: float
    t2_plus: float
    t1_pct: float
    t2_pct: float
    n_below_t2_minus: int
    n_below_t1_minus: int
    n_above_t1_plus: int
    n_above_t2_plus: int

    @property
    def passed(self) -> bool:
        """Ph.Eur. 2.9.5: keine Einheit außerhalb ±20%, max. 2 außerhalb ±10%."""
        n_outside_t1 = self.n_below_t1_minus + self.n_above_t1_plus
        n_outside_t2 = self.n_below_t2_minus + self.n_above_t2_plus
        return n_outside_t2 == 0 and n_outside_t1 <= 2


def compute_stats(
    net_values: list[float],
    nominal_fill_g: float,
    t1_pct: float = 10.0,
    t2_pct: float = 20.0,
) -> SampleStats:
    if len(net_values) < 2:
        raise ValueError("Mindestens 2 Werte für die Statistik nötig.")

    n = len(net_values)
    mean = statistics.mean(net_values)
    stdev = statistics.stdev(net_values)  # n-1
    minimum = min(net_values)
    maximum = max(net_values)
    range_ = maximum - minimum

    t1_minus = mean * (1 - t1_pct / 100)
    t1_plus = mean * (1 + t1_pct / 100)
    t2_minus = mean * (1 - t2_pct / 100)
    t2_plus = mean * (1 + t2_pct / 100)

    return SampleStats(
        n=n,
        mean=mean,
        mean_pct_nominal=mean / nominal_fill_g * 100,
        stdev=stdev,
        stdev_pct_mean=stdev / mean * 100,
        minimum=minimum,
        minimum_pct_mean=minimum / mean * 100,
        maximum=maximum,
        maximum_pct_mean=maximum / mean * 100,
        range_=range_,
        range_pct_mean=range_ / mean * 100,
        t2_minus=t2_minus,
        t1_minus=t1_minus,
        t1_plus=t1_plus,
        t2_plus=t2_plus,
        t1_pct=t1_pct,
        t2_pct=t2_pct,
        n_below_t2_minus=sum(1 for v in net_values if v < t2_minus),
        n_below_t1_minus=sum(1 for v in net_values if v < t1_minus),
        n_above_t1_plus=sum(1 for v in net_values if v > t1_plus),
        n_above_t2_plus=sum(1 for v in net_values if v > t2_plus),
    )
