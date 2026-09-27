from datetime import date

from pydantic import BaseModel


class RuntimeRead(BaseModel):
    timezone: str
    local_date: date
