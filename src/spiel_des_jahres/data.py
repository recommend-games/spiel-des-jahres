import dataclasses
from datetime import datetime


@dataclasses.dataclass(frozen=True, kw_only=True)
class User:
    bgg_user_name: str
    first_name: str | None = None
    last_name: str | None = None
    updated_at: datetime
    scraped_at: datetime


@dataclasses.dataclass(frozen=True, kw_only=True)
class Rating:
    bgg_id: int
    bgg_user_name: str
    bgg_user_rating: float
    updated_at: datetime
    scraped_at: datetime


@dataclasses.dataclass(frozen=True, kw_only=True)
class AwardRatings:
    winner_rating: float = 10.0
    nominated_rating: float = 8.0
    recommended_rating: float = 7.0
    sonderpreis_rating: float = 9.0
