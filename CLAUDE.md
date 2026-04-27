# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This project generates professional PowerPoint presentations from Excel data files using Python. It is used for manufacturing machine status reports (Die Attach, SAW, Wire Bond) and headcount/resource planning at a semiconductor facility. The output is Microchip-inspired corporate-style slide decks with charts, KPI cards, and data tables.

## Running Scripts

```bash
python create_ppt.py                          # Main report (reads from project root xlsx)
python raw/generate_da_status_ppt.py          # Die Attach turn-on status
python raw/generate_headcount_wave3_ppt.py    # Headcount Wave3 report
python raw/generate_wb_turnon_mc_status_ppt.py # Wire Bond turn-on status
```

Each script is standalone — it reads an Excel file, processes the data, and writes a `.pptx` to `Output/`.

## Dependencies

- `python-pptx` — PowerPoint generation (Presentation, charts, shapes, text)
- `openpyxl` — Excel reading (`.xlsx` files with `data_only=True`)
- `lxml` — XML manipulation for chart color customization via `pptx.oxml.ns.qn`

## Architecture

**Each script follows the same pattern:**
1. Load Excel workbook with `openpyxl`, parse specific sheets/row ranges into dicts
2. Compute statistics using `collections.Counter`
3. Build a widescreen presentation (13.333 x 7.5 inches) using blank layout (`slide_layouts[6]`)
4. Add slides: Title → Executive Summary → Data Visualizations → Detail Tables → Recommendations
5. Save to `Output/`

**Key helpers defined in each script (not shared):**
- `add_bg()` — solid background fill on a slide
- `add_text_box()` — positioned text box with font/color/alignment
- `add_shape_box()` — rounded rectangle shape fill
- `add_kpi_card()` — colored top-bar card with large value + label

**Chart colors are set via raw XML** (`lxml.etree.SubElement` + `qn()`) because python-pptx does not expose per-point/series color natively.

## Style Guide

All presentations follow `.claude/skills/file-to-ppt/presentation-style.md`:
- Color palette: Dark Blue `#1B3A5C`, Medium Blue `#2E75B6`, Green `#2D8E4E`, Red `#C0392B`, Orange `#E67E22`
- Header bar: full-width dark blue rectangle at slide top (0.9" tall)
- KPI cards: white rounded rectangle with colored top accent bar
- Font sizes: Title 44pt, Section headers 28pt, Body 12-14pt
- All text uses absolute positioning with `Inches()` — no automatic layouts

## Data Sources

Excel files live in `raw/` (working data) or project root. Each script hardcodes its input path. Data contains Thai text (เสีย = broken, ปกติ = normal) — scripts must use UTF-8 encoding (`sys.stdout` wrapper at top of each file).

## Output

Generated `.pptx` files go to `Output/`. These are gitignored artifacts — regenerate by running the corresponding script.
