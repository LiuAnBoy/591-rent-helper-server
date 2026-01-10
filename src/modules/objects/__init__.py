"""Objects module."""

from src.modules.objects.models import (
    RentalObject,
    Surrounding,
)
from src.modules.objects.repository import ObjectRepository

__all__ = [
    "RentalObject",
    "Surrounding",
    "ObjectRepository",
]
