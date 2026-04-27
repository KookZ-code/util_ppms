const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3" x 7.5"
pres.title = "MMT Machine Status Report";

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
    x:0, y:0, w:W, h:1.0, fill:{color:C.navy}, line:{color:C.navy}
  });
  slide.addText(title, {
    x:0.45, y:0, w: subtitle?9:12.8, h:1.0,
    fontSize:24, bold:true, color:C.white, fontFace:"Calibri", valign:"middle", margin:0
  });
  if (subtitle) {
    slide.addText(subtitle, {
      x:9.5, y:0, w:3.5, h:1.0,
      fontSize:12, color:"BDD7EE", fontFace:"Calibri", valign:"middle", align:"right", margin:0
    });
  }
  slide.background = {color:C.offwhite};
}

function footer(slide, n) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x:0, y:H-0.32, w:W, h:0.32, fill:{color:C.navy}, line:{color:C.navy}
  });
  slide.addText("CONFIDENTIAL – For Management Review Only", {
    x:0.3, y:H-0.32, w:9, h:0.32,
    fontSize:9, color:"BDD7EE", fontFace:"Calibri", valign:"middle", margin:0
  });
  slide.addText(`${n} / ${TOTAL_SLIDES}`, {
    x:W-1.2, y:H-0.32, w:1.0, h:0.32,
    fontSize:9, color:C.white, fontFace:"Calibri", valign:"middle", align:"right", margin:0
  });
}

function kpiCard(slide, x, y, w, h, value, label, accent, valueColor) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x:x+0.04, y:y+0.04, w, h,
    fill:{color:"D1DDEF",transparency:50}, line:{color:"D1DDEF",transparency:50}
  });
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h, fill:{color:C.white}, line:{color:C.border,width:1}
  });
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h:0.07, fill:{color:accent}, line:{color:accent}
  });
  slide.addText(value, {
    x, y:y+0.07, w, h:h*0.58,
    fontSize:30, bold:true, color:valueColor||C.navy,
    fontFace:"Calibri", align:"center", valign:"middle", margin:0
  });
  slide.addText(label, {
    x, y:y+h*0.62, w, h:h*0.35,
    fontSize:11, color:C.muted, fontFace:"Calibri", align:"center", valign:"top", margin:0
  });
}

const hdrCell = (t) => ({
  text:t,
  options:{bold:true, fill:{color:C.navy}, color:C.white, align:"center", valign:"middle"}
});

// SAW-style full-width table (shared by SAW/DA/WB slides)
// rows: [process, model, before, current, statusColor, remark, col7, col8]
function sawStyleTable(s, kpis, rows, totalRow, col7Label, col8Label) {
  kpis.forEach((k, i) => {
    kpiCard(s, 0.35+i*2.52, 1.15, 2.35, 1.3, k.val, k.lbl, k.accent, k.vc);
  });
  const tableData = [
    [
      hdrCell("Process"), hdrCell("Model"), hdrCell("Before"),
      hdrCell("Current"), hdrCell("Status"), hdrCell("Remark"),
      hdrCell(col7Label||"Apr '26"), hdrCell(col8Label||"May '26"),
    ],
    ...rows.map((r, idx) => {
      const bg  = idx%2===0?"F4F7FB":C.white;
      const curr = parseInt(r[3]), bef = parseInt(r[2]);
      const lbl  = curr===0&&bef===0 ? "N/A"
                 : curr>bef ? "ADDED"
                 : curr===bef ? "OK"
                 : curr===0 ? "OFF" : "PARTIAL";
      const lblColor = curr>bef?C.green : curr===bef?C.green : curr===0?C.red : C.orange;
      const c7=r[6], c8=r[7];
      return [
        {text:r[0], options:{fill:{color:bg},align:"center",bold:true,valign:"middle"}},
        {text:r[1], options:{fill:{color:bg},align:"left",  bold:true,valign:"middle"}},
        {text:r[2], options:{fill:{color:bg},align:"center",valign:"middle"}},
        {text:r[3], options:{fill:{color:bg},align:"center",bold:true,color:r[4],valign:"middle"}},
        {text:lbl,  options:{fill:{color:bg},align:"center",bold:true,color:lblColor,valign:"middle"}},
        {text:r[5], options:{fill:{color:bg},align:"left",  fontSize:9.5,color:C.muted,valign:"middle"}},
        {text:c7,   options:{fill:{color:bg},align:"center",bold:c7!=="—",color:c7==="—"?C.muted:C.green,valign:"middle"}},
        {text:c8,   options:{fill:{color:bg},align:"center",bold:c8!=="—",color:c8==="—"?C.muted:C.green,valign:"middle"}},
      ];
    }),
    totalRow,
  ];
  s.addTable(tableData, {
    x:0.35, y:2.6, w:12.6, h:4.38,
    fontFace:"Calibri", fontSize:11,
    border:{pt:0.5,color:C.border},
    rowH:0.39,
    colW:[1.1,2.2,1.1,1.1,1.1,3.3,1.3,1.4],
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 1 – TITLE
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = {color:C.navy};
  s.addShape(pres.shapes.RECTANGLE, {x:0,y:3.5,w:W,h:0.08,fill:{color:C.blue,transparency:40},line:{color:C.blue,transparency:40}});
  s.addShape(pres.shapes.RECTANGLE, {x:0,y:3.65,w:W,h:0.04,fill:{color:C.orange},line:{color:C.orange}});
  s.addText("MMT Machine Status Report", {
    x:1.0,y:1.4,w:11.3,h:1.4,
    fontSize:44,bold:true,color:C.white,fontFace:"Calibri",align:"center",valign:"middle"
  });
  s.addText("Equipment Status & Capacity Recovery Report", {
    x:1.0,y:2.85,w:11.3,h:0.6,
    fontSize:22,color:"BDD7EE",fontFace:"Calibri",align:"center",valign:"middle"
  });
  [
    {label:"Date",    value:"April 2026"},
    {label:"Scope",   value:"All 9 Processes"},
    {label:"Audience",value:"Top Management"},
  ].forEach((m,i)=>{
    const bx=1.5+i*3.5;
    s.addShape(pres.shapes.RECTANGLE,{x:bx,y:4.15,w:3.0,h:0.9,fill:{color:C.blue,transparency:30},line:{color:C.blue}});
    s.addText([
      {text:m.label+"\n",options:{fontSize:10,color:"BDD7EE",breakLine:true}},
      {text:m.value,     options:{fontSize:13,bold:true,color:C.white}},
    ],{x:bx,y:4.15,w:3.0,h:0.9,align:"center",valign:"middle",fontFace:"Calibri"});
  });
  s.addText("MICROCHIP TECHNOLOGY", {
    x:0,y:H-0.55,w:W,h:0.45,
    fontSize:11,color:"BDD7EE",fontFace:"Calibri",align:"center",valign:"middle",charSpacing:4
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
  [
    {val:"5,550K", lbl:"Min Capacity Now\n(SAW Bottleneck)",   accent:C.orange, vc:C.orange},
    {val:"11",     lbl:"M/Cs Offline\n(SAW×6, WB×4, Plt×1)",  accent:C.red,    vc:C.red   },
    {val:"73%",    lbl:"HC Utilization\n(103 / 141 approved)", accent:C.blue               },
    {val:"Jun '26",lbl:"Full WB Recovery\nTarget Month",       accent:C.green              },
  ].forEach((k,i)=>{
    kpiCard(s, 0.35+i*3.1, 1.15, 2.9, 1.4, k.val, k.lbl, k.accent, k.vc);
  });

  // 3-month table (Apr/May/Jun)
  const tY=2.75;
  // [process, beforeMC, currentMC, capNow, apr, may, jun, changed]
  const rows=[
    ["BG",         "3",  "3",   "6,700","—",             "—",             "—",             false],
    ["SAW Wafer",  "35", "29",  "5,550","33 / 6,300K",   "35 / 6,700K",   "—",             true ],
    ["Die Attach", "87", "81",  "6,200","81 / 6,200K",   "—",             "—",             true ],
    ["Wire Bond",  "519","500", "6,400","500 / 6,400K",  "502 / 6,450K",  "504 / 6,500K",  true ],
    ["Mold",       "36", "38",  "6,700","—",             "—",             "—",             false],
    ["Plating",    "4",  "3",   "5,500","4 / 6,700K",    "—",             "—",             true ],
    ["Laser Mark", "18", "17",  "6,700","—",             "—",             "—",             false],
    ["Trim & Form","25", "25",  "6,700","—",             "—",             "—",             false],
    ["Saw QFN",    "42", "42",  "6,700","—",             "—",             "—",             false],
  ];

  const tableData=[
    [
      hdrCell("Process"),hdrCell("Before\n(MC)"),hdrCell("Current\n(MC)"),
      hdrCell("Cap Now\n(K)"),
      hdrCell("Apr '26\nMC / Cap(K)"),hdrCell("May '26\nMC / Cap(K)"),hdrCell("Jun '26\nMC / Cap(K)"),
    ],
    ...rows.map((r,idx)=>{
      const bg=idx%2===0?"F4F7FB":C.white;
      const isOK=!r[7];
      const curr=parseInt(r[2]), bef=parseInt(r[1]);
      const capColor=r[3]==="6,700"?C.green:C.red;
      const currColor= curr>bef?C.green : (isOK?C.green:C.navy);
      const mc=(v)=>(v==="—"?C.muted:C.green);
      return[
        {text:r[0], options:{fill:{color:bg},align:"left",  bold:true, valign:"middle"}},
        {text:r[1], options:{fill:{color:bg},align:"center",valign:"middle"}},
        {text:r[2]+(curr>bef?" ▲":""), options:{fill:{color:bg},align:"center",bold:true,color:currColor,valign:"middle"}},
        {text:r[3], options:{fill:{color:bg},align:"center",bold:true,color:capColor,valign:"middle"}},
        {text:r[4], options:{fill:{color:bg},align:"center",fontSize:10,color:mc(r[4]),valign:"middle"}},
        {text:r[5], options:{fill:{color:bg},align:"center",fontSize:10,color:mc(r[5]),valign:"middle"}},
        {text:r[6], options:{fill:{color:bg},align:"center",fontSize:10,color:mc(r[6]),bold:r[7]&&r[6]!=="—",valign:"middle"}},
      ];
    }),
  ];
  s.addTable(tableData,{
    x:0.35,y:tY,w:12.6,h:4.1,
    fontFace:"Calibri",fontSize:11,
    border:{pt:0.5,color:C.border},rowH:0.40,
    colW:[1.8,1.15,1.2,1.15,2.45,2.45,2.4],
  });
  s.addText("Green = 6,700K Target   Red Cap = Below target   ▲ = Machines Added", {
    x:0.35,y:6.88,w:9,h:0.2,
    fontSize:8.5,color:C.muted,fontFace:"Calibri",align:"left"
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 3 – CAPACITY RECOVERY CHART
// ═══════════════════════════════════════════════════════════════════════════
{
  const s=pres.addSlide();
  hdr(s,"Capacity Recovery Roadmap","SAW · Die Attach · Wire Bond  |  K units/month");
  footer(s,3);
  s.addChart(pres.charts.LINE,[
    {name:"SAW Wafer",labels:["Before","Current","Apr '26","May '26","Jun '26"],values:[6700,5550,6300,6700,6700]},
    {name:"Die Attach",labels:["Before","Current","Apr '26","May '26","Jun '26"],values:[6700,6200,6200,6200,6200]},
    {name:"Wire Bond", labels:["Before","Current","Apr '26","May '26","Jun '26"],values:[6700,6400,6400,6450,6500]},
  ],{
    x:0.4,y:1.15,w:12.5,h:5.6,
    chartColors:[C.orange,C.green,C.blue],
    lineSize:3,lineSmooth:false,
    showValue:true,dataLabelPosition:"t",
    dataLabelColor:C.text,dataLabelFontSize:10,dataLabelFontBold:true,
    dataLabelFontFace:"Calibri",
    showLegend:true,legendPos:"b",legendFontSize:11,legendFontFace:"Calibri",
    catAxisLabelColor:C.muted,valAxisLabelColor:C.muted,
    catAxisLabelFontFace:"Calibri",valAxisLabelFontFace:"Calibri",
    catAxisLabelFontSize:12,valAxisLabelFontSize:10,
    valAxisMinVal:5000,valAxisMaxVal:7200,
    valGridLine:{color:"E2E8F0",size:0.5},catGridLine:{style:"none"},
    chartArea:{fill:{color:C.offwhite},roundedCorners:false},
    plotArea:{fill:{color:C.offwhite}},
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 4 – SAW + BG STATUS
// ═══════════════════════════════════════════════════════════════════════════
{
  const s=pres.addSlide();
  hdr(s,"SAW Machine Status","Before: 35 MC → Current: 29 MC  |  BG: 3/3 On Track");
  footer(s,4);

  const kpis=[
    {val:"35",    lbl:"Total Before",           accent:C.blue  },
    {val:"29",    lbl:"Current Active",          accent:C.green },
    {val:"6",     lbl:"Shutdown\n(AD3000)",       accent:C.red,  vc:C.red   },
    {val:"+2/wk", lbl:"Turn-On Rate\n(WW03–05)",  accent:C.orange},
    {val:"May '26",lbl:"Full Recovery\nTarget",  accent:C.green },
  ];
  // [process, model, before, current, statusColor, remark, apr26, may26]
  const rows=[
    ["BG", "DFG841",    "1",  "1",  C.green, "",                                                       "1",  "1"],
    ["BG", "DFG8540",   "1",  "1",  C.green, "",                                                       "1",  "1"],
    ["BG", "DGP8761",   "1",  "1",  C.green, "",                                                       "1",  "1"],
    ["SAW","DFD640",    "4",  "4",  C.green, "",                                                       "4",  "4"],
    ["SAW","DFD6560",   "6",  "6",  C.green, "",                                                       "6",  "6"],
    ["SAW","AD3000",    "25", "19", C.red,   "DS46,47,48,51,52,53 shutdown  |  +2 M/C/week (WW03/04/05)","23", "25"],
  ];
  const totalRow=[
    {text:"TOTAL",options:{colspan:2,bold:true,fill:{color:C.lightBlue},color:C.navy,align:"center",valign:"middle"}},
    {text:"38",   options:{bold:true,fill:{color:C.lightBlue},color:C.navy, align:"center",valign:"middle"}},
    {text:"32",   options:{bold:true,fill:{color:C.lightBlue},color:C.navy, align:"center",valign:"middle"}},
    {text:"",     options:{fill:{color:C.lightBlue}}},
    {text:"Turn-on plan: +2 M/C/week  |  WW03: 21  |  WW04: 23  |  WW05: 25 (full recovery SAW)",
      options:{bold:true,fill:{color:C.lightBlue},color:C.navy,align:"left",fontSize:9.5,valign:"middle"}},
    {text:"33+3=36",options:{bold:true,fill:{color:C.lightBlue},color:C.green,align:"center",valign:"middle"}},
    {text:"38",   options:{bold:true,fill:{color:C.lightBlue},color:C.green,align:"center",valign:"middle"}},
  ];
  sawStyleTable(s,kpis,rows,totalRow);
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 5 – DIE ATTACH STATUS
// ═══════════════════════════════════════════════════════════════════════════
{
  const s=pres.addSlide();
  hdr(s,"Die Attach Machine Status","Original: 87 MC (6 decommissioned)  →  Active: 81 MC  |  Max Cap: 6,200K");
  footer(s,5);

  const kpis=[
    {val:"87",    lbl:"Original Fleet",           accent:C.blue  },
    {val:"81",    lbl:"Current Active\n(all running)", accent:C.green},
    {val:"6,200K",lbl:"Max Cap\n(perm. reduced)",  accent:C.orange, vc:C.orange},
    {val:"0",     lbl:"M/Cs Offline\n(all OK)",    accent:C.green },
    {val:"38",    lbl:"Tech H/C\n(was 40)",        accent:C.muted },
  ];
  // All 81 active machines listed; before=current per model
  const rows=[
    ["DA","AD8312",    "6",  "6",  C.green, "",                                        "6",  "6"],
    ["DA","AD8312PLUS","10", "10", C.green, "",                                        "10", "10"],
    ["DA","AD832I",    "27", "27", C.green, "",                                        "27", "27"],
    ["DA","AD838",     "29", "29", C.green, "",                                        "29", "29"],
    ["DA","AD889",     "3",  "3",  C.green, "2 units decommissioned (DA-52/53)",       "3",  "3"],
    ["DA","AD898",     "5",  "5",  C.green, "1 unit decommissioned (DA-38)",           "5",  "5"],
    ["DA","E8002",     "1",  "1",  C.green, "4 units decommissioned (DA-25/29/30/32)", "1",  "1"],
  ];
  const totalRow=[
    {text:"TOTAL",options:{colspan:2,bold:true,fill:{color:C.lightBlue},color:C.navy,align:"center",valign:"middle"}},
    {text:"87*",  options:{bold:true,fill:{color:C.lightBlue},color:C.navy, align:"center",valign:"middle"}},
    {text:"81",   options:{bold:true,fill:{color:C.lightBlue},color:C.green,align:"center",valign:"middle"}},
    {text:"",     options:{fill:{color:C.lightBlue}}},
    {text:"*6 M/Cs permanently decommissioned (AD889×2, AD898×1, E8002×3)  |  Max Cap permanently 6,200K",
      options:{bold:true,fill:{color:C.lightBlue},color:C.navy,align:"left",fontSize:9.5,valign:"middle"}},
    {text:"81",   options:{bold:true,fill:{color:C.lightBlue},color:C.green,align:"center",valign:"middle"}},
    {text:"81",   options:{bold:true,fill:{color:C.lightBlue},color:C.green,align:"center",valign:"middle"}},
  ];
  sawStyleTable(s,kpis,rows,totalRow);
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 6 – WIRE BOND STATUS
// ═══════════════════════════════════════════════════════════════════════════
{
  const s=pres.addSlide();
  hdr(s,"Wire Bond Machine Status","Original: 519 MC  →  Fleet: 504 (AB-339 removed)  →  Active: 500 MC");
  footer(s,6);

  const kpis=[
    {val:"504",   lbl:"Current Fleet\n(after AB-339 removal)",accent:C.blue  },
    {val:"500",   lbl:"Currently Active",                      accent:C.green },
    {val:"4",     lbl:"Offline\n(TWIN-AERO LM guide)",         accent:C.orange,vc:C.orange},
    {val:"May '26",lbl:"+2 TWIN-AERO\nrecovery (WW09)",        accent:C.orange},
    {val:"Jun '26",lbl:"Full Recovery\n(504 MC / 6,500K)",     accent:C.green },
  ];
  // Current fleet after AB-339 removal
  const rows=[
    ["WB","AB-339",           "0",  "0",  C.muted, "Removed: 12 scrapped + 3 transferred to SPG",           "0",  "0"],
    ["WB","EAGLE-60",         "41", "41", C.green, "",                                                        "41", "41"],
    ["WB","EAGLE-60AP",       "5",  "5",  C.green, "",                                                        "5",  "5"],
    ["WB","GoCu (SingleHead)","4",  "4",  C.green, "",                                                        "4",  "4"],
    ["WB","HARRIER",          "12", "12", C.green, "",                                                        "12", "12"],
    ["WB","TWIN-GoCu",        "250","250",C.green, "",                                                        "250","250"],
    ["WB","TWIN-AERO",        "192","188",C.orange,"AB210/AB286+2: Bond head LM guide failure  |  +2 May WW09","190","192"],
  ];
  const totalRow=[
    {text:"TOTAL",options:{colspan:2,bold:true,fill:{color:C.lightBlue},color:C.navy,align:"center",valign:"middle"}},
    {text:"504",  options:{bold:true,fill:{color:C.lightBlue},color:C.navy, align:"center",valign:"middle"}},
    {text:"500",  options:{bold:true,fill:{color:C.lightBlue},color:C.navy, align:"center",valign:"middle"}},
    {text:"",     options:{fill:{color:C.lightBlue}}},
    {text:"TWIN-AERO recovery: +2 May (WW09) → +2 Jun  |  Full fleet 504 MC by Jun '26",
      options:{bold:true,fill:{color:C.lightBlue},color:C.navy,align:"left",fontSize:9.5,valign:"middle"}},
    {text:"502",  options:{bold:true,fill:{color:C.lightBlue},color:C.green,align:"center",valign:"middle"}},
    {text:"504",  options:{bold:true,fill:{color:C.lightBlue},color:C.green,align:"center",valign:"middle"}},
  ];
  sawStyleTable(s,kpis,rows,totalRow,"May '26","Jun '26");
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 7 – OTHER PROCESSES (clean card grid)
// ═══════════════════════════════════════════════════════════════════════════
{
  const s=pres.addSlide();
  hdr(s,"Other Processes Status","Mold · Trim & Form · Saw QFN  ✓  |  Plating  ⚠  |  Laser Mark  ⚠");
  footer(s,7);

  // ── Top row: 4 process cards ──────────────────────────────────────────────
  const cards=[
    {
      name:"Mold",mc:"38 MC",sub:"(was 36, +2 added!)",
      cap:"6,700K ✓",capColor:C.green,accent:C.green,
      models:"GP-Hop×3  |  Cosmo×9*  |  GP Pro×10\nGP-ELF×14  |  TOWA×1  |  ASM×1*\n(*Mozart & 84 PLCC added)",
    },
    {
      name:"Trim & Form",mc:"25 / 25",sub:"All OK",
      cap:"6,700K ✓",capColor:C.green,accent:C.green,
      models:"Dejunk: SANTEC×5, APM×1\nT&F: SANTEC×6, HANMI×3, APPLIED×2\nASM×5, GPM×2, APM×1",
    },
    {
      name:"Saw QFN",mc:"42 / 42",sub:"All OK",
      cap:"6,700K ✓",capColor:C.green,accent:C.green,
      models:"AD3000 ×15\nAD3000 Plus ×27",
    },
    {
      name:"Plating",mc:"3 / 4",sub:"1 Offline (buy-off)",
      cap:"5,500K ⚠",capColor:C.orange,accent:C.orange,
      models:"Technic AB ×1 offline (buy-off)\nMeco ×2  |  Deflash ×2  |  Hi-Press ×3",
    },
  ];

  cards.forEach((p,i)=>{
    const cx=0.35+i*3.15, cy=1.1, cw=3.0, ch=2.55;
    s.addShape(pres.shapes.RECTANGLE,{x:cx+0.04,y:cy+0.04,w:cw,h:ch,fill:{color:"D1DDEF",transparency:55},line:{color:"D1DDEF",transparency:55}});
    s.addShape(pres.shapes.RECTANGLE,{x:cx,y:cy,w:cw,h:ch,fill:{color:C.white},line:{color:C.border,width:1}});
    s.addShape(pres.shapes.RECTANGLE,{x:cx,y:cy,w:cw,h:0.07,fill:{color:p.accent},line:{color:p.accent}});
    s.addText(p.name,{x:cx,y:cy+0.07,w:cw,h:0.42,fontSize:15,bold:true,color:C.navy,fontFace:"Calibri",align:"center",valign:"middle"});
    s.addShape(pres.shapes.LINE,{x:cx+0.15,y:cy+0.52,w:cw-0.3,h:0,line:{color:C.border,width:0.5}});
    s.addText(p.mc,{x:cx,y:cy+0.55,w:cw,h:0.55,fontSize:26,bold:true,color:p.accent,fontFace:"Calibri",align:"center",valign:"middle"});
    s.addText(p.sub,{x:cx,y:cy+1.1,w:cw,h:0.25,fontSize:10,color:p.accent,fontFace:"Calibri",align:"center",valign:"middle",bold:p.accent===C.orange});
    s.addText("Cap: "+p.cap,{x:cx,y:cy+1.38,w:cw,h:0.28,fontSize:11,bold:true,color:p.capColor,fontFace:"Calibri",align:"center",valign:"middle"});
    s.addText(p.models,{x:cx+0.1,y:cy+1.7,w:cw-0.2,h:ch-1.76,fontSize:8.5,color:C.muted,fontFace:"Calibri",align:"center",valign:"top"});
  });

  // ── Bottom: Laser Mark panel ──────────────────────────────────────────────
  const lmY=3.88, lmH=3.08;
  s.addShape(pres.shapes.RECTANGLE,{x:0.35,y:lmY,w:12.6,h:lmH,fill:{color:C.white},line:{color:C.border,width:1}});
  s.addShape(pres.shapes.RECTANGLE,{x:0.35,y:lmY,w:12.6,h:0.42,fill:{color:C.orange},line:{color:C.orange}});
  s.addText("⚠  Laser Mark  |  17 / 17 MC Active  |  M#04: Cut / Double-Mark Issue  |  Scanner Replacement: Jun '26", {
    x:0.45,y:lmY,w:12.3,h:0.42,
    fontSize:12,bold:true,color:C.white,fontFace:"Calibri",valign:"middle",margin:0
  });

  // Model table
  const lmTbl=[
    [hdrCell("Model"),hdrCell("Before"),hdrCell("Current"),hdrCell("Status")],
    ...[
      ["Mark EO Technic","10","10"],["Mark Dong Yang","3","3"],
      ["GPM Mark","2","2"],["STI Mark","1","1"],["HANS","1","1"],
    ].map((r,i)=>{
      const bg=i%2===0?"F4F7FB":C.white;
      return[
        {text:r[0],options:{fill:{color:bg},align:"left",bold:true,valign:"middle"}},
        {text:r[1],options:{fill:{color:bg},align:"center",valign:"middle"}},
        {text:r[2],options:{fill:{color:bg},align:"center",bold:true,color:C.green,valign:"middle"}},
        {text:"OK", options:{fill:{color:bg},align:"center",bold:true,color:C.green,valign:"middle"}},
      ];
    }),
    [hdrCell("TOTAL"),
      {text:"17",options:{bold:true,fill:{color:C.lightBlue},color:C.navy,align:"center",valign:"middle"}},
      {text:"17",options:{bold:true,fill:{color:C.lightBlue},color:C.green,align:"center",valign:"middle"}},
      {text:"",  options:{fill:{color:C.lightBlue}}},
    ],
  ];
  s.addTable(lmTbl,{
    x:0.45,y:lmY+0.52,w:5.5,h:2.4,
    fontFace:"Calibri",fontSize:11,
    border:{pt:0.5,color:C.border},rowH:0.39,
    colW:[2.4,1.0,1.0,1.1],
  });

  // Vertical divider
  s.addShape(pres.shapes.LINE,{x:6.25,y:lmY+0.52,w:0,h:lmH-0.62,line:{color:C.border,width:0.8}});

  // Right: issue detail + recovery plan
  s.addText("M#04 Issue & Recovery Plan",{
    x:6.45,y:lmY+0.52,w:6.2,h:0.32,
    fontSize:11,bold:true,color:C.navy,fontFace:"Calibri"
  });
  const issueTable=[
    [hdrCell("Machine"),hdrCell("Issue"),hdrCell("Plan"),hdrCell("Target")],
    ...[
      ["M#04","Cut mark / Double mark defect","Replace scanner unit","Jun '26"],
    ].map((r,i)=>{
      const bg=i%2===0?"F4F7FB":C.white;
      return[
        {text:r[0],options:{fill:{color:bg},align:"center",bold:true,color:C.orange,valign:"middle"}},
        {text:r[1],options:{fill:{color:bg},align:"left",  fontSize:10,valign:"middle"}},
        {text:r[2],options:{fill:{color:bg},align:"left",  fontSize:10,valign:"middle"}},
        {text:r[3],options:{fill:{color:bg},align:"center",bold:true,color:C.orange,valign:"middle"}},
      ];
    }),
  ];
  s.addTable(issueTable,{
    x:6.45,y:lmY+0.85,w:6.2,h:0.76,
    fontFace:"Calibri",fontSize:11,
    border:{pt:0.5,color:C.border},rowH:0.38,
    colW:[1.0,2.2,1.9,1.1],
  });

  // Plating recovery detail
  s.addText("Plating Recovery Plan",{
    x:6.45,y:lmY+1.72,w:6.2,h:0.32,
    fontSize:11,bold:true,color:C.navy,fontFace:"Calibri"
  });
  const pltTable=[
    [hdrCell("Machine"),hdrCell("Issue"),hdrCell("Plan"),hdrCell("Target")],
    ...[
      ["Technic AB","Shutdown – on buy-off process","Complete buy-off → restart","Apr WW04"],
    ].map((r,i)=>{
      const bg="F4F7FB";
      return[
        {text:r[0],options:{fill:{color:bg},align:"center",bold:true,color:C.orange,valign:"middle"}},
        {text:r[1],options:{fill:{color:bg},align:"left",  fontSize:10,valign:"middle"}},
        {text:r[2],options:{fill:{color:bg},align:"left",  fontSize:10,valign:"middle"}},
        {text:r[3],options:{fill:{color:bg},align:"center",bold:true,color:C.green,valign:"middle"}},
      ];
    }),
  ];
  s.addTable(pltTable,{
    x:6.45,y:lmY+2.05,w:6.2,h:0.76,
    fontFace:"Calibri",fontSize:11,
    border:{pt:0.5,color:C.border},rowH:0.38,
    colW:[1.0,2.2,1.9,1.1],
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 8 – KEY ACTIONS & NEXT STEPS
// ═══════════════════════════════════════════════════════════════════════════
{
  const s=pres.addSlide();
  hdr(s,"Key Actions & Next Steps","As of April 2026");
  footer(s,8);

  const panels=[
    {
      title:"SAW",
      color:C.orange,
      lines:[
        "6 units (AD3000: DS46,47,48,51,52,53) shut down",
        "Recovery plan: +2 M/C per week (WW03, WW04, WW05)",
        "WW03: 21 active  |  WW04: 23 active  |  WW05: 25 (full SAW)",
        "Full recovery by May '26 (SAW: 35 MC / 6,700K)",
        "BG (3 MC) stable, no issues",
      ],
    },
    {
      title:"Die Attach",
      color:C.green,
      lines:[
        "All 81 active machines currently running (0 offline)",
        "6 machines permanently decommissioned from original fleet of 87",
        "AD889×2 (DA-52/53)  |  AD898×1 (DA-38)  |  E8002×3 (DA-25/29/30/32)",
        "Max capacity permanently reduced: 6,700K → 6,200K",
        "DA stable — no recovery actions needed, capacity accepted at 6.2M",
      ],
    },
    {
      title:"Wire Bond",
      color:C.blue,
      lines:[
        "AB-339 removed from fleet (12 scrapped + 3 transferred to SPG)",
        "TWIN-AERO: 4 heads offline — bond head LM guide failure (AB210, AB286 +2)",
        "Recovery: +2 in May '26 (WW09)  |  +2 in Jun '26",
        "Full WB fleet active: Jun '26 (504 MC / 6,500K)",
        "Tech H/C: W/B has 4 current vs 10 approved — 6 vacancies to fill",
      ],
    },
  ];

  panels.forEach((p,i)=>{
    const px=0.35+i*4.3, py=1.2, pw=4.1, ph=5.8;
    s.addShape(pres.shapes.RECTANGLE,{x:px,y:py,w:pw,h:ph,fill:{color:C.white},line:{color:C.border,width:1}});
    s.addShape(pres.shapes.RECTANGLE,{x:px,y:py,w:pw,h:0.07,fill:{color:p.color},line:{color:p.color}});
    s.addText(p.title,{x:px,y:py+0.1,w:pw,h:0.5,fontSize:16,bold:true,color:p.color,fontFace:"Calibri",align:"center",valign:"middle"});
    s.addShape(pres.shapes.LINE,{x:px+0.2,y:py+0.65,w:pw-0.4,h:0,line:{color:C.border,width:0.5}});
    const bullets=p.lines.map((l,li)=>({text:l,options:{bullet:true,breakLine:li<p.lines.length-1}}));
    s.addText(bullets,{x:px+0.12,y:py+0.75,w:pw-0.24,h:ph-0.95,fontSize:11,color:C.text,fontFace:"Calibri",valign:"top",paraSpaceAfter:6});
  });
}

// ─── Save ──────────────────────────────────────────────────────────────────
pres.writeFile({fileName:"Output/MMT_Machine_Status_Report.pptx"})
  .then(()=>console.log("Saved: Output/MMT_Machine_Status_Report.pptx"))
  .catch(err=>{console.error(err);process.exit(1);});
