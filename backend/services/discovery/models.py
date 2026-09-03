from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class NormalizedCandidate:
    source_url: str
    source_platform: str
    source_id: Optional[str] = None
    title: Optional[str] = None
    source_channel: Optional[str] = None
    duration: Optional[float] = None
    thumbnail_url: Optional[str] = None
    published_date: Optional[datetime] = None
    description: Optional[str] = None
    
    # V4 Relevance fields
    relevance_score: float = 0.0
    is_short: bool = False
    source_type: str = "UNKNOWN"
    rejection_reason: Optional[str] = None
