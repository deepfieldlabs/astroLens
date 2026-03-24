"""
Test suite for AstroLens <-> MitraSETI integration.

Tests:
- SETISignalAnalyzer loads MitraSETI radio candidates
- Angular separation calculation
- Skymap export JSON schema
- Coordinate extraction from image filenames
"""

import json
import math
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestAngularSeparation:
    """Test Haversine angular separation helper."""

    def test_same_point_is_zero(self):
        from features.seti_signals import SETISignalAnalyzer

        sep = SETISignalAnalyzer._angular_separation_arcmin(
            180.0, 45.0, 180.0, 45.0
        )
        assert sep == pytest.approx(0.0, abs=1e-6)

    def test_known_separation(self):
        from features.seti_signals import SETISignalAnalyzer

        sep = SETISignalAnalyzer._angular_separation_arcmin(
            0.0, 0.0, 1.0, 0.0
        )
        assert sep == pytest.approx(60.0, abs=0.1)

    def test_poles(self):
        from features.seti_signals import SETISignalAnalyzer

        sep = SETISignalAnalyzer._angular_separation_arcmin(
            0.0, 90.0, 180.0, 90.0
        )
        assert sep == pytest.approx(0.0, abs=0.01)


class TestMitraSETIDataLoading:
    """Test loading radio candidates from MitraSETI artifacts."""

    def test_loads_candidates_from_json(self, tmp_path):
        from features.seti_signals import SETISignalAnalyzer

        candidates_dir = tmp_path / "data"
        candidates_dir.mkdir()
        state_file = candidates_dir / "streaming_state.json"
        state_file.write_text(json.dumps({
            "candidates": [
                {
                    "source_name": "TRAPPIST-1",
                    "ra": 346.622,
                    "dec": -5.041,
                    "frequency_hz": 1420405000.0,
                    "drift_rate": 0.38,
                    "is_candidate": True,
                },
                {
                    "source_name": "Voyager-1",
                    "ra": 286.86,
                    "dec": 12.17,
                    "frequency_hz": 8419921066.0,
                    "drift_rate": 0.287,
                    "is_candidate": True,
                },
            ]
        }))

        analyzer = SETISignalAnalyzer()

        with patch.object(
            SETISignalAnalyzer,
            "_get_mitraseti_candidates_path",
            return_value=state_file,
        ):
            signals = analyzer.check_radio_at_coordinates(
                ra=286.86, dec=12.17, search_radius_arcmin=5.0
            )

        assert len(signals) == 1
        assert signals[0].source_id == "Voyager-1"
        assert signals[0].has_doppler_drift is True
        assert signals[0].frequency_mhz == pytest.approx(8419.921066, abs=0.01)

    def test_no_match_outside_radius(self, tmp_path):
        from features.seti_signals import SETISignalAnalyzer

        candidates_dir = tmp_path / "data"
        candidates_dir.mkdir()
        state_file = candidates_dir / "streaming_state.json"
        state_file.write_text(json.dumps([
            {
                "source_name": "far_source",
                "ra": 10.0,
                "dec": 10.0,
                "frequency_hz": 1420e6,
                "drift_rate": 0.1,
                "is_candidate": True,
            }
        ]))

        analyzer = SETISignalAnalyzer()

        with patch.object(
            SETISignalAnalyzer,
            "_get_mitraseti_candidates_path",
            return_value=state_file,
        ):
            signals = analyzer.check_radio_at_coordinates(
                ra=180.0, dec=45.0, search_radius_arcmin=5.0
            )

        assert len(signals) == 0

    def test_graceful_when_no_data(self):
        from features.seti_signals import SETISignalAnalyzer

        analyzer = SETISignalAnalyzer()

        with patch.object(
            SETISignalAnalyzer,
            "_get_mitraseti_candidates_path",
            return_value=None,
        ):
            signals = analyzer.check_radio_at_coordinates(180.0, 45.0)

        assert signals == []


class TestCandidateCreation:
    """Test SETI candidate workflow end-to-end."""

    def test_create_candidate_with_optical(self):
        from features.seti_signals import SETISignalAnalyzer

        analyzer = SETISignalAnalyzer()
        candidate = analyzer.create_candidate(
            ra=180.0,
            dec=30.0,
            optical_detection={
                "confidence": 0.85,
                "type": "transient",
            },
        )

        assert candidate.has_optical_anomaly is True
        assert candidate.optical_confidence == 0.85
        assert candidate.optical_type == "transient"
        assert candidate.combined_score > 0

    def test_correlate_optical_radio(self):
        from features.seti_signals import SETISignalAnalyzer

        analyzer = SETISignalAnalyzer()
        anomalies = [
            {"ra": 180.0, "dec": 30.0, "confidence": 0.9},
            {"ra": 200.0, "dec": -10.0, "confidence": 0.7},
        ]
        candidates = analyzer.correlate_optical_radio(anomalies)

        assert len(candidates) == 2
        assert candidates[0].combined_score >= candidates[1].combined_score


class TestSkymapExport:
    """Test skymap export utility for MitraSETI."""

    def test_export_schema(self, tmp_path):
        from catalog.skymap_export import export_skymap_json

        artifacts = tmp_path / "astrolens_artifacts"
        data_dir = artifacts / "data"
        data_dir.mkdir(parents=True)

        candidates = [
            {
                "image_path": "/img/sdss_ra180.5_dec30.2.jpg",
                "ood_score": 0.45,
                "classification": "galaxy",
                "confidence": 0.92,
                "source": "sdss",
                "is_transient_source": False,
                "yolo_confirmed": True,
                "detected_at": "2026-01-15T10:00:00",
            }
        ]
        (data_dir / "anomaly_candidates.json").write_text(json.dumps(candidates))

        result = export_skymap_json(str(artifacts))

        assert len(result) == 1
        entry = result[0]
        assert entry["ra_deg"] == pytest.approx(180.5, abs=0.01)
        assert entry["dec_deg"] == pytest.approx(30.2, abs=0.01)
        assert "ood_score" in entry
        assert "classification" in entry

        output_file = data_dir / "skymap_export.json"
        assert output_file.exists()

    def test_skips_entries_without_coordinates(self, tmp_path):
        from catalog.skymap_export import export_skymap_json

        artifacts = tmp_path / "artifacts"
        data_dir = artifacts / "data"
        data_dir.mkdir(parents=True)

        candidates = [
            {"image_path": "/img/no_coords.jpg", "ood_score": 0.5},
            {"image_path": "/img/sdss_ra10.0_dec20.0.jpg", "ood_score": 0.8},
        ]
        (data_dir / "anomaly_candidates.json").write_text(json.dumps(candidates))

        result = export_skymap_json(str(artifacts))
        assert len(result) == 1


class TestVotingSystem:
    """Test community voting system."""

    def test_add_vote_and_consensus(self):
        from features.seti_signals import CommunityVotingSystem, Vote

        system = CommunityVotingSystem()

        for uid in ["u1", "u2", "u3", "u4"]:
            v = Vote(
                user_id=uid,
                candidate_id="c1",
                vote="real",
                confidence=0.9,
            )
            assert system.add_vote(v) is True

        label, agreement = system.get_consensus("c1")
        assert label == "real"
        assert agreement > 0.5

    def test_duplicate_vote_rejected(self):
        from features.seti_signals import CommunityVotingSystem, Vote

        system = CommunityVotingSystem()
        v1 = Vote(user_id="u1", candidate_id="c1", vote="real")
        assert system.add_vote(v1) is True
        assert system.add_vote(v1) is False
