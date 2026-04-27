import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.formatting.rule import CellIsRule, DataBarRule

# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ══════════════════════════════════════════════════════════════════════════════
SRC = 'raw/Wire bond_UPH_DRR.xlsx'

# Canonical model order used across all sheets
UPH_MODELS = ['AB339', 'Eagle/Eagle60', 'Harrier', 'Aero Twin',
              'Extreme GoCU', 'TwinEagleExtream', 'Egle Aero GoCU']

def load_uph_table(sheet_name):
    raw = pd.read_excel(SRC, sheet_name=sheet_name, header=None)
    df = raw.iloc[4:, 1:].copy()
    df.columns = list(raw.iloc[3, 1:])
    df = df[df['PKG'].notna()].reset_index(drop=True)
    # Reorder to canonical model order (Gold table has different column order)
    for m in UPH_MODELS:
        if m in df.columns:
            df[m] = pd.to_numeric(df[m], errors='coerce')
        else:
            df[m] = 0
    return df[['PKG', 'Std#wire'] + UPH_MODELS]

uph_cu = load_uph_table('MTHAI_Tbl#11_WB_CopperSingledie')
uph_au = load_uph_table('MTHAI_Tbl#08_WB_AuSingledie')
print(f'UPH Cu packages: {len(uph_cu)}, Au packages: {len(uph_au)}')

# ── Package name normalization ───────────────────────────────────────────────
def norm(s, strip_wp=False):
    s = re.sub(r'\(.*?\)', '', str(s).upper().strip())
    s = re.sub(r'(?<=[0-9])L(?=[A-Z])', '', s)
    s = re.sub(r'(?<=[0-9])L(?=\s)', '', s)
    s = re.sub(r'_TA[0-9]+', '', s)
    s = re.sub(r'\s+', '', s).replace('-', '').replace('_', '')
    if strip_wp:
        s = re.sub(r'[WP]+$', '', s)
    return s.strip()

TQFP_MAP = {
    '32TQFP': '32TQFP 7X7', '48TQFP': '48TQFP 7X7',
    '44TQFP': '44TQFP 10X10', '64TQFP': '64TQFP 10X10',
    '80TQFP': '80TQFP 12X12', '100TQFP': '100TQFP 12X12',
    '8SOICIDF': '8SOIC-HD', '20SSOPUD': '20SSOP-HD', '8EIAJ': None,
}

uph_norm  = {norm(p): p for p in uph_cu['PKG']}
uph_norm2 = {norm(p, True): p for p in uph_cu['PKG']}

def find_uph_pkg(raw):
    n = norm(raw)
    if n in uph_norm: return uph_norm[n]
    if n in TQFP_MAP:
        m = TQFP_MAP[n]
        if m: return uph_norm.get(norm(m)) or uph_norm2.get(norm(m, True))
        return None
    n2 = re.sub(r'[WP]+$', '', n)
    return uph_norm.get(n2) or uph_norm2.get(n2)

# ── WW#04 Loading Plan + Wire Type ──────────────────────────────────────────
ww_raw = pd.read_excel(SRC, sheet_name='WW#04', header=None)
SKIP = {'PLAN', 'Total (k)', 'Grand Total (K)', 'Die bonder 115 M/C', 'Wire bonder 688 M/C'}
ww_rows = []
for _, row in ww_raw.iterrows():
    pkg = str(row[0]).strip() if pd.notna(row[0]) else ''
    drr = row[2]
    copper_drr = row[19]  # Copper column
    if pkg and pkg not in SKIP and isinstance(drr, (int, float)) and not pd.isna(drr):
        uph_pkg = find_uph_pkg(pkg)
        cu_val = float(copper_drr) if pd.notna(copper_drr) and isinstance(copper_drr, (int, float)) else 0
        wire = 'Cu' if cu_val > 0 else 'Au'
        ww_rows.append({'pkg_ww': pkg, 'drr_k': float(drr), 'uph_pkg': uph_pkg,
                        'copper_k': cu_val, 'wire_type': wire})
ww_df = pd.DataFrame(ww_rows)

# Aggregate by uph_pkg
ww_agg = (ww_df.groupby('uph_pkg', dropna=False)
                .agg(drr_k=('drr_k', 'sum'),
                     copper_k=('copper_k', 'sum'),
                     ww_pkgs=('pkg_ww', lambda x: ' / '.join(sorted(set(x)))))
                .reset_index())
# Wire type for aggregated: if any copper > 0
ww_agg['wire_type'] = ww_agg['copper_k'].apply(lambda x: 'Cu' if x > 0 else 'Au')

# Merge with UPH data (use Cu table for matching — same PKG names)
calc = ww_agg[ww_agg['uph_pkg'].notna()].merge(
    uph_cu[['PKG', 'Std#wire']].rename(columns={'PKG': 'uph_pkg'}),
    on='uph_pkg', how='left'
)

# For each model, add both Cu and Au UPH so we can pick based on wire_type
for m in UPH_MODELS:
    cu_lookup = dict(zip(uph_cu['PKG'], uph_cu[m]))
    au_lookup = dict(zip(uph_au['PKG'], uph_au[m]))
    calc[f'{m}_cu'] = calc['uph_pkg'].map(cu_lookup).fillna(0)
    calc[f'{m}_au'] = calc['uph_pkg'].map(au_lookup).fillna(0)
    # Select UPH based on wire_type
    calc[m] = calc.apply(lambda r: r[f'{m}_cu'] if r['wire_type'] == 'Cu' else r[f'{m}_au'], axis=1)

# Add unmatched rows
unmatched = ww_df[ww_df['uph_pkg'].isna() & (ww_df['drr_k'] > 0)]
for _, row in unmatched.iterrows():
    entry = {'uph_pkg': row['pkg_ww'] + ' (unmapped)', 'drr_k': row['drr_k'],
             'copper_k': row['copper_k'], 'ww_pkgs': row['pkg_ww'],
             'wire_type': row['wire_type'], 'Std#wire': None}
    for m in UPH_MODELS:
        entry[m] = 0
        entry[f'{m}_cu'] = 0
        entry[f'{m}_au'] = 0
    calc = pd.concat([calc, pd.DataFrame([entry])], ignore_index=True)

calc = calc.sort_values('drr_k', ascending=False).reset_index(drop=True)
print(f'Calc rows: {len(calc)}, Total DRR: {calc.drr_k.sum():.0f} K/day')

# ── Machine counts ───────────────────────────────────────────────────────────
ml = pd.read_excel(SRC, sheet_name='Machine list', header=0)
has_lr = ml['ods_name'].str.contains('_L$|_R$', na=False, regex=True)
single = ml[~has_lr].groupby('model')['ods_name'].count().reset_index()
lr_bases = ml[has_lr].copy()
lr_bases['base'] = lr_bases['ods_name'].str.replace(r'_[LR]$', '', regex=True)
lr_cnt = lr_bases.drop_duplicates('base').groupby('model')['base'].count().reset_index()
lr_cnt.columns = ['model', 'ods_name']
mc_df = pd.concat([single, lr_cnt]).groupby('model')['ods_name'].sum().reset_index()
mc_df.columns = ['model', 'machines']
mc_df['heads'] = mc_df['model'].apply(lambda x: 2 if any(t in str(x) for t in ['Twin', 'Harrier']) else 1)
mc_df['total_heads'] = mc_df['machines'] * mc_df['heads']

MODEL_MAP = {
    'AB339': 'AB339', 'Eagle/Eagle60': 'Eagle60',
    'Harrier': 'Harrier ', 'Aero Twin': 'Aero Twin',
    'Extreme GoCU': 'Eagle Xtreme GoCu',
    'TwinEagleExtream': 'Twin Eagle Xtreme GoCu',
    'Egle Aero GoCU': 'Eagle Aero GoCu',
}
HEADS = {'AB339': 1, 'Eagle/Eagle60': 1, 'Harrier': 2, 'Aero Twin': 2,
         'Extreme GoCU': 1, 'TwinEagleExtream': 2, 'Egle Aero GoCU': 1}

def get_mc(uph_model):
    ml_name = MODEL_MAP.get(uph_model, uph_model)
    row = mc_df[mc_df['model'].str.strip() == ml_name.strip()]
    return int(row['machines'].sum()) if not row.empty else 0

MC_AVAIL = {m: get_mc(m) for m in UPH_MODELS}
print('MC Available:', MC_AVAIL)

# ══════════════════════════════════════════════════════════════════════════════
# STYLES
# ══════════════════════════════════════════════════════════════════════════════
BLUE = '0E3689'; LT_BLUE = '1D9CE4'; GREEN = '5EBF33'
ORANGE = 'FD7F20'; RED = 'CC0000'; COPPER = 'B87333'
GOLD_CLR = 'DAA520'; GRAY1 = '37474F'; GRAY2 = 'F5F5F5'
WHITE = 'FFFFFF'; DARK = '1A1A1A'; LIGHT_Y = 'FFFFCC'; LT_BLU_BG = 'E3F2FD'

def bdr():
    s = Side(style='thin', color='CCCCCC')
    return Border(left=s, right=s, top=s, bottom=s)

def hdr(cell, txt, bg=GRAY1, fc=WHITE, sz=10, wrap=True):
    cell.value = txt; cell.font = Font(name='Arial', bold=True, size=sz, color=fc)
    cell.fill = PatternFill('solid', fgColor=bg)
    cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=wrap)
    cell.border = bdr()

def dat(cell, val, align='center', bold=False, color=DARK, bg=None, fmt=None):
    cell.value = val; cell.font = Font(name='Arial', size=10, bold=bold, color=color)
    cell.alignment = Alignment(horizontal=align, vertical='center')
    cell.border = bdr()
    if bg: cell.fill = PatternFill('solid', fgColor=bg)
    if fmt: cell.number_format = fmt

def inp(cell, val, fmt=None):
    cell.value = val; cell.font = Font(name='Arial', size=11, bold=True, color=BLUE)
    cell.fill = PatternFill('solid', fgColor=LIGHT_Y)
    cell.alignment = Alignment(horizontal='center', vertical='center')
    cell.border = Border(left=Side('medium', color=BLUE), right=Side('medium', color=BLUE),
                         top=Side('medium', color=BLUE), bottom=Side('medium', color=BLUE))
    if fmt: cell.number_format = fmt

def section(ws, r, c1, c2, txt, bg=BLUE, fc=WHITE, sz=12):
    ws.merge_cells(start_row=r, start_column=c1, end_row=r, end_column=c2)
    c = ws.cell(row=r, column=c1)
    c.value = txt; c.font = Font(name='Arial', bold=True, size=sz, color=fc)
    c.fill = PatternFill('solid', fgColor=bg)
    c.alignment = Alignment(horizontal='center', vertical='center')

def total_row_style(ws, r, max_col):
    for ci in range(1, max_col + 1):
        c = ws.cell(row=r, column=ci)
        c.fill = PatternFill('solid', fgColor=BLUE)
        c.font = Font(name='Arial', bold=True, size=11, color=WHITE)
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border = bdr()

wb = Workbook()

# ══════════════════════════════════════════════════════════════════════════════
# SHEET 1: Parameters
# ══════════════════════════════════════════════════════════════════════════════
ws1 = wb.active
ws1.title = 'Parameters'
ws1.sheet_properties.tabColor = BLUE
ws1.sheet_view.showGridLines = False

ws1.row_dimensions[1].height = 36
section(ws1, 1, 1, 7, 'WB Loading Calculator — Parameters', BLUE, WHITE, 14)
ws1.row_dimensions[2].height = 18
ws1.merge_cells('A2:G2')
ws1['A2'].value = 'Edit YELLOW cells to change assumptions. All calculator sheets update automatically.'
ws1['A2'].font = Font(name='Arial', size=9, italic=True, color='666666')
ws1.row_dimensions[3].height = 10

# Operating Hours
section(ws1, 4, 1, 4, 'Operating Hours', GRAY1, WHITE, 11)
ws1.row_dimensions[4].height = 24
ws1.cell(row=5, column=1).value = 'Operating Hours / Day'
ws1.cell(row=5, column=1).font = Font(name='Arial', bold=True, size=11)
ws1.cell(row=5, column=1).alignment = Alignment(horizontal='left', vertical='center')
inp(ws1.cell(row=5, column=2), 21, '0')  # B5 = Operating Hours
ws1.cell(row=5, column=3).value = 'hrs/day (3 shifts × 7 hrs)'
ws1.cell(row=5, column=3).font = Font(name='Arial', size=9, color='888888')
ws1.row_dimensions[5].height = 26
ws1.row_dimensions[6].height = 10

# Model parameters
section(ws1, 7, 1, 7, 'Machine Model — Heads per Machine & Available Count', GRAY1, WHITE, 11)
ws1.row_dimensions[7].height = 24

p_hdrs = ['Model (UPH)', 'Machine List Model', 'Machines\nAvailable', 'Heads / MC',
          'Total Heads', 'Cu Capable?', 'Notes']
p_widths = [22, 24, 14, 12, 14, 12, 30]
for ci, (h, w) in enumerate(zip(p_hdrs, p_widths), 1):
    hdr(ws1.cell(row=8, column=ci), h, GRAY1)
    ws1.column_dimensions[get_column_letter(ci)].width = w
ws1.row_dimensions[8].height = 30

CU_CAPABLE = {'AB339': 'No (Gold only)', 'Eagle/Eagle60': 'Yes', 'Harrier': 'Yes',
              'Aero Twin': 'Yes', 'Extreme GoCU': 'Yes (GoCu)', 'TwinEagleExtream': 'Yes',
              'Egle Aero GoCU': 'Yes (GoCu)'}

PARAM_ROW = {}
for ri, m in enumerate(UPH_MODELS):
    r = 9 + ri
    bg = GRAY2 if ri % 2 == 0 else WHITE
    PARAM_ROW[m] = r
    dat(ws1.cell(row=r, column=1), m, 'left', True, bg=bg)
    dat(ws1.cell(row=r, column=2), MODEL_MAP[m], 'left', bg=bg)
    dat(ws1.cell(row=r, column=3), MC_AVAIL[m], bold=True, color=BLUE, bg=bg)
    inp(ws1.cell(row=r, column=4), HEADS[m], '0')   # Editable heads/MC
    # Total Heads = formula
    c = ws1.cell(row=r, column=5)
    c.value = f'=C{r}*D{r}'
    c.font = Font(name='Arial', bold=True, size=10, color=DARK)
    c.alignment = Alignment(horizontal='center', vertical='center')
    c.fill = PatternFill('solid', fgColor=LT_BLU_BG)
    c.border = bdr()
    cu_cap = CU_CAPABLE.get(m, '?')
    cap_color = GREEN if 'Yes' in cu_cap else RED
    dat(ws1.cell(row=r, column=6), cu_cap, bold=True, color=cap_color, bg=bg)
    dat(ws1.cell(row=r, column=7), '', 'left', bg=bg, color='555555')
    ws1.row_dimensions[r].height = 22

TOT_P = 9 + len(UPH_MODELS)
total_row_style(ws1, TOT_P, 7)
ws1.cell(row=TOT_P, column=1).value = 'TOTAL'
ws1.cell(row=TOT_P, column=1).alignment = Alignment(horizontal='left', vertical='center')
ws1.cell(row=TOT_P, column=3).value = f'=SUM(C9:C{TOT_P - 1})'
ws1.cell(row=TOT_P, column=5).value = f'=SUM(E9:E{TOT_P - 1})'
ws1.row_dimensions[TOT_P].height = 24

# ══════════════════════════════════════════════════════════════════════════════
# SHEET 2: Loading Calculator
# ══════════════════════════════════════════════════════════════════════════════
ws2 = wb.create_sheet('Loading Calculator')
ws2.sheet_properties.tabColor = LT_BLUE
ws2.sheet_view.showGridLines = False

N_MODELS = len(UPH_MODELS)
TOTAL_COLS = 6 + N_MODELS * 2  # A-F static + 2 per model

ws2.row_dimensions[1].height = 36
section(ws2, 1, 1, TOTAL_COLS,
        'WB Loading Calculator — Machines Required per Package & Model', BLUE, WHITE, 14)
ws2.row_dimensions[2].height = 18
ws2.merge_cells(f'A2:{get_column_letter(TOTAL_COLS)}2')
ws2['A2'].value = ('MC Required = DRR(K) × 1000 / (Heads/MC × UPH/head × Hours)  |  '
                   'Yellow = editable  |  Blue = calculated  |  Wire Type auto-filled from WW#04')
ws2['A2'].font = Font(name='Arial', size=9, italic=True, color='444444')
ws2.row_dimensions[3].height = 8

# Model group headers (row 4)
for ci in range(1, 7):
    ws2.cell(row=4, column=ci).value = ''
for mi, m in enumerate(UPH_MODELS):
    col1 = 7 + mi * 2
    ws2.merge_cells(start_row=4, start_column=col1, end_row=4, end_column=col1 + 1)
    c = ws2.cell(row=4, column=col1)
    h_mark = ' (2h)' if HEADS[m] == 2 else ' (1h)'
    c.value = m + h_mark
    c.font = Font(name='Arial', bold=True, size=9, color=WHITE)
    c.fill = PatternFill('solid', fgColor=LT_BLUE)
    c.alignment = Alignment(horizontal='center', vertical='center')
    c.border = bdr()
    ws2.cell(row=4, column=col1 + 1).fill = PatternFill('solid', fgColor=LT_BLUE)
    ws2.cell(row=4, column=col1 + 1).border = bdr()
ws2.row_dimensions[4].height = 22

# Column headers (row 5)
STATIC_HDRS = ['UPH Table\nPackage', 'WW#04\nPackages', 'DRR\n(K/day)', 'DRR\n(units/day)',
               'Std#\nWire', 'Wire\nType']
for ci, h in enumerate(STATIC_HDRS, 1):
    bg = BLUE if ci in [3, 6] else GRAY1  # highlight editable columns
    hdr(ws2.cell(row=5, column=ci), h, bg, WHITE)
for mi in range(N_MODELS):
    col_uph = 7 + mi * 2
    hdr(ws2.cell(row=5, column=col_uph), 'UPH/\nhead', GRAY1)
    hdr(ws2.cell(row=5, column=col_uph + 1), 'MC\nReq.', BLUE)
ws2.row_dimensions[5].height = 36

# Column widths
ws2.column_dimensions['A'].width = 20
ws2.column_dimensions['B'].width = 28
ws2.column_dimensions['C'].width = 11
ws2.column_dimensions['D'].width = 13
ws2.column_dimensions['E'].width = 8
ws2.column_dimensions['F'].width = 7
for mi in range(N_MODELS):
    ws2.column_dimensions[get_column_letter(7 + mi * 2)].width = 9
    ws2.column_dimensions[get_column_letter(8 + mi * 2)].width = 8

# Data rows
DATA_START = 6
for ri, row in calc.iterrows():
    r = DATA_START + ri
    bg = GRAY2 if ri % 2 == 0 else WHITE
    is_zero = (row['drr_k'] == 0)
    txt_c = '999999' if is_zero else DARK

    # A: Package
    dat(ws2.cell(row=r, column=1), row['uph_pkg'] or '—', 'left', False, txt_c, bg)
    # B: WW#04 packages
    dat(ws2.cell(row=r, column=2), row.get('ww_pkgs', ''), 'left', False, '666666', bg)
    # C: DRR (yellow input)
    c_drr = ws2.cell(row=r, column=3)
    c_drr.value = row['drr_k']
    c_drr.font = Font(name='Arial', size=10, bold=True, color=BLUE if not is_zero else '999999')
    c_drr.fill = PatternFill('solid', fgColor=LIGHT_Y)
    c_drr.alignment = Alignment(horizontal='center', vertical='center')
    c_drr.border = bdr()
    c_drr.number_format = '#,##0.00'
    # D: DRR units (formula)
    c_du = ws2.cell(row=r, column=4)
    c_du.value = f'=C{r}*1000'
    c_du.font = Font(name='Arial', size=10, color=DARK)
    c_du.number_format = '#,##0'
    c_du.alignment = Alignment(horizontal='center', vertical='center')
    c_du.fill = PatternFill('solid', fgColor=LT_BLU_BG)
    c_du.border = bdr()
    # E: Std#Wire
    std_w = row.get('Std#wire')
    dat(ws2.cell(row=r, column=5), round(float(std_w), 1) if pd.notna(std_w) else '', bg=bg)
    # F: Wire Type (yellow input)
    wt = row.get('wire_type', 'Cu')
    c_wt = ws2.cell(row=r, column=6)
    c_wt.value = wt
    c_wt.font = Font(name='Arial', size=10, bold=True,
                     color=COPPER if wt == 'Cu' else GOLD_CLR)
    c_wt.fill = PatternFill('solid', fgColor=LIGHT_Y)
    c_wt.alignment = Alignment(horizontal='center', vertical='center')
    c_wt.border = bdr()

    # Per model: UPH + MC Required
    for mi, m in enumerate(UPH_MODELS):
        col_uph = 7 + mi * 2
        col_mc = col_uph + 1
        uph_val = row.get(m, 0)

        # UPH value (static, selected by wire type)
        uc = ws2.cell(row=r, column=col_uph)
        if pd.notna(uph_val) and float(uph_val) > 0:
            uc.value = round(float(uph_val), 1)
            uc.number_format = '#,##0.0'
            uc.font = Font(name='Arial', size=9, color='555555' if is_zero else DARK)
        else:
            uc.value = None
            uc.font = Font(name='Arial', size=9, color='BBBBBB')
        uc.alignment = Alignment(horizontal='center', vertical='center')
        uc.border = bdr()
        uc.fill = PatternFill('solid', fgColor=bg)

        # MC Required (formula referencing Parameters sheet)
        mc = ws2.cell(row=r, column=col_mc)
        heads_row = PARAM_ROW[m]
        uph_cl = get_column_letter(col_uph)
        if pd.notna(uph_val) and float(uph_val) > 0:
            mc.value = (f'=IF(AND(D{r}>0,{uph_cl}{r}>0),'
                        f'D{r}/(Parameters!$D${heads_row}*{uph_cl}{r}*Parameters!$B$5),"")')
            mc.number_format = '#,##0.00'
        else:
            mc.value = '—'
        mc.font = Font(name='Arial', size=10, bold=True,
                       color=BLUE if not is_zero else '999999')
        mc.alignment = Alignment(horizontal='center', vertical='center')
        mc.fill = PatternFill('solid', fgColor=LT_BLU_BG)
        mc.border = bdr()

    ws2.row_dimensions[r].height = 18

# TOTAL row
DATA_END = DATA_START + len(calc) - 1
TOT2 = DATA_END + 1
ws2.row_dimensions[TOT2].height = 26
total_row_style(ws2, TOT2, TOTAL_COLS)
ws2.cell(row=TOT2, column=1).value = 'TOTAL'
ws2.cell(row=TOT2, column=1).alignment = Alignment(horizontal='left', vertical='center')
ws2.cell(row=TOT2, column=3).value = f'=SUM(C{DATA_START}:C{DATA_END})'
ws2.cell(row=TOT2, column=3).number_format = '#,##0.0'
ws2.cell(row=TOT2, column=4).value = f'=SUM(D{DATA_START}:D{DATA_END})'
ws2.cell(row=TOT2, column=4).number_format = '#,##0'

for mi, m in enumerate(UPH_MODELS):
    col_mc = 8 + mi * 2
    cl = get_column_letter(col_mc)
    # SUM only numeric cells (skip "—")
    ws2.cell(row=TOT2, column=col_mc).value = (
        f'=SUMPRODUCT(({cl}{DATA_START}:{cl}{DATA_END}<>"—")*'
        f'IFERROR(VALUE(IF({cl}{DATA_START}:{cl}{DATA_END}="","0",{cl}{DATA_START}:{cl}{DATA_END})),0))')
    ws2.cell(row=TOT2, column=col_mc).number_format = '#,##0.0'

# Conditional formatting on MC Required columns
for mi in range(N_MODELS):
    col_mc = 8 + mi * 2
    cl = get_column_letter(col_mc)
    rng = f'{cl}{DATA_START}:{cl}{DATA_END}'
    ws2.conditional_formatting.add(rng, CellIsRule(
        operator='greaterThan', formula=['5'],
        fill=PatternFill('solid', fgColor='FFCCCC'),
        font=Font(color=RED, bold=True, name='Arial', size=10)))
    ws2.conditional_formatting.add(rng, CellIsRule(
        operator='between', formula=['2', '5'],
        fill=PatternFill('solid', fgColor='FFF9C4'),
        font=Font(color='B8860B', bold=True, name='Arial', size=10)))

ws2.freeze_panes = f'G{DATA_START}'

# ══════════════════════════════════════════════════════════════════════════════
# SHEET 3: Summary by Model
# ══════════════════════════════════════════════════════════════════════════════
ws3 = wb.create_sheet('Summary by Model')
ws3.sheet_properties.tabColor = GREEN
ws3.sheet_view.showGridLines = False

ws3.row_dimensions[1].height = 36
section(ws3, 1, 1, 8, 'WB Machine Requirement Summary — by Model', BLUE, WHITE, 14)
ws3.merge_cells('A2:H2')
ws3['A2'].value = 'MC Req. pulled from Loading Calculator totals. Gap = Available − Required.'
ws3['A2'].font = Font(name='Arial', size=9, italic=True, color='444444')
ws3.row_dimensions[3].height = 8

section(ws3, 4, 1, 8, 'Machine Availability vs. Requirement', GRAY1, WHITE, 11)
ws3.row_dimensions[4].height = 24

s_hdrs = ['Model', 'Heads\n/MC', 'Machines\nAvailable', 'Total Heads\nAvailable',
          'MC Required\n(from DRR)', 'MC Gap\n(Avail − Req)', 'Utilization\n%', 'Status']
s_widths = [24, 10, 14, 14, 14, 14, 12, 14]
for ci, (h, w) in enumerate(zip(s_hdrs, s_widths), 1):
    hdr(ws3.cell(row=5, column=ci), h, GRAY1)
    ws3.column_dimensions[get_column_letter(ci)].width = w
ws3.row_dimensions[5].height = 36

for ri, m in enumerate(UPH_MODELS):
    r = 6 + ri
    bg = GRAY2 if ri % 2 == 0 else WHITE
    pr = PARAM_ROW[m]
    mc_col = 8 + ri * 2
    mc_cl = get_column_letter(mc_col)

    dat(ws3.cell(row=r, column=1), m, 'left', True, bg=bg)
    c = ws3.cell(row=r, column=2); c.value = f"=Parameters!D{pr}"
    c.font = Font(name='Arial', size=10); c.alignment = Alignment(horizontal='center', vertical='center')
    c.border = bdr(); c.fill = PatternFill('solid', fgColor=bg)
    c = ws3.cell(row=r, column=3); c.value = f"=Parameters!C{pr}"
    c.font = Font(name='Arial', size=10, bold=True, color=BLUE)
    c.alignment = Alignment(horizontal='center', vertical='center')
    c.border = bdr(); c.fill = PatternFill('solid', fgColor=bg)
    c = ws3.cell(row=r, column=4); c.value = f"=Parameters!E{pr}"
    c.font = Font(name='Arial', size=10); c.alignment = Alignment(horizontal='center', vertical='center')
    c.border = bdr(); c.fill = PatternFill('solid', fgColor=bg)
    c = ws3.cell(row=r, column=5); c.value = f"='Loading Calculator'!{mc_cl}{TOT2}"
    c.font = Font(name='Arial', size=11, bold=True, color=BLUE)
    c.number_format = '#,##0.0'; c.alignment = Alignment(horizontal='center', vertical='center')
    c.border = bdr(); c.fill = PatternFill('solid', fgColor=LT_BLU_BG)
    c = ws3.cell(row=r, column=6); c.value = f"=C{r}-ROUNDUP(E{r},0)"
    c.number_format = '+#,##0;-#,##0;0'; c.font = Font(name='Arial', size=11, bold=True)
    c.alignment = Alignment(horizontal='center', vertical='center'); c.border = bdr()
    c.fill = PatternFill('solid', fgColor=bg)
    c = ws3.cell(row=r, column=7); c.value = f"=IF(C{r}>0,E{r}/C{r},0)"
    c.number_format = '0.0%'; c.font = Font(name='Arial', size=10)
    c.alignment = Alignment(horizontal='center', vertical='center'); c.border = bdr()
    c.fill = PatternFill('solid', fgColor=bg)
    c = ws3.cell(row=r, column=8)
    c.value = f'=IF(F{r}>=0,"Sufficient",IF(F{r}>=-5,"Tight","Shortage"))'
    c.font = Font(name='Arial', size=10, bold=True)
    c.alignment = Alignment(horizontal='center', vertical='center'); c.border = bdr()
    c.fill = PatternFill('solid', fgColor=bg)
    ws3.row_dimensions[r].height = 22

TOT3 = 6 + len(UPH_MODELS)
total_row_style(ws3, TOT3, 8)
ws3.cell(row=TOT3, column=1).value = 'TOTAL'
ws3.cell(row=TOT3, column=1).alignment = Alignment(horizontal='left', vertical='center')
ws3.cell(row=TOT3, column=3).value = f'=SUM(C6:C{TOT3 - 1})'
ws3.cell(row=TOT3, column=4).value = f'=SUM(D6:D{TOT3 - 1})'
ws3.cell(row=TOT3, column=5).value = f'=SUM(E6:E{TOT3 - 1})'
ws3.cell(row=TOT3, column=5).number_format = '#,##0.0'
ws3.cell(row=TOT3, column=6).value = f'=SUM(C6:C{TOT3-1})-ROUNDUP(SUM(E6:E{TOT3-1}),0)'
ws3.cell(row=TOT3, column=6).number_format = '+#,##0;-#,##0;0'
ws3.row_dimensions[TOT3].height = 26

# Gap conditional formatting
ws3.conditional_formatting.add(f'F6:F{TOT3}', CellIsRule(
    operator='lessThan', formula=['0'],
    fill=PatternFill('solid', fgColor='FFCCCC'), font=Font(color=RED, bold=True)))
ws3.conditional_formatting.add(f'F6:F{TOT3}', CellIsRule(
    operator='greaterThanOrEqual', formula=['0'],
    fill=PatternFill('solid', fgColor='CCFFCC'), font=Font(color='1B6B1B', bold=True)))
ws3.conditional_formatting.add(f'G6:G{TOT3-1}', DataBarRule(
    start_type='num', start_value=0, end_type='num', end_value=2, color=LT_BLUE))

# Chart data table
CDR = TOT3 + 3
for ci, h in enumerate(['Model', 'Available', 'Required'], 1):
    hdr(ws3.cell(row=CDR, column=ci), h, GRAY1)
for ri, m in enumerate(UPH_MODELS):
    r = CDR + 1 + ri
    ws3.cell(row=r, column=1).value = m
    ws3.cell(row=r, column=2).value = f'=C{6 + ri}'
    ws3.cell(row=r, column=3).value = f'=IFERROR(ROUNDUP(E{6 + ri},0),0)'
    for ci in range(1, 4):
        ws3.cell(row=r, column=ci).border = bdr()

bar = BarChart()
bar.type = 'col'; bar.grouping = 'clustered'
bar.title = 'Machines Available vs Required by Model'
bar.y_axis.title = 'Machines'; bar.style = 2; bar.width = 22; bar.height = 13
bar.add_data(Reference(ws3, min_col=2, max_col=2, min_row=CDR, max_row=CDR + N_MODELS), titles_from_data=True)
bar.add_data(Reference(ws3, min_col=3, max_col=3, min_row=CDR, max_row=CDR + N_MODELS), titles_from_data=True)
bar.set_categories(Reference(ws3, min_col=1, max_col=1, min_row=CDR + 1, max_row=CDR + N_MODELS))
bar.series[0].graphicalProperties.solidFill = LT_BLUE
bar.series[0].graphicalProperties.line.solidFill = BLUE
bar.series[1].graphicalProperties.solidFill = ORANGE
bar.series[1].graphicalProperties.line.solidFill = 'CC4400'
bar.dataLabels = DataLabelList(); bar.dataLabels.showVal = True
ws3.add_chart(bar, f'A{CDR + 1}')

# ══════════════════════════════════════════════════════════════════════════════
# SHEET 4: UPH Reference (Cu)
# ══════════════════════════════════════════════════════════════════════════════
def build_uph_sheet(ws, title, tab_color, uph_df):
    ws.sheet_properties.tabColor = tab_color
    ws.sheet_view.showGridLines = False
    ws.row_dimensions[1].height = 34
    section(ws, 1, 1, 2 + N_MODELS, title, tab_color, WHITE, 12)
    ws.row_dimensions[2].height = 8
    uph_h = ['PKG', 'Std#Wire'] + UPH_MODELS
    uph_w = [22, 10] + [14] * N_MODELS
    for ci, (h, w) in enumerate(zip(uph_h, uph_w), 1):
        hdr(ws.cell(row=3, column=ci), h, GRAY1)
        ws.column_dimensions[get_column_letter(ci)].width = w
    ws.row_dimensions[3].height = 26
    for ri, row in uph_df.iterrows():
        r = 4 + ri
        bg = 'FFF8F0' if ri % 2 == 0 else WHITE
        dat(ws.cell(row=r, column=1), row['PKG'], 'left', True, bg=bg)
        std_w = row.get('Std#wire')
        dat(ws.cell(row=r, column=2), round(float(std_w), 1) if pd.notna(std_w) else '—', bg=bg)
        for mi, m in enumerate(UPH_MODELS):
            c = ws.cell(row=r, column=3 + mi)
            val = row.get(m, 0)
            if pd.notna(val) and float(val) > 0:
                c.value = round(float(val), 1)
                c.number_format = '#,##0.0'
                c.font = Font(name='Arial', size=10, color=DARK if float(val) > 200 else '888888')
            else:
                c.value = '—'
                c.font = Font(name='Arial', size=10, color='BBBBBB')
            c.alignment = Alignment(horizontal='center', vertical='center')
            c.border = bdr()
            c.fill = PatternFill('solid', fgColor=bg)
        ws.row_dimensions[r].height = 18
    ws.freeze_panes = 'A4'

ws4 = wb.create_sheet('UPH Reference (Cu)')
build_uph_sheet(ws4, 'STD UPH per Head — Copper Wire Single Die', COPPER, uph_cu)

# ══════════════════════════════════════════════════════════════════════════════
# SHEET 5: UPH Reference (Au) — NEW
# ══════════════════════════════════════════════════════════════════════════════
ws5 = wb.create_sheet('UPH Reference (Au)')
build_uph_sheet(ws5, 'STD UPH per Head — Gold Wire Single Die', GOLD_CLR, uph_au)

# ══════════════════════════════════════════════════════════════════════════════
# SHEET 6: Machine List — NEW
# ══════════════════════════════════════════════════════════════════════════════
ws6 = wb.create_sheet('Machine List')
ws6.sheet_properties.tabColor = ORANGE
ws6.sheet_view.showGridLines = False

ws6.row_dimensions[1].height = 34
section(ws6, 1, 1, 6, f'Wire Bond Machine List — {len(ml)} entries ({mc_df["machines"].sum()} unique machines)', BLUE, WHITE, 13)
ws6.row_dimensions[2].height = 8

ml_hdrs = ['No.', 'ODS Name', 'Model', 'Heads/MC', 'Head Side', 'Wire Capability']
ml_widths = [6, 22, 26, 10, 10, 18]
for ci, (h, w) in enumerate(zip(ml_hdrs, ml_widths), 1):
    hdr(ws6.cell(row=3, column=ci), h, GRAY1)
    ws6.column_dimensions[get_column_letter(ci)].width = w
ws6.row_dimensions[3].height = 26

MODEL_CLR = {
    'AB339': 'E3F2FD', 'Eagle60': 'F3E5F5', 'Harrier ': 'FFF8E1', 'Harrier': 'FFF8E1',
    'Aero Twin': 'FFF3E0', 'Twin Eagle Xtreme GoCu': 'FBE9E7',
    'Eagle Aero GoCu': 'E8F5E9', 'Eagle Xtreme GoCu': 'E0F7FA',
    'AB339Eagle': 'E3F2FD', 'Harrier Xtreme': 'FFF8E1', 'Eagle Xtreme': 'E0F7FA',
}
WIRE_CAP = {
    'AB339': 'Gold only', 'AB339Eagle': 'Gold only',
    'Eagle60': 'Both', 'Harrier ': 'Both', 'Harrier': 'Both', 'Harrier Xtreme': 'Both',
    'Aero Twin': 'Both', 'Twin Eagle Xtreme GoCu': 'Both',
    'Eagle Aero GoCu': 'Copper (GoCu)', 'Eagle Xtreme GoCu': 'Copper (GoCu)',
    'Eagle Xtreme': 'Both',
}

for ri, row in ml.iterrows():
    r = 4 + ri
    model = str(row['model']).strip()
    ods = str(row['ods_name']).strip()
    bg = MODEL_CLR.get(model, WHITE)
    is_lr = bool(re.search(r'_[LR]$', ods))
    heads = 2 if any(t in model for t in ['Twin', 'Harrier']) else 1
    side = ods[-1] if is_lr else 'Single'

    dat(ws6.cell(row=r, column=1), ri + 1, bg=bg)
    dat(ws6.cell(row=r, column=2), ods, 'left', True, bg=bg)
    dat(ws6.cell(row=r, column=3), model, 'left', bg=bg)
    dat(ws6.cell(row=r, column=4), heads, bg=bg)
    dat(ws6.cell(row=r, column=5), side, bg=bg, color=LT_BLUE if side in ('L', 'R') else DARK)
    wire_cap = WIRE_CAP.get(model, 'Unknown')
    wc_color = COPPER if 'Copper' in wire_cap else (GREEN if 'Both' in wire_cap else GOLD_CLR)
    dat(ws6.cell(row=r, column=6), wire_cap, bold=True, color=wc_color, bg=bg)
    ws6.row_dimensions[r].height = 16

ws6.freeze_panes = 'A4'

# Machine summary at bottom
SR = 4 + len(ml) + 2
section(ws6, SR, 1, 6, 'Summary by Model', GRAY1, WHITE, 11)
ws6.row_dimensions[SR].height = 24
SR += 1
for ci, h in enumerate(['Model', 'Entries', 'Unique MC', 'Heads/MC', 'Total Heads', 'Wire Cap.'], 1):
    hdr(ws6.cell(row=SR, column=ci), h, GRAY1)
ws6.row_dimensions[SR].height = 24
SR += 1

mc_sorted = mc_df.sort_values('machines', ascending=False)
for ri, (_, row) in enumerate(mc_sorted.iterrows()):
    r = SR + ri
    bg = GRAY2 if ri % 2 == 0 else WHITE
    model = row['model'].strip()
    entries = int(ml[ml['model'].str.strip() == model].shape[0])
    dat(ws6.cell(row=r, column=1), model, 'left', True, bg=bg)
    dat(ws6.cell(row=r, column=2), entries, bg=bg)
    dat(ws6.cell(row=r, column=3), int(row['machines']), bold=True, color=BLUE, bg=bg)
    dat(ws6.cell(row=r, column=4), int(row['heads']), bg=bg)
    dat(ws6.cell(row=r, column=5), int(row['total_heads']), bold=True, color=BLUE, bg=bg)
    dat(ws6.cell(row=r, column=6), WIRE_CAP.get(model, '?'), bg=bg)
    ws6.row_dimensions[r].height = 20

# ══════════════════════════════════════════════════════════════════════════════
# SAVE
# ══════════════════════════════════════════════════════════════════════════════
out = 'Output/WB_Loading_Calculator.xlsx'
os.makedirs('Output', exist_ok=True)
wb.save(out)
print(f'\nSaved: {out}')
print(f'  Sheets: {[s.title for s in wb.worksheets]}')
print(f'  Packages: {len(calc)} (DRR total: {calc.drr_k.sum():.0f} K/day)')
print(f'  Wire Type: Cu={len(calc[calc.wire_type=="Cu"])}, Au={len(calc[calc.wire_type=="Au"])}')
print(f'  Models: {N_MODELS}, Total MC: {mc_df["machines"].sum()}, Total Heads: {mc_df["total_heads"].sum()}')
