from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.utils import get_column_letter

wb = Workbook()

# Remove default sheet
default_sheet = wb.active
wb.remove(default_sheet)

# Create sheets
ws_master = wb.create_sheet("Spool_Master")
ws_log = wb.create_sheet("Movement_Log")
ws_list = wb.create_sheet("Dropdown_List")
ws_dash = wb.create_sheet("Dashboard")

# Styles
header_fill = PatternFill("solid", fgColor="1F4E78")
header_font = Font(color="FFFFFF", bold=True)
thin = Side(style="thin", color="CCCCCC")
border = Border(left=thin, right=thin, top=thin, bottom=thin)
center = Alignment(horizontal="center", vertical="center")

status_fills = {
    "IN_STORE": PatternFill("solid", fgColor="C6E0B4"),
    "AT_ENGINEER": PatternFill("solid", fgColor="BDD7EE"),
    "IN_TRIAL": PatternFill("solid", fgColor="FFE699"),
    "HOLD": PatternFill("solid", fgColor="F4B183"),
    "SCRAP": PatternFill("solid", fgColor="F8CBAD"),
    "EMPTY": PatternFill("solid", fgColor="D9D9D9"),
}

# -------------------------
# Dropdown_List sheet
# -------------------------
dropdown_data = {
    "A1": ["Status", "IN_STORE", "ISSUED", "AT_ENGINEER", "AT_MACHINE", "IN_TRIAL", "HOLD", "RETURNED", "EMPTY", "SCRAP", "CLOSED"],
    "D1": ["Move_Type", "RECEIVE", "ISSUE", "HANDOVER", "LOAD_TO_MACHINE", "UNLOAD_FROM_MACHINE", "CONSUME", "WEIGH_UPDATE", "RETURN", "SCRAP", "HOLD", "ADJUSTMENT", "CLOSE"],
    "G1": ["Location", "STORE-A1", "STORE-A2", "ENG LAB", "WB-01", "WB-02", "WB-03", "SCRAP BIN", "QA HOLD"],
    "J1": ["UOM", "gram", "meter", "spool"],
}

for start_cell, values in dropdown_data.items():
    col = ws_list[start_cell].column
    row = ws_list[start_cell].row
    for i, v in enumerate(values, start=row):
        ws_list.cell(i, col, v)

# -------------------------
# Spool_Master sheet
# -------------------------
master_headers = [
    "Spool_ID","Material_Code","Description","Diameter_um","Purity","Supplier","Supplier_Lot","Internal_Lot",
    "Receive_Date","Original_Qty","Current_Qty","UOM","Current_Status","Current_Location","Current_Owner",
    "Last_Trial_ID","Last_Machine_ID","Last_Movement_Date","Final_Result","Remark","Days_No_Movement","Alert"
]
ws_master.append(master_headers)

master_data = [
    ["GW240001","AU-20UM","Gold Wire 20um",20,"99.99%","ABC Metal","SL24001","IL24001","2024-01-15",10,8.8,"gram","IN_STORE","STORE-A1","Store","TR-001","WB-03","2024-01-18 16:00","RETURNED","",None,None],
    ["GW240002","AU-25UM","Gold Wire 25um",25,"99.99%","ABC Metal","SL24002","IL24002","2024-01-16",12,0,"gram","EMPTY","WB-02","Narin","TR-002","WB-02","2024-01-22 11:45","EMPTY","Used up",None,None],
    ["GW240003","AU-20UM","Gold Wire 20um",20,"99.99%","XYZ Precious","SL24003","IL24003","2024-01-18",9.5,9.5,"gram","AT_ENGINEER","ENG LAB","Somchai","TR-003","","2024-01-25 09:00","","",None,None],
    ["GW240004","AU-20UM","Gold Wire 20um",20,"99.99%","XYZ Precious","SL24004","IL24004","2024-01-20",10,7.2,"gram","IN_TRIAL","WB-01","Tech1","TR-004","WB-01","2024-01-25 14:20","","",None,None],
    ["GW240005","AU-30UM","Gold Wire 30um",30,"99.99%","ABC Metal","SL24005","IL24005","2024-01-21",8,8,"gram","IN_STORE","STORE-A2","Store","","","2024-01-21 08:30","","",None,None],
    ["GW240006","AU-20UM","Gold Wire 20um",20,"99.99%","ABC Metal","SL24006","IL24006","2024-01-22",10,6.5,"gram","HOLD","ENG LAB","Narin","TR-005","WB-02","2024-01-24 17:10","","Hold for retest",None,None],
    ["GW240007","AU-25UM","Gold Wire 25um",25,"99.99%","XYZ Precious","SL24007","IL24007","2024-01-22",11,11,"gram","IN_STORE","STORE-A1","Store","","","2024-01-22 10:20","","",None,None],
    ["GW240008","AU-20UM","Gold Wire 20um",20,"99.99%","ABC Metal","SL24008","IL24008","2024-01-23",10,0,"gram","SCRAP","SCRAP BIN","QA","TR-006","WB-03","2024-01-24 15:00","SCRAP","Damaged spool",None,None],
]

for row in master_data:
    ws_master.append(row)

# formulas
for r in range(2, ws_master.max_row + 1):
    ws_master[f"U{r}"] = f'=IF(R{r}="","",TODAY()-INT(R{r}))'
    ws_master[f"V{r}"] = f'=IF(OR(M{r}="EMPTY",M{r}="SCRAP",M{r}="CLOSED"),"Closed",IF(U{r}>7,"No movement > 7 days",IF(K{r}<=0.5,"Low balance","")))'

# -------------------------
# Movement_Log sheet
# -------------------------
log_headers = [
    "Txn_ID","Date","Time","DateTime","Spool_ID","Move_Type","From_Status","To_Status","From_Location","To_Location",
    "Request_By","Approve_By","Receive_By","Machine_ID","Trial_ID","Product_or_Sample",
    "Qty_Before","Qty_Used","Qty_Adjust","Qty_After","UOM","Reason","Remark","Attach_Ref","Input_By","Input_DateTime",
    "Check_Qty","Check_Input","Check_Status"
]
ws_log.append(log_headers)

log_data = [
    ["TXN0001","2024-01-15","09:00","","GW240001","RECEIVE","","IN_STORE","Supplier","STORE-A1","","","Store","","","",0,0,10,"","gram","New receive","","","Store","2024-01-15 09:05","","",""],
    ["TXN0002","2024-01-18","10:15","","GW240001","ISSUE","IN_STORE","AT_ENGINEER","STORE-A1","ENG LAB","Narin","Sup-A","Narin","","TR-001","Sample A",10,0,0,"","gram","Trial use","","","Store","2024-01-18 10:16","","",""],
    ["TXN0003","2024-01-18","11:00","","GW240001","LOAD_TO_MACHINE","AT_ENGINEER","IN_TRIAL","ENG LAB","WB-03","Narin","","Tech1","WB-03","TR-001","Sample A",10,0,0,"","gram","Start trial","","","Tech1","2024-01-18 11:01","","",""],
    ["TXN0004","2024-01-18","15:30","","GW240001","CONSUME","IN_TRIAL","IN_TRIAL","WB-03","WB-03","Narin","","Narin","WB-03","TR-001","Sample A",10,1.2,0,"","gram","Trial consumption","","","Narin","2024-01-18 15:31","","",""],
    ["TXN0005","2024-01-18","16:00","","GW240001","RETURN","AT_ENGINEER","IN_STORE","ENG LAB","STORE-A1","Narin","","Store","","TR-001","Sample A",8.8,0,0,"","gram","Return after trial","","","Store","2024-01-18 16:01","","",""],
    ["TXN0006","2024-01-16","08:45","","GW240002","RECEIVE","","IN_STORE","Supplier","STORE-A1","","","Store","","","",0,0,12,"","gram","New receive","","","Store","2024-01-16 08:46","","",""],
    ["TXN0007","2024-01-20","09:10","","GW240002","ISSUE","IN_STORE","AT_ENGINEER","STORE-A1","ENG LAB","Narin","Sup-A","Narin","","TR-002","Sample B",12,0,0,"","gram","Trial use","","","Store","2024-01-20 09:11","","",""],
    ["TXN0008","2024-01-20","09:40","","GW240002","LOAD_TO_MACHINE","AT_ENGINEER","IN_TRIAL","ENG LAB","WB-02","Narin","","Tech2","WB-02","TR-002","Sample B",12,0,0,"","gram","Start trial","","","Tech2","2024-01-20 09:41","","",""],
    ["TXN0009","2024-01-22","11:45","","GW240002","CONSUME","IN_TRIAL","EMPTY","WB-02","WB-02","Narin","","Narin","WB-02","TR-002","Sample B",12,12,0,"","gram","Used up","","","Narin","2024-01-22 11:46","","",""],
    ["TXN0010","2024-01-18","13:20","","GW240003","RECEIVE","","IN_STORE","Supplier","STORE-A2","","","Store","","","",0,0,9.5,"","gram","New receive","","","Store","2024-01-18 13:21","","",""],
    ["TXN0011","2024-01-25","09:00","","GW240003","ISSUE","IN_STORE","AT_ENGINEER","STORE-A2","ENG LAB","Somchai","Sup-B","Somchai","","TR-003","Sample C",9.5,0,0,"","gram","Engineering trial","","","Somchai","2024-01-25 09:01","","",""],
    ["TXN0012","2024-01-20","08:30","","GW240004","RECEIVE","","IN_STORE","Supplier","STORE-A1","","","Store","","","",0,0,10,"","gram","New receive","","","Store","2024-01-20 08:31","","",""],
    ["TXN0013","2024-01-24","13:00","","GW240004","ISSUE","IN_STORE","AT_ENGINEER","STORE-A1","ENG LAB","Tech1","Sup-A","Tech1","","TR-004","Sample D",10,0,0,"","gram","Trial use","","","Store","2024-01-24 13:01","","",""],
    ["TXN0014","2024-01-25","14:20","","GW240004","LOAD_TO_MACHINE","AT_ENGINEER","IN_TRIAL","ENG LAB","WB-01","Tech1","","Tech1","WB-01","TR-004","Sample D",10,0,0,"","gram","Start trial","","","Tech1","2024-01-25 14:21","","",""],
    ["TXN0015","2024-01-25","15:45","","GW240004","CONSUME","IN_TRIAL","IN_TRIAL","WB-01","WB-01","Tech1","","Tech1","WB-01","TR-004","Sample D",10,2.8,0,"","gram","Trial consumption","","","Tech1","2024-01-25 15:46","","",""],
]

for row_idx, row in enumerate(log_data, start=2):
    ws_log.append(row)
    ws_log[f"D{row_idx}"] = f'=B{row_idx}+C{row_idx}'
    ws_log[f"T{row_idx}"] = f'=Q{row_idx}-R{row_idx}+S{row_idx}'
    ws_log[f"AA{row_idx}"] = f'=IF(T{row_idx}<0,"ERROR: Negative Qty","OK")'
    ws_log[f"AB{row_idx}"] = f'=IF(AND(F{row_idx}="CONSUME",R{row_idx}=""),"Missing Qty_Used","OK")'
    ws_log[f"AC{row_idx}"] = f'=IF(AND(F{row_idx}="SCRAP",H{row_idx}<>"SCRAP"),"Check To_Status",IF(AND(F{row_idx}="RETURN",H{row_idx}<>"IN_STORE"),"Check Return Status","OK"))'

# -------------------------
# Dashboard
# -------------------------
ws_dash["A1"] = "Gold Wire Spool Dashboard"
ws_dash["A1"].font = Font(size=14, bold=True)

dashboard_items = [
    ("A3", "Total Spools", '=COUNTA(Spool_Master!A:A)-1'),
    ("A4", "In Store", '=COUNTIF(Spool_Master!M:M,"IN_STORE")'),
    ("A5", "At Engineer", '=COUNTIF(Spool_Master!M:M,"AT_ENGINEER")'),
    ("A6", "In Trial", '=COUNTIF(Spool_Master!M:M,"IN_TRIAL")'),
    ("A7", "Scrap", '=COUNTIF(Spool_Master!M:M,"SCRAP")'),
    ("A8", "Empty", '=COUNTIF(Spool_Master!M:M,"EMPTY")'),
    ("A9", "No Movement > 7 Days", '=COUNTIF(Spool_Master!U:U,">7")'),
    ("A10", "Total Qty Used", '=SUM(Movement_Log!R:R)'),
]

for cell, label, formula in dashboard_items:
    ws_dash[cell] = label
    ws_dash[cell.replace("A", "B")] = formula

# -------------------------
# Formatting
# -------------------------
for ws in [ws_master, ws_log]:
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border
        cell.alignment = center

    for row in ws.iter_rows():
        for cell in row:
            cell.border = border

# Column widths
widths_master = {
    1:15,2:15,3:20,4:12,5:10,6:15,7:15,8:15,9:15,10:12,11:12,12:10,
    13:15,14:18,15:15,16:12,17:15,18:20,19:15,20:20,21:18,22:25
}
for col_idx, width in widths_master.items():
    ws_master.column_dimensions[get_column_letter(col_idx)].width = width

for col in range(1, 30):
    ws_log.column_dimensions[get_column_letter(col)].width = 15

for col in range(1, 5):
    ws_list.column_dimensions[get_column_letter(col)].width = 18

ws_dash.column_dimensions["A"].width = 25
ws_dash.column_dimensions["B"].width = 18

# Data validation
dv_status = DataValidation(type="list", formula1="=Dropdown_List!$A$2:$A$11", allow_blank=True)
dv_move = DataValidation(type="list", formula1="=Dropdown_List!$D$2:$D$13", allow_blank=True)
dv_location = DataValidation(type="list", formula1="=Dropdown_List!$G$2:$G$9", allow_blank=True)
dv_uom = DataValidation(type="list", formula1="=Dropdown_List!$J$2:$J$4", allow_blank=True)

ws_log.add_data_validation(dv_status)
ws_log.add_data_validation(dv_move)
ws_log.add_data_validation(dv_location)
ws_log.add_data_validation(dv_uom)

dv_move.add(f"F2:F500")
dv_status.add(f"G2:H500")
dv_location.add(f"I2:J500")
dv_uom.add(f"U2:U500")

# Conditional formatting for Spool_Master status
for status, fill in status_fills.items():
    ws_master.conditional_formatting.add(
        "M2:M500",
        FormulaRule(formula=[f'M2="{status}"'], fill=fill)
    )

# Conditional formatting for alerts
red_fill = PatternFill("solid", fgColor="FFC7CE")
yellow_fill = PatternFill("solid", fgColor="FFEB9C")

ws_master.conditional_formatting.add("V2:V500",
    FormulaRule(formula=['ISNUMBER(SEARCH("No movement",V2))'], fill=red_fill)
)
ws_master.conditional_formatting.add("V2:V500",
    FormulaRule(formula=['ISNUMBER(SEARCH("Low balance",V2))'], fill=yellow_fill)
)

# Negative qty highlight
ws_log.conditional_formatting.add("AA2:AA500",
    FormulaRule(formula=['AA2="ERROR: Negative Qty"'], fill=red_fill)
)

# Freeze panes
ws_master.freeze_panes = "A2"
ws_log.freeze_panes = "A2"
ws_dash.freeze_panes = "A3"

# Save
filename = "Gold_Wire_Spool_Tracking.xlsx"
wb.save(filename)
print(f"Created: {filename}")
