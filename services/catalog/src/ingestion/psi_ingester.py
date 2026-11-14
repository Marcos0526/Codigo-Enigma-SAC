"""PSI Investigation ingestion from NASA PSI index."""

import csv
import hashlib
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

import httpx
import structlog
from bs4 import BeautifulSoup

from services.catalog.src.models.catalog import (
    PSIInvestigation,
    VerificationStatus,
    SOURCE_COLLECTION,
)
from services.catalog.src.validation.url_validator import URLValidator, URLValidationResult

logger = structlog.get_logger()


@dataclass
class IngestionResult:
    """Result of ingestion operation."""

    success: bool
    investigation: Optional[PSIInvestigation] = None
    error: Optional[str] = None
    warnings: list[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class PSIIngester:
    """Ingests PSI investigations from NASA PSI index and investigation pages."""

    PSI_INDEX_CSV_URL = "https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv"
    PSI_BASE_URL = "https://psi.nasa.gov/physci/repo/data/investigations/"

    # The 26 selected investigation IDs
    SELECTED_PSI_IDS = {
        "PSI-20", "PSI-21", "PSI-159", "PSI-10", "PSI-22", "PSI-23",
        "PSI-26", "PSI-25", "PSI-60", "PSI-62", "PSI-39", "PSI-47",
        "PSI-117", "PSI-69", "PSI-68", "PSI-142", "PSI-101", "PSI-102",
        "PSI-107", "PSI-99", "PSI-100", "PSI-98", "PSI-106", "PSI-181",
        "PSI-108", "PSI-115"
    }

    def __init__(
        self,
        db_pool,
        allowed_domains: Optional[set[str]] = None,
        timeout: float = 30.0,
    ):
        self.db_pool = db_pool
        self.allowed_domains = allowed_domains or {
            "psi.nasa.gov",
            "raw.githubusercontent.com",
            "data.nasa.gov",
            "doi.org",
            "github.com",
            "githubusercontent.com",
        }
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    def _get_client(self) -> httpx.AsyncClient:
        if not self._client:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
            )
        return self._client

    async def fetch_psi_index(self) -> list[dict]:
        """Fetch and parse the PSI index CSV."""
        client = self._get_client()
        response = await client.get(self.PSI_INDEX_CSV_URL)
        response.raise_for_status()

        # Parse CSV
        lines = response.text.strip().split("\n")
        reader = csv.DictReader(lines)
        return list(reader)

    def filter_selected_investigations(self, index_rows: list[dict]) -> list[dict]:
        """Filter index rows to only include the 26 selected investigations."""
        filtered = []
        for row in index_rows:
            psi_id = row.get("psi_id") or row.get("PSI_ID") or row.get("id", "").strip()
            if psi_id in self.SELECTED_PSI_IDS:
                filtered.append(row)
        return filtered

    async def fetch_investigation_page(self, psi_id: str) -> Optional[BeautifulSoup]:
        """Fetch and parse an investigation page."""
        url = urljoin(self.PSI_BASE_URL, psi_id)
        try:
            client = self._get_client()
            response = await client.get(url)
            if response.status_code == 404:
                logger.warning("investigation_page_not_found", psi_id=psi_id, url=url)
                return None
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            logger.error("fetch_investigation_page_failed", psi_id=psi_id, error=str(e))
            return None

    def parse_investigation_page(self, psi_id: str, soup: BeautifulSoup) -> dict:
        """Parse investigation metadata from HTML page."""
        metadata = {
            "psi_id": psi_id,
            "title": f"Investigation {psi_id} — Official title pending verification",
            "description": "Metadata pending verification from official NASA PSI record.",
            "research_area": "Combustion Science",
            "sub_research_area": None,
            "scientific_focus": None,
            "project_setting": None,
            "record_type": "Investigation",
            "doi": None,
            "doi_url": None,
            "psi_record_url": f"{self.PSI_BASE_URL}{psi_id}",
            "objectives": "Pending verification from the official NASA PSI record. No objectives have been invented.",
            "approach": "Pending verification from the official NASA PSI record. No experimental methodology has been invented.",
            "sources": [f"{self.PSI_BASE_URL}{psi_id}"],
            "metadata_status": VerificationStatus.PENDING.value,
            "tags": ["pending-verification", "metadata-pending"],
        }

        # Try to extract title
        title_elem = soup.find("h1") or soup.find("title")
        if title_elem:
            title_text = title_elem.get_text(strip=True)
            if title_text and psi_id in title_text:
                metadata["title"] = title_text

        # Try to extract description/objectives from page content
        # Look for common patterns in PSI pages
        content_text = soup.get_text(separator=" ", strip=True)

        # Extract DOI if present
        doi_match = re.search(r"10\.\d{4,5}/[^\s]+", content_text)
        if doi_match:
            doi = doi_match.group(0)
            metadata["doi"] = doi
            metadata["doi_url"] = f"https://doi.org/{doi}"

        # Try to find objectives/approach sections
        for heading in soup.find_all(["h2", "h3", "h4"]):
            heading_text = heading.get_text(strip=True).lower()
            next_elem = heading.find_next_sibling()
            if next_elem:
                content = next_elem.get_text(strip=True)
                if "objective" in heading_text or "goal" in heading_text:
                    metadata["objectives"] = content
                elif "approach" in heading_text or "method" in heading_text:
                    metadata["approach"] = content

        # Update status if we found substantial content
        if metadata["objectives"] != "Pending verification from the official NASA PSI record. No objectives have been invented.":
            metadata["metadata_status"] = VerificationStatus.VERIFIED.value
            metadata["tags"] = ["combustion-science", "nasa-psi"]

        return metadata

    async def ingest_single(self, index_row: dict) -> IngestionResult:
        """Ingest a single investigation from index row."""
        psi_id = index_row.get("psi_id") or index_row.get("PSI_ID") or index_row.get("id", "").strip()

        if psi_id not in self.SELECTED_PSI_IDS:
            return IngestionResult(
                success=False,
                error=f"PSI ID {psi_id} not in selected 26 investigations"
            )

        logger.info("ingesting_investigation", psi_id=psi_id)

        # Fetch investigation page
        soup = await self.fetch_investigation_page(psi_id)

        if soup:
            metadata = self.parse_investigation_page(psi_id, soup)
        else:
            # Use index row data as fallback
            metadata = {
                "psi_id": psi_id,
                "title": index_row.get("title") or index_row.get("Title") or f"Investigation {psi_id}",
                "description": index_row.get("description") or index_row.get("Description") or "",
                "research_area": index_row.get("research_area") or index_row.get("Research Area") or "Combustion Science",
                "sub_research_area": index_row.get("sub_research_area") or index_row.get("Sub Research Area"),
                "scientific_focus": index_row.get("scientific_focus") or index_row.get("Scientific Focus"),
                "project_setting": index_row.get("project_setting") or index_row.get("Project Setting"),
                "record_type": index_row.get("record_type") or index_row.get("Record Type") or "Investigation",
                "doi": index_row.get("doi") or index_row.get("DOI"),
                "doi_url": f"https://doi.org/{index_row.get('doi')}" if index_row.get("doi") else None,
                "psi_record_url": f"{self.PSI_BASE_URL}{psi_id}",
                "objectives": index_row.get("objectives") or index_row.get("Objectives"),
                "approach": index_row.get("approach") or index_row.get("Approach"),
                "sources": [f"{self.PSI_BASE_URL}{psi_id}"],
                "metadata_status": VerificationStatus.VERIFIED.value if index_row.get("title") else VerificationStatus.PENDING.value,
                "tags": ["nasa-psi", "combustion-science"],
            }

        # Validate URLs
        validated_sources = []
        for source in metadata.get("sources", []):
            async with URLValidator(allowed_domains=self.allowed_domains) as validator:
                result = await validator.validate_url(source)
                if result.is_valid:
                    validated_sources.append(source)
                else:
                    logger.warning("source_url_validation_failed", url=source, error=result.error)

        if validated_sources:
            metadata["sources"] = validated_sources

        # Create investigation model
        try:
            investigation = PSIInvestigation(**metadata)
        except Exception as e:
            return IngestionResult(
                success=False,
                error=f"Failed to create investigation model: {str(e)}"
            )

        # Store in database
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO psi_investigations (
                        psi_id, title, description, research_area, sub_research_area,
                        scientific_focus, project_setting, record_type, doi, doi_url,
                        psi_record_url, objectives, approach, sources, metadata_status,
                        verified_at, tags
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                    ON CONFLICT (psi_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        sub_research_area = EXCLUDED.sub_research_area,
                        scientific_focus = EXCLUDED.scientific_focus,
                        project_setting = EXCLUDED.project_setting,
                        doi = EXCLUDED.doi,
                        doi_url = EXCLUDED.doi_url,
                        objectives = EXCLUDED.objectives,
                        approach = EXCLUDED.approach,
                        sources = EXCLUDED.sources,
                        metadata_status = EXCLUDED.metadata_status,
                        verified_at = EXCLUDED.verified_at,
                        tags = EXCLUDED.tags,
                        updated_at = NOW()
                    """,
                    investigation.psi_id,
                    investigation.title,
                    investigation.description,
                    investigation.research_area,
                    investigation.sub_research_area,
                    investigation.scientific_focus,
                    investigation.project_setting,
                    investigation.record_type,
                    investigation.doi,
                    investigation.doi_url,
                    investigation.psi_record_url,
                    investigation.objectives,
                    investigation.approach,
                    investigation.sources,
                    investigation.metadata_status,
                    investigation.verified_at,
                    investigation.tags,
                )
        except Exception as e:
            logger.error("investigation_db_insert_failed", psi_id=psi_id, error=str(e))
            return IngestionResult(
                success=False,
                error=f"Database insert failed: {str(e)}"
            )

        return IngestionResult(success=True, investigation=investigation)

    async def ingest_all(self) -> list[IngestionResult]:
        """Ingest all 26 selected investigations."""
        logger.info("starting_psi_ingestion", count=len(self.SELECTED_PSI_IDS))

        # Fetch index
        index_rows = await self.fetch_psi_index()
        logger.info("fetched_psi_index", total_rows=len(index_rows))

        # Filter to selected
        selected_rows = self.filter_selected_investigations(index_rows)
        logger.info("filtered_selected_investigations", count=len(selected_rows))

        # Ingest each
        results = []
        for row in selected_rows:
            result = await self.ingest_single(row)
            results.append(result)
            if result.success:
                logger.info("investigation_ingested", psi_id=result.investigation.psi_id)
            else:
                logger.error("investigation_ingestion_failed", psi_id=row.get("psi_id"), error=result.error)

        successful = sum(1 for r in results if r.success)
        logger.info("psi_ingestion_complete", successful=successful, total=len(results))

        return results


async def run_psi_ingestion(
    db_pool,
    allowed_domains: Optional[set[str]] = None,
) -> list[IngestionResult]:
    """Convenience function to run PSI ingestion."""
    async with PSIIngester(db_pool, allowed_domains) as ingester:
        return await ingester.ingest_all()