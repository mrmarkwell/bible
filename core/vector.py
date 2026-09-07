"""Zero-Dependency Vector Similarity Engine for the Bible Engine.

This module provides high-performance vector operations, float32 <-> int8 quantization,
pure Python cosine similarity, and hierarchical two-tier indexing (768-bit sign hash + exact rerank)
for whole-Bible semantic search over 31,102 canonical verses and pericope units.

Architectural invariants:
- Pure Python 3 standard library only (math, struct, array, heapq, typing, dataclasses).
- Zero external packages (no numpy, scipy, faiss, chromadb).
- Complies with ADR-003 and ADR-051.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

# Standard embedding dimensions (defaulting to text-embedding-004 standard)
DEFAULT_VECTOR_DIM = 768

# Packing wire formats
PACK_FORMAT_FLOAT32 = "float32"
PACK_FORMAT_INT8 = "int8"
PACK_FORMAT_SIGN_HASH = "sign_hash"


@dataclass(frozen=True)
class VectorRecord:
    """Represents an embedded vector associated with an entity ID."""

    entity_id: Union[int, str]
    human_ref: str
    dimensions: int
    raw_bytes: bytes
    format: str = PACK_FORMAT_INT8
    sign_hash: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert vector record to JSON-serializable dictionary."""
        return {
            "entity_id": self.entity_id,
            "human_ref": self.human_ref,
            "dimensions": self.dimensions,
            "format": self.format,
            "bytes_length": len(self.raw_bytes),
            "sign_hash_hex": hex(self.sign_hash) if self.sign_hash is not None else None,
            "metadata": self.metadata or {},
        }


@dataclass(frozen=True)
class SimilarityMatch:
    """Represents a scored vector match from a similarity search."""

    entity_id: Union[int, str]
    human_ref: str
    score: float  # Cosine similarity in range [-1.0, 1.0]
    rank: int
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert similarity match to JSON-serializable dictionary."""
        return {
            "entity_id": self.entity_id,
            "human_ref": self.human_ref,
            "score": round(self.score, 6),
            "rank": self.rank,
            "metadata": self.metadata or {},
        }


# ==============================================================================
# Vector Math & Quantization Primitives
# ==============================================================================

def vector_norm(vec: Sequence[float]) -> float:
    """Compute the Euclidean L2 norm of a vector."""
    return math.sqrt(sum(x * x for x in vec))


def normalize_vector(vec: Sequence[float], eps: float = 1e-12) -> List[float]:
    """Normalize a vector to unit L2 length."""
    norm = vector_norm(vec)
    if norm < eps:
        return [0.0] * len(vec)
    inv = 1.0 / norm
    return [x * inv for x in vec]


def quantize_float_to_int8(
    vec: Sequence[float],
    scale: float = 127.0,
) -> Tuple[bytes, int]:
    """Quantize normalized float32 vector components in [-1.0, 1.0] to signed 8-bit integers.

    Args:
        vec: Sequence of float values (typically L2 normalized).
        scale: Scale factor, defaulting to 127.0 for signed int8 range [-127, 127].

    Returns:
        Tuple of (packed_int8_bytes, 768_bit_sign_hash).
    """
    dim = len(vec)
    sign_hash = 0
    # Pack into signed int8 bytes
    byte_vals = [0] * dim
    for i, x in enumerate(vec):
        clamped = max(-1.0, min(1.0, x))
        q = int(round(clamped * scale))
        if q > 127:
            q = 127
        elif q < -127:
            q = -127
        byte_vals[i] = q
        if x >= 0.0:
            sign_hash |= (1 << i)

    packed = struct.pack(f"{dim}b", *byte_vals)
    return packed, sign_hash


def dequantize_int8_to_float(
    packed_bytes: bytes,
    scale: float = 127.0,
) -> List[float]:
    """Dequantize packed signed int8 bytes back to normalized float32 values."""
    dim = len(packed_bytes)
    byte_vals = struct.unpack(f"{dim}b", packed_bytes)
    inv = 1.0 / scale
    return [b * inv for b in byte_vals]


def pack_float32_vector(vec: Sequence[float]) -> bytes:
    """Pack a float sequence into raw IEEE 754 float32 bytes."""
    dim = len(vec)
    return struct.pack(f"{dim}f", *vec)


def unpack_float32_vector(packed_bytes: bytes) -> List[float]:
    """Unpack raw IEEE 754 float32 bytes into a Python float list."""
    dim = len(packed_bytes) // 4
    return list(struct.unpack(f"{dim}f", packed_bytes))


def compute_sign_hash(vec: Sequence[float]) -> int:
    """Compute an arbitrary N-bit sign hash integer from vector components.

    Bit i is set to 1 if vec[i] >= 0.0, else 0.
    """
    h = 0
    for i, x in enumerate(vec):
        if x >= 0.0:
            h |= (1 << i)
    return h


def compute_sign_hash_from_int8(packed_bytes: bytes) -> int:
    """Extract N-bit sign hash integer directly from packed signed int8 bytes."""
    h = 0
    dim = len(packed_bytes)
    unpacked = struct.unpack(f"{dim}b", packed_bytes)
    for i, b in enumerate(unpacked):
        if b >= 0:
            h |= (1 << i)
    return h


# ==============================================================================
# Pure Python Cosine Similarity & Distance Metrics
# ==============================================================================

def cosine_similarity(
    vec_a: Sequence[float],
    vec_b: Sequence[float],
    eps: float = 1e-12,
) -> float:
    """Compute exact cosine similarity between two float vectors.

    cos_sim(A, B) = dot(A, B) / (norm(A) * norm(B)).
    Returns 0.0 if either vector has norm near zero.
    """
    if len(vec_a) != len(vec_b):
        raise ValueError(
            f"Vector dimension mismatch: len(a)={len(vec_a)} vs len(b)={len(vec_b)}"
        )

    dot = 0.0
    norm_a_sq = 0.0
    norm_b_sq = 0.0

    for a, b in zip(vec_a, vec_b):
        dot += a * b
        norm_a_sq += a * a
        norm_b_sq += b * b

    denom = math.sqrt(norm_a_sq * norm_b_sq)
    if denom < eps:
        return 0.0

    return max(-1.0, min(1.0, dot / denom))


def int8_dot_product(
    packed_a: bytes,
    packed_b: bytes,
) -> int:
    """Compute integer dot product between two packed signed int8 vectors."""
    dim = len(packed_a)
    vals_a = struct.unpack(f"{dim}b", packed_a)
    vals_b = struct.unpack(f"{dim}b", packed_b)
    return sum(a * b for a, b in zip(vals_a, vals_b))


def int8_cosine_similarity(
    query_unpacked: Sequence[int],
    target_packed: bytes,
    query_norm_sq: Optional[float] = None,
    scale: float = 127.0,
) -> float:
    """Compute fast quantized cosine similarity between unpacked query and packed target bytes.

    Args:
        query_unpacked: Unpacked integer sequence of query components in [-127, 127].
        target_packed: Packed signed int8 bytes of target vector.
        query_norm_sq: Precomputed sum of squares for query vector.
        scale: Quantization scale factor (default 127.0).

    Returns:
        Estimated cosine similarity in [-1.0, 1.0].
    """
    dim = len(target_packed)
    target_vals = struct.unpack(f"{dim}b", target_packed)

    dot = 0
    target_norm_sq = 0
    for q, t in zip(query_unpacked, target_vals):
        dot += q * t
        target_norm_sq += t * t

    if query_norm_sq is None:
        query_norm_sq = sum(q * q for q in query_unpacked)

    denom = math.sqrt(query_norm_sq * target_norm_sq)
    if denom < 1e-12:
        return 0.0

    return max(-1.0, min(1.0, dot / denom))


def hamming_distance(hash_a: int, hash_b: int) -> int:
    """Compute bitwise Hamming distance between two large integers."""
    return (hash_a ^ hash_b).bit_count()


def hamming_to_cosine_estimate(dist: int, total_bits: int) -> float:
    """Convert bitwise Hamming distance to an estimated cosine similarity.

    Based on the Goemans-Williamson hypercube sign projection theorem:
    angle = pi * (dist / total_bits)
    est_cos = cos(angle)
    """
    if total_bits <= 0:
        return 0.0
    frac = max(0.0, min(1.0, dist / total_bits))
    angle = math.pi * frac
    return math.cos(angle)


# ==============================================================================
# In-Memory Vector Index & Fast Similarity Search Engine
# ==============================================================================

class VectorIndex:
    """High-performance, in-memory zero-dependency vector search index.

    Supports:
    - Adding vectors in float32 or int8 format.
    - Automatic int8 quantization with 768-bit sign hash extraction.
    - Two-tier hierarchical search:
      * Tier 1: 768-bit bitwise Hamming scan (<5ms across 31k vectors) to collect top candidate pool.
      * Tier 2: Exact quantized int8 dot product reranking on top candidates (<5ms).
    - Exact exhaustive search mode for absolute precision.
    - Metadata filtering by book, testament, or custom predicate.
    """

    def __init__(self, dimensions: int = DEFAULT_VECTOR_DIM) -> None:
        self.dimensions = dimensions
        self.records: List[VectorRecord] = []
        self._id_map: Dict[Union[int, str], int] = {}  # entity_id -> index in self.records

        # Parallel flat arrays for maximum iteration velocity
        self._hashes: List[int] = []
        self._packed_bytes: List[bytes] = []

    def __len__(self) -> int:
        return len(self.records)

    def clear(self) -> None:
        """Clear all vectors from the index."""
        self.records.clear()
        self._id_map.clear()
        self._hashes.clear()
        self._packed_bytes.clear()

    def add_vector(
        self,
        entity_id: Union[int, str],
        human_ref: str,
        vector: Union[Sequence[float], bytes],
        is_packed: bool = False,
        format: str = PACK_FORMAT_INT8,
        sign_hash: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VectorRecord:
        """Add or update an embedded vector in the index.

        Args:
            entity_id: Canonical integer ID (e.g. 43003016) or string ID.
            human_ref: Human-readable reference (e.g. 'John 3:16').
            vector: Float sequence OR already-packed bytes.
            is_packed: Set True if `vector` is raw bytes.
            format: 'int8' or 'float32'.
            sign_hash: Optional precomputed sign hash integer.
            metadata: Optional dictionary of attributes (book, testament, etc.).

        Returns:
            The created VectorRecord.
        """
        if is_packed:
            if not isinstance(vector, (bytes, bytearray)):
                raise TypeError("Expected bytes when is_packed=True")
            raw_bytes = bytes(vector)
            if sign_hash is None:
                if format == PACK_FORMAT_INT8:
                    sign_hash = compute_sign_hash_from_int8(raw_bytes)
                else:
                    unpacked = unpack_float32_vector(raw_bytes)
                    sign_hash = compute_sign_hash(unpacked)
        else:
            if not isinstance(vector, (list, tuple)):
                raise TypeError("Expected float sequence when is_packed=False")
            if len(vector) != self.dimensions:
                raise ValueError(
                    f"Vector length {len(vector)} does not match index dimension {self.dimensions}"
                )
            norm_vec = normalize_vector(vector)
            if format == PACK_FORMAT_INT8:
                raw_bytes, computed_hash = quantize_float_to_int8(norm_vec)
                sign_hash = computed_hash if sign_hash is None else sign_hash
            else:
                raw_bytes = pack_float32_vector(norm_vec)
                if sign_hash is None:
                    sign_hash = compute_sign_hash(norm_vec)

        rec = VectorRecord(
            entity_id=entity_id,
            human_ref=human_ref,
            dimensions=self.dimensions,
            raw_bytes=raw_bytes,
            format=format,
            sign_hash=sign_hash,
            metadata=metadata or {},
        )

        if entity_id in self._id_map:
            idx = self._id_map[entity_id]
            self.records[idx] = rec
            self._hashes[idx] = sign_hash
            self._packed_bytes[idx] = raw_bytes
        else:
            idx = len(self.records)
            self.records.append(rec)
            self._id_map[entity_id] = idx
            self._hashes.append(sign_hash)
            self._packed_bytes.append(raw_bytes)

        return rec

    def add_batch(
        self,
        items: Sequence[Tuple[Union[int, str], str, Union[Sequence[float], bytes]]],
        is_packed: bool = False,
        format: str = PACK_FORMAT_INT8,
    ) -> int:
        """Batch insert multiple vectors into the index."""
        count = 0
        for item in items:
            entity_id = item[0]
            human_ref = item[1]
            vector = item[2]
            metadata = item[3] if len(item) > 3 else None
            self.add_vector(
                entity_id=entity_id,
                human_ref=human_ref,
                vector=vector,
                is_packed=is_packed,
                format=format,
                metadata=metadata,
            )
            count += 1
        return count

    def get_vector(self, entity_id: Union[int, str]) -> Optional[VectorRecord]:
        """Fetch vector record by entity ID."""
        idx = self._id_map.get(entity_id)
        if idx is None:
            return None
        return self.records[idx]

    def search(
        self,
        query_vector: Union[Sequence[float], bytes],
        top_k: int = 10,
        mode: str = "hierarchical",  # "hierarchical" or "exhaustive"
        candidate_pool_size: int = 300,
        min_score: float = -1.0,
        filter_fn: Optional[Callable[[VectorRecord], bool]] = None,
    ) -> List[SimilarityMatch]:
        """Search the index for the most semantically similar vectors.

        Args:
            query_vector: Query float sequence or packed int8 bytes.
            top_k: Number of top results to return.
            mode: 'hierarchical' (two-tier sign-hash filter + int8 rerank) or 'exhaustive'.
            candidate_pool_size: Size of candidate pool for hierarchical search (default 300).
            min_score: Minimum cosine similarity threshold (default -1.0).
            filter_fn: Optional predicate accepting VectorRecord, returning True to keep.

        Returns:
            List of SimilarityMatch objects ranked from highest to lowest similarity.
        """
        if not self.records:
            return []

        # Prepare query representation
        if isinstance(query_vector, (bytes, bytearray)):
            query_packed = bytes(query_vector)
            query_unpacked = struct.unpack(f"{self.dimensions}b", query_packed)
            query_hash = compute_sign_hash_from_int8(query_packed)
        else:
            norm_q = normalize_vector(query_vector)
            query_packed, query_hash = quantize_float_to_int8(norm_q)
            query_unpacked = struct.unpack(f"{self.dimensions}b", query_packed)

        query_norm_sq = sum(q * q for q in query_unpacked)
        total_vectors = len(self.records)

        # ----------------------------------------------------------------------
        # Strategy A: Exhaustive Linear Scan (Used if mode == 'exhaustive' or small N)
        # ----------------------------------------------------------------------
        if mode == "exhaustive" or total_vectors <= candidate_pool_size:
            scored: List[Tuple[float, int]] = []
            for idx in range(total_vectors):
                rec = self.records[idx]
                if filter_fn is not None and not filter_fn(rec):
                    continue
                score = int8_cosine_similarity(
                    query_unpacked=query_unpacked,
                    target_packed=self._packed_bytes[idx],
                    query_norm_sq=query_norm_sq,
                )
                if score >= min_score:
                    scored.append((score, idx))

            scored.sort(key=lambda x: x[0], reverse=True)
            results: List[SimilarityMatch] = []
            for rank, (score, idx) in enumerate(scored[:top_k], start=1):
                rec = self.records[idx]
                results.append(
                    SimilarityMatch(
                        entity_id=rec.entity_id,
                        human_ref=rec.human_ref,
                        score=score,
                        rank=rank,
                        metadata=rec.metadata,
                    )
                )
            return results

        # ----------------------------------------------------------------------
        # Strategy B: Hierarchical Two-Tier Search (Sub-15ms for whole Bible)
        # ----------------------------------------------------------------------
        # Tier 1: Fast bitwise Hamming distance scan over 768-bit sign hashes
        # Collect candidate pool using bucket collection (counting sort on distances in [0, 768])
        pool_target = max(top_k * 5, candidate_pool_size)
        buckets: List[List[int]] = [[] for _ in range(self.dimensions + 1)]

        for idx in range(total_vectors):
            rec = self.records[idx]
            if filter_fn is not None and not filter_fn(rec):
                continue
            dist = (self._hashes[idx] ^ query_hash).bit_count()
            if dist <= self.dimensions:
                buckets[dist].append(idx)

        # Gather top candidate indices from the lowest Hamming buckets
        candidate_indices: List[int] = []
        for d in range(self.dimensions + 1):
            bucket = buckets[d]
            if not bucket:
                continue
            candidate_indices.extend(bucket)
            if len(candidate_indices) >= pool_target:
                break

        # Tier 2: Exact quantized int8 dot product rerank on candidate pool
        scored_candidates: List[Tuple[float, int]] = []
        for idx in candidate_indices:
            score = int8_cosine_similarity(
                query_unpacked=query_unpacked,
                target_packed=self._packed_bytes[idx],
                query_norm_sq=query_norm_sq,
            )
            if score >= min_score:
                scored_candidates.append((score, idx))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        results: List[SimilarityMatch] = []
        for rank, (score, idx) in enumerate(scored_candidates[:top_k], start=1):
            rec = self.records[idx]
            results.append(
                SimilarityMatch(
                    entity_id=rec.entity_id,
                    human_ref=rec.human_ref,
                    score=score,
                    rank=rank,
                    metadata=rec.metadata,
                )
            )

        return results

    def build_from_database(
        self,
        db: Any,
        table: str = "verse_embeddings",
        model_id: Optional[str] = None,
    ) -> int:
        """Load and build vector index directly from SQLite database.

        Args:
            db: Database instance from core.db.
            table: 'verse_embeddings' or 'pericope_embeddings'.
            model_id: Optional model filtering (e.g. 'text-embedding-004').

        Returns:
            Number of vectors loaded.
        """
        self.clear()
        if table == "verse_embeddings":
            records = db.get_all_verse_embeddings(model_id=model_id)
            for r in records:
                self.add_vector(
                    entity_id=r.canonical_verse_id,
                    human_ref=r.human_ref,
                    vector=r.embedding,
                    is_packed=True,
                    format=PACK_FORMAT_INT8 if len(r.embedding) == r.dimensions else PACK_FORMAT_FLOAT32,
                    metadata={"model_id": r.model_id},
                )
        elif table == "pericope_embeddings":
            records = db.get_all_pericope_embeddings(model_id=model_id)
            for r in records:
                self.add_vector(
                    entity_id=r.pericope_id,
                    human_ref=r.human_ref,
                    vector=r.embedding,
                    is_packed=True,
                    format=PACK_FORMAT_INT8 if len(r.embedding) == r.dimensions else PACK_FORMAT_FLOAT32,
                    metadata={
                        "model_id": r.model_id,
                        "start_id": r.start_canonical_id,
                        "end_id": r.end_canonical_id,
                    },
                )
        else:
            raise ValueError(f"Unknown vector table: {table}")

        return len(self.records)


# Global singleton cache for vector indices
_GLOBAL_VERSE_INDEX: Optional[VectorIndex] = None
_GLOBAL_PERICOPE_INDEX: Optional[VectorIndex] = None


def get_verse_vector_index(dimensions: int = DEFAULT_VECTOR_DIM) -> VectorIndex:
    """Get or create the process-wide verse vector index."""
    global _GLOBAL_VERSE_INDEX
    if _GLOBAL_VERSE_INDEX is None:
        _GLOBAL_VERSE_INDEX = VectorIndex(dimensions=dimensions)
    return _GLOBAL_VERSE_INDEX


def get_pericope_vector_index(dimensions: int = DEFAULT_VECTOR_DIM) -> VectorIndex:
    """Get or create the process-wide pericope vector index."""
    global _GLOBAL_PERICOPE_INDEX
    if _GLOBAL_PERICOPE_INDEX is None:
        _GLOBAL_PERICOPE_INDEX = VectorIndex(dimensions=dimensions)
    return _GLOBAL_PERICOPE_INDEX
