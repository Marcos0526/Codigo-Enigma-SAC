"""URL validation utilities for catalog service."""

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx
import structlog

from services.catalog.src.models.catalog import URLType

logger = structlog.get_logger()


@dataclass
class URLValidationResult:
    """Result of URL validation."""

    is_valid: bool
    url_type: str  # investigation_page, direct_download, doi, unverified
    content_type: Optional[str] = None
    content_length: Optional[int] = None
    error: Optional[str] = None
    final_url: Optional[str] = None
    redirect_chain: list[str] = None

    def __post_init__(self):
        if self.redirect_chain is None:
            self.redirect_chain = []


class URLValidator:
    """Validates and classifies URLs for NASA PSI datasets."""

    # Allowlisted domains for data access
    ALLOWED_DOMAINS = {
        "psi.nasa.gov",
        "raw.githubusercontent.com",
        "data.nasa.gov",
        "doi.org",
        "github.com",
        "githubusercontent.com",
    }

    # Blocked IP ranges (SSRF protection)
    BLOCKED_IP_RANGES = [
        "127.0.0.0/8",      # Loopback
        "10.0.0.0/8",       # Private
        "172.16.0.0/12",    # Private
        "192.168.0.0/16",   # Private
        "169.254.0.0/16",   # Link-local
        "::1/128",          # IPv6 loopback
        "fc00::/7",         # IPv6 private
        "fe80::/10",        # IPv6 link-local
    ]

    # File extensions that indicate downloadable data
    DATA_EXTENSIONS = {
        ".csv", ".parquet", ".json", ".xlsx", ".xls", ".tsv",
        ".txt", ".dat", ".nc", ".hdf5", ".h5", ".fits", ".zip",
        ".gz", ".tar", ".tgz"
    }

    # Patterns for DOI URLs
    DOI_PATTERN = re.compile(r"^https?://(?:dx\.)?doi\.org/")

    # Patterns for NASA PSI investigation pages
    PSI_INVESTIGATION_PATTERN = re.compile(
        r"^https?://psi\.nasa\.gov/physci/repo/data/investigations/PSI-\d+/?$"
    )

    def __init__(
        self,
        allowed_domains: Optional[set[str]] = None,
        timeout: float = 10.0,
        max_redirects: int = 5,
        max_content_length: int = 100 * 1024 * 1024,  # 100 MB
    ):
        self.allowed_domains = allowed_domains or self.ALLOWED_DOMAINS
        self.timeout = timeout
        self.max_redirects = max_redirects
        self.max_content_length = max_content_length
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True,
            max_redirects=self.max_redirects,
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
                max_redirects=self.max_redirects,
            )
        return self._client

    def _is_allowed_domain(self, url: str) -> bool:
        """Check if URL domain is in allowlist."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Check exact match or subdomain
            for allowed in self.allowed_domains:
                if domain == allowed or domain.endswith("." + allowed):
                    return True
            return False
        except Exception:
            return False

    def _classify_url_type(self, url: str, content_type: Optional[str] = None) -> str:
        """Classify URL type based on pattern and content type."""
        # Check for DOI
        if self.DOI_PATTERN.match(url):
            return URLType.DOI.value

        # Check for PSI investigation page pattern
        if self.PSI_INVESTIGATION_PATTERN.match(url):
            return URLType.INVESTIGATION_PAGE.value

        # Check for direct download extensions
        parsed = urlparse(url)
        path = parsed.path.lower()
        for ext in self.DATA_EXTENSIONS:
            if path.endswith(ext):
                return URLType.DIRECT_DOWNLOAD.value

        # Check content type if available
        if content_type:
            data_types = [
                "text/csv", "application/csv", "application/vnd.ms-excel",
                "application/parquet", "application/json", "application/octet-stream",
                "application/zip", "application/gzip", "application/x-tar",
                "text/plain", "text/tab-separated-values"
            ]
            if any(dt in content_type.lower() for dt in data_types):
                return URLType.DIRECT_DOWNLOAD.value

        return URLType.UNVERIFIED.value

    async def validate_url(self, url: str) -> URLValidationResult:
        """Validate a URL and classify its type."""
        # Basic URL validation
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return URLValidationResult(
                    is_valid=False,
                    url_type=URLType.UNVERIFIED.value,
                    error="Invalid URL format"
                )
        except Exception as e:
            return URLValidationResult(
                is_valid=False,
                url_type=URLType.UNVERIFIED.value,
                error=f"URL parsing failed: {str(e)}"
            )

        # Check allowlist
        if not self._is_allowed_domain(url):
            logger.warning("url_blocked_not_allowlisted", url=url)
            return URLValidationResult(
                is_valid=False,
                url_type=URLType.UNVERIFIED.value,
                error="Domain not in allowlist"
            )

        # Check for SSRF (basic - in production use proper IP resolution)
        # This is a placeholder - real implementation should resolve DNS and check IPs

        # Make HEAD request to check accessibility and get headers
        try:
            client = self._get_client()
            response = await client.head(url, follow_redirects=True)
            response.raise_for_status()

            final_url = str(response.url)
            content_type = response.headers.get("content-type")
            content_length = response.headers.get("content-length")

            # Check content length
            if content_length and int(content_length) > self.max_content_length:
                return URLValidationResult(
                    is_valid=False,
                    url_type=URLType.UNVERIFIED.value,
                    error=f"Content too large: {content_length} bytes (max {self.max_content_length})",
                    final_url=final_url,
                    content_type=content_type,
                    content_length=int(content_length)
                )

            url_type = self._classify_url_type(final_url, content_type)

            return URLValidationResult(
                is_valid=True,
                url_type=url_type,
                content_type=content_type,
                content_length=int(content_length) if content_length else None,
                final_url=final_url,
                redirect_chain=[str(r.url) for r in response.history] if response.history else [final_url]
            )

        except httpx.HTTPStatusError as e:
            return URLValidationResult(
                is_valid=False,
                url_type=URLType.UNVERIFIED.value,
                error=f"HTTP {e.response.status_code}: {e.response.reason_phrase}",
                final_url=str(e.response.url)
            )
        except httpx.TimeoutException:
            return URLValidationResult(
                is_valid=False,
                url_type=URLType.UNVERIFIED.value,
                error="Request timeout"
            )
        except httpx.TooManyRedirects:
            return URLValidationResult(
                is_valid=False,
                url_type=URLType.UNVERIFIED.value,
                error="Too many redirects"
            )
        except Exception as e:
            logger.error("url_validation_error", url=url, error=str(e))
            return URLValidationResult(
                is_valid=False,
                url_type=URLType.UNVERIFIED.value,
                error=f"Validation failed: {str(e)}"
            )

    async def validate_multiple(self, urls: list[str]) -> dict[str, URLValidationResult]:
        """Validate multiple URLs concurrently."""
        import asyncio
        tasks = [self.validate_url(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        validated = {}
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                validated[url] = URLValidationResult(
                    is_valid=False,
                    url_type=URLType.UNVERIFIED.value,
                    error=str(result)
                )
            else:
                validated[url] = result
        return validated


# Convenience function
async def validate_dataset_url(
    url: str,
    allowed_domains: Optional[set[str]] = None,
    timeout: float = 10.0,
) -> URLValidationResult:
    """Convenience function to validate a single dataset URL."""
    async with URLValidator(allowed_domains=allowed_domains, timeout=timeout) as validator:
        return await validator.validate_url(url)