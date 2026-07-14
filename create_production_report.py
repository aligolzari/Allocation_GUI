# -*- coding: utf-8 -*-
"""
create_production_report.py  –  Four PDF report types.

Rounding rules (applied uniformly across all reports):
  gas columns  (m_gas, cum_gas, avg_GOR, S_GOR, GOR)  → 2 decimal places
  API, W.Cut (WC)                                       → 1 decimal place
  everything else numeric                               → integer (rounded)
"""

from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import (SimpleDocTemplate, Spacer, Table,
                                 TableStyle, PageBreak)
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Image
import pandas as pd, numpy as np, os

_LOGO = "IOOC_logo.png"
_CO   = "Iranian Offshore Oil Company"
_DEPT = "Res. Eng. Department"
_RED  = colors.HexColor("#740000")


# ─────────────────────────────────────────────────────────────────────────────
# Value formatter  –  rounding rules enforced here
# ─────────────────────────────────────────────────────────────────────────────
def _v(val, fmt='int'):
    """
    fmt:
      'int'   → rounded integer   (default for most numeric columns)
      'gas'   → 2 decimal places  (gas volumes, GOR values)
      'float' → 1 decimal place   (API, W.Cut)
      'str'   → plain string      (text columns)
    """
    if val is None: return ""
    try:
        if isinstance(val, float) and pd.isna(val): return ""
    except Exception: pass
    try:
        if fmt == 'int':
            return str(int(round(float(val))))   # round, not truncate
        if fmt == 'float':
            return f"{float(val):.1f}"
        if fmt == 'gas':
            return f"{float(val):.2f}"
    except (ValueError, TypeError):
        pass
    return str(val)


# ─────────────────────────────────────────────────────────────────────────────
# Shared layout helpers
# ─────────────────────────────────────────────────────────────────────────────
def _meta_table(district, field_name, prod_date,
                right_label="Field Name:",
                title="PRODUCTION REPORT OF WELLS"):
    if os.path.exists(_LOGO):
        logo = Image(_LOGO, width=27*mm, height=13.5*mm)
        nest = Table([[logo], [_CO], [_DEPT]], colWidths=[30*mm])
        nest.setStyle(TableStyle([
            ('ALIGN',  (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('FONT',   (0,1), (0,2),   'Helvetica', 7.5),
            ('LEFTPADDING',   (0,0), (-1,-1), 0),
            ('RIGHTPADDING',  (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING',    (0,0), (-1,-1), 0)]))
        left = nest
    else:
        left = f"{_CO}\n{_DEPT}"

    data = [[left,  title,  'District:',  district],
            ["",    "",     right_label,  field_name],
            ["",    "",     'Date:',      prod_date]]
    t = Table(data, colWidths=[50*mm, 152*mm, 30*mm, 27*mm],
              rowHeights=[6*mm, 6*mm, 6*mm])
    t.setStyle(TableStyle([
        ('SPAN',  (0,0), (0,2)), ('VALIGN', (0,0), (0,2), 'MIDDLE'),
        ('ALIGN', (0,0), (0,2), 'CENTER'),
        ('SPAN',  (1,0), (1,2)), ('VALIGN', (1,0), (1,2), 'MIDDLE'),
        ('ALIGN', (1,0), (1,2), 'CENTER'),
        ('ALIGN', (2,0), (-1,-1), 'LEFT'),
        ('VALIGN',(2,0), (-1,-1), 'MIDDLE'),
        ('FONT',  (1,0), (1,0),   'Helvetica', 14),
        ('FONT',  (2,0), (-1,-1), 'Helvetica', 9),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING',    (0,0), (-1,-1), 0)]))
    return t


def _footer_cb(prod_date, label):
    def _add(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        w = landscape(A4)[0]
        canvas.drawCentredString(
            w / 2, 15,
            f"Page {doc.page}  –  {label}  –  {prod_date}  –  {_CO}")
        canvas.line(50, 25, w - 50, 25)
        canvas.restoreState()
    return _add


def _doc(output_file):
    return SimpleDocTemplate(output_file, pagesize=landscape(A4),
        rightMargin=10*mm, leftMargin=10*mm,
        topMargin=10*mm,  bottomMargin=10*mm)


def _hdr_style(spans=(), boxes=()):
    """Build a header TableStyle with optional SPAN and BOX entries."""
    s = TableStyle([
        ('ALIGN',  (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TEXTCOLOR', (0,0), (-1,-1), _RED),
        ('FONT',   (0,0), (-1,-1), 'Times-Roman', 9),
        ('GRID',   (0,0), (-1,-1), 1, colors.black),
        ('LEFTPADDING',   (0,0), (-1,-1), 3),
        ('RIGHTPADDING',  (0,0), (-1,-1), 3),
        ('TOPPADDING',    (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ])
    for (r0c0, r0r0, r0c1, r0r1) in spans:
        s.add('SPAN', (r0c0, r0r0), (r0c1, r0r1))
    for (c0, c1) in boxes:
        s.add('BOX', (c0, 0), (c1, -1), 1.5, colors.black)
    return s


def _data_style(boxes=()):
    s = TableStyle([
        ('ALIGN',  (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONT',   (0,0), (-1,-1), 'Times-Roman', 8),
        ('LEFTPADDING',   (0,0), (-1,-1), 3),
        ('RIGHTPADDING',  (0,0), (-1,-1), 3),
        ('TOPPADDING',    (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LINEBEFORE', (0,0), (-1,-1), 0.5, colors.black),
        ('LINEABOVE',  (0,1), (-1,-1), 0.5, colors.black),
    ])
    for (c0, c1) in boxes:
        s.add('BOX', (c0, 0), (c1, -1), 1.5, colors.black)
    return s


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Well Production Report
# ─────────────────────────────────────────────────────────────────────────────
# Column index map:
# 0-3: A (Well Name, Formation, Status, Choke)
# 4-6: B (WHP, MFP, BHP)        ← Pressure block
# 7:   C (Date of Last Prod.)
# 8-11: D (Monthly: Days, Oil, Gas, Water)
# 12-15: E (Cumulative: Days, Oil, Gas, Water)
# 16-20: F (Avg: Oil/D, Oil/PD, GOR, API, W.Cut)

_PROD_CW = (
    [20*mm, 15*mm, 10*mm, 10*mm] +   # A – identity
    [8.5*mm, 8.5*mm, 8.5*mm] +       # B – pressure
    [16*mm] +                         # C – last prod date
    [8.5*mm, 10*mm, 14*mm, 11*mm] +  # D – monthly
    [11*mm, 18*mm, 16*mm, 16*mm] +   # E – cumulative
    [13*mm, 15*mm, 16*mm, 7*mm, 10*mm]  # F – rates
)

_PROD_BOXES = [(0,3),(4,6),(7,7),(8,11),(12,15),(16,20)]

_PROD_HDR = [
    # row 0 – group labels (spans filled in via style)
    ["Well Name","Formation","Status","Choke\n(/64)",
     "Pressure (PSIG)","","",
     "Date of\nLast\nProd.",
     "Monthly Production","","","",
     "Cumulative Production","","","",
     "Average Daily Production","","","",""],
    # row 1 – column sub-labels
    ["","","","",
     "WHP","MFP","BHP",
     "",
     "Day\n(PD)","Oil\n(STB)","Gas\n(MMSCF)","Water\n(BBL)",
     "Day\n(PD)","Oil\n(STB)","Gas\n(MMSCF)","Water\n(BBL)",
     "Oil\n(STB/D)","Oil\n(STB/PD)","GOR\n(SCF/BBL)","API","W.Cut\n(%)"],
]

_PROD_SPANS = [
    # (col_start, row_start, col_end, row_end)  in (col,row) notation for TableStyle
    (0,0,0,1),(1,0,1,1),(2,0,2,1),(3,0,3,1),   # A cols span both rows
    (4,0,6,0),                                   # B group header
    (7,0,7,1),                                   # C spans both rows
    (8,0,11,0),(12,0,15,0),(16,0,20,0),          # D, E, F group headers
]


def _prod_header():
    t = Table(_PROD_HDR, colWidths=_PROD_CW)
    t.setStyle(_hdr_style(spans=_PROD_SPANS, boxes=_PROD_BOXES))
    return t


def _prod_rows(df):
    rows = []
    for _, r in df.iterrows():
        rows.append([
            str(r.get("WEL_NAM","")),
            str(r.get("Z_COD","")),
            str(r.get("status","")),
            _v(r.get("choke_t")),
            _v(r.get("WHP_t")),
            _v(r.get("MFP_t")),
            _v(r.get("BHP")),
            str(r.get("last_prod_date","")),
            _v(r.get("prod_days")),
            _v(r.get("m_oil")),
            _v(r.get("m_gas"),    'gas'),
            _v(r.get("m_water")),
            _v(r.get("c_days")),
            _v(r.get("cum_oil")),
            _v(r.get("cum_gas"),  'gas'),
            _v(r.get("cum_water")),
            _v(r.get("oil_rate_avg")),
            _v(r.get("oil_rate")),
            _v(r.get("GOR_a")),          # GOR in SCF/BBL → integer
            _v(r.get("API"),      'float'),
            _v(r.get("WC"),       'float'),
        ])
    return rows


def _prod_totals(df):
    row = [""] * 21
    row[0]  = "Total"
    row[9]  = _v(df['m_oil'].sum()          if 'm_oil'    in df else None)
    row[10] = _v(df['m_gas'].sum()          if 'm_gas'    in df else None, 'gas')
    row[11] = _v(df['m_water'].sum()        if 'm_water'  in df else None)
    row[13] = _v(df['cum_oil'].sum()        if 'cum_oil'  in df else None)
    row[14] = _v(df['cum_gas'].sum()        if 'cum_gas'  in df else None, 'gas')
    row[15] = _v(df['cum_water'].sum()      if 'cum_water'in df else None)
    t = Table([row], colWidths=_PROD_CW)
    t.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONT',  (0,0), (-1,-1), 'Helvetica-Bold', 8),
    ]))
    return t


def create_well_production_report(df, district, field_name, prod_date,
                                   output_file=None):
    if output_file is None:
        clean = prod_date.replace('/', '')
        output_file = f"{field_name}_{clean}_Well_Production_Report.pdf"

    doc   = _doc(output_file)
    cb    = _footer_cb(prod_date, field_name)
    story = []
    rpp   = 30
    pages = max(1, (len(df) + rpp - 1) // rpp)

    for pg in range(pages):
        if pg: story.append(PageBreak())
        story += [
            _meta_table(district, field_name, prod_date),
            Spacer(1, 6),
            _prod_header(),
            Spacer(1, 2),
        ]
        chunk = df.iloc[pg * rpp:(pg + 1) * rpp]
        dt = Table(_prod_rows(chunk), colWidths=_PROD_CW)
        dt.setStyle(_data_style(boxes=_PROD_BOXES))
        story.append(dt)
        if pg == pages - 1:
            story.append(_prod_totals(df))

    doc.build(story, onFirstPage=cb, onLaterPages=cb)
    return output_file


# backwards-compat alias
def create_report(df, district, field_name, prod_date, output_file=None):
    return create_well_production_report(df, district, field_name,
                                         prod_date, output_file)


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Test Report
#
# Column order (16 cols):
#   0  Well Name          1  Formation          2  Test Date
#   3  Choke(/64)         4  WHP(PSIG)          5  BHP(PSIG)
#   6  MFP(PSIG)          7  LGP(PSIG)          8  Sep.P(PSIG)
#   9  Sep.T(°F)          10 LGR(MSCF/D)        11 Oil Rate(STB/D)
#   12 API                13 W.Cut(%)            14 S_GOR(SCF/BBL)
#   15 GOR(SCF/BBL)
#
# Header groups:
#   A: cols 0-2  (identity – each spans 2 rows)
#   B: cols 3-7  "Pressure & Lift Data"
#   C: cols 8-10 "Separator Data"
#   D: cols 11-15 "Test Results"
# ─────────────────────────────────────────────────────────────────────────────

_TEST_CW = [
    22*mm, 14*mm, 18*mm,       # A: Well Name, Formation, Test Date
    10*mm, 11*mm, 11*mm, 11*mm, 11*mm,   # B: Choke, WHP, BHP, MFP, LGP
    11*mm, 11*mm, 13*mm,       # C: Sep.P, Sep.T, LGR
    14*mm, 9*mm,  10*mm, 15*mm, 15*mm,   # D: Oil Rate, API, W.Cut, S_GOR, GOR
]

_TEST_HDR = [
    # row 0 – group labels
    ["Well Name", "Formation", "Test Date",
     "Pressure & Lift Data", "", "", "", "",
     "Separator Data", "", "",
     "Test Results", "", "", "", ""],
    # row 1 – column sub-labels
    ["", "", "",
     "Choke\n(/64)", "WHP\n(PSIG)", "BHP\n(PSIG)", "MFP\n(PSIG)", "LGP\n(PSIG)",
     "Sep.P\n(PSIG)", "Sep.T\n(°F)", "LGR",
     "Oil Rate\n(STB/D)", "API", "W.Cut\n(%)", "S_GOR\n(SCF/BBL)", "GOR\n(SCF/BBL)"],
]

_TEST_SPANS = [
    (0,0,0,1),(1,0,1,1),(2,0,2,1),    # identity cols span both rows
    (3,0,7,0),                          # B group header
    (8,0,10,0),                         # C group header
    (11,0,15,0),                        # D group header
]
_TEST_BOXES = [(0,2),(3,7),(8,10),(11,15)]


def _compute_test_gor(df):
    """
    Calculate GOR for each well in test df using the RS-polynomial formula.
    Returns df with an added 'GOR' column.
    Silently skips if RS_Code data is unavailable.
    """
    try:
        import db_manager as db
        rs_df = db.get_rs_codes()
        if rs_df.empty:
            df['GOR'] = np.nan
            return df

        df = df.copy()
        df['LGAS_rate'] = pd.to_numeric(df.get('LGAS_rate', 0), errors='coerce').fillna(0)

        merged = pd.merge(df, rs_df, left_on='RS_Code', right_on='Code_No', how='left')

        def _rs(row):
            try:
                if row['RS_Code'] != 9:
                    return (row['A']*row['S_P']**3 + row['B']*row['S_P']**2 +
                            row['C']*row['S_P'] + row['D'] +
                            row['E']*row['S_T'] + row['F']*row['S_T']**2 +
                            row['G']*row['S_T']*row['S_P'])
                sp = row['S_P'] + 14.7
                return (row['A']*sp**3 + row['B']*sp**2 + row['C']*sp + row['D'])
            except Exception:
                return np.nan

        rs_vals = merged.apply(_rs, axis=1).values

        def _gor(i, row):
            try:
                s_gor = float(row['S_GOR'])
                if s_gor == 0: return 0.0
                oil   = float(row['oil_rate_t'])
                lgas  = float(row['LGAS_rate'])
                rs    = float(rs_vals[i])
                g = (s_gor * oil - lgas * 1_000_000) / (oil + rs)
                return g if g >= 0 else np.nan
            except Exception:
                return np.nan

        df['GOR'] = [_gor(i, row) for i, (_, row) in enumerate(df.iterrows())]
        return df

    except Exception:
        df = df.copy()
        df['GOR'] = np.nan
        return df


def create_test_report(df, district, field_name, prod_date, output_file=None):
    if output_file is None:
        clean = prod_date.replace('/', '')
        output_file = f"{field_name}_{clean}_Test_Report.pdf"

    df = _compute_test_gor(df)

    hdr = Table(_TEST_HDR, colWidths=_TEST_CW)
    hdr.setStyle(_hdr_style(spans=_TEST_SPANS, boxes=_TEST_BOXES))

    rows = []
    for _, r in df.iterrows():
        rows.append([
            str(r.get("WEL_NAM",  "")),
            str(r.get("Z_COD",    "")),
            str(r.get("Test_Date","") or r.get("test_date","")),
            _v(r.get("choke_t")),
            _v(r.get("WHP_t")),
            _v(r.get("BHP")),
            _v(r.get("MFP_t")),
            _v(r.get("LGAS_P")),
            _v(r.get("S_P")),
            _v(r.get("S_T")),
            _v(r.get("LGAS_rate")),
            _v(r.get("oil_rate_t")),
            _v(r.get("API"),  'float'),
            _v(r.get("BSW_p"),'float'),   # operational W.Cut
            _v(r.get("S_GOR")),          # Separator GOR  → integer
            _v(r.get("GOR")),            # Computed GOR   → integer
        ])

    dt = Table(rows, colWidths=_TEST_CW)
    dt.setStyle(_data_style(boxes=_TEST_BOXES))

    meta = _meta_table(district, field_name, prod_date,
                       title="TEST REPORT OF WELLS")
    cb   = _footer_cb(prod_date, field_name)
    doc  = _doc(output_file)
    doc.build([meta, Spacer(1,6), hdr, Spacer(1,2), dt],
              onFirstPage=cb, onLaterPages=cb)
    return output_file


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Field Production Report  (one row per field within the district)
#
# Meaning: district-level view, each field = one row.
# Data source: db.get_district_field_summary(district, prod_date)
# ─────────────────────────────────────────────────────────────────────────────

_FLD_CW = [32*mm, 12*mm, 13*mm,
            24*mm, 20*mm, 22*mm,
            24*mm, 20*mm, 22*mm]

_FLD_HDR = [
    ["Field Name", "Total\nWells", "Active\nWells",
     "Monthly Production", "", "",
     "Cumulative Production", "", ""],
    ["", "", "",
     "Oil\n(STB)", "Gas\n(MMSCF)", "Water\n(BBL)",
     "Oil\n(STB)", "Gas\n(MMSCF)", "Water\n(BBL)"],
]

_FLD_SPANS = [(0,0,0,1),(1,0,1,1),(2,0,2,1),(3,0,5,0),(6,0,8,0)]
_FLD_BOXES = [(0,2),(3,5),(6,8)]


def create_field_production_report(df, district, prod_date, output_file=None):
    """
    Field Production Report for a District.
    df must have columns: Field_Name, wells, active_wells,
                          m_oil, m_gas, m_water, cum_oil, cum_gas, cum_water
    One row per field.
    """
    if output_file is None:
        clean = prod_date.replace('/', '')
        output_file = f"{district}_{clean}_Field_Production_Report.pdf"

    hdr = Table(_FLD_HDR, colWidths=_FLD_CW)
    hdr.setStyle(_hdr_style(spans=_FLD_SPANS, boxes=_FLD_BOXES))

    rows = []
    for _, r in df.iterrows():
        rows.append([
            str(r.get('Field_Name', '')),
            _v(r.get('wells')),
            _v(r.get('active_wells')),
            _v(r.get('m_oil')),
            _v(r.get('m_gas'),   'gas'),
            _v(r.get('m_water')),
            _v(r.get('cum_oil')),
            _v(r.get('cum_gas'), 'gas'),
            _v(r.get('cum_water')),
        ])

    # Totals row
    tot = [
        "Total",
        _v(df['wells'].sum()       if 'wells'       in df else None),
        _v(df['active_wells'].sum() if 'active_wells' in df else None),
        _v(df['m_oil'].sum()       if 'm_oil'       in df else None),
        _v(df['m_gas'].sum()       if 'm_gas'       in df else None, 'gas'),
        _v(df['m_water'].sum()     if 'm_water'     in df else None),
        _v(df['cum_oil'].sum()     if 'cum_oil'     in df else None),
        _v(df['cum_gas'].sum()     if 'cum_gas'     in df else None, 'gas'),
        _v(df['cum_water'].sum()   if 'cum_water'   in df else None),
    ]
    rows.append(tot)

    dt = Table(rows, colWidths=_FLD_CW)
    ds = _data_style(boxes=_FLD_BOXES)
    ds.add('FONT',  (0, len(rows)-1), (-1, len(rows)-1), 'Helvetica-Bold', 8)
    dt.setStyle(ds)

    meta = _meta_table(district, district, prod_date,
                       right_label="District:",
                       title="FIELD PRODUCTION REPORT")
    cb  = _footer_cb(prod_date, district)
    doc = _doc(output_file)
    doc.build([meta, Spacer(1,6), hdr, Spacer(1,2), dt],
              onFirstPage=cb, onLaterPages=cb)
    return output_file


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Reservoir Production Report  (one row per Z_COD within the field)
#
# Data source: db.get_reservoir_summary(field_code, prod_date)
# ─────────────────────────────────────────────────────────────────────────────

_RES_CW = [25*mm, 12*mm, 13*mm,
            22*mm, 18*mm, 20*mm,
            22*mm, 18*mm, 20*mm,
            16*mm, 11*mm]

_RES_HDR = [
    ["Reservoir\n(Z_COD)", "Total\nWells", "Active\nWells",
     "Monthly Production", "", "",
     "Cumulative Production", "", "",
     "Avg\nGOR\n(SCF/BBL)", "Avg\nW.Cut\n(%)"],
    ["", "", "",
     "Oil\n(STB)", "Gas\n(MMSCF)", "Water\n(BBL)",
     "Oil\n(STB)", "Gas\n(MMSCF)", "Water\n(BBL)",
     "", ""],
]

_RES_SPANS = [(0,0,0,1),(1,0,1,1),(2,0,2,1),
              (3,0,5,0),(6,0,8,0),
              (9,0,9,1),(10,0,10,1)]
_RES_BOXES = [(0,2),(3,5),(6,8),(9,9),(10,10)]


def create_reservoir_production_report(df, district, field_name, prod_date,
                                        output_file=None):
    """
    Reservoir Production Report for a single field.
    df must have: Z_COD, wells, active_wells,
                  m_oil, m_gas, m_water, cum_oil, cum_gas, cum_water,
                  avg_GOR, avg_WC
    One row per Z_COD.
    """
    if output_file is None:
        clean = prod_date.replace('/', '')
        output_file = f"{field_name}_{clean}_Reservoir_Production_Report.pdf"

    hdr = Table(_RES_HDR, colWidths=_RES_CW)
    hdr.setStyle(_hdr_style(spans=_RES_SPANS, boxes=_RES_BOXES))

    rows = []
    for _, r in df.iterrows():
        rows.append([
            str(r.get('Z_COD', '')),
            _v(r.get('wells')),
            _v(r.get('active_wells')),
            _v(r.get('m_oil')),
            _v(r.get('m_gas'),   'gas'),
            _v(r.get('m_water')),
            _v(r.get('cum_oil')),
            _v(r.get('cum_gas'), 'gas'),
            _v(r.get('cum_water')),
            _v(r.get('avg_GOR')),        # Avg GOR  → integer
            _v(r.get('avg_WC'),  'float'),
        ])

    dt = Table(rows, colWidths=_RES_CW)
    dt.setStyle(_data_style(boxes=_RES_BOXES))

    meta = _meta_table(district, field_name, prod_date,
                       title="RESERVOIR PRODUCTION REPORT")
    cb  = _footer_cb(prod_date, field_name)
    doc = _doc(output_file)
    doc.build([meta, Spacer(1,6), hdr, Spacer(1,2), dt],
              onFirstPage=cb, onLaterPages=cb)
    return output_file
