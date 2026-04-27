#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate Industrial Command theme preview page for theme-showcase.pdf.
Matches the exact layout of existing pages (Ocean Depths reference, page 1).
Uses fpdf2 for PDF generation and pypdf for merging.
"""

import sys
import os
from fpdf import FPDF
from pypdf import PdfReader, PdfWriter


# ── helpers ──────────────────────────────────────────────────────────────────

def hex_to_rgb(hex_color):
    """Convert #RRGGBB to (r, g, b) tuple."""
    h = hex_color.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


# ── layout constants (points; A4 = 612 x 792 pt = 210 x 297 mm) ─────────────
# fpdf2 works in mm by default. A4: 210 x 297 mm.

PAGE_W = 210   # mm
PAGE_H = 297   # mm

# Theme colors
BG_COLOR        = "#F0F2F5"   # page background
HEADING_COLOR   = "#1A1F2E"   # dark text
ACCENT_COLOR    = "#0E3689"   # Command Blue
TAGLINE_COLOR   = "#0E3689"
FOOTER_COLOR    = "#4A5568"
DIVIDER_COLOR   = "#C8CDD6"

# Swatches
SWATCHES = [
    ("Command Blue",  "#0E3689"),
    ("Signal Green",  "#2E9E4F"),
    ("Alert Orange",  "#E07B00"),
    ("Critical Red",  "#C0392B"),
]


def build_preview_page(output_path):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(False)
    pdf.add_page()

    # ── Background ──────────────────────────────────────────────────────────
    bg = hex_to_rgb(BG_COLOR)
    pdf.set_fill_color(*bg)
    pdf.rect(0, 0, PAGE_W, PAGE_H, style='F')

    # ── Top accent bar (Command Blue, 6 mm tall) ─────────────────────────────
    accent = hex_to_rgb(ACCENT_COLOR)
    pdf.set_fill_color(*accent)
    pdf.rect(0, 0, PAGE_W, 6, style='F')

    # ── Theme name ───────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(*hex_to_rgb(HEADING_COLOR))
    pdf.set_xy(18, 16)
    pdf.cell(0, 10, "Industrial Command", ln=True)

    # ── Tagline ──────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "", 13)
    pdf.set_text_color(*hex_to_rgb(TAGLINE_COLOR))
    pdf.set_xy(18, 28)
    pdf.cell(0, 7, "Professional manufacturing & operations dashboard theme", ln=True)

    # ── Thin horizontal divider under header ─────────────────────────────────
    pdf.set_draw_color(*hex_to_rgb(DIVIDER_COLOR))
    pdf.set_line_width(0.3)
    pdf.line(18, 38, PAGE_W - 18, 38)

    # ── COLOR PALETTE section label ──────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*hex_to_rgb(HEADING_COLOR))
    pdf.set_xy(18, 42)
    pdf.cell(0, 5, "COLOR PALETTE", ln=True)

    # ── Color swatches (4 swatches in a row) ─────────────────────────────────
    swatch_y     = 50       # top of swatch rectangle
    swatch_h     = 24       # rectangle height
    swatch_w     = 38       # rectangle width
    swatch_gap   = 5        # gap between swatches
    swatch_start = 18       # left margin

    for i, (name, hex_val) in enumerate(SWATCHES):
        x = swatch_start + i * (swatch_w + swatch_gap)

        # Colored rectangle
        pdf.set_fill_color(*hex_to_rgb(hex_val))
        pdf.set_draw_color(*hex_to_rgb(hex_val))
        pdf.set_line_width(0)
        pdf.rect(x, swatch_y, swatch_w, swatch_h, style='F')

        # Small white label overlay at bottom of swatch
        label_h = 8
        pdf.set_fill_color(255, 255, 255)
        pdf.rect(x, swatch_y + swatch_h - label_h, swatch_w, label_h, style='F')

        # Hex code inside white strip
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*hex_to_rgb(HEADING_COLOR))
        pdf.set_xy(x, swatch_y + swatch_h - label_h + 0.5)
        pdf.cell(swatch_w, label_h - 1, hex_val.upper(), align='C')

        # Color name below swatch
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*hex_to_rgb(HEADING_COLOR))
        pdf.set_xy(x, swatch_y + swatch_h + 2)
        pdf.cell(swatch_w, 5, name, align='C')

    # ── Thin divider ─────────────────────────────────────────────────────────
    divider_y = swatch_y + swatch_h + 11
    pdf.set_draw_color(*hex_to_rgb(DIVIDER_COLOR))
    pdf.set_line_width(0.3)
    pdf.line(18, divider_y, PAGE_W - 18, divider_y)

    # ── TYPOGRAPHY section ───────────────────────────────────────────────────
    typo_y = divider_y + 5
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*hex_to_rgb(HEADING_COLOR))
    pdf.set_xy(18, typo_y)
    pdf.cell(0, 5, "TYPOGRAPHY", ln=True)

    # Two-column layout: Headers | Body Text
    col_left  = 18
    col_right = 110
    col_w     = 85

    # Left column — Headers
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*hex_to_rgb(FOOTER_COLOR))
    pdf.set_xy(col_left, typo_y + 8)
    pdf.cell(col_w, 5, "Headers:", ln=False)

    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*hex_to_rgb(HEADING_COLOR))
    pdf.set_xy(col_left + 22, typo_y + 8)
    pdf.cell(0, 5, "DejaVu Sans Bold", ln=True)

    # Sample header text
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*hex_to_rgb(HEADING_COLOR))
    pdf.set_xy(col_left, typo_y + 15)
    pdf.cell(col_w, 8, "Sample Header Text", ln=True)

    # Right column — Body Text
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*hex_to_rgb(FOOTER_COLOR))
    pdf.set_xy(col_right, typo_y + 8)
    pdf.cell(col_w, 5, "Body Text:", ln=False)

    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*hex_to_rgb(HEADING_COLOR))
    pdf.set_xy(col_right + 25, typo_y + 8)
    pdf.cell(0, 5, "DejaVu Sans", ln=True)

    # Sample body text
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*hex_to_rgb(FOOTER_COLOR))
    pdf.set_xy(col_right, typo_y + 15)
    pdf.multi_cell(
        col_w, 4.5,
        "This is sample body text showing how your content will appear in "
        "presentations. The typography pairs perfectly with the color palette "
        "for a cohesive design.",
        align='L'
    )

    # ── Thin divider ─────────────────────────────────────────────────────────
    divider2_y = typo_y + 38
    pdf.set_draw_color(*hex_to_rgb(DIVIDER_COLOR))
    pdf.set_line_width(0.3)
    pdf.line(18, divider2_y, PAGE_W - 18, divider2_y)

    # ── STATUS COLORS section ────────────────────────────────────────────────
    # (Extra section unique to Industrial Command — showcases semantic colors)
    status_y = divider2_y + 5
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*hex_to_rgb(HEADING_COLOR))
    pdf.set_xy(18, status_y)
    pdf.cell(0, 5, "STATUS COLOR SYSTEM", ln=True)

    status_items = [
        ("Running / Good",     "#2E9E4F"),
        ("Warning / Lost Time","#E07B00"),
        ("Down / Critical",    "#C0392B"),
        ("PM / Planned",       "#6B3FA0"),
    ]

    bar_x     = 18
    bar_y     = status_y + 7
    bar_h     = 6
    bar_gap   = 4
    bar_label_w = 42

    for idx, (label, color) in enumerate(status_items):
        y = bar_y + idx * (bar_h + bar_gap)
        # Colored pill / bar
        r, g, b = hex_to_rgb(color)
        pdf.set_fill_color(r, g, b)
        pdf.rect(bar_x, y, 10, bar_h, style='F')
        # Label
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*hex_to_rgb(HEADING_COLOR))
        pdf.set_xy(bar_x + 12, y + 0.5)
        pdf.cell(bar_label_w, bar_h, label, align='L')

    # Right side: extended swatches for Control Purple and Data Blue
    extra_items = [
        ("Control Purple", "#6B3FA0"),
        ("Data Blue",      "#1D9CE4"),
    ]
    extra_x = 110
    for idx, (name, color) in enumerate(extra_items):
        y = bar_y + idx * (bar_h + bar_gap)
        pdf.set_fill_color(*hex_to_rgb(color))
        pdf.rect(extra_x, y, 10, bar_h, style='F')
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*hex_to_rgb(HEADING_COLOR))
        pdf.set_xy(extra_x + 12, y + 0.5)
        pdf.cell(50, bar_h, name, align='L')

    # ── Thin divider ─────────────────────────────────────────────────────────
    divider3_y = bar_y + len(status_items) * (bar_h + bar_gap) + 3
    pdf.set_draw_color(*hex_to_rgb(DIVIDER_COLOR))
    pdf.set_line_width(0.3)
    pdf.line(18, divider3_y, PAGE_W - 18, divider3_y)

    # ── BEST FOR section ──────────────────────────────────────────────────────
    bestfor_y = divider3_y + 5
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*hex_to_rgb(HEADING_COLOR))
    pdf.set_xy(18, bestfor_y)
    pdf.cell(22, 5, "Best for: ", ln=False)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*hex_to_rgb(FOOTER_COLOR))
    pdf.set_xy(40, bestfor_y)
    pdf.multi_cell(
        PAGE_W - 40 - 18, 5,
        "Manufacturing dashboards, OEE reporting, machine status monitoring, "
        "industrial operations",
        align='L'
    )

    # ── Page number (bottom right) ────────────────────────────────────────────
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*hex_to_rgb(FOOTER_COLOR))
    pdf.set_xy(0, PAGE_H - 12)
    pdf.cell(PAGE_W - 18, 6, "11 of 11", align='R')

    # ── Bottom accent bar ─────────────────────────────────────────────────────
    pdf.set_fill_color(*hex_to_rgb(ACCENT_COLOR))
    pdf.rect(0, PAGE_H - 4, PAGE_W, 4, style='F')

    pdf.output(output_path)
    print(f"Preview page written: {output_path}")


def merge_pdfs(source1, source2, output_path):
    """Merge source1 (all pages) + source2 (all pages) into output_path."""
    writer = PdfWriter()

    # Add all pages from source1
    reader1 = PdfReader(source1)
    for page in reader1.pages:
        writer.add_page(page)

    # Add all pages from source2
    reader2 = PdfReader(source2)
    for page in reader2.pages:
        writer.add_page(page)

    with open(output_path, "wb") as f:
        writer.write(f)

    print(f"Merged PDF written: {output_path}  ({len(reader1.pages) + len(reader2.pages)} pages)")


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    base = "d:/claude/Project/.claude/skills/theme-factory"
    preview_path  = f"{base}/industrial-command-preview.pdf"
    showcase_path = f"{base}/theme-showcase.pdf"
    temp_showcase = f"{base}/theme-showcase-merged.pdf"

    # Step 1: Generate the preview page
    build_preview_page(preview_path)

    # Step 2: Merge existing showcase (pages 1-10) + new preview
    merge_pdfs(showcase_path, preview_path, temp_showcase)

    # Step 3: Replace original showcase with merged version
    import shutil
    shutil.move(temp_showcase, showcase_path)
    print(f"Showcase updated: {showcase_path}")
