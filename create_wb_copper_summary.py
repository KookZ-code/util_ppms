import sys, os
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter, get_column_letter as gcl
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.chart.series import DataPoint
from openpyxl.chart.label import DataLabelList

# ── Load data ────────────────────────────────────────────────────────────────
df = pd.read_excel('raw/Saw_DA_WB machine list.xls.xlsx', sheet_name='WB', header=0)
df['Accept Date'] = pd.to_datetime(df['Accept Date'])
df['Year'] = df['Accept Date'].dt.year
df['Heads'] = df['Model'].apply(lambda x: 2 if ('Twin' in str(x) or 'Harrier' in str(x)) else 1)

df['Remark'] = df['Remark'].fillna('Gold Wire Automotive')

# Harrier ทั้งหมด run copper ได้ ยกเว้น 3 เครื่อง Discoloration
HARRIER_EXCLUDE = {'W/B # 210', 'W/B # 212', 'W/B # 255'}
mask_harrier_cu = (
    df['Model'].str.contains('Harrier', na=False) &
    ~df['Machine Code'].isin(HARRIER_EXCLUDE)
)
df.loc[mask_harrier_cu, 'Remark'] = 'Copper Wire Automotive'
df.loc[df['Machine Code'].isin(HARRIER_EXCLUDE), 'Remark'] = 'Gold Wire Automotive (Discoloration)'

cu    = df[df['Remark'] == 'Copper Wire Automotive'].copy().reset_index(drop=True)
gold  = df[df['Remark'].str.startswith('Gold Wire Automotive', na=False)].copy()
total_wb   = len(df)
total_cu   = len(cu)
total_gold = len(gold)
total_heads_all  = int(df['Heads'].sum())
total_heads_cu   = int(cu['Heads'].sum())
total_heads_gold = int(gold['Heads'].sum())

model_summary = cu.groupby('Model').agg(
    Machines=('Machine Code', 'count'),
    Heads=('Heads', 'sum'),
    Oldest=('Accept Date', 'min'),
    Newest=('Accept Date', 'max')
).reset_index().sort_values('Heads', ascending=False).reset_index(drop=True)

year_summary = (cu.groupby('Year').agg(
    Machines=('Machine Code', 'count'),
    Heads=('Heads', 'sum')
).reset_index())

# All-model summary (copper + gold, for chart)
all_model_summary = df.groupby('Model').agg(
    Machines=('Machine Code', 'count'),
    Heads=('Heads', 'sum'),
    HeadsPerMC=('Heads', 'mean')
).reset_index().sort_values('Heads', ascending=False).reset_index(drop=True)

df['WireGroup'] = df['Remark'].apply(
    lambda x: 'Copper Wire Automotive' if x == 'Copper Wire Automotive' else 'Gold Wire Automotive'
)
all_model_cu = df.groupby(['Model', 'WireGroup']).agg(
    Machines=('Machine Code', 'count'),
    Heads=('Heads', 'sum')
).reset_index().rename(columns={'WireGroup': 'Remark'})

# ── Styles ───────────────────────────────────────────────────────────────────
BLUE      = '0E3689'
COPPER    = 'B87333'
COPPER_BG = 'FFF3E0'
GREEN_BG  = 'E8F5E9'
GRAY_BG   = 'F5F5F5'
GRAY_HDR  = '37474F'
WHITE     = 'FFFFFF'
DARK      = '1A1A1A'

def thin_bdr():
    s = Side(style='thin', color='CCCCCC')
    return Border(left=s, right=s, top=s, bottom=s)

def hdr(cell, txt, bg=GRAY_HDR, fc=WHITE, sz=10, bold=True, wrap=False):
    cell.value = txt
    cell.font = Font(name='Arial', bold=bold, size=sz, color=fc)
    cell.fill = PatternFill('solid', fgColor=bg)
    cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=wrap)
    cell.border = thin_bdr()

def dat(cell, val, align='center', bold=False, color=DARK, bg=None, fmt=None):
    cell.value = val
    cell.font = Font(name='Arial', size=10, bold=bold, color=color)
    cell.alignment = Alignment(horizontal=align, vertical='center')
    cell.border = thin_bdr()
    if bg:
        cell.fill = PatternFill('solid', fgColor=bg)
    if fmt:
        cell.number_format = fmt

def merge_hdr(ws, r, c1, c2, txt, bg=BLUE, fc=WHITE, sz=12):
    ws.merge_cells(start_row=r, start_column=c1, end_row=r, end_column=c2)
    c = ws.cell(row=r, column=c1)
    c.value = txt
    c.font = Font(name='Arial', bold=True, size=sz, color=fc)
    c.fill = PatternFill('solid', fgColor=bg)
    c.alignment = Alignment(horizontal='center', vertical='center')

# ══════════════════════════════════════════════════════════════════════════════
# WORKBOOK
# ══════════════════════════════════════════════════════════════════════════════
wb = Workbook()

# ─────────────────────────────────────────────────────────────────────────────
# SHEET 1: Summary Dashboard
# ─────────────────────────────────────────────────────────────────────────────
ws1 = wb.active
ws1.title = 'Summary'
ws1.sheet_properties.tabColor = COPPER

# Title
ws1.row_dimensions[1].height = 38
ws1.merge_cells('A1:M1')
c = ws1['A1']
c.value = 'Wire Bond — Copper Wire Machine Summary'
c.font = Font(name='Arial', bold=True, size=16, color=WHITE)
c.fill = PatternFill('solid', fgColor=BLUE)
c.alignment = Alignment(horizontal='left', vertical='center')

ws1.row_dimensions[2].height = 18
ws1.merge_cells('A2:N2')
c = ws1['A2']
c.value = (f'Source: Saw_DA_WB machine list.xls.xlsx  |  Sheet: WB  |  '
           f'Total WB: {total_wb} machines / {total_heads_all} heads  '
           f'(Twin machine = 2 heads)')
c.font = Font(name='Arial', size=9, color='666666')
c.alignment = Alignment(horizontal='left', vertical='center')

ws1.row_dimensions[3].height = 10

# ── KPI cards — 2 rows: Machines + Heads ─────────────────────────────────
# Row 1 of cards: Total / Cu / Gold by MACHINES
kpis_mc = [
    ('Total WB\nMachines', total_wb,   1, 3, BLUE),
    ('Copper Wire\nMachines', total_cu,  5, 7, COPPER),
    ('Gold Wire\nMachines', total_gold,  9, 11, GRAY_HDR),
]
# Row 2 of cards: Total / Cu / Gold by HEADS
kpis_hd = [
    ('Total WB\nHeads', total_heads_all,  1, 3, BLUE),
    ('Copper Wire\nHeads', total_heads_cu,  5, 7, COPPER),
    ('Gold Wire\nHeads', total_heads_gold,  9, 11, GRAY_HDR),
]

def kpi_block(ws, row_start, label, val, cs, ce, bg, pct_text):
    # accent bar
    for cc in range(cs, ce + 1):
        ws.cell(row=row_start, column=cc).fill = PatternFill('solid', fgColor=COPPER)
        ws.cell(row=row_start, column=cc).border = thin_bdr()
    ws.row_dimensions[row_start].height = 7
    # value
    ws.merge_cells(start_row=row_start+1, start_column=cs, end_row=row_start+1, end_column=ce)
    vc = ws.cell(row=row_start+1, column=cs)
    vc.value = val
    vc.font = Font(name='Arial', bold=True, size=26, color=WHITE)
    vc.fill = PatternFill('solid', fgColor=bg)
    vc.alignment = Alignment(horizontal='center', vertical='center')
    vc.border = thin_bdr()
    ws.row_dimensions[row_start+1].height = 32
    # label
    ws.merge_cells(start_row=row_start+2, start_column=cs, end_row=row_start+2, end_column=ce)
    lc = ws.cell(row=row_start+2, column=cs)
    lc.value = label
    lc.font = Font(name='Arial', size=9, color=WHITE)
    lc.fill = PatternFill('solid', fgColor=bg)
    lc.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    lc.border = thin_bdr()
    ws.row_dimensions[row_start+2].height = 20
    # pct
    ws.merge_cells(start_row=row_start+3, start_column=cs, end_row=row_start+3, end_column=ce)
    pc = ws.cell(row=row_start+3, column=cs)
    pc.value = pct_text
    pc.font = Font(name='Arial', size=8, color='AAAAAA')
    pc.fill = PatternFill('solid', fgColor=bg)
    pc.alignment = Alignment(horizontal='center', vertical='center')
    pc.border = thin_bdr()
    ws.row_dimensions[row_start+3].height = 16

for label, val, cs, ce, bg in kpis_mc:
    pct = f'{val/total_wb*100:.1f}% of total' if 'Total' not in label else 'All WB machines'
    kpi_block(ws1, 4, label, val, cs, ce, bg, pct)

ws1.row_dimensions[8].height = 6  # gap between card rows

for label, val, cs, ce, bg in kpis_hd:
    pct = f'{val/total_heads_all*100:.1f}% of total heads' if 'Total' not in label else 'All WB heads'
    kpi_block(ws1, 9, label, val, cs, ce, bg, pct)

ws1.row_dimensions[13].height = 16  # gap

# ── Model summary (Heads primary) ─────────────────────────────────────────
R = 14
merge_hdr(ws1, R, 1, 10, 'Copper Wire — Summary by Model  (Heads = primary metric)', COPPER, WHITE, 12)
ws1.row_dimensions[R].height = 26
R += 1

hdrs1 = ['Model', 'Heads per MC', 'Machines', 'Heads (Total)',
         '% of Cu Heads', 'Oldest Accept', 'Newest Accept',
         'Years Range', 'Cum. Heads', 'Wire Type']
widths1 = [28, 13, 11, 14, 15, 18, 18, 14, 13, 25]
for i, (h, w) in enumerate(zip(hdrs1, widths1), 1):
    hdr(ws1.cell(row=R, column=i), h, GRAY_HDR, wrap=True)
    ws1.column_dimensions[get_column_letter(i)].width = w
ws1.row_dimensions[R].height = 28
R += 1

cum_h = 0
for ri, row in model_summary.iterrows():
    bg = COPPER_BG if ri % 2 == 0 else WHITE
    hpm = int(row['Heads'] / row['Machines'])
    cum_h += row['Heads']
    dat(ws1.cell(row=R, column=1), row['Model'], 'left', True, bg=bg)
    dat(ws1.cell(row=R, column=2), f'{hpm} head{"s" if hpm > 1 else ""}/MC', bg=bg,
        bold=(hpm == 2), color=COPPER if hpm == 2 else DARK)
    dat(ws1.cell(row=R, column=3), row['Machines'], bg=bg)
    dat(ws1.cell(row=R, column=4), int(row['Heads']), bold=True, color=COPPER, bg=bg)
    dat(ws1.cell(row=R, column=5), f"{row['Heads']/total_heads_cu*100:.1f}%", bg=bg)
    oldest = row['Oldest'].strftime('%d %b %Y') if pd.notna(row['Oldest']) else '-'
    newest = row['Newest'].strftime('%d %b %Y') if pd.notna(row['Newest']) else '-'
    dat(ws1.cell(row=R, column=6), oldest, bg=bg)
    dat(ws1.cell(row=R, column=7), newest, bg=bg)
    yrange = (f"{row['Oldest'].year} - {row['Newest'].year}"
              if pd.notna(row['Oldest']) and pd.notna(row['Newest']) else '-')
    dat(ws1.cell(row=R, column=8), yrange, bg=bg)
    dat(ws1.cell(row=R, column=9), cum_h, bg=bg)
    dat(ws1.cell(row=R, column=10), 'Copper Wire Automotive', color=COPPER, bg=bg)
    ws1.row_dimensions[R].height = 22
    R += 1

for ci in range(1, 11):
    tc = ws1.cell(row=R, column=ci)
    tc.fill = PatternFill('solid', fgColor=COPPER)
    tc.font = Font(name='Arial', bold=True, size=11, color=WHITE)
    tc.alignment = Alignment(horizontal='center', vertical='center')
    tc.border = thin_bdr()
ws1.cell(row=R, column=1).value = 'TOTAL'
ws1.cell(row=R, column=1).alignment = Alignment(horizontal='left', vertical='center')
ws1.cell(row=R, column=3).value = total_cu
ws1.cell(row=R, column=4).value = total_heads_cu
ws1.cell(row=R, column=5).value = '100.0%'
ws1.row_dimensions[R].height = 24
R += 2

# ── Year breakdown (Heads + Machines) ─────────────────────────────────────
merge_hdr(ws1, R, 1, 7, 'Copper Wire — by Accept Year', GRAY_HDR, WHITE, 12)
ws1.row_dimensions[R].height = 26
R += 1

hdrs2 = ['Accept Year', 'Machines', 'Heads', '% of Cu Heads', 'Cum. Heads', 'Cum. %', 'Note']
for i, h in enumerate(hdrs2, 1):
    hdr(ws1.cell(row=R, column=i), h, GRAY_HDR)
ws1.row_dimensions[R].height = 26
R += 1

cum2h = 0
for ri, row in year_summary.iterrows():
    cum2h += int(row['Heads'])
    bg = GRAY_BG if ri % 2 == 0 else WHITE
    dat(ws1.cell(row=R, column=1), int(row['Year']), bold=True, bg=bg)
    dat(ws1.cell(row=R, column=2), int(row['Machines']), bg=bg)
    dat(ws1.cell(row=R, column=3), int(row['Heads']), bold=True, color=COPPER, bg=bg)
    dat(ws1.cell(row=R, column=4), f"{row['Heads']/total_heads_cu*100:.1f}%", bg=bg)
    dat(ws1.cell(row=R, column=5), cum2h, bg=bg)
    dat(ws1.cell(row=R, column=6), f"{cum2h/total_heads_cu*100:.1f}%", bg=bg)
    # note: model per year
    yr_models = cu[cu['Year'] == row['Year']]['Model'].value_counts()
    note = ', '.join(f'{m} ({c})' for m, c in yr_models.items())
    dat(ws1.cell(row=R, column=7), note, 'left', bg=bg, color='555555')
    ws1.row_dimensions[R].height = 22
    R += 1

for ci in range(1, 6):
    tc = ws1.cell(row=R, column=ci)
    tc.fill = PatternFill('solid', fgColor=COPPER)
    tc.font = Font(name='Arial', bold=True, size=11, color=WHITE)
    tc.alignment = Alignment(horizontal='center', vertical='center')
    tc.border = thin_bdr()
for ci in range(1, 8):
    tc = ws1.cell(row=R, column=ci)
    tc.fill = PatternFill('solid', fgColor=COPPER)
    tc.font = Font(name='Arial', bold=True, size=11, color=WHITE)
    tc.alignment = Alignment(horizontal='center', vertical='center')
    tc.border = thin_bdr()
ws1.cell(row=R, column=1).value = 'TOTAL'
ws1.cell(row=R, column=1).alignment = Alignment(horizontal='left', vertical='center')
ws1.cell(row=R, column=2).value = total_cu
ws1.cell(row=R, column=3).value = total_heads_cu
ws1.cell(row=R, column=4).value = '100.0%'
ws1.row_dimensions[R].height = 24

ws1.sheet_view.showGridLines = False

# ─────────────────────────────────────────────────────────────────────────────
# SHEET 2: Copper Wire Machine List
# ─────────────────────────────────────────────────────────────────────────────
ws2 = wb.create_sheet('Copper Wire Machines')
ws2.sheet_properties.tabColor = COPPER

ws2.row_dimensions[1].height = 35
ws2.merge_cells('A1:H1')
c = ws2['A1']
c.value = f'Copper Wire Automotive Machines  —  {total_cu} machines  /  {total_heads_cu} heads  (Twin = 2 heads/MC)'
c.font = Font(name='Arial', bold=True, size=14, color=WHITE)
c.fill = PatternFill('solid', fgColor=COPPER)
c.alignment = Alignment(horizontal='left', vertical='center')

ws2.row_dimensions[2].height = 6

R2 = 3
list_hdrs  = ['No.', 'Machine Code', 'Machine Name', 'ODS Name', 'Serial No', 'Model', 'Accept Date', 'Wire Type']
list_widths = [6, 14, 36, 16, 16, 26, 16, 24]
for i, (h, w) in enumerate(zip(list_hdrs, list_widths), 1):
    hdr(ws2.cell(row=R2, column=i), h, GRAY_HDR)
    ws2.column_dimensions[get_column_letter(i)].width = w
ws2.row_dimensions[R2].height = 26
R2 += 1

MODEL_COLORS = {
    'Twin Eagle Xtreme GoCu': 'FFF8E1',
    'Aero Twin':               'FFF3E0',
    'Eagle Aero GoCu':         'FBE9E7',
}
current_model = None
row_no = 0
for _, row in cu.iterrows():
    row_no += 1
    if row['Model'] != current_model:
        current_model = row['Model']
        ws2.merge_cells(start_row=R2, start_column=1, end_row=R2, end_column=8)
        gc = ws2.cell(row=R2, column=1)
        model_count = len(cu[cu['Model'] == row['Model']])
        model_heads = int(cu[cu['Model'] == row['Model']]['Heads'].sum())
        hpm = model_heads // model_count
        gc.value = f'  ▶  {row["Model"]}  ({model_count} machines  /  {model_heads} heads  —  {hpm} head/MC)'
        gc.font = Font(name='Arial', bold=True, size=10, color=WHITE)
        gc.fill = PatternFill('solid', fgColor=COPPER)
        gc.alignment = Alignment(horizontal='left', vertical='center')
        for ci in range(1, 9):
            ws2.cell(row=R2, column=ci).border = thin_bdr()
        ws2.row_dimensions[R2].height = 20
        R2 += 1

    bg = MODEL_COLORS.get(row['Model'], WHITE)
    dat(ws2.cell(row=R2, column=1), row_no, bg=bg)
    dat(ws2.cell(row=R2, column=2), row['Machine Code'], 'left', True, bg=bg)
    dat(ws2.cell(row=R2, column=3), row['Machine Name'], 'left', bg=bg)
    ods = row['ODS Name'] if pd.notna(row['ODS Name']) else '-'
    dat(ws2.cell(row=R2, column=4), ods, bg=bg)
    sn = str(row['Serian No']) if pd.notna(row['Serian No']) else '-'
    dat(ws2.cell(row=R2, column=5), sn, bg=bg)
    dat(ws2.cell(row=R2, column=6), row['Model'], 'left', color=COPPER, bg=bg)
    dc = ws2.cell(row=R2, column=7)
    dc.value = row['Accept Date']
    dc.font = Font(name='Arial', size=10)
    dc.number_format = 'DD-MMM-YYYY'
    dc.alignment = Alignment(horizontal='center', vertical='center')
    dc.border = thin_bdr()
    dc.fill = PatternFill('solid', fgColor=bg)
    dat(ws2.cell(row=R2, column=8), 'Copper Wire Automotive', color=COPPER, bold=True, bg=bg)
    ws2.row_dimensions[R2].height = 18
    R2 += 1

ws2.freeze_panes = 'A4'
ws2.sheet_view.showGridLines = False

# ─────────────────────────────────────────────────────────────────────────────
# SHEET 3: All WB — Gold vs Copper
# ─────────────────────────────────────────────────────────────────────────────
ws3 = wb.create_sheet('All WB - Wire Type')
ws3.sheet_properties.tabColor = BLUE

ws3.row_dimensions[1].height = 35
ws3.merge_cells('A1:I1')
c = ws3['A1']
c.value = f'All Wire Bond Machines — Grouped by Wire Type  ({total_wb} machines)'
c.font = Font(name='Arial', bold=True, size=14, color=WHITE)
c.fill = PatternFill('solid', fgColor=BLUE)
c.alignment = Alignment(horizontal='left', vertical='center')

ws3.row_dimensions[2].height = 22
ws3.merge_cells('A2:I2')
c2 = ws3['A2']
c2.value = (f'Copper Wire: {total_cu} ({total_cu/total_wb*100:.1f}%)     '
            f'Gold Wire: {total_gold} ({total_gold/total_wb*100:.1f}%)     '
            f'Total: {total_wb}')
c2.font = Font(name='Arial', bold=True, size=11, color=WHITE)
c2.fill = PatternFill('solid', fgColor=COPPER)
c2.alignment = Alignment(horizontal='center', vertical='center')

ws3.row_dimensions[3].height = 8

R3 = 4
all_hdrs   = ['No.', 'Machine Code', 'ODS Name', 'Model', 'MFG', 'Accept Date', 'Wire Type', 'Year', 'Cu Wire?']
all_widths  = [6, 14, 16, 28, 8, 16, 25, 8, 10]
for i, (h, w) in enumerate(zip(all_hdrs, all_widths), 1):
    hdr(ws3.cell(row=R3, column=i), h, GRAY_HDR)
    ws3.column_dimensions[get_column_letter(i)].width = w
ws3.row_dimensions[R3].height = 26
R3 += 1

df_sorted = (df.sort_values(['Remark', 'Model', 'Accept Date'], na_position='last')
               .reset_index(drop=True))
for i, row in df_sorted.iterrows():
    is_cu = row['Remark'] == 'Copper Wire Automotive'
    bg = COPPER_BG if is_cu else (WHITE if i % 2 == 0 else GRAY_BG)
    wire = row['Remark'] if pd.notna(row['Remark']) else 'Unknown'
    dat(ws3.cell(row=R3, column=1), i + 1, bg=bg)
    dat(ws3.cell(row=R3, column=2), row['Machine Code'], 'left', True, bg=bg)
    dat(ws3.cell(row=R3, column=3), row['ODS Name'] if pd.notna(row['ODS Name']) else '-', bg=bg)
    dat(ws3.cell(row=R3, column=4), row['Model'], 'left', color=COPPER if is_cu else DARK, bg=bg)
    dat(ws3.cell(row=R3, column=5), row['MFG'] if pd.notna(row['MFG']) else '-', bg=bg)
    dc = ws3.cell(row=R3, column=6)
    dc.value = row['Accept Date']
    dc.font = Font(name='Arial', size=10)
    dc.number_format = 'DD-MMM-YYYY'
    dc.alignment = Alignment(horizontal='center', vertical='center')
    dc.border = thin_bdr()
    dc.fill = PatternFill('solid', fgColor=bg)
    dat(ws3.cell(row=R3, column=7), wire, color=COPPER if is_cu else '37474F', bold=is_cu, bg=bg)
    yr = int(row['Year']) if pd.notna(row['Year']) else '-'
    dat(ws3.cell(row=R3, column=8), yr, bg=bg)
    mark = ws3.cell(row=R3, column=9)
    mark.value = 'YES' if is_cu else ''
    mark.font = Font(name='Arial', size=9, bold=True, color=WHITE if is_cu else DARK)
    mark.fill = PatternFill('solid', fgColor=COPPER if is_cu else bg)
    mark.alignment = Alignment(horizontal='center', vertical='center')
    mark.border = thin_bdr()
    ws3.row_dimensions[R3].height = 18
    R3 += 1

ws3.freeze_panes = 'A5'
ws3.sheet_view.showGridLines = False

# ─────────────────────────────────────────────────────────────────────────────
# SHEET 4: Charts — by Model
# ─────────────────────────────────────────────────────────────────────────────
ws4 = wb.create_sheet('Charts by Model')
ws4.sheet_properties.tabColor = '1D9CE4'
ws4.sheet_view.showGridLines = False

# Title
ws4.row_dimensions[1].height = 35
ws4.merge_cells('A1:P1')
ct = ws4['A1']
ct.value = 'Wire Bond — Copper Wire Capacity by Model (Head Count)'
ct.font = Font(name='Arial', bold=True, size=15, color=WHITE)
ct.fill = PatternFill('solid', fgColor=BLUE)
ct.alignment = Alignment(horizontal='left', vertical='center')

ws4.row_dimensions[2].height = 18
ws4.merge_cells('A2:P2')
ct2 = ws4['A2']
ct2.value = (f'Total WB: {total_heads_all} heads  |  '
             f'Copper Wire: {total_heads_cu} heads ({total_heads_cu/total_heads_all*100:.1f}%)  |  '
             f'Gold Wire: {total_heads_gold} heads ({total_heads_gold/total_heads_all*100:.1f}%)'
             f'  |  Twin machine = 2 heads')
ct2.font = Font(name='Arial', size=10, bold=True, color=WHITE)
ct2.fill = PatternFill('solid', fgColor=COPPER)
ct2.alignment = Alignment(horizontal='center', vertical='center')

# ── Data tables for charts ────────────────────────────────────────────────

# Table A: Copper Wire heads by model (col A-C, row 4+)
ws4.row_dimensions[4].height = 10
DATA_ROW = 5

# Table A header
for ci, h in enumerate(['Model', 'Machines', 'Heads (Cu Wire)'], 1):
    c = ws4.cell(row=DATA_ROW, column=ci)
    c.value = h
    c.font = Font(name='Arial', bold=True, size=10, color=WHITE)
    c.fill = PatternFill('solid', fgColor=COPPER)
    c.alignment = Alignment(horizontal='center', vertical='center')
    c.border = thin_bdr()
ws4.column_dimensions['A'].width = 28
ws4.column_dimensions['B'].width = 13
ws4.column_dimensions['C'].width = 18

tbl_a_start = DATA_ROW + 1
for ri, row in model_summary.iterrows():
    r = tbl_a_start + ri
    dat(ws4.cell(row=r, column=1), row['Model'], 'left', True,
        bg=COPPER_BG if ri % 2 == 0 else WHITE)
    dat(ws4.cell(row=r, column=2), int(row['Machines']),
        bg=COPPER_BG if ri % 2 == 0 else WHITE)
    dat(ws4.cell(row=r, column=3), int(row['Heads']), bold=True, color=COPPER,
        bg=COPPER_BG if ri % 2 == 0 else WHITE)
    ws4.row_dimensions[r].height = 22

tbl_a_end = tbl_a_start + len(model_summary) - 1

# Table B: All WB heads by model — Cu vs Gold (col E-H, row 5+)
ws4.column_dimensions['E'].width = 3   # spacer
ws4.column_dimensions['F'].width = 28
ws4.column_dimensions['G'].width = 18
ws4.column_dimensions['H'].width = 18

for ci, (h, col) in enumerate(zip(['Model', 'Cu Wire Heads', 'Gold Wire Heads'], [6, 7, 8]), 0):
    c = ws4.cell(row=DATA_ROW, column=6 + ci)
    c.value = h
    c.font = Font(name='Arial', bold=True, size=10, color=WHITE)
    c.fill = PatternFill('solid', fgColor=GRAY_HDR)
    c.alignment = Alignment(horizontal='center', vertical='center')
    c.border = thin_bdr()

tbl_b_start = DATA_ROW + 1
all_models_sorted = df['Model'].value_counts().index.tolist()
for ri, mdl in enumerate(all_models_sorted):
    r = tbl_b_start + ri
    bg = COPPER_BG if ri % 2 == 0 else WHITE
    cu_h  = int(all_model_cu[(all_model_cu['Model']==mdl) & (all_model_cu['Remark']=='Copper Wire Automotive')]['Heads'].sum()) if not all_model_cu[(all_model_cu['Model']==mdl) & (all_model_cu['Remark']=='Copper Wire Automotive')].empty else 0
    gld_h = int(all_model_cu[(all_model_cu['Model']==mdl) & (all_model_cu['Remark']=='Gold Wire Automotive')]['Heads'].sum()) if not all_model_cu[(all_model_cu['Model']==mdl) & (all_model_cu['Remark']=='Gold Wire Automotive')].empty else 0
    dat(ws4.cell(row=r, column=6), mdl, 'left', True, bg=bg)
    dat(ws4.cell(row=r, column=7), cu_h if cu_h else None, bold=cu_h > 0, color=COPPER if cu_h else '999999', bg=bg)
    dat(ws4.cell(row=r, column=8), gld_h if gld_h else None, bold=gld_h > 0, color='5EBF33' if gld_h else '999999', bg=bg)
    ws4.row_dimensions[r].height = 20

tbl_b_end = tbl_b_start + len(all_models_sorted) - 1

# ── Chart 1: Bar — Copper Wire Heads by Model ─────────────────────────────
bar1 = BarChart()
bar1.type = 'bar'
bar1.grouping = 'clustered'
bar1.title = 'Copper Wire — Heads by Model'
bar1.y_axis.title = 'Heads'
bar1.x_axis.title = 'Model'
bar1.style = 2
bar1.width = 18
bar1.height = 12

data_ref = Reference(ws4, min_col=3, max_col=3,
                     min_row=DATA_ROW, max_row=tbl_a_end)
cats_ref  = Reference(ws4, min_col=1, max_col=1,
                      min_row=tbl_a_start, max_row=tbl_a_end)
bar1.add_data(data_ref, titles_from_data=True)
bar1.set_categories(cats_ref)
bar1.series[0].graphicalProperties.solidFill = COPPER
bar1.series[0].graphicalProperties.line.solidFill = '8B5E3C'
bar1.dataLabels = DataLabelList()
bar1.dataLabels.showVal = True
bar1.dataLabels.txPr = None
ws4.add_chart(bar1, 'A10')

# ── Chart 2: Pie — Copper Wire Head % by Model ────────────────────────────
pie1 = PieChart()
pie1.title = 'Copper Wire Heads — Model Share'
pie1.style = 2
pie1.width = 14
pie1.height = 12

pie_data = Reference(ws4, min_col=3, max_col=3,
                     min_row=DATA_ROW, max_row=tbl_a_end)
pie_cats  = Reference(ws4, min_col=1, max_col=1,
                      min_row=tbl_a_start, max_row=tbl_a_end)
pie1.add_data(pie_data, titles_from_data=True)
pie1.set_categories(pie_cats)
pie1.dataLabels = DataLabelList()
pie1.dataLabels.showPercent = True
pie1.dataLabels.showCatName = True
pie1.dataLabels.showVal = False
pie1.dataLabels.separator = '\n'

SLICE_COLORS = [COPPER, 'D2691E', 'CD853F']
for idx, hex_color in enumerate(SLICE_COLORS[:len(model_summary)]):
    pt = DataPoint(idx=idx)
    pt.graphicalProperties.solidFill = hex_color
    pie1.series[0].dPt.append(pt)

ws4.add_chart(pie1, 'J10')

# ── Chart 3: Stacked Bar — Cu vs Gold heads by Model ──────────────────────
bar2 = BarChart()
bar2.type = 'bar'
bar2.grouping = 'stacked'
bar2.title = 'All WB Models — Copper vs Gold Wire Heads'
bar2.y_axis.title = 'Heads'
bar2.x_axis.title = 'Model'
bar2.style = 2
bar2.width = 22
bar2.height = 12

cu_ref  = Reference(ws4, min_col=7, max_col=7,
                    min_row=DATA_ROW, max_row=tbl_b_end)
gld_ref = Reference(ws4, min_col=8, max_col=8,
                    min_row=DATA_ROW, max_row=tbl_b_end)
cats2   = Reference(ws4, min_col=6, max_col=6,
                    min_row=tbl_b_start, max_row=tbl_b_end)
bar2.add_data(cu_ref,  titles_from_data=True)
bar2.add_data(gld_ref, titles_from_data=True)
bar2.set_categories(cats2)
bar2.series[0].graphicalProperties.solidFill = COPPER
bar2.series[0].graphicalProperties.line.solidFill = '8B5E3C'
bar2.series[1].graphicalProperties.solidFill = 'DAA520'
bar2.series[1].graphicalProperties.line.solidFill = 'B8860B'
bar2.dataLabels = DataLabelList()
bar2.dataLabels.showVal = True
ws4.add_chart(bar2, 'A30')

# ── Save ──────────────────────────────────────────────────────────────────
out = 'Output/WB_Copper_Wire_Summary.xlsx'
wb.save(out)
print(f'Saved: {out}')
print(f'  Total WB      : {total_wb} machines / {total_heads_all} heads')
print(f'  Copper Wire   : {total_cu} machines / {total_heads_cu} heads ({total_heads_cu/total_heads_all*100:.1f}%)')
print(f'  Gold Wire     : {total_gold} machines / {total_heads_gold} heads ({total_heads_gold/total_heads_all*100:.1f}%)')
print('  Copper models :')
for _, row in model_summary.iterrows():
    print(f'    {row["Model"]}: {row["Machines"]} machines / {int(row["Heads"])} heads')
