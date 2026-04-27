const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3" x 7.5"
pres.title = "MTAI Machine Status Report";

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

const W = 13.3, H = 7.5;
const TOTAL_SLIDES = 8;

// ─── Helpers ───────────────────────────────────────────────────────────────
function hdr(slide, title, subtitle) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: W, h: 1.0,
    fill: { color: C.navy }, line: { color: C.navy }
  });
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
  slide.background = { color: C.offwhite };
}

function footer(slide, n) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: H - 0.32, w: W, h: 0.32,
    fill: { color: C.navy }, line: { color: C.navy }
  });
  slide.addText("CONFIDENTIAL – For Management Review Only", {
    x: 0.3, y: H - 0.32, w: 9, h: 0.32,
    fontSize: 9, color: "BDD7EE", fontFace: "Calibri", valign: "middle", margin: 0
  });
  slide.addText(`${n} / ${TOTAL_SLIDES}`, {
    x: W - 1.2, y: H - 0.32, w: 1.0, h: 0.32,
    fontSize: 9, color: C.white, fontFace: "Calibri",
    valign: "middle", align: "right", margin: 0
  });
}

function kpiCard(slide, x, y, w, h, value, label, accent, valueColor) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x: x + 0.04, y: y + 0.04, w, h,
    fill: { color: "D1DDEF", transparency: 50 }, line: { color: "D1DDEF", transparency: 50 }
  });
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h,
    fill: { color: C.white }, line: { color: C.border, width: 1 }
  });
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h: 0.07,
    fill: { color: accent }, line: { color: accent }
  });
  slide.addText(value, {
    x, y: y + 0.07, w, h: h * 0.58,
    fontSize: 30, bold: true, color: valueColor || C.navy,
    fontFace: "Calibri", align: "center", valign: "middle", margin: 0
  });
  slide.addText(label, {
    x, y: y + h * 0.62, w, h: h * 0.35,
    fontSize: 11, color: C.muted,
    fontFace: "Calibri", align: "center", valign: "top", margin: 0
  });
}

const hdrCell = (t) => ({
  text: t,
  options: { bold: true, fill: { color: C.navy }, color: C.white, align: "center", valign: "middle" }
});

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 1 – TITLE
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: C.navy };

  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 3.5, w: W, h: 0.08,
    fill: { color: C.blue, transparency: 40 }, line: { color: C.blue, transparency: 40 }
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 3.65, w: W, h: 0.04,
    fill: { color: C.orange }, line: { color: C.orange }
  });

  s.addText("MTAI Machine Status Report", {
    x: 1.0, y: 1.4, w: 11.3, h: 1.4,
    fontSize: 44, bold: true, color: C.white,
    fontFace: "Calibri", align: "center", valign: "middle"
  });
  s.addText("Equipment Turn-On Status & Capacity Recovery", {
    x: 1.0, y: 2.85, w: 11.3, h: 0.6,
    fontSize: 22, color: "BDD7EE",
    fontFace: "Calibri", align: "center", valign: "middle"
  });

  const metas = [
    { label: "Date",     value: "April 2026" },
    { label: "Scope",    value: "All 9 Processes" },
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

  s.addText("MICROCHIP TECHNOLOGY", {
    x: 0, y: H - 0.55, w: W, h: 0.45,
    fontSize: 11, color: "BDD7EE", fontFace: "Calibri",
    align: "center", valign: "middle", charSpacing: 4
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 2 – EXECUTIVE SUMMARY
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  hdr(s, "Executive Summary", "All Processes – Machine & Capacity Status");
  footer(s, 2);

  // KPI cards
  const kpis = [
    { val: "6,200K",  lbl: "Min Capacity Now\n(SAW Bottleneck)",    accent: C.red,    vc: C.red    },
    { val: "42",      lbl: "Units Still Offline\n(Pending Turn-On)",accent: C.orange, vc: C.orange },
    { val: "76%",     lbl: "Turn-On Progress\n(132 of 174 units)",  accent: C.blue               },
    { val: "May '26", lbl: "Full Recovery\nTarget Month",           accent: C.green              },
  ];
  kpis.forEach((k, i) => {
    kpiCard(s, 0.35 + i * 3.1, 1.15, 2.9, 1.4, k.val, k.lbl, k.accent, k.vc);
  });

  // 3-col progress table: Process | Before | Current | Cap Now | Apr'26 | May'26
  const tY = 2.75;
  // [process, beforeMC, currentMC, capNow, apr(mc/cap), may(mc/cap), changed]
  const rows = [
    ["BG",          "2",   "2",   "8,500", "—",            "—",             false],
    ["SAW Wafer",   "51",  "35",  "6,200", "41 / 7,700K",  "51 / 8,500K",   true ],
    ["Die Attach",  "113", "88",  "6,500", "98 / 7,200K",  "113 / 8,500K",  true ],
    ["Wire Bond",   "686", "553", "6,900", "669 / 8,200K", "686 / 8,500K",  true ],
    ["Mold",        "24",  "24",  "8,500", "—",            "—",             false],
    ["Plating",     "3",   "3",   "8,500", "—",            "—",             false],
    ["Laser Mark",  "18",  "16",  "8,000", "18 / 8,500K",  "—",             true ],
    ["Trim & Form", "70",  "70",  "8,500", "—",            "—",             false],
    ["Saw QFN",     "39",  "39",  "8,500", "—",            "—",             false],
  ];

  const tableData = [
    [
      hdrCell("Process"),
      hdrCell("Before\n(MC)"),
      hdrCell("Current\n(MC)"),
      hdrCell("Cap Now\n(K)"),
      hdrCell("Apr '26\nMC / Cap(K)"),
      hdrCell("May '26\nMC / Cap(K)"),
    ],
    ...rows.map((r, idx) => {
      const bg = idx % 2 === 0 ? "F4F7FB" : C.white;
      const isOK = !r[6];
      const capColor = r[3] === "8,500" ? C.green : C.red;
      const mc = (v) => (v === "—" ? C.muted : C.green);
      return [
        { text: r[0], options: { fill: { color: bg }, align: "left",   bold: true, valign: "middle" } },
        { text: r[1], options: { fill: { color: bg }, align: "center", valign: "middle" } },
        { text: r[2], options: { fill: { color: bg }, align: "center", bold: true, color: isOK ? C.green : C.navy, valign: "middle" } },
        { text: r[3], options: { fill: { color: bg }, align: "center", bold: true, color: capColor, valign: "middle" } },
        { text: r[4], options: { fill: { color: bg }, align: "center", fontSize: 10, color: mc(r[4]), valign: "middle" } },
        { text: r[5], options: { fill: { color: bg }, align: "center", fontSize: 10, color: mc(r[5]), bold: r[6], valign: "middle" } },
      ];
    }),
  ];

  s.addTable(tableData, {
    x: 0.35, y: tY, w: 12.6, h: 4.1,
    fontFace: "Calibri", fontSize: 11,
    border: { pt: 0.5, color: C.border },
    rowH: 0.40,
    colW: [2.0, 1.3, 1.3, 1.3, 2.85, 3.85],
  });

  s.addText("Green = Recovered / On Track   Red Cap = Below 8,500K target", {
    x: 0.35, y: 6.85, w: 7.5, h: 0.2,
    fontSize: 8.5, color: C.muted, fontFace: "Calibri", align: "left"
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 3 – CAPACITY RECOVERY CHART
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  hdr(s, "Capacity Recovery Roadmap", "SAW · Die Attach · Wire Bond  |  K units/month");
  footer(s, 3);

  const chartData = [
    { name: "SAW Wafer", labels: ["Before","Current","Apr '26","May '26"], values: [8500,6200,7700,8500] },
    { name: "Die Attach",labels: ["Before","Current","Apr '26","May '26"], values: [8500,6500,7200,8500] },
    { name: "Wire Bond", labels: ["Before","Current","Apr '26","May '26"], values: [8500,6900,8200,8500] },
  ];

  s.addChart(pres.charts.LINE, chartData, {
    x: 0.4, y: 1.15, w: 12.5, h: 5.6,
    chartColors: [C.orange, C.green, C.blue],
    lineSize: 3, lineSmooth: false,
    showValue: true, dataLabelPosition: "t",
    dataLabelColor: C.text, dataLabelFontSize: 10, dataLabelFontBold: true,
    dataLabelFontFace: "Calibri",
    showLegend: true, legendPos: "b", legendFontSize: 11, legendFontFace: "Calibri",
    catAxisLabelColor: C.muted, valAxisLabelColor: C.muted,
    catAxisLabelFontFace: "Calibri", valAxisLabelFontFace: "Calibri",
    catAxisLabelFontSize: 12, valAxisLabelFontSize: 10,
    valAxisMinVal: 5000, valAxisMaxVal: 9000,
    valGridLine: { color: "E2E8F0", size: 0.5 }, catGridLine: { style: "none" },
    chartArea: { fill: { color: C.offwhite }, roundedCorners: false },
    plotArea: { fill: { color: C.offwhite } },
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 4 – SAW + BG STATUS
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  hdr(s, "SAW Machine Status", "Before: 51 MC → Current: 35 MC  |  BG: 2/2 On Track");
  footer(s, 4);

  const sawKPIs = [
    { val: "51",  lbl: "Total Before", accent: C.blue  },
    { val: "35",  lbl: "Current Active",accent: C.green},
    { val: "16",  lbl: "Shutdown\n(7500 PLUS)",accent: C.red, vc: C.red },
    { val: "6",   lbl: "Turned On\n(of 16)",   accent: C.orange },
    { val: "10",  lbl: "Remaining\n(No SAS Parts)", accent: C.red, vc: C.red },
  ];
  sawKPIs.forEach((k, i) => {
    kpiCard(s, 0.35 + i * 2.52, 1.15, 2.35, 1.3, k.val, k.lbl, k.accent, k.vc);
  });

  // SAW detail table
  const sawRows = [
    ["BG",  "DFG 8540",     "2",  "2",  C.green, "",          "2",  "2"],
    ["SAW", "7500 PLUS",    "16", "0",  C.red,   "Shutdown #01–16 | 10 M/C: no SAS HDD spare parts", "+6",  "—"],
    ["SAW", "AD2000T",      "7",  "7",  C.green, "",          "7",  "7"],
    ["SAW", "AD3000T",      "12", "12", C.green, "",          "12", "12"],
    ["SAW", "AD3000T Plus", "1",  "1",  C.green, "",          "1",  "1"],
    ["SAW", "DFD6340",      "9",  "9",  C.green, "",          "9",  "9"],
    ["SAW", "DFD6361",      "1",  "1",  C.green, "",          "1",  "1"],
    ["SAW", "DFD6560",      "5",  "5",  C.green, "",          "5",  "5"],
  ];

  const tableData = [
    [
      hdrCell("Process"), hdrCell("Model"),  hdrCell("Before"),
      hdrCell("Current"), hdrCell("Status"), hdrCell("Remark"),
      hdrCell("Apr '26"), hdrCell("May '26"),
    ],
    ...sawRows.map((r, idx) => {
      const bg = idx % 2 === 0 ? "F4F7FB" : C.white;
      const curr = parseInt(r[3]);
      const bef  = parseInt(r[2]);
      const lbl  = curr === bef ? "OK" : (curr === 0 ? "OFF" : "PARTIAL");
      return [
        { text: r[0], options: { fill: { color: bg }, align: "center", bold: true, valign: "middle" } },
        { text: r[1], options: { fill: { color: bg }, align: "left",   bold: true, valign: "middle" } },
        { text: r[2], options: { fill: { color: bg }, align: "center", valign: "middle" } },
        { text: r[3], options: { fill: { color: bg }, align: "center", bold: true, color: r[4], valign: "middle" } },
        { text: lbl,  options: { fill: { color: bg }, align: "center", bold: true, color: r[4], valign: "middle" } },
        { text: r[5], options: { fill: { color: bg }, align: "left",   fontSize: 9.5, color: C.muted, valign: "middle" } },
        { text: r[6], options: { fill: { color: bg }, align: "center", bold: r[6]!=="—", color: r[6]==="—"?C.muted:C.green, valign: "middle" } },
        { text: r[7], options: { fill: { color: bg }, align: "center", bold: r[7]!=="—", color: r[7]==="—"?C.muted:C.green, valign: "middle" } },
      ];
    }),
    // Total
    [
      { text: "TOTAL", options: { colspan: 2, bold: true, fill: { color: C.lightBlue }, color: C.navy, align: "center", valign: "middle" } },
      { text: "53",    options: { bold: true, fill: { color: C.lightBlue }, color: C.navy, align: "center", valign: "middle" } },
      { text: "37",    options: { bold: true, fill: { color: C.lightBlue }, color: C.navy, align: "center", valign: "middle" } },
      { text: "",      options: { fill: { color: C.lightBlue } } },
      { text: "Turn-on completed: Saw#02,03,05,07,09,11 (6 M/C)  |  10 M/C pending SAS spare parts",
        options: { bold: true, fill: { color: C.lightBlue }, color: C.navy, align: "left", fontSize: 9.5, valign: "middle" } },
      { text: "43",    options: { bold: true, fill: { color: C.lightBlue }, color: C.green, align: "center", valign: "middle" } },
      { text: "53",    options: { bold: true, fill: { color: C.lightBlue }, color: C.green, align: "center", valign: "middle" } },
    ],
  ];

  s.addTable(tableData, {
    x: 0.35, y: 2.6, w: 12.6, h: 4.38,
    fontFace: "Calibri", fontSize: 11,
    border: { pt: 0.5, color: C.border },
    rowH: 0.44,
    colW: [1.1, 2.2, 1.1, 1.1, 1.1, 3.3, 1.3, 1.4],
  });
}

// ─── Shared helper: SAW-style process table ──────────────────────────────
// rows: [process, model, before, current, statusColor, remark, apr, may]
function sawStyleTable(s, kpis, rows, totalRow, aprLabel, mayLabel) {
  kpis.forEach((k, i) => {
    kpiCard(s, 0.35 + i * 2.52, 1.15, 2.35, 1.3, k.val, k.lbl, k.accent, k.vc);
  });

  const tableData = [
    [
      hdrCell("Process"), hdrCell("Model"), hdrCell("Before"),
      hdrCell("Current"), hdrCell("Status"), hdrCell("Remark"),
      hdrCell(aprLabel || "Apr '26"), hdrCell(mayLabel || "May '26"),
    ],
    ...rows.map((r, idx) => {
      const bg   = idx % 2 === 0 ? "F4F7FB" : C.white;
      const curr = parseInt(r[3]);
      const bef  = parseInt(r[2]);
      const apr  = r[6];
      const may  = r[7];
      const lbl  = curr === bef ? "OK" : (curr === 0 ? "OFF" : "PARTIAL");
      return [
        { text: r[0], options: { fill:{color:bg}, align:"center", bold:true, valign:"middle" } },
        { text: r[1], options: { fill:{color:bg}, align:"left",   bold:true, valign:"middle" } },
        { text: r[2], options: { fill:{color:bg}, align:"center", valign:"middle" } },
        { text: r[3], options: { fill:{color:bg}, align:"center", bold:true, color:r[4], valign:"middle" } },
        { text: lbl,  options: { fill:{color:bg}, align:"center", bold:true, color:r[4], valign:"middle" } },
        { text: r[5], options: { fill:{color:bg}, align:"left",   fontSize:9.5, color:C.muted, valign:"middle" } },
        { text: apr,  options: { fill:{color:bg}, align:"center", bold: apr!=="—", color: apr==="—"?C.muted:C.green, valign:"middle" } },
        { text: may,  options: { fill:{color:bg}, align:"center", bold: may!=="—", color: may==="—"?C.muted:C.green, valign:"middle" } },
      ];
    }),
    totalRow,
  ];

  s.addTable(tableData, {
    x: 0.35, y: 2.6, w: 12.6, h: 4.38,
    fontFace:"Calibri", fontSize:11,
    border:{pt:0.5, color:C.border},
    rowH: 0.39,
    colW: [1.1, 2.2, 1.1, 1.1, 1.1, 3.3, 1.3, 1.4],
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 5 – DIE ATTACH STATUS
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  hdr(s, "Die Attach Machine Status", "Before: 113 MC  →  Current: 88 MC");
  footer(s, 5);

  const daKPIs = [
    { val: "113", lbl: "Total Before",      accent: C.blue   },
    { val: "88",  lbl: "Current Active",    accent: C.green  },
    { val: "25",  lbl: "Shutdown\n(AD889)", accent: C.red,  vc: C.red  },
    { val: "10",  lbl: "Turned On\n(Apr '26)", accent: C.orange },
    { val: "38",  lbl: "Tech H/C\n(was 40)",accent: C.muted  },
  ];

  // [process, model, before, current, statusColor, remark, apr26, may26]
  const daRows = [
    ["Die Attach","AD828",      "5",  "5",  C.green, "",                                          "5",  "5"  ],
    ["Die Attach","AD830",      "15", "15", C.green, "",                                          "15", "15" ],
    ["Die Attach","AD8312",     "10", "10", C.green, "",                                          "10", "10" ],
    ["Die Attach","AD8312Plus", "8",  "8",  C.green, "",                                          "8",  "8"  ],
    ["Die Attach","AD832i",     "13", "13", C.green, "",                                          "13", "13" ],
    ["Die Attach","AD838",      "13", "13", C.green, "",                                          "13", "13" ],
    ["Die Attach","AD889",      "25", "0",  C.red,   "Shutdown 25 M/C | +10 turned on (Apr WW2)","10", "25" ],
    ["Die Attach","AD8912",     "1",  "1",  C.green, "",                                          "1",  "1"  ],
    ["Die Attach","AD898",      "23", "23", C.green, "",                                          "23", "23" ],
  ];

  const daTotalRow = [
    { text:"TOTAL", options:{colspan:2, bold:true, fill:{color:C.lightBlue}, color:C.navy, align:"center", valign:"middle"} },
    { text:"113",   options:{bold:true, fill:{color:C.lightBlue}, color:C.navy,  align:"center", valign:"middle"} },
    { text:"88",    options:{bold:true, fill:{color:C.lightBlue}, color:C.navy,  align:"center", valign:"middle"} },
    { text:"",      options:{fill:{color:C.lightBlue}} },
    { text:"Turn-on completed 10 M/Cs (AD889)  |  Tech H/C: 40 → 38",
      options:{bold:true, fill:{color:C.lightBlue}, color:C.navy, align:"left", fontSize:9.5, valign:"middle"} },
    { text:"98",    options:{bold:true, fill:{color:C.lightBlue}, color:C.green, align:"center", valign:"middle"} },
    { text:"113",   options:{bold:true, fill:{color:C.lightBlue}, color:C.green, align:"center", valign:"middle"} },
  ];

  sawStyleTable(s, daKPIs, daRows, daTotalRow);
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 6 – WIRE BOND STATUS
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  hdr(s, "Wire Bond Machine Status", "Before: 686 MC  →  Current: 553 MC");
  footer(s, 6);

  const wbKPIs = [
    { val: "686", lbl: "Total Before",       accent: C.blue   },
    { val: "553", lbl: "Current Active",     accent: C.green  },
    { val: "133", lbl: "Shutdown (Heads)",   accent: C.red,  vc: C.red  },
    { val: "116", lbl: "Turned On\n(of 133)",accent: C.orange },
    { val: "17",  lbl: "Remaining Heads",    accent: C.red,  vc: C.red  },
  ];

  // [process, model, before, current, statusColor, remark, apr_ww2, apr_ww4]
  const wbRows = [
    ["Wire Bond","AB339",                  "74",  "0",   C.red,   "Shut down 74 M/C  |  Turn-on: 72/74",      "72",  "74"  ],
    ["Wire Bond","Eagle60",                "47",  "18",  C.red,   "Shut down 29 M/C  |  Turn-on: 38/47",      "38",  "47"  ],
    ["Wire Bond","Harrier",                "98",  "72",  C.orange,"Shut down 26 heads  |  Turn-on: 96/98",     "96",  "98"  ],
    ["Wire Bond","Harrier Xtreme",         "2",   "2",   C.green, "",                                           "2",   "2"   ],
    ["Wire Bond","Eagle Xtreme GoCu",      "14",  "13",  C.orange,"WB#329 down",                               "13",  "14"  ],
    ["Wire Bond","Eagle Xtreme",           "1",   "0",   C.red,   "WB#211 down",                               "0",   "1"   ],
    ["Wire Bond","Eagle Aero GoCu",        "34",  "34",  C.green, "",                                           "34",  "34"  ],
    ["Wire Bond","Twin Eagle Xtreme GoCu", "214", "214", C.green, "",                                           "214", "214" ],
    ["Wire Bond","Aero Twin",              "202", "200", C.orange,"WB#407 down",                               "200", "202" ],
  ];

  const wbTotalRow = [
    { text:"TOTAL", options:{colspan:2, bold:true, fill:{color:C.lightBlue}, color:C.navy, align:"center", valign:"middle"} },
    { text:"686",   options:{bold:true, fill:{color:C.lightBlue}, color:C.navy,  align:"center", valign:"middle"} },
    { text:"553",   options:{bold:true, fill:{color:C.lightBlue}, color:C.navy,  align:"center", valign:"middle"} },
    { text:"",      options:{fill:{color:C.lightBlue}} },
    { text:"17 heads remaining  |  Tech H/C: 58 → 40",
      options:{bold:true, fill:{color:C.lightBlue}, color:C.navy, align:"left", fontSize:9.5, valign:"middle"} },
    { text:"669",   options:{bold:true, fill:{color:C.lightBlue}, color:C.green, align:"center", valign:"middle"} },
    { text:"686",   options:{bold:true, fill:{color:C.lightBlue}, color:C.green, align:"center", valign:"middle"} },
  ];

  sawStyleTable(s, wbKPIs, wbRows, wbTotalRow, "Apr '26 (WW2)", "Apr '26 (WW4)");
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 7 – OTHER PROCESSES (clean card grid)
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  hdr(s, "Other Processes Status", "Mold · Plating · Trim & Form · Saw QFN  ✓  |  Laser Mark  ⚠");
  footer(s, 7);

  // ── Top row: 4 stable process cards ──────────────────────────────────────
  const stableProcs = [
    {
      name: "Mold", mc: "24 / 24",
      models: "DP80 ×8  |  GP-ELF ×1  |  GP-Pro ×15",
    },
    {
      name: "Plating", mc: "3 / 3",
      models: "MECO EDF+EPL2400S ×3",
    },
    {
      name: "Trim & Form", mc: "70 / 70",
      models: "T&F: GPM×3, ASM MP209×5\nIsolation: GPM×5, MP209×18, MPHENIX×7\nF/S: GPM×5, MP209×17, MPHENIX×10",
    },
    {
      name: "Saw QFN", mc: "39 / 39",
      models: "Disco EAD6750 ×2\nDisco DFD6750 ×6\nAccretech AD3000T ×31",
    },
  ];

  stableProcs.forEach((p, i) => {
    const cx = 0.35 + i * 3.15;
    const cy = 1.1;
    const cw = 3.0;
    const ch = 2.55;

    // Card shadow
    s.addShape(pres.shapes.RECTANGLE, {
      x: cx + 0.04, y: cy + 0.04, w: cw, h: ch,
      fill: { color: "D1DDEF", transparency: 55 }, line: { color: "D1DDEF", transparency: 55 }
    });
    // Card body
    s.addShape(pres.shapes.RECTANGLE, {
      x: cx, y: cy, w: cw, h: ch,
      fill: { color: C.white }, line: { color: C.border, width: 1 }
    });
    // Green accent bar
    s.addShape(pres.shapes.RECTANGLE, {
      x: cx, y: cy, w: cw, h: 0.07,
      fill: { color: C.green }, line: { color: C.green }
    });
    // Process name
    s.addText(p.name, {
      x: cx, y: cy + 0.07, w: cw, h: 0.42,
      fontSize: 15, bold: true, color: C.navy,
      fontFace: "Calibri", align: "center", valign: "middle"
    });
    // Divider
    s.addShape(pres.shapes.LINE, {
      x: cx + 0.15, y: cy + 0.52, w: cw - 0.3, h: 0,
      line: { color: C.border, width: 0.5 }
    });
    // MC count (big)
    s.addText(p.mc, {
      x: cx, y: cy + 0.55, w: cw, h: 0.65,
      fontSize: 26, bold: true, color: C.green,
      fontFace: "Calibri", align: "center", valign: "middle"
    });
    // Cap badge
    s.addText("Cap:  8,500K  ✓", {
      x: cx, y: cy + 1.22, w: cw, h: 0.3,
      fontSize: 11, bold: true, color: C.green,
      fontFace: "Calibri", align: "center", valign: "middle"
    });
    // Model list
    s.addText(p.models, {
      x: cx + 0.1, y: cy + 1.55, w: cw - 0.2, h: ch - 1.62,
      fontSize: 9, color: C.muted,
      fontFace: "Calibri", align: "center", valign: "top"
    });
  });

  // ── Bottom: Laser Mark panel ──────────────────────────────────────────────
  const lmY = 3.88;
  const lmH = 3.08;

  // Panel background
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.35, y: lmY, w: 12.6, h: lmH,
    fill: { color: C.white }, line: { color: C.border, width: 1 }
  });
  // Orange header bar
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.35, y: lmY, w: 12.6, h: 0.42,
    fill: { color: C.orange }, line: { color: C.orange }
  });
  s.addText("⚠  Laser Mark  |  Before: 17 MC  →  Current: 15 MC  |  2 M/Cs Offline  |  Cap: 8,000K → Target: 8,500K (Apr 30 '26)", {
    x: 0.45, y: lmY, w: 12.3, h: 0.42,
    fontSize: 12, bold: true, color: C.white, fontFace: "Calibri", valign: "middle", margin: 0
  });

  // Left section: model table
  const lmModelTable = [
    [ hdrCell("Model"), hdrCell("Before"), hdrCell("Current"), hdrCell("Offline"), hdrCell("Apr '26\n(WW4)") ],
    ...[
      ["GPM Smart Mark","16","14","2","16"],
      ["ENR B2200",     "1", "1", "—","1"],
    ].map((r,i) => {
      const bg = i%2===0 ? "F4F7FB" : C.white;
      const down = r[3] !== "—";
      return [
        { text:r[0], options:{fill:{color:bg},align:"left",bold:true,valign:"middle"} },
        { text:r[1], options:{fill:{color:bg},align:"center",valign:"middle"} },
        { text:r[2], options:{fill:{color:bg},align:"center",bold:true,color:down?C.orange:C.green,valign:"middle"} },
        { text:r[3], options:{fill:{color:bg},align:"center",bold:down,color:down?C.red:C.muted,valign:"middle"} },
        { text:r[4], options:{fill:{color:bg},align:"center",bold:true,color:C.green,valign:"middle"} },
      ];
    }),
    [
      hdrCell("TOTAL"),
      {text:"17",options:{bold:true,fill:{color:C.lightBlue},color:C.navy,align:"center",valign:"middle"}},
      {text:"15",options:{bold:true,fill:{color:C.lightBlue},color:C.orange,align:"center",valign:"middle"}},
      {text:"2", options:{bold:true,fill:{color:C.lightBlue},color:C.red,align:"center",valign:"middle"}},
      {text:"17",options:{bold:true,fill:{color:C.lightBlue},color:C.green,align:"center",valign:"middle"}},
    ],
  ];
  s.addTable(lmModelTable, {
    x: 0.45, y: lmY + 0.52, w: 5.5, h: 1.45,
    fontFace:"Calibri", fontSize:11,
    border:{pt:0.5,color:C.border}, rowH:0.38,
    colW:[2.3,0.9,0.9,0.9,0.9],
  });

  // Vertical divider
  s.addShape(pres.shapes.LINE, {
    x: 6.25, y: lmY + 0.52, w: 0, h: lmH - 0.62,
    line: { color: C.border, width: 0.8 }
  });

  // Middle section: repair schedule
  s.addText("Machine Repair Schedule", {
    x: 6.45, y: lmY + 0.52, w: 4.0, h: 0.32,
    fontSize: 11, bold: true, color: C.navy, fontFace: "Calibri"
  });
  const repairTable = [
    [ hdrCell("Machine"), hdrCell("Action Required"), hdrCell("Target") ],
    ...[
      ["L/M #07","Replace Keyence 2D Camera",                        "Apr 30 '26"],
      ["L/M #10","Laser chamber re-alignment & PLC part replacement", "Apr 30 '26"],
    ].map((r,i) => {
      const bg = i%2===0 ? "F4F7FB" : C.white;
      return [
        { text:r[0], options:{fill:{color:bg},align:"center",bold:true,color:C.orange,valign:"middle"} },
        { text:r[1], options:{fill:{color:bg},align:"left",  fontSize:10,valign:"middle"} },
        { text:r[2], options:{fill:{color:bg},align:"center",bold:true,color:C.green,valign:"middle"} },
      ];
    }),
  ];
  s.addTable(repairTable, {
    x: 6.45, y: lmY + 0.85, w: 5.8, h: 1.12,
    fontFace:"Calibri", fontSize:11,
    border:{pt:0.5,color:C.border}, rowH:0.38,
    colW:[1.1,3.4,1.3],
  });

  // Capacity recovery callout
  s.addShape(pres.shapes.RECTANGLE, {
    x: 6.45, y: lmY + 2.1, w: 5.8, h: 0.72,
    fill: { color: "FFF3E0" }, line: { color: C.orange, width: 1.5 }
  });
  s.addText([
    { text: "Capacity Recovery  ", options: { bold: true, color: C.navy, fontSize: 12 } },
    { text: "8,000K  →  8,500K", options: { bold: true, color: C.green, fontSize: 12 } },
    { text: "\nBoth L/M#07 & L/M#10 repair complete by ", options: { color: C.text, fontSize: 10.5 } },
    { text: "Apr 30 '26", options: { bold: true, color: C.green, fontSize: 10.5 } },
  ], {
    x: 6.6, y: lmY + 2.13, w: 5.5, h: 0.66,
    fontFace: "Calibri", valign: "middle"
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 8 – KEY ACTIONS & NEXT STEPS
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  hdr(s, "Key Actions & Next Steps", "As of April 2026");
  footer(s, 8);

  const panels = [
    {
      title: "SAW",
      color: C.orange,
      lines: [
        "16 units (7500 PLUS) shut down – end of life",
        "Root cause: Missing SAS-type HDD spare parts",
        "6 of 16 M/Cs successfully turned on (Saw#02,03,05,07,09,11)",
        "10 M/Cs remain offline – spare parts procurement in progress",
        "Capacity recovery: 6,200K → 7,700K (Apr) → 8,500K (May)",
      ]
    },
    {
      title: "Die Attach",
      color: C.green,
      lines: [
        "AD889 model (25 M/Cs) fully shutdown",
        "10 M/Cs turned on (Apr WW2): DB#20,02,01,04,12,22,15,09,13,10",
        "3 M/Cs waiting: PC/MES security update, setup, on-going repair",
        "12 M/Cs Boot Fail: ELMO driver damage – no spare parts available",
        "Capacity recovery: 6,500K → 7,200K (Apr) → 8,500K (May)",
      ]
    },
    {
      title: "Wire Bond",
      color: C.blue,
      lines: [
        "AB339 (74) & Eagle60 (29 heads) shutdown in progress",
        "Harrier: 26 heads shut down – 24 turned on, 2 remaining",
        "Eagle60: 29 heads – 20 turned on, 9 remaining",
        "Total: 116/133 turned on  |  17 heads still pending",
        "Capacity recovery: 6,900K → 8,200K (Apr WW2) → 8,500K (Apr WW4)",
      ]
    },
  ];

  panels.forEach((p, i) => {
    const px = 0.35 + i * 4.3;
    const py = 1.2;
    const pw = 4.1;
    const ph = 5.8;

    s.addShape(pres.shapes.RECTANGLE, {
      x: px, y: py, w: pw, h: ph,
      fill: { color: C.white }, line: { color: C.border, width: 1 }
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x: px, y: py, w: pw, h: 0.07,
      fill: { color: p.color }, line: { color: p.color }
    });
    s.addText(p.title, {
      x: px, y: py + 0.1, w: pw, h: 0.5,
      fontSize: 16, bold: true, color: p.color,
      fontFace: "Calibri", align: "center", valign: "middle"
    });
    s.addShape(pres.shapes.LINE, {
      x: px + 0.2, y: py + 0.65, w: pw - 0.4, h: 0,
      line: { color: C.border, width: 0.5 }
    });
    const bullets = p.lines.map((l, li) => ({
      text: l,
      options: { bullet: true, breakLine: li < p.lines.length - 1 }
    }));
    s.addText(bullets, {
      x: px + 0.12, y: py + 0.75, w: pw - 0.24, h: ph - 0.95,
      fontSize: 11, color: C.text, fontFace: "Calibri",
      valign: "top", paraSpaceAfter: 6
    });
  });
}

// ─── Save ──────────────────────────────────────────────────────────────────
pres.writeFile({ fileName: "Output/MTAI_Machine_Status_Report.pptx" })
  .then(() => console.log("Saved: Output/MTAI_Machine_Status_Report.pptx"))
  .catch(err => { console.error(err); process.exit(1); });
