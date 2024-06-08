from datetime import datetime
from typing import Any


def json_datetime(obj: Any) -> str:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"{obj} is not JSON serializable")
