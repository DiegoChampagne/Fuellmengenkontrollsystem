"""
Grafische Darstellung der Stichprobe. Wird beim Klick auf "Ende: Auswerten &
Drucken" zusätzlich zum (Bon-)Ausdruck angezeigt - ersetzt/ergänzt die
ASCII-Balkengrafik des Originalbons durch eine echte Grafik auf dem
Bildschirm. Unterstützt beide Auswertungsmethoden (Massenabweichung nach
Ph. Eur. 2.9.5 und Akzeptanzwert nach Ph. Eur. 2.9.40).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QWidget
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from calculations import compute_stats, SampleStats
from acceptance_value import compute_acceptance_value, AcceptanceValueResult


def _status_label(passed: bool) -> str:
    farbe = "#28a745" if passed else "#dc3545"
    text = "BESTANDEN" if passed else "NICHT BESTANDEN"
    return f"<span style='color:{farbe}; font-size: 14pt;'><b>{text}</b></span>"


def _build_mass_variation_figure(net_values: list[float], stats: SampleStats, nominal_fill_g: float) -> Figure:
    n = len(net_values)
    x = list(range(1, n + 1))

    fig = Figure(figsize=(7.5, 5))
    ax = fig.add_subplot(111)

    ax.axhspan(stats.t2_minus, stats.t1_minus, color="#fff3cd", zorder=0)
    ax.axhspan(stats.t1_plus, stats.t2_plus, color="#fff3cd", zorder=0)
    ax.axhspan(stats.t1_minus, stats.t1_plus, color="#d4edda", zorder=0)

    ax.axhline(stats.mean, color="black", linewidth=1.2, label="x̄ (Mittelwert)")
    ax.axhline(stats.t1_minus, color="#856404", linewidth=1, linestyle="--", label=f"T1 (±{stats.t1_pct:g}%)")
    ax.axhline(stats.t1_plus, color="#856404", linewidth=1, linestyle="--")
    ax.axhline(stats.t2_minus, color="#a94442", linewidth=1, linestyle=":", label=f"T2 (±{stats.t2_pct:g}%)")
    ax.axhline(stats.t2_plus, color="#a94442", linewidth=1, linestyle=":")

    colors = []
    for v in net_values:
        if v < stats.t2_minus or v > stats.t2_plus:
            colors.append("#dc3545")
        elif v < stats.t1_minus or v > stats.t1_plus:
            colors.append("#e0a800")
        else:
            colors.append("#28a745")

    ax.scatter(x, net_values, c=colors, zorder=5, edgecolors="black", linewidths=0.5, s=50)

    ax.set_xlabel("Einzelmessung Nr.")
    ax.set_ylabel("Nettomasse (g)")
    ax.set_title(
        f"Massenabweichung (Ph. Eur. 2.9.5) - Nennfüllm. {nominal_fill_g:.3f} g, "
        f"n={n}, x̄={stats.mean:.4f} g, s={stats.stdev_pct_mean:.2f}%"
    )
    ax.legend(loc="best", fontsize=8)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


def _build_acceptance_value_figure(net_values: list[float], result: AcceptanceValueResult, nominal_fill_g: float) -> Figure:
    n = len(net_values)
    x = list(range(1, n + 1))
    prozentwerte = [(v / nominal_fill_g) * 100 for v in net_values]

    fig = Figure(figsize=(7.5, 5))
    ax = fig.add_subplot(111)

    ax.axhspan(result.untere_grenze_prozent, result.obere_grenze_prozent, color="#d4edda", zorder=0)
    ax.axhline(result.m, color="black", linewidth=1.2, label="M (Referenzwert)")
    ax.axhline(100.0, color="#6c757d", linewidth=1, linestyle="-.", label="T (Ziel = 100%)")
    ax.axhline(result.untere_grenze_prozent, color="#a94442", linewidth=1, linestyle=":",
               label=f"±L2 ({result.l2:.0f}%) um M")
    ax.axhline(result.obere_grenze_prozent, color="#a94442", linewidth=1, linestyle=":")

    ausserhalb_indices = {i for i, _ in result.werte_ausserhalb_l2}
    colors = ["#dc3545" if (i + 1) in ausserhalb_indices else "#28a745" for i in range(n)]

    ax.scatter(x, prozentwerte, c=colors, zorder=5, edgecolors="black", linewidths=0.5, s=50)

    ax.set_xlabel("Einzelmessung Nr.")
    ax.set_ylabel("Masse (% der Nennfüllmenge)")
    stufe = "amtliche Stufe" if result.stufe_offiziell else "KEINE amtliche Stufe (nur Orientierung)"
    ax.set_title(
        f"Akzeptanzwert (Ph. Eur. 2.9.40) - n={n} ({stufe})\n"
        f"x̄={result.x_quer_prozent:.2f}%, s={result.s_prozent:.2f}%, k={result.k}, AV={result.av:.2f} (L1={result.l1:.0f})"
    )
    ax.legend(loc="best", fontsize=8)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


class ChartDialog(QDialog):
    def __init__(self, figure: Figure, passed: bool, proben_id: str, nr: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Grafische Auswertung - {proben_id} Nr. {nr}")
        self.resize(760, 560)
        layout = QVBoxLayout(self)

        header = QLabel(_status_label(passed))
        layout.addWidget(header)

        canvas = FigureCanvas(figure)
        layout.addWidget(canvas)


def show_mass_variation_chart(net_values, stats: SampleStats, nominal_fill_g: float, proben_id: str, nr: int, parent=None) -> ChartDialog:
    fig = _build_mass_variation_figure(net_values, stats, nominal_fill_g)
    dlg = ChartDialog(fig, stats.passed, proben_id, nr, parent=parent)
    dlg.show()
    return dlg


def show_acceptance_value_chart(net_values, result: AcceptanceValueResult, nominal_fill_g: float, proben_id: str, nr: int, parent=None) -> ChartDialog:
    fig = _build_acceptance_value_figure(net_values, result, nominal_fill_g)
    dlg = ChartDialog(fig, result.passed, proben_id, nr, parent=parent)
    dlg.show()
    return dlg


class LivePreviewWidget(QWidget):
    """Eingebettete, laufend aktualisierte grafische Vorschau fürs
    Hauptfenster (kein Popup, kein Druckvorgang). Zeigt bewusst KEINE
    Zahlen-Ergebnisse (kein x̄, s, AV, kein "BESTANDEN"-Text) - nur die reine
    grafische Verteilung der bisher erfassten Werte samt Toleranzbereichen.
    Lässt sich per set_locked() sperren (zeigt dann nur "Vorschau gesperrt")."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._locked_label = QLabel("Vorschau gesperrt")
        self._locked_label.setAlignment(Qt.AlignCenter)
        self._locked_label.setStyleSheet("font-size: 20pt; color: #888888;")

        self._figure = Figure()
        self._canvas = FigureCanvas(self._figure)

        layout.addWidget(self._locked_label)
        layout.addWidget(self._canvas)

        self._locked = False
        self.set_locked(False)
        self._draw_placeholder("Warte auf Messwerte …")

    def set_locked(self, locked: bool):
        self._locked = locked
        self._locked_label.setVisible(locked)
        self._canvas.setVisible(not locked)

    def _draw_placeholder(self, text: str):
        self._figure.clear()
        ax = self._figure.add_subplot(111)
        ax.text(0.5, 0.5, text, ha="center", va="center", transform=ax.transAxes, color="#888888")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        self._canvas.draw()

    def clear(self):
        if not self._locked:
            self._draw_placeholder("Warte auf Messwerte …")

    def update_preview(
        self,
        net_values: list[float],
        nominal_fill_g: float,
        ist_akzeptanzwert: bool,
        t1_pct: float = 10.0,
        t2_pct: float = 20.0,
    ):
        if self._locked:
            return
        n = len(net_values)
        if n < 2:
            self._draw_placeholder("Warte auf Messwerte …")
            return

        self._figure.clear()
        ax = self._figure.add_subplot(111)
        x = list(range(1, n + 1))

        try:
            if ist_akzeptanzwert:
                result = compute_acceptance_value(net_values, nominal_fill_g)
                prozentwerte = [(v / nominal_fill_g) * 100 for v in net_values]
                ax.axhspan(result.untere_grenze_prozent, result.obere_grenze_prozent, color="#d4edda", zorder=0)
                ax.axhline(result.m, color="black", linewidth=1)
                ausserhalb = {i for i, _ in result.werte_ausserhalb_l2}
                colors = ["#dc3545" if (i + 1) in ausserhalb else "#28a745" for i in range(n)]
                ax.scatter(x, prozentwerte, c=colors, edgecolors="black", linewidths=0.5, zorder=5, s=45)
                ax.set_ylabel("Masse (% der Nennfüllmenge)")
            else:
                stats = compute_stats(net_values, nominal_fill_g, t1_pct=t1_pct, t2_pct=t2_pct)
                ax.axhspan(stats.t2_minus, stats.t1_minus, color="#fff3cd", zorder=0)
                ax.axhspan(stats.t1_plus, stats.t2_plus, color="#fff3cd", zorder=0)
                ax.axhspan(stats.t1_minus, stats.t1_plus, color="#d4edda", zorder=0)
                ax.axhline(stats.mean, color="black", linewidth=1)
                colors = []
                for v in net_values:
                    if v < stats.t2_minus or v > stats.t2_plus:
                        colors.append("#dc3545")
                    elif v < stats.t1_minus or v > stats.t1_plus:
                        colors.append("#e0a800")
                    else:
                        colors.append("#28a745")
                ax.scatter(x, net_values, c=colors, edgecolors="black", linewidths=0.5, zorder=5, s=45)
                ax.set_ylabel("Nettomasse (g)")
        except Exception:
            self._draw_placeholder("Warte auf Messwerte …")
            return

        ax.set_xlabel("Messung Nr.")
        ax.grid(True, axis="y", alpha=0.3)
        self._figure.tight_layout()
        self._canvas.draw()
