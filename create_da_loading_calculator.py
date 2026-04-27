import sys, os
sys.stdout.reconfigure(encoding='utf-8')

import openpyxl
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, numbers
)
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import CellIsRule, DataBarRule
from copy import copy

# ── Paths ────────────────────────────────────────────────────────────────
EXCEL_PATH = os.path.join('raw', 'DA_machine.xls.xlsx')
OUTPUT_DIR = 'Output'
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_PATH = os.path.join(OUTPUT_DIR, 'DA_Loading_Calculator.xlsx')

# ── Load source data ─────────────────────────────────────────────────────
src = openpyxl.load_workbook(EXCEL_PATH, data_only=True)

# MTAI ASSY DA
ws_cap = src['MTAI ASSY DA']
packages = []
for row in ws_cap.iter_rows(min_row=3, max_row=24, values_only=True):
    _, item, pkg, max_cap_mold, drr_max, std_uph, cur_uph, uph_diff, std_req, cur_da, mc_no, mc_shutdown, _, cur_usage, cur_output = row
    if pkg and pkg != 'Total':
        packages.append({
            'pkg': pkg,
            'max_cap_mold': max_cap_mold or 0,
            'drr_max': drr_max or 0,
            'std_uph': std_uph or 0,
            'cur_uph': cur_uph or 0,
            'std_req': std_req or 0,
            'cur_da': cur_da or 0,
            'mc_no': mc_no or '',
            'mc_shutdown': mc_shutdown or '',
            'cur_usage': cur_usage or 0,
            'cur_output': cur_output or 0,
        })

# DA_UPH reference
ws_uph = src['DA_UPH']
uph_ref = []
for row in ws_uph.iter_rows(min_row=2, max_row=ws_uph.max_row, values_only=True):
    mc, mc_type, pkg, die_size, uph = row
    if mc:
        uph_ref.append({'mc': mc, 'type': mc_type, 'pkg': pkg, 'die_size': die_size, 'uph': uph or 0})

# ── Styles ───────────────────────────────────────────────────────────────
BLUE       = '0E3689'
LIGHT_BLUE = '1D9CE4'
GREEN_HEX  = '5EBF33'
ORANGE_HEX = 'FD7F20'
RED_HEX    = 'CC0000'
DARK_GRAY  = '4A4A4A'
MED_GRAY   = '8A8A8A'
LIGHT_GRAY = 'D9D9D9'
VLIGHT     = 'F7F7F7'

header_font = Font(name='Calibri', bold=True, size=11, color='FFFFFF')
header_fill = PatternFill('solid', fgColor=BLUE)
header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)

input_font = Font(name='Calibri', bold=True, size=12, color=BLUE)
input_fill = PatternFill('solid', fgColor='FFFFCC')  # light yellow = editable
input_border = Border(
    left=Side(style='medium', color=BLUE),
    right=Side(style='medium', color=BLUE),
    top=Side(style='medium', color=BLUE),
    bottom=Side(style='medium', color=BLUE),
)

result_font = Font(name='Calibri', bold=True, size=11, color=BLUE)
result_fill = PatternFill('solid', fgColor='E3F2FD')

normal_font = Font(name='Calibri', size=11, color='000000')
normal_align = Alignment(horizontal='center', vertical='center')
left_align = Alignment(horizontal='left', vertical='center')
num_fmt_int = '#,##0'
num_fmt_dec1 = '#,##0.0'
num_fmt_dec2 = '#,##0.00'
num_fmt_pct = '0.0%'

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

# ── Create workbook ──────────────────────────────────────────────────────
wb = openpyxl.Workbook()

# =====================================================================
# SHEET 1: Calculator (main)
# =====================================================================
ws1 = wb.active
ws1.title = 'Loading Calculator'
ws1.sheet_properties.tabColor = BLUE

# --- Global Parameters ---
ws1.merge_cells('A1:R1')
cell = ws1['A1']
cell.value = 'DA Machine Loading Calculator — Change yellow cells to simulate different loading scenarios'
cell.font = Font(name='Calibri', bold=True, size=16, color=BLUE)
cell.alignment = Alignment(horizontal='left', vertical='center')
ws1.row_dimensions[1].height = 35

# Operating hours parameter
ws1['A3'] = 'Operating Hours/Day:'
ws1['A3'].font = Font(name='Calibri', bold=True, size=11, color=DARK_GRAY)
ws1['B3'] = 21
style_input_cell(ws1, 3, 2)
ws1['B3'].number_format = '0'
ws1['C3'] = 'hrs (editable — default 21 hrs for 3-shift operation)'
ws1['C3'].font = Font(name='Calibri', size=10, color=MED_GRAY)

ws1.row_dimensions[4].height = 8  # spacer

# --- Column headers ---
HDR_ROW = 5
headers = [
    ('A', 'No.'),
    ('B', 'Package'),
    ('C', 'Max CAP\nMold'),
    ('D', 'Current\nDRR'),
    ('E', 'NEW DRR\n(Input)'),
    ('F', 'STD UPH'),
    ('G', 'Current\nUPH'),
    ('H', 'NEW UPH\n(Input)'),
    ('I', 'MC Required\n(STD UPH)'),
    ('J', 'MC Required\n(Cur UPH)'),
    ('K', 'MC Required\n(NEW)'),
    ('L', 'Current\nMC Usage'),
    ('M', 'MC Gap\nvs Current'),
    ('N', 'Current\nOutput/Day'),
    ('O', 'NEW\nOutput/Day'),
    ('P', 'Output\nChange'),
    ('Q', 'Output\nChange %'),
    ('R', 'Shutdown\nMCs'),
]

for col_letter, title in headers:
    ws1[f'{col_letter}{HDR_ROW}'] = title
style_header_row(ws1, HDR_ROW, 18)
ws1.row_dimensions[HDR_ROW].height = 40

# Column widths
col_widths = {
    'A': 5, 'B': 22, 'C': 13, 'D': 13, 'E': 14, 'F': 11, 'G': 11, 'H': 13,
    'I': 13, 'J': 13, 'K': 13, 'L': 11, 'M': 11, 'N': 14, 'O': 14, 'P': 14, 'Q': 11, 'R': 12,
}
for col, w in col_widths.items():
    ws1.column_dimensions[col].width = w

# --- Data rows ---
DATA_START = 6
for i, p in enumerate(packages):
    r = DATA_START + i
    is_alt = i % 2 == 0
    ws1.row_dimensions[r].height = 22

    # A: No
    c = style_data_cell(ws1, r, 1, is_alt)
    c.value = i + 1

    # B: Package
    c = style_data_cell(ws1, r, 2, is_alt, 'left')
    c.value = p['pkg']

    # C: Max CAP Mold
    c = style_data_cell(ws1, r, 3, is_alt)
    c.value = p['max_cap_mold'] if p['max_cap_mold'] else None
    c.number_format = num_fmt_int

    # D: Current DRR
    c = style_data_cell(ws1, r, 4, is_alt)
    c.value = p['drr_max']
    c.number_format = num_fmt_int

    # E: NEW DRR (INPUT — yellow)
    c = style_input_cell(ws1, r, 5)
    c.value = p['drr_max']
    c.number_format = num_fmt_int

    # F: STD UPH
    c = style_data_cell(ws1, r, 6, is_alt)
    c.value = p['std_uph']
    c.number_format = num_fmt_int

    # G: Current UPH
    c = style_data_cell(ws1, r, 7, is_alt)
    c.value = p['cur_uph']
    c.number_format = num_fmt_int

    # H: NEW UPH (INPUT — yellow)
    c = style_input_cell(ws1, r, 8)
    c.value = p['cur_uph']
    c.number_format = num_fmt_int

    # I: MC Required (STD UPH) = NEW DRR / (STD UPH * hours)
    c = style_result_cell(ws1, r, 9)
    c.value = f'=IF(F{r}>0, E{r}/(F{r}*$B$3), 0)'
    c.number_format = num_fmt_dec1

    # J: MC Required (Cur UPH) = NEW DRR / (Cur UPH * hours)
    c = style_result_cell(ws1, r, 10)
    c.value = f'=IF(G{r}>0, E{r}/(G{r}*$B$3), 0)'
    c.number_format = num_fmt_dec1

    # K: MC Required (NEW UPH) = NEW DRR / (NEW UPH * hours)
    c = style_result_cell(ws1, r, 11)
    c.value = f'=IF(H{r}>0, E{r}/(H{r}*$B$3), 0)'
    c.number_format = num_fmt_dec1

    # L: Current MC Usage
    c = style_data_cell(ws1, r, 12, is_alt)
    c.value = int(p['cur_usage']) if p['cur_usage'] else 0
    c.number_format = num_fmt_int

    # M: MC Gap = MC Required (NEW) - Current Usage
    c = style_result_cell(ws1, r, 13)
    c.value = f'=ROUNDUP(K{r},0)-L{r}'
    c.number_format = '+#,##0;-#,##0;0'

    # N: Current Output/Day
    c = style_data_cell(ws1, r, 14, is_alt)
    c.value = p['cur_output'] if p['cur_output'] else 0
    c.number_format = num_fmt_int

    # O: NEW Output/Day = min(NEW DRR, L * NEW UPH * hours)
    c = style_result_cell(ws1, r, 15)
    c.value = f'=MIN(E{r}, L{r}*H{r}*$B$3)'
    c.number_format = num_fmt_int

    # P: Output Change = NEW - Current
    c = style_result_cell(ws1, r, 16)
    c.value = f'=O{r}-N{r}'
    c.number_format = '+#,##0;-#,##0;0'

    # Q: Output Change %
    c = style_result_cell(ws1, r, 17)
    c.value = f'=IF(N{r}>0, (O{r}-N{r})/N{r}, 0)'
    c.number_format = num_fmt_pct

    # R: Shutdown MCs
    c = style_data_cell(ws1, r, 18, is_alt, 'left')
    c.value = str(p['mc_shutdown']) if p['mc_shutdown'] else '-'

DATA_END = DATA_START + len(packages) - 1

# --- Total row ---
TOT_ROW = DATA_END + 1
ws1.row_dimensions[TOT_ROW].height = 28
for col in range(1, 19):
    cell = ws1.cell(row=TOT_ROW, column=col)
    cell.font = Font(name='Calibri', bold=True, size=11, color='FFFFFF')
    cell.fill = PatternFill('solid', fgColor=BLUE)
    cell.alignment = normal_align
    cell.border = thin_border

ws1.cell(row=TOT_ROW, column=2).value = 'TOTAL'
ws1.cell(row=TOT_ROW, column=2).alignment = left_align

for col_idx, fmt in [(3, num_fmt_int), (4, num_fmt_int), (5, num_fmt_int)]:
    cl = get_column_letter(col_idx)
    ws1.cell(row=TOT_ROW, column=col_idx).value = f'=SUM({cl}{DATA_START}:{cl}{DATA_END})'
    ws1.cell(row=TOT_ROW, column=col_idx).number_format = fmt

for col_idx in [9, 10, 11]:
    cl = get_column_letter(col_idx)
    ws1.cell(row=TOT_ROW, column=col_idx).value = f'=SUM({cl}{DATA_START}:{cl}{DATA_END})'
    ws1.cell(row=TOT_ROW, column=col_idx).number_format = num_fmt_dec1

ws1.cell(row=TOT_ROW, column=12).value = f'=SUM(L{DATA_START}:L{DATA_END})'
ws1.cell(row=TOT_ROW, column=12).number_format = num_fmt_int

ws1.cell(row=TOT_ROW, column=13).value = f'=ROUNDUP(K{TOT_ROW},0)-L{TOT_ROW}'
ws1.cell(row=TOT_ROW, column=13).number_format = '+#,##0;-#,##0;0'

ws1.cell(row=TOT_ROW, column=14).value = f'=SUM(N{DATA_START}:N{DATA_END})'
ws1.cell(row=TOT_ROW, column=14).number_format = num_fmt_int

ws1.cell(row=TOT_ROW, column=15).value = f'=SUM(O{DATA_START}:O{DATA_END})'
ws1.cell(row=TOT_ROW, column=15).number_format = num_fmt_int

ws1.cell(row=TOT_ROW, column=16).value = f'=O{TOT_ROW}-N{TOT_ROW}'
ws1.cell(row=TOT_ROW, column=16).number_format = '+#,##0;-#,##0;0'

ws1.cell(row=TOT_ROW, column=17).value = f'=IF(N{TOT_ROW}>0, (O{TOT_ROW}-N{TOT_ROW})/N{TOT_ROW}, 0)'
ws1.cell(row=TOT_ROW, column=17).number_format = num_fmt_pct

# --- Conditional formatting ---
# MC Gap: red if positive (need more), green if negative (surplus)
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

# Output Change %: green if positive, red if negative
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

# Data bars on MC Required (NEW)
ws1.conditional_formatting.add(
    f'K{DATA_START}:K{DATA_END}',
    DataBarRule(start_type='min', end_type='max', color=LIGHT_BLUE)
)

# --- Summary box below table ---
SUM_ROW = TOT_ROW + 2
add_section_header(ws1, SUM_ROW, 1, 8, 'Quick Summary Dashboard', BLUE)

labels_vals = [
    ('Total Machines Available (Running):', 98, None),
    ('Total Machines in Shutdown:', 16, None),
    ('Total Machines (All):', 114, None),
    ('', None, None),
    ('Current MC Usage:', f'=L{TOT_ROW}', num_fmt_int),
    ('MC Required at NEW Loading (NEW UPH):', f'=ROUNDUP(K{TOT_ROW},0)', num_fmt_int),
    ('Machine Gap (+ = need more):', f'=ROUNDUP(K{TOT_ROW},0)-L{TOT_ROW}', '+#,##0;-#,##0;0'),
    ('', None, None),
    ('Current Total Output/Day:', f'=N{TOT_ROW}', num_fmt_int),
    ('NEW Total Output/Day:', f'=O{TOT_ROW}', num_fmt_int),
    ('Output Change:', f'=O{TOT_ROW}-N{TOT_ROW}', '+#,##0;-#,##0;0'),
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

# --- Instructions ---
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
    c.alignment = Alignment(horizontal='left', vertical='center')

# Freeze panes
ws1.freeze_panes = 'C6'

# =====================================================================
# SHEET 2: Scenario Comparison
# =====================================================================
ws2 = wb.create_sheet('Scenario Comparison')
ws2.sheet_properties.tabColor = ORANGE_HEX

ws2.merge_cells('A1:N1')
ws2['A1'] = 'Loading Scenario Comparison — Enter multipliers to simulate % loading changes'
ws2['A1'].font = Font(name='Calibri', bold=True, size=14, color=BLUE)
ws2.row_dimensions[1].height = 30

# Scenario parameters
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
for idx, (name, drr_m, uph_m, hrs) in enumerate(scenarios):
    col = sc_cols[idx]
    col2 = get_column_letter(ord(col) - 64 + 1)  # next col for merge
    ws2.merge_cells(f'{col}3:{col2}3')
    c = ws2[f'{col}3']
    c.value = name
    style_input_cell(ws2, 3, ord(col) - 64)
    c.font = Font(name='Calibri', bold=True, size=11, color=BLUE)
    c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    ws2.merge_cells(f'{col}4:{col2}4')
    c = style_input_cell(ws2, 4, ord(col) - 64)
    c.value = drr_m
    c.number_format = '0.00'

    ws2.merge_cells(f'{col}5:{col2}5')
    c = style_input_cell(ws2, 5, ord(col) - 64)
    c.value = uph_m
    c.number_format = '0.00'

    ws2.merge_cells(f'{col}6:{col2}6')
    c = style_input_cell(ws2, 6, ord(col) - 64)
    c.value = hrs
    c.number_format = '0'

ws2.row_dimensions[3].height = 35

# Scenario results table
SC_HDR = 8
ws2[f'A{SC_HDR}'] = 'Package'
ws2[f'B{SC_HDR}'] = 'Current\nDRR'
for idx, col in enumerate(sc_cols):
    col2 = get_column_letter(ord(col) - 64 + 1)
    ws2.merge_cells(f'{col}{SC_HDR}:{col2}{SC_HDR}')
    ws2[f'{col}{SC_HDR}'] = f'Scenario {idx+1}\nMC Required'

style_header_row(ws2, SC_HDR, 12)
ws2.row_dimensions[SC_HDR].height = 35

ws2.column_dimensions['A'].width = 22
ws2.column_dimensions['B'].width = 13
for col in sc_cols:
    ws2.column_dimensions[col].width = 10
    ws2.column_dimensions[get_column_letter(ord(col) - 64 + 1)].width = 5

# Data rows
for i, p in enumerate(packages):
    r = SC_HDR + 1 + i
    is_alt = i % 2 == 0

    c = style_data_cell(ws2, r, 1, is_alt, 'left')
    c.value = p['pkg']

    c = style_data_cell(ws2, r, 2, is_alt)
    c.value = p['drr_max']
    c.number_format = num_fmt_int

    for idx, col in enumerate(sc_cols):
        col_num = ord(col) - 64
        col2_num = col_num + 1
        ws2.merge_cells(start_row=r, start_column=col_num, end_row=r, end_column=col2_num)
        c = style_result_cell(ws2, r, col_num)
        # Formula: DRR * DRR_mult / (CurUPH * UPH_mult * Hours)
        cur_uph = p['cur_uph'] if p['cur_uph'] > 0 else 1
        # Reference: B{r} = DRR, {col}4 = DRR_mult, cur_uph constant, {col}5 = UPH_mult, {col}6 = hours
        c.value = f'=IF({cur_uph}*{col}$5*{col}$6>0, B{r}*{col}$4/({cur_uph}*{col}$5*{col}$6), 0)'
        c.number_format = num_fmt_dec1

SC_DATA_END = SC_HDR + len(packages)

# Total row
TOT2 = SC_DATA_END + 1
for col_num in range(1, 13):
    cell = ws2.cell(row=TOT2, column=col_num)
    cell.font = Font(name='Calibri', bold=True, size=11, color='FFFFFF')
    cell.fill = PatternFill('solid', fgColor=BLUE)
    cell.alignment = normal_align
    cell.border = thin_border

ws2.cell(row=TOT2, column=1).value = 'TOTAL MC Required'
ws2.cell(row=TOT2, column=1).alignment = left_align

ws2.cell(row=TOT2, column=2).value = f'=SUM(B{SC_HDR+1}:B{SC_DATA_END})'
ws2.cell(row=TOT2, column=2).number_format = num_fmt_int

for idx, col in enumerate(sc_cols):
    col_num = ord(col) - 64
    ws2.merge_cells(start_row=TOT2, start_column=col_num, end_row=TOT2, end_column=col_num+1)
    ws2.cell(row=TOT2, column=col_num).value = f'=SUM({col}{SC_HDR+1}:{col}{SC_DATA_END})'
    ws2.cell(row=TOT2, column=col_num).number_format = num_fmt_dec1

# Current MC row
CUR_ROW = TOT2 + 1
ws2.cell(row=CUR_ROW, column=1).value = 'Current MC Available'
ws2.cell(row=CUR_ROW, column=1).font = Font(name='Calibri', bold=True, size=11, color=DARK_GRAY)
ws2.cell(row=CUR_ROW, column=2).value = 94
ws2.cell(row=CUR_ROW, column=2).font = Font(name='Calibri', bold=True, size=13, color=GREEN_HEX)
ws2.cell(row=CUR_ROW, column=2).alignment = normal_align

# Gap row
GAP_ROW = TOT2 + 2
ws2.cell(row=GAP_ROW, column=1).value = 'MC Gap (+ = need more)'
ws2.cell(row=GAP_ROW, column=1).font = Font(name='Calibri', bold=True, size=11, color=RED_HEX)
for idx, col in enumerate(sc_cols):
    col_num = ord(col) - 64
    ws2.merge_cells(start_row=GAP_ROW, start_column=col_num, end_row=GAP_ROW, end_column=col_num+1)
    c = ws2.cell(row=GAP_ROW, column=col_num)
    c.value = f'=ROUNDUP({col}{TOT2},0)-$B${CUR_ROW}'
    c.number_format = '+#,##0;-#,##0;0'
    c.font = Font(name='Calibri', bold=True, size=13, color=RED_HEX)
    c.alignment = normal_align

# Conditional formatting for gap
for col in sc_cols:
    col_num = ord(col) - 64
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

# =====================================================================
# SHEET 3: UPH Reference
# =====================================================================
ws3 = wb.create_sheet('UPH Reference')
ws3.sheet_properties.tabColor = GREEN_HEX

ws3.merge_cells('A1:E1')
ws3['A1'] = 'DA Machine UPH Reference Data'
ws3['A1'].font = Font(name='Calibri', bold=True, size=14, color=BLUE)
ws3.row_dimensions[1].height = 30

uph_headers = ['M/C No', 'M/C Type', 'Package', 'Die Size', 'UPH']
for i, h in enumerate(uph_headers):
    ws3.cell(row=3, column=i+1).value = h
style_header_row(ws3, 3, 5)

ws3.column_dimensions['A'].width = 12
ws3.column_dimensions['B'].width = 14
ws3.column_dimensions['C'].width = 28
ws3.column_dimensions['D'].width = 18
ws3.column_dimensions['E'].width = 10

for i, u in enumerate(uph_ref):
    r = 4 + i
    is_alt = i % 2 == 0
    style_data_cell(ws3, r, 1, is_alt, 'left').value = u['mc']
    style_data_cell(ws3, r, 2, is_alt, 'left').value = u['type']
    style_data_cell(ws3, r, 3, is_alt, 'left').value = u['pkg']
    style_data_cell(ws3, r, 4, is_alt).value = u['die_size']
    c = style_data_cell(ws3, r, 5, is_alt)
    c.value = u['uph']
    c.number_format = num_fmt_int

# Data bars on UPH
ws3.conditional_formatting.add(
    f'E4:E{3+len(uph_ref)}',
    DataBarRule(start_type='min', end_type='max', color=LIGHT_BLUE)
)

ws3.freeze_panes = 'A4'

# =====================================================================
# SHEET 4: Machine List
# =====================================================================
ws4 = wb.create_sheet('Machine List')
ws4.sheet_properties.tabColor = ORANGE_HEX

ws4.merge_cells('A1:F1')
ws4['A1'] = 'Die Bonder Machine List & Status'
ws4['A1'].font = Font(name='Calibri', bold=True, size=14, color=BLUE)
ws4.row_dimensions[1].height = 30

ml_headers = ['No', 'Machine Code', 'Machine Name', 'Model', 'Status', 'Available']
for i, h in enumerate(ml_headers):
    ws4.cell(row=3, column=i+1).value = h
style_header_row(ws4, 3, 6)

ws4.column_dimensions['A'].width = 5
ws4.column_dimensions['B'].width = 18
ws4.column_dimensions['C'].width = 38
ws4.column_dimensions['D'].width = 14
ws4.column_dimensions['E'].width = 18
ws4.column_dimensions['F'].width = 10

# Read all die bonders from source
ws_src = src['DA_machine list']
db_list = []
for row in ws_src.iter_rows(min_row=2, max_row=ws_src.max_row, values_only=True):
    area, mc_code, mc_name, ods, serial, model, accept_date, status = row
    if mc_name and 'Die bonder' in str(mc_name):
        db_list.append({
            'code': mc_code, 'name': mc_name, 'model': model,
            'status': status or '-'
        })

for i, m in enumerate(db_list):
    r = 4 + i
    is_alt = i % 2 == 0
    style_data_cell(ws4, r, 1, is_alt).value = i + 1
    style_data_cell(ws4, r, 2, is_alt, 'left').value = m['code']
    style_data_cell(ws4, r, 3, is_alt, 'left').value = m['name']
    style_data_cell(ws4, r, 4, is_alt, 'left').value = m['model']
    c = style_data_cell(ws4, r, 5, is_alt)
    c.value = m['status']
    if m['status'] == 'Run':
        c.font = Font(name='Calibri', size=11, color=GREEN_HEX, bold=True)
    elif m['status'] == 'Machine Shutdown':
        c.font = Font(name='Calibri', size=11, color=RED_HEX, bold=True)
    # Available = 1 if Run
    c2 = style_data_cell(ws4, r, 6, is_alt)
    c2.value = 1 if m['status'] == 'Run' else 0

ML_END = 3 + len(db_list)

# Summary at bottom
ws4.cell(row=ML_END+2, column=4).value = 'Total Running:'
ws4.cell(row=ML_END+2, column=4).font = Font(name='Calibri', bold=True, size=11)
ws4.cell(row=ML_END+2, column=5).value = f'=COUNTIF(E4:E{ML_END},"Run")'
ws4.cell(row=ML_END+2, column=5).font = Font(name='Calibri', bold=True, size=13, color=GREEN_HEX)

ws4.cell(row=ML_END+3, column=4).value = 'Total Shutdown:'
ws4.cell(row=ML_END+3, column=4).font = Font(name='Calibri', bold=True, size=11)
ws4.cell(row=ML_END+3, column=5).value = f'=COUNTIF(E4:E{ML_END},"Machine Shutdown")'
ws4.cell(row=ML_END+3, column=5).font = Font(name='Calibri', bold=True, size=13, color=RED_HEX)

ws4.cell(row=ML_END+4, column=4).value = 'Total:'
ws4.cell(row=ML_END+4, column=4).font = Font(name='Calibri', bold=True, size=11)
ws4.cell(row=ML_END+4, column=5).value = f'=COUNTA(E4:E{ML_END})'
ws4.cell(row=ML_END+4, column=5).font = Font(name='Calibri', bold=True, size=13, color=BLUE)

ws4.freeze_panes = 'A4'

# Conditional formatting: status
ws4.conditional_formatting.add(
    f'E4:E{ML_END}',
    CellIsRule(operator='equal', formula=['"Run"'],
              fill=PatternFill('solid', fgColor='CCFFCC'))
)
ws4.conditional_formatting.add(
    f'E4:E{ML_END}',
    CellIsRule(operator='equal', formula=['"Machine Shutdown"'],
              fill=PatternFill('solid', fgColor='FFCCCC'))
)

# ── Save ─────────────────────────────────────────────────────────────────
wb.save(OUTPUT_PATH)
print(f'Saved: {OUTPUT_PATH}')
print(f'Sheets: {wb.sheetnames}')
print(f'Packages: {len(packages)}, UPH records: {len(uph_ref)}, Machines: {len(db_list)}')
