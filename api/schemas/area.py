"""Area endpoint schemas."""
from typing import List, Optional
from pydantic import BaseModel


class Area(BaseModel):
    area: str
    short_name: Optional[str] = None
    source: str  # 'sql' or 'oracle'
    machine_count: int = 0


class AreaListData(BaseModel):
    areas: List[Area]
    total: int
