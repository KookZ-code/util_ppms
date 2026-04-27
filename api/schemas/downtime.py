"""Downtime endpoint schemas."""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class DowntimeEvent(BaseModel):
    machine_id: str
    area: str
    job_type: str
    symptom: Optional[str] = None
    cause: Optional[str] = None
    action: Optional[str] = None
    technician: Optional[str] = None
    package_type: Optional[str] = None
    lot_number: Optional[str] = None
    die_mask: Optional[str] = None
    opr_start: Optional[datetime] = None
    tech_start: Optional[datetime] = None
    end_time: Optional[datetime] = None
    wait_min: int = 0
    repair_min: int = 0
    shift: Optional[str] = None
    source: str = Field('sql', description="'sql' or 'oracle'")


class DowntimeEventList(BaseModel):
    events: List[DowntimeEvent]
    total: int
    period: dict


class ParetoRow(BaseModel):
    reason: str
    events: int
    repair_hrs: float
    wait_hrs: float
    total_hrs: float
    avg_repair_min: float
    avg_wait_min: float
    max_wait_min: float


class ParetoData(BaseModel):
    rows: List[ParetoRow]
    total_events: int
    total_hours: float
    period: dict
