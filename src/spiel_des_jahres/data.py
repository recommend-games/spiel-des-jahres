import dataclasses
from datetime import datetime


@dataclasses.dataclass(frozen=True, kw_only=True)
class Rating:
    bgg_id: int
    bgg_user_name: str
    bgg_user_rating: float
    updated_at: datetime
    scraped_at: datetime
