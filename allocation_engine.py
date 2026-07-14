# -*- coding: utf-8 -*-
"""
allocation_engine.py  –  Core allocation logic.

Two-phase design:
  1. compute_allocation(field_code, prod_date_yyyymm)
       Runs the maths; returns (df, prod_data, district, field_name, formatted_date).
       Does NOT touch the database.

  2. save_allocation(df, prod_data, field_code, prod_date_raw,
                     current_prod_date, field_name, district)
       Persists results to `production` table and updates `cum_table`.

  run_allocation(field_code, prod_date_yyyymm)
       Convenience wrapper that calls both phases (used by older callers).
"""

import numpy as np, pandas as pd
import db_manager as db


def persian_month_days(month: int) -> int:
    if 1 <= month <= 6:  return 31
    elif 7 <= month <= 11: return 30
    else: return 29


def _calc_RS(row) -> float:
    if row['RS_Code'] != 9:
        return (row['A']*row['S_P']**3 + row['B']*row['S_P']**2 +
                row['C']*row['S_P'] + row['D'] + row['E']*row['S_T'] +
                row['F']*row['S_T']**2 + row['G']*row['S_T']*row['S_P'])
    sp = row['S_P'] + 14.7
    return row['A']*sp**3 + row['B']*sp**2 + row['C']*sp + row['D']


def _calc_GOR(row) -> float:
    if row['S_GOR'] == 0: return 0.0
    g = (row['S_GOR']*row['oil_rate_t'] -
         row['LGAS_rate']*1_000_000) / (row['oil_rate_t'] + row['RS'])
    return g if g >= 0 else np.nan


# ── phase 1 ───────────────────────────────────────────────────────────────────
def compute_allocation(field_code: int, prod_date_yyyymm: str):
    """
    Compute allocation without saving.
    Returns (df, prod_data, district, field_name, formatted_prod_date).
    `prod_data` is the full intermediate DataFrame needed for cum_table update.
    """
    test_data  = db.get_test_data(field_code)
    cum_data   = db.get_cum_table(field_code)
    month_row  = db.get_monthly_production(field_code, prod_date_yyyymm)
    RS_Code_df = db.get_rs_codes()

    if test_data.empty:
        raise ValueError(f"No test data for field {field_code}. Import Excel first.")
    if month_row is None:
        raise ValueError(f"No monthly production entry for field {field_code} / {prod_date_yyyymm}.")
    if cum_data.empty:
        raise ValueError(f"No cumulative data for field {field_code}.")

    m_oil, m_gas, m_water = (float(month_row[k]) for k in ('m_oil','m_gas','m_water'))
    raw          = str(int(float(month_row['prod_date'])))
    formatted    = raw[:4] + "/" + raw[4:]
    month_days   = persian_month_days(int(raw[4:]))
    district     = str(month_row.get('District','')).strip().replace('\u200d','')
    field_name   = str(month_row.get('Field_Name','')).strip()

    p = test_data.copy()
    p['prod_days']      = p['P_Hour'] / 24
    p['cum_test_based'] = p['prod_days'] * p['oil_rate_t']

    mg = pd.merge(p, RS_Code_df, left_on='RS_Code', right_on='Code_No', how='left')
    p['RS']        = mg.apply(_calc_RS, axis=1)
    p['LGAS_rate'] = p['LGAS_rate'].fillna(0)
    p['GOR']       = p.apply(_calc_GOR, axis=1)

    total = p['cum_test_based'].sum()
    p['allocation_ratio'] = p['cum_test_based'] / total
    p['m_oil'] = p['allocation_ratio'] * m_oil

    p['_mg_tb'] = p['m_oil'] * p['GOR']
    gs = p['_mg_tb'].sum()
    p['m_gas'] = (p['_mg_tb'] / gs * m_gas) if gs > 0 else 0.0

    p['_mw_tb'] = p['m_oil'] * (p['BSW_p'] / (100 - p['BSW_p']))
    ws = p['_mw_tb'].sum()
    p['m_water'] = (p['_mw_tb'] / ws * m_water) if ws > 0 else 0.0

    p['oil_rate']     = p['m_oil'] / p['prod_days']
    p['oil_rate_avg'] = np.where(p['prod_days'] > 0, p['m_oil'] / month_days, np.nan)
    p['GOR_a']        = p['m_gas'] / p['m_oil'] * 1_000_000
    p['WC']           = p['m_water'] * 100 / (p['m_water'] + p['m_oil'])

    cum_f = cum_data[['WEL_NAM','Z_COD','C_DAY','C_OL','C_G','C_WAT','DATE','STAT']].copy()
    p = pd.merge(p, cum_f, on=['WEL_NAM','Z_COD'], how='left')

    p['c_days']    = p['C_DAY'] + p['prod_days']
    p['cum_oil']   = p['C_OL']  + p['m_oil']
    p['cum_gas']   = p['C_G']   + p['m_gas']
    p['cum_water'] = p['C_WAT'] + p['m_water']

    p['last_prod_date'] = np.where(p['P_Hour'] > 0, formatted, p['DATE'])
    p = p.sort_values('WEL_NAM').reset_index(drop=True)
    p['status'] = p['STAT'].fillna('')
    p['BHP']    = np.nan

    gas_set = {'m_gas','cum_gas'}
    for col in ['choke_t','WHP_t','MFP_t','prod_days','m_oil','m_gas','m_water',
                'c_days','cum_oil','cum_gas','cum_water',
                'oil_rate_avg','oil_rate','GOR_a','API','WC']:
        if col in p.columns:
            p[col] = p[col].round(2 if col in gas_set else 1)

    df = p[['WEL_NAM','Z_COD','status','choke_t','WHP_t','MFP_t','BHP',
            'last_prod_date','prod_days','m_oil','m_gas','m_water',
            'c_days','cum_oil','cum_gas','cum_water',
            'oil_rate_avg','oil_rate','GOR_a','API','WC']].copy()

    return df, p, district, field_name, formatted


# ── phase 2 ───────────────────────────────────────────────────────────────────
def save_allocation(df, prod_data, field_code, prod_date_raw,
                    current_prod_date, field_name, district):
    """Save allocation results to `production` table and update `cum_table`."""
    db.save_production(df, field_code, prod_date_raw, field_name, district)
    db.update_cum_table(prod_data, field_code, current_prod_date)


# ── convenience wrapper ───────────────────────────────────────────────────────
def run_allocation(field_code: int, prod_date_yyyymm: str = None):
    """Compute + save in one call. Returns (df, district, field_name, prod_date)."""
    if prod_date_yyyymm is None:
        row = db.get_monthly_production(field_code)
        if row is None:
            raise ValueError(f"No monthly production data for field {field_code}.")
        prod_date_yyyymm = str(int(float(row['prod_date'])))

    df, prod_data, district, field_name, formatted = compute_allocation(
        field_code, prod_date_yyyymm)
    save_allocation(df, prod_data, field_code, prod_date_yyyymm,
                    formatted, field_name, district)
    return df, district, field_name, formatted
