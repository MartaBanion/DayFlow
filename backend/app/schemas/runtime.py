from datetime import date

from pydantic import BaseModel


class RuntimeRead(BaseModel):
    timezone: str
    local_date: date
    app_version: str
    database_schema: str | None
