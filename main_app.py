# -*- coding: utf-8 -*-
"""
main_app.py  –  IOOC Production Allocation System
Each tab has its own independent District / Field selector.
"""

import sys, os
import pandas as pd

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QLineEdit, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QMessageBox, QFileDialog, QAction, QFrame, QScrollArea,
    QFormLayout, QTabWidget, QDialog, QDialogButtonBox, QSizePolicy
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
# Style constants
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

_CB_STYLE = ("QComboBox QAbstractItemView{"
             "color:black;background:white;"
             "selection-color:black;"
             "selection-background-color:#bbdefb;}")

_SEL_BG = ("background:#e3f2fd;"
           "border-bottom:2px solid #90caf9;")

TEST_FIELDS = [
    ("Test Date",          "Test_Date"),
    ("Oil Rate (STB/D)",   "oil_rate_t"),
    ("Test Choke (/64)",   "choke_t"),
    ("Test WHP (PSIG)",    "WHP_t"),
    ("Test MFP (PSIG)",    "MFP_t"),
    ("BHP (PSIG)",         "BHP"),
    ("Sep. Press (PSIG)",  "S_P"),
    ("Sep. Temp (°F)",     "S_T"),
    ("Sep. GOR (SCF/BBL)", "S_GOR"),
    ("Lift Gas Press.",    "LGAS_P"),
    ("Lift Gas Rate",      "LGAS_rate"),
    ("API",                "API"),
    ("Test BS&W (%)",      "BSW_t"),
    ("Oper. BS&W (%)",     "BSW_p"),
    ("Prod. Hour",         "prod_hour"),
]

REPORT_TYPES = [
    "Production Report of Wells",
    "Test Report",
    "Production Report of Fields",
    "Production Report of Reservoirs",
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _sep():
    f = QFrame(); f.setFrameShape(QFrame.HLine)
    f.setStyleSheet("color:#cccccc;"); return f

def _tab_title(text):
    """Bold centred title bar — sits above the selector in every tab."""
    w = QWidget()
    w.setStyleSheet("background:#fafafa; border-bottom:1px solid #e0e0e0;")
    h = QHBoxLayout(w); h.setContentsMargins(10, 8, 10, 8)
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setFont(QFont("", 12, QFont.Bold))
    lbl.setStyleSheet("color:#b71c1c; background:transparent;")
    h.addWidget(lbl)
    return w

def _bold(text):
    l = QLabel(text); l.setFont(QFont("", -1, QFont.Bold))
    l.setStyleSheet("color:#0d47a1;"); return l


# ─────────────────────────────────────────────────────────────────────────────
# Persian Date Widget
# ─────────────────────────────────────────────────────────────────────────────
class PersianDateWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        h = QHBoxLayout(self); h.setContentsMargins(0,0,0,0); h.setSpacing(4)
        self.year_cb = QComboBox()
        self.year_cb.addItems([str(y) for y in range(1330,1431)])
        self.year_cb.setCurrentText("1404")
        self.year_cb.setMaximumWidth(72)
        self.year_cb.setMaxVisibleItems(10)
        self.month_cb = QComboBox()
        self.month_cb.addItems([f"{m:02d}" for m in range(1,13)])
        self.month_cb.setCurrentText("06")
        self.month_cb.setMaximumWidth(55)
        h.addWidget(QLabel("Year:")); h.addWidget(self.year_cb)
        h.addWidget(QLabel("Month:")); h.addWidget(self.month_cb)

    def get_yyyymm(self): return f"{self.year_cb.currentText()}{self.month_cb.currentText()}"
    def get_display(self): return f"{self.year_cb.currentText()}/{self.month_cb.currentText()}"
    def set_date(self, s):
        s = str(s).replace("/","").strip()
        if len(s)>=6:
            self.year_cb.setCurrentText(s[:4])
            self.month_cb.setCurrentText(s[4:6])


# ─────────────────────────────────────────────────────────────────────────────
# FieldSelectorRow  – reusable, embeds into any tab
# ─────────────────────────────────────────────────────────────────────────────
class FieldSelectorRow(QWidget):
    """
    A self-contained District + Field dropdown bar.
    Emits field_changed(field_code, field_name, district) whenever
    the selection changes.
    """
    field_changed = pyqtSignal(int, str, str)   # code, name, district

    def __init__(self, parent=None):
        super().__init__(parent)
        self._districts = {}
        self._build()
        self.refresh()

    def _build(self):
        self.setStyleSheet(_SEL_BG)
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 7, 10, 7); h.setSpacing(10)

        h.addWidget(_bold("District:"))
        self.district_cb = QComboBox()
        self.district_cb.setMinimumWidth(130)
        self.district_cb.setStyleSheet(_CB_STYLE)
        h.addWidget(self.district_cb)

        h.addWidget(_bold("Field:"))
        self.field_cb = QComboBox()
        self.field_cb.setMinimumWidth(200)
        self.field_cb.setStyleSheet(_CB_STYLE)
        h.addWidget(self.field_cb)
        h.addStretch()

        self.district_cb.currentIndexChanged.connect(self._populate_fields)
        self.field_cb.currentIndexChanged.connect(self._emit)

    # ── public API ────────────────────────────────────────────────────
    def refresh(self):
        """Reload districts from DB; tries to keep the current selection."""
        prev_district = self.district_cb.currentText()
        self._districts = db.get_districts_fields()

        self.district_cb.blockSignals(True)
        self.district_cb.clear()
        self.district_cb.addItems(self._districts.keys())
        idx = self.district_cb.findText(prev_district)
        self.district_cb.setCurrentIndex(max(idx, 0))
        self.district_cb.blockSignals(False)
        self._populate_fields()

    def current_code(self):
        d = self.field_cb.currentData()
        return d[0] if d else None

    def current_name(self):
        d = self.field_cb.currentData()
        return d[1] if d else ""

    def current_district(self):
        d = self.field_cb.currentData()
        return d[2] if d else ""

    # ── internals ─────────────────────────────────────────────────────
    def _populate_fields(self):
        district = self.district_cb.currentText()
        fields   = self._districts.get(district, [])
        self.field_cb.blockSignals(True)
        self.field_cb.clear()
        for name, code in fields:
            self.field_cb.addItem(f"{name}  ({code})", (code, name, district))
        self.field_cb.blockSignals(False)
        self._emit()

    def _emit(self):
        d = self.field_cb.currentData()
        if d:
            self.field_changed.emit(d[0], d[1], d[2])   # code, name, district


# ─────────────────────────────────────────────────────────────────────────────
# Background worker
# ─────────────────────────────────────────────────────────────────────────────
class AllocWorker(QThread):
    done  = pyqtSignal(object, object, str, str, str)
    error = pyqtSignal(str)
    def __init__(self, field_code, prod_date):
        super().__init__(); self.fc=field_code; self.pd=prod_date
    def run(self):
        try: self.done.emit(*compute_allocation(self.fc, self.pd))
        except Exception as e: self.error.emit(str(e))


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — Test Data Entry
# ─────────────────────────────────────────────────────────────────────────────
class TestDataTab(QWidget):
    def __init__(self):
        super().__init__()
        self._field_code = None; self._wells = []; self._well_idx = 0
        self._build()

    def _build(self):
        root = QVBoxLayout(self); root.setSpacing(0); root.setContentsMargins(0,0,0,0)

        # ── title (topmost) ───────────────────────────────────────────
        root.addWidget(_tab_title("Last Test and Production Data"))

        # ── own selector ──────────────────────────────────────────────
        self.selector = FieldSelectorRow()
        self.selector.field_changed.connect(self._on_field)
        root.addWidget(self.selector)

        # ── scrollable body ───────────────────────────────────────────
        body_w = QWidget(); body_l = QVBoxLayout(body_w)
        body_l.setSpacing(5); body_l.setContentsMargins(8,8,8,8)

        # date + well controls
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("<b>Prod. Month:</b>"))
        self.date_w = PersianDateWidget(); ctrl.addWidget(self.date_w)
        ctrl.addSpacing(16)
        ctrl.addWidget(QLabel("<b>Well:</b>"))
        self.well_cb = QComboBox(); self.well_cb.setMinimumWidth(160)
        ctrl.addWidget(self.well_cb)
        self.load_btn = QPushButton("Load"); self.load_btn.setStyleSheet(BTN_PLAIN)
        ctrl.addWidget(self.load_btn); ctrl.addStretch()
        body_l.addLayout(ctrl)
        body_l.addWidget(_sep())

        # General data
        gen = QGroupBox("General Data"); gg = self._grid()
        self.f_field_no  = self._ro(); self.f_field_code= self._ro()
        self.f_well_name = self._ro(); self.f_zone_code = self._ro()
        self.f_platform  = self._ro()
        for c,(lb,w) in enumerate([("Field No.:",self.f_field_no),
                                    ("Field Code:",self.f_field_code),
                                    ("Platform:",self.f_platform)]):
            gg.addWidget(QLabel(lb),0,c*2); gg.addWidget(w,0,c*2+1)
        for c,(lb,w) in enumerate([("Well Name:",self.f_well_name),
                                    ("Zone Code:",self.f_zone_code)]):
            gg.addWidget(QLabel(lb),1,c*2); gg.addWidget(w,1,c*2+1)
        for c in range(6): gg.setColumnStretch(c,1)
        gen.setLayout(gg); body_l.addWidget(gen)

        # 3 test columns
        test_box = QGroupBox("Test Data"); tl = QHBoxLayout(test_box); tl.setSpacing(4)
        self._test_w = []
        for n in range(3):
            cw = QWidget(); cl = QVBoxLayout(cw); cl.setSpacing(2); cl.setContentsMargins(4,2,4,2)
            hdr = QLabel(f"Test Data No. {n+1}")
            hdr.setAlignment(Qt.AlignCenter)
            hdr.setStyleSheet("font-weight:bold;color:#1565c0;font-size:11px;")
            cl.addWidget(hdr)
            flds = {}
            for lbl,key in TEST_FIELDS:
                rw=QWidget(); rl=QHBoxLayout(rw); rl.setContentsMargins(0,0,0,0); rl.setSpacing(3)
                lb=QLabel(f"{lbl}:"); lb.setMinimumWidth(125)
                le=QLineEdit(); le.setMinimumHeight(21)
                rl.addWidget(lb); rl.addWidget(le); cl.addWidget(rw); flds[key]=le
            self._test_w.append(flds); tl.addWidget(cw)
            if n<2:
                vl=QFrame(); vl.setFrameShape(QFrame.VLine); vl.setStyleSheet("color:#cccccc;"); tl.addWidget(vl)
        body_l.addWidget(test_box)

        # Operational data
        op=QGroupBox("Operational Data"); og=self._grid()
        self.f_status=QLineEdit(); self.f_oper_whp=QLineEdit()
        self.f_tot_h=QLineEdit(); self.f_choke=QLineEdit()
        self.f_mfp=QLineEdit(); self.f_rs=QLineEdit()
        for c,(lb,w) in enumerate([("Well Status:",self.f_status),
                                    ("Oper. WHP (PSIG):",self.f_oper_whp),
                                    ("Total Prod. Hour:",self.f_tot_h)]):
            og.addWidget(QLabel(lb),0,c*2); og.addWidget(w,0,c*2+1)
        for c,(lb,w) in enumerate([("Oper. Choke (/64):",self.f_choke),
                                    ("Oper. MFP (PSIG):",self.f_mfp),
                                    ("RS Code:",self.f_rs)]):
            og.addWidget(QLabel(lb),1,c*2); og.addWidget(w,1,c*2+1)
        for c in range(6): og.setColumnStretch(c,1)
        op.setLayout(og); body_l.addWidget(op)
        body_l.addWidget(_sep())

        # Navigation bar
        nav = QHBoxLayout()
        self.well_lbl = QLabel("No field loaded")
        self.well_lbl.setStyleSheet("color:grey;font-style:italic;")
        nav.addWidget(self.well_lbl); nav.addStretch()
        self.prev_btn = QPushButton("◀  Prev"); self.prev_btn.setStyleSheet(BTN_PLAIN)
        self.next_btn = QPushButton("Next  ▶"); self.next_btn.setStyleSheet(BTN_PLAIN)
        self.save_btn = QPushButton("Save to DB"); self.save_btn.setStyleSheet(BTN_SAVE)
        self.finish_btn = QPushButton("Finish")
        self.clear_btn  = QPushButton("Clear Tests")
        for b in (self.prev_btn,self.next_btn,self.save_btn,self.finish_btn,self.clear_btn):
            nav.addWidget(b)
        body_l.addLayout(nav)

        sc = QScrollArea(); sc.setWidgetResizable(True); sc.setWidget(body_w)
        root.addWidget(sc)

        # connections
        self.well_cb.currentIndexChanged.connect(self._on_well_changed)
        self.load_btn.clicked.connect(self._load_tests)
        self.prev_btn.clicked.connect(self._prev)
        self.next_btn.clicked.connect(self._next)
        self.save_btn.clicked.connect(self._save)
        self.finish_btn.clicked.connect(self._finish)
        self.clear_btn.clicked.connect(self._clear_tests)

    # helpers
    @staticmethod
    def _grid():
        from PyQt5.QtWidgets import QGridLayout
        g=QGridLayout(); g.setVerticalSpacing(4); g.setHorizontalSpacing(8)
        g.setContentsMargins(6,4,6,4); return g
    @staticmethod
    def _ro():
        e=QLineEdit(); e.setReadOnly(True); e.setStyleSheet("background:#f5f5f5;"); return e

    def _on_field(self, code, name, district):
        self._field_code=code
        self._wells=db.get_well_list(code)
        self._well_idx=0
        self.f_field_code.setText(str(code))
        self.well_cb.blockSignals(True)
        self.well_cb.clear()
        for w in self._wells:
            self.well_cb.addItem(f"{w['WEL_NAM']}  ({w['Z_COD']})")
        self.well_cb.blockSignals(False)
        if self._wells: self._show_well()

    def _on_well_changed(self, idx): self._well_idx=idx; self._show_well()
    def _prev(self):
        if self._well_idx>0: self._well_idx-=1; self.well_cb.setCurrentIndex(self._well_idx)
    def _next(self):
        if self._well_idx<len(self._wells)-1: self._well_idx+=1; self.well_cb.setCurrentIndex(self._well_idx)

    def _show_well(self):
        if not self._wells: return
        w=self._wells[self._well_idx]
        self.f_field_no.setText(str(w.get('F_NO') or ''))
        self.f_well_name.setText(str(w.get('WEL_NAM') or ''))
        self.f_zone_code.setText(str(w.get('Z_COD') or ''))
        self.f_platform.setText(str(w.get('PLTFO') or ''))
        td=db.get_test_data(self._field_code)
        mask=(td['WEL_NAM']==w['WEL_NAM'])&(td['Z_COD']==w['Z_COD'])
        row=td[mask].iloc[0] if mask.any() else None
        def _fill(le,val): le.setText('' if (val is None or (isinstance(val,float) and pd.isna(val))) else str(val))
        _fill(self.f_status,w.get('STAT'))
        if row is not None:
            _fill(self.f_oper_whp,row.get('WHP_t')); _fill(self.f_tot_h,row.get('P_Hour'))
            _fill(self.f_choke,row.get('choke_t')); _fill(self.f_mfp,row.get('MFP_t'))
            _fill(self.f_rs,row.get('RS_Code'))
        else:
            for f in (self.f_oper_whp,self.f_tot_h,self.f_choke,self.f_mfp,self.f_rs): f.clear()
        self._load_tests()
        tot=len(self._wells)
        self.well_lbl.setText(f"Well  {self._well_idx+1}  of  {tot}")
        self.prev_btn.setEnabled(self._well_idx>0)
        self.next_btn.setEnabled(self._well_idx<tot-1)

    def _load_tests(self):
        if not self._wells: return
        w=self._wells[self._well_idx]
        recs=db.get_test_records(self._field_code,self.date_w.get_yyyymm(),w['WEL_NAM'],w['Z_COD'])
        for n,rec in enumerate(recs):
            for _,key in TEST_FIELDS:
                val=rec.get(key,'')
                self._test_w[n][key].setText('' if (val is None or val=='' or (isinstance(val,float) and pd.isna(val))) else str(val))

    def _clear_tests(self):
        for col in self._test_w:
            for le in col.values(): le.clear()

    def _save(self):
        if not self._wells: QMessageBox.warning(self,"No Data","Load a field first."); return
        w=self._wells[self._well_idx]
        prod_date=self.date_w.get_yyyymm()
        tests=[{key:col[key].text().strip() for _,key in TEST_FIELDS} for col in self._test_w]
        last=db.save_test_records(self._field_code,prod_date,w['WEL_NAM'],w['Z_COD'],tests)
        row_dict={'Field_Code':self._field_code,'WEL_NAM':w['WEL_NAM'],'Z_COD':w['Z_COD'],
                  'RS_Code':self.f_rs.text().strip(),'choke_t':self.f_choke.text().strip(),
                  'WHP_t':self.f_oper_whp.text().strip(),'MFP_t':self.f_mfp.text().strip(),
                  'P_Hour':self.f_tot_h.text().strip()}
        if last:
            for _,key in TEST_FIELDS:
                if key not in ('choke_t','WHP_t','MFP_t','prod_hour','BHP'): row_dict[key]=last.get(key,'')
            row_dict['Test_Date']=last.get('Test_Date','')
        stat=self.f_status.text().strip()
        if stat:
            conn=db.get_connection()
            conn.execute("UPDATE cum_table SET STAT=? WHERE WEL_NAM=? AND Z_COD=? AND Field_Code=?",
                         (stat,w['WEL_NAM'],w['Z_COD'],self._field_code)); conn.commit(); conn.close()
        db.save_test_row(row_dict,self._field_code)
        self.well_lbl.setText(f"Well  {self._well_idx+1}  of  {len(self._wells)}  — saved ✓")

    def _finish(self):
        self._save()
        QMessageBox.information(self,"Done","Data saved. You can now run allocation.")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — Monthly Production
# ─────────────────────────────────────────────────────────────────────────────
class MonthlyProductionTab(QWidget):
    def __init__(self):
        super().__init__()
        self._field_code=None; self._field_name=""; self._district=""
        self._build()

    def _build(self):
        root=QVBoxLayout(self); root.setSpacing(0); root.setContentsMargins(0,0,0,0)

        root.addWidget(_tab_title("Monthly Field Production"))

        self.selector=FieldSelectorRow()
        self.selector.field_changed.connect(self._on_field)
        root.addWidget(self.selector)

        body=QWidget(); bl=QVBoxLayout(body); bl.setSpacing(10); bl.setContentsMargins(20,14,20,14)

        bl.addWidget(_sep())

        dr=QHBoxLayout(); dr.addWidget(QLabel("<b>Production Month:</b>"))
        self.date_w=PersianDateWidget(); dr.addWidget(self.date_w)
        self.load_btn=QPushButton("Load Existing"); self.load_btn.setStyleSheet(BTN_PLAIN)
        dr.addWidget(self.load_btn); dr.addStretch(); bl.addLayout(dr)

        grp=QGroupBox("Production Values"); frm=QFormLayout()
        frm.setLabelAlignment(Qt.AlignRight); frm.setSpacing(10); frm.setContentsMargins(20,12,20,12)
        self.f_oil=QLineEdit(); self.f_oil.setPlaceholderText("STB")
        self.f_gas=QLineEdit(); self.f_gas.setPlaceholderText("MMSCF")
        self.f_water=QLineEdit(); self.f_water.setPlaceholderText("BBL")
        frm.addRow("Oil Production (STB):",self.f_oil)
        frm.addRow("Gas Production (MMSCF):",self.f_gas)
        frm.addRow("Water Production (BBL):",self.f_water)
        grp.setLayout(frm); bl.addWidget(grp)

        br=QHBoxLayout()
        self.save_btn=QPushButton("Save to DB"); self.save_btn.setStyleSheet(BTN_SAVE)
        self.save_btn.setMaximumWidth(160); br.addWidget(self.save_btn); br.addStretch()
        bl.addLayout(br)
        self.status_lbl=QLabel(""); self.status_lbl.setStyleSheet("color:grey;font-style:italic;")
        bl.addWidget(self.status_lbl); bl.addStretch()

        root.addWidget(body)
        self.load_btn.clicked.connect(self._load)
        self.save_btn.clicked.connect(self._save)

    def _on_field(self,code,name,district):
        self._field_code=code; self._field_name=name; self._district=district
        self.status_lbl.setText(f"Field: {name}  ({code})"); self._load()

    def _load(self):
        if not self._field_code: return
        row=db.get_monthly_production(self._field_code,self.date_w.get_yyyymm()) or \
            db.get_monthly_production(self._field_code)
        if row:
            self.date_w.set_date(str(int(float(row.get('prod_date',0)))))
            self.f_oil.setText(str(row.get('m_oil',''))); self.f_gas.setText(str(row.get('m_gas','')))
            self.f_water.setText(str(row.get('m_water',''))); self.status_lbl.setText(f"Loaded for {self.date_w.get_display()}.")
        else: self.status_lbl.setText("No existing record — enter new data.")

    def _save(self):
        if not self._field_code: QMessageBox.warning(self,"No Field","Select a field first."); return
        try:
            db.save_monthly_production({'Field_Code':self._field_code,'Field_Name':self._field_name,
                'District':self._district,'prod_date':self.date_w.get_yyyymm(),
                'm_oil':float(self.f_oil.text()),'m_gas':float(self.f_gas.text()),'m_water':float(self.f_water.text())})
            self.status_lbl.setText(f"Saved for {self._field_name} / {self.date_w.get_display()}.")
            QMessageBox.information(self,"Saved","Monthly production data saved.")
        except ValueError: QMessageBox.warning(self,"Input Error","Enter valid numbers for oil, gas, and water.")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — Allocation
# ─────────────────────────────────────────────────────────────────────────────
class AllocationTab(QWidget):
    def __init__(self):
        super().__init__()
        self._field_code=None; self._result={}
        self._build()

    def _build(self):
        root=QVBoxLayout(self); root.setSpacing(0); root.setContentsMargins(0,0,0,0)

        root.addWidget(_tab_title("Production Allocation"))

        self.selector=FieldSelectorRow()
        self.selector.field_changed.connect(self._on_field)
        root.addWidget(self.selector)

        body=QWidget(); bl=QVBoxLayout(body); bl.setSpacing(10); bl.setContentsMargins(16,12,16,12)

        bl.addWidget(_sep())

        top=QHBoxLayout(); top.addWidget(QLabel("<b>Allocation Month:</b>"))
        self.date_w=PersianDateWidget(); top.addWidget(self.date_w)
        top.addSpacing(20)
        self.run_btn=QPushButton("▶  Run Allocation"); self.run_btn.setStyleSheet(BTN_RUN)
        top.addWidget(self.run_btn); top.addStretch(); bl.addLayout(top)

        res_box=QGroupBox("Results Summary"); rl=QVBoxLayout()
        self.results_txt=QTextEdit(); self.results_txt.setReadOnly(True)
        self.results_txt.setFont(QFont("Courier New",9)); self.results_txt.setMinimumHeight(200)
        rl.addWidget(self.results_txt); res_box.setLayout(rl); bl.addWidget(res_box)

        sr=QHBoxLayout()
        self.save_btn=QPushButton("💾  Save to Production Table"); self.save_btn.setStyleSheet(BTN_SAVE)
        self.save_btn.setEnabled(False); sr.addWidget(self.save_btn); sr.addStretch(); bl.addLayout(sr)

        self.status_lbl=QLabel("Select a month and click Run Allocation.")
        self.status_lbl.setStyleSheet("color:grey;font-style:italic;"); bl.addWidget(self.status_lbl)
        bl.addStretch(); root.addWidget(body)

        self.run_btn.clicked.connect(self._run)
        self.save_btn.clicked.connect(self._save_to_db)

    def _on_field(self,code,name,district):
        self._field_code=code; self._result={}; self.save_btn.setEnabled(False)
        self.results_txt.clear(); self.status_lbl.setText(f"Ready: {name}  ({code})")
        self.status_lbl.setStyleSheet("color:grey;font-style:italic;")

    def _run(self):
        if not self._field_code: QMessageBox.warning(self,"No Field","Select a field first."); return
        self.run_btn.setEnabled(False); self.save_btn.setEnabled(False)
        self.status_lbl.setText("Running…"); self.status_lbl.setStyleSheet("color:darkorange;")
        self._worker=AllocWorker(self._field_code,self.date_w.get_yyyymm())
        self._worker.done.connect(self._on_done); self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_done(self,df,prod_data,district,field_name,formatted):
        self._result=dict(df=df,prod_data=prod_data,district=district,
                          field_name=field_name,formatted=formatted,raw=self.date_w.get_yyyymm())
        active=int((df['prod_days']>0).sum())
        self.results_txt.setText(
            f"  Field      : {field_name}  ({district})\n  Period     : {formatted}\n"
            f"  Wells      : {active} active / {len(df)} total\n\n"
            f"  ─── Monthly ────────────────────────────────────\n"
            f"  Oil        : {df['m_oil'].sum():>14,.0f}  STB\n"
            f"  Gas        : {df['m_gas'].sum():>14,.2f}  MMSCF\n"
            f"  Water      : {df['m_water'].sum():>14,.0f}  BBL\n\n"
            f"  ─── Cumulative (after this month) ──────────────\n"
            f"  Oil        : {df['cum_oil'].sum():>14,.0f}  STB\n"
            f"  Gas        : {df['cum_gas'].sum():>14,.2f}  MMSCF\n"
            f"  Water      : {df['cum_water'].sum():>14,.0f}  BBL\n")
        self.status_lbl.setText("Computed. Click 'Save to Production Table' to commit.")
        self.status_lbl.setStyleSheet("color:#1565c0;font-weight:bold;")
        self.run_btn.setEnabled(True); self.save_btn.setEnabled(True)

    def _on_error(self,msg):
        self.status_lbl.setText(f"Error: {msg}"); self.status_lbl.setStyleSheet("color:red;font-weight:bold;")
        self.run_btn.setEnabled(True); QMessageBox.critical(self,"Allocation Error",msg)

    def _save_to_db(self):
        if not self._result: return
        r=self._result; raw=r['raw']
        exists=db.production_exists(self._field_code,raw)
        msg=(f"Production data for  {r['field_name']} / {r['formatted']}  "
             f"{'already exists. Replace it?' if exists else 'will be saved. Confirm?'}")
        if QMessageBox.question(self,"Confirm Save",msg,QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes: return
        save_allocation(r['df'],r['prod_data'],self._field_code,raw,r['formatted'],r['field_name'],r['district'])
        self.status_lbl.setText(f"Saved: {r['field_name']} / {r['formatted']}")
        self.status_lbl.setStyleSheet("color:green;font-weight:bold;"); self.save_btn.setEnabled(False)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — Database Viewer
# ─────────────────────────────────────────────────────────────────────────────
class DatabaseTab(QWidget):
    def __init__(self):
        super().__init__()
        self._field_code=None; self._active_tbl=None; self._df=pd.DataFrame()
        self._build()

    def _build(self):
        root=QVBoxLayout(self); root.setSpacing(0); root.setContentsMargins(0,0,0,0)

        root.addWidget(_tab_title("Database Viewer"))

        self.selector=FieldSelectorRow()
        self.selector.field_changed.connect(self._on_field)
        root.addWidget(self.selector)

        body=QWidget(); bl=QVBoxLayout(body); bl.setSpacing(6); bl.setContentsMargins(8,8,8,8)

        bl.addWidget(_sep())

        br=QHBoxLayout()
        self.btn_test=QPushButton("Test Table"); self.btn_test.setCheckable(True)
        self.btn_mon=QPushButton("Monthly Production"); self.btn_mon.setCheckable(True)
        self.btn_prod=QPushButton("Production Table"); self.btn_prod.setCheckable(True)
        for b in (self.btn_test,self.btn_mon,self.btn_prod):
            b.setStyleSheet(BTN_PLAIN); br.addWidget(b)
        br.addStretch(); bl.addLayout(br)

        self.table=QTableWidget(); self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers); bl.addWidget(self.table)

        cr=QHBoxLayout()
        self.refresh_btn=QPushButton("🔄 Refresh"); self.refresh_btn.setStyleSheet(BTN_PLAIN)
        self.add_btn=QPushButton("➕ Add Row"); self.add_btn.setStyleSheet(BTN_WARN)
        self.edit_btn=QPushButton("✏️ Edit Row"); self.edit_btn.setStyleSheet(BTN_PLAIN)
        self.del_btn=QPushButton("🗑 Delete Row"); self.del_btn.setStyleSheet(BTN_DEL)
        for b in (self.refresh_btn,self.add_btn,self.edit_btn,self.del_btn): cr.addWidget(b)
        cr.addStretch(); bl.addLayout(cr)
        self.info_lbl=QLabel(""); self.info_lbl.setStyleSheet("color:grey;font-style:italic;")
        bl.addWidget(self.info_lbl); root.addWidget(body)

        self.btn_test.clicked.connect(lambda: self._show('test_data','Test Table'))
        self.btn_mon.clicked.connect(lambda: self._show('monthly_production','Monthly Production'))
        self.btn_prod.clicked.connect(lambda: self._show('production','Production Table'))
        self.refresh_btn.clicked.connect(self._refresh)
        self.del_btn.clicked.connect(self._delete_row)
        self.edit_btn.clicked.connect(self._edit_row)
        self.add_btn.clicked.connect(self._add_row)

    def _on_field(self,code,name,district):
        self._field_code=code
        if self._active_tbl: self._refresh()

    def _show(self,tbl,label):
        self._active_tbl=tbl
        for b,t in ((self.btn_test,'test_data'),(self.btn_mon,'monthly_production'),(self.btn_prod,'production')):
            b.setChecked(t==tbl)
        self._refresh(); self.info_lbl.setText(f"Showing: {label}")

    def _refresh(self):
        if not self._active_tbl: return
        self._df=db.get_table_df(self._active_tbl,self._field_code)
        cols=self._df.columns.tolist(); self.table.setRowCount(0)
        self.table.setColumnCount(len(cols)); self.table.setHorizontalHeaderLabels(cols)
        for _,row in self._df.iterrows():
            ri=self.table.rowCount(); self.table.insertRow(ri)
            for ci,col in enumerate(cols):
                val=row[col]
                self.table.setItem(ri,ci,QTableWidgetItem(
                    '' if (val is None or (isinstance(val,float) and pd.isna(val))) else str(val)))

    def _selected_id(self):
        if not self.table.selectedItems(): QMessageBox.warning(self,"No Selection","Select a row first."); return None
        ri=self.table.currentRow()
        if 'id' not in self._df.columns: QMessageBox.warning(self,"Error","Table has no 'id' column."); return None
        return self._df.iloc[ri]['id']

    def _delete_row(self):
        rid=self._selected_id()
        if rid is None: return
        if QMessageBox.question(self,"Confirm Delete",f"Delete row id={rid}?\nThis cannot be undone.",
                                QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:
            db.delete_table_row(self._active_tbl,rid); self._refresh()
            self.info_lbl.setText(f"Deleted row id={rid}.")

    def _edit_row(self):
        rid=self._selected_id()
        if rid is None: return
        row=self._df.iloc[self.table.currentRow()].to_dict()
        dlg=_RowEditDialog(row,self)
        if dlg.exec_():
            for col,val in dlg.get_values().items():
                if col!='id': db.update_table_row(self._active_tbl,rid,col,val)
            self._refresh(); self.info_lbl.setText(f"Updated row id={rid}.")

    def _add_row(self):
        if not self._active_tbl: QMessageBox.warning(self,"No Table","Select a table first."); return
        template={c:'' for c in self._df.columns if c!='id'}
        dlg=_RowEditDialog(template,self,title="Add Row")
        if dlg.exec_():
            nd=dlg.get_values(); nd.pop('id',None)
            try: db.insert_table_row(self._active_tbl,nd); self._refresh(); self.info_lbl.setText("New row added.")
            except Exception as e: QMessageBox.critical(self,"Insert Error",str(e))


class _RowEditDialog:
    def __init__(self,row_dict,parent,title="Edit Row"):
        self._dialog=QDialog(parent); self._dialog.setWindowTitle(title)
        self._dialog.setMinimumWidth(400); self._edits={}
        layout=QVBoxLayout(self._dialog)
        sc=QScrollArea(); sc.setWidgetResizable(True); inner=QWidget(); frm=QFormLayout(inner)
        frm.setLabelAlignment(Qt.AlignRight)
        for k,v in row_dict.items():
            if k=='id': continue
            le=QLineEdit(str(v) if v is not None else ''); frm.addRow(f"{k}:",le); self._edits[k]=le
        sc.setWidget(inner); layout.addWidget(sc)
        bb=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        bb.accepted.connect(self._dialog.accept); bb.rejected.connect(self._dialog.reject)
        layout.addWidget(bb)
    def exec_(self): return self._dialog.exec_()
    def get_values(self): return {k:le.text() for k,le in self._edits.items()}


# ─────────────────────────────────────────────────────────────────────────────
# TAB 5 — Report
# ─────────────────────────────────────────────────────────────────────────────
class ReportTab(QWidget):
    def __init__(self):
        super().__init__()
        self._field_code=None; self._field_name=""; self._district=""
        self._build()

    def _build(self):
        root=QVBoxLayout(self); root.setSpacing(0); root.setContentsMargins(0,0,0,0)

        root.addWidget(_tab_title("Report Generation"))

        self.selector=FieldSelectorRow()
        self.selector.field_changed.connect(self._on_field)
        root.addWidget(self.selector)

        body=QWidget(); bl=QVBoxLayout(body); bl.setSpacing(10); bl.setContentsMargins(16,12,16,12)
        bl.addWidget(_sep())

        grp=QGroupBox("Report Options"); frm=QFormLayout()
        frm.setLabelAlignment(Qt.AlignRight); frm.setSpacing(10); frm.setContentsMargins(20,12,20,12)
        self.date_w=PersianDateWidget(); frm.addRow("Report Month:",self.date_w)
        self.type_cb=QComboBox(); self.type_cb.addItems(REPORT_TYPES)
        frm.addRow("Report Type:",self.type_cb); grp.setLayout(frm); bl.addWidget(grp)

        gr=QHBoxLayout()
        self.gen_btn=QPushButton("📄  Generate Report"); self.gen_btn.setStyleSheet(BTN_PDF)
        gr.addWidget(self.gen_btn); gr.addStretch(); bl.addLayout(gr)
        self.status_lbl=QLabel("Select month and report type, then click Generate.")
        self.status_lbl.setStyleSheet("color:grey;font-style:italic;"); bl.addWidget(self.status_lbl)
        bl.addStretch(); root.addWidget(body)
        self.gen_btn.clicked.connect(self._generate)

    def _on_field(self,code,name,district):
        self._field_code=code; self._field_name=name; self._district=district

    def _generate(self):
        if not self._field_code: QMessageBox.warning(self,"No Field","Select a field first."); return
        pd_str=self.date_w.get_yyyymm(); fmt=self.date_w.get_display()
        rtype=self.type_cb.currentText()
        try:
            if rtype=="Production Report of Wells":
                df=db.get_production(self._field_code,pd_str)
                if df.empty: QMessageBox.warning(self,"No Data","Run and save an allocation first."); return
                f=create_well_production_report(df,self._district,self._field_name,fmt)
            elif rtype=="Test Report":
                df=db.get_latest_tests(self._field_code)
                if df.empty: QMessageBox.warning(self,"No Data","No test data found."); return
                f=create_test_report(df,self._district,self._field_name,fmt)
            elif rtype=="Production Report of Fields":
                df=db.get_district_field_summary(self._district,pd_str)
                if df.empty: QMessageBox.warning(self,"No Data",f"No data for district {self._district} / {fmt}."); return
                f=create_field_production_report(df,self._district,fmt)
            elif rtype=="Production Report of Reservoirs":
                df=db.get_reservoir_summary(self._field_code,pd_str)
                if df.empty: QMessageBox.warning(self,"No Data",f"No data for {self._field_name} / {fmt}."); return
                f=create_reservoir_production_report(df,self._district,self._field_name,fmt)
            self.status_lbl.setText(f"Report saved: {f}")
            self.status_lbl.setStyleSheet("color:green;font-weight:bold;")
            QMessageBox.information(self,"Done",f"Saved as:\n{f}")
        except Exception as e:
            self.status_lbl.setStyleSheet("color:red;"); self.status_lbl.setText(f"Error: {e}")
            QMessageBox.critical(self,"Report Error",str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Main Window  (no shared selector — each tab owns its own)
# ─────────────────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IOOC – Production Allocation System")
        self.setMinimumSize(1100,800)
        self._build_menu(); self._build_ui()
        self.statusBar().showMessage("Ready.  Use  File → Import from Excel  on first run.")

    def _build_menu(self):
        mb=self.menuBar(); fm=mb.addMenu("File")
        ia=QAction("Import from Excel…",self); ia.setShortcut("Ctrl+I")
        ia.triggered.connect(self._import); fm.addAction(ia)
        fm.addSeparator()
        ex=QAction("Exit",self); ex.setShortcut("Ctrl+Q"); ex.triggered.connect(self.close)
        fm.addAction(ex)
        hm=mb.addMenu("Help")
        ab=QAction("About",self)
        ab.triggered.connect(lambda: QMessageBox.about(self,"About",
            "<b>IOOC Production Allocation System</b><br><br>"
            "Iranian Offshore Oil Company – Reservoir Engineering Dept."))
        hm.addAction(ab)

    def _build_ui(self):
        central=QWidget(); self.setCentralWidget(central)
        layout=QVBoxLayout(central); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)

        self.tabs=QTabWidget(); self.tabs.setDocumentMode(True)

        self.tab_test    = TestDataTab()
        self.tab_monthly = MonthlyProductionTab()
        self.tab_alloc   = AllocationTab()
        self.tab_db      = DatabaseTab()
        self.tab_report  = ReportTab()

        self.tabs.addTab(self.tab_test,    "📋  Test Data")
        self.tabs.addTab(self.tab_monthly, "📊  Monthly Production")
        self.tabs.addTab(self.tab_alloc,   "⚙️  Allocation")
        self.tabs.addTab(self.tab_db,      "🗄️  Database")
        self.tabs.addTab(self.tab_report,  "📄  Report")

        layout.addWidget(self.tabs)

    def _import(self):
        folder=QFileDialog.getExistingDirectory(self,"Select folder containing Excel files")
        if not folder: return
        required=["Test_Data_1.xlsx","Cum_Table.xlsx","Monthly_Data.xlsx","RS_Code.xlsx"]
        missing=[f for f in required if not os.path.exists(f"{folder}/{f}")]
        if missing:
            QMessageBox.warning(self,"Missing Files","Files not found:\n"+"\n".join(f"  • {f}" for f in missing)); return
        try:
            self.statusBar().showMessage("Importing…"); QApplication.processEvents()
            db.import_from_excel(folder)
            # refresh every tab's selector after import
            for tab in (self.tab_test,self.tab_monthly,self.tab_alloc,self.tab_db,self.tab_report):
                tab.selector.refresh()
            self.statusBar().showMessage("Import complete.")
            QMessageBox.information(self,"Done","Data imported successfully.")
        except Exception as e:
            QMessageBox.critical(self,"Import Error",str(e))


# ─────────────────────────────────────────────────────────────────────────────
if __name__=="__main__":
    db.create_tables()
    app=QApplication(sys.argv); app.setStyle("Fusion")
    pal=app.palette()
    pal.setColor(QPalette.Highlight,QColor("#1565c0"))
    pal.setColor(QPalette.HighlightedText,QColor("white"))
    app.setPalette(pal)
    w=MainWindow(); w.show(); sys.exit(app.exec_())