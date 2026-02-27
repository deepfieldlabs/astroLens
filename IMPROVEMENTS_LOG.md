# astroLens Improvements Log

Chronological record of improvements applied to astroLens, the reasoning behind each change, and its measured impact.

---

## Disk Space Cleanup (Feb 27, 2026)

### Redundant Data Removal
- **What**: Identified and removed redundant artifacts that were no longer needed for active model inference or training.
- **Deleted**:
  - 6 old timestamped weight checkpoints + 3 empty folders (11.2 GB): `vit_astrolens_20260123_201823`, `vit_astrolens_20260123_190856`, `vit_astrolens_20260124_112523`, `vit_astrolens_20260123_181315`, `vit_astrolens_20260123_151153`, `vit_astrolens_20260123_143739`
  - 2 superseded weight variants — `vit_astrolens_galaxy_zoo`, `vit_astrolens_anomalies` (2.6 GB). These are superseded by `vit_astrolens_latest`.
  - 992 old discovery download folders in `astrolens_artifacts/downloads/` (2.5 GB processed intermediates)
  - Galaxy10 extracted `train/` and `test/` folders (2.5 GB). Raw `Galaxy10_DECals.h5` kept for future re-extraction.
  - `downloads/` folder in project root (197 MB old files)
- **Preserved**:
  - `vit_astrolens` (base model weights)
  - `vit_astrolens_latest` (active production model)
  - `vit_astrolens_galaxy10` (fine-tuned variant)
  - `Galaxy10_DECals.h5` raw dataset for future re-extraction
  - All data images, transient data, website assets, marketing materials
- **Impact**: Freed ~19 GB from astroLens artifacts.
