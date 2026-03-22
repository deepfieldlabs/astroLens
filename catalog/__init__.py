"""
Catalog Cross-Reference Module

Query astronomical databases to verify anomalies against known objects.
"""

from .cross_reference import (
    CatalogCrossReference,
    CatalogMatch,
    CrossReferenceResult,
    cross_reference_anomaly,
)
from .skymap_export import export_skymap_json

__all__ = [
    "CatalogCrossReference",
    "CatalogMatch",
    "CrossReferenceResult",
    "cross_reference_anomaly",
    "export_skymap_json",
]
