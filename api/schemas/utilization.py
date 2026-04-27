"""Utilization endpoint schemas."""
from typing import List, Optional
from pydantic import BaseModel, Field


class UtilizationKPI(BaseModel):
    utilization_pct: float = Field(description='% utilization (running time / total time)')
    downtime_pct: float = Field(description='% M/C DOWN + PM time')
    lost_time_pct: float = Field(description='% setup/convert/etc. time + waiting')
    total_machines: int
    total_hours: float = Field(description='Sum of all machine-hours in the period')
    downtime_hours: float
    lost_time_hours: float


class AreaUtilization(BaseModel):
    area: str
    machines: int
    utilization_pct: float
    downtime_pct: float
    lost_time_pct: float
    target_pct: Optional[int] = None


class UtilizationData(BaseModel):
    kpi: UtilizationKPI
    by_area: List[AreaUtilization]
    period: dict  # {'start': ..., 'end': ..., 'shift': ...}
