"""Deduplication utilities for catalog datasets."""

import hashlib
from dataclasses import dataclass
from typing import Optional

import structlog

logger = structlog.get_logger()


@dataclass
class DuplicateCheckResult:
    """Result of duplicate check."""

    is_duplicate: bool
    existing_dataset_id: Optional[str] = None
    match_type: Optional[str] = None  # "exact_url", "content_hash", "metadata_similarity"
    similarity_score: float = 0.0
    details: Optional[dict] = None


class DatasetDeduplicator:
    """Handles dataset deduplication based on multiple strategies."""

    def __init__(self, db_pool=None):
        self.db_pool = db_pool

    def compute_content_hash(self, content: bytes) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content).hexdigest()

    def compute_metadata_hash(self, metadata: dict) -> str:
        """Compute hash of key metadata fields for similarity comparison."""
        # Use stable fields for metadata hash
        key_fields = [
            metadata.get("name", ""),
            metadata.get("psi_id", ""),
            metadata.get("description", ""),
            str(sorted(metadata.get("numeric_columns", []))),
        ]
        content = "|".join(key_fields)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def check_duplicate_by_url(self, url: str) -> DuplicateCheckResult:
        """Check if a dataset with the same URL already exists."""
        if not self.db_pool:
            return DuplicateCheckResult(is_duplicate=False)

        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT dataset_id FROM datasets WHERE url = $1 OR provenance_dataset_url = $1",
                    url
                )
                if row:
                    return DuplicateCheckResult(
                        is_duplicate=True,
                        existing_dataset_id=row["dataset_id"],
                        match_type="exact_url",
                        similarity_score=1.0,
                        details={"matched_url": url}
                    )
        except Exception as e:
            logger.error("duplicate_check_url_failed", url=url, error=str(e))

        return DuplicateCheckResult(is_duplicate=False)

    async def check_duplicate_by_content_hash(self, content_hash: str) -> DuplicateCheckResult:
        """Check if a dataset with the same content hash already exists."""
        if not self.db_pool:
            return DuplicateCheckResult(is_duplicate=False)

        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT dataset_id FROM dataset_embeddings WHERE content_hash = $1",
                    content_hash
                )
                if row:
                    # Get the dataset_id from datasets table
                    dataset_row = await conn.fetchrow(
                        "SELECT dataset_id FROM datasets WHERE id = $1",
                        row["dataset_id"]
                    )
                    if dataset_row:
                        return DuplicateCheckResult(
                            is_duplicate=True,
                            existing_dataset_id=dataset_row["dataset_id"],
                            match_type="content_hash",
                            similarity_score=1.0,
                            details={"content_hash": content_hash}
                        )
        except Exception as e:
            logger.error("duplicate_check_hash_failed", content_hash=content_hash, error=str(e))

        return DuplicateCheckResult(is_duplicate=False)

    async def check_duplicate_by_metadata(
        self,
        metadata_hash: str,
        psi_id: str,
        numeric_columns: list[str],
        threshold: float = 0.9
    ) -> DuplicateCheckResult:
        """Check for similar datasets based on metadata similarity."""
        if not self.db_pool:
            return DuplicateCheckResult(is_duplicate=False)

        try:
            async with self.db_pool.acquire() as conn:
                # Find datasets in same investigation with similar numeric columns
                rows = await conn.fetch(
                    """
                    SELECT d.dataset_id, d.numeric_columns, d.name
                    FROM datasets d
                    WHERE d.psi_id = $1
                      AND d.verification_status = 'verified'
                    """,
                    psi_id
                )

                for row in rows:
                    existing_columns = set(row["numeric_columns"] or [])
                    new_columns = set(numeric_columns)

                    if not existing_columns or not new_columns:
                        continue

                    # Jaccard similarity
                    intersection = len(existing_columns & new_columns)
                    union = len(existing_columns | new_columns)
                    similarity = intersection / union if union > 0 else 0.0

                    if similarity >= threshold:
                        return DuplicateCheckResult(
                            is_duplicate=True,
                            existing_dataset_id=row["dataset_id"],
                            match_type="metadata_similarity",
                            similarity_score=similarity,
                            details={
                                "existing_name": row["name"],
                                "existing_columns": list(existing_columns),
                                "new_columns": list(new_columns),
                                "jaccard_similarity": similarity
                            }
                        )

        except Exception as e:
            logger.error("duplicate_check_metadata_failed", psi_id=psi_id, error=str(e))

        return DuplicateCheckResult(is_duplicate=False)

    async def check_all(self, dataset_metadata: dict, content: Optional[bytes] = None) -> DuplicateCheckResult:
        """Run all duplicate checks and return the first match."""
        # Check by URL first (fastest)
        url = dataset_metadata.get("url") or dataset_metadata.get("provenance_dataset_url")
        if url:
            result = await self.check_duplicate_by_url(url)
            if result.is_duplicate:
                logger.info("duplicate_found_by_url", dataset_id=result.existing_dataset_id)
                return result

        # Check by content hash if content provided
        if content:
            content_hash = self.compute_content_hash(content)
            result = await self.check_duplicate_by_content_hash(content_hash)
            if result.is_duplicate:
                logger.info("duplicate_found_by_hash", dataset_id=result.existing_dataset_id)
                return result

        # Check by metadata similarity
        metadata_hash = self.compute_metadata_hash(dataset_metadata)
        result = await self.check_duplicate_by_metadata(
            metadata_hash=metadata_hash,
            psi_id=dataset_metadata.get("psi_id", ""),
            numeric_columns=dataset_metadata.get("numeric_columns", [])
        )
        if result.is_duplicate:
            logger.info("duplicate_found_by_metadata", dataset_id=result.existing_dataset_id)
            return result

        return DuplicateCheckResult(is_duplicate=False)


def generate_stable_dataset_id(psi_id: str, name: str, url: str) -> str:
    """Generate a stable dataset ID from key identifiers."""
    # Normalize inputs using shared normalization function
    psi_normalized = psi_id.upper().strip()
    name_normalized = normalize_dataset_name(name)
    url_normalized = url.strip()

    # Create hash from stable components
    content = f"{psi_normalized}|{name_normalized}|{url_normalized}"
    hash_suffix = hashlib.sha256(content.encode()).hexdigest()[:8]

    return f"{psi_normalized.lower()}-{name_normalized}-{hash_suffix}"


def normalize_dataset_name(name: str) -> str:
    """Normalize dataset name for consistent identification."""
    import re
    # Remove file extension
    if "." in name:
        name = name.rsplit(".", 1)[0]
    # Remove special characters, replace spaces with hyphens
    normalized = re.sub(r"[^\w\s-]", "", name.lower())
    normalized = re.sub(r"[\s_]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized)
    return normalized.strip("-")