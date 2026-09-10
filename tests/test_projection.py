#!/usr/bin/env python3
"""Hermetic Unit Tests for 2D Semantic Embedding Projection Engine.

Zero external dependencies (ADR-003):
- Tests FastMap (Faloutsos & Lin, 1995) non-linear dimensionality reduction.
- Tests Power Iteration PCA 2D variance projection.
- Tests coordinate normalization, edge cases (0, 1, 2 points), and SVG rendering.
"""

import math
import struct
import unittest

from core.projection import (
    DEFAULT_MAP_HEIGHT,
    DEFAULT_MAP_MARGIN,
    DEFAULT_MAP_WIDTH,
    FastMapProjector,
    MapPoint,
    PCAProjector,
    cosine_distance,
    dequantize_vector_bytes,
    normalize_coordinates,
    project_embeddings,
    render_scatter_map_svg,
)


class TestProjectionEngine(unittest.TestCase):
    """Test suite for core.projection mathematical operations and algorithms."""

    def test_dequantize_int8(self) -> None:
        """Verify int8 packed bytes dequantize to normalized float32."""
        dim = 4
        # [127, 0, -127, 0]
        packed = struct.pack("4b", 127, 0, -127, 0)
        vec = dequantize_vector_bytes(packed, dim=dim)
        self.assertEqual(len(vec), 4)
        # Check unit L2 norm
        norm = math.sqrt(sum(x * x for x in vec))
        self.assertAlmostEqual(norm, 1.0, places=5)
        self.assertGreater(vec[0], 0.6)
        self.assertLess(vec[2], -0.6)
        self.assertAlmostEqual(vec[1], 0.0, places=5)

    def test_dequantize_float32(self) -> None:
        """Verify IEEE 754 float32 bytes dequantize and normalize properly."""
        packed = struct.pack("4f", 1.0, 2.0, 3.0, 4.0)
        vec = dequantize_vector_bytes(packed, dim=4)
        self.assertEqual(len(vec), 4)
        norm = math.sqrt(sum(x * x for x in vec))
        self.assertAlmostEqual(norm, 1.0, places=5)

    def test_cosine_distance(self) -> None:
        """Verify chord Euclidean distance on unit hypersphere."""
        v1 = [1.0, 0.0, 0.0]
        v2 = [1.0, 0.0, 0.0]
        self.assertAlmostEqual(cosine_distance(v1, v2), 0.0, places=5)

        v3 = [0.0, 1.0, 0.0]  # Orthogonal
        self.assertAlmostEqual(cosine_distance(v1, v3), math.sqrt(2.0), places=5)

        v4 = [-1.0, 0.0, 0.0]  # Opposite
        self.assertAlmostEqual(cosine_distance(v1, v4), 2.0, places=5)

    def test_normalize_coordinates(self) -> None:
        """Verify normalization maps arbitrary coordinates into target viewport."""
        raw = [(0.0, 0.0), (10.0, 20.0), (5.0, 10.0)]
        norm = normalize_coordinates(raw, width=1000.0, height=700.0, margin=50.0)
        self.assertEqual(len(norm), 3)
        # Min point should be at margin
        self.assertAlmostEqual(norm[0][0], 50.0)
        self.assertAlmostEqual(norm[0][1], 50.0)
        # Max point should be at width-margin, height-margin
        self.assertAlmostEqual(norm[1][0], 950.0)
        self.assertAlmostEqual(norm[1][1], 650.0)
        # Midpoint
        self.assertAlmostEqual(norm[2][0], 500.0)
        self.assertAlmostEqual(norm[2][1], 350.0)

    def test_normalize_coordinates_single_point(self) -> None:
        """Verify single point gets centered in viewport."""
        raw = [(42.0, 84.0)]
        norm = normalize_coordinates(raw, width=1000.0, height=700.0, margin=50.0)
        self.assertEqual(len(norm), 1)
        self.assertAlmostEqual(norm[0][0], 500.0)
        self.assertAlmostEqual(norm[0][1], 350.0)

    def test_fastmap_projector_edge_cases(self) -> None:
        """Verify FastMap handles empty, 1-point, and 2-point inputs gracefully."""
        projector = FastMapProjector(seed=42)
        self.assertEqual(projector.project([]), [])

        one_pt = projector.project([[1.0, 0.0, 0.0]])
        self.assertEqual(len(one_pt), 1)
        self.assertAlmostEqual(one_pt[0][0], DEFAULT_MAP_WIDTH / 2.0)
        self.assertAlmostEqual(one_pt[0][1], DEFAULT_MAP_HEIGHT / 2.0)

        two_pts = projector.project([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        self.assertEqual(len(two_pts), 2)
        self.assertAlmostEqual(two_pts[0][0], DEFAULT_MAP_MARGIN)
        self.assertAlmostEqual(two_pts[1][0], DEFAULT_MAP_WIDTH - DEFAULT_MAP_MARGIN)

    def test_fastmap_projection_multi_points(self) -> None:
        """Verify FastMap projects high-dimensional synthetic points within viewport."""
        # 10 synthetic 16-dimensional vectors
        vectors = []
        for i in range(10):
            row = [0.0] * 16
            row[i % 16] = 1.0
            row[(i + 3) % 16] = 0.5
            norm = math.sqrt(sum(x * x for x in row))
            vectors.append([x / norm for x in row])

        projector = FastMapProjector(seed=42)
        coords = projector.project(vectors, width=1000.0, height=700.0, margin=50.0)
        self.assertEqual(len(coords), 10)
        for x, y in coords:
            self.assertGreaterEqual(x, 49.9)
            self.assertLessEqual(x, 950.1)
            self.assertGreaterEqual(y, 49.9)
            self.assertLessEqual(y, 650.1)

    def test_pca_projector(self) -> None:
        """Verify Power Iteration PCA projects points within viewport boundaries."""
        vectors = []
        for i in range(12):
            row = [float(i * j) for j in range(8)]
            norm = math.sqrt(sum(x * x for x in row)) or 1.0
            vectors.append([x / norm for x in row])

        pca = PCAProjector(max_iter=15, seed=42)
        coords = pca.project(vectors, width=1000.0, height=700.0, margin=50.0)
        self.assertEqual(len(coords), 12)
        for x, y in coords:
            self.assertGreaterEqual(x, 49.9)
            self.assertLessEqual(x, 950.1)
            self.assertGreaterEqual(y, 49.9)
            self.assertLessEqual(y, 650.1)

    def test_project_embeddings_high_level(self) -> None:
        """Verify project_embeddings works with both float sequences and packed bytes."""
        # Create packed int8 bytes
        dim = 8
        packed1 = struct.pack(f"{dim}b", 120, -50, 30, 0, 10, -80, 40, 20)
        packed2 = struct.pack(f"{dim}b", -100, 70, -20, 10, -5, 60, -30, -10)
        packed3 = struct.pack(f"{dim}b", 10, 20, 30, 40, 50, 60, 70, 80)

        coords = project_embeddings([packed1, packed2, packed3], method="fastmap")
        self.assertEqual(len(coords), 3)

        coords_pca = project_embeddings([packed1, packed2, packed3], method="pca")
        self.assertEqual(len(coords_pca), 3)

    def test_map_point_data_model(self) -> None:
        """Verify MapPoint structure and JSON dictionary serialization."""
        pt = MapPoint(
            entity_id=101,
            human_ref="Romans 8:28-30",
            title="Golden Chain of Redemption",
            book_id=45,
            book_name="Romans",
            testament="NT",
            genre="Epistle",
            x=512.345,
            y=284.678,
            tags=["predestination", "calling", "justification"],
            redemptive_summary="God works all things together for the good of those who love Him.",
        )
        d = pt.to_dict()
        self.assertEqual(d["entity_id"], 101)
        self.assertEqual(d["human_ref"], "Romans 8:28-30")
        self.assertEqual(d["x"], 512.35)
        self.assertEqual(d["y"], 284.68)
        self.assertEqual(len(d["tags"]), 3)
        self.assertEqual(d["testament"], "NT")

    def test_render_scatter_map_svg(self) -> None:
        """Verify render_scatter_map_svg produces well-formed vector XML."""
        pts = [
            MapPoint(1, "Gen 1:1", "Creation", 1, "Genesis", "OT", "Law", 100.0, 150.0),
            MapPoint(2, "Rom 8:28", "Redemption", 45, "Romans", "NT", "Epistle", 800.0, 500.0),
        ]
        svg = render_scatter_map_svg(pts, width=1000, height=700, title="Test Scatter Map")
        self.assertTrue(svg.startswith("<svg"))
        self.assertTrue(svg.endswith("</svg>"))
        self.assertIn("Test Scatter Map", svg)
        self.assertIn("Old Testament", svg)
        self.assertIn("New Testament", svg)
        self.assertIn("<circle cx=\"100.0\" cy=\"150.0\"", svg)
        self.assertIn("<circle cx=\"800.0\" cy=\"500.0\"", svg)


if __name__ == "__main__":
    unittest.main()
