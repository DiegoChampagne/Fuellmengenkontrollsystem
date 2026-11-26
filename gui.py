from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QDoubleSpinBox,
    QSpinBox,
    QPushButton,
    QListWidget,
    QMessageBox,
    QDialog,
    QComboBox,
    QGroupBox,
    QCheckBox,
    QInputDialog,
    QScrollArea,
    QScroller,
)

from config import (
    AppConfig, load_config, save_config, DARREICHUNGSFORMEN, KAPSELGROESSEN,
    tara_fuer_darreichungsform, nennfuellmenge_fuer_darreichungsform,
    hash_passwort, pruefe_passwort, datenbank_pfad_aufloesen, t1_prozent_tabelle_2_9_5,
)
from balance import BalanceReader, BalanceConfig, ManualBalance
from calculations import compute_stats
from acceptance_value import compute_acceptance_value
from receipt import build_receipt_text, build_receipt_text_av
from printer import print_receipt, PrinterConfig
from storage import save_sample
from chart import show_mass_variation_chart, show_acceptance_value_chart, LivePreviewWidget

METHODEN = [
    "Massenabweichung (Ph. Eur. 2.9.5)",
    "Akzeptanzwert (Ph. Eur. 2.9.40)",
]


class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.config = config

        # Der Dialog ist länger als der Bildschirm. Deshalb liegt das Formular
        # in einem Scrollbereich mit breiter Scrollleiste (gut mit Finger oder
        # Maus zu greifen). Die Knöpfe "Speichern"/"Abbrechen" bleiben unten
        # fest sichtbar und scrollen nicht mit.
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.verticalScrollBar().setStyleSheet(
            "QScrollBar:vertical { width: 16px; background: #ececec; margin: 0; }"
            "QScrollBar::handle:vertical { background: #8a8a8a; min-height: 40px;"
            " border-radius: 5px; margin: 2px; }"
            "QScrollBar::handle:vertical:hover { background: #555555; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }"
        )
        # Auf Touchscreens (z.B. Surface) lässt sich der Inhalt mit dem Finger ziehen.
        QScroller.grabGesture(scroll.viewport(), QScroller.ScrollerGestureType.TouchGesture)
        outer.addWidget(scroll, 1)

        inhalt = QWidget()
        scroll.setWidget(inhalt)
        form = QFormLayout(inhalt)

        screen = self.screen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.resize(max(620, int(geo.width() * 0.4)), int(geo.height() * 0.9))

        self.schulname_edit = QLineEdit(config.schulname)
        form.addRow("Kopfzeile / Schulname:", self.schulname_edit)

        self.umfang_spin = QSpinBox()
        self.umfang_spin.setRange(2, 100)
        self.umfang_spin.setValue(config.stichprobenumfang)
        form.addRow("Standard-Stichprobenumfang (n):", self.umfang_spin)

        self.test_modus_check = QCheckBox("Testmodus (manuelle Werteingabe erlauben)")
        self.test_modus_check.setChecked(config.test_modus)
        self.test_modus_check.setStyleSheet("QCheckBox { color: #b34700; font-weight: bold; }")
        form.addRow(self.test_modus_check)
        form.addRow(QLabel(
            "⚠ Vor dem echten Einsatz durch Schüler:innen UNBEDINGT deaktivieren -\n"
            "sonst können Werte frei erfunden statt gewogen werden!"
        ))

        self.waage_modus_combo = QComboBox()
        self.waage_modus_combo.addItems(["manuell", "seriell"])
        self.waage_modus_combo.setCurrentText(config.waage_modus)
        form.addRow("Waagen-Modus:", self.waage_modus_combo)

        self.neues_passwort_edit = QLineEdit()
        self.neues_passwort_edit.setEchoMode(QLineEdit.Password)
        self.neues_passwort_edit.setPlaceholderText("leer lassen = Passwort unverändert")
        form.addRow("Neues Einstellungs-Passwort:", self.neues_passwort_edit)

        self.waage_port_edit = QLineEdit(config.waage_port)
        form.addRow("Waage Port (COM3 / /dev/ttyUSB0):", self.waage_port_edit)

        self.waage_baud_spin = QSpinBox()
        self.waage_baud_spin.setRange(300, 115200)
        self.waage_baud_spin.setValue(config.waage_baudrate)
        form.addRow("Waage Baudrate:", self.waage_baud_spin)

        self.drucker_backend_combo = QComboBox()
        self.drucker_backend_combo.addItems(["dummy", "win32raw", "windows_text", "cups", "file", "network"])
        self.drucker_backend_combo.setCurrentText(config.drucker_backend)
        form.addRow("Drucker-Backend:", self.drucker_backend_combo)
        form.addRow(QLabel(
            "\"windows_text\" druckt als reinen Text auf JEDEM normal\n"
            "installierten Windows-Drucker (z.B. eurem Netzwerkdrucker) -\n"
            "praktisch zum Testen ohne ESC/POS-fähigen Bondrucker."
        ))

        self.drucker_name_edit = QLineEdit(config.drucker_windows_name or "")
        form.addRow("Windows-Druckername:", self.drucker_name_edit)

        self.drucker_cups_edit = QLineEdit(config.drucker_cups_name or "")
        form.addRow("CUPS-Warteschlange (Linux, 'lpstat -p'):", self.drucker_cups_edit)

        self.drucker_datei_edit = QLineEdit(config.drucker_geraetedatei or "")
        form.addRow("Geraetedatei (Linux, Backend 'file', z.B. /dev/usb/lp0):", self.drucker_datei_edit)

        self.drucker_host_edit = QLineEdit(config.drucker_netzwerk_host or "")
        form.addRow("Netzwerkdrucker IP:", self.drucker_host_edit)

        self.bon_breite_spin = QSpinBox()
        self.bon_breite_spin.setRange(24, 64)
        self.bon_breite_spin.setValue(config.bon_zeichen_breite)
        form.addRow("Bonbreite (Zeichen):", self.bon_breite_spin)

        form.addRow(QLabel("--- Kapsel-Leergewichte (g) - bitte kalibrieren! ---"))
        self.kapsel_spins: dict[str, QDoubleSpinBox] = {}
        for groesse in KAPSELGROESSEN:
            spin = QDoubleSpinBox()
            spin.setDecimals(3)
            spin.setRange(0.0, 1.0)
            spin.setSuffix(" g")
            spin.setValue(config.kapsel_leergewichte_g.get(groesse, 0.0))
            form.addRow(f"Kapsel Größe {groesse}:", spin)
            self.kapsel_spins[groesse] = spin

        form.addRow(QLabel("--- Nennfüllmenge-Default je Kapselgröße (g) ---"))
        self.kapsel_nennfuellm_spins: dict[str, QDoubleSpinBox] = {}
        for groesse in KAPSELGROESSEN:
            spin = QDoubleSpinBox()
            spin.setDecimals(3)
            spin.setRange(0.0, 5.0)
            spin.setSuffix(" g")
            spin.setValue(config.kapsel_nennfuellmengen_g.get(groesse, 0.0))
            form.addRow(f"Kapsel Größe {groesse}:", spin)
            self.kapsel_nennfuellm_spins[groesse] = spin

        form.addRow(QLabel("--- Pulverbriefchen ---"))
        self.pulverbriefchen_spin = QDoubleSpinBox()
        self.pulverbriefchen_spin.setDecimals(3)
        self.pulverbriefchen_spin.setRange(0.0, 1.0)
        self.pulverbriefchen_spin.setSuffix(" g")
        self.pulverbriefchen_spin.setValue(config.pulverbriefchen_leergewicht_g)
        form.addRow("Leeres Pulverbriefchen:", self.pulverbriefchen_spin)
        form.addRow(QLabel(
            "Kein Herstellerstandard wie bei Kapseln - bitte selbst durch\n"
            "Wiegen leerer Briefchen ermitteln!"
        ))

        form.addRow(QLabel("--- Grafische Vorschau ---"))
        self.vorschau_sperren_check = QCheckBox("Grafische Vorschau sperren")
        self.vorschau_sperren_check.setChecked(config.vorschau_gesperrt)
        form.addRow(self.vorschau_sperren_check)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Speichern")
        cancel_btn = QPushButton("Abbrechen")
        for knopf in (save_btn, cancel_btn):
            knopf.setMinimumHeight(44)
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        outer.addLayout(btn_row)

    def result_config(self) -> AppConfig:
        c = self.config
        c.schulname = self.schulname_edit.text()
        if self.neues_passwort_edit.text():
            c.einstellungen_passwort_hash = hash_passwort(self.neues_passwort_edit.text())
        c.stichprobenumfang = self.umfang_spin.value()
        c.test_modus = self.test_modus_check.isChecked()
        c.waage_modus = self.waage_modus_combo.currentText()
        c.waage_port = self.waage_port_edit.text()
        c.waage_baudrate = self.waage_baud_spin.value()
        c.drucker_backend = self.drucker_backend_combo.currentText()
        c.drucker_windows_name = self.drucker_name_edit.text() or None
        c.drucker_cups_name = self.drucker_cups_edit.text() or None
        c.drucker_geraetedatei = self.drucker_datei_edit.text() or None
        c.drucker_netzwerk_host = self.drucker_host_edit.text() or None
        c.bon_zeichen_breite = self.bon_breite_spin.value()
        c.kapsel_leergewichte_g = {g: spin.value() for g, spin in self.kapsel_spins.items()}
        c.kapsel_nennfuellmengen_g = {g: spin.value() for g, spin in self.kapsel_nennfuellm_spins.items()}
        c.pulverbriefchen_leergewicht_g = self.pulverbriefchen_spin.value()
        c.vorschau_gesperrt = self.vorschau_sperren_check.isChecked()
        return c


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Füllmengenkontrolle - PTA Schule")
        self.resize(480, 700)

        self.config = load_config()
        self.balance = None
        self.net_values: list[float] = []
        self.laufende_nr = 1
        self.laufend = False
        self._kumulative_basis = 0.0

        self._build_ui()
        self._init_balance()
        self._apply_test_modus_visibility()

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll_balance)
        self.poll_timer.start(200)

    # ---------- UI Aufbau ----------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)

        left_widget = QWidget()
        layout = QVBoxLayout(left_widget)
        left_widget.setMaximumWidth(480)

        stammdaten_box = QGroupBox("Stammdaten der Stichprobe")
        form = QFormLayout(stammdaten_box)

        self.darreichungsform_combo = QComboBox()
        self.darreichungsform_combo.addItems(DARREICHUNGSFORMEN + ["Benutzerdefiniert"])
        self.darreichungsform_combo.currentTextChanged.connect(self._on_darreichungsform_changed)
        form.addRow("Arzneiform (= ID):", self.darreichungsform_combo)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("frei wählbar, z.B. Übungsgruppe/Datum")
        form.addRow("Name:", self.name_edit)

        self.nr_spin = QSpinBox()
        self.nr_spin.setRange(1, 999999)
        self.nr_spin.setValue(self.laufende_nr)
        form.addRow("Nr.:", self.nr_spin)

        self.nennfuellm_spin = QDoubleSpinBox()
        self.nennfuellm_spin.setDecimals(3)
        self.nennfuellm_spin.setRange(0.001, 100.0)
        self.nennfuellm_spin.setSuffix(" g")
        self.nennfuellm_spin.setValue(self.config.nennfuellm_g)
        form.addRow("Nennfüllmenge:", self.nennfuellm_spin)

        self.tara_spin = QDoubleSpinBox()
        self.tara_spin.setDecimals(3)
        self.tara_spin.setRange(0.0, 100.0)
        self.tara_spin.setSuffix(" g")
        self.tara_spin.setEnabled(False)  # nur bei "Benutzerdefiniert" editierbar
        form.addRow("Tara (automatisch):", self.tara_spin)

        self.umfang_spin = QSpinBox()
        self.umfang_spin.setRange(2, 100)
        self.umfang_spin.setValue(self.config.stichprobenumfang)
        self.umfang_spin.valueChanged.connect(self._on_umfang_changed)
        form.addRow("Stichprobenumfang:", self.umfang_spin)

        self.methode_combo = QComboBox()
        self.methode_combo.addItems(METHODEN)
        form.addRow("Auswertungsmethode:", self.methode_combo)

        layout.addWidget(stammdaten_box)
        self.darreichungsform_combo.setCurrentText("Kapsel Größe 1")  # Default beim Start
        self._on_darreichungsform_changed(self.darreichungsform_combo.currentText())

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self._on_start)
        btn_row.addWidget(self.start_btn)

        self.finish_btn = QPushButton("Ende: Auswerten && Drucken")
        self.finish_btn.clicked.connect(self._on_finish)
        self.finish_btn.setEnabled(False)
        btn_row.addWidget(self.finish_btn)

        reset_btn = QPushButton("Zurücksetzen")
        reset_btn.clicked.connect(lambda: self._reset_sample(increment_nr=False))
        btn_row.addWidget(reset_btn)

        settings_btn = QPushButton("Einstellungen")
        settings_btn.clicked.connect(self._open_settings)
        btn_row.addWidget(settings_btn)

        layout.addLayout(btn_row)

        messung_box = QGroupBox("Messung")
        m_layout = QVBoxLayout(messung_box)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #b34700; font-weight: bold;")
        m_layout.addWidget(self.status_label)

        self.live_weight_label = QLabel("-- g")
        self.live_weight_label.setAlignment(Qt.AlignCenter)
        self.live_weight_label.setStyleSheet("font-size: 28pt; font-weight: bold;")
        m_layout.addWidget(self.live_weight_label)

        self.live_netto_label = QLabel("Netto (letzter Wert): -- g")
        self.live_netto_label.setAlignment(Qt.AlignCenter)
        self.live_netto_label.setStyleSheet("font-size: 14pt; color: #444;")
        m_layout.addWidget(self.live_netto_label)

        # Manuelle Eingabe - NUR im Testmodus sichtbar (siehe _apply_test_modus_visibility)
        self.manual_group = QWidget()
        manual_row = QHBoxLayout(self.manual_group)
        manual_row.setContentsMargins(0, 0, 0, 0)
        self.manual_edit = QLineEdit()
        self.manual_edit.setPlaceholderText("[TESTMODUS] Wert manuell eingeben (g)")
        manual_row.addWidget(self.manual_edit)
        manual_btn = QPushButton("Testwert übernehmen")
        manual_btn.clicked.connect(self._on_capture_manual_value)
        manual_row.addWidget(manual_btn)
        m_layout.addWidget(self.manual_group)

        self.values_list = QListWidget()
        m_layout.addWidget(self.values_list)

        self.progress_label = QLabel("0 / 0 Werte erfasst")
        m_layout.addWidget(self.progress_label)

        self.warn_label = QLabel("")
        self.warn_label.setWordWrap(True)
        self.warn_label.setStyleSheet("color: #a94442; font-weight: bold;")
        m_layout.addWidget(self.warn_label)

        layout.addWidget(messung_box)

        self.progress_label.setText(f"0 / {self.umfang_spin.value()} Werte erfasst")

        root_layout.addWidget(left_widget)

        preview_box = QGroupBox("Grafische Vorschau")
        preview_layout = QVBoxLayout(preview_box)
        self.live_preview = LivePreviewWidget()
        preview_layout.addWidget(self.live_preview)
        root_layout.addWidget(preview_box, 1)  # Stretch-Faktor 1: füllt den restlichen Platz

        self.live_preview.set_locked(self.config.vorschau_gesperrt)
        self._set_laufend(False)

    def _aktuelle_toleranzen(self) -> tuple[float, float]:
        """Liefert (T1%, T2%) für die aktuelle Darreichungsform und
        Nennfüllmenge nach Ph. Eur. Tabelle 2.9.5-1. Fällt für nicht in der
        Tabelle abgebildete Fälle (z.B. "Benutzerdefiniert") auf die in den
        Einstellungen konfigurierten Werte zurück."""
        darreichungsform = self.darreichungsform_combo.currentText()
        masse_mg = self.nennfuellm_spin.value() * 1000
        t1 = t1_prozent_tabelle_2_9_5(darreichungsform, masse_mg)
        if t1 is None:
            return self.config.toleranz_t1_prozent, self.config.toleranz_t2_prozent
        return t1, t1 * 2

    def _refresh_live_preview(self):
        ist_av = self.methode_combo.currentText() == METHODEN[1]
        t1, t2 = self._aktuelle_toleranzen()
        self.live_preview.update_preview(
            self.net_values,
            self.nennfuellm_spin.value(),
            ist_akzeptanzwert=ist_av,
            t1_pct=t1,
            t2_pct=t2,
        )

    def _set_laufend(self, laufend: bool):
        """Sperrt/entsperrt die Stammdaten-Felder und aktiviert/deaktiviert
        die Werteerfassung (manuell und automatisch)."""
        self.laufend = laufend
        for feld in (
            self.name_edit, self.nr_spin, self.nennfuellm_spin,
            self.darreichungsform_combo, self.umfang_spin, self.methode_combo,
        ):
            feld.setEnabled(not laufend)
        if laufend:
            self.tara_spin.setEnabled(False)  # während der Messung immer gesperrt
        else:
            self._on_darreichungsform_changed(self.darreichungsform_combo.currentText())

        self.manual_group.setEnabled(laufend)
        self.start_btn.setEnabled(not laufend)
        self._apply_test_modus_visibility()

    def _on_start(self):
        self.net_values = []
        self.values_list.clear()
        self.progress_label.setText(f"0 / {self.umfang_spin.value()} Werte erfasst")
        self.finish_btn.setEnabled(False)
        self.live_preview.clear()
        self.warn_label.setText("")
        self.live_netto_label.setText("Netto (letzter Wert): -- g")

        # Softwareseitige "virtuelle Tarierung": die Waage tariert nach
        # unseren Tests nicht zuverlässig selbst, obwohl additiv gewogen
        # wird (Kapseln bleiben liegen). Deshalb merken wir uns hier den
        # kumulierten Ausgangswert (0.0 = leere Waage bei Start) und bilden
        # bei jedem neuen Rohwert selbst die Differenz zur vorherigen Summe.
        self._kumulative_basis = 0.0

        # Alles verwerfen, was die Waage VOR dem Start-Klick schon gesendet
        # haben könnte (z.B. versehentliches Drücken von [Print] beim
        # Einrichten), damit die Stichprobe garantiert sauber beginnt.
        if self.balance is not None:
            self.balance.pop_new_values()

        self._set_laufend(True)

    def _on_darreichungsform_changed(self, text: str):
        if text == "Benutzerdefiniert":
            self.tara_spin.setEnabled(True)
        else:
            self.tara_spin.setEnabled(False)
            self.tara_spin.setValue(tara_fuer_darreichungsform(self.config, text))

        default_nennfuellm = nennfuellmenge_fuer_darreichungsform(self.config, text)
        if default_nennfuellm is not None:
            self.nennfuellm_spin.setValue(default_nennfuellm)

    def _on_umfang_changed(self, value: int):
        self.progress_label.setText(f"{len(self.net_values)} / {value} Werte erfasst")

    def _apply_test_modus_visibility(self):
        # Manuelle Eingabe nur, wenn wirklich der manuelle Modus aktiv ist -
        # im seriellen Modus IMMER ausgeblendet, auch wenn Testmodus an ist,
        # damit dort keine Interaktion mit dem Programm nötig/möglich ist.
        zeige_manuell = self.config.test_modus and self.config.waage_modus == "manuell"
        self.manual_group.setVisible(zeige_manuell)

        if self.config.waage_modus == "seriell":
            if isinstance(self.balance, BalanceReader):
                self.status_label.setStyleSheet("color: #1e7e34; font-weight: bold;")
                self.status_label.setText("● Serieller Modus")
            else:
                self.status_label.setStyleSheet("color: #b34700; font-weight: bold;")
                self.status_label.setText("● Serieller Modus (nicht verbunden)")
        elif self.config.test_modus:
            self.status_label.setStyleSheet("color: #b34700; font-weight: bold;")
            self.status_label.setText("● Manueller Modus (Testmodus)")
        else:
            self.status_label.setStyleSheet("color: #a94442; font-weight: bold;")
            self.status_label.setText("● Kein Modus aktiv")

    # ---------- Waage ----------
    def _init_balance(self):
        if self.balance is not None:
            try:
                self.balance.close()
            except Exception:
                pass

        if self.config.waage_modus == "seriell":
            try:
                bc = BalanceConfig(port=self.config.waage_port, baudrate=self.config.waage_baudrate)
                self.balance = BalanceReader(bc)
                self.balance.connect()
            except Exception as e:
                QMessageBox.warning(
                    self, "Waage",
                    f"Verbindung zur Waage fehlgeschlagen ({e}).",
                )
                self.balance = None
        elif self.config.test_modus:
            self.balance = ManualBalance()
        else:
            self.balance = None

    def _poll_balance(self):
        if self.balance is None:
            self.live_weight_label.setText("-- g")
            return

        val = self.balance.latest_value()
        self.live_weight_label.setText(f"{val:.4f} g (brutto)" if val is not None else "-- g")

        # Automatische Übernahme: jeder von der Waage per [Print]-Taste
        # gesendete stabile Wert wird ohne Klick im Programm erfasst -
        # aber nur, solange eine Messung tatsächlich gestartet ist.
        neue_werte = self.balance.pop_new_values()
        if not self.laufend:
            return
        for gross_value in neue_werte:
            self._process_new_gross_reading(gross_value)

    # ---------- Aktionen ----------
    def _on_capture_manual_value(self):
        if not self.config.test_modus or not self.laufend:
            return  # Sicherheitsnetz: sollte durch UI-Sichtbarkeit/-Sperre bereits verhindert sein
        text = self.manual_edit.text().replace(",", ".")
        try:
            value = float(text)
        except ValueError:
            QMessageBox.warning(self, "Ungültiger Wert", "Bitte eine gültige Zahl eingeben.")
            return
        self._process_new_gross_reading(value)
        self.manual_edit.clear()

    def _process_new_gross_reading(self, roh_wert: float):
        """Verarbeitet einen neuen (kumulativen) Bruttomesswert.

        Da die Waage sich nach unseren Tests NICHT zuverlässig selbst
        tariert (obwohl additiv gewogen wird - Kapseln bleiben liegen),
        übernimmt das Programm die Tarierung selbst: Nur die Differenz zum
        zuletzt gesehenen kumulierten Wert gilt als Gewicht der neu
        hinzugefügten Kapsel. Das verhindert insbesondere, dass ein
        doppelt gesendeter (unveränderter) Wert als zusätzliche Kapsel
        gezählt wird.
        """
        RAUSCH_SCHWELLE = 0.005  # g - kleinere Änderungen gelten als "keine neue Kapsel"

        delta = roh_wert - self._kumulative_basis

        if abs(delta) < RAUSCH_SCHWELLE:
            # Keine echte Änderung - z.B. doppelt gesendeter/unveränderter
            # Wert. NICHT als Kapsel werten, Basis bleibt unverändert.
            self.warn_label.setText(
                f"Hinweis: unveränderter Wert ({roh_wert:.3f} g) ignoriert - keine neue Kapsel erkannt."
            )
            return

        if delta < 0:
            # Gewicht ist gesunken - kann bei additiver Wägung nicht durch
            # eine neu hinzugefügte Kapsel entstehen. Vermutlich wurde etwas
            # von der Waage genommen oder es gab eine Störung.
            self.warn_label.setText(
                f"⚠ Gewicht um {abs(delta):.3f} g gesunken (Rohwert {roh_wert:.3f} g) - "
                "NICHT übernommen. Wurde etwas von der Waage entfernt?"
            )
            return  # Basis bewusst NICHT aktualisieren

        # Plausible Zunahme -> als neue Kapsel werten, Basis fortschreiben
        self._kumulative_basis = roh_wert
        netto = delta - self.tara_spin.value()

        nennfuellm = self.nennfuellm_spin.value()
        unplausibel = netto <= 0 or netto > nennfuellm * 3
        self._append_value(netto, unplausibel=unplausibel)

        if unplausibel:
            self.warn_label.setText(
                f"⚠ Wert Nr. {len(self.net_values)} unüblich ({netto:.3f} g netto) - bitte später prüfen."
            )
        else:
            self.warn_label.setText("")

    def _append_value(self, netto: float, unplausibel: bool = False):
        self.net_values.append(netto)
        praefix = "⚠ " if unplausibel else ""
        eintrag = f"{praefix}{len(self.net_values)}: {netto:.3f} g"
        self.values_list.insertItem(0, eintrag)  # neuester Wert immer zuoberst
        if unplausibel:
            self.values_list.item(0).setForeground(Qt.red)
        self.live_netto_label.setText(f"Netto (letzter Wert): {netto:.3f} g")
        umfang = self.umfang_spin.value()
        self.progress_label.setText(f"{len(self.net_values)} / {umfang} Werte erfasst")
        self.finish_btn.setEnabled(len(self.net_values) >= 2)
        self._refresh_live_preview()

        if len(self.net_values) >= umfang:
            # Stichprobenumfang erreicht -> automatisch auswerten & drucken,
            # ohne dass "Ende" extra geklickt werden muss.
            self._on_finish()

    def _on_finish(self):
        if len(self.net_values) < 2:
            QMessageBox.warning(self, "Zu wenig Werte", "Mindestens 2 Werte werden für die Auswertung benötigt.")
            return

        proben_id = self.darreichungsform_combo.currentText()  # Arzneiform dient als ID
        methode = self.methode_combo.currentText()
        ist_akzeptanzwert = methode == METHODEN[1]

        try:
            if ist_akzeptanzwert:
                result = compute_acceptance_value(self.net_values, self.nennfuellm_spin.value())
                text = build_receipt_text_av(
                    kopfzeile=self.config.schulname,
                    proben_id=proben_id,
                    nr=self.nr_spin.value(),
                    nennfuellm_g=self.nennfuellm_spin.value(),
                    tara_g=self.tara_spin.value(),
                    net_values=self.net_values,
                    result=result,
                    width=self.config.bon_zeichen_breite,
                )
                passed = result.passed
            else:
                t1, t2 = self._aktuelle_toleranzen()
                result = compute_stats(
                    self.net_values,
                    self.nennfuellm_spin.value(),
                    t1_pct=t1,
                    t2_pct=t2,
                )
                # Zusätzlich die Akzeptanzwert-Analyse berechnen, um sie auf
                # denselben Bon zu drucken (ersetzt die entfernten
                # redundanten Prozent-Grenzen bei den T-Werten). Schlägt das
                # aus irgendeinem Grund fehl, wird der Bon trotzdem ohne
                # diesen Zusatzblock gedruckt.
                try:
                    av_result = compute_acceptance_value(self.net_values, self.nennfuellm_spin.value())
                except Exception:
                    av_result = None
                text = build_receipt_text(
                    kopfzeile=self.config.schulname,
                    proben_id=proben_id,
                    nr=self.nr_spin.value(),
                    nennfuellm_g=self.nennfuellm_spin.value(),
                    tara_g=self.tara_spin.value(),
                    net_values=self.net_values,
                    stats=result,
                    width=self.config.bon_zeichen_breite,
                    av_result=av_result,
                )
                passed = result.passed
        except Exception as e:
            QMessageBox.critical(self, "Fehler bei der Berechnung", str(e))
            return

        # Drucken und grafische Anzeige laufen unabhängig voneinander los:
        # ein Druckfehler (z.B. noch kein Drucker angeschlossen) verhindert
        # nicht mehr die Anzeige des Diagramms und das Speichern.
        try:
            print_receipt(
                text,
                PrinterConfig(
                    backend=self.config.drucker_backend,
                    windows_printer_name=self.config.drucker_windows_name,
                    cups_printer_name=self.config.drucker_cups_name,
                    device_path=self.config.drucker_geraetedatei,
                    network_host=self.config.drucker_netzwerk_host,
                ),
            )
            druckfehler = None
        except Exception as e:
            druckfehler = str(e)

        if ist_akzeptanzwert:
            self._chart_dialog = show_acceptance_value_chart(
                self.net_values, result, self.nennfuellm_spin.value(),
                proben_id, self.nr_spin.value(), parent=self,
            )
        else:
            self._chart_dialog = show_mass_variation_chart(
                self.net_values, result, self.nennfuellm_spin.value(),
                proben_id, self.nr_spin.value(), parent=self,
            )

        save_sample(
            datenbank_pfad_aufloesen(self.config.datenbank_pfad),
            proben_id,
            self.nr_spin.value(),
            self.nennfuellm_spin.value(),
            self.tara_spin.value(),
            self.net_values,
            result,
            methode=methode,
            name=self.name_edit.text(),
        )

        if druckfehler:
            QMessageBox.warning(
                self, "Druckfehler",
                f"Der Bon konnte nicht gedruckt werden:\n{druckfehler}\n\n"
                "Die Auswertung wurde trotzdem berechnet, angezeigt und gespeichert.",
            )

        self._reset_sample(increment_nr=True)

    def _reset_sample(self, increment_nr: bool = False):
        self.net_values = []
        self.values_list.clear()
        self.progress_label.setText(f"0 / {self.umfang_spin.value()} Werte erfasst")
        self.finish_btn.setEnabled(False)
        self.live_preview.clear()
        self.warn_label.setText("")
        self.live_netto_label.setText("Netto (letzter Wert): -- g")
        self._kumulative_basis = 0.0
        self._set_laufend(False)
        if increment_nr:
            self.nr_spin.setValue(self.nr_spin.value() + 1)

    def _passwort_festlegen(self) -> bool:
        """Fragt zweimal nach einem neuen Passwort und speichert dessen Hash."""
        text = "Es ist noch kein Passwort für die Einstellungen gesetzt.\nNeues Lehrkraft-Passwort (mind. 4 Zeichen):"
        pw1, ok = QInputDialog.getText(self, "Passwort festlegen", text, QLineEdit.Password)
        if not ok:
            return False
        if len(pw1) < 4:
            QMessageBox.warning(self, "Zu kurz", "Das Passwort muss mindestens 4 Zeichen lang sein.")
            return False
        pw2, ok = QInputDialog.getText(self, "Passwort festlegen", "Passwort wiederholen:", QLineEdit.Password)
        if not ok:
            return False
        if pw1 != pw2:
            QMessageBox.warning(self, "Nicht identisch", "Die beiden Eingaben stimmen nicht überein.")
            return False
        self.config.einstellungen_passwort_hash = hash_passwort(pw1)
        if not self._speichere_config():
            # Ohne dauerhaft gespeichertes Passwort keine Einstellungen öffnen.
            self.config.einstellungen_passwort_hash = ""
            return False
        return True

    def _speichere_config(self) -> bool:
        """Speichert config.json; meldet einen Fehler (z.B. fehlende
        Schreibrechte im Schüler-Konto) statt abzustürzen."""
        try:
            save_config(self.config)
            return True
        except OSError as e:
            QMessageBox.warning(
                self, "Nicht gespeichert",
                "Die Einstellungen konnten nicht gespeichert werden (in diesem "
                "Benutzerkonto fehlen die Schreibrechte). Dauerhaft ändern kann "
                "man sie nur im Lehrkraft-Konto.\n\n" + str(e),
            )
            return False

    def _open_settings(self):
        if not self.config.einstellungen_passwort_hash:
            # Erststart bzw. noch kein Passwort: jetzt eines festlegen.
            if not self._passwort_festlegen():
                return
        else:
            passwort, ok = QInputDialog.getText(
                self, "Einstellungen geschützt",
                "Bitte Lehrkraft-Passwort eingeben:",
                QLineEdit.Password,
            )
            if not ok:
                return
            if not pruefe_passwort(passwort, self.config.einstellungen_passwort_hash):
                QMessageBox.warning(self, "Falsches Passwort", "Das eingegebene Passwort ist nicht korrekt.")
                return

        dlg = SettingsDialog(self.config, self)
        if dlg.exec() == QDialog.Accepted:
            self.config = dlg.result_config()
            self._speichere_config()
            self.umfang_spin.setValue(self.config.stichprobenumfang)
            self._on_darreichungsform_changed(self.darreichungsform_combo.currentText())
            self._init_balance()
            self._apply_test_modus_visibility()
            self.live_preview.set_locked(self.config.vorschau_gesperrt)
            self._refresh_live_preview()
            self.progress_label.setText(f"{len(self.net_values)} / {self.umfang_spin.value()} Werte erfasst")

    def keyPressEvent(self, event):
        # F11 schaltet Vollbild um, Escape beendet Vollbild (falls aktiv) -
        # praktischer Fluchtweg z.B. für Einrichtung/Wartung.
        if event.key() == Qt.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        elif event.key() == Qt.Key_Escape and self.isFullScreen():
            self.showNormal()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if self.balance:
            try:
                self.balance.close()
            except Exception:
                pass
        super().closeEvent(event)


def main():
    app = QApplication([])
    window = MainWindow()
    window.showFullScreen()
    app.exec()


if __name__ == "__main__":
    main()
