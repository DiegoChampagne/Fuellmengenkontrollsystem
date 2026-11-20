"""
Baut den Bon-Text nach, im Stil des alten Mettler-Toledo SQC14-D Ausdrucks.
Die Zeilenbreite (WIDTH) muss an die tatsächliche Papierbreite/Schriftgröße
des Bonrollendruckers angepasst werden (Standardwert 42 Zeichen passt bei
den meisten 80mm-Thermodruckern mit "Font A").
"""

from datetime import datetime
from calculations import SampleStats
from acceptance_value import AcceptanceValueResult

WIDTH = 42


def _line(left: str, right: str, width: int = WIDTH) -> str:
    space = max(1, width - len(left) - len(right))
    return f"{left}{' ' * space}{right}"


def _mini_balken(
    wert: float,
    t1_minus: float,
    t1_plus: float,
    t2_minus: float,
    t2_plus: float,
    breite: int = 21,
) -> str:
    """Kompakte Text-Balkengrafik pro Einzelwert, wie auf dem Original-Bon
    des alten Geräts: zeigt auf einen Blick, wo der Wert innerhalb der
    Toleranzgrenzen liegt. "|" = T2-Grenze, ":" = T1-Grenze, Markierung an
    der Position des Werts selbst ("*" innerhalb T1, "+" zwischen T1 und T2,
    "X" außerhalb T2). Nur ASCII-Zeichen, damit es auf jedem Druckweg
    (ESC/POS wie auch der reine Textdruck auf normalen Druckern) sauber
    dargestellt wird."""
    spanne = t2_plus - t2_minus
    if spanne <= 0:
        return ""

    def position(x: float) -> int:
        frac = (x - t2_minus) / spanne
        frac = min(max(frac, 0.0), 1.0)
        return round(frac * (breite - 1))

    zeichen = [" "] * breite
    zeichen[0] = "|"
    zeichen[breite - 1] = "|"
    zeichen[position(t1_minus)] = ":"
    zeichen[position(t1_plus)] = ":"

    if wert < t2_minus or wert > t2_plus:
        marker = "X"
    elif wert < t1_minus or wert > t1_plus:
        marker = "+"
    else:
        marker = "*"
    zeichen[position(wert)] = marker
    return "".join(zeichen)


def build_receipt_text(
    kopfzeile: str,
    proben_id: str,
    nr: int,
    nennfuellm_g: float,
    tara_g: float,
    net_values: list[float],
    stats: SampleStats,
    width: int = WIDTH,
    zeitpunkt_start: datetime | None = None,
    av_result: AcceptanceValueResult | None = None,
) -> str:
    zeitpunkt_start = zeitpunkt_start or datetime.now()

    L = []
    L.append(kopfzeile.center(width))
    L.append("")
    L.append(" STICHPROBE ".center(width, "-"))
    L.append(_line(zeitpunkt_start.strftime("%d.%m.%y"), zeitpunkt_start.strftime("%H:%M"), width))
    L.append(_line("ID", proben_id, width))
    L.append(_line("Nr.", str(nr), width))
    L.append("")
    L.append(_line("Nennfüllm.", f"{nennfuellm_g:.3f} g", width))
    L.append(_line("Tara", f"{tara_g:.3f} g", width))
    L.append(_line("T2-", f"{-stats.t2_pct:.1f}%   {stats.t2_minus:.4f} g", width))
    L.append(_line("T1-", f"{-stats.t1_pct:.1f}%   {stats.t1_minus:.4f} g", width))
    L.append(_line("T1+", f"+{stats.t1_pct:.1f}%   {stats.t1_plus:.4f} g", width))
    L.append(_line("T2+", f"+{stats.t2_pct:.1f}%   {stats.t2_plus:.4f} g", width))
    L.append("")
    for i, v in enumerate(net_values, start=1):
        balken = _mini_balken(v, stats.t1_minus, stats.t1_plus, stats.t2_minus, stats.t2_plus)
        L.append(_line(str(i), f"{v:.3f} {balken}", width))
    L.append("")
    L.append(_line("x\u0304", f"{stats.mean_pct_nominal:6.2f}%   {stats.mean:.4f} g", width))
    L.append(_line("s", f"{stats.stdev_pct_mean:6.2f}%   {stats.stdev:.4f} g", width))
    L.append(_line("Min", f"{stats.minimum_pct_mean:6.2f}%   {stats.minimum:.3f} g", width))
    L.append(_line("Max", f"{stats.maximum_pct_mean:6.2f}%   {stats.maximum:.3f} g", width))
    L.append(_line("R", f"{stats.range_pct_mean:6.2f}%   {stats.range_:.3f} g", width))
    L.append("")
    if not stats.passed:
        L.append("!! AUSSERHALB TOLERANZ !!".center(width))
        L.append("")
    n = stats.n
    L.append(_line("<T2-", f"{stats.n_below_t2_minus}       {stats.n_below_t2_minus/n*100:5.2f} %", width))
    L.append(_line("<T1-", f"{stats.n_below_t1_minus}       {stats.n_below_t1_minus/n*100:5.2f} %", width))
    L.append(_line(">T1+", f"{stats.n_above_t1_plus}       {stats.n_above_t1_plus/n*100:5.2f} %", width))
    L.append(_line(">T2+", f"{stats.n_above_t2_plus}       {stats.n_above_t2_plus/n*100:5.2f} %", width))

    if av_result is not None:
        L.append("")
        L.append(" AKZEPTANZWERT ".center(width, "-"))
        stufe = "amtlich" if av_result.stufe_offiziell else "NICHT amtlich!"
        L.append(_line("n / Stufe", f"{av_result.n} / k={av_result.k} ({stufe})", width))
        L.append(_line("x\u0304", f"{av_result.x_quer_prozent:.2f} %", width))
        L.append(_line("s", f"{av_result.s_prozent:.2f} %", width))
        L.append(_line("M", f"{av_result.m:.2f} %", width))
        L.append(_line("AV", f"{av_result.av:.2f}  (L1={av_result.l1:.0f})", width))
        av_status = "BESTANDEN" if av_result.passed else "NICHT BESTANDEN"
        L.append(f"-> {av_status}".center(width))

    L.append("")
    L.append("")
    return "\n".join(L)


def build_receipt_text_av(
    kopfzeile: str,
    proben_id: str,
    nr: int,
    nennfuellm_g: float,
    tara_g: float,
    net_values: list[float],
    result: AcceptanceValueResult,
    width: int = WIDTH,
    zeitpunkt_start: datetime | None = None,
) -> str:
    """Bon-Text für die Akzeptanzwert-Methode (Ph. Eur. 2.9.40)."""
    zeitpunkt_start = zeitpunkt_start or datetime.now()

    L = []
    L.append(kopfzeile.center(width))
    L.append("")
    L.append(" AKZEPTANZWERT ".center(width, "-"))
    L.append(_line(zeitpunkt_start.strftime("%d.%m.%y"), zeitpunkt_start.strftime("%H:%M"), width))
    L.append(_line("ID", proben_id, width))
    L.append(_line("Nr.", str(nr), width))
    L.append("")
    L.append(_line("Nennfüllm.", f"{nennfuellm_g:.3f} g", width))
    L.append(_line("Tara", f"{tara_g:.3f} g", width))
    L.append(_line("n", str(result.n), width))
    stufe = "amtlich" if result.stufe_offiziell else "NICHT amtlich!"
    L.append(_line("Stufe (k)", f"k={result.k} ({stufe})", width))
    L.append("")
    for i, v in enumerate(net_values, start=1):
        prozent = v / nennfuellm_g * 100
        L.append(_line(str(i), f"{v:.3f} g  {prozent:6.2f}%", width))
    L.append("")
    L.append(_line("x\u0304", f"{result.x_quer_prozent:.2f} %", width))
    L.append(_line("s", f"{result.s_prozent:.2f} %", width))
    L.append(_line("M", f"{result.m:.2f} %", width))
    L.append(_line("AV", f"{result.av:.2f}  (L1={result.l1:.0f})", width))
    L.append("")
    if result.l2_pruefung_relevant:
        L.append(_line("Grenzen L2", f"{result.untere_grenze_prozent:.1f}-{result.obere_grenze_prozent:.1f}%", width))
        L.append(_line("Außerhalb L2", str(len(result.werte_ausserhalb_l2)), width))
    else:
        L.append("(L2-Prüfung erst ab n=30 gefordert)".center(width))
    L.append("")
    status = "BESTANDEN" if result.passed else "NICHT BESTANDEN"
    L.append(f"!! {status} !!".center(width))
    if not result.stufe_offiziell:
        L.append("(n ist keine amtliche Ph.Eur.-Stufe!)".center(width))
    L.append("")
    L.append("")
    return "\n".join(L)
