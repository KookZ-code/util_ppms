import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import CellIsRule
from collections import defaultdict

# ── Paths ────────────────────────────────────────────────────────────────
EXCEL_SRC = os.path.join('raw', 'DA_machine.xls.xlsx')
EXCEL_TARGET = os.path.join('Output', 'DA_Loading_Calculator.xlsx')

# ── Colors / Styles ──────────────────────────────────────────────────────
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
thin_border = Border(
    left=Side(style='thin', color=LIGHT_GRAY),
    right=Side(style='thin', color=LIGHT_GRAY),
    top=Side(style='thin', color=LIGHT_GRAY),
    bottom=Side(style='thin', color=LIGHT_GRAY),
)
normal_font = Font(name='Calibri', size=11, color='000000')

def style_header(ws, row, max_col):
    for c in range(1, max_col + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border

def cell_style(ws, r, c, is_alt=False, align='center'):
    cell = ws.cell(row=r, column=c)
    cell.font = normal_font
    cell.fill = PatternFill('solid', fgColor=VLIGHT if is_alt else 'FFFFFF')
    cell.alignment = Alignment(horizontal=align, vertical='center', wrap_text=True)
    cell.border = thin_border
    return cell

def section_fill(ws, r, col_start, col_end, text, color):
    ws.merge_cells(start_row=r, start_column=col_start, end_row=r, end_column=col_end)
    cell = ws.cell(row=r, column=col_start)
    cell.value = text
    cell.font = Font(name='Calibri', bold=True, size=13, color='FFFFFF')
    cell.fill = PatternFill('solid', fgColor=color)
    cell.alignment = Alignment(horizontal='center', vertical='center')

# ── Load source data ─────────────────────────────────────────────────────
src = openpyxl.load_workbook(EXCEL_SRC, data_only=True)

# Machine list: number -> (model, status)
ws_list = src['DA_machine list']
mc_info = {}
for row in ws_list.iter_rows(min_row=2, max_row=ws_list.max_row, values_only=True):
    area, mc_code, mc_name, ods, serial, model, accept_date, status = row
    if mc_code and 'Die bonder' in str(mc_name or ''):
        m = re.search(r'#\s*0*(\d+)', str(mc_code))
        if m:
            mc_info[m.group(1)] = {'model': model, 'status': status or '-', 'code': mc_code}

# UPH data: number -> (type, pkg, uph)
ws_uph = src['DA_UPH']
mc_uph = {}
for row in ws_uph.iter_rows(min_row=2, max_row=ws_uph.max_row, values_only=True):
    mc, mc_type, pkg, die_size, uph = row
    if mc:
        m = re.search(r'#\s*0*(\d+)', str(mc))
        if m:
            mc_uph[m.group(1)] = {'type': mc_type, 'pkg': pkg, 'uph': uph or 0}

# MTAI ASSY DA: packages
ws_cap = src['MTAI ASSY DA']
pkg_data = []
for row in ws_cap.iter_rows(min_row=3, max_row=24, values_only=True):
    _, item, pkg, max_cap, drr, std_uph, cur_uph, uph_diff, std_req, cur_da, mc_no, mc_shutdown, _, cur_usage, cur_output = row
    if not pkg or pkg == 'Total':
        continue

    mc_list = []
    if mc_no:
        mc_list = [x.strip() for x in str(mc_no).replace(' ', '').split(',') if x.strip()]

    # Group by model
    model_group = defaultdict(lambda: {'machines': [], 'uphs': [], 'statuses': []})
    for num in mc_list:
        info = mc_info.get(num, {})
        uph_info = mc_uph.get(num, {})
        model = info.get('model') or uph_info.get('type') or 'Unknown'
        uph = uph_info.get('uph', 0)
        status = info.get('status', '-')
        model_group[model]['machines'].append(f'DB#{num}')
        model_group[model]['uphs'].append(uph)
        model_group[model]['statuses'].append(status)

    pkg_data.append({
        'pkg': pkg, 'drr': drr or 0, 'std_uph': std_uph or 0,
        'cur_uph': cur_uph or 0, 'cur_usage': cur_usage or 0,
        'models': dict(model_group),
        'num_models': len(model_group),
    })

# ── Open target workbook & add sheet ─────────────────────────────────────
wb = openpyxl.load_workbook(EXCEL_TARGET)

# Remove existing sheet if present
SHEET_NAME = 'Package-Model Analysis'
if SHEET_NAME in wb.sheetnames:
    del wb[SHEET_NAME]

ws = wb.create_sheet(SHEET_NAME)
ws.sheet_properties.tabColor = '702076'

# ═══════════════════════════════════════════════════════════════════════
# SECTION 1: Summary — Package x Model Matrix
# ═══════════════════════════════════════════════════════════════════════
ws.merge_cells('A1:Q1')
ws['A1'] = 'Package vs Model Analysis — Which models run each package and at what UPH?'
ws['A1'].font = Font(name='Calibri', bold=True, size=15, color=BLUE)
ws['A1'].alignment = Alignment(horizontal='left', vertical='center')
ws.row_dimensions[1].height = 35

# Collect all models used
all_models = sorted(set(m for p in pkg_data for m in p['models'].keys() if m != 'Unknown'))

# ─── Part A: Package-Model detail table ───
HDR = 3
headers = [
    'Package', 'Models\nCount', 'Model', 'MCs in\nModel', 'Running', 'Shutdown',
    'Avg UPH', 'Min UPH', 'Max UPH', 'UPH Range\n(Max-Min)',
    'Machine List', 'DRR', 'STD UPH\n(Package)', 'Current UPH\n(Package)',
]
NUM_COLS = len(headers)

for i, h in enumerate(headers):
    ws.cell(row=HDR, column=i+1).value = h
style_header(ws, HDR, NUM_COLS)
ws.row_dimensions[HDR].height = 40

col_widths = [22, 9, 14, 9, 9, 10, 10, 10, 10, 11, 35, 12, 12, 12]
for i, w in enumerate(col_widths):
    ws.column_dimensions[get_column_letter(i+1)].width = w

# Fill data — one row per package-model combination
r = HDR + 1
pkg_start_rows = {}  # for merging package cells

for pi, p in enumerate(pkg_data):
    pkg_first_row = r
    models_sorted = sorted(p['models'].items(), key=lambda x: (
        sum(x[1]['uphs'])/max(len(x[1]['uphs']),1)
    ), reverse=True)

    for mi, (model, data) in enumerate(models_sorted):
        is_alt = pi % 2 == 0
        uphs = data['uphs']
        avg_uph = sum(uphs) / len(uphs) if uphs else 0
        min_uph = min(uphs) if uphs else 0
        max_uph = max(uphs) if uphs else 0
        running = sum(1 for s in data['statuses'] if s == 'Run')
        shutdown = sum(1 for s in data['statuses'] if s == 'Machine Shutdown')
        mc_str = ', '.join(data['machines'])

        # Col A: Package (will merge later)
        c = cell_style(ws, r, 1, is_alt, 'left')
        if mi == 0:
            c.value = p['pkg']
            c.font = Font(name='Calibri', bold=True, size=11, color='000000')

        # Col B: Models count
        c = cell_style(ws, r, 2, is_alt)
        if mi == 0:
            c.value = p['num_models']
            if p['num_models'] > 1:
                c.font = Font(name='Calibri', bold=True, size=11, color=ORANGE_HEX)
            else:
                c.font = Font(name='Calibri', size=11, color=GREEN_HEX)

        # Col C: Model
        c = cell_style(ws, r, 3, is_alt, 'left')
        c.value = model
        c.font = Font(name='Calibri', bold=True, size=11, color=BLUE)

        # Col D: MCs in model
        c = cell_style(ws, r, 4, is_alt)
        c.value = len(data['machines'])

        # Col E: Running
        c = cell_style(ws, r, 5, is_alt)
        c.value = running
        if running > 0:
            c.font = Font(name='Calibri', bold=True, size=11, color=GREEN_HEX)

        # Col F: Shutdown
        c = cell_style(ws, r, 6, is_alt)
        c.value = shutdown
        if shutdown > 0:
            c.font = Font(name='Calibri', bold=True, size=11, color=RED_HEX)

        # Col G: Avg UPH
        c = cell_style(ws, r, 7, is_alt)
        c.value = round(avg_uph) if avg_uph > 0 else '-'
        if isinstance(c.value, int):
            c.number_format = '#,##0'

        # Col H: Min UPH
        c = cell_style(ws, r, 8, is_alt)
        c.value = min_uph if min_uph > 0 else '-'
        if isinstance(c.value, int):
            c.number_format = '#,##0'

        # Col I: Max UPH
        c = cell_style(ws, r, 9, is_alt)
        c.value = max_uph if max_uph > 0 else '-'
        if isinstance(c.value, int):
            c.number_format = '#,##0'

        # Col J: UPH Range
        c = cell_style(ws, r, 10, is_alt)
        if max_uph > 0 and min_uph > 0:
            c.value = max_uph - min_uph
            c.number_format = '#,##0'
            if (max_uph - min_uph) > 1500:
                c.font = Font(name='Calibri', bold=True, size=11, color=RED_HEX)
        else:
            c.value = '-'

        # Col K: Machine list
        c = cell_style(ws, r, 11, is_alt, 'left')
        c.value = mc_str
        c.font = Font(name='Calibri', size=9, color=DARK_GRAY)

        # Col L: DRR
        c = cell_style(ws, r, 12, is_alt)
        if mi == 0:
            c.value = p['drr']
            c.number_format = '#,##0'

        # Col M: STD UPH
        c = cell_style(ws, r, 13, is_alt)
        if mi == 0:
            c.value = p['std_uph']
            c.number_format = '#,##0'

        # Col N: Current UPH
        c = cell_style(ws, r, 14, is_alt)
        if mi == 0:
            c.value = p['cur_uph']
            c.number_format = '#,##0'

        ws.row_dimensions[r].height = 22
        r += 1

    # Merge package cells if multiple models
    if len(models_sorted) > 1:
        for merge_col in [1, 2, 12, 13, 14]:
            ws.merge_cells(
                start_row=pkg_first_row, start_column=merge_col,
                end_row=pkg_first_row + len(models_sorted) - 1, end_column=merge_col
            )
            ws.cell(row=pkg_first_row, column=merge_col).alignment = Alignment(
                horizontal='left' if merge_col == 1 else 'center',
                vertical='center', wrap_text=True
            )

    # Add separator border after each package group
    for c in range(1, NUM_COLS + 1):
        cell = ws.cell(row=r - 1, column=c)
        cell.border = Border(
            left=Side(style='thin', color=LIGHT_GRAY),
            right=Side(style='thin', color=LIGHT_GRAY),
            top=Side(style='thin', color=LIGHT_GRAY),
            bottom=Side(style='medium', color=BLUE),
        )

DETAIL_END = r - 1

# ═══════════════════════════════════════════════════════════════════════
# SECTION 2: Cross-tab — Package x Model matrix (MC count)
# ═══════════════════════════════════════════════════════════════════════
MATRIX_START = DETAIL_END + 3
section_fill(ws, MATRIX_START, 1, len(all_models) + 2,
             'Package x Model Matrix — Machine Count per Model', BLUE)

# Headers
MX_HDR = MATRIX_START + 1
ws.cell(row=MX_HDR, column=1).value = 'Package'
ws.cell(row=MX_HDR, column=2).value = 'Total\nMCs'
for i, mdl in enumerate(all_models):
    ws.cell(row=MX_HDR, column=3 + i).value = mdl
style_header(ws, MX_HDR, 2 + len(all_models))
ws.row_dimensions[MX_HDR].height = 35

# Data
for pi, p in enumerate(pkg_data):
    r = MX_HDR + 1 + pi
    is_alt = pi % 2 == 0

    c = cell_style(ws, r, 1, is_alt, 'left')
    c.value = p['pkg']
    c.font = Font(name='Calibri', bold=True, size=11)

    total_mcs = sum(len(d['machines']) for d in p['models'].values())
    c = cell_style(ws, r, 2, is_alt)
    c.value = total_mcs
    c.font = Font(name='Calibri', bold=True, size=11, color=BLUE)

    for mi, mdl in enumerate(all_models):
        c = cell_style(ws, r, 3 + mi, is_alt)
        if mdl in p['models']:
            count = len(p['models'][mdl]['machines'])
            c.value = count
            c.font = Font(name='Calibri', bold=True, size=11, color=BLUE)
        else:
            c.value = '-'
            c.font = Font(name='Calibri', size=10, color=MED_GRAY)

# Total row
r = MX_HDR + 1 + len(pkg_data)
for c_idx in range(1, 3 + len(all_models)):
    cell = ws.cell(row=r, column=c_idx)
    cell.font = Font(name='Calibri', bold=True, size=11, color='FFFFFF')
    cell.fill = PatternFill('solid', fgColor=BLUE)
    cell.alignment = Alignment(horizontal='center', vertical='center')
    cell.border = thin_border

ws.cell(row=r, column=1).value = 'Total'
ws.cell(row=r, column=1).alignment = Alignment(horizontal='left', vertical='center')
cl2 = get_column_letter(2)
ws.cell(row=r, column=2).value = f'=SUM({cl2}{MX_HDR+1}:{cl2}{r-1})'
for mi in range(len(all_models)):
    cl = get_column_letter(3 + mi)
    ws.cell(row=r, column=3+mi).value = f'=SUM({cl}{MX_HDR+1}:{cl}{r-1})'

MATRIX_END = r

# ═══════════════════════════════════════════════════════════════════════
# SECTION 3: Cross-tab — Package x Model matrix (Avg UPH)
# ═══════════════════════════════════════════════════════════════════════
UPH_START = MATRIX_END + 2
section_fill(ws, UPH_START, 1, len(all_models) + 2,
             'Package x Model Matrix — Average UPH per Model', LIGHT_BLUE)

UPH_HDR = UPH_START + 1
ws.cell(row=UPH_HDR, column=1).value = 'Package'
ws.cell(row=UPH_HDR, column=2).value = 'Pkg Avg\nUPH'
for i, mdl in enumerate(all_models):
    ws.cell(row=UPH_HDR, column=3 + i).value = mdl
style_header(ws, UPH_HDR, 2 + len(all_models))
ws.row_dimensions[UPH_HDR].height = 35

for pi, p in enumerate(pkg_data):
    r = UPH_HDR + 1 + pi
    is_alt = pi % 2 == 0

    c = cell_style(ws, r, 1, is_alt, 'left')
    c.value = p['pkg']
    c.font = Font(name='Calibri', bold=True, size=11)

    c = cell_style(ws, r, 2, is_alt)
    c.value = p['cur_uph'] if p['cur_uph'] else '-'
    if isinstance(c.value, (int, float)):
        c.number_format = '#,##0'
        c.font = Font(name='Calibri', bold=True, size=11, color=BLUE)

    for mi, mdl in enumerate(all_models):
        c = cell_style(ws, r, 3 + mi, is_alt)
        if mdl in p['models']:
            uphs = p['models'][mdl]['uphs']
            avg = sum(uphs) / len(uphs) if uphs else 0
            if avg > 0:
                c.value = round(avg)
                c.number_format = '#,##0'
                # Color: green if above pkg avg, orange if below
                if p['cur_uph'] and avg >= p['cur_uph']:
                    c.font = Font(name='Calibri', bold=True, size=11, color=GREEN_HEX)
                else:
                    c.font = Font(name='Calibri', bold=True, size=11, color=ORANGE_HEX)
            else:
                c.value = 'N/A'
                c.font = Font(name='Calibri', size=10, color=MED_GRAY)
        else:
            c.value = '-'
            c.font = Font(name='Calibri', size=10, color=MED_GRAY)

# ═══════════════════════════════════════════════════════════════════════
# SECTION 4: Multi-model highlight summary
# ═══════════════════════════════════════════════════════════════════════
UPH_END = UPH_HDR + len(pkg_data)
MULTI_START = UPH_END + 3
section_fill(ws, MULTI_START, 1, 10,
             'Multi-Model Packages — Packages running on more than 1 model', ORANGE_HEX)

M_HDR = MULTI_START + 1
m_headers = ['Package', 'Models\nCount', 'Models', 'Best Model\n(Highest UPH)',
             'Best Avg UPH', 'Worst Model\n(Lowest UPH)', 'Worst Avg UPH',
             'UPH Spread', 'Spread %', 'Recommendation']
for i, h in enumerate(m_headers):
    ws.cell(row=M_HDR, column=i+1).value = h
style_header(ws, M_HDR, len(m_headers))
ws.row_dimensions[M_HDR].height = 40

m_col_widths = [22, 9, 35, 14, 12, 14, 12, 11, 10, 40]
for i, w in enumerate(m_col_widths):
    ws.column_dimensions[get_column_letter(i+1)].width = max(
        ws.column_dimensions[get_column_letter(i+1)].width or 0, w
    )

mr = M_HDR + 1
multi_pkgs = [p for p in pkg_data if p['num_models'] > 1]

for pi, p in enumerate(multi_pkgs):
    is_alt = pi % 2 == 0

    # Find best and worst model by avg UPH (exclude zero-UPH)
    model_avgs = []
    for mdl, data in p['models'].items():
        if mdl == 'Unknown':
            continue
        uphs = [u for u in data['uphs'] if u > 0]
        if uphs:
            model_avgs.append((mdl, sum(uphs)/len(uphs)))
    model_avgs.sort(key=lambda x: x[1], reverse=True)

    best_model = model_avgs[0] if model_avgs else ('N/A', 0)
    worst_model = model_avgs[-1] if model_avgs else ('N/A', 0)
    spread = best_model[1] - worst_model[1] if len(model_avgs) > 1 else 0
    spread_pct = spread / worst_model[1] if worst_model[1] > 0 else 0

    # Package
    c = cell_style(ws, mr, 1, is_alt, 'left')
    c.value = p['pkg']
    c.font = Font(name='Calibri', bold=True, size=11)

    # Model count
    c = cell_style(ws, mr, 2, is_alt)
    c.value = p['num_models']
    c.font = Font(name='Calibri', bold=True, size=11, color=ORANGE_HEX)

    # Models list
    c = cell_style(ws, mr, 3, is_alt, 'left')
    c.value = ', '.join(sorted(p['models'].keys()))
    c.font = Font(name='Calibri', size=10, color=DARK_GRAY)

    # Best model
    c = cell_style(ws, mr, 4, is_alt)
    c.value = best_model[0]
    c.font = Font(name='Calibri', bold=True, size=11, color=GREEN_HEX)

    c = cell_style(ws, mr, 5, is_alt)
    c.value = round(best_model[1])
    c.number_format = '#,##0'
    c.font = Font(name='Calibri', bold=True, size=11, color=GREEN_HEX)

    # Worst model
    c = cell_style(ws, mr, 6, is_alt)
    c.value = worst_model[0]
    c.font = Font(name='Calibri', bold=True, size=11, color=RED_HEX)

    c = cell_style(ws, mr, 7, is_alt)
    c.value = round(worst_model[1])
    c.number_format = '#,##0'
    c.font = Font(name='Calibri', bold=True, size=11, color=RED_HEX)

    # Spread
    c = cell_style(ws, mr, 8, is_alt)
    c.value = round(spread)
    c.number_format = '#,##0'
    if spread > 2000:
        c.font = Font(name='Calibri', bold=True, size=11, color=RED_HEX)

    c = cell_style(ws, mr, 9, is_alt)
    c.value = spread_pct
    c.number_format = '0%'
    if spread_pct > 0.5:
        c.font = Font(name='Calibri', bold=True, size=11, color=RED_HEX)
    elif spread_pct > 0.25:
        c.font = Font(name='Calibri', bold=True, size=11, color=ORANGE_HEX)

    # Recommendation
    c = cell_style(ws, mr, 10, is_alt, 'left')
    if spread_pct > 0.5:
        c.value = f'Large UPH gap — consider consolidating to {best_model[0]} or optimizing {worst_model[0]}'
        c.font = Font(name='Calibri', size=10, color=RED_HEX)
    elif spread_pct > 0.25:
        c.value = f'Moderate gap — review {worst_model[0]} setup for UPH improvement'
        c.font = Font(name='Calibri', size=10, color=ORANGE_HEX)
    else:
        c.value = 'Models perform similarly — flexible allocation OK'
        c.font = Font(name='Calibri', size=10, color=GREEN_HEX)

    ws.row_dimensions[mr].height = 22
    mr += 1

# ── Freeze panes ─────────────────────────────────────────────────────
ws.freeze_panes = 'B4'

# ── Save ─────────────────────────────────────────────────────────────
wb.save(EXCEL_TARGET)
print(f'Updated: {EXCEL_TARGET}')
print(f'Sheet added: "{SHEET_NAME}"')
print(f'Packages: {len(pkg_data)}, Multi-model packages: {len(multi_pkgs)}')
print(f'Models found: {all_models}')
