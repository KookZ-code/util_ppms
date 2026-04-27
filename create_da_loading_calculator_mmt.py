"""
Generate DA Loading Calculator Excel from MMT ASSY DA CAP data.
Reads:  raw/MMT assy DA cap.xlsx
Writes: Output/DA_Loading_Calculator_MMT.xlsx
"""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import openpyxl
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, numbers
)
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import CellIsRule, DataBarRule

# ── Paths ────────────────────────────────────────────────────────────────
EXCEL_PATH = os.path.join('raw', 'MMT assy DA cap.xlsx')
OUTPUT_DIR = 'Output'
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_PATH = os.path.join(OUTPUT_DIR, 'DA_Loading_Calculator_MMT.xlsx')

# ── Colour palette ──────────────────────────────────────────────────────
BLUE       = '0E3689'
LIGHT_BLUE = '1D9CE4'
GREEN_HEX  = '5EBF33'
ORANGE_HEX = 'FD7F20'
RED_HEX    = 'CC0000'
DARK_GRAY  = '4A4A4A'
MED_GRAY   = '8A8A8A'
LIGHT_GRAY = 'D9D9D9'
VLIGHT     = 'F7F7F7'

# ── Reusable styles ─────────────────────────────────────────────────────
header_font  = Font(name='Calibri', bold=True, size=11, color='FFFFFF')
header_fill  = PatternFill('solid', fgColor=BLUE)
header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)

input_font   = Font(name='Calibri', bold=True, size=12, color=BLUE)
input_fill   = PatternFill('solid', fgColor='FFFFCC')
input_border = Border(
    left=Side(style='medium', color=BLUE),
    right=Side(style='medium', color=BLUE),
    top=Side(style='medium', color=BLUE),
    bottom=Side(style='medium', color=BLUE),
)

result_font = Font(name='Calibri', bold=True, size=11, color=BLUE)
result_fill = PatternFill('solid', fgColor='E3F2FD')

normal_font  = Font(name='Calibri', size=11, color='000000')
normal_align = Alignment(horizontal='center', vertical='center')
left_align   = Alignment(horizontal='left', vertical='center')

num_fmt_int  = '#,##0'
num_fmt_dec1 = '#,##0.0'
num_fmt_pct  = '0.0%'

thin_border = Border(
    left=Side(style='thin', color=LIGHT_GRAY),
    right=Side(style='thin', color=LIGHT_GRAY),
    top=Side(style='thin', color=LIGHT_GRAY),
    bottom=Side(style='thin', color=LIGHT_GRAY),
)


def style_header_row(ws, row, max_col):
    for c in range(1, max_col + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border


def style_data_cell(ws, row, col, is_alt=False, align='center'):
    cell = ws.cell(row=row, column=col)
    cell.font = normal_font
    cell.fill = PatternFill('solid', fgColor=VLIGHT) if is_alt else PatternFill('solid', fgColor='FFFFFF')
    cell.alignment = Alignment(horizontal=align, vertical='center')
    cell.border = thin_border
    return cell


def style_input_cell(ws, row, col):
    cell = ws.cell(row=row, column=col)
    cell.font = input_font
    cell.fill = input_fill
    cell.alignment = normal_align
    cell.border = input_border
    return cell


def style_result_cell(ws, row, col):
    cell = ws.cell(row=row, column=col)
    cell.font = result_font
    cell.fill = result_fill
    cell.alignment = normal_align
    cell.border = thin_border
    return cell


def add_section_header(ws, row, col_start, col_end, text, color=BLUE):
    ws.merge_cells(start_row=row, start_column=col_start, end_row=row, end_column=col_end)
    cell = ws.cell(row=row, column=col_start)
    cell.value = text
    cell.font = Font(name='Calibri', bold=True, size=13, color='FFFFFF')
    cell.fill = PatternFill('solid', fgColor=color)
    cell.alignment = Alignment(horizontal='center', vertical='center')


# ── Load source data ─────────────────────────────────────────────────────
src = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
ws_src = src['MMT ASSY DA']

packages = []
for r in range(3, 42):  # rows 3–41: individual packages
    item      = ws_src.cell(r, 2).value   # B: Item
    pkg       = ws_src.cell(r, 3).value   # C: Package
    if pkg is None or pkg == 'Total':
        continue
    max_cap   = ws_src.cell(r, 4).value or 0   # D: Max CAP Mold
    drr_max   = ws_src.cell(r, 5).value or 0   # E: Actual DRR MAX
    std_ie    = ws_src.cell(r, 6).value         # F: STD DA UPH IE
    std_uph   = ws_src.cell(r, 7).value or 0   # G: STD DA UPH
    cur_uph   = ws_src.cell(r, 8).value or 0   # H: Current DA UPH
    mc_no     = ws_src.cell(r, 12).value or ''  # L: MC No
    shutdown  = ws_src.cell(r, 13).value or ''  # M: Machine Shutdown
    repair    = ws_src.cell(r, 14).value or ''  # N: Machine wait for repair
    transfer  = ws_src.cell(r, 15).value or ''  # O: Machine transfer
    cur_usage = ws_src.cell(r, 17).value or 0   # Q: Current DA Machine usage
    cur_out   = ws_src.cell(r, 18).value or 0   # R: Current Output per day

    packages.append({
        'pkg':         str(pkg),
        'max_cap':     int(max_cap) if max_cap else 0,
        'drr':         int(round(drr_max)) if drr_max else 0,
        'std_ie':      int(std_ie) if std_ie else 0,
        'std_uph':     int(std_uph) if std_uph else 0,
        'cur_uph':     int(cur_uph) if cur_uph else 0,
        'mc_no':       str(mc_no).strip() if mc_no else '',
        'shutdown':    str(shutdown).strip() if shutdown else '',
        'repair':      str(repair).strip() if repair else '',
        'transfer':    str(transfer).strip() if transfer else '',
        'cur_usage':   int(cur_usage) if cur_usage else 0,
        'cur_output':  int(cur_out) if cur_out else 0,
    })

# Source totals (row 42)
total_mc_usage  = int(ws_src.cell(42, 17).value or 0)
total_shutdown  = int(ws_src.cell(42, 13).value or 0)
total_repair    = int(ws_src.cell(42, 14).value or 0)
total_transfer  = int(ws_src.cell(42, 15).value or 0)
total_cur_out   = int(ws_src.cell(42, 18).value or 0)

# Read action items (rows 46–53)
actions = []
for r in range(46, 54):
    val = ws_src.cell(r, 3).value
    if val:
        actions.append(str(val))

src.close()

# Build machine list from per-package MC No + Shutdown columns
all_machines = []  # (mc_id, package, status)
for p in packages:
    # Running machines
    if p['mc_no']:
        for mc in p['mc_no'].split(','):
            mc = mc.strip()
            if mc:
                all_machines.append((mc, p['pkg'], 'Run'))
    # Shutdown machines (only if not already listed in mc_no)
    if p['shutdown']:
        existing = set(m.strip() for m in p['mc_no'].split(',')) if p['mc_no'] else set()
        for mc in p['shutdown'].split(','):
            mc = mc.strip()
            if mc and mc not in existing:
                all_machines.append((mc, p['pkg'], 'Machine Shutdown'))
    # Repair machines
    if p['repair']:
        existing = set(m.strip() for m in p['mc_no'].split(',')) if p['mc_no'] else set()
        for mc in p['repair'].split(','):
            mc = mc.strip()
            if mc and mc not in existing:
                all_machines.append((mc, p['pkg'], 'Wait for Repair'))

n_pkgs = len(packages)
n_running  = total_mc_usage
n_shutdown = total_shutdown + total_repair
n_all      = n_running + n_shutdown

print(f"Loaded {n_pkgs} packages, {len(all_machines)} machines")
print(f"  Running: {n_running}, Shutdown: {total_shutdown}, Repair: {total_repair}")

# ══════════════════════════════════════════════════════════════════════════
#  Create workbook
# ══════════════════════════════════════════════════════════════════════════
wb = openpyxl.Workbook()

# ======================================================================
#  SHEET 1: Loading Calculator
# ======================================================================
ws1 = wb.active
ws1.title = 'Loading Calculator'
ws1.sheet_properties.tabColor = BLUE

# Column widths
for col, w in {'A': 5, 'B': 22, 'C': 13, 'D': 13, 'E': 14, 'F': 11,
               'G': 11, 'H': 13, 'I': 13, 'J': 13, 'K': 13, 'L': 11,
               'M': 11, 'N': 14, 'O': 14, 'P': 14, 'Q': 11, 'R': 14}.items():
    ws1.column_dimensions[col].width = w

# Title
ws1.merge_cells('A1:R1')
c = ws1['A1']
c.value = 'DA Machine Loading Calculator — Change yellow cells to simulate different loading scenarios'
c.font = Font(name='Calibri', bold=True, size=16, color=BLUE)
c.alignment = Alignment(horizontal='left', vertical='center')
ws1.row_dimensions[1].height = 35

# Operating hours
ws1['A3'] = 'Operating Hours/Day:'
ws1['A3'].font = Font(name='Calibri', bold=True, size=11, color=DARK_GRAY)
c = style_input_cell(ws1, 3, 2)
c.value = 21
c.number_format = '0'
ws1['C3'] = 'hrs'
ws1['C3'].font = Font(name='Calibri', size=10, color=MED_GRAY)
ws1.row_dimensions[3].height = 15.5
ws1.row_dimensions[4].height = 8

# Column headers
HDR_ROW = 5
headers = [
    ('A', 'No.'), ('B', 'Package'), ('C', 'Max CAP\nMold'), ('D', 'Max\nDRR'),
    ('E', 'NEW DRR\n(Input)'), ('F', 'STD IE UPH'), ('G', 'Current\nUPH'),
    ('H', 'NEW UPH\n(Input)'), ('I', 'MC Required\n(STD UPH)'),
    ('J', 'MC Required\n(Cur UPH)'), ('K', 'MC Required\n(NEW)'),
    ('L', 'Current\nMC Usage'), ('M', 'MC Gap\nvs Current'),
    ('N', 'Current\nOutput/Day'), ('O', 'NEW\nOutput/Day'),
    ('P', 'Output\nChange'), ('Q', 'Output\nChange %'), ('R', 'Shutdown\nMCs'),
]
for col_letter, title in headers:
    ws1[f'{col_letter}{HDR_ROW}'] = title
style_header_row(ws1, HDR_ROW, 18)
ws1.row_dimensions[HDR_ROW].height = 40

# Data rows
DATA_START = 6
for i, p in enumerate(packages):
    r = DATA_START + i
    is_alt = i % 2 == 0

    # A: No.
    style_data_cell(ws1, r, 1, is_alt).value = i + 1

    # B: Package
    style_data_cell(ws1, r, 2, is_alt, 'left').value = p['pkg']

    # C: Max CAP Mold
    c = style_data_cell(ws1, r, 3, is_alt)
    c.value = p['max_cap'] if p['max_cap'] else None
    c.number_format = num_fmt_int

    # D: Max DRR
    c = style_data_cell(ws1, r, 4, is_alt)
    c.value = p['drr']
    c.number_format = num_fmt_int

    # E: NEW DRR (INPUT — yellow)
    c = style_input_cell(ws1, r, 5)
    c.value = p['drr']
    c.number_format = num_fmt_int

    # F: STD IE UPH (prefer STD IE, fallback to STD UPH)
    uph_f = p['std_ie'] if p['std_ie'] else p['std_uph']
    c = style_data_cell(ws1, r, 6, is_alt)
    c.value = uph_f if uph_f else None
    c.number_format = num_fmt_int

    # G: Current UPH
    c = style_data_cell(ws1, r, 7, is_alt)
    c.value = p['cur_uph'] if p['cur_uph'] else None
    c.number_format = num_fmt_int

    # H: NEW UPH (INPUT — yellow, default = current)
    new_uph = p['cur_uph'] if p['cur_uph'] else p['std_uph']
    c = style_input_cell(ws1, r, 8)
    c.value = new_uph if new_uph else None
    c.number_format = num_fmt_int

    # I: MC Required (STD UPH)
    c = style_result_cell(ws1, r, 9)
    c.value = f'=IF(F{r}>0, E{r}/(F{r}*$B$3), 0)'
    c.number_format = num_fmt_dec1

    # J: MC Required (Cur UPH)
    c = style_result_cell(ws1, r, 10)
    c.value = f'=IF(G{r}>0, E{r}/(G{r}*$B$3), 0)'
    c.number_format = num_fmt_dec1

    # K: MC Required (NEW)
    c = style_result_cell(ws1, r, 11)
    c.value = f'=IF(H{r}>0, E{r}/(H{r}*$B$3), 0)'
    c.number_format = num_fmt_dec1

    # L: Current MC Usage
    c = style_data_cell(ws1, r, 12, is_alt)
    c.value = p['cur_usage']
    c.number_format = num_fmt_int

    # M: MC Gap = ROUNDUP(K,0) - L
    c = style_result_cell(ws1, r, 13)
    c.value = f'=ROUNDUP(K{r},0)-L{r}'
    c.number_format = '\\+#,##0;\\-#,##0;0'

    # N: Current Output/Day
    c = style_data_cell(ws1, r, 14, is_alt)
    c.value = p['cur_output']
    c.number_format = num_fmt_int

    # O: NEW Output/Day = MIN(NEW DRR, Current_MC * NEW_UPH * hours)
    c = style_result_cell(ws1, r, 15)
    c.value = f'=MIN(E{r}, L{r}*H{r}*$B$3)'
    c.number_format = num_fmt_int

    # P: Output Change
    c = style_result_cell(ws1, r, 16)
    c.value = f'=O{r}-N{r}'
    c.number_format = '\\+#,##0;\\-#,##0;0'

    # Q: Output Change %
    c = style_result_cell(ws1, r, 17)
    c.value = f'=IF(N{r}>0, (O{r}-N{r})/N{r}, 0)'
    c.number_format = num_fmt_pct

    # R: Shutdown MCs
    shutdown_text = p['shutdown'] if p['shutdown'] else '-'
    style_data_cell(ws1, r, 18, is_alt, 'left').value = shutdown_text

DATA_END = DATA_START + n_pkgs - 1

# ── TOTAL row ──
TOT_ROW = DATA_END + 1
ws1.row_dimensions[TOT_ROW].height = 28
for col in range(1, 19):
    cell = ws1.cell(row=TOT_ROW, column=col)
    cell.font = header_font
    cell.fill = header_fill
    cell.alignment = normal_align
    cell.border = thin_border

ws1.cell(row=TOT_ROW, column=2).value = 'TOTAL'
ws1.cell(row=TOT_ROW, column=2).alignment = left_align

for ci, fmt in [(3, num_fmt_int), (4, num_fmt_int), (5, num_fmt_int)]:
    cl = get_column_letter(ci)
    ws1.cell(row=TOT_ROW, column=ci).value = f'=SUM({cl}{DATA_START}:{cl}{DATA_END})'
    ws1.cell(row=TOT_ROW, column=ci).number_format = fmt

for ci in [9, 10, 11]:
    cl = get_column_letter(ci)
    ws1.cell(row=TOT_ROW, column=ci).value = f'=SUM({cl}{DATA_START}:{cl}{DATA_END})'
    ws1.cell(row=TOT_ROW, column=ci).number_format = num_fmt_dec1

ws1.cell(row=TOT_ROW, column=12).value = f'=SUM(L{DATA_START}:L{DATA_END})'
ws1.cell(row=TOT_ROW, column=12).number_format = num_fmt_int

ws1.cell(row=TOT_ROW, column=13).value = f'=ROUNDUP(K{TOT_ROW},0)-L{TOT_ROW}'
ws1.cell(row=TOT_ROW, column=13).number_format = '\\+#,##0;\\-#,##0;0'

ws1.cell(row=TOT_ROW, column=14).value = f'=SUM(N{DATA_START}:N{DATA_END})'
ws1.cell(row=TOT_ROW, column=14).number_format = num_fmt_int

ws1.cell(row=TOT_ROW, column=15).value = f'=SUM(O{DATA_START}:O{DATA_END})'
ws1.cell(row=TOT_ROW, column=15).number_format = num_fmt_int

ws1.cell(row=TOT_ROW, column=16).value = f'=O{TOT_ROW}-N{TOT_ROW}'
ws1.cell(row=TOT_ROW, column=16).number_format = '\\+#,##0;\\-#,##0;0'

ws1.cell(row=TOT_ROW, column=17).value = f'=IF(N{TOT_ROW}>0, (O{TOT_ROW}-N{TOT_ROW})/N{TOT_ROW}, 0)'
ws1.cell(row=TOT_ROW, column=17).number_format = num_fmt_pct

# ── Conditional formatting ──
ws1.conditional_formatting.add(
    f'M{DATA_START}:M{DATA_END}',
    CellIsRule(operator='greaterThan', formula=['0'],
              fill=PatternFill('solid', fgColor='FFCCCC'),
              font=Font(color=RED_HEX, bold=True))
)
ws1.conditional_formatting.add(
    f'M{DATA_START}:M{DATA_END}',
    CellIsRule(operator='lessThan', formula=['0'],
              fill=PatternFill('solid', fgColor='CCFFCC'),
              font=Font(color=GREEN_HEX, bold=True))
)
ws1.conditional_formatting.add(
    f'Q{DATA_START}:Q{DATA_END}',
    CellIsRule(operator='greaterThan', formula=['0'],
              font=Font(color=GREEN_HEX, bold=True))
)
ws1.conditional_formatting.add(
    f'Q{DATA_START}:Q{DATA_END}',
    CellIsRule(operator='lessThan', formula=['0'],
              font=Font(color=RED_HEX, bold=True))
)
ws1.conditional_formatting.add(
    f'K{DATA_START}:K{DATA_END}',
    DataBarRule(start_type='min', end_type='max', color=LIGHT_BLUE)
)

# ── Quick Summary Dashboard ──
SUM_ROW = TOT_ROW + 2
add_section_header(ws1, SUM_ROW, 1, 8, 'Quick Summary Dashboard', BLUE)

labels_vals = [
    ('Total Machines Available (Running):', f'=L{TOT_ROW}', num_fmt_int),
    ('Total Machines in Shutdown:', n_shutdown, None),
    ('Total Machines (All):', f'=L{TOT_ROW}+{n_shutdown}', None),
    ('', None, None),
    ('Current MC Usage:', f'=L{TOT_ROW}', num_fmt_int),
    ('MC Required at NEW Loading (NEW UPH):', f'=ROUNDUP(K{TOT_ROW},0)', num_fmt_int),
    ('Machine Gap (+ = need more):', f'=ROUNDUP(K{TOT_ROW},0)-L{TOT_ROW}', '\\+#,##0;\\-#,##0;0'),
    ('', None, None),
    ('Current Total Output/Day:', f'=N{TOT_ROW}', num_fmt_int),
    ('NEW Total Output/Day:', f'=O{TOT_ROW}', num_fmt_int),
    ('Output Change:', f'=O{TOT_ROW}-N{TOT_ROW}', '\\+#,##0;\\-#,##0;0'),
    ('Output Change %:', f'=IF(N{TOT_ROW}>0,(O{TOT_ROW}-N{TOT_ROW})/N{TOT_ROW},0)', num_fmt_pct),
]

for j, (label, val, fmt) in enumerate(labels_vals):
    r = SUM_ROW + 1 + j
    ws1.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
    c = ws1.cell(row=r, column=1)
    c.value = label
    c.font = Font(name='Calibri', bold=True, size=11, color=DARK_GRAY)
    c.alignment = Alignment(horizontal='right', vertical='center')

    ws1.merge_cells(start_row=r, start_column=6, end_row=r, end_column=8)
    c2 = ws1.cell(row=r, column=6)
    c2.value = val
    c2.font = Font(name='Calibri', bold=True, size=13, color=BLUE)
    c2.alignment = Alignment(horizontal='center', vertical='center')
    c2.fill = PatternFill('solid', fgColor='E3F2FD')
    c2.border = thin_border
    if fmt:
        c2.number_format = fmt

# ── Instructions ──
INST_ROW = SUM_ROW + len(labels_vals) + 2
add_section_header(ws1, INST_ROW, 1, 8, 'How to Use', LIGHT_BLUE)
instructions = [
    '1. Change values in YELLOW cells to simulate new loading scenarios',
    '2. Column E (NEW DRR): Enter the new daily demand rate for each package',
    '3. Column H (NEW UPH): Enter the expected UPH after optimization',
    '4. Cell B3 (Operating Hours): Change if shift schedule is different',
    '5. Results update automatically — check MC Gap and Output Change columns',
    '6. Positive MC Gap (red) = need more machines, Negative (green) = surplus',
    '7. Use the Scenario sheet to compare multiple loading scenarios side by side',
]
for j, inst in enumerate(instructions):
    r = INST_ROW + 1 + j
    ws1.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
    c = ws1.cell(row=r, column=1)
    c.value = inst
    c.font = Font(name='Calibri', size=10, color=DARK_GRAY)

ws1.freeze_panes = 'C6'

# ======================================================================
#  SHEET 2: Scenario Comparison
# ======================================================================
ws2 = wb.create_sheet('Scenario Comparison')
ws2.sheet_properties.tabColor = ORANGE_HEX

ws2.merge_cells('A1:K1')
ws2['A1'] = 'Loading Scenario Comparison — Enter multipliers to simulate % loading changes'
ws2['A1'].font = Font(name='Calibri', bold=True, size=14, color=BLUE)
ws2.row_dimensions[1].height = 30

ws2['A3'] = 'Scenario Name:'
ws2['A3'].font = Font(name='Calibri', bold=True, size=11, color=DARK_GRAY)
ws2['A4'] = 'DRR Multiplier:'
ws2['A4'].font = Font(name='Calibri', bold=True, size=11, color=DARK_GRAY)
ws2['A5'] = 'UPH Multiplier:'
ws2['A5'].font = Font(name='Calibri', bold=True, size=11, color=DARK_GRAY)
ws2['A6'] = 'Hours/Day:'
ws2['A6'].font = Font(name='Calibri', bold=True, size=11, color=DARK_GRAY)

scenarios = [
    ('Current\n(Baseline)', 1.0, 1.0, 21),
    ('+20% Loading', 1.2, 1.0, 21),
    ('+50% Loading', 1.5, 1.0, 21),
    ('+20% Load\n+UPH Optimize', 1.2, 1.17, 21),
    ('+50% Load\n+UPH Optimize', 1.5, 1.17, 21),
]
sc_cols = ['C', 'E', 'G', 'I', 'K']

ws2.column_dimensions['A'].width = 22
ws2.column_dimensions['B'].width = 13
for col in sc_cols:
    ws2.column_dimensions[col].width = 14

for idx, (name, drr_m, uph_m, hrs) in enumerate(scenarios):
    col = sc_cols[idx]
    ci = openpyxl.utils.column_index_from_string(col)

    c = ws2.cell(row=3, column=ci)
    c.value = name
    c.font = Font(name='Calibri', bold=True, size=11, color=BLUE)
    c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    c.fill = input_fill

    c = style_input_cell(ws2, 4, ci)
    c.value = drr_m
    c.number_format = '0.00'

    c = style_input_cell(ws2, 5, ci)
    c.value = uph_m
    c.number_format = '0.00'

    c = style_input_cell(ws2, 6, ci)
    c.value = hrs
    c.number_format = '0'

ws2.row_dimensions[3].height = 35

# Header row
SC_HDR = 8
ws2[f'A{SC_HDR}'] = 'Package'
ws2[f'B{SC_HDR}'] = 'Current\nDRR'
for idx, col in enumerate(sc_cols):
    ws2[f'{col}{SC_HDR}'] = f'Scenario {idx+1}\nMC Required'
style_header_row(ws2, SC_HDR, 11)
ws2.row_dimensions[SC_HDR].height = 35

# Data rows
for i, p in enumerate(packages):
    r = SC_HDR + 1 + i
    is_alt = i % 2 == 0

    style_data_cell(ws2, r, 1, is_alt, 'left').value = p['pkg']
    c = style_data_cell(ws2, r, 2, is_alt)
    c.value = p['drr']
    c.number_format = num_fmt_int

    cur_uph = p['cur_uph'] if p['cur_uph'] > 0 else (p['std_uph'] if p['std_uph'] > 0 else 1)
    for idx2, col in enumerate(sc_cols):
        ci = openpyxl.utils.column_index_from_string(col)
        c = style_result_cell(ws2, r, ci)
        c.value = f'=IF({cur_uph}*{col}$5*{col}$6>0, B{r}*{col}$4/({cur_uph}*{col}$5*{col}$6), 0)'
        c.number_format = num_fmt_dec1

SC_DATA_END = SC_HDR + n_pkgs

# Total row
TOT2 = SC_DATA_END + 1
for ci in range(1, 12):
    cell = ws2.cell(row=TOT2, column=ci)
    cell.font = header_font
    cell.fill = header_fill
    cell.alignment = normal_align
    cell.border = thin_border

ws2.cell(row=TOT2, column=1).value = 'TOTAL MC Required'
ws2.cell(row=TOT2, column=1).alignment = left_align
ws2.cell(row=TOT2, column=2).value = f'=SUM(B{SC_HDR+1}:B{SC_DATA_END})'
ws2.cell(row=TOT2, column=2).number_format = num_fmt_int

for col in sc_cols:
    ci = openpyxl.utils.column_index_from_string(col)
    ws2.cell(row=TOT2, column=ci).value = f'=SUM({col}{SC_HDR+1}:{col}{SC_DATA_END})'
    ws2.cell(row=TOT2, column=ci).number_format = num_fmt_dec1

# Current MC Available
CUR_ROW = TOT2 + 1
ws2.cell(row=CUR_ROW, column=1).value = 'Current MC Available'
ws2.cell(row=CUR_ROW, column=1).font = Font(name='Calibri', bold=True, size=11, color=DARK_GRAY)
ws2.cell(row=CUR_ROW, column=2).value = n_running
ws2.cell(row=CUR_ROW, column=2).font = Font(name='Calibri', bold=True, size=13, color=GREEN_HEX)

# MC Gap
GAP_ROW = TOT2 + 2
ws2.cell(row=GAP_ROW, column=1).value = 'MC Gap (+ = need more)'
ws2.cell(row=GAP_ROW, column=1).font = Font(name='Calibri', bold=True, size=11, color=RED_HEX)
for col in sc_cols:
    ci = openpyxl.utils.column_index_from_string(col)
    c = ws2.cell(row=GAP_ROW, column=ci)
    c.value = f'=ROUNDUP({col}{TOT2},0)-$B${CUR_ROW}'
    c.number_format = '\\+#,##0;\\-#,##0;0'
    c.font = Font(name='Calibri', bold=True, size=13, color=RED_HEX)

# Conditional formatting for gap
for col in sc_cols:
    ci = openpyxl.utils.column_index_from_string(col)
    cell_ref = f'{col}{GAP_ROW}'
    ws2.conditional_formatting.add(
        cell_ref,
        CellIsRule(operator='greaterThan', formula=['0'],
                  fill=PatternFill('solid', fgColor='FFCCCC'),
                  font=Font(color=RED_HEX, bold=True, size=13))
    )
    ws2.conditional_formatting.add(
        cell_ref,
        CellIsRule(operator='lessThanOrEqual', formula=['0'],
                  fill=PatternFill('solid', fgColor='CCFFCC'),
                  font=Font(color=GREEN_HEX, bold=True, size=13))
    )

ws2.freeze_panes = f'C{SC_HDR+1}'

# ======================================================================
#  SHEET 3: UPH Reference
# ======================================================================
ws3 = wb.create_sheet('UPH Reference')
ws3.sheet_properties.tabColor = GREEN_HEX

ws3.merge_cells('A1:G1')
ws3['A1'] = 'DA Machine UPH Reference Data'
ws3['A1'].font = Font(name='Calibri', bold=True, size=14, color=BLUE)
ws3.row_dimensions[1].height = 30

uph_headers = ['No.', 'Package', 'STD UPH IE', 'STD UPH', 'Current UPH', '% UPH Diff', 'MC Required\n(Cur UPH)']
for i, h in enumerate(uph_headers):
    ws3.cell(row=3, column=i+1).value = h
style_header_row(ws3, 3, 7)
ws3.row_dimensions[3].height = 35

ws3.column_dimensions['A'].width = 5
ws3.column_dimensions['B'].width = 22
ws3.column_dimensions['C'].width = 14
ws3.column_dimensions['D'].width = 14
ws3.column_dimensions['E'].width = 14
ws3.column_dimensions['F'].width = 14
ws3.column_dimensions['G'].width = 14

for i, p in enumerate(packages):
    r = 4 + i
    is_alt = i % 2 == 0

    style_data_cell(ws3, r, 1, is_alt).value = i + 1
    style_data_cell(ws3, r, 2, is_alt, 'left').value = p['pkg']

    c = style_data_cell(ws3, r, 3, is_alt)
    c.value = p['std_ie'] if p['std_ie'] else '-'
    if p['std_ie']:
        c.number_format = num_fmt_int

    c = style_data_cell(ws3, r, 4, is_alt)
    c.value = p['std_uph'] if p['std_uph'] else '-'
    if p['std_uph']:
        c.number_format = num_fmt_int

    c = style_data_cell(ws3, r, 5, is_alt)
    c.value = p['cur_uph'] if p['cur_uph'] else '-'
    if p['cur_uph']:
        c.number_format = num_fmt_int

    # % UPH Diff (STD vs Current)
    c = style_data_cell(ws3, r, 6, is_alt)
    if p['std_uph'] and p['cur_uph'] and p['std_uph'] > 0:
        diff = (p['std_uph'] - p['cur_uph']) / p['std_uph']
        c.value = diff
        c.number_format = num_fmt_pct
        if diff > 0.1:
            c.font = Font(name='Calibri', bold=True, color=RED_HEX)
        elif diff > 0:
            c.font = Font(name='Calibri', bold=True, color=ORANGE_HEX)
        else:
            c.font = Font(name='Calibri', bold=True, color=GREEN_HEX)
    else:
        c.value = '-'

    # MC Required at Current UPH
    c = style_data_cell(ws3, r, 7, is_alt)
    if p['cur_uph'] and p['drr']:
        c.value = p['drr'] / (p['cur_uph'] * 21)
        c.number_format = num_fmt_dec1
    else:
        c.value = '-'

# Data bars on Current UPH
ws3.conditional_formatting.add(
    f'E4:E{3+n_pkgs}',
    DataBarRule(start_type='min', end_type='max', color=LIGHT_BLUE)
)

ws3.freeze_panes = 'A4'

# ======================================================================
#  SHEET 4: Machine List
# ======================================================================
ws4 = wb.create_sheet('Machine List')
ws4.sheet_properties.tabColor = ORANGE_HEX

ws4.merge_cells('A1:F1')
ws4['A1'] = 'DA Machine List & Status'
ws4['A1'].font = Font(name='Calibri', bold=True, size=14, color=BLUE)
ws4.row_dimensions[1].height = 30

ml_headers = ['No', 'Machine ID', 'Package', 'Status', 'Available', 'Notes']
for i, h in enumerate(ml_headers):
    ws4.cell(row=3, column=i+1).value = h
style_header_row(ws4, 3, 6)

ws4.column_dimensions['A'].width = 5
ws4.column_dimensions['B'].width = 18
ws4.column_dimensions['C'].width = 18
ws4.column_dimensions['D'].width = 20
ws4.column_dimensions['E'].width = 10
ws4.column_dimensions['F'].width = 18

for i, (mc_id, pkg_name, status) in enumerate(all_machines):
    r = 4 + i
    is_alt = i % 2 == 0

    style_data_cell(ws4, r, 1, is_alt).value = i + 1
    style_data_cell(ws4, r, 2, is_alt, 'left').value = mc_id
    style_data_cell(ws4, r, 3, is_alt, 'left').value = pkg_name

    c = style_data_cell(ws4, r, 4, is_alt)
    c.value = status
    if status == 'Run':
        c.font = Font(name='Calibri', size=11, color=GREEN_HEX, bold=True)
    elif 'Shutdown' in status:
        c.font = Font(name='Calibri', size=11, color=RED_HEX, bold=True)
    else:
        c.font = Font(name='Calibri', size=11, color=ORANGE_HEX, bold=True)

    c = style_data_cell(ws4, r, 5, is_alt)
    c.value = 1 if status == 'Run' else 0

    style_data_cell(ws4, r, 6, is_alt, 'left').value = ''

ML_END = 3 + len(all_machines)

# Conditional formatting for status
ws4.conditional_formatting.add(
    f'D4:D{ML_END}',
    CellIsRule(operator='equal', formula=['"Run"'],
              fill=PatternFill('solid', fgColor='CCFFCC'))
)
ws4.conditional_formatting.add(
    f'D4:D{ML_END}',
    CellIsRule(operator='equal', formula=['"Machine Shutdown"'],
              fill=PatternFill('solid', fgColor='FFCCCC'))
)

# Summary
sr = ML_END + 2
ws4.cell(row=sr, column=4).value = 'Total Running:'
ws4.cell(row=sr, column=4).font = Font(name='Calibri', bold=True, size=11)
ws4.cell(row=sr, column=5).value = f'=COUNTIF(D4:D{ML_END},"Run")'
ws4.cell(row=sr, column=5).font = Font(name='Calibri', bold=True, size=13, color=GREEN_HEX)

ws4.cell(row=sr+1, column=4).value = 'Total Shutdown:'
ws4.cell(row=sr+1, column=4).font = Font(name='Calibri', bold=True, size=11)
ws4.cell(row=sr+1, column=5).value = f'=COUNTIF(D4:D{ML_END},"Machine Shutdown")'
ws4.cell(row=sr+1, column=5).font = Font(name='Calibri', bold=True, size=13, color=RED_HEX)

ws4.cell(row=sr+2, column=4).value = 'Total:'
ws4.cell(row=sr+2, column=4).font = Font(name='Calibri', bold=True, size=11)
ws4.cell(row=sr+2, column=5).value = f'=COUNTA(D4:D{ML_END})'
ws4.cell(row=sr+2, column=5).font = Font(name='Calibri', bold=True, size=13, color=BLUE)

ws4.freeze_panes = 'A4'

# ======================================================================
#  SHEET 5: Action Items
# ======================================================================
ws5 = wb.create_sheet('Action Items')
ws5.sheet_properties.tabColor = RED_HEX

ws5.merge_cells('A1:B1')
ws5['A1'] = 'Recommended Action Items'
ws5['A1'].font = Font(name='Calibri', bold=True, size=14, color=BLUE)
ws5.row_dimensions[1].height = 30

ws5.column_dimensions['A'].width = 5
ws5.column_dimensions['B'].width = 65

header_cell_ai = ['No.', 'Action Item']
for i, h in enumerate(header_cell_ai):
    ws5.cell(row=3, column=i+1).value = h
style_header_row(ws5, 3, 2)

for i, action in enumerate(actions):
    r = 4 + i
    is_alt = i % 2 == 0
    style_data_cell(ws5, r, 1, is_alt).value = i + 1
    style_data_cell(ws5, r, 2, is_alt, 'left').value = action

# ── Save ─────────────────────────────────────────────────────────────────
wb.save(OUTPUT_PATH)
print(f'\nSaved: {OUTPUT_PATH}')
print(f'Sheets: {wb.sheetnames}')
print(f'Packages: {n_pkgs}, Machines: {len(all_machines)}')
print(f'Running: {n_running}, Shutdown: {n_shutdown}')
