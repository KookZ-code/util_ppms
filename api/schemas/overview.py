"""Overview endpoint schemas."""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel


class KPIData(BaseModel):
    total_machines: int
    running: int
    down: int
    waiting: int
    on_process: int
    closed_this_shift: int


class StatusMatrixRow(BaseModel):
    job_type: str
    waiting: int
    on_process: int
    closed: int
    total: int


class OverviewData(BaseModel):
    kpi: KPIData
    status_matrix: List[StatusMatrixRow]
    updated_at: str


class OpenJob(BaseModel):
    code_machine: str
    area: Optional[str] = None
    job_type: str
    des_job: Optional[str] = None
    datex: Optional[datetime] = None
    date_ack: Optional[datetime] = None
    tech: Optional[str] = None
    wait_min: Optional[int] = None
    repair_min: Optional[int] = None
    status: str
    die_mask: Optional[str] = None
    die_size: Optional[str] = None
    package_type: Optional[str] = None
    wire_type: Optional[str] = None
    source: str = 'sql'


class OpenJobsData(BaseModel):
    jobs: List[OpenJob]
    total: int
