const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3" x 7.5"

// ─── Palette ───────────────────────────────────────────────────────────────
const C = {
  navy:      "1B3A5C",
  blue:      "2E75B6",
  lightBlue: "EBF3FB",
  green:     "2D8E4E",
  red:       "C0392B",
  orange:    "E67E22",
  white:     "FFFFFF",
  offwhite:  "F4F7FB",
  text:      "1A1A2E",
  muted:     "64748B",
  border:    "D1DDEF",
};

// ─── Helpers ────────────────────────────────────────────────────────────────
const W = 13.3, H = 7.5;

function hdr(slide, title, subtitle) {
  // Header bar
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: W, h: 1.0,
    fill: { color: C.navy }, line: { color: C.navy }
  });
  // Title in header
  slide.addText(title, {
    x: 0.45, y: 0, w: subtitle ? 9 : 12.8, h: 1.0,
    fontSize: 24, bold: true, color: C.white,
    fontFace: "Calibri", valign: "middle", margin: 0
  });
  if (subtitle) {
    slide.addText(subtitle, {
      x: 9.5, y: 0, w: 3.5, h: 1.0,
      fontSize: 12, color: "BDD7EE",
      fontFace: "Calibri", valign: "middle", align: "right", margin: 0
    });
  }
  // Slide background
  slide.background = { color: C.offwhite };
}

function footer(slide, pageNum, total) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: H - 0.32, w: W, h: 0.32,
    fill: { color: C.navy }, line: { color: C.navy }
  });
  slide.addText("CONFIDENTIAL – For Management Review Only", {
    x: 0.3, y: H - 0.32, w: 9, h: 0.32,
    fontSize: 9, color: "BDD7EE", fontFace: "Calibri", valign: "middle", margin: 0
  });
  slide.addText(`${pageNum} / ${total}`, {
    x: W - 1.2, y: H - 0.32, w: 1.0, h: 0.32,
    fontSize: 9, color: C.white, fontFace: "Calibri",
    valign: "middle", align: "right", margin: 0
  });
}

function kpiCard(slide, x, y, w, h, value, label, accent, valueColor) {
  // Card shadow
  slide.addShape(pres.shapes.RECTANGLE, {
    x: x + 0.04, y: y + 0.04, w, h,
    fill: { color: "D1DDEF", transparency: 50 }, line: { color: "D1DDEF", transparency: 50 }
  });
  // Card body
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h,
    fill: { color: C.white }, line: { color: C.border, width: 1 }
  });
  // Top accent bar
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h: 0.07,
    fill: { color: accent }, line: { color: accent }
  });
  slide.addText(value, {
    x, y: y + 0.07, w, h: h * 0.58,
    fontSize: 32, bold: true, color: valueColor || C.navy,
    fontFace: "Calibri", align: "center", valign: "middle", margin: 0
  });
  slide.addText(label, {
    x, y: y + h * 0.62, w, h: h * 0.35,
    fontSize: 11, color: C.muted,
    fontFace: "Calibri", align: "center", valign: "top", margin: 0
  });
}

function statusDot(slide, x, y, color) {
  slide.addShape(pres.shapes.OVAL, {
    x, y, w: 0.14, h: 0.14,
    fill: { color }, line: { color }
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 1 – TITLE
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: C.navy };

  // Decorative angled stripe
  s.addShape(pres.shapes.RECTANGLE, {
    x: -0.5, y: 3.5, w: 14.5, h: 0.08,
    fill: { color: C.blue, transparency: 40 }, line: { color: C.blue, transparency: 40 }
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: -0.5, y: 3.65, w: 14.5, h: 0.04,
    fill: { color: C.orange }, line: { color: C.orange }
  });

  // Title
  s.addText("Machine Status Summary", {
    x: 1.0, y: 1.4, w: 11.3, h: 1.4,
    fontSize: 44, bold: true, color: C.white,
    fontFace: "Calibri", align: "center", valign: "middle"
  });

  // Subtitle
  s.addText("Equipment Turn-On Status Report", {
    x: 1.0, y: 2.85, w: 11.3, h: 0.6,
    fontSize: 22, color: "BDD7EE",
    fontFace: "Calibri", align: "center", valign: "middle"
  });

  // Meta info row
  const metas = [
    { label: "Date", value: "April 2026" },
    { label: "Scope", value: "SAW / Die Attach / Wire Bond" },
    { label: "Audience", value: "Top Management" },
  ];
  metas.forEach((m, i) => {
    const bx = 1.5 + i * 3.5;
    s.addShape(pres.shapes.RECTANGLE, {
      x: bx, y: 4.15, w: 3.0, h: 0.9,
      fill: { color: C.blue, transparency: 30 }, line: { color: C.blue }
    });
    s.addText([
      { text: m.label + "\n", options: { fontSize: 10, color: "BDD7EE", breakLine: true } },
      { text: m.value, options: { fontSize: 13, bold: true, color: C.white } }
    ], {
      x: bx, y: 4.15, w: 3.0, h: 0.9,
      align: "center", valign: "middle", fontFace: "Calibri"
    });
  });

  // Microchip-style brand mark
  s.addText("MICROCHIP TECHNOLOGY", {
    x: 0, y: H - 0.55, w: W, h: 0.45,
    fontSize: 11, color: "BDD7EE", fontFace: "Calibri",
    align: "center", valign: "middle", charSpacing: 4
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 2 – EXECUTIVE SUMMARY (KPI Overview)
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  hdr(s, "Executive Summary", "Overall Machine Fleet Status");
  footer(s, 2, 7);

  // ── KPI cards: business-impact focused ───────────────────────────────────
  const kpis = [
    { val: "6,200K",  lbl: "Min Capacity Now\n(SAW Bottleneck)",       accent: C.red,    vc: C.red    },
    { val: "42",      lbl: "Units Still Offline\n(Pending Turn-On)",    accent: C.orange, vc: C.orange },
    { val: "76%",     lbl: "Turn-On Progress\n(132 of 174 units)",      accent: C.blue               },
    { val: "Jun '26", lbl: "Full Recovery\nTarget Month",               accent: C.green              },
  ];
  kpis.forEach((k, i) => {
    kpiCard(s, 0.35 + i * 3.1, 1.15, 2.9, 1.4, k.val, k.lbl, k.accent, k.vc);
  });

  // ── 3-month recovery progress table ──────────────────────────────────────
  // Columns: Process | Before MC | Current MC | Cap(K) Now | Apr'26 | May'26 | Jun'26
  // Apr/May/Jun cells show "XX MC / X,XXXK"
  const tY = 2.75;

  // [process, beforeMC, currentMC, capNow, apr(mc/cap), may(mc/cap), jun(mc/cap), changed]
  const rows = [
    ["BG",          "2",   "2",   "8,500", "—",              "—",              "—",              false],
    ["SAW Wafer",   "51",  "35",  "6,200", "41 / 7,700K",    "44 / 7,900K",    "44 / 7,900K",    true ],
    ["Die Attach",  "113", "88",  "6,500", "98 / 7,200K",    "107 / 7,900K",   "107 / 7,900K",   true ],
    ["Wire Bond",   "686", "553", "6,900", "669 / 8,200K",   "669 / 8,200K",   "686 / 8,500K",   true ],
    ["Mold",        "24",  "24",  "8,500", "—",              "—",              "—",              false],
    ["Plating",     "3",   "3",   "8,500", "—",              "—",              "—",              false],
    ["Laser Mark",  "18",  "16",  "8,000", "18 / 8,500K",    "—",              "—",              true ],
    ["Trim & Form", "70",  "67",  "8,000", "70 / 8,500K",    "—",              "—",              true ],
    ["Saw QFN",     "39",  "39",  "8,500", "—",              "—",              "—",              false],
  ];

  const hdrOpt = (t) => ({
    text: t,
    options: { bold: true, fill: { color: C.navy }, color: C.white, align: "center", valign: "middle" }
  });

  const tableData = [
    [
      hdrOpt("Process"),
      hdrOpt("Before\n(MC)"),
      hdrOpt("Current\n(MC)"),
      hdrOpt("Cap Now\n(K)"),
      hdrOpt("Apr '26\nMC / Cap(K)"),
      hdrOpt("May '26\nMC / Cap(K)"),
      hdrOpt("Jun '26\nMC / Cap(K)"),
    ],
    ...rows.map((r, idx) => {
      const bg = idx % 2 === 0 ? "F4F7FB" : C.white;
      const isOK = !r[7];
      const capColor = r[3] === "8,500" ? C.green : C.red;
      const monthColor = (v) => (v === "—" ? C.muted : C.green);
      return [
        { text: r[0], options: { fill: { color: bg }, align: "left",   bold: true,  valign: "middle" } },
        { text: r[1], options: { fill: { color: bg }, align: "center", valign: "middle" } },
        { text: r[2], options: { fill: { color: bg }, align: "center", bold: true,  color: isOK ? C.green : C.navy, valign: "middle" } },
        { text: r[3], options: { fill: { color: bg }, align: "center", bold: true,  color: capColor, valign: "middle" } },
        { text: r[4], options: { fill: { color: bg }, align: "center", fontSize: 10, color: monthColor(r[4]), valign: "middle" } },
        { text: r[5], options: { fill: { color: bg }, align: "center", fontSize: 10, color: monthColor(r[5]), valign: "middle" } },
        { text: r[6], options: { fill: { color: bg }, align: "center", fontSize: 10, color: monthColor(r[6]), bold: r[7], valign: "middle" } },
      ];
    }),
  ];

  s.addTable(tableData, {
    x: 0.35, y: tY, w: 12.6, h: 4.1,
    fontFace: "Calibri", fontSize: 11,
    border: { pt: 0.5, color: C.border },
    rowH: 0.37,
    colW: [1.9, 1.2, 1.2, 1.2, 2.3, 2.3, 2.5],
  });

  // Legend
  s.addText("● Green = Recovered / On Track   Red Cap = Below 8,500K target", {
    x: 0.35, y: 6.92, w: 7.5, h: 0.2,
    fontSize: 8.5, color: C.muted, fontFace: "Calibri", align: "left"
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 3 – CAPACITY RECOVERY ROADMAP
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  hdr(s, "Capacity Recovery Roadmap", "SAW · Die Attach · Wire Bond  |  K units/month");
  footer(s, 3, 7);

  const chartData = [
    {
      name: "SAW Wafer",
      labels: ["Before", "Current", "Apr'26", "May'26", "Jun'26"],
      values: [8500, 6200, 7700, 7900, 7900],
    },
    {
      name: "Die Attach",
      labels: ["Before", "Current", "Apr'26", "May'26", "Jun'26"],
      values: [8500, 6500, 7200, 7900, 7900],
    },
    {
      name: "Wire Bond",
      labels: ["Before", "Current", "Apr'26", "May'26", "Jun'26"],
      values: [8500, 6900, 8200, 8200, 8500],
    },
  ];

  s.addChart(pres.charts.LINE, chartData, {
    x: 0.4, y: 1.15, w: 12.5, h: 5.6,
    chartColors: [C.orange, C.green, C.blue],
    lineSize: 3,
    lineSmooth: false,
    showValue: true,
    dataLabelPosition: "t",
    dataLabelColor: C.text,
    dataLabelFontSize: 10,
    dataLabelFontBold: true,
    dataLabelFontFace: "Calibri",
    showLegend: true,
    legendPos: "b",
    legendFontSize: 11,
    legendFontFace: "Calibri",
    catAxisLabelColor: C.muted,
    valAxisLabelColor: C.muted,
    catAxisLabelFontFace: "Calibri",
    valAxisLabelFontFace: "Calibri",
    catAxisLabelFontSize: 12,
    valAxisLabelFontSize: 10,
    valAxisMinVal: 5000,
    valAxisMaxVal: 9000,
    valGridLine: { color: "E2E8F0", size: 0.5 },
    catGridLine: { style: "none" },
    chartArea: { fill: { color: C.offwhite }, roundedCorners: false },
    plotArea: { fill: { color: C.offwhite } },
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 4 – SAW STATUS
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  hdr(s, "SAW Machine Status", "Before: 51 MC  →  Current: 35 MC");
  footer(s, 4, 7);

  // KPI mini cards
  const sawKPIs = [
    { val: "51",  lbl: "Total Before", accent: C.blue },
    { val: "35",  lbl: "Current Active", accent: C.green },
    { val: "16",  lbl: "Shutdown\n(7500 PLUS)", accent: C.red, vc: C.red },
    { val: "6",   lbl: "Turned On\n(of 16)", accent: C.orange },
    { val: "10",  lbl: "Remaining\n(No Spare Parts)", accent: C.red, vc: C.red },
  ];
  sawKPIs.forEach((k, i) => {
    kpiCard(s, 0.35 + i * 2.52, 1.15, 2.35, 1.3, k.val, k.lbl, k.accent, k.vc);
  });

  // Detail table
  const sawRows = [
    ["7500 PLUS",    "16",  "0",   C.red,   "Shutdown ADT Saw#01–16\n10 M/C down – no SAS spare parts"],
    ["AD2000T",      "7",   "7",   C.green, ""],
    ["AD3000T",      "12",  "12",  C.green, ""],
    ["AD3000T Plus", "1",   "1",   C.green, ""],
    ["DFD6340",      "9",   "9",   C.green, ""],
    ["DFD6361",      "1",   "1",   C.green, ""],
    ["DFD6560",      "5",   "5",   C.green, ""],
  ];

  const sawTable = [
    [
      { text: "Model",    options: { bold: true, fill: { color: C.navy }, color: C.white, align: "center" } },
      { text: "Before",   options: { bold: true, fill: { color: C.navy }, color: C.white, align: "center" } },
      { text: "Current",  options: { bold: true, fill: { color: C.navy }, color: C.white, align: "center" } },
      { text: "Δ",        options: { bold: true, fill: { color: C.navy }, color: C.white, align: "center" } },
      { text: "Status",   options: { bold: true, fill: { color: C.navy }, color: C.white, align: "center" } },
      { text: "Remark",   options: { bold: true, fill: { color: C.navy }, color: C.white, align: "left" } },
    ],
    ...sawRows.map((r, idx) => {
      const bg = idx % 2 === 0 ? "F4F7FB" : C.white;
      const delta = parseInt(r[2]) - parseInt(r[1]);
      const deltaStr = delta === 0 ? "—" : delta.toString();
      return [
        { text: r[0], options: { fill: { color: bg }, align: "left",   bold: true } },
        { text: r[1], options: { fill: { color: bg }, align: "center" } },
        { text: r[2], options: { fill: { color: bg }, align: "center", bold: true, color: r[3] } },
        { text: deltaStr, options: { fill: { color: bg }, align: "center", color: delta < 0 ? C.red : C.muted } },
        { text: parseInt(r[2]) === parseInt(r[1]) ? "OK" : (parseInt(r[2]) === 0 ? "OFF" : "PARTIAL"),
          options: { fill: { color: bg }, align: "center", bold: true, color: r[3] } },
        { text: r[4], options: { fill: { color: bg }, align: "left",   fontSize: 10, color: C.muted } },
      ];
    }),
    // Total row
    [
      { text: "TOTAL", options: { bold: true, fill: { color: C.lightBlue }, color: C.navy, align: "center" } },
      { text: "51",    options: { bold: true, fill: { color: C.lightBlue }, color: C.navy, align: "center" } },
      { text: "35",    options: { bold: true, fill: { color: C.lightBlue }, color: C.navy, align: "center" } },
      { text: "-16",   options: { bold: true, fill: { color: C.lightBlue }, color: C.red,  align: "center" } },
      { text: "",      options: { fill: { color: C.lightBlue } } },
      { text: "Turn-on completed: Saw#02,03,05,07,09,11 (6 M/C)",
        options: { bold: true, fill: { color: C.lightBlue }, color: C.navy, align: "left", fontSize: 10 } },
    ],
  ];

  s.addTable(sawTable, {
    x: 0.35, y: 2.6, w: 12.6, h: 4.38,
    fontFace: "Calibri", fontSize: 12,
    border: { pt: 0.5, color: C.border },
    rowH: 0.48,
    colW: [2.4, 1.3, 1.3, 0.9, 1.3, 5.4],
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 5 – DIE ATTACH STATUS
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  hdr(s, "Die Attach Machine Status", "Before: 113 MC  →  Current: 88 MC");
  footer(s, 5, 7);

  const daKPIs = [
    { val: "113", lbl: "Total Before",    accent: C.blue },
    { val: "88",  lbl: "Current Active",  accent: C.green },
    { val: "25",  lbl: "Shutdown\n(AD889)", accent: C.red, vc: C.red },
    { val: "10",  lbl: "Turned On",       accent: C.orange },
    { val: "38",  lbl: "Tech H/C\n(was 40)", accent: C.muted },
  ];
  daKPIs.forEach((k, i) => {
    kpiCard(s, 0.35 + i * 2.52, 1.15, 2.35, 1.3, k.val, k.lbl, k.accent, k.vc);
  });

  const daRows = [
    ["AD828",      "5",  "5",  C.green, ""],
    ["AD830",      "15", "15", C.green, ""],
    ["AD8312",     "10", "10", C.green, ""],
    ["AD8312Plus", "8",  "8",  C.green, ""],
    ["AD832i",     "13", "13", C.green, ""],
    ["AD838",      "13", "13", C.green, ""],
    ["AD889",      "25", "0",  C.red,   "Shutdown 25 M/C"],
    ["AD8912HS",   "1",  "1",  C.green, ""],
    ["AD898",      "23", "23", C.green, ""],
  ];

  const daTable = [
    [
      { text: "Model",   options: { bold: true, fill: { color: C.navy }, color: C.white, align: "center" } },
      { text: "Before",  options: { bold: true, fill: { color: C.navy }, color: C.white, align: "center" } },
      { text: "Current", options: { bold: true, fill: { color: C.navy }, color: C.white, align: "center" } },
      { text: "Δ",       options: { bold: true, fill: { color: C.navy }, color: C.white, align: "center" } },
      { text: "Status",  options: { bold: true, fill: { color: C.navy }, color: C.white, align: "center" } },
      { text: "Remark",  options: { bold: true, fill: { color: C.navy }, color: C.white, align: "left" } },
    ],
    ...daRows.map((r, idx) => {
      const bg = idx % 2 === 0 ? "F4F7FB" : C.white;
      const delta = parseInt(r[2]) - parseInt(r[1]);
      const deltaStr = delta === 0 ? "—" : delta.toString();
      return [
        { text: r[0], options: { fill: { color: bg }, align: "left", bold: true } },
        { text: r[1], options: { fill: { color: bg }, align: "center" } },
        { text: r[2], options: { fill: { color: bg }, align: "center", bold: true, color: r[3] } },
        { text: deltaStr, options: { fill: { color: bg }, align: "center", color: delta < 0 ? C.red : C.muted } },
        { text: parseInt(r[2]) === parseInt(r[1]) ? "OK" : "OFF",
          options: { fill: { color: bg }, align: "center", bold: true, color: r[3] } },
        { text: r[4], options: { fill: { color: bg }, align: "left", fontSize: 10, color: C.muted } },
      ];
    }),
    [
      { text: "TOTAL", options: { bold: true, fill: { color: C.lightBlue }, color: C.navy, align: "center" } },
      { text: "113",   options: { bold: true, fill: { color: C.lightBlue }, color: C.navy, align: "center" } },
      { text: "88",    options: { bold: true, fill: { color: C.lightBlue }, color: C.navy, align: "center" } },
      { text: "-25",   options: { bold: true, fill: { color: C.lightBlue }, color: C.red,  align: "center" } },
      { text: "",      options: { fill: { color: C.lightBlue } } },
      { text: "Turn-on completed: 10 M/Cs",
        options: { bold: true, fill: { color: C.lightBlue }, color: C.navy, align: "left", fontSize: 10 } },
    ],
  ];

  s.addTable(daTable, {
    x: 0.35, y: 2.6, w: 12.6, h: 4.38,
    fontFace: "Calibri", fontSize: 12,
    border: { pt: 0.5, color: C.border },
    rowH: 0.4,
    colW: [2.4, 1.3, 1.3, 0.9, 1.3, 5.4],
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 6 – WIRE BOND STATUS
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  hdr(s, "Wire Bond Machine Status", "Before: 686 MC  →  Current: 553 MC");
  footer(s, 6, 7);

  const wbKPIs = [
    { val: "686",  lbl: "Total Before",     accent: C.blue },
    { val: "553",  lbl: "Current Active",   accent: C.green },
    { val: "133",  lbl: "Shutdown (Heads)", accent: C.red, vc: C.red },
    { val: "116",  lbl: "Turned On\n(of 133)", accent: C.orange },
    { val: "17",   lbl: "Remaining Heads",  accent: C.red, vc: C.red },
  ];
  wbKPIs.forEach((k, i) => {
    kpiCard(s, 0.35 + i * 2.52, 1.15, 2.35, 1.3, k.val, k.lbl, k.accent, k.vc);
  });

  const wbRows = [
    ["AB339",                   "74",  "0",   C.red,   "Shut down 74 M/C"],
    ["Eagle60",                 "47",  "18",  C.red,   "Shut down 29 M/C  |  Turn-on: 20/29"],
    ["Harrier",                 "98",  "72",  C.orange,"Shut down 13 M/C (26 heads)  |  Turn-on: 24/26 heads"],
    ["Harrier Xtreme",          "2",   "2",   C.green, ""],
    ["Eagle Xtreme GoCu",       "14",  "13",  C.orange,"WB#329 down"],
    ["Eagle Xtreme",            "1",   "0",   C.red,   "WB#211 down"],
    ["Eagle Aero GoCu",         "34",  "34",  C.green, ""],
    ["Twin Eagle Xtreme GoCu",  "214", "214", C.green, ""],
    ["Aero Twin",               "202", "200", C.orange,"WB#407 down"],
  ];

  const wbTable = [
    [
      { text: "Model",   options: { bold: true, fill: { color: C.navy }, color: C.white, align: "left" } },
      { text: "Before",  options: { bold: true, fill: { color: C.navy }, color: C.white, align: "center" } },
      { text: "Current", options: { bold: true, fill: { color: C.navy }, color: C.white, align: "center" } },
      { text: "Δ",       options: { bold: true, fill: { color: C.navy }, color: C.white, align: "center" } },
      { text: "Status",  options: { bold: true, fill: { color: C.navy }, color: C.white, align: "center" } },
      { text: "Remark",  options: { bold: true, fill: { color: C.navy }, color: C.white, align: "left" } },
    ],
    ...wbRows.map((r, idx) => {
      const bg = idx % 2 === 0 ? "F4F7FB" : C.white;
      const delta = parseInt(r[2]) - parseInt(r[1]);
      const deltaStr = delta === 0 ? "—" : delta.toString();
      const curr = parseInt(r[2]);
      const bef = parseInt(r[1]);
      const statusLabel = curr === bef ? "OK" : (curr === 0 ? "OFF" : "PARTIAL");
      return [
        { text: r[0], options: { fill: { color: bg }, align: "left", bold: true } },
        { text: r[1], options: { fill: { color: bg }, align: "center" } },
        { text: r[2], options: { fill: { color: bg }, align: "center", bold: true, color: r[3] } },
        { text: deltaStr, options: { fill: { color: bg }, align: "center", color: delta < 0 ? C.red : C.muted } },
        { text: statusLabel, options: { fill: { color: bg }, align: "center", bold: true, color: r[3] } },
        { text: r[4], options: { fill: { color: bg }, align: "left", fontSize: 10, color: C.muted } },
      ];
    }),
    [
      { text: "TOTAL", options: { bold: true, fill: { color: C.lightBlue }, color: C.navy, align: "center" } },
      { text: "686",   options: { bold: true, fill: { color: C.lightBlue }, color: C.navy, align: "center" } },
      { text: "553",   options: { bold: true, fill: { color: C.lightBlue }, color: C.navy, align: "center" } },
      { text: "-133",  options: { bold: true, fill: { color: C.lightBlue }, color: C.red,  align: "center" } },
      { text: "",      options: { fill: { color: C.lightBlue } } },
      { text: "Remaining 17 heads pending turn-on  |  Tech H/C: 58 → 40",
        options: { bold: true, fill: { color: C.lightBlue }, color: C.navy, align: "left", fontSize: 10 } },
    ],
  ];

  s.addTable(wbTable, {
    x: 0.35, y: 2.6, w: 12.6, h: 4.38,
    fontFace: "Calibri", fontSize: 11,
    border: { pt: 0.5, color: C.border },
    rowH: 0.4,
    colW: [2.8, 1.1, 1.1, 0.8, 1.2, 5.6],
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 7 – KEY ACTIONS & NEXT STEPS
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  hdr(s, "Key Actions & Next Steps", "As of April 2026");
  footer(s, 7, 7);

  const panels = [
    {
      title: "SAW",
      color: C.orange,
      lines: [
        "16 units (7500 PLUS) shut down due to end-of-life",
        "Root cause: Missing SAS-type HDD spare parts",
        "6 of 16 M/Cs successfully turned on",
        "10 M/Cs remain offline — spare parts procurement in progress",
        "Capacity recovery target: 7,900K by May 2026",
      ]
    },
    {
      title: "Die Attach",
      color: C.green,
      lines: [
        "AD889 model fully shutdown (25 M/Cs)",
        "Turn-on completed for 10 M/Cs",
        "88 M/Cs currently active",
        "Tech H/C reduced: 40 → 38",
        "Capacity recovery target: 7,900K by May 2026",
      ]
    },
    {
      title: "Wire Bond",
      color: C.blue,
      lines: [
        "AB339 (74 M/C) & Eagle60 (29 M/C) shutdown in progress",
        "Harrier: 26 heads shut down – 24 turned on, 2 remaining",
        "Eagle60: 29 heads – 20 turned on, 9 remaining",
        "Total: 116 / 133 turned on  |  17 heads still remaining",
        "Tech H/C reduced: 58 → 40",
      ]
    },
  ];

  panels.forEach((p, i) => {
    const px = 0.35 + i * 4.3;
    const py = 1.2;
    const pw = 4.1;
    const ph = 5.8;

    // Panel background
    s.addShape(pres.shapes.RECTANGLE, {
      x: px, y: py, w: pw, h: ph,
      fill: { color: C.white }, line: { color: C.border, width: 1 }
    });
    // Accent top bar
    s.addShape(pres.shapes.RECTANGLE, {
      x: px, y: py, w: pw, h: 0.07,
      fill: { color: p.color }, line: { color: p.color }
    });
    // Process label
    s.addText(p.title, {
      x: px, y: py + 0.1, w: pw, h: 0.5,
      fontSize: 16, bold: true, color: p.color,
      fontFace: "Calibri", align: "center", valign: "middle"
    });
    // Divider
    s.addShape(pres.shapes.LINE, {
      x: px + 0.2, y: py + 0.65, w: pw - 0.4, h: 0,
      line: { color: C.border, width: 0.5 }
    });
    // Bullet items
    const bulletItems = p.lines.map((l, li) => ({
      text: l,
      options: { bullet: true, breakLine: li < p.lines.length - 1 }
    }));
    s.addText(bulletItems, {
      x: px + 0.12, y: py + 0.75, w: pw - 0.24, h: ph - 0.95,
      fontSize: 11, color: C.text, fontFace: "Calibri",
      valign: "top", paraSpaceAfter: 6
    });
  });
}

// ─── Save ──────────────────────────────────────────────────────────────────
pres.writeFile({ fileName: "Output/Machine_Status_Report.pptx" })
  .then(() => console.log("Saved: Output/Machine_Status_Report.pptx"))
  .catch(err => { console.error(err); process.exit(1); });
