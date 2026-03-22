"""
Skymap export — produce a coordinate-enriched JSON for MitraSETI's unified sky map.

Reads AstroLens discovery outputs (anomaly_candidates.json, cross_reference_results.json,
ZTF transient metadata) and emits a flat list of detections with RA/Dec coordinates
suitable for overlay on MitraSETI's radio sky map.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_RA_DEC_PATTERNS = [
    re.compile(r"ra([-+]?\d+\.?\d*)_dec([-+]?\d+\.?\d*)", re.IGNORECASE),
    re.compile(r"ra_([-+]?\d+\.?\d*)_dec_([-+]?\d+\.?\d*)", re.IGNORECASE),
]


def _extract_coords_from_path(image_path: str) -> Optional[Tuple[float, float]]:
    """Parse RA/Dec from an image filename (e.g. '…_ra206.887_dec41.529.jpg')."""
    filename = Path(image_path).name
    for pattern in _RA_DEC_PATTERNS:
        m = pattern.search(filename)
        if m:
            return float(m.group(1)), float(m.group(2))
    return None


def _load_ztf_coords(transient_dir: Path) -> Dict[str, Tuple[float, float]]:
    """Build a lookup of ZTF region filenames → (RA, Dec) from transient metadata JSONs."""
    coords: Dict[str, Tuple[float, float]] = {}
    downloads = transient_dir / "downloads" / "ztf"
    if not downloads.is_dir():
        return coords
    for meta_file in downloads.glob("ztf_*.json"):
        try:
            with open(meta_file) as f:
                meta = json.load(f)
            ra = meta.get("ra")
            dec = meta.get("dec")
            ztf_id = meta.get("ztf_id", "")
            if ra is not None and dec is not None and ztf_id:
                coords[ztf_id] = (float(ra), float(dec))
        except Exception:
            continue
    return coords


def export_skymap_json(
    artifacts_dir: str | Path,
    output_path: Optional[str | Path] = None,
) -> List[Dict[str, Any]]:
    """Generate a skymap-ready JSON from AstroLens discovery artifacts.

    Args:
        artifacts_dir: Path to astrolens_artifacts/ (contains data/, transient_data/).
        output_path: Where to write the JSON. Defaults to
                     ``<artifacts_dir>/data/skymap_export.json``.

    Returns:
        List of dicts, each with ``ra_deg``, ``dec_deg``, and detection metadata.
    """
    artifacts_dir = Path(artifacts_dir)
    candidates_file = artifacts_dir / "data" / "anomaly_candidates.json"
    xref_file = artifacts_dir / "data" / "cross_reference_results.json"
    transient_dir = artifacts_dir / "transient_data"

    if output_path is None:
        output_path = artifacts_dir / "data" / "skymap_export.json"
    output_path = Path(output_path)

    ztf_coords = _load_ztf_coords(transient_dir)
    xref_coords: Dict[str, Tuple[float, float]] = {}

    if xref_file.exists():
        try:
            with open(xref_file) as f:
                xrefs = json.load(f)
            for xr in xrefs if isinstance(xrefs, list) else []:
                ip = xr.get("image_path", "")
                ra = xr.get("query_ra")
                dec = xr.get("query_dec")
                if ip and ra is not None and dec is not None:
                    xref_coords[Path(ip).name] = (float(ra), float(dec))
        except Exception as e:
            logger.warning("Failed to read cross-reference results: %s", e)

    results: List[Dict[str, Any]] = []

    if not candidates_file.exists():
        logger.warning("No anomaly_candidates.json found at %s", candidates_file)
        return results

    try:
        with open(candidates_file) as f:
            candidates = json.load(f)
    except Exception as e:
        logger.error("Failed to read anomaly_candidates.json: %s", e)
        return results

    for cand in candidates if isinstance(candidates, list) else []:
        image_path = cand.get("image_path", "")
        filename = Path(image_path).name

        ra, dec = None, None

        coords = _extract_coords_from_path(image_path)
        if coords:
            ra, dec = coords

        if ra is None and filename in xref_coords:
            ra, dec = xref_coords[filename]

        if ra is None:
            for ztf_id, zcoords in ztf_coords.items():
                if ztf_id in filename:
                    ra, dec = zcoords
                    break

        if ra is None:
            continue

        results.append(
            {
                "ra_deg": ra,
                "dec_deg": dec,
                "ood_score": cand.get("ood_score", 0.0),
                "classification": cand.get("classification", "unknown"),
                "confidence": cand.get("confidence", 0.0),
                "source": cand.get("source", "astrolens"),
                "is_transient": cand.get("is_transient_source", False),
                "yolo_confirmed": cand.get("yolo_confirmed", False),
                "detected_at": cand.get("detected_at", ""),
                "image_path": image_path,
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    logger.info(
        "Exported %d AstroLens detections with coordinates to %s "
        "(skipped %d without coords)",
        len(results),
        output_path,
        len(candidates) - len(results) if isinstance(candidates, list) else 0,
    )

    return results


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Export AstroLens detections for sky map")
    parser.add_argument(
        "--artifacts-dir",
        default=str(Path(__file__).parent.parent.parent / "astrolens_artifacts"),
        help="Path to astrolens_artifacts/",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON path (default: <artifacts>/data/skymap_export.json)",
    )
    args = parser.parse_args()
    results = export_skymap_json(args.artifacts_dir, args.output)
    print(f"Exported {len(results)} detections")
