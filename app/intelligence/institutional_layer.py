"""Backward-compatible import surface for the institutional expansion layer.

The implementation now lives under `app.intelligence.institutional` as a
multi-module package so each subsystem can evolve independently.
"""

from app.intelligence.institutional import InstitutionalExpansionLayer
from app.intelligence.institutional.schemas import *

__all__ = ["InstitutionalExpansionLayer"]
