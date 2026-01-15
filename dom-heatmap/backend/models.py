from pydantic import BaseModel
from typing import List, Dict, Optional
from enum import Enum

class Side(str, Enum):
    BID = "bid"
    ASK = "ask"

class OrderUpdate(BaseModel):
    price: float
    size: int
    side: Side
    id: str  # Order ID (for tracking specific orders if needed, though heat map aggregates often)

class PriceLevel(BaseModel):
    price: float
    size: int
    order_count: int
    heat_intensity: float = 0.0  # 0.0 to 1.0

class DomSnapshot(BaseModel):
    bids: List[PriceLevel]
    asks: List[PriceLevel]
    symbol: str
    timestamp: float

class DomUpdate(BaseModel):
    """Incremental update for the frontend"""
    type: str # 'snapshot' or 'delta'
    data: DomSnapshot
