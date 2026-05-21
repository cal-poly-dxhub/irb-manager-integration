"""Local numpy-based vector store for past submission RAG.

Stores embeddings as a single numpy array with a metadata JSON sidecar.
Supports filtered search by dataId (to find past responses for a specific field).
"""

import json
from pathlib import Path
from typing import Optional

import numpy as np


class VectorStore:
    """Numpy-based vector store for past submission responses.

    Storage format:
      embeddings_dir/
        vectors.npy       - (N, D) float32 array of all vectors
        metadata.json     - list of N entries, each with:
                            {dataId, protocol, text, index}
    """

    def __init__(self, embeddings_dir: str):
        self._dir = Path(embeddings_dir)
        self._vectors: Optional[np.ndarray] = None
        self._metadata: list[dict] = []
        self._field_index: dict[int, list[int]] = {}
        self._load()

    def _load(self):
        vectors_path = self._dir / "vectors.npy"
        metadata_path = self._dir / "metadata.json"

        if not vectors_path.exists() or not metadata_path.exists():
            return

        self._vectors = np.load(str(vectors_path))
        with open(metadata_path) as f:
            self._metadata = json.load(f)

        # Build index: dataId -> list of vector indices
        self._field_index = {}
        for i, entry in enumerate(self._metadata):
            data_id = int(entry["dataId"])
            if data_id not in self._field_index:
                self._field_index[data_id] = []
            self._field_index[data_id].append(i)

    @property
    def is_loaded(self) -> bool:
        return self._vectors is not None and len(self._metadata) > 0

    @property
    def size(self) -> int:
        return len(self._metadata)

    def search(
        self,
        query_vector: list[float],
        top_k: int = 3,
        data_id: Optional[int] = None,
    ) -> list[dict]:
        """Search for similar past submission responses.

        Args:
            query_vector: The query embedding vector.
            top_k: Number of results to return.
            data_id: If provided, only search within responses for this specific field.

        Returns:
            List of dicts with keys: dataId, protocol, text, score.
        """
        if not self.is_loaded:
            return []

        query = np.array(query_vector, dtype=np.float32)

        if data_id is not None:
            indices = self._field_index.get(data_id, [])
            if not indices:
                return []
            candidates = self._vectors[indices]
            scores = candidates @ query
            top_indices = np.argsort(scores)[::-1][:top_k]
            results = []
            for idx in top_indices:
                original_idx = indices[idx]
                entry = self._metadata[original_idx]
                results.append({
                    "dataId": entry["dataId"],
                    "protocol": entry["protocol"],
                    "text": entry["text"],
                    "score": float(scores[idx]),
                })
            return results
        else:
            scores = self._vectors @ query
            top_indices = np.argsort(scores)[::-1][:top_k]
            results = []
            for idx in top_indices:
                entry = self._metadata[idx]
                results.append({
                    "dataId": entry["dataId"],
                    "protocol": entry["protocol"],
                    "text": entry["text"],
                    "score": float(scores[idx]),
                })
            return results

    def search_by_field(
        self,
        query_vector: list[float],
        data_id: int,
        top_k: int = 3,
    ) -> list[dict]:
        """Convenience wrapper: search only within a specific field's past responses."""
        return self.search(query_vector, top_k=top_k, data_id=data_id)

    def get_all_for_field(self, data_id: int) -> list[dict]:
        """Get all past submission responses for a specific field (no vector search)."""
        indices = self._field_index.get(data_id, [])
        return [
            {
                "dataId": self._metadata[i]["dataId"],
                "protocol": self._metadata[i]["protocol"],
                "text": self._metadata[i]["text"],
            }
            for i in indices
        ]

    def get_covered_fields(self) -> list[int]:
        """Return dataIds that have at least one past submission response."""
        return list(self._field_index.keys())
