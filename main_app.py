# -*- coding: utf-8 -*-
"""
main_app.py  –  IOOC Production Allocation System
"""

import sys, os
import pandas as pd

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QLineEdit, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QMessageBox, QFileDialog, QAction, QFrame, QScrollArea,
    QFormLayout, QTabWidget, QTabBar, QStackedWidget,
    QDialog, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui  import QFont, QColor, QPalette

import db_manager as db
from allocation_engine        import compute_allocation, save_allocation
from create_production_report import (
    create_well_production_report, create_test_report,
    create_field_production_report, create_reservoir_production_report,
)


# ─────────────────────────────────────────────────────────────────────────────
# Styles
# ─────────────────────────────────────────────────────────────────────────────
BTN_SAVE  = ("QPushButton{background:#2e7d32;color:white;font-weight:bold;"
             "padding:6px 16px;border-radius:4px;}"
             "QPushButton:hover{background:#388e3c;}")
BTN_RUN   = ("QPushButton{background:#1565c0;color:white;font-weight:bold;"
             "padding:6px 16px;border-radius:4px;}"
             "QPushButton:hover{background:#1976d2;}")
BTN_PDF   = ("QPushButton{background:#6a1b9a;color:white;font-weight:bold;"
             "padding:6px 16px;border-radius:4px;}"
             "QPushButton:hover{background:#7b1fa2;}")
BTN_WARN  = ("QPushButton{background:#e65100;color:white;font-weight:bold;"
             "padding:6px 14px;border-radius:4px;}"
             "QPushButton:hover{background:#f4511e;}")
BTN_DEL   = ("QPushButton{background:#b71c1c;color:white;font-weight:bold;"
             "padding:6px 14px;border-radius:4px;}"
             "QPushButton:hover{background:#c62828;}")
BTN_PLAIN = "padding:5px 12px;border-radius:4px;border:1px solid #bdbdbd;"

# Fix for combobox drop-down items turning white on hover (Fusion palette override)
_CB_STYLE = ("QComboBox QAbstractItemView {"
             "  color: black;"
             "  background: white;"
             "  selection-color: black;"
             "  selection-background-color: #bbdefb;"   # light blue highlight
             "}")

TEST_FIELDS = [
    ("Test Date",         "Test_Date"),
    ("Oil Rate (STB/D)",  "oil_rate_t"),
    ("Test Choke (/64)",  "choke_t"),
    ("Test WHP (PSIG)",   "WHP_t"),
    ("Test MFP (PSIG)",   "MFP_t"),
    ("BHP (PSIG)",        "BHP"),
    ("Sep. Press (PSIG)", "S_P"),
    ("Sep. Temp (°F)",    "S_T"),
    ("Sep. GOR (SCF/BBL)","S_GOR"),
    ("Lift Gas Press.",   "LGAS_P"),
    ("Lift Gas Rate",     "LGAS_rate"),
    ("API",               "API"),
    ("Test BS&W (%)",     "BSW_t"),
    ("Oper. BS&W (%)",    "BSW_p"),
    ("Prod. Hour",        "prod_hour"),
]

REPORT_TYPES = [
    "Production Report of Wells",
    "Test Report",
    "Production Report of Fields",
    "Production Report of Reservoirs",
]


# ─────────────────────────────────────────────────────────────────────────────
# PersianDateWidget  – single reusable date selector
# ─────────────────────────────────────────────────────────────────────────────
class PersianDateWidget(QWidget):
    """
    Three linked QComboBox widgets — year / month / day — that together
    form a validated Persian (Solar Hijri) date picker.

        year  : 1330 – 1430   (QComboBox, no free typing)
        month : 01 – 12       (QComboBox, no free typing)
        day   : 01 – 29/30/31 (QComboBox, refreshes automatically when
                                month changes so invalid days are impossible)

    Display format  :  YYYY / MM / DD   (read-only label separators)
    get_display()   →  "1404/06/15"
    get_yyyymm()    →  "140406"          (for prod_date DB keys)
    get_yyyymmdd()  →  "14040615"        (for Test_Date fields)
    set_date(s)     accepts YYYYMMDD, YYYYMM, YYYY/MM/DD, or YYYY/MM
    """

    # Days in each Persian month (non-leap year 12 = 29 days)
    _MONTH_DAYS = {**{m: 31 for m in range(1, 7)},
                   **{m: 30 for m in range(7, 12)},
                   12: 29}

    def __init__(self, parent=None):
        super().__init__(parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(1)

        # ── year ──────────────────────────────────────────────────────
        self.year_cb = QComboBox()
        self.year_cb.addItems([str(y) for y in range(1330, 1431)])
        self.year_cb.setCurrentText("1404")
        self.year_cb.setMinimumWidth(62)
        self.year_cb.setMaximumWidth(72)
        self.year_cb.setMaxVisibleItems(10)   # show 10, scroll for the rest

        # ── month ─────────────────────────────────────────────────────
        self.month_cb = QComboBox()
        self.month_cb.addItems([f"{m:02d}" for m in range(1, 13)])
        self.month_cb.setCurrentText("06")
        self.month_cb.setMaximumWidth(46)

        # ── day ───────────────────────────────────────────────────────
        self.day_cb = QComboBox()
        self.day_cb.setMaximumWidth(46)
        self._refresh_days(keep="01")

        # ── layout ────────────────────────────────────────────────────
        for widget in (self.year_cb, QLabel("/"),
                       self.month_cb, QLabel("/"),
                       self.day_cb):
            h.addWidget(widget)

        self.month_cb.currentIndexChanged.connect(
            lambda: self._refresh_days(keep=self.day_cb.currentText()))

    # ── internal ──────────────────────────────────────────────────────
    def _refresh_days(self, keep="01"):
        try:
            m = int(self.month_cb.currentText())
        except ValueError:
            m = 6
        max_day = self._MONTH_DAYS.get(m, 30)
        self.day_cb.blockSignals(True)
        self.day_cb.clear()
        self.day_cb.addItems([f"{d:02d}" for d in range(1, max_day + 1)])
        # restore previous day if still valid; else clamp to last valid day
        try:
            d = int(keep)
        except (ValueError, TypeError):
            d = 1
        self.day_cb.setCurrentText(f"{min(d, max_day):02d}")
        self.day_cb.blockSignals(False)

    # ── public API ────────────────────────────────────────────────────
    def get_display(self) -> str:
        """'1404/06/15'"""
        return (f"{self.year_cb.currentText()}/"
                f"{self.month_cb.currentText()}/"
                f"{self.day_cb.currentText()}")

    def get_yyyymm(self) -> str:
        """'140406'  — used as the prod_date DB key"""
        return f"{self.year_cb.currentText()}{self.month_cb.currentText()}"

    def get_yyyymmdd(self) -> str:
        """'14040615'  — used for Test_Date fields"""
        return (f"{self.year_cb.currentText()}"
                f"{self.month_cb.currentText()}"
                f"{self.day_cb.currentText()}")

    def set_date(self, value):
        """
        Accept any of:  14040615  |  140406  |  1404/06/15  |  1404/06
        Floats (e.g. 14040615.0) are handled automatically.
        """
        if value is None: return
        try:
            s = str(int(float(value)))    # handles 14040615.0 → '14040615'
        except (ValueError, TypeError):
            s = str(value).replace("/", "").strip()
        if len(s) < 4:
            return
        # year
        self.year_cb.setCurrentText(s[:4])
        # month
        if len(s) >= 6:
            self.month_cb.setCurrentText(s[4:6])
            self._refresh_days(keep=s[6:8] if len(s) >= 8 else "01")
        # day
        if len(s) >= 8:
            self.day_cb.setCurrentText(s[6:8])


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _sep():
    f = QFrame(); f.setFrameShape(QFrame.HLine)
    f.setStyleSheet("color:#cccccc;"); return f


def _get_field_val(widget):
    """Unified getter for QLineEdit or PersianDateWidget."""
    if isinstance(widget, PersianDateWidget):
        return widget.get_yyyymmdd()        # store YYYYMMDD in test_records
    return widget.text().strip()


def _set_field_val(widget, val):
    """Unified setter for QLineEdit or PersianDateWidget."""
    if isinstance(widget, PersianDateWidget):
        widget.set_date(val)
    else:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            widget.setText("")
        else:
            widget.setText(str(val))


# ─────────────────────────────────────────────────────────────────────────────
# Background worker
# ─────────────────────────────────────────────────────────────────────────────
class AllocWorker(QThread):
    done  = pyqtSignal(object, object, str, str, str)
    error = pyqtSignal(str)

    def __init__(self, field_code, prod_date):
        super().__init__()
        self.fc = field_code
        self.pd = prod_date

    def run(self):
        try:
            self.done.emit(*compute_allocation(self.fc, self.pd))
        except Exception as e:
            self.error.emit(str(e))


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — Test Data Entry
# ═════════════════════════════════════════════════════════════════════════════
class TestDataTab(QWidget):
    def __init__(self):
        super().__init__()
        self._field_code = None
        self._wells      = []
        self._well_idx   = 0
        self._build()

    # ── build ─────────────────────────────────────────────────────────────────
    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(5); root.setContentsMargins(8, 8, 8, 8)

        # top controls: prod month + well selector
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("<b>Prod. Month:</b>"))
        self.date_w = PersianDateWidget()
        ctrl.addWidget(self.date_w)

        ctrl.addSpacing(16)
        ctrl.addWidget(QLabel("<b>Well:</b>"))
        self.well_cb = QComboBox(); self.well_cb.setMinimumWidth(170)
        ctrl.addWidget(self.well_cb)

        self.load_btn = QPushButton("Load"); self.load_btn.setStyleSheet(BTN_PLAIN)
        ctrl.addWidget(self.load_btn); ctrl.addStretch()
        root.addLayout(ctrl); root.addWidget(_sep())

        # title
        ttl = QLabel("Last Test and Production Data")
        ttl.setAlignment(Qt.AlignCenter)
        ttl.setFont(QFont("", 12, QFont.Bold))
        ttl.setStyleSheet("color:#b71c1c; margin:2px 0;")
        root.addWidget(ttl)

        # General data
        gen = QGroupBox("General Data")
        gg  = self._grid(); 
        self.f_field_no   = self._ro()
        self.f_field_code = self._ro()
        self.f_well_name  = self._ro()
        self.f_zone_code  = self._ro()
        self.f_platform   = self._ro()
        for col, (lb, w) in enumerate([("Field No.:", self.f_field_no),
                                        ("Field Code:", self.f_field_code),
                                        ("Platform:", self.f_platform)]):
            gg.addWidget(QLabel(lb), 0, col*2); gg.addWidget(w, 0, col*2+1)
        for col, (lb, w) in enumerate([("Well Name:", self.f_well_name),
                                        ("Zone Code:", self.f_zone_code)]):
            gg.addWidget(QLabel(lb), 1, col*2); gg.addWidget(w, 1, col*2+1)
        for c in range(6): gg.setColumnStretch(c, 1)
        gen.setLayout(gg); root.addWidget(gen)

        # 3 test columns — Test_Date uses PersianDateWidget, all others QLineEdit
        test_box = QGroupBox("Test Data")
        test_lay = QHBoxLayout(test_box); test_lay.setSpacing(4)
        self._test_widgets = []

        for n in range(3):
            col_w = QWidget(); col_l = QVBoxLayout(col_w)
            col_l.setSpacing(2); col_l.setContentsMargins(4, 2, 4, 2)

            hdr = QLabel(f"Test Data No. {n+1}")
            hdr.setAlignment(Qt.AlignCenter)
            hdr.setStyleSheet("font-weight:bold; color:#1565c0; font-size:11px;")
            col_l.addWidget(hdr)

            fields = {}
            for label, key in TEST_FIELDS:
                rw = QWidget(); rl = QHBoxLayout(rw)
                rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(3)
                lb = QLabel(f"{label}:"); lb.setMinimumWidth(128)

                if key == "Test_Date":
                    # ← Persian date picker instead of QLineEdit
                    widget = PersianDateWidget()
                else:
                    widget = QLineEdit(); widget.setMinimumHeight(21)

                rl.addWidget(lb); rl.addWidget(widget)
                col_l.addWidget(rw)
                fields[key] = widget

            self._test_widgets.append(fields)
            test_lay.addWidget(col_w)
            if n < 2:
                vl = QFrame(); vl.setFrameShape(QFrame.VLine)
                vl.setStyleSheet("color:#cccccc;"); test_lay.addWidget(vl)

        root.addWidget(test_box)

        # Operational data
        op = QGroupBox("Operational Data"); og = self._grid()
        self.f_status     = QLineEdit()
        self.f_oper_whp   = QLineEdit()
        self.f_tot_hours  = QLineEdit()
        self.f_oper_choke = QLineEdit()
        self.f_oper_mfp   = QLineEdit()
        self.f_rs_code    = QLineEdit()
        for col, (lb, w) in enumerate([("Well Status:",      self.f_status),
                                        ("Oper. WHP (PSIG):", self.f_oper_whp),
                                        ("Total Prod. Hour:", self.f_tot_hours)]):
            og.addWidget(QLabel(lb), 0, col*2); og.addWidget(w, 0, col*2+1)
        for col, (lb, w) in enumerate([("Oper. Choke (/64):", self.f_oper_choke),
                                        ("Oper. MFP (PSIG):",  self.f_oper_mfp),
                                        ("RS Code:",            self.f_rs_code)]):
            og.addWidget(QLabel(lb), 1, col*2); og.addWidget(w, 1, col*2+1)
        for c in range(6): og.setColumnStretch(c, 1)
        op.setLayout(og); root.addWidget(op)

        root.addWidget(_sep())

        # navigation bar
        nav = QHBoxLayout()
        self.well_lbl = QLabel("No field loaded")
        self.well_lbl.setStyleSheet("color:grey; font-style:italic;")
        nav.addWidget(self.well_lbl); nav.addStretch()
        self.prev_btn   = QPushButton("◀  Prev"); self.prev_btn.setStyleSheet(BTN_PLAIN)
        self.next_btn   = QPushButton("Next  ▶"); self.next_btn.setStyleSheet(BTN_PLAIN)
        self.save_btn   = QPushButton("Save to DB"); self.save_btn.setStyleSheet(BTN_SAVE)
        self.finish_btn = QPushButton("Finish")
        self.clear_btn  = QPushButton("Clear Tests")
        for b in (self.prev_btn, self.next_btn, self.save_btn,
                  self.finish_btn, self.clear_btn):
            nav.addWidget(b)
        root.addLayout(nav)

        # connections
        self.well_cb.currentIndexChanged.connect(self._on_well_changed)
        self.load_btn.clicked.connect(self._load_tests)
        self.prev_btn.clicked.connect(self._prev)
        self.next_btn.clicked.connect(self._next)
        self.save_btn.clicked.connect(self._save)
        self.finish_btn.clicked.connect(self._finish)
        self.clear_btn.clicked.connect(self._clear_tests)

    # ── helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def _grid():
        from PyQt5.QtWidgets import QGridLayout
        g = QGridLayout()
        g.setVerticalSpacing(4); g.setHorizontalSpacing(8)
        g.setContentsMargins(6, 4, 6, 4); return g

    @staticmethod
    def _ro():
        e = QLineEdit(); e.setReadOnly(True)
        e.setStyleSheet("background:#f5f5f5;"); return e

    # ── field / well loading ──────────────────────────────────────────────────
    def load_field(self, field_code, field_name):
        self._field_code = field_code
        self._wells      = db.get_well_list(field_code)
        self._well_idx   = 0
        self.f_field_code.setText(str(field_code))
        self.well_cb.blockSignals(True)
        self.well_cb.clear()
        for w in self._wells:
            self.well_cb.addItem(f"{w['WEL_NAM']}  ({w['Z_COD']})")
        self.well_cb.blockSignals(False)
        if self._wells:
            self._show_well()

    def _on_well_changed(self, idx):
        self._well_idx = idx; self._show_well()

    def _prev(self):
        if self._well_idx > 0:
            self._well_idx -= 1
            self.well_cb.setCurrentIndex(self._well_idx)

    def _next(self):
        if self._well_idx < len(self._wells) - 1:
            self._well_idx += 1
            self.well_cb.setCurrentIndex(self._well_idx)

    def _show_well(self):
        if not self._wells: return
        w = self._wells[self._well_idx]
        self.f_field_no.setText(str(w.get('F_NO') or ''))
        self.f_well_name.setText(str(w.get('WEL_NAM') or ''))
        self.f_zone_code.setText(str(w.get('Z_COD') or ''))
        self.f_platform.setText(str(w.get('PLTFO') or ''))

        td   = db.get_test_data(self._field_code)
        mask = (td['WEL_NAM'] == w['WEL_NAM']) & (td['Z_COD'] == w['Z_COD'])
        row  = td[mask].iloc[0] if mask.any() else None

        _set_field_val(self.f_status, w.get('STAT'))
        if row is not None:
            for f, k in ((self.f_oper_whp,   'WHP_t'),
                         (self.f_tot_hours,   'P_Hour'),
                         (self.f_oper_choke,  'choke_t'),
                         (self.f_oper_mfp,    'MFP_t'),
                         (self.f_rs_code,     'RS_Code')):
                _set_field_val(f, row.get(k))
        else:
            for f in (self.f_oper_whp, self.f_tot_hours,
                      self.f_oper_choke, self.f_oper_mfp, self.f_rs_code):
                f.clear()

        self._load_tests()
        tot = len(self._wells)
        self.well_lbl.setText(f"Well  {self._well_idx+1}  of  {tot}")
        self.prev_btn.setEnabled(self._well_idx > 0)
        self.next_btn.setEnabled(self._well_idx < tot - 1)

    def _load_tests(self):
        if not self._wells: return
        w    = self._wells[self._well_idx]
        recs = db.get_test_records(
            self._field_code, self.date_w.get_yyyymm(),
            w['WEL_NAM'], w['Z_COD'])
        for n, rec in enumerate(recs):
            for _, key in TEST_FIELDS:
                _set_field_val(self._test_widgets[n][key], rec.get(key))

    def _clear_tests(self):
        for col in self._test_widgets:
            for key, widget in col.items():
                if isinstance(widget, PersianDateWidget):
                    widget.set_date("14040101")
                else:
                    widget.clear()

    # ── save ──────────────────────────────────────────────────────────────────
    def _save(self):
        if not self._wells:
            QMessageBox.warning(self, "No Data", "Load a field first."); return
        w = self._wells[self._well_idx]
        prod_date = self.date_w.get_yyyymm()

        tests = [{key: _get_field_val(col[key]) for _, key in TEST_FIELDS}
                 for col in self._test_widgets]
        last = db.save_test_records(
            self._field_code, prod_date, w['WEL_NAM'], w['Z_COD'], tests)

        row_dict = {
            'Field_Code':  self._field_code,
            'WEL_NAM':     w['WEL_NAM'],
            'Z_COD':       w['Z_COD'],
            'RS_Code':     self.f_rs_code.text().strip(),
            'choke_t':     self.f_oper_choke.text().strip(),
            'WHP_t':       self.f_oper_whp.text().strip(),
            'MFP_t':       self.f_oper_mfp.text().strip(),
            'P_Hour':      self.f_tot_hours.text().strip(),
        }
        if last:
            for _, key in TEST_FIELDS:
                if key not in ('choke_t','WHP_t','MFP_t','prod_hour','BHP'):
                    row_dict[key] = last.get(key, '')
        db.save_test_row(row_dict, self._field_code)

        stat = self.f_status.text().strip()
        if stat:
            conn = db.get_connection()
            conn.execute(
                "UPDATE cum_table SET STAT=? WHERE WEL_NAM=? AND Z_COD=? AND Field_Code=?",
                (stat, w['WEL_NAM'], w['Z_COD'], self._field_code))
            conn.commit(); conn.close()

        self.well_lbl.setText(
            f"Well  {self._well_idx+1}  of  {len(self._wells)}  — saved ✓")

    def _finish(self):
        self._save()
        QMessageBox.information(self, "Done",
            "Data saved. Run the allocation from the Allocation tab.")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — Monthly Production
# ═════════════════════════════════════════════════════════════════════════════
class MonthlyProductionTab(QWidget):
    def __init__(self):
        super().__init__()
        self._fc = self._fn = self._dist = None
        self._build()

    def _build(self):
        ly = QVBoxLayout(self)
        ly.setSpacing(10); ly.setContentsMargins(20, 14, 20, 14)

        ttl = QLabel("Monthly Field Production")
        ttl.setAlignment(Qt.AlignCenter)
        ttl.setFont(QFont("", 12, QFont.Bold))
        ttl.setStyleSheet("color:#b71c1c;")
        ly.addWidget(ttl); ly.addWidget(_sep())

        dr = QHBoxLayout()
        dr.addWidget(QLabel("<b>Production Month:</b>"))
        self.date_w = PersianDateWidget()
        dr.addWidget(self.date_w)
        self.load_btn = QPushButton("Load Existing")
        self.load_btn.setStyleSheet(BTN_PLAIN)
        dr.addWidget(self.load_btn); dr.addStretch()
        ly.addLayout(dr)

        grp  = QGroupBox("Production Values")
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(10); form.setContentsMargins(20, 12, 20, 12)
        self.f_oil   = QLineEdit(); self.f_oil.setPlaceholderText("STB")
        self.f_gas   = QLineEdit(); self.f_gas.setPlaceholderText("MMSCF")
        self.f_water = QLineEdit(); self.f_water.setPlaceholderText("BBL")
        form.addRow("Oil Production (STB):",    self.f_oil)
        form.addRow("Gas Production (MMSCF):",  self.f_gas)
        form.addRow("Water Production (BBL):",  self.f_water)
        grp.setLayout(form); ly.addWidget(grp)

        br = QHBoxLayout()
        self.save_btn = QPushButton("Save to DB")
        self.save_btn.setStyleSheet(BTN_SAVE); self.save_btn.setMaximumWidth(160)
        br.addWidget(self.save_btn); br.addStretch()
        ly.addLayout(br)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color:grey; font-style:italic;")
        ly.addWidget(self.status_lbl); ly.addStretch()

        self.load_btn.clicked.connect(self._load)
        self.save_btn.clicked.connect(self._save)

    def load_field(self, fc, fn, dist):
        self._fc = fc; self._fn = fn; self._dist = dist
        self.status_lbl.setText(f"Field: {fn}  ({fc})")
        self._load()

    def _load(self):
        if not self._fc: return
        row = db.get_monthly_production(self._fc, self.date_w.get_yyyymm())
        if row is None:
            row = db.get_monthly_production(self._fc)
        if row:
            self.date_w.set_date(str(int(float(row.get('prod_date', 0)))))
            self.f_oil.setText(str(row.get('m_oil', '')))
            self.f_gas.setText(str(row.get('m_gas', '')))
            self.f_water.setText(str(row.get('m_water', '')))
            self.status_lbl.setText(
                f"Loaded for {self.date_w.get_display()[:7]}.")
        else:
            self.status_lbl.setText("No existing record — enter new data.")

    def _save(self):
        if not self._fc:
            QMessageBox.warning(self, "No Field", "Select a field first."); return
        try:
            db.save_monthly_production({
                'Field_Code': self._fc, 'Field_Name': self._fn,
                'District': self._dist, 'prod_date': self.date_w.get_yyyymm(),
                'm_oil': float(self.f_oil.text()),
                'm_gas': float(self.f_gas.text()),
                'm_water': float(self.f_water.text()),
            })
            self.status_lbl.setText(
                f"Saved: {self._fn} / {self.date_w.get_display()[:7]}.")
            QMessageBox.information(self, "Saved", "Monthly production saved.")
        except ValueError:
            QMessageBox.warning(self, "Input Error",
                                "Enter valid numbers for oil, gas, and water.")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — Allocation
# ═════════════════════════════════════════════════════════════════════════════
class AllocationTab(QWidget):
    def __init__(self):
        super().__init__()
        self._fc = None; self._result = {}
        self._build()

    def _build(self):
        ly = QVBoxLayout(self)
        ly.setSpacing(10); ly.setContentsMargins(16, 12, 16, 12)

        ttl = QLabel("Production Allocation")
        ttl.setAlignment(Qt.AlignCenter)
        ttl.setFont(QFont("", 12, QFont.Bold))
        ttl.setStyleSheet("color:#b71c1c;")
        ly.addWidget(ttl); ly.addWidget(_sep())

        tr = QHBoxLayout()
        tr.addWidget(QLabel("<b>Allocation Month:</b>"))
        self.date_w = PersianDateWidget()
        tr.addWidget(self.date_w); tr.addSpacing(20)
        self.run_btn = QPushButton("▶  Run Allocation")
        self.run_btn.setStyleSheet(BTN_RUN)
        tr.addWidget(self.run_btn); tr.addStretch()
        ly.addLayout(tr)

        rb = QGroupBox("Results Summary"); rl = QVBoxLayout()
        self.res_txt = QTextEdit(); self.res_txt.setReadOnly(True)
        self.res_txt.setFont(QFont("Courier New", 9))
        self.res_txt.setMinimumHeight(200)
        rl.addWidget(self.res_txt); rb.setLayout(rl); ly.addWidget(rb)

        sr = QHBoxLayout()
        self.save_btn = QPushButton("💾  Save to Production Table")
        self.save_btn.setStyleSheet(BTN_SAVE); self.save_btn.setEnabled(False)
        sr.addWidget(self.save_btn); sr.addStretch(); ly.addLayout(sr)

        self.status_lbl = QLabel("Select a month and click Run Allocation.")
        self.status_lbl.setStyleSheet("color:grey; font-style:italic;")
        ly.addWidget(self.status_lbl); ly.addStretch()

        self.run_btn.clicked.connect(self._run)
        self.save_btn.clicked.connect(self._save_to_db)

    def load_field(self, fc, fn):
        self._fc = fc; self._result = {}
        self.save_btn.setEnabled(False); self.res_txt.clear()
        self.status_lbl.setText(f"Ready: {fn}  ({fc})")
        self.status_lbl.setStyleSheet("color:grey; font-style:italic;")

    def _run(self):
        if not self._fc:
            QMessageBox.warning(self, "No Field", "Select a field first."); return
        self.run_btn.setEnabled(False); self.save_btn.setEnabled(False)
        self.status_lbl.setText("Running…")
        self.status_lbl.setStyleSheet("color:darkorange;")
        self._worker = AllocWorker(self._fc, self.date_w.get_yyyymm())
        self._worker.done.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_done(self, df, prod_data, district, field_name, formatted):
        self._result = dict(df=df, prod_data=prod_data, district=district,
                            field_name=field_name, formatted=formatted,
                            raw=self.date_w.get_yyyymm())
        active = int((df['prod_days'] > 0).sum())
        self.res_txt.setText(
            f"  Field      : {field_name}  ({district})\n"
            f"  Period     : {formatted}\n"
            f"  Wells      : {active} active / {len(df)} total\n\n"
            f"  ─── Monthly Production ────────────────────────\n"
            f"  Oil        : {df['m_oil'].sum():>15,.0f}  STB\n"
            f"  Gas        : {df['m_gas'].sum():>15,.2f}  MMSCF\n"
            f"  Water      : {df['m_water'].sum():>15,.0f}  BBL\n\n"
            f"  ─── Cumulative (after this month) ─────────────\n"
            f"  Oil        : {df['cum_oil'].sum():>15,.0f}  STB\n"
            f"  Gas        : {df['cum_gas'].sum():>15,.2f}  MMSCF\n"
            f"  Water      : {df['cum_water'].sum():>15,.0f}  BBL\n")
        self.status_lbl.setText(
            "Computed. Click 'Save to Production Table' to commit.")
        self.status_lbl.setStyleSheet("color:#1565c0; font-weight:bold;")
        self.run_btn.setEnabled(True); self.save_btn.setEnabled(True)

    def _on_error(self, msg):
        self.status_lbl.setText(f"Error: {msg}")
        self.status_lbl.setStyleSheet("color:red; font-weight:bold;")
        self.run_btn.setEnabled(True)
        QMessageBox.critical(self, "Allocation Error", msg)

    def _save_to_db(self):
        if not self._result: return
        r = self._result; raw = r['raw']
        exists = db.production_exists(self._fc, raw)
        msg = (f"Data for  {r['field_name']} / {r['formatted'][:7]}  "
               f"{'already exists — replace?' if exists else 'will be saved. Confirm?'}")
        if QMessageBox.question(self, "Confirm Save", msg,
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        save_allocation(r['df'], r['prod_data'], self._fc, raw,
                        r['formatted'], r['field_name'], r['district'])
        self.status_lbl.setText(
            f"Saved: {r['field_name']} / {r['formatted'][:7]}")
        self.status_lbl.setStyleSheet("color:green; font-weight:bold;")
        self.save_btn.setEnabled(False)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 4 — Database Viewer
# ═════════════════════════════════════════════════════════════════════════════
class DatabaseTab(QWidget):
    def __init__(self):
        super().__init__()
        self._fc = None; self._tbl = None; self._df = pd.DataFrame()
        self._build()

    def _build(self):
        ly = QVBoxLayout(self)
        ly.setSpacing(6); ly.setContentsMargins(8, 8, 8, 8)

        ttl = QLabel("Database Viewer")
        ttl.setAlignment(Qt.AlignCenter)
        ttl.setFont(QFont("", 12, QFont.Bold))
        ttl.setStyleSheet("color:#b71c1c;")
        ly.addWidget(ttl); ly.addWidget(_sep())

        br = QHBoxLayout()
        self.btn_test    = QPushButton("Test Table")
        self.btn_monthly = QPushButton("Monthly Production")
        self.btn_prod    = QPushButton("Production Table")
        for b in (self.btn_test, self.btn_monthly, self.btn_prod):
            b.setStyleSheet(BTN_PLAIN); b.setCheckable(True); br.addWidget(b)
        br.addStretch(); ly.addLayout(br)

        self.tbl = QTableWidget()
        self.tbl.setAlternatingRowColors(True)
        self.tbl.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        ly.addWidget(self.tbl)

        cr = QHBoxLayout()
        self.ref_btn  = QPushButton("🔄 Refresh");   self.ref_btn.setStyleSheet(BTN_PLAIN)
        self.add_btn  = QPushButton("➕ Add Row");   self.add_btn.setStyleSheet(BTN_WARN)
        self.edit_btn = QPushButton("✏️ Edit Row");  self.edit_btn.setStyleSheet(BTN_PLAIN)
        self.del_btn  = QPushButton("🗑 Delete Row"); self.del_btn.setStyleSheet(BTN_DEL)
        for b in (self.ref_btn, self.add_btn, self.edit_btn, self.del_btn):
            cr.addWidget(b)
        cr.addStretch(); ly.addLayout(cr)

        self.info_lbl = QLabel("")
        self.info_lbl.setStyleSheet("color:grey; font-style:italic;")
        ly.addWidget(self.info_lbl)

        self.btn_test.clicked.connect(   lambda: self._show('test_data',         'Test Table'))
        self.btn_monthly.clicked.connect(lambda: self._show('monthly_production', 'Monthly Production'))
        self.btn_prod.clicked.connect(   lambda: self._show('production',         'Production Table'))
        self.ref_btn.clicked.connect(self._refresh)
        self.del_btn.clicked.connect(self._delete)
        self.edit_btn.clicked.connect(self._edit)
        self.add_btn.clicked.connect(self._add)

    def load_field(self, fc):
        self._fc = fc
        if self._tbl: self._refresh()

    def _show(self, tbl, label):
        self._tbl = tbl
        for b, t in ((self.btn_test,'test_data'),(self.btn_monthly,'monthly_production'),
                     (self.btn_prod,'production')):
            b.setChecked(t == tbl)
        self._refresh(); self.info_lbl.setText(f"Showing: {label}")

    def _refresh(self):
        if not self._tbl: return
        self._df = db.get_table_df(self._tbl, self._fc)
        cols = self._df.columns.tolist()
        self.tbl.setRowCount(0); self.tbl.setColumnCount(len(cols))
        self.tbl.setHorizontalHeaderLabels(cols)
        for _, row in self._df.iterrows():
            ri = self.tbl.rowCount(); self.tbl.insertRow(ri)
            for ci, col in enumerate(cols):
                v = row[col]
                self.tbl.setItem(ri, ci, QTableWidgetItem(
                    '' if (v is None or (isinstance(v, float) and pd.isna(v)))
                    else str(v)))

    def _sel_id(self):
        if not self.tbl.selectedItems():
            QMessageBox.warning(self, "No Selection", "Select a row first."); return None
        ri = self.tbl.currentRow()
        if 'id' not in self._df.columns:
            QMessageBox.warning(self, "Error", "Table has no id column."); return None
        return self._df.iloc[ri]['id']

    def _delete(self):
        rid = self._sel_id()
        if rid is None: return
        if QMessageBox.question(
            self, "Confirm Delete",
            f"Delete row id={rid} from {self._tbl}?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            db.delete_table_row(self._tbl, rid)
            self._refresh(); self.info_lbl.setText(f"Deleted row id={rid}.")

    def _edit(self):
        rid = self._sel_id()
        if rid is None: return
        row = self._df.iloc[self.tbl.currentRow()].to_dict()
        dlg = _RowDialog(row, self)
        if dlg.exec_():
            for col, val in dlg.values().items():
                if col != 'id': db.update_table_row(self._tbl, rid, col, val)
            self._refresh(); self.info_lbl.setText(f"Updated row id={rid}.")

    def _add(self):
        if not self._tbl:
            QMessageBox.warning(self, "No Table", "Select a table first."); return
        template = {c: '' for c in self._df.columns if c != 'id'}
        dlg = _RowDialog(template, self, title="Add Row")
        if dlg.exec_():
            try:
                db.insert_table_row(self._tbl, dlg.values())
                self._refresh(); self.info_lbl.setText("New row added.")
            except Exception as e:
                QMessageBox.critical(self, "Insert Error", str(e))


class _RowDialog:
    """Simple key/value edit dialog."""
    def __init__(self, row_dict, parent, title="Edit Row"):
        self._dlg = QDialog(parent); self._dlg.setWindowTitle(title)
        self._dlg.setMinimumWidth(420); self._edits = {}
        ly = QVBoxLayout(self._dlg)
        sc = QScrollArea(); sc.setWidgetResizable(True)
        inn = QWidget(); frm = QFormLayout(inn)
        frm.setLabelAlignment(Qt.AlignRight)
        for k, v in row_dict.items():
            if k == 'id': continue
            le = QLineEdit('' if v is None else str(v))
            frm.addRow(f"{k}:", le); self._edits[k] = le
        sc.setWidget(inn); ly.addWidget(sc)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._dlg.accept)
        bb.rejected.connect(self._dlg.reject)
        ly.addWidget(bb)

    def exec_(self): return self._dlg.exec_()
    def values(self): return {k: le.text() for k, le in self._edits.items()}


# ═════════════════════════════════════════════════════════════════════════════
# TAB 5 — Reports
# ═════════════════════════════════════════════════════════════════════════════
class ReportTab(QWidget):
    def __init__(self):
        super().__init__()
        self._fc = self._fn = self._dist = None
        self._build()

    def _build(self):
        ly = QVBoxLayout(self)
        ly.setSpacing(10); ly.setContentsMargins(16, 12, 16, 12)

        ttl = QLabel("Report Generation")
        ttl.setAlignment(Qt.AlignCenter)
        ttl.setFont(QFont("", 12, QFont.Bold))
        ttl.setStyleSheet("color:#b71c1c;")
        ly.addWidget(ttl); ly.addWidget(_sep())

        grp  = QGroupBox("Report Options")
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(10); form.setContentsMargins(20, 12, 20, 12)
        self.date_w = PersianDateWidget()
        form.addRow("Report Month:", self.date_w)
        self.type_cb = QComboBox(); self.type_cb.addItems(REPORT_TYPES)
        form.addRow("Report Type:", self.type_cb)
        grp.setLayout(form); ly.addWidget(grp)

        gr = QHBoxLayout()
        self.gen_btn = QPushButton("📄  Generate Report")
        self.gen_btn.setStyleSheet(BTN_PDF)
        gr.addWidget(self.gen_btn); gr.addStretch(); ly.addLayout(gr)

        self.status_lbl = QLabel(
            "Select month and report type, then click Generate.")
        self.status_lbl.setStyleSheet("color:grey; font-style:italic;")
        ly.addWidget(self.status_lbl); ly.addStretch()
        self.gen_btn.clicked.connect(self._generate)

    def load_field(self, fc, fn, dist):
        self._fc = fc; self._fn = fn; self._dist = dist

    def _generate(self):
        if not self._fc:
            QMessageBox.warning(self, "No Field", "Select a field first."); return
        pd_key = self.date_w.get_yyyymm()
        fmt    = self.date_w.get_display()[:7]   # YYYY/MM
        rtype  = self.type_cb.currentText()
        try:
            if rtype == "Production Report of Wells":
                df = db.get_production(self._fc, pd_key)
                if df.empty:
                    raise ValueError(f"No production data for {self._fn}/{fmt}.")
                f = create_well_production_report(df, self._dist, self._fn, fmt)

            elif rtype == "Test Report":
                df = db.get_latest_tests(self._fc)
                if df.empty: raise ValueError("No test data found.")
                f = create_test_report(df, self._dist, self._fn, fmt)

            elif rtype == "Production Report of Fields":
                df = db.get_district_field_summary(self._dist, pd_key)
                if df.empty:
                    raise ValueError(f"No data for district {self._dist}/{fmt}.")
                f = create_field_production_report(df, self._dist, fmt)

            elif rtype == "Production Report of Reservoirs":
                df = db.get_reservoir_summary(self._fc, pd_key)
                if df.empty:
                    raise ValueError(f"No data for {self._fn}/{fmt}.")
                f = create_reservoir_production_report(df, self._dist, self._fn, fmt)

            self.status_lbl.setText(f"Saved: {f}")
            self.status_lbl.setStyleSheet("color:green; font-weight:bold;")
            QMessageBox.information(self, "Report Generated", f"Saved as:\n{f}")
        except Exception as e:
            self.status_lbl.setText(f"Error: {e}")
            self.status_lbl.setStyleSheet("color:red;")
            QMessageBox.critical(self, "Report Error", str(e))


# ═════════════════════════════════════════════════════════════════════════════
# Main Window
# ═════════════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IOOC – Production Allocation System")
        self.setMinimumSize(1100, 820)
        self._districts = {}
        self._build_menu(); self._build_ui()
        self._refresh_districts()
        self.statusBar().showMessage(
            "Ready.  Use  File → Import from Excel  on first run.")

    def _build_menu(self):
        mb = self.menuBar()
        fm = mb.addMenu("File")
        ia = QAction("Import from Excel…", self); ia.setShortcut("Ctrl+I")
        ia.triggered.connect(self._import); fm.addAction(ia)
        fm.addSeparator()
        ex = QAction("Exit", self); ex.setShortcut("Ctrl+Q")
        ex.triggered.connect(self.close); fm.addAction(ex)
        hm = mb.addMenu("Help")
        ab = QAction("About", self)
        ab.triggered.connect(lambda: QMessageBox.about(
            self, "About",
            "<b>IOOC Production Allocation System</b><br><br>"
            "Iranian Offshore Oil Company – Reservoir Engineering Dept."))
        hm.addAction(ab)

    def _build_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(0); root.setContentsMargins(0, 0, 0, 0)

        # ── Tab bar (no content here) ─────────────────────────────────
        from PyQt5.QtWidgets import QTabBar
        self.tab_bar = QTabBar()
        self.tab_bar.setDocumentMode(True)
        self.tab_bar.setExpanding(False)
        for label in ("📋  Test Data", "📊  Monthly Production",
                      "⚙️  Allocation", "🗄️  Database", "📄  Report"):
            self.tab_bar.addTab(label)
        self.tab_bar.setStyleSheet(
            "QTabBar::tab { padding: 7px 18px; font-size: 11px; }"
            "QTabBar::tab:selected { background:#e3f2fd; border-bottom: 3px solid #1565c0; }"
            "QTabBar::tab:hover:!selected { background:#f5f5f5; }")
        root.addWidget(self.tab_bar)

        # ── District / Field selectors — always visible below tab bar ─
        sel = QWidget()
        sel.setStyleSheet(
            "background:#e3f2fd; border-top:1px solid #90caf9;"
            "border-bottom:2px solid #90caf9;")
        sl = QHBoxLayout(sel)
        sl.setContentsMargins(12, 6, 12, 6); sl.setSpacing(10)

        sl.addWidget(self._tl("District:"))
        self.district_cb = QComboBox(); self.district_cb.setMinimumWidth(130)
        self.district_cb.setStyleSheet(_CB_STYLE)
        sl.addWidget(self.district_cb)

        sl.addWidget(self._tl("Field:"))
        self.field_cb = QComboBox(); self.field_cb.setMinimumWidth(200)
        self.field_cb.setStyleSheet(_CB_STYLE)
        sl.addWidget(self.field_cb)
        sl.addStretch()
        root.addWidget(sel)

        # ── Page stack ────────────────────────────────────────────────
        from PyQt5.QtWidgets import QStackedWidget
        self.stack = QStackedWidget()

        self.tab_test    = TestDataTab()
        self.tab_monthly = MonthlyProductionTab()
        self.tab_alloc   = AllocationTab()
        self.tab_db      = DatabaseTab()
        self.tab_report  = ReportTab()

        sc = QScrollArea(); sc.setWidgetResizable(True); sc.setWidget(self.tab_test)
        self.stack.addWidget(sc)
        self.stack.addWidget(self.tab_monthly)
        self.stack.addWidget(self.tab_alloc)
        self.stack.addWidget(self.tab_db)
        self.stack.addWidget(self.tab_report)
        root.addWidget(self.stack)

        self.tab_bar.currentChanged.connect(self.stack.setCurrentIndex)
        self.district_cb.currentIndexChanged.connect(self._on_district)
        self.field_cb.currentIndexChanged.connect(self._on_field)

    @staticmethod
    def _tl(text):
        l = QLabel(f"<b>{text}</b>")
        l.setStyleSheet("color:#0d47a1; background:transparent;"); return l

    def _refresh_districts(self):
        self._districts = db.get_districts_fields()
        self.district_cb.blockSignals(True)
        self.district_cb.clear()
        self.district_cb.addItems(self._districts.keys())
        self.district_cb.blockSignals(False)
        self._on_district()

    def _on_district(self):
        district = self.district_cb.currentText()
        fields   = self._districts.get(district, [])
        self.field_cb.blockSignals(True)
        self.field_cb.clear()
        for name, code in fields:
            self.field_cb.addItem(f"{name}  ({code})", (name, code, district))
        self.field_cb.blockSignals(False)
        self._on_field()

    def _on_field(self):
        data = self.field_cb.currentData()
        if not data: return
        name, code, district = data
        self.tab_test.load_field(code, name)
        self.tab_monthly.load_field(code, name, district)
        self.tab_alloc.load_field(code, name)
        self.tab_db.load_field(code)
        self.tab_report.load_field(code, name, district)
        self.statusBar().showMessage(
            f"Field: {name}  ({code})  |  District: {district}")

    def _import(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select folder containing Excel files")
        if not folder: return
        missing = [f for f in ["Test_Data_1.xlsx","Cum_Table.xlsx",
                                "Monthly_Data.xlsx","RS_Code.xlsx"]
                   if not os.path.exists(f"{folder}/{f}")]
        if missing:
            QMessageBox.warning(self, "Missing Files",
                "Files not found:\n" + "\n".join(f"  • {f}" for f in missing)); return
        try:
            self.statusBar().showMessage("Importing…")
            QApplication.processEvents()
            db.import_from_excel(folder)
            self._refresh_districts()
            self.statusBar().showMessage("Import complete.")
            QMessageBox.information(self, "Done", "Data imported successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    db.create_tables()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    pal = app.palette()
    pal.setColor(QPalette.Highlight,       QColor("#1565c0"))
    pal.setColor(QPalette.HighlightedText, QColor("white"))
    app.setPalette(pal)

    w = MainWindow(); w.show()
    sys.exit(app.exec_())