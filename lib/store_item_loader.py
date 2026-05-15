"""Shared loader for Store Item xlsx files — MTHAI only.

Used by:
  - generate_store_item_dashboard.py  (standalone HTML export)
  - scripts/import_store_items.py     (DB import)
"""
import re
import numpy as np
import pandas as pd
from pathlib import Path

BASE = Path(r"D:\claude\Project\raw\Store item")

MONTH_ORDER = [
    "Jan'25","Feb'25","Mar'25","Apr'25","May'25","Jun'25",
    "Jul'25","Aug'25","Sep'25","Oct'25","Nov'25",
    "Dec'25","Jan'26","Feb'26","Mar'26","Apr'26",
]
ASO_MONTHS = [m for m in MONTH_ORDER if m.endswith("'25")]

# ── Column name normalizer ────────────────────────────────────────────────────
COL_MAP = {
    "item":             "Item",
    "item (child)":     "Item",
    "item(child)":      "Item",
    "description":      "Description",
    "process":          "Process",
    "machine model":    "Machine_model",
    "category":         "Category",
    "qty":              "Quantity",
    "cost":             "Cost",
    "unit price":       "Cost",
    "total":            "Total",
    "amount usd":       "Total",
}

TARGETS  = ["Item","Description","Process","Machine_model","Category","Quantity","Cost","Total"]
QTY_KEYS = {"quantity", "quantity.1", "quantity (child)", "quantity (child).1"}

# ── Value normalization maps ──────────────────────────────────────────────────
PROCESS_MAP = {
    "trim&form":         "Trim & Form",
    "trim & form":       "Trim & Form",
    "tf":                "Trim & Form",
    "wire bond":         "Wire Bond",
    "die attach & cure": "Die Attach & Cure",
    "die attach":        "Die Attach & Cure",
    "mold":              "Mold",
    "plating":           "Plating",
    "marker":            "Marker",
    "saw eol":           "Saw EOL",
    "saw fol":           "Saw FOL",
    "back grind":        "Back Grind",
    "back grinding":     "Back Grind",
    "screen print":      "Screen Print",
    "wafer mount":       "Wafer Mount",
    "common parts":      "Common Parts",
    "assembly":          "Common Parts",
}

CATEGORY_MAP = {
    "emergency":   "Emergency",
    "consumable":  "Consumable",
    "consume":     "Consumable",
    "jit":         "JIT",
    "consignment": "Consignment",
    "critical":    "Emergency",
}

SHEET_TO_MONTH = {
    "jan 2025": "Jan'25", "jan": "Jan'25",
    "feb": "Feb'25", "mar": "Mar'25", "apr": "Apr'25", "may": "May'25",
    "jun": "Jun'25", "jul": "Jul'25", "aug": "Aug'25",
    "sep": "Sep'25", "oct": "Oct'25", "nov": "Nov'25",
}

_MN = {
    "jan":"Jan","feb":"Feb","mar":"Mar","apr":"Apr","may":"May","jun":"Jun",
    "jul":"Jul","aug":"Aug","sep":"Sep","oct":"Oct","nov":"Nov","dec":"Dec",
}


def map_cols(df: pd.DataFrame) -> pd.DataFrame:
    result = {}
    qty_candidates = {}
    for i, col in enumerate(df.columns):
        key = str(col).strip().lower()
        if key in QTY_KEYS:
            qty_candidates[i] = df.iloc[:, i]
        else:
            target = COL_MAP.get(key)
            if target in TARGETS:
                result[target] = df.iloc[:, i]
    if qty_candidates:
        best = max(qty_candidates.items(),
                   key=lambda kv: pd.to_numeric(kv[1], errors='coerce').notna().sum())
        result["Quantity"] = best[1]
    return pd.DataFrame(result)


def detect_header(path, sheet: str) -> int:
    for hdr in range(4):
        try:
            tmp = pd.read_excel(path, sheet_name=sheet, header=hdr, nrows=0, engine='openpyxl')
            lc = [str(c).strip().lower() for c in tmp.columns]
            if any("item" in c or "description" in c for c in lc):
                return hdr
        except Exception:
            pass
    return 0


def parse_month(fname: str):
    m = re.search(r"ASSY\s+([A-Za-z]+)'(\d{2})", fname, re.IGNORECASE)
    if not m:
        return None
    name = _MN.get(m.group(1).lower())
    return f"{name}'{m.group(2)}" if name else None


def load_aso2025() -> pd.DataFrame:
    path = BASE / "Issue cost ASO 2025.xlsx"
    if not path.exists():
        print(f"  [ASO2025] file not found: {path}")
        return pd.DataFrame()
    xl = pd.ExcelFile(path, engine='openpyxl')
    frames = []
    for sheet in xl.sheet_names:
        month = SHEET_TO_MONTH.get(sheet.strip().lower())
        if not month:
            print(f"  [ASO2025] skip: {sheet!r}")
            continue
        hdr = detect_header(path, sheet)
        df  = pd.read_excel(path, sheet_name=sheet, header=hdr, engine='openpyxl')
        df  = map_cols(df)
        df["Month"]  = month
        df["Source"] = "ASO2025"
        frames.append(df)
        print(f"  [ASO2025] {sheet!r} → {month}: {len(df)} rows")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def load_sum_assy() -> pd.DataFrame:
    frames = []
    for fpath in sorted(BASE.glob("SUM ISSUED ASSY *.xlsx")):
        if fpath.name.startswith("~$"):
            continue
        month = parse_month(fpath.name)
        if not month:
            print(f"  [SUM_ASSY] cannot parse month: {fpath.name!r}")
            continue
        xl    = pd.ExcelFile(fpath, engine='openpyxl')
        sheet = next((s for s in xl.sheet_names if s.strip().upper() in ("MTAI","MTHAI")), None)
        if not sheet:
            print(f"  [SUM_ASSY] no MTAI/MTHAI sheet: {fpath.name!r}")
            continue
        hdr = detect_header(fpath, sheet)
        df  = pd.read_excel(fpath, sheet_name=sheet, header=hdr, engine='openpyxl')
        df  = map_cols(df)
        df["Month"]  = month
        df["Source"] = "SUM_ASSY"
        frames.append(df)
        print(f"  [SUM_ASSY] {fpath.name!r} ({sheet}) → {month}: {len(df)} rows")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    for c in ["Item","Description","Process","Machine_model","Category"]:
        if c not in df.columns:
            df[c] = ""
        df[c] = (df[c].astype(str)
                 .str.strip()
                 .str.replace('\xa0', '', regex=False)
                 .str.replace('\n', ' ', regex=False)
                 .replace({'nan': '', 'None': '', '<NA>': ''}))

    df["Process"]  = df["Process"].apply(
        lambda v: PROCESS_MAP.get(v.strip().lower(), v.strip()) if v.strip() else "Unknown")
    df["Category"] = df["Category"].apply(
        lambda v: CATEGORY_MAP.get(v.strip().lower(), v.strip()) if v.strip() else "Unknown")

    df["Total"]    = pd.to_numeric(df.get("Total",    pd.Series(dtype=float)), errors='coerce').fillna(0)
    df["Quantity"] = pd.to_numeric(df.get("Quantity", pd.Series(dtype=float)), errors='coerce').fillna(0).round().astype(int)
    df["Cost"]     = pd.to_numeric(df.get("Cost",     pd.Series(dtype=float)), errors='coerce').fillna(0)

    mask = (df["Cost"] == 0) & (df["Quantity"] > 0)
    df.loc[mask, "Cost"] = (df.loc[mask, "Total"] / df.loc[mask, "Quantity"]).round(4)

    SKIP_ITEMS = {'grand total','total','subtotal','sub total','grand  total','รวม','sum'}
    df = df[
        df["Item"].str.strip().ne("") &
        df["Description"].str.strip().ne("") &
        df["Process"].ne("Unknown") &
        df["Total"].gt(0) &
        ~df["Item"].str.strip().str.lower().isin(SKIP_ITEMS)
    ].reset_index(drop=True)

    known = set(MONTH_ORDER)
    df = df[df["Month"].isin(known)].reset_index(drop=True)
    df["Month"] = pd.Categorical(df["Month"], categories=MONTH_ORDER, ordered=True)
    return df.sort_values("Month").reset_index(drop=True)
