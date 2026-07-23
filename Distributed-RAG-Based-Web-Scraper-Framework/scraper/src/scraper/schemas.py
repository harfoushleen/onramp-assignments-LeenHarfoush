"""Pydantic schema for the normalized output of the processing step.

Validated before a ProcessedPage row is ever written, so a malformed record
fails loudly at processing time instead of silently landing bad data in the
processed_pages table.
"""

from pydantic import BaseModel, ConfigDict, Field


class ProcessedRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    tables: list[dict[str, str]] = Field(default_factory=list)
