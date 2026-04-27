"""Technician performance schemas."""
from typing import List, Optional
from pydantic import BaseModel


class TechScore(BaseModel):
    technician: str
    job_count: int
    avg_response_min: float
    avg_repair_min: float
    area_count: int
    ftfr_pct: float
    mttr_score: float
    response_score: float
    ftfr_score: float
    volume_score: float
    versatility_score: float
    composite_score: float
    grade: str


class TechPerformanceData(BaseModel):
    technicians: List[TechScore]
    total: int
    period: dict
