import sys, io, os, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from collections import defaultdict

def norm_prefix(p):
    return re.sub(r'[^A-Z0-9]', '', p.upper())

def parse_mc_no(mc_str):
    """Parse MC No. field into a set of (normalized_prefix, number) tuples."""
    if not mc_str:
        return set()
    machines = set()
    current_prefix = ''
    s = str(mc_str).strip()
    # Strip parenthetical content (serial numbers, notes)
    s = re.sub(r'\([^)]*\)', '', s)
    # Replace space between tokens, and missing commas like "D/B # 31D/B # 32"
    s = re.sub(r'(\d)\s+([A-Z])', r'\1,\2', s)
    s = re.sub(r'(\d)\s*([A-Z/])', r'\1,\2', s)
    segments = [seg.strip() for seg in s.split(',') if seg.strip()]
    for seg in segments:
        tokens = re.findall(r'([^\d,]*?)(\d+)', seg)
        if not tokens:
            continue
        is_range = False
        if len(tokens) == 2:
            first_num_end = seg.index(tokens[0][1]) + len(tokens[0][1])
            rest = seg[first_num_end:]
            if '-' in rest and re.search(r'\d', rest):
                is_range = True
        if is_range:
            prefix1 = tokens[0][0].strip()
            num1 = int(tokens[0][1])
            num2 = int(tokens[1][1])
            if prefix1:
                current_prefix = norm_prefix(prefix1)
            for n in range(min(num1, num2), max(num1, num2) + 1):
                machines.add((current_prefix, n))
        else:
            for pfx, num in tokens:
                pfx = pfx.strip()
                if pfx:
                    current_prefix = norm_prefix(pfx)
                machines.add((current_prefix, int(num)))
    return machines

SRC = r"D:\claude\Project\raw\BOI 14 upgrade up Mar 20'26_finance confirm.xlsx"
OUT = r"D:\claude\Project\Output\BOI14_Assembly_Budget_Analysis.xlsx"

wb_src = openpyxl.load_workbook(SRC, data_only=True)

# ============ STYLES ============
DARK_BLUE = "1B3A5C"
MED_BLUE = "2E75B6"
GREEN = "2D8E4E"
ORANGE = "E67E22"
LIGHT_BLUE = "E8F0FE"
LIGHT_GREEN = "E2F0D9"
WHITE = "FFFFFF"

hdr_font = Font(name="Arial", bold=True, color=WHITE, size=11)
hdr_fill = PatternFill("solid", fgColor=DARK_BLUE)
hdr_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
data_font = Font(name="Arial", size=10)
title_font = Font(name="Arial", bold=True, size=16, color=DARK_BLUE)
section_font = Font(name="Arial", bold=True, size=13, color=DARK_BLUE)
thin_border = Border(
    left=Side(style='thin', color='D0D0D0'), right=Side(style='thin', color='D0D0D0'),
    top=Side(style='thin', color='D0D0D0'), bottom=Side(style='thin', color='D0D0D0'))
alt_fill_1 = PatternFill("solid", fgColor=LIGHT_BLUE)
alt_fill_2 = PatternFill("solid", fgColor=WHITE)

def style_header_row(ws, row, cols, font=hdr_font, fill=hdr_fill):
    for c in range(1, cols+1):
        cell = ws.cell(row, c)
        cell.font = font; cell.fill = fill; cell.alignment = hdr_align; cell.border = thin_border

def style_data_row(ws, row, cols, idx=0):
    fill = alt_fill_1 if idx % 2 == 0 else alt_fill_2
    for c in range(1, cols+1):
        cell = ws.cell(row, c)
        cell.font = data_font; cell.border = thin_border; cell.fill = fill

def style_total_row(ws, row, cols, fill_color=MED_BLUE):
    for c in range(1, cols+1):
        cell = ws.cell(row, c)
        cell.font = Font(name="Arial", bold=True, color=WHITE, size=10)
        cell.fill = PatternFill("solid", fgColor=fill_color); cell.border = thin_border

# ============ PARSE SOURCE DATA ============
ws_fa = wb_src['Detail upgrade BOI 9 to 14 (FA)']
ws_summary = wb_src['Summary ']
ws_pr = wb_src['PR']
ws_sum15m = wb_src['SUM 1.5M']

# Machine type mapping (process -> summary machine type)
process_map = {
    'SAW': 'SAW',
    'DIE ATTACH': 'DieAttach',
    'WIRE BONDING': 'Wirebonder',
    'Backgrind': 'Backgrind',
    'INSPECTION': 'Inspection',
    'MOLD': 'MOLD',
    'MARK': 'Laser Mark',
    'TRIM/FORM': 'Trim Form',
    'Form/Sing': 'F/S',
    'ISOLATE': 'ISOLATE',
    'OVEN': 'OVEN',
}

# --- Parse Assembly items from FA sheet (rows 7-115) ---
assy_upgrade = []
current_process = ''
mch_data = defaultdict(lambda: {'plan': 0, 'spent': 0, 'remain': 0, 'count': 0, 'pr_count': 0, 'items': [], 'machines': set()})

for r in range(7, 116):
    b = ws_fa.cell(r, 2).value
    if not b:
        continue
    a = ws_fa.cell(r, 1).value
    if a and isinstance(a, str) and 'ขั้นตอน' not in a:
        current_process = a.strip()

    # Plant: col 13. Normalize MTHAI -> MTAI for consistency
    plant_raw = ws_fa.cell(r, 13).value or ''
    plant_raw = str(plant_raw).strip()
    if 'MMT' in plant_raw:
        plant = 'MMT'
    else:
        plant = 'MTAI'  # MTHAI, BOI transfer, and unassigned are all MTAI

    total_usd = ws_fa.cell(r, 12).value or 0
    spent = float(ws_fa.cell(r, 17).value or 0)
    remain = float(ws_fa.cell(r, 18).value or 0) if ws_fa.cell(r, 18).value is not None else 0
    pr = ws_fa.cell(r, 15).value
    ccid = ws_fa.cell(r, 14).value
    remark = ws_fa.cell(r, 19).value

    # Determine machine type
    mch = process_map.get(current_process, current_process)
    dl = str(b).lower()
    if 'x-ray' in dl or 'xray' in dl:
        mch = 'X-RAY'
    elif 'plasma' in dl:
        mch = 'PLASMA'

    item = {
        'process': current_process, 'mch_type': mch, 'detail': str(b).strip(),
        'propose': ws_fa.cell(r, 3).value,
        'mc_no': ws_fa.cell(r, 6).value,
        'qty_set': ws_fa.cell(r, 7).value,
        'qty_mc': ws_fa.cell(r, 8).value,
        'total_usd': total_usd, 'plant': plant,
        'contact': plant_raw if plant_raw and 'BOI' not in plant_raw else '',
        'ccid': ccid, 'pr': pr, 'spent': spent, 'remain': remain,
        'remark': remark,
    }
    assy_upgrade.append(item)

    key = (plant, mch)
    mch_data[key]['plan'] += total_usd
    mch_data[key]['spent'] += spent
    mch_data[key]['remain'] += remain
    mch_data[key]['count'] += 1
    if pr:
        mch_data[key]['pr_count'] += 1
    mch_data[key]['machines'] |= parse_mc_no(item['mc_no'])

# --- Upgrade PRs ---
upgrade_prs = []
for r in range(2, ws_pr.max_row + 1):
    pr_num = ws_pr.cell(r, 1).value
    pr_usd = ws_pr.cell(r, 2).value
    if pr_num and pr_usd:
        upgrade_prs.append({'pr': str(pr_num), 'usd': pr_usd})

# --- Summary data (Assembly = rows 11-24) ---
summary_assy = []
for r in range(11, 25):
    mch = ws_summary.cell(r, 1).value
    mc_count = ws_summary.cell(r, 2).value
    cost = ws_summary.cell(r, 3).value
    q2_actual = ws_summary.cell(r, 4).value or 0
    q3_actual = ws_summary.cell(r, 5).value or 0
    total_actual = ws_summary.cell(r, 6).value or 0
    pending = ws_summary.cell(r, 7).value or 0
    if mch and cost:
        summary_assy.append({'mch': mch.strip(), 'mc_count': mc_count, 'cost': cost,
                            'q2': q2_actual, 'q3': q3_actual, 'total_actual': total_actual, 'pending': pending})

# Summary test (rows 3-8)
summary_test = []
for r in range(3, 9):
    mch = ws_summary.cell(r, 1).value
    mc_count = ws_summary.cell(r, 2).value
    cost = ws_summary.cell(r, 3).value
    total_actual = ws_summary.cell(r, 6).value or 0
    pending = ws_summary.cell(r, 7).value or 0
    if mch and cost:
        summary_test.append({'mch': mch.strip(), 'cost': cost, 'total_actual': total_actual, 'pending': pending})

# --- SUM 1.5M data ---
# Row 7: Assembly MTHAI (col 1 is empty, inferred from position)
# Row 8: Assembly MMT
# Let me read the actual labels
sum15m_labels = []
for r in range(7, 14):
    label = ws_sum15m.cell(r, 1).value
    sum15m_labels.append(label)

# Actually the SUM 1.5M doesn't have labels per row clearly
# From the data: row 6 is total header (1500), rows 7+ are departments
# Based on context: row 7 = Assembly MTHAI, row 8 = Assembly MMT, etc.
# Let me use Summary totals instead

# ============ CREATE WORKBOOK ============
wb = Workbook()

# ============================
# SHEET 1: DASHBOARD
# ============================
ws1 = wb.active
ws1.title = "Assembly Dashboard"
ws1.sheet_properties.tabColor = DARK_BLUE

ws1.cell(1, 1, "BOI 14 - Assembly Budget Analysis (BOI 6&9 Upgrade to BOI14)").font = Font(name="Arial", bold=True, size=18, color=DARK_BLUE)
ws1.merge_cells("A1:H1")
ws1.cell(2, 1, "Upgrade Only | MTAI & MMT | As of Mar 2026 (Finance Confirmed) | Rate: 35 THB/USD").font = Font(name="Arial", size=11, color="666666")
ws1.merge_cells("A2:H2")

# --- Budget Overview: MTAI ---
r = 4
ws1.cell(r, 1, "ASSEMBLY UPGRADE OVERVIEW - MTAI").font = section_font
ws1.merge_cells(f"A{r}:G{r}")
# (7 columns total: Machine Type, Items, Unique M/C, Cost, Spent, Pending, % Spent)

r = 6
ov_headers = ["Machine Type", "Items", "Unique M/C", "Upgrade Cost (USD)", "Spent (USD)", "Pending (USD)", "% Spent"]
for c, h in enumerate(ov_headers, 1):
    ws1.cell(r, c, h)
style_header_row(ws1, r, 7)

r = 7
ov_mtai_first = r
# Collect all machine types across both plants
all_mch_types = sorted(set(k[1] for k in mch_data))

# Track unique machines across all types per plant
mtai_total_machines = set()
for idx, mch in enumerate(all_mch_types):
    key = ('MTAI', mch)
    v = mch_data.get(key)
    if not v:
        continue
    ws1.cell(r, 1, mch)
    ws1.cell(r, 2, v['count'])
    ws1.cell(r, 3, len(v['machines']))
    ws1.cell(r, 4, v['plan'])
    ws1.cell(r, 5, v['spent'])
    ws1.cell(r, 6, v['plan'] - v['spent'])
    ws1.cell(r, 7).value = f'=IF(D{r}=0,"",E{r}/D{r})'
    style_data_row(ws1, r, 7, idx)
    for c in [4, 5, 6]: ws1.cell(r, c).number_format = '#,##0.00'
    ws1.cell(r, 7).number_format = '0.0%'
    ws1.cell(r, 2).alignment = Alignment(horizontal="center")
    ws1.cell(r, 3).alignment = Alignment(horizontal="center")
    mtai_total_machines |= v['machines']
    r += 1

ws1.cell(r, 1, "MTAI TOTAL")
ws1.cell(r, 2).value = f'=SUM(B{ov_mtai_first}:B{r-1})'
ws1.cell(r, 3, len(mtai_total_machines))
ws1.cell(r, 4).value = f'=SUM(D{ov_mtai_first}:D{r-1})'
ws1.cell(r, 5).value = f'=SUM(E{ov_mtai_first}:E{r-1})'
ws1.cell(r, 6).value = f'=SUM(F{ov_mtai_first}:F{r-1})'
ws1.cell(r, 7).value = f'=IF(D{r}=0,"",E{r}/D{r})'
style_total_row(ws1, r, 7, MED_BLUE)
for c in [4, 5, 6]: ws1.cell(r, c).number_format = '#,##0.00'
ws1.cell(r, 7).number_format = '0.0%'
ws1.cell(r, 3).alignment = Alignment(horizontal="center")
ov_mtai_total = r

# --- Budget Overview: MMT ---
r += 2
ws1.cell(r, 1, "ASSEMBLY UPGRADE OVERVIEW - MMT").font = section_font
ws1.merge_cells(f"A{r}:G{r}")

r += 2
for c, h in enumerate(ov_headers, 1):
    ws1.cell(r, c, h)
style_header_row(ws1, r, 7)

r += 1
ov_mmt_first = r
mmt_total_machines = set()
for idx, mch in enumerate(all_mch_types):
    key = ('MMT', mch)
    v = mch_data.get(key)
    if not v:
        continue
    ws1.cell(r, 1, mch)
    ws1.cell(r, 2, v['count'])
    ws1.cell(r, 3, len(v['machines']))
    ws1.cell(r, 4, v['plan'])
    ws1.cell(r, 5, v['spent'])
    ws1.cell(r, 6, v['plan'] - v['spent'])
    ws1.cell(r, 7).value = f'=IF(D{r}=0,"",E{r}/D{r})'
    style_data_row(ws1, r, 7, idx)
    for c in [4, 5, 6]: ws1.cell(r, c).number_format = '#,##0.00'
    ws1.cell(r, 7).number_format = '0.0%'
    ws1.cell(r, 2).alignment = Alignment(horizontal="center")
    ws1.cell(r, 3).alignment = Alignment(horizontal="center")
    mmt_total_machines |= v['machines']
    r += 1

ws1.cell(r, 1, "MMT TOTAL")
ws1.cell(r, 2).value = f'=SUM(B{ov_mmt_first}:B{r-1})'
ws1.cell(r, 3, len(mmt_total_machines))
ws1.cell(r, 4).value = f'=SUM(D{ov_mmt_first}:D{r-1})'
ws1.cell(r, 5).value = f'=SUM(E{ov_mmt_first}:E{r-1})'
ws1.cell(r, 6).value = f'=SUM(F{ov_mmt_first}:F{r-1})'
ws1.cell(r, 7).value = f'=IF(D{r}=0,"",E{r}/D{r})'
style_total_row(ws1, r, 7, MED_BLUE)
for c in [4, 5, 6]: ws1.cell(r, c).number_format = '#,##0.00'
ws1.cell(r, 7).number_format = '0.0%'
ws1.cell(r, 3).alignment = Alignment(horizontal="center")
ov_mmt_total = r

# Assembly Grand Total
r += 1
ws1.cell(r, 1, "ASSEMBLY GRAND TOTAL")
ws1.cell(r, 2).value = f'=B{ov_mtai_total}+B{ov_mmt_total}'
ws1.cell(r, 3).value = f'=C{ov_mtai_total}+C{ov_mmt_total}'
ws1.cell(r, 4).value = f'=D{ov_mtai_total}+D{ov_mmt_total}'
ws1.cell(r, 5).value = f'=E{ov_mtai_total}+E{ov_mmt_total}'
ws1.cell(r, 6).value = f'=F{ov_mtai_total}+F{ov_mmt_total}'
ws1.cell(r, 7).value = f'=IF(D{r}=0,"",E{r}/D{r})'
style_total_row(ws1, r, 7, DARK_BLUE)
for c in [4, 5, 6]: ws1.cell(r, c).number_format = '#,##0.00'
ws1.cell(r, 7).number_format = '0.0%'

for c, w in {1:28, 2:10, 3:12, 4:18, 5:16, 6:16, 7:10}.items():
    ws1.column_dimensions[get_column_letter(c)].width = w
ws1.freeze_panes = "A3"

# ============================
# Helper: write detail sheet
# ============================
def write_detail_sheet(wb, sheet_name, tab_color, title, items):
    ws = wb.create_sheet(sheet_name)
    ws.sheet_properties.tabColor = tab_color
    ws.cell(1, 1, title).font = title_font
    ws.merge_cells("A1:P1")

    detail_headers = ["No.", "Machine Type", "Process", "Upgrade Details", "MC No.", "Qty/Set", "Qty MC",
                      "Total (USD)", "CCID", "PR#", "Spent (USD)", "Remain (USD)", "% Spent", "Status", "Remark"]
    r = 3
    for c, h in enumerate(detail_headers, 1):
        ws.cell(r, c, h)
    style_header_row(ws, r, 15)

    r = 4
    sorted_items = sorted(items, key=lambda x: (0 if x['spent'] > 0 else (1 if x['pr'] else 2), x['mch_type']))

    for idx, item in enumerate(sorted_items):
        spent = item['spent']
        has_pr = item['pr'] is not None and str(item['pr']).strip() != ''
        if spent > 0 and item['remain'] <= 0:
            status = "Completed"
        elif spent > 0:
            status = "In Progress"
        elif has_pr:
            status = "PR Issued"
        else:
            status = "Pending"

        ws.cell(r, 1, idx + 1)
        ws.cell(r, 2, item['mch_type'])
        ws.cell(r, 3, item['process'])
        ws.cell(r, 4, item['detail'])
        ws.cell(r, 5, item['mc_no'])
        ws.cell(r, 6, item['qty_set'])
        ws.cell(r, 7, item['qty_mc'])
        ws.cell(r, 8, item['total_usd'])
        ws.cell(r, 9, item['ccid'])
        ws.cell(r, 10, item['pr'])
        ws.cell(r, 11, item['spent'] if item['spent'] else None)
        ws.cell(r, 12, item['remain'] if item['remain'] else None)
        ws.cell(r, 13).value = f'=IF(H{r}=0,"",K{r}/H{r})'
        ws.cell(r, 14, status)
        ws.cell(r, 15, item['remark'])

        style_data_row(ws, r, 15, idx)
        ws.cell(r, 8).number_format = '#,##0.00'
        ws.cell(r, 11).number_format = '#,##0.00'
        ws.cell(r, 12).number_format = '#,##0.00'
        ws.cell(r, 13).number_format = '0.0%'
        for cc in [1, 2, 6, 7, 14]:
            ws.cell(r, cc).alignment = Alignment(horizontal="center")

        if status == "Completed":
            ws.cell(r, 14).fill = PatternFill("solid", fgColor="C6EFCE")
            ws.cell(r, 14).font = Font(name="Arial", size=10, color="006100")
        elif status == "In Progress":
            ws.cell(r, 14).fill = PatternFill("solid", fgColor="FFEB9C")
            ws.cell(r, 14).font = Font(name="Arial", size=10, color="9C6500")
        elif status == "PR Issued":
            ws.cell(r, 14).fill = PatternFill("solid", fgColor="FCD5B4")
            ws.cell(r, 14).font = Font(name="Arial", size=10, color="974706")
        r += 1

    last = r - 1
    ws.cell(r, 1, "TOTAL")
    ws.cell(r, 7).value = f'=SUM(G4:G{last})'
    ws.cell(r, 8).value = f'=SUM(H4:H{last})'
    ws.cell(r, 11).value = f'=SUM(K4:K{last})'
    ws.cell(r, 12).value = f'=SUM(L4:L{last})'
    ws.cell(r, 13).value = f'=IF(H{r}=0,"",K{r}/H{r})'
    for c in [8, 11, 12]: ws.cell(r, c).number_format = '#,##0.00'
    ws.cell(r, 13).number_format = '0.0%'
    style_total_row(ws, r, 15, DARK_BLUE)

    ws.auto_filter.ref = f"A3:O{last}"
    ws.freeze_panes = "A4"
    for c, w in {1:5, 2:16, 3:18, 4:55, 5:35, 6:8, 7:8, 8:13, 9:12, 10:22, 11:13, 12:13, 13:9, 14:13, 15:40}.items():
        ws.column_dimensions[get_column_letter(c)].width = w
    return ws

# ============================
# SHEET 2: MTAI UPGRADE DETAIL
# ============================
mtai_items = [i for i in assy_upgrade if i['plant'] == 'MTAI']
write_detail_sheet(wb, "MTAI Upgrade Detail", MED_BLUE, "MTAI - Assembly Upgrade Items Detail (BOI 14)", mtai_items)

# ============================
# SHEET 3: MMT UPGRADE DETAIL
# ============================
mmt_items = [i for i in assy_upgrade if i['plant'] == 'MMT']
write_detail_sheet(wb, "MMT Upgrade Detail", GREEN, "MMT - Assembly Upgrade Items Detail (BOI 14)", mmt_items)

# ============================
# SHEET 5: UPGRADE PRs
# ============================
ws4 = wb.create_sheet("Upgrade PRs")
ws4.sheet_properties.tabColor = ORANGE

ws4.cell(1, 1, "BOI 14 Upgrade - PR List (All Departments)").font = title_font
ws4.merge_cells("A1:E1")

pr_to_item = {}
for item in assy_upgrade:
    if item['pr']:
        for pr_raw in str(item['pr']).split(','):
            pr_clean = pr_raw.strip()
            if pr_clean:
                pr_to_item[pr_clean] = f"{item['plant']} | {item['mch_type']} - {str(item['detail'])[:40]}"

r = 3
for c, h in enumerate(["No.", "PR#", "Amount (USD)", "Linked Item (Plant | Machine - Detail)", "Type"], 1):
    ws4.cell(r, c, h)
style_header_row(ws4, r, 5)

r = 4
for idx, p in enumerate(upgrade_prs):
    ws4.cell(r, 1, idx + 1)
    ws4.cell(r, 2, p['pr'])
    ws4.cell(r, 3, p['usd'])
    ws4.cell(r, 3).number_format = '#,##0.00'
    linked = pr_to_item.get(p['pr'], '')
    ws4.cell(r, 4, linked)
    ws4.cell(r, 5, "ASSY" if linked else "TEST")
    style_data_row(ws4, r, 5, idx)
    if linked:
        for c in range(1, 6):
            ws4.cell(r, c).fill = PatternFill("solid", fgColor=LIGHT_BLUE)
    r += 1

ws4.cell(r, 1, "TOTAL")
ws4.cell(r, 3).value = f'=SUM(C4:C{r-1})'
ws4.cell(r, 3).number_format = '#,##0.00'
style_total_row(ws4, r, 5, DARK_BLUE)

ws4.auto_filter.ref = f"A3:E{r-1}"
ws4.freeze_panes = "A4"
ws4.column_dimensions['A'].width = 6
ws4.column_dimensions['B'].width = 18
ws4.column_dimensions['C'].width = 18
ws4.column_dimensions['D'].width = 55
ws4.column_dimensions['E'].width = 10

# ============ SAVE ============
os.makedirs(os.path.dirname(OUT), exist_ok=True)
wb.save(OUT)
print(f"Saved: {OUT}")
print(f"Sheets: {wb.sheetnames}")
print(f"Total Assembly items: {len(assy_upgrade)}")
print(f"  MTAI: {len(mtai_items)}")
print(f"  MMT:  {len(mmt_items)}")
print(f"  (All unassigned items merged into MTAI)")
print(f"MTAI machine types: {len([k for k in mch_data if k[0]=='MTAI'])}")
print(f"MMT machine types: {len([k for k in mch_data if k[0]=='MMT'])}")
print(f"Upgrade PRs: {len(upgrade_prs)}")

# Summary stats
for plant in ['MTAI', 'MMT']:
    items = [i for i in assy_upgrade if i['plant'] == plant]
    if items:
        plan = sum(i['total_usd'] for i in items)
        spent = sum(i['spent'] for i in items)
        prs = len([i for i in items if i['pr']])
        print(f"  {plant}: Plan ${plan:,.2f} | Spent ${spent:,.2f} | PRs: {prs}")
