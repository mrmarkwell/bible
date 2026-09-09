# Treasury of Scripture Knowledge (TSK) Cross-References Dataset

This directory contains the authoritative, public-domain cross-reference dataset connecting passages across the canonical Old and New Testaments.

## Dataset Provenance & Overview
- **Source**: Treasury of Scripture Knowledge (TSK), originally compiled by Samuel Bagster and augmented by R. A. Torrey and the OpenBible.info project.
- **Original Publisher**: Samuel Bagster & Sons (1836), London.
- **Modern Harmonization & Community Weighting**: OpenBible.info (Labs Cross-References).
- **License**: Public Domain (Original TSK) / Creative Commons Attribution (CC-BY) for modern OpenBible community votes.
- **Total Edges**: 344,756 raw rows (343,513 with non-negative community votes).

## File Specifications
- `cross_references.txt`: Tab-separated values (TSV) containing:
  1. `From Verse`: Canonical verse in OSIS format (e.g., `Gen.1.1`, `John.3.16`).
  2. `To Verse`: Target verse or verse range in OSIS format (e.g., `Exod.20.11`, `John.1.1-John.1.3`).
  3. `Votes`: Community confidence score / vote tally reflecting cross-reference relevance.

## Coordinate Mapping
- OSIS book identifiers match `core.reference.ALL_BOOKS` across all 66 canonical books.
- Verse boundaries are converted to canonical integer IDs (`BBCCCVVV`).
- Inter-book spans (18 rare instances) are partitioned into valid intra-book edges.
