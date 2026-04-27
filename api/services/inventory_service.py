"""Inventory service — mirrors dashboard/pages/inventory.py _load_machines()
data-shaping logic so the dashboard can consume a single pre-processed list.
"""
import logging
import pandas as pd

log = logging.getLogger(__name__)


def _df_to_records(df: pd.DataFrame) -> list:
    if df is None or df.empty:
        return []
    out = []
    for _, r in df.iterrows():
        row = {}
        for k, v in r.items():
            if v is None:
                row[k] = None
            elif isinstance(v, float) and pd.isna(v):
                row[k] = None
            elif hasattr(v, 'item'):
                try:
                    row[k] = v.item()
                except Exception:
                    row[k] = str(v)
            elif isinstance(v, pd.Timestamp):
                row[k] = v.isoformat()
            else:
                row[k] = v
        out.append(row)
    return out


MODEL_NAME_MAP = {
    'GP-PRO SP80N':    'GP-PRO8 SP80N',
    'GP-PRO-8 SP80N':  'GP-PRO8 SP80N',
    'GP-PRO-8-SP80N':  'GP-PRO8 SP80N',
    'GP-PRO8-SP80N':   'GP-PRO8 SP80N',
    'GP-PRO-8-SP170N': 'GP-PRO8 SP170N',
    'GP-PRO8-SP170N':  'GP-PRO8 SP170N',
    'DP80-8-MOUT':     'DP80-8-M',
    'GP-ELF-D24084':   'GP-ELF',
}


def get_inventory_machines() -> dict:
    """Return shaped inventory list matching dashboard _load_machines() output.

    - Filters out deleted machines (flag_delete != 1)
    - Excludes MOLD sub-machines (Press 1-4, L/R suffix)
    - For WB: counts heads rather than bases (L/R heads replace base when
      the base has L/R children; key status is inherited from the base)
    - Normalizes model name variants
    """
    from db import query_df
    from utils.queries import inventory_all_machines

    df = query_df(inventory_all_machines())
    if df.empty:
        return {'machines': [], 'total': 0}

    # Normalize dtypes (SQL bit can come back as float/object)
    for col in ['flag_key', 'flag_automotive', 'flag_gold', 'flag_pm', 'flag_downtime']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
    for col in ['model', 'mfg', 'code_machine', 'des_machine', 'short_name', 'id_operation']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace('nan', '')

    if 'model' in df.columns:
        df['model'] = df['model'].replace(MODEL_NAME_MAP)

    # MOLD: exclude sub-machines (Press 1-4, L/R suffixes)
    mold_mask = df['id_operation'] == 'MOLD'
    sub_pattern = r'(?i)(\s+Press\s*\d+|L|R)$'
    mold_sub = mold_mask & df['code_machine'].str.contains(sub_pattern, regex=True, na=False)
    df = df[~mold_sub]

    # WB: L/R heads replace bases when base has L/R children
    wb_mask = df['id_operation'] == 'WB'
    wb_all = query_df(inventory_all_machines())
    wb_all_lr = wb_all[
        (wb_all['id_operation'] == 'WB')
        & wb_all['code_machine'].astype(str).str.strip().str.match(r'.*[LR]$', na=False)
    ].copy()
    wb_all_lr['base_name'] = wb_all_lr['code_machine'].astype(str).str.strip().str[:-1]
    bases_with_lr = set(wb_all_lr['base_name'].unique())

    # Remove WB bases that have L/R heads (replace with L/R rows)
    wb_base_to_remove = wb_mask & df['code_machine'].isin(bases_with_lr)
    df = df[~wb_base_to_remove]

    # Add L/R heads whose base is key=1 (even if the L/R row itself is flag_key=0)
    all_wb_key = set(query_df("""
        SELECT code_machine FROM dbo.machine
        WHERE id_operation = 'WB' AND flag_key = 1
    """)['code_machine'].str.strip().tolist())
    key_bases_with_lr = bases_with_lr & all_wb_key

    lr_to_add = wb_all_lr[wb_all_lr['base_name'].isin(key_bases_with_lr)].copy()
    if not lr_to_add.empty:
        lr_to_add = lr_to_add.drop(columns=['base_name'])
        for col in ['flag_key', 'flag_automotive', 'flag_gold', 'flag_pm', 'flag_downtime']:
            if col in lr_to_add.columns:
                lr_to_add[col] = pd.to_numeric(
                    lr_to_add[col], errors='coerce').fillna(0).astype(int)
        for col in ['model', 'mfg', 'code_machine', 'des_machine', 'short_name', 'id_operation']:
            if col in lr_to_add.columns:
                lr_to_add[col] = lr_to_add[col].astype(str).str.strip().replace('nan', '')
        lr_to_add['flag_key'] = 1
        common_cols = [c for c in df.columns if c in lr_to_add.columns]
        df = pd.concat([df, lr_to_add[common_cols]], ignore_index=True)

    return {'machines': _df_to_records(df), 'total': int(len(df))}


def get_inventory_downtime() -> dict:
    """Per-machine downtime KPIs for the inventory treemap.

    Wraps utils.queries.inventory_machine_downtime() — SQL only (no Oracle
    merge) matching the dashboard behaviour.
    """
    from db import query_df
    from utils.queries import inventory_machine_downtime
    df = query_df(inventory_machine_downtime())
    return {'rows': _df_to_records(df), 'total': int(len(df))}
