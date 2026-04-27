import sys, os, math
sys.stdout.reconfigure(encoding='utf-8')

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.chart.data import CategoryChartData
import lxml.etree as etree
from pptx.oxml.ns import qn
import openpyxl
from collections import Counter, defaultdict

# ── Paths ────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.join(SCRIPT_DIR, '.claude', 'skills', 'data-to-slides')
EXCEL_PATH = os.path.join(SCRIPT_DIR, 'raw', 'DA_machine.xls.xlsx')
OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'Output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

LOGO_FOOTER = os.path.join(SKILL_DIR, 'microchip_logo.jpg')
LOGO_TITLE_ROUND = os.path.join(SKILL_DIR, 'microchip_logo_title.png')
LOGO_TITLE_WORD = os.path.join(SKILL_DIR, 'microchip_logo_title.jpg')

# ── Colors ───────────────────────────────────────────────────────────────
PRIMARY_BLUE = RGBColor(0x0E, 0x36, 0x89)
LIGHT_BLUE   = RGBColor(0x1D, 0x9C, 0xE4)
DARK_TEXT     = RGBColor(0x0A, 0x0B, 0x0F)
DARK_GRAY     = RGBColor(0x4A, 0x4A, 0x4A)
MEDIUM_GRAY   = RGBColor(0x8A, 0x8A, 0x8A)
LIGHT_GRAY    = RGBColor(0xD9, 0xD9, 0xD9)
VLIGHT_GRAY   = RGBColor(0xF7, 0xF7, 0xF7)
WHITE         = RGBColor(0xFF, 0xFF, 0xFF)
GREEN         = RGBColor(0x5E, 0xBF, 0x33)
ORANGE        = RGBColor(0xFD, 0x7F, 0x20)
RED           = RGBColor(0xCC, 0x00, 0x00)
YELLOW        = RGBColor(0xFF, 0xD5, 0x3A)
PURPLE        = RGBColor(0x70, 0x20, 0x76)

CHART_COLORS = ['0E3689', '1D9CE4', '5EBF33', 'FD7F20', 'CC0000', '702076', 'FFD53A', '4A4A4A']

# ── Data Loading ─────────────────────────────────────────────────────────
wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)

# Die Bonder machines from DA_machine list
ws_list = wb['DA_machine list']
die_bonders = []
for row in ws_list.iter_rows(min_row=2, max_row=ws_list.max_row, values_only=True):
    area, mc_code, mc_name, ods, serial, model, accept_date, status = row
    if mc_name and 'Die bonder' in str(mc_name):
        die_bonders.append({
            'code': mc_code, 'name': mc_name, 'model': model,
            'status': status or 'No Status'
        })

total_db = len(die_bonders)
status_cnt = Counter(m['status'] for m in die_bonders)
model_cnt = Counter(m['model'] for m in die_bonders)
model_status = defaultdict(lambda: Counter())
for m in die_bonders:
    model_status[m['model']][m['status']] += 1

# MTAI ASSY DA capacity analysis
ws_cap = wb['MTAI ASSY DA']
packages = []
for row in ws_cap.iter_rows(min_row=3, max_row=24, values_only=True):
    _, item, pkg, max_cap_mold, drr_max, std_uph, cur_uph, uph_diff_pct, std_da_req, cur_da, mc_no, mc_shutdown, _, cur_usage, cur_output = row
    if pkg and pkg != 'Total':
        packages.append({
            'pkg': pkg, 'drr_max': drr_max or 0, 'std_uph': std_uph or 0,
            'cur_uph': cur_uph or 0, 'uph_diff': uph_diff_pct or 0,
            'std_req': std_da_req or 0, 'cur_da': cur_da or 0,
            'cur_usage': cur_usage or 0, 'cur_output': cur_output or 0,
            'max_cap_mold': max_cap_mold or 0,
            'mc_shutdown': mc_shutdown, 'mc_no': mc_no
        })

# Totals row
total_row = list(ws_cap.iter_rows(min_row=25, max_row=25, values_only=True))[0]
total_drr = total_row[4] or 0
total_output = total_row[14] or 0
total_std_req = total_row[8] or 0
total_cur_da = total_row[9] or 0
total_shutdown = total_row[11] or 0
total_cur_usage = total_row[13] or 0

# DA_UPH data
ws_uph = wb['DA_UPH']
uph_data = []
for row in ws_uph.iter_rows(min_row=2, max_row=ws_uph.max_row, values_only=True):
    mc, mc_type, pkg, die_size, uph = row
    if mc:
        uph_data.append({'mc': mc, 'type': mc_type, 'pkg': pkg, 'uph': uph or 0})

uph_by_type = defaultdict(list)
for u in uph_data:
    uph_by_type[u['type']].append(u['uph'])

# ── Presentation Setup ───────────────────────────────────────────────────
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

# ── Helpers ──────────────────────────────────────────────────────────────
def add_bg(slide, color=WHITE):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color

def add_text_box(slide, left, top, width, height, text, font_size=14,
                 bold=False, color=DARK_TEXT, align=PP_ALIGN.LEFT,
                 font_name='Calibri', anchor=MSO_ANCHOR.TOP):
    txBox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = txBox.text_frame
    tf.word_wrap = True
    tf.auto_size = None
    p = tf.paragraphs[0]
    p.text = str(text)
    p.font.size = Pt(font_size)
    p.font.bold = bold
    p.font.color.rgb = color
    p.font.name = font_name
    p.alignment = align
    tf.vertical_anchor = anchor
    return txBox

def add_shape_box(slide, left, top, width, height, fill_color=WHITE, border_color=None):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(left), Inches(top), Inches(width), Inches(height)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if border_color:
        shape.line.color.rgb = border_color
        shape.line.width = Pt(1)
    else:
        shape.line.fill.background()
    shape.shadow.inherit = False
    return shape

def add_header_bar(slide, title_text):
    bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), Inches(0), Inches(13.333), Inches(0.9)
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = PRIMARY_BLUE
    bar.line.fill.background()
    bar.shadow.inherit = False
    add_text_box(slide, 0.4, 0.15, 12, 0.6, title_text,
                 font_size=26, bold=True, color=WHITE)

def add_footer(slide, slide_num):
    # Footer text
    add_text_box(slide, 4.55, 7.09, 4.22, 0.26,
                 "Microchip Proprietary and Confidential",
                 font_size=9, color=MEDIUM_GRAY, font_name='Calibri Light',
                 align=PP_ALIGN.CENTER)
    # Slide number
    add_text_box(slide, 0.17, 7.06, 0.42, 0.40,
                 str(slide_num), font_size=9, color=MEDIUM_GRAY,
                 font_name='Calibri Light', align=PP_ALIGN.CENTER)
    # Logo
    if os.path.exists(LOGO_FOOTER):
        slide.shapes.add_picture(LOGO_FOOTER, Inches(11.57), Inches(6.99), Inches(1.58), Inches(0.40))

def add_kpi_card(slide, left, top, width, height, label, value, accent_color=PRIMARY_BLUE, sub_text=None):
    # Card background
    card = add_shape_box(slide, left, top, width, height, WHITE, LIGHT_GRAY)
    # Accent bar on top
    bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(left), Inches(top), Inches(width), Inches(0.08)
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = accent_color
    bar.line.fill.background()
    bar.shadow.inherit = False
    # Value
    add_text_box(slide, left + 0.15, top + 0.2, width - 0.3, 0.6,
                 str(value), font_size=32, bold=True, color=accent_color,
                 align=PP_ALIGN.CENTER)
    # Label
    add_text_box(slide, left + 0.15, top + 0.85, width - 0.3, 0.4,
                 label, font_size=12, color=DARK_GRAY,
                 align=PP_ALIGN.CENTER)
    if sub_text:
        add_text_box(slide, left + 0.15, top + 1.15, width - 0.3, 0.3,
                     sub_text, font_size=10, color=MEDIUM_GRAY,
                     align=PP_ALIGN.CENTER)

def set_series_color(series_element, hex_color):
    spPr = series_element.find(qn('c:spPr'))
    if spPr is None:
        spPr = etree.SubElement(series_element, qn('c:spPr'))
    solidFill = spPr.find(qn('a:solidFill'))
    if solidFill is None:
        solidFill = etree.SubElement(spPr, qn('a:solidFill'))
    for child in list(solidFill):
        solidFill.remove(child)
    srgbClr = etree.SubElement(solidFill, qn('a:srgbClr'))
    srgbClr.set('val', hex_color)

def set_point_color(series_element, point_idx, hex_color):
    dPt = etree.SubElement(series_element, qn('c:dPt'))
    idx_el = etree.SubElement(dPt, qn('c:idx'))
    idx_el.set('val', str(point_idx))
    spPr = etree.SubElement(dPt, qn('c:spPr'))
    solidFill = etree.SubElement(spPr, qn('a:solidFill'))
    srgbClr = etree.SubElement(solidFill, qn('a:srgbClr'))
    srgbClr.set('val', hex_color)

def format_number(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n/1_000:.0f}K"
    return str(int(n))

slide_num = 0

# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 1: Title
# ═══════════════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, WHITE)

# Thin blue accent line
line = slide.shapes.add_shape(
    MSO_SHAPE.RECTANGLE,
    Inches(0.5), Inches(3.2), Inches(7.5), Inches(0.05)
)
line.fill.solid()
line.fill.fore_color.rgb = PRIMARY_BLUE
line.line.fill.background()
line.shadow.inherit = False

# Vertical blue line
vline = slide.shapes.add_shape(
    MSO_SHAPE.RECTANGLE,
    Inches(8.2), Inches(1.5), Inches(0.04), Inches(4.0)
)
vline.fill.solid()
vline.fill.fore_color.rgb = PRIMARY_BLUE
vline.line.fill.background()
vline.shadow.inherit = False

add_text_box(slide, 0.5, 1.2, 7.5, 1.0,
             "Die Attach Machine", font_size=40, bold=True, color=PRIMARY_BLUE)
add_text_box(slide, 0.5, 2.0, 7.5, 0.8,
             "Loading Capacity Analysis", font_size=36, bold=True, color=PRIMARY_BLUE)
add_text_box(slide, 0.5, 3.5, 7.5, 0.5,
             "Machine Requirement Analysis for Additional Loading",
             font_size=17, color=LIGHT_BLUE, font_name='Calibri Light')
add_text_box(slide, 0.5, 4.2, 7.5, 0.5,
             "MTAI Assembly  |  Die Attach Section  |  April 2026",
             font_size=14, color=DARK_GRAY, font_name='Calibri Light')

if os.path.exists(LOGO_TITLE_ROUND):
    slide.shapes.add_picture(LOGO_TITLE_ROUND, Inches(0.23), Inches(5.62), Inches(1.78), Inches(1.78))
if os.path.exists(LOGO_TITLE_WORD):
    slide.shapes.add_picture(LOGO_TITLE_WORD, Inches(8.60), Inches(2.88), Inches(3.92), Inches(0.99))

# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 2: Executive Summary
# ═══════════════════════════════════════════════════════════════════════════
slide_num += 1
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, WHITE)
add_header_bar(slide, "Executive Summary")
add_footer(slide, slide_num)

# KPI cards row
gap_pct = ((total_drr - total_output) / total_drr * 100) if total_drr else 0
add_kpi_card(slide, 0.4, 1.2, 2.4, 1.5, "Total DA Machines", str(total_db), PRIMARY_BLUE, f"Running: {status_cnt.get('Run',0)}")
add_kpi_card(slide, 3.1, 1.2, 2.4, 1.5, "Running", str(status_cnt.get('Run', 0)), GREEN, f"{status_cnt.get('Run',0)/total_db*100:.0f}% of total")
add_kpi_card(slide, 5.8, 1.2, 2.4, 1.5, "Shutdown", str(status_cnt.get('Machine Shutdown', 0)), RED, "Need repair")
add_kpi_card(slide, 8.5, 1.2, 2.4, 1.5, "Output Gap", f"{gap_pct:.0f}%", ORANGE, f"vs DRR Target")
add_kpi_card(slide, 11.2, 1.2, 1.8, 1.5, "MC Usage", str(int(total_cur_usage)), LIGHT_BLUE, f"of {total_db}")

# Key findings
findings_box = add_shape_box(slide, 0.4, 3.0, 6.2, 4.0, VLIGHT_GRAY, LIGHT_GRAY)
add_text_box(slide, 0.6, 3.1, 5.8, 0.4, "Key Findings", font_size=16, bold=True, color=PRIMARY_BLUE)

findings = [
    f"Total Die Attach machines: {total_db} units ({status_cnt.get('Run',0)} running, {status_cnt.get('Machine Shutdown',0)} shutdown)",
    f"Current daily output: {total_output:,.0f} units vs DRR target: {total_drr:,.0f} units ({gap_pct:.0f}% gap)",
    f"STD machines required: {total_std_req:.0f} MCs vs Currently used: {int(total_cur_usage)} MCs",
    f"19 packages show UPH below standard (avg 17% lower than STD)",
    f"Critical packages: 28L SOIC (82% gap), 100L TQFP (79% gap), QFN (51% gap)",
    f"{int(total_shutdown)} machines currently in shutdown — repairable for capacity recovery",
]
y = 3.55
for f in findings:
    add_text_box(slide, 0.8, y, 5.6, 0.35, f"•  {f}", font_size=11, color=DARK_GRAY)
    y += 0.38

# Action summary
action_box = add_shape_box(slide, 6.9, 3.0, 6.1, 4.0, VLIGHT_GRAY, LIGHT_GRAY)
add_text_box(slide, 7.1, 3.1, 5.7, 0.4, "Recommended Actions", font_size=16, bold=True, color=PRIMARY_BLUE)

actions = [
    ("1. Repair Shutdown Machines", f"Restore {int(total_shutdown)} shutdown machines to increase available capacity", RED),
    ("2. Increase UPH to Standard", "Close 17% UPH gap across 19 packages through optimization", ORANGE),
    ("3. Hire Additional Operators", "Add 13 persons/shift (26 total) to support loading increase", LIGHT_BLUE),
    ("4. Prioritize Critical Packages", "Focus on 28L SOIC, 100L TQFP, QFN, 80L TQFP — largest gaps", PRIMARY_BLUE),
]
y = 3.55
for title, desc, color in actions:
    # Small color indicator
    ind = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(7.1), Inches(y+0.03), Inches(0.12), Inches(0.18))
    ind.fill.solid()
    ind.fill.fore_color.rgb = color
    ind.line.fill.background()
    ind.shadow.inherit = False
    add_text_box(slide, 7.4, y, 5.4, 0.25, title, font_size=12, bold=True, color=DARK_TEXT)
    add_text_box(slide, 7.4, y + 0.25, 5.4, 0.3, desc, font_size=10, color=DARK_GRAY)
    y += 0.6

# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 3: Machine Status Overview
# ═══════════════════════════════════════════════════════════════════════════
slide_num += 1
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, WHITE)
add_header_bar(slide, "DA Machine Status Overview")
add_footer(slide, slide_num)

# Donut-style: use pie chart for status
chart_data = CategoryChartData()
chart_data.categories = list(status_cnt.keys())
chart_data.add_series('Status', list(status_cnt.values()))

chart_frame = slide.shapes.add_chart(
    XL_CHART_TYPE.PIE, Inches(0.4), Inches(1.2), Inches(5.5), Inches(4.5), chart_data
)
chart = chart_frame.chart
chart.has_legend = True
chart.legend.position = XL_LEGEND_POSITION.BOTTOM
chart.legend.font.size = Pt(11)
chart.legend.font.name = 'Calibri'
chart.legend.include_in_layout = False

plot = chart.plots[0]
plot.has_data_labels = True
dl = plot.data_labels
dl.font.size = Pt(12)
dl.font.bold = True
dl.font.color.rgb = WHITE
dl.font.name = 'Calibri'
dl.number_format = '0'
dl.show_value = True
dl.show_percentage = True

status_colors = {'Run': '5EBF33', 'Machine Shutdown': 'CC0000', 'Automotive': '0E3689'}
ser = chart.series[0]._element
for i, cat in enumerate(status_cnt.keys()):
    set_point_color(ser, i, status_colors.get(cat, '4A4A4A'))

add_text_box(slide, 0.5, 5.85, 5.0, 0.4,
             f"Total: {total_db} Die Bonder Machines", font_size=13, bold=True, color=DARK_GRAY, align=PP_ALIGN.CENTER)

# Machine model breakdown - bar chart
chart_data2 = CategoryChartData()
models_sorted = sorted(model_cnt.items(), key=lambda x: x[1], reverse=True)
chart_data2.categories = [m[0] for m in models_sorted]
run_vals = [model_status[m[0]].get('Run', 0) for m in models_sorted]
sd_vals = [model_status[m[0]].get('Machine Shutdown', 0) for m in models_sorted]
chart_data2.add_series('Running', run_vals)
chart_data2.add_series('Shutdown', sd_vals)

chart_frame2 = slide.shapes.add_chart(
    XL_CHART_TYPE.BAR_STACKED, Inches(6.2), Inches(1.2), Inches(6.8), Inches(5.3), chart_data2
)
chart2 = chart_frame2.chart
chart2.has_legend = True
chart2.legend.position = XL_LEGEND_POSITION.BOTTOM
chart2.legend.font.size = Pt(10)
chart2.legend.font.name = 'Calibri'
chart2.legend.include_in_layout = False

# Style
set_series_color(chart2.series[0]._element, '5EBF33')
set_series_color(chart2.series[1]._element, 'CC0000')

chart2.value_axis.has_title = False
chart2.value_axis.tick_labels.font.size = Pt(9)
chart2.value_axis.tick_labels.font.name = 'Calibri'
chart2.category_axis.tick_labels.font.size = Pt(10)
chart2.category_axis.tick_labels.font.name = 'Calibri'

add_text_box(slide, 6.2, 6.6, 6.8, 0.3,
             "AD889 has 15 of 16 total shutdown machines — priority repair target",
             font_size=11, bold=True, color=RED, align=PP_ALIGN.CENTER)

# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 4: Capacity Gap Analysis (Output vs DRR)
# ═══════════════════════════════════════════════════════════════════════════
slide_num += 1
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, WHITE)
add_header_bar(slide, "Capacity Gap Analysis — Current Output vs DRR Target")
add_footer(slide, slide_num)

# Sort packages by gap percentage (largest gap first)
pkgs_with_gap = []
for p in packages:
    if p['drr_max'] > 0 and p['cur_output'] > 0:
        gap = (1 - p['cur_output'] / p['drr_max']) * 100
        pkgs_with_gap.append({**p, 'gap_pct': gap})
pkgs_with_gap.sort(key=lambda x: x['gap_pct'], reverse=True)

# Take top 12 for readability
top_pkgs = pkgs_with_gap[:12]

chart_data3 = CategoryChartData()
chart_data3.categories = [p['pkg'] for p in top_pkgs]
chart_data3.add_series('Current Output', [p['cur_output'] for p in top_pkgs])
chart_data3.add_series('DRR Target', [p['drr_max'] for p in top_pkgs])

chart_frame3 = slide.shapes.add_chart(
    XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.3), Inches(1.1), Inches(9.0), Inches(5.8), chart_data3
)
chart3 = chart_frame3.chart
chart3.has_legend = True
chart3.legend.position = XL_LEGEND_POSITION.BOTTOM
chart3.legend.font.size = Pt(11)
chart3.legend.font.name = 'Calibri'
chart3.legend.include_in_layout = False

set_series_color(chart3.series[0]._element, '1D9CE4')
set_series_color(chart3.series[1]._element, '0E3689')

chart3.value_axis.tick_labels.font.size = Pt(9)
chart3.value_axis.tick_labels.font.name = 'Calibri'
chart3.value_axis.tick_labels.number_format = '#,##0'
chart3.category_axis.tick_labels.font.size = Pt(9)
chart3.category_axis.tick_labels.font.name = 'Calibri'

# Gap % callout cards on the right
add_text_box(slide, 9.5, 1.1, 3.5, 0.4, "Output Gap %", font_size=16, bold=True, color=PRIMARY_BLUE)
y = 1.6
for i, p in enumerate(top_pkgs[:10]):
    gap_color = RED if p['gap_pct'] > 50 else (ORANGE if p['gap_pct'] > 25 else DARK_GRAY)
    row_bg = VLIGHT_GRAY if i % 2 == 0 else WHITE
    row = add_shape_box(slide, 9.5, y, 3.5, 0.38, row_bg)
    add_text_box(slide, 9.55, y + 0.02, 2.0, 0.34, p['pkg'], font_size=9, color=DARK_TEXT)
    add_text_box(slide, 11.5, y + 0.02, 1.4, 0.34, f"{p['gap_pct']:.0f}%",
                 font_size=11, bold=True, color=gap_color, align=PP_ALIGN.RIGHT)
    y += 0.39

# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 5: UPH Gap Analysis
# ═══════════════════════════════════════════════════════════════════════════
slide_num += 1
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, WHITE)
add_header_bar(slide, "UPH Performance Gap — STD vs Current UPH by Package")
add_footer(slide, slide_num)

# Sort by UPH diff (biggest gap first)
uph_sorted = sorted(packages, key=lambda x: abs(x['uph_diff']), reverse=True)

chart_data4 = CategoryChartData()
chart_data4.categories = [p['pkg'] for p in uph_sorted]
chart_data4.add_series('STD UPH', [p['std_uph'] for p in uph_sorted])
chart_data4.add_series('Current UPH', [p['cur_uph'] for p in uph_sorted])

chart_frame4 = slide.shapes.add_chart(
    XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.3), Inches(1.1), Inches(9.2), Inches(5.8), chart_data4
)
chart4 = chart_frame4.chart
chart4.has_legend = True
chart4.legend.position = XL_LEGEND_POSITION.BOTTOM
chart4.legend.font.size = Pt(11)
chart4.legend.font.name = 'Calibri'
chart4.legend.include_in_layout = False

set_series_color(chart4.series[0]._element, '0E3689')
set_series_color(chart4.series[1]._element, 'FD7F20')

chart4.value_axis.tick_labels.font.size = Pt(9)
chart4.value_axis.tick_labels.font.name = 'Calibri'
chart4.category_axis.tick_labels.font.size = Pt(9)
chart4.category_axis.tick_labels.font.name = 'Calibri'

# UPH Diff % column on right
add_text_box(slide, 9.7, 1.1, 3.3, 0.4, "UPH Difference %", font_size=16, bold=True, color=PRIMARY_BLUE)
y = 1.6
for i, p in enumerate(uph_sorted):
    diff = p['uph_diff']
    if diff > 0:
        diff_color = RED
        symbol = f"-{diff:.0f}%"
    else:
        diff_color = GREEN
        symbol = f"+{abs(diff):.0f}%"
    row_bg = VLIGHT_GRAY if i % 2 == 0 else WHITE
    row = add_shape_box(slide, 9.7, y, 3.3, 0.27, row_bg)
    add_text_box(slide, 9.75, y, 2.0, 0.27, p['pkg'], font_size=8, color=DARK_TEXT)
    add_text_box(slide, 11.6, y, 1.3, 0.27, symbol,
                 font_size=9, bold=True, color=diff_color, align=PP_ALIGN.RIGHT)
    y += 0.28

add_text_box(slide, 0.3, 6.9, 9.0, 0.3,
             "Average UPH gap: 17% — closing this gap can recover significant output without adding machines",
             font_size=11, bold=True, color=ORANGE, align=PP_ALIGN.LEFT)

# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 6: Machine Requirement — STD Required vs Current Usage
# ═══════════════════════════════════════════════════════════════════════════
slide_num += 1
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, WHITE)
add_header_bar(slide, "Machine Requirement — STD Required vs Current DA Usage")
add_footer(slide, slide_num)

# Sort by current usage
mc_sorted = sorted(packages, key=lambda x: x['cur_usage'], reverse=True)

chart_data5 = CategoryChartData()
chart_data5.categories = [p['pkg'] for p in mc_sorted]
chart_data5.add_series('STD Required MCs', [round(p['std_req'], 1) for p in mc_sorted])
chart_data5.add_series('Current DA MCs', [round(p['cur_da'], 1) for p in mc_sorted])
chart_data5.add_series('Actual Usage', [p['cur_usage'] for p in mc_sorted])

chart_frame5 = slide.shapes.add_chart(
    XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.3), Inches(1.1), Inches(12.7), Inches(5.7), chart_data5
)
chart5 = chart_frame5.chart
chart5.has_legend = True
chart5.legend.position = XL_LEGEND_POSITION.BOTTOM
chart5.legend.font.size = Pt(11)
chart5.legend.font.name = 'Calibri'
chart5.legend.include_in_layout = False

set_series_color(chart5.series[0]._element, '0E3689')
set_series_color(chart5.series[1]._element, '1D9CE4')
set_series_color(chart5.series[2]._element, '5EBF33')

chart5.value_axis.tick_labels.font.size = Pt(9)
chart5.value_axis.tick_labels.font.name = 'Calibri'
chart5.category_axis.tick_labels.font.size = Pt(9)
chart5.category_axis.tick_labels.font.name = 'Calibri'

add_text_box(slide, 0.3, 6.85, 12.7, 0.3,
             f"Total: STD Required = {total_std_req:.0f} MCs  |  Current DA = {total_cur_da:.0f} MCs  |  Actual Usage = {int(total_cur_usage)} MCs  |  All QFN is the largest consumer at 17 machines",
             font_size=11, bold=True, color=PRIMARY_BLUE, align=PP_ALIGN.CENTER)

# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 7: Detailed Package Analysis Table
# ═══════════════════════════════════════════════════════════════════════════
slide_num += 1
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, WHITE)
add_header_bar(slide, "Package-Level Capacity Detail")
add_footer(slide, slide_num)

# Table
headers = ['Package', 'DRR Max', 'STD UPH', 'Cur UPH', 'UPH Diff%', 'STD Req MC', 'Cur Usage', 'Cur Output', 'Gap%']
col_widths = [1.8, 1.1, 0.9, 0.9, 0.9, 1.0, 0.9, 1.2, 0.8]
n_rows = len(packages) + 1
table_shape = slide.shapes.add_table(n_rows, len(headers), Inches(0.3), Inches(1.15), Inches(12.7), Inches(5.7))
table = table_shape.table

# Set column widths
for i, w in enumerate(col_widths):
    table.columns[i].width = Inches(w)

# Style header
for i, h in enumerate(headers):
    cell = table.cell(0, i)
    cell.text = h
    for para in cell.text_frame.paragraphs:
        para.font.size = Pt(10)
        para.font.bold = True
        para.font.color.rgb = WHITE
        para.font.name = 'Calibri'
        para.alignment = PP_ALIGN.CENTER
    cell.fill.solid()
    cell.fill.fore_color.rgb = PRIMARY_BLUE
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE

# Fill data
for r, p in enumerate(packages):
    gap = (1 - p['cur_output'] / p['drr_max'] * 1.0) * 100 if p['drr_max'] > 0 and p['cur_output'] > 0 else 0
    row_data = [
        p['pkg'],
        f"{p['drr_max']:,.0f}" if p['drr_max'] else '-',
        f"{p['std_uph']:,.0f}" if p['std_uph'] else '-',
        f"{p['cur_uph']:,.0f}" if p['cur_uph'] else '-',
        f"{p['uph_diff']:.1f}%" if p['uph_diff'] else '-',
        f"{p['std_req']:.1f}" if p['std_req'] else '-',
        str(int(p['cur_usage'])) if p['cur_usage'] else '-',
        f"{p['cur_output']:,.0f}" if p['cur_output'] else '-',
        f"{gap:.0f}%"
    ]
    for c, val in enumerate(row_data):
        cell = table.cell(r + 1, c)
        cell.text = str(val)
        for para in cell.text_frame.paragraphs:
            para.font.size = Pt(9)
            para.font.name = 'Calibri'
            para.font.color.rgb = DARK_TEXT
            para.alignment = PP_ALIGN.CENTER if c > 0 else PP_ALIGN.LEFT
        # Alternate row colors
        cell.fill.solid()
        cell.fill.fore_color.rgb = VLIGHT_GRAY if r % 2 == 0 else WHITE
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE

    # Highlight gap > 50%
    if gap > 50:
        gap_cell = table.cell(r + 1, 8)
        for para in gap_cell.text_frame.paragraphs:
            para.font.color.rgb = RED
            para.font.bold = True

# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 8: Top Critical Packages
# ═══════════════════════════════════════════════════════════════════════════
slide_num += 1
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, WHITE)
add_header_bar(slide, "Critical Packages — Largest Output Gaps for Loading Increase")
add_footer(slide, slide_num)

# Top 6 critical packages as cards
critical = pkgs_with_gap[:6]
card_positions = [
    (0.3, 1.3, 4.1, 2.7),
    (4.6, 1.3, 4.1, 2.7),
    (8.9, 1.3, 4.1, 2.7),
    (0.3, 4.2, 4.1, 2.7),
    (4.6, 4.2, 4.1, 2.7),
    (8.9, 4.2, 4.1, 2.7),
]
card_colors = [RED, RED, ORANGE, ORANGE, ORANGE, PRIMARY_BLUE]

for i, (p, (left, top, w, h)) in enumerate(zip(critical, card_positions)):
    accent = card_colors[i]
    card = add_shape_box(slide, left, top, w, h, WHITE, LIGHT_GRAY)
    # Accent bar
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(w), Inches(0.08))
    bar.fill.solid()
    bar.fill.fore_color.rgb = accent
    bar.line.fill.background()
    bar.shadow.inherit = False

    add_text_box(slide, left + 0.2, top + 0.2, w - 0.4, 0.35, p['pkg'],
                 font_size=16, bold=True, color=DARK_TEXT)

    add_text_box(slide, left + 0.2, top + 0.6, 1.8, 0.25, "Output Gap",
                 font_size=10, color=MEDIUM_GRAY)
    add_text_box(slide, left + 2.0, top + 0.6, 1.8, 0.25, f"{p['gap_pct']:.0f}%",
                 font_size=14, bold=True, color=accent, align=PP_ALIGN.RIGHT)

    add_text_box(slide, left + 0.2, top + 0.95, 1.8, 0.25, "DRR Target",
                 font_size=10, color=MEDIUM_GRAY)
    add_text_box(slide, left + 2.0, top + 0.95, 1.8, 0.25, format_number(p['drr_max']),
                 font_size=12, bold=True, color=DARK_TEXT, align=PP_ALIGN.RIGHT)

    add_text_box(slide, left + 0.2, top + 1.25, 1.8, 0.25, "Current Output",
                 font_size=10, color=MEDIUM_GRAY)
    add_text_box(slide, left + 2.0, top + 1.25, 1.8, 0.25, format_number(p['cur_output']),
                 font_size=12, bold=True, color=DARK_TEXT, align=PP_ALIGN.RIGHT)

    add_text_box(slide, left + 0.2, top + 1.6, 1.8, 0.25, "MC Usage",
                 font_size=10, color=MEDIUM_GRAY)
    add_text_box(slide, left + 2.0, top + 1.6, 1.8, 0.25, f"{int(p['cur_usage'])} MCs",
                 font_size=12, bold=True, color=DARK_TEXT, align=PP_ALIGN.RIGHT)

    add_text_box(slide, left + 0.2, top + 1.95, 1.8, 0.25, "UPH Gap",
                 font_size=10, color=MEDIUM_GRAY)
    uph_gap_color = RED if p['uph_diff'] > 25 else (ORANGE if p['uph_diff'] > 0 else GREEN)
    add_text_box(slide, left + 2.0, top + 1.95, 1.8, 0.25, f"{p['uph_diff']:.0f}%",
                 font_size=12, bold=True, color=uph_gap_color, align=PP_ALIGN.RIGHT)

    # Additional machines needed
    if p['std_req'] > 0 and p['cur_usage'] > 0:
        needed = max(0, math.ceil(p['cur_da']) - int(p['cur_usage']))
        if needed > 0:
            add_text_box(slide, left + 0.2, top + 2.3, 3.6, 0.25,
                         f"Need {needed} more MCs to meet DRR",
                         font_size=10, bold=True, color=accent)

# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 9: UPH by Machine Type
# ═══════════════════════════════════════════════════════════════════════════
slide_num += 1
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, WHITE)
add_header_bar(slide, "UPH Distribution by Machine Type")
add_footer(slide, slide_num)

# Calculate avg UPH per machine type
type_stats = {}
for t, uphs in uph_by_type.items():
    type_stats[t] = {
        'avg': sum(uphs)/len(uphs),
        'min': min(uphs),
        'max': max(uphs),
        'count': len(uphs)
    }
type_sorted = sorted(type_stats.items(), key=lambda x: x[1]['avg'], reverse=True)

chart_data6 = CategoryChartData()
chart_data6.categories = [t[0] for t in type_sorted]
chart_data6.add_series('Avg UPH', [round(t[1]['avg']) for t in type_sorted])
chart_data6.add_series('Max UPH', [t[1]['max'] for t in type_sorted])

chart_frame6 = slide.shapes.add_chart(
    XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.3), Inches(1.1), Inches(8.5), Inches(5.5), chart_data6
)
chart6 = chart_frame6.chart
chart6.has_legend = True
chart6.legend.position = XL_LEGEND_POSITION.BOTTOM
chart6.legend.font.size = Pt(10)
chart6.legend.font.name = 'Calibri'
chart6.legend.include_in_layout = False

set_series_color(chart6.series[0]._element, '0E3689')
set_series_color(chart6.series[1]._element, '1D9CE4')

chart6.value_axis.tick_labels.font.size = Pt(9)
chart6.value_axis.tick_labels.font.name = 'Calibri'
chart6.category_axis.tick_labels.font.size = Pt(10)
chart6.category_axis.tick_labels.font.name = 'Calibri'
chart6.value_axis.has_title = True
chart6.value_axis.axis_title.text_frame.paragraphs[0].text = "UPH"
chart6.value_axis.axis_title.text_frame.paragraphs[0].font.size = Pt(10)

# Stats cards on right
add_text_box(slide, 9.1, 1.1, 4.0, 0.4, "Machine Type Stats", font_size=16, bold=True, color=PRIMARY_BLUE)
y = 1.6
for t_name, stats in type_sorted:
    row_bg = VLIGHT_GRAY if type_sorted.index((t_name, stats)) % 2 == 0 else WHITE
    row = add_shape_box(slide, 9.1, y, 4.0, 0.5, row_bg, LIGHT_GRAY)
    add_text_box(slide, 9.2, y + 0.02, 1.5, 0.25, t_name, font_size=10, bold=True, color=DARK_TEXT)
    add_text_box(slide, 9.2, y + 0.25, 1.2, 0.2, f"Machines: {stats['count']}", font_size=8, color=MEDIUM_GRAY)
    add_text_box(slide, 10.7, y + 0.02, 1.1, 0.25, f"Avg: {stats['avg']:,.0f}", font_size=9, color=DARK_TEXT)
    add_text_box(slide, 11.8, y + 0.02, 1.2, 0.25, f"Range: {stats['min']:,}-{stats['max']:,}",
                 font_size=9, color=DARK_GRAY, align=PP_ALIGN.RIGHT)
    y += 0.52

# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 10: Loading Scenario Analysis
# ═══════════════════════════════════════════════════════════════════════════
slide_num += 1
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, WHITE)
add_header_bar(slide, "Loading Increase Scenario — Machine Requirement Projection")
add_footer(slide, slide_num)

add_text_box(slide, 0.4, 1.15, 12.5, 0.35,
             "If loading increases to DRR MAX, what additional machines and capacity recovery are needed?",
             font_size=14, color=DARK_GRAY, font_name='Calibri Light')

# Scenario table
headers2 = ['Scenario', 'Machines Available', 'Machines Required', 'Gap', 'Output/Day', 'vs DRR Target']
col_w2 = [3.0, 2.0, 2.0, 1.5, 2.0, 2.2]
tbl_shape = slide.shapes.add_table(4, 6, Inches(0.4), Inches(1.7), Inches(12.5), Inches(2.0))
tbl = tbl_shape.table
for i, w in enumerate(col_w2):
    tbl.columns[i].width = Inches(w)

for i, h in enumerate(headers2):
    cell = tbl.cell(0, i)
    cell.text = h
    for para in cell.text_frame.paragraphs:
        para.font.size = Pt(11)
        para.font.bold = True
        para.font.color.rgb = WHITE
        para.font.name = 'Calibri'
        para.alignment = PP_ALIGN.CENTER
    cell.fill.solid()
    cell.fill.fore_color.rgb = PRIMARY_BLUE
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE

# Scenario data
scenarios = [
    ("Current State (as-is)", f"{int(total_cur_usage)}", f"{total_std_req:.0f}", f"{int(total_cur_da - total_std_req):.0f}",
     f"{total_output:,.0f}", f"{total_output/total_drr*100:.0f}%"),
    ("+ Repair 19 Shutdown MCs", f"{int(total_cur_usage) + 19}", f"{total_std_req:.0f}", f"{int(total_cur_usage) + 19 - total_std_req:.0f}",
     f"{total_output * 1.15:,.0f}", f"{total_output*1.15/total_drr*100:.0f}%"),
    ("+ Repair + UPH Optimization (17%)", f"{int(total_cur_usage) + 19}", f"{total_std_req:.0f}", f"{int(total_cur_usage) + 19 - total_std_req:.0f}",
     f"{total_output * 1.15 * 1.17:,.0f}", f"{total_output*1.15*1.17/total_drr*100:.0f}%"),
]
row_colors = [VLIGHT_GRAY, RGBColor(0xE8, 0xF5, 0xE9), RGBColor(0xE3, 0xF2, 0xFD)]
for r, (s_data, bg_color) in enumerate(zip(scenarios, row_colors)):
    for c, val in enumerate(s_data):
        cell = tbl.cell(r + 1, c)
        cell.text = val
        for para in cell.text_frame.paragraphs:
            para.font.size = Pt(11)
            para.font.name = 'Calibri'
            para.font.color.rgb = DARK_TEXT
            para.alignment = PP_ALIGN.CENTER if c > 0 else PP_ALIGN.LEFT
            if r == 2:
                para.font.bold = True
        cell.fill.solid()
        cell.fill.fore_color.rgb = bg_color
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE

# Visual: 3 scenario cards
scenarios_vis = [
    ("Scenario 1: Current", f"{total_output:,.0f}", f"{total_output/total_drr*100:.0f}% of DRR",
     "Baseline — 94 MCs in use, 16 shutdown", ORANGE),
    ("Scenario 2: + Repair MCs", f"{total_output * 1.15:,.0f}", f"{total_output*1.15/total_drr*100:.0f}% of DRR",
     "Restore 19 shutdown machines (+15% capacity)", GREEN),
    ("Scenario 3: + UPH Optimize", f"{total_output * 1.15 * 1.17:,.0f}", f"{total_output*1.15*1.17/total_drr*100:.0f}% of DRR",
     "Close 17% UPH gap on all packages", PRIMARY_BLUE),
]

for i, (title, output, target, desc, color) in enumerate(scenarios_vis):
    left = 0.4 + i * 4.3
    card = add_shape_box(slide, left, 4.1, 4.0, 2.5, WHITE, LIGHT_GRAY)
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(4.1), Inches(4.0), Inches(0.08))
    bar.fill.solid()
    bar.fill.fore_color.rgb = color
    bar.line.fill.background()
    bar.shadow.inherit = False

    add_text_box(slide, left + 0.2, 4.25, 3.6, 0.3, title, font_size=13, bold=True, color=DARK_TEXT)
    add_text_box(slide, left + 0.2, 4.6, 3.6, 0.5, f"Output: {output}", font_size=20, bold=True, color=color)
    add_text_box(slide, left + 0.2, 5.15, 3.6, 0.3, target, font_size=14, bold=True, color=DARK_GRAY)
    add_text_box(slide, left + 0.2, 5.5, 3.6, 0.5, desc, font_size=10, color=MEDIUM_GRAY)

# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 11: Recommendations & Action Plan
# ═══════════════════════════════════════════════════════════════════════════
slide_num += 1
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, WHITE)
add_header_bar(slide, "Recommendations & Action Plan")
add_footer(slide, slide_num)

# 3-column layout: Issue | Action | Expected Benefit
col_headers = ['Priority', 'Issue', 'Recommended Action', 'Expected Benefit']
col_w3 = [1.0, 3.5, 4.0, 4.0]
tbl3_shape = slide.shapes.add_table(5, 4, Inches(0.3), Inches(1.2), Inches(12.7), Inches(3.5))
tbl3 = tbl3_shape.table
for i, w in enumerate(col_w3):
    tbl3.columns[i].width = Inches(w)

for i, h in enumerate(col_headers):
    cell = tbl3.cell(0, i)
    cell.text = h
    for para in cell.text_frame.paragraphs:
        para.font.size = Pt(11)
        para.font.bold = True
        para.font.color.rgb = WHITE
        para.font.name = 'Calibri'
        para.alignment = PP_ALIGN.CENTER
    cell.fill.solid()
    cell.fill.fore_color.rgb = PRIMARY_BLUE
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE

recs = [
    ("1 — Critical", "19 machines in shutdown status\n(15 are AD889 model)",
     "Repair and restore all 19 shutdown\nmachines to production",
     "Recover ~15% capacity\nReduce machine gap significantly"),
    ("2 — High", "UPH below standard on 19 packages\n(avg 17% gap from STD UPH)",
     "Optimize machine parameters, PM schedule,\nand process settings to close UPH gap",
     "Additional ~17% throughput gain\nwithout new machine investment"),
    ("3 — High", "Insufficient operators for\nadditional machine loading",
     "Hire 13 operators per shift\n(26 total) to support increased loading",
     "Enable full utilization of restored\nand optimized machines"),
    ("4 — Medium", "Critical packages severely under target\n(28L SOIC: 82%, 100L TQFP: 79% gap)",
     "Prioritize critical package allocation\nand dedicate machines to high-gap packages",
     "Close largest output gaps first\nfor maximum DRR improvement"),
]

rec_colors = [RED, ORANGE, LIGHT_BLUE, PRIMARY_BLUE]
for r, (pri, issue, action, benefit) in enumerate(recs):
    row_bg = VLIGHT_GRAY if r % 2 == 0 else WHITE
    for c, val in enumerate([pri, issue, action, benefit]):
        cell = tbl3.cell(r + 1, c)
        cell.text = val
        for para in cell.text_frame.paragraphs:
            para.font.size = Pt(10)
            para.font.name = 'Calibri'
            para.font.color.rgb = DARK_TEXT
            para.alignment = PP_ALIGN.LEFT
            if c == 0:
                para.font.bold = True
                para.font.color.rgb = rec_colors[r]
                para.alignment = PP_ALIGN.CENTER
        cell.fill.solid()
        cell.fill.fore_color.rgb = row_bg
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE

# Roadmap section
add_text_box(slide, 0.3, 5.0, 12.7, 0.4, "Implementation Roadmap", font_size=18, bold=True, color=PRIMARY_BLUE)

phases = [
    ("Phase 1: Immediate (0-30 days)", "Repair shutdown MCs, prioritize AD889 restoration", RED),
    ("Phase 2: Short-term (30-60 days)", "UPH optimization program, hire operators, process tuning", ORANGE),
    ("Phase 3: Medium-term (60-90 days)", "Full loading ramp-up, monitor output vs DRR targets", GREEN),
]

for i, (phase, desc, color) in enumerate(phases):
    left = 0.3 + i * 4.3
    phase_box = add_shape_box(slide, left, 5.5, 4.1, 1.3, WHITE, LIGHT_GRAY)
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(5.5), Inches(4.1), Inches(0.06))
    bar.fill.solid()
    bar.fill.fore_color.rgb = color
    bar.line.fill.background()
    bar.shadow.inherit = False
    add_text_box(slide, left + 0.15, 5.6, 3.8, 0.35, phase, font_size=12, bold=True, color=color)
    add_text_box(slide, left + 0.15, 5.95, 3.8, 0.7, desc, font_size=10, color=DARK_GRAY)

# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 12: Closing / Next Steps
# ═══════════════════════════════════════════════════════════════════════════
slide_num += 1
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, WHITE)
add_header_bar(slide, "Summary & Next Steps")
add_footer(slide, slide_num)

# Key conclusions
add_text_box(slide, 0.5, 1.2, 12.3, 0.4, "Key Conclusions", font_size=20, bold=True, color=PRIMARY_BLUE)

conclusions = [
    f"Die Attach section has {total_db} machines — {status_cnt.get('Run',0)} running, {status_cnt.get('Machine Shutdown',0)} in shutdown, {status_cnt.get('Automotive',0)} dedicated to Automotive",
    f"Current daily output ({total_output:,.0f} units) is {gap_pct:.0f}% below DRR target ({total_drr:,.0f} units)",
    f"19 shutdown machines (mainly AD889) represent immediate recovery opportunity",
    f"17% average UPH gap across 19 packages — significant throughput gain without CAPEX",
    f"Most critical gaps: 28L SOIC (82%), 100L TQFP (79%), 80L TQFP (52%), QFN (51%)",
]
y = 1.75
for c in conclusions:
    ind = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.7), Inches(y + 0.07), Inches(0.12), Inches(0.12))
    ind.fill.solid()
    ind.fill.fore_color.rgb = PRIMARY_BLUE
    ind.line.fill.background()
    ind.shadow.inherit = False
    add_text_box(slide, 1.0, y, 11.8, 0.35, c, font_size=13, color=DARK_TEXT)
    y += 0.42

# Divider line
divider = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(3.95), Inches(12.3), Inches(0.02))
divider.fill.solid()
divider.fill.fore_color.rgb = LIGHT_GRAY
divider.line.fill.background()
divider.shadow.inherit = False

# Next steps
add_text_box(slide, 0.5, 4.1, 12.3, 0.4, "Next Steps", font_size=20, bold=True, color=PRIMARY_BLUE)

next_steps = [
    ("Approve repair budget for 19 shutdown machines (priority: AD889 x15)", "Management", RED),
    ("Initiate UPH optimization project across 19 packages", "Engineering", ORANGE),
    ("Submit headcount request: 13 operators/shift x 2 shifts = 26 persons", "HR / Production", LIGHT_BLUE),
    ("Set up weekly output tracking dashboard vs DRR targets", "Production Planning", GREEN),
    ("Dedicate machine allocation for critical gap packages", "Production", PRIMARY_BLUE),
]
y = 4.6
for step, owner, color in next_steps:
    ind = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.7), Inches(y + 0.04), Inches(0.15), Inches(0.2))
    ind.fill.solid()
    ind.fill.fore_color.rgb = color
    ind.line.fill.background()
    ind.shadow.inherit = False
    add_text_box(slide, 1.05, y, 9.5, 0.35, step, font_size=12, color=DARK_TEXT)
    # Owner badge
    badge = add_shape_box(slide, 10.8, y, 2.0, 0.3, VLIGHT_GRAY, LIGHT_GRAY)
    add_text_box(slide, 10.8, y, 2.0, 0.3, owner, font_size=9, bold=True, color=color, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    y += 0.42

# Q&A
add_text_box(slide, 0.5, 6.6, 12.3, 0.35,
             "Questions & Discussion",
             font_size=16, bold=True, color=MEDIUM_GRAY, align=PP_ALIGN.CENTER)

# ═══════════════════════════════════════════════════════════════════════════
# Save
# ═══════════════════════════════════════════════════════════════════════════
output_path = os.path.join(OUTPUT_DIR, 'DA_Machine_Loading_Analysis.pptx')
prs.save(output_path)
print(f"Presentation saved to: {output_path}")
print(f"Total slides: {len(prs.slides)}")
