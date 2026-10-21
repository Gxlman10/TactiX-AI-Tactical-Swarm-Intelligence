"""Primitive value types reused across the domain."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

# Player attribute on the canonical 0-100 scale.
Rating = Annotated[int, Field(ge=0, le=100)]


class Point(BaseModel):
    """A pitch location normalised to a 100x100 grid (attacking left -> right)."""

    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)
