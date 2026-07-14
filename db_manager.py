# -*- coding: utf-8 -*-
"""
db_manager.py  –  All SQLite operations for the Production Allocation System.

Tables
──────
test_data           one test row per well+formation+field (latest test values)
test_records        up to 3 monthly tests per well+formation+field+month
cum_table           running cumulative totals, updated after each allocation
monthly_production  monthly field-level oil/gas/water (one per field+month)
production          allocated well-level results (same columns as PDF report)
rs_code             RS-polynomial coefficient reference (read-only after import)
"""

import sqlite3, math, pandas as pd

DB_PATH = "production.db"

# ── connection ────────────────────────────────────────────────────────────────
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

# ── schema ────────────────────────────────────────────────────────────────────
def create_tables():
    conn = get_connection(); c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS test_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        District TEXT, Field TEXT, Field_Code INTEGER NOT NULL,
        WEL_NAM TEXT NOT NULL, Z_COD TEXT NOT NULL,
        Test_Date TEXT, RS_Code INTEGER,
        oil_rate_t REAL, choke_t REAL, WHP_t REAL, MFP_t REAL,
        S_P REAL, S_T REAL, S_GOR REAL, LGAS_P REAL, LGAS_rate REAL,
        API REAL, BSW_t REAL, P_Hour REAL, BSW_p REAL,
        UNIQUE(WEL_NAM, Z_COD, Field_Code))""")

    c.execute("""CREATE TABLE IF NOT EXISTS test_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        Field_Code INTEGER NOT NULL, prod_date TEXT NOT NULL,
        WEL_NAM TEXT NOT NULL, Z_COD TEXT NOT NULL, test_no INTEGER NOT NULL,
        Test_Date TEXT, oil_rate_t REAL, choke_t REAL, WHP_t REAL, MFP_t REAL,
        BHP REAL, S_P REAL, S_T REAL, S_GOR REAL, LGAS_P REAL, LGAS_rate REAL,
        API REAL, BSW_t REAL, BSW_p REAL, prod_hour REAL,
        UNIQUE(Field_Code, prod_date, WEL_NAM, Z_COD, test_no))""")

    c.execute("""CREATE TABLE IF NOT EXISTS cum_table (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        District TEXT, Field TEXT, Field_Code INTEGER NOT NULL,
        F_NO TEXT, WEL_NAM TEXT NOT NULL, Z_COD TEXT NOT NULL,
        DATE TEXT, C_DAY REAL, C_OL REAL, C_G REAL, C_WAT REAL,
        STAT TEXT, PLTFO TEXT,
        UNIQUE(WEL_NAM, Z_COD, Field_Code))""")

    c.execute("""CREATE TABLE IF NOT EXISTS monthly_production (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        Field_Code INTEGER NOT NULL, Field_Name TEXT, District TEXT,
        prod_date TEXT NOT NULL, m_oil REAL, m_gas REAL, m_water REAL,
        UNIQUE(Field_Code, prod_date))""")

    c.execute("""CREATE TABLE IF NOT EXISTS production (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        Field_Code     INTEGER NOT NULL, Field_Name TEXT, District TEXT,
        prod_date      TEXT    NOT NULL,
        WEL_NAM        TEXT    NOT NULL, Z_COD TEXT NOT NULL,
        status TEXT, choke_t REAL, WHP_t REAL, MFP_t REAL, BHP REAL,
        last_prod_date TEXT, prod_days REAL,
        m_oil REAL, m_gas REAL, m_water REAL,
        c_days REAL, cum_oil REAL, cum_gas REAL, cum_water REAL,
        oil_rate_avg REAL, oil_rate REAL, GOR_a REAL, API REAL, WC REAL,
        UNIQUE(Field_Code, prod_date, WEL_NAM, Z_COD))""")

    c.execute("""CREATE TABLE IF NOT EXISTS rs_code (
        Code_No INTEGER PRIMARY KEY,
        A REAL, B REAL, C REAL, D REAL, E REAL, F REAL, G REAL)""")

    conn.commit(); conn.close()


# ── Excel import ──────────────────────────────────────────────────────────────
def import_from_excel(folder):
    conn = get_connection()
    for tbl, file in [('test_data','Test_Data_1.xlsx'),
                      ('cum_table','Cum_Table.xlsx'),
                      ('rs_code','RS_Code.xlsx')]:
        df = pd.read_excel(f"{folder}/{file}")
        conn.execute(f"DELETE FROM {tbl}")
        df.to_sql(tbl, conn, if_exists='append', index=False)

    mdf = pd.read_excel(f"{folder}/Monthly_Data.xlsx")
    mdf.columns = [c.replace('\u200d','').strip() for c in mdf.columns]
    conn.execute("DELETE FROM monthly_production")
    mdf.to_sql('monthly_production', conn, if_exists='append', index=False)

    conn.commit(); conn.close()


# ── districts / fields ────────────────────────────────────────────────────────
def get_districts_fields():
    conn = get_connection()
    try:
        df = pd.read_sql(
            "SELECT DISTINCT District,Field_Name,Field_Code "
            "FROM monthly_production ORDER BY Field_Code", conn)
        df['District'] = df['District'].str.strip()
        result = {}
        for _, row in df.iterrows():
            result.setdefault(row['District'], []).append(
                (row['Field_Name'], int(row['Field_Code'])))
        return result if result else _fallback_districts()
    except Exception:
        return _fallback_districts()
    finally:
        conn.close()

def _fallback_districts():
    return {
        'Kharg':    [('Aboozar',110),('Soroosh_1',112),('Dorood',113),('Foroozan',114)],
        'Lavan':    [('Salman',220),('Resalat',221),('Reshadat',222),('Balal',223)],
        'Sirri':    [('Sirri_D',330),('Sirri_C',331),('Sirri_A',332),('Sirri_E',333),('Nosrat',338)],
        'Bahregan': [('Nowrooz_1',440),('Hendijan',441),('Bahregan_Sar',442),('Soroosh',443),('Nowrooz',444)],
        'Qeshm':    [('Hengam',550)],
    }


# ── test_data CRUD ────────────────────────────────────────────────────────────
def get_test_data(field_code):
    conn = get_connection()
    try:
        return pd.read_sql(
            "SELECT * FROM test_data WHERE Field_Code=? ORDER BY WEL_NAM",
            conn, params=(field_code,))
    except Exception: return pd.DataFrame()
    finally: conn.close()

def save_test_row(row_dict, field_code):
    conn = get_connection(); c = conn.cursor()
    c.execute("""INSERT OR REPLACE INTO test_data
        (District,Field,Field_Code,WEL_NAM,Z_COD,Test_Date,RS_Code,
         oil_rate_t,choke_t,WHP_t,MFP_t,S_P,S_T,S_GOR,LGAS_P,
         LGAS_rate,API,BSW_t,P_Hour,BSW_p)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        row_dict.get('District',''), row_dict.get('Field',''), field_code,
        row_dict.get('WEL_NAM',''), row_dict.get('Z_COD',''),
        row_dict.get('Test_Date',''), _int(row_dict.get('RS_Code')),
        *[_flt(row_dict.get(k)) for k in
          ('oil_rate_t','choke_t','WHP_t','MFP_t','S_P','S_T','S_GOR',
           'LGAS_P','LGAS_rate','API','BSW_t','P_Hour','BSW_p')]))
    conn.commit(); conn.close()

def delete_test_row(wel_nam, z_cod, field_code):
    conn = get_connection()
    conn.execute("DELETE FROM test_data WHERE WEL_NAM=? AND Z_COD=? AND Field_Code=?",
                 (wel_nam, z_cod, field_code))
    conn.commit(); conn.close()


# ── test_records ──────────────────────────────────────────────────────────────
def save_test_records(field_code, prod_date, wel_nam, z_cod, tests):
    conn = get_connection(); c = conn.cursor(); last = None
    for i, t in enumerate(tests):
        if not any(v for v in t.values()): continue
        last = t
        c.execute("""INSERT OR REPLACE INTO test_records
            (Field_Code,prod_date,WEL_NAM,Z_COD,test_no,Test_Date,
             oil_rate_t,choke_t,WHP_t,MFP_t,BHP,S_P,S_T,S_GOR,
             LGAS_P,LGAS_rate,API,BSW_t,BSW_p,prod_hour)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            field_code, str(prod_date), wel_nam, z_cod, i+1,
            t.get('Test_Date'),
            *[_flt(t.get(k)) for k in
              ('oil_rate_t','choke_t','WHP_t','MFP_t','BHP','S_P','S_T','S_GOR',
               'LGAS_P','LGAS_rate','API','BSW_t','BSW_p','prod_hour')]))
    conn.commit(); conn.close()
    return last

def get_test_records(field_code, prod_date, wel_nam, z_cod):
    conn = get_connection()
    try:
        df = pd.read_sql("""SELECT * FROM test_records
            WHERE Field_Code=? AND prod_date=? AND WEL_NAM=? AND Z_COD=?
            ORDER BY test_no""",
            conn, params=(field_code, str(prod_date), wel_nam, z_cod))
        recs = [{} for _ in range(3)]
        for _, row in df.iterrows():
            idx = int(row['test_no']) - 1
            if 0 <= idx < 3: recs[idx] = row.to_dict()
        return recs
    finally: conn.close()

def get_well_list(field_code):
    conn = get_connection()
    try:
        df = pd.read_sql(
            "SELECT WEL_NAM,Z_COD,F_NO,PLTFO,STAT FROM cum_table "
            "WHERE Field_Code=? ORDER BY WEL_NAM", conn, params=(field_code,))
        return df.to_dict('records')
    finally: conn.close()


# ── cum_table ─────────────────────────────────────────────────────────────────
def get_cum_table(field_code):
    conn = get_connection()
    try:
        return pd.read_sql(
            "SELECT * FROM cum_table WHERE Field_Code=? ORDER BY WEL_NAM",
            conn, params=(field_code,))
    except Exception: return pd.DataFrame()
    finally: conn.close()

def update_cum_table(prod_data, field_code, prod_date):
    conn = get_connection(); c = conn.cursor()
    for _, row in prod_data.iterrows():
        c.execute("""UPDATE cum_table SET C_DAY=?,C_OL=?,C_G=?,C_WAT=?,DATE=?
            WHERE WEL_NAM=? AND Z_COD=? AND Field_Code=?""",
            (_flt(row.get('c_days')), _flt(row.get('cum_oil')),
             _flt(row.get('cum_gas')), _flt(row.get('cum_water')),
             prod_date, str(row['WEL_NAM']), str(row['Z_COD']), field_code))
    conn.commit(); conn.close()


# ── monthly_production ────────────────────────────────────────────────────────
def get_monthly_production(field_code, prod_date=None):
    conn = get_connection()
    try:
        if prod_date:
            c = conn.cursor()
            c.execute("SELECT * FROM monthly_production WHERE Field_Code=? AND prod_date=?",
                      (field_code, str(prod_date)))
            row = c.fetchone()
            return dict(zip([d[0] for d in c.description], row)) if row else None
        else:
            df = pd.read_sql(
                "SELECT * FROM monthly_production WHERE Field_Code=? "
                "ORDER BY prod_date DESC LIMIT 1", conn, params=(field_code,))
            return df.iloc[0].to_dict() if len(df) > 0 else None
    finally: conn.close()

def save_monthly_production(data):
    conn = get_connection()
    conn.execute("""INSERT OR REPLACE INTO monthly_production
        (Field_Code,Field_Name,District,prod_date,m_oil,m_gas,m_water)
        VALUES(?,?,?,?,?,?,?)""",
        (data['Field_Code'], data.get('Field_Name',''), data.get('District',''),
         str(data['prod_date']), _flt(data.get('m_oil')),
         _flt(data.get('m_gas')), _flt(data.get('m_water'))))
    conn.commit(); conn.close()

def get_rs_codes():
    conn = get_connection()
    try: return pd.read_sql("SELECT * FROM rs_code", conn)
    finally: conn.close()


# ── production table ──────────────────────────────────────────────────────────
PROD_COLS = ['Field_Code','Field_Name','District','prod_date','WEL_NAM','Z_COD',
             'status','choke_t','WHP_t','MFP_t','BHP','last_prod_date','prod_days',
             'm_oil','m_gas','m_water','c_days','cum_oil','cum_gas','cum_water',
             'oil_rate_avg','oil_rate','GOR_a','API','WC']

def save_production(df, field_code, prod_date, field_name, district):
    """Upsert allocated rows into the production table."""
    conn = get_connection(); c = conn.cursor()
    for _, row in df.iterrows():
        c.execute("""INSERT OR REPLACE INTO production
            (Field_Code,Field_Name,District,prod_date,WEL_NAM,Z_COD,
             status,choke_t,WHP_t,MFP_t,BHP,last_prod_date,prod_days,
             m_oil,m_gas,m_water,c_days,cum_oil,cum_gas,cum_water,
             oil_rate_avg,oil_rate,GOR_a,API,WC)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (field_code, field_name, district, str(prod_date),
             str(row['WEL_NAM']), str(row['Z_COD']), str(row.get('status','')),
             _flt(row.get('choke_t')),  _flt(row.get('WHP_t')),
             _flt(row.get('MFP_t')),    _flt(row.get('BHP')),
             str(row.get('last_prod_date','')), _flt(row.get('prod_days')),
             _flt(row.get('m_oil')),    _flt(row.get('m_gas')),
             _flt(row.get('m_water')),  _flt(row.get('c_days')),
             _flt(row.get('cum_oil')),  _flt(row.get('cum_gas')),
             _flt(row.get('cum_water')),_flt(row.get('oil_rate_avg')),
             _flt(row.get('oil_rate')), _flt(row.get('GOR_a')),
             _flt(row.get('API')),      _flt(row.get('WC'))))
    conn.commit(); conn.close()

def get_production(field_code, prod_date):
    conn = get_connection()
    try:
        return pd.read_sql(
            "SELECT * FROM production WHERE Field_Code=? AND prod_date=? ORDER BY WEL_NAM",
            conn, params=(field_code, str(prod_date)))
    except Exception: return pd.DataFrame()
    finally: conn.close()

def get_production_dates(field_code):
    """Return sorted list of prod_date strings available in production table."""
    conn = get_connection()
    try:
        df = pd.read_sql(
            "SELECT DISTINCT prod_date FROM production WHERE Field_Code=? ORDER BY prod_date DESC",
            conn, params=(field_code,))
        return df['prod_date'].tolist()
    except Exception: return []
    finally: conn.close()

def get_reservoir_summary(field_code, prod_date):
    """Aggregate production by Z_COD for a field+month."""
    conn = get_connection()
    try:
        return pd.read_sql("""
            SELECT Z_COD,
                   COUNT(*) as wells,
                   SUM(CASE WHEN prod_days>0 THEN 1 ELSE 0 END) as active_wells,
                   SUM(m_oil)   as m_oil,   SUM(m_gas)   as m_gas,
                   SUM(m_water) as m_water,  SUM(cum_oil) as cum_oil,
                   SUM(cum_gas) as cum_gas,  SUM(cum_water) as cum_water,
                   AVG(CASE WHEN GOR_a>0 THEN GOR_a END) as avg_GOR,
                   AVG(CASE WHEN WC>0 THEN WC END) as avg_WC
            FROM production WHERE Field_Code=? AND prod_date=?
            GROUP BY Z_COD ORDER BY m_oil DESC""",
            conn, params=(field_code, str(prod_date)))
    except Exception: return pd.DataFrame()
    finally: conn.close()

def get_district_field_summary(district, prod_date):
    """Aggregate production by field for a district+month."""
    conn = get_connection()
    try:
        return pd.read_sql("""
            SELECT Field_Name, Field_Code,
                   COUNT(*) as wells,
                   SUM(CASE WHEN prod_days>0 THEN 1 ELSE 0 END) as active_wells,
                   SUM(m_oil)   as m_oil,   SUM(m_gas)   as m_gas,
                   SUM(m_water) as m_water,  SUM(cum_oil) as cum_oil,
                   SUM(cum_gas) as cum_gas,  SUM(cum_water) as cum_water
            FROM production WHERE District=? AND prod_date=?
            GROUP BY Field_Name, Field_Code ORDER BY m_oil DESC""",
            conn, params=(district, str(prod_date)))
    except Exception: return pd.DataFrame()
    finally: conn.close()

def production_exists(field_code, prod_date):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM production WHERE Field_Code=? AND prod_date=?",
                  (field_code, str(prod_date)))
        return c.fetchone()[0] > 0
    finally: conn.close()


# ── generic table viewer ──────────────────────────────────────────────────────
VIEWABLE_TABLES = {
    'Test Data':          'test_data',
    'Monthly Production': 'monthly_production',
    'Production':         'production',
}

def get_table_df(table_name, field_code=None):
    conn = get_connection()
    try:
        if field_code:
            return pd.read_sql(
                f"SELECT * FROM {table_name} WHERE Field_Code=?",
                conn, params=(field_code,))
        return pd.read_sql(f"SELECT * FROM {table_name}", conn)
    except Exception: return pd.DataFrame()
    finally: conn.close()

def update_table_row(table_name, row_id, col, value):
    conn = get_connection()
    conn.execute(f"UPDATE {table_name} SET {col}=? WHERE id=?", (value, row_id))
    conn.commit(); conn.close()

def delete_table_row(table_name, row_id):
    conn = get_connection()
    conn.execute(f"DELETE FROM {table_name} WHERE id=?", (row_id,))
    conn.commit(); conn.close()

def insert_table_row(table_name, data_dict):
    data_dict.pop('id', None)
    cols = ', '.join(data_dict.keys())
    placeholders = ', '.join(['?'] * len(data_dict))
    conn = get_connection()
    conn.execute(f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})",
                 list(data_dict.values()))
    conn.commit(); conn.close()


# ── helpers ───────────────────────────────────────────────────────────────────
def _flt(v):
    try:
        f = float(v); return None if math.isnan(f) else f
    except (TypeError, ValueError): return None

def _int(v):
    try: return int(float(v))
    except (TypeError, ValueError): return None


def get_latest_test_per_well(field_code):
    """
    Return one row per well+formation containing the most recently entered
    test record.  Prefers test_records (up to 3 tests/month); falls back to
    test_data when no test_records exist for the field.
    """
    conn = get_connection()
    try:
        # Pick the highest test_no per well — that is the last test entered
        df = pd.read_sql("""
            SELECT tr.*
            FROM test_records tr
            INNER JOIN (
                SELECT WEL_NAM, Z_COD, MAX(test_no) AS max_tn
                FROM test_records
                WHERE Field_Code = ?
                GROUP BY WEL_NAM, Z_COD
            ) mx
              ON  tr.WEL_NAM  = mx.WEL_NAM
             AND  tr.Z_COD    = mx.Z_COD
             AND  tr.test_no  = mx.max_tn
             AND  tr.Field_Code = ?
            ORDER BY tr.WEL_NAM
        """, conn, params=(field_code, field_code))

        if not df.empty:
            return df

        # Fall back: test_data already holds one (latest) row per well
        return pd.read_sql(
            "SELECT * FROM test_data WHERE Field_Code=? ORDER BY WEL_NAM",
            conn, params=(field_code,))
    except Exception:
        try:
            return pd.read_sql(
                "SELECT * FROM test_data WHERE Field_Code=? ORDER BY WEL_NAM",
                conn, params=(field_code,))
        except Exception:
            return pd.DataFrame()
    finally:
        conn.close()


# ── latest test per well (for Test Report) ────────────────────────────────────
def get_latest_tests(field_code):
    """
    For each (WEL_NAM, Z_COD) return the single test row that has the
    most recent Test_Date, drawn from EITHER table:

      test_records  – tests entered via the GUI (may have multiple per well)
      test_data     – tests imported from Excel (one row per well)

    Logic per well:
      • If test_records contains a later Test_Date than test_data → use that row
      • Otherwise keep the test_data row
    This ensures the very latest test is always shown, regardless of source.
    """
    conn = get_connection()
    try:
        # ── Step 1: latest row per well from test_records ──────────────
        rec_df = pd.read_sql("""
            SELECT tr.*
            FROM   test_records tr
            INNER JOIN (
                SELECT WEL_NAM, Z_COD, MAX(Test_Date) AS latest
                FROM   test_records
                WHERE  Field_Code = ?
                  AND  Test_Date  IS NOT NULL
                  AND  Test_Date  != ''
                GROUP  BY WEL_NAM, Z_COD
            ) m ON tr.WEL_NAM   = m.WEL_NAM
               AND tr.Z_COD     = m.Z_COD
               AND tr.Test_Date = m.latest
            WHERE  tr.Field_Code = ?
        """, conn, params=(field_code, field_code))

        # ── Step 2: test_data (one row per well, already the latest import) ──
        td_df = pd.read_sql(
            "SELECT * FROM test_data WHERE Field_Code=? ORDER BY WEL_NAM",
            conn, params=(field_code,))

        if rec_df.empty:
            return td_df          # no GUI entries yet → use Excel data

        # ── Step 3: normalise test_records columns to match test_data ──
        rec_df = rec_df.rename(columns={"prod_hour": "P_Hour"})

        # ── Step 4: merge and pick the row with the later Test_Date ────
        rows = []
        for _, td_row in td_df.iterrows():
            wn, zc = td_row["WEL_NAM"], td_row["Z_COD"]
            mask   = (rec_df["WEL_NAM"] == wn) & (rec_df["Z_COD"] == zc)
            rec_match = rec_df[mask]

            if rec_match.empty:
                rows.append(td_row)          # no GUI entry → keep Excel row
                continue

            rec_best = rec_match.iloc[0]     # already the latest (MAX above)
            # Compare dates as strings (YYYYMMDD lexicographic order works)
            td_date  = str(td_row.get("Test_Date",  "") or "")
            rec_date = str(rec_best.get("Test_Date", "") or "")

            if rec_date >= td_date:
                rows.append(rec_best)        # GUI test is newer
            else:
                rows.append(td_row)          # Excel test is still more recent

        result = pd.DataFrame(rows).reset_index(drop=True)
        return result.sort_values(["WEL_NAM", "Z_COD"]).reset_index(drop=True)

    except Exception:
        pass
    finally:
        conn.close()

    return get_test_data(field_code)