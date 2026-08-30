"""Synthetic data generation.

Milestone 1 loads a fixed, fabricated catalogue. Phase 9 replaces this with
``SourceAdapter`` implementations; ``catalog.py`` documents the record shape
those adapters must produce.
"""
from .seed import seed_database

__all__ = ["seed_database"]
