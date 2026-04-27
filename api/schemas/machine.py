"""Machine endpoint schemas."""
from typing import List, Optional
from datetime import datetime, date
from pydantic import BaseModel


class MachineSummary(BaseModel):
    machine_id: str
    des_machine: Optional[str] = None
    area: Optional[str] = None
    area_name: Optional[str] = None
    mfg: Optional[str] = None
    model: Optional[str] = None
    sn: Optional[str] = None
    short_name: Optional[str] = None
    flag_key: Optional[int] = 0
    flag_automotive: Optional[int] = 0
    flag_gold: Optional[int] = 0


class MachineListData(BaseModel):
    machines: List[MachineSummary]
    total: int


class MachineKPI(BaseModel):
    total_events: int
    down_events: int
    avg_mttr_min: Optional[float] = None
    avg_wait_min: Optional[float] = None
    total_down_hrs: Optional[float] = None


class MachineRecentEvent(BaseModel):
    job_type: str
    symptom: Optional[str] = None
    opr_start: Optional[datetime] = None
    end_time: Optional[datetime] = None
    wait_min: int = 0
    repair_min: int = 0
    technician: Optional[str] = None


class MachineDetailData(BaseModel):
    info: MachineSummary
    date_install: Optional[date] = None
    flags: dict
    kpis: MachineKPI
    recent_events: List[MachineRecentEvent]
