"""Catalog data models for NASA PSI Combustion Science datasets."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl, field_validator
from pgvector.sqlalchemy import Vector

from sqlalchemy import (
    ARRAY,
    JSON,
    BigInteger,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class VerificationStatus(str, Enum):
    """Verification status for metadata and numerical content."""

    VERIFIED = "verified"
    PENDING = "pending"
    FAILED = "failed"
    UNKNOWN = "unknown"


class AccessPolicy(str, Enum):
    """Access policy for datasets."""

    PUBLIC = "public"
    RESTRICTED = "restricted"
    AUTHENTICATED = "authenticated"
    UNKNOWN = "unknown"


class URLType(str, Enum):
    """Type of URL - distinguishes investigation pages from direct downloads."""

    INVESTIGATION_PAGE = "investigation_page"
    DIRECT_DOWNLOAD = "direct_download"
    DOI = "doi"
    UNVERIFIED = "unverified"


class DataFormat(str, Enum):
    """Supported data formats."""

    CSV = "csv"
    PARQUET = "parquet"
    JSON = "json"
    XLSX = "xlsx"
    API = "api"
    SQL = "sql"
    UNKNOWN = "unknown"


class ColumnType(str, Enum):
    """Column data types."""

    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    DATETIME = "datetime"
    TEXT = "text"
    BOOLEAN = "boolean"
    UNKNOWN = "unknown"


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    pass


class PSIInvestigation(Base):
    """PSI Investigation metadata."""

    __tablename__ = "psi_investigations"

    psi_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    research_area: Mapped[str] = mapped_column(String(100), nullable=False, default="Combustion Science")
    sub_research_area: Mapped[Optional[str]] = mapped_column(String(100))
    scientific_focus: Mapped[Optional[str]] = mapped_column(Text)
    project_setting: Mapped[Optional[str]] = mapped_column(Text)
    record_type: Mapped[str] = mapped_column(String(50), nullable=False, default="Investigation")
    doi: Mapped[Optional[str]] = mapped_column(String(100))
    doi_url: Mapped[Optional[str]] = mapped_column(Text)
    psi_record_url: Mapped[str] = mapped_column(Text, nullable=False)
    objectives: Mapped[Optional[str]] = mapped_column(Text)
    approach: Mapped[Optional[str]] = mapped_column(Text)
    sources: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    metadata_status: Mapped[VerificationStatus] = mapped_column(
        SQLEnum(VerificationStatus), nullable=False, default=VerificationStatus.UNKNOWN
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    datasets: Mapped[list["Dataset"]] = relationship("Dataset", back_populates="investigation", lazy="selectin")

    # Indexes
    __table_args__ = (
        Index("ix_psi_investigations_tags", "tags", postgresql_using="gin"),
        Index("ix_psi_investigations_sub_area", "sub_research_area"),
        Index("ix_psi_investigations_status", "metadata_status"),
    )


class Dataset(Base):
    """Dataset metadata in the catalog."""

    __tablename__ = "datasets"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    dataset_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    psi_id: Mapped[str] = mapped_column(String(20), ForeignKey("psi_investigations.psi_id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    url_type: Mapped[URLType] = mapped_column(
        SQLEnum(URLType), nullable=False, default=URLType.UNVERIFIED
    )
    format: Mapped[DataFormat] = mapped_column(
        SQLEnum(DataFormat), nullable=False, default=DataFormat.UNKNOWN
    )
    numeric_columns: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    source: Mapped[Optional[str]] = mapped_column(Text)
    license: Mapped[Optional[str]] = mapped_column(Text)
    access_policy: Mapped[AccessPolicy] = mapped_column(
        SQLEnum(AccessPolicy), nullable=False, default=AccessPolicy.UNKNOWN
    )
    coverage_temporal: Mapped[Optional[str]] = mapped_column(Text)
    coverage_geographic: Mapped[Optional[str]] = mapped_column(Text)
    catalog_version: Mapped[str] = mapped_column(String(20), nullable=False)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(100))
    embedding_version: Mapped[Optional[str]] = mapped_column(String(20))
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SQLEnum(VerificationStatus), nullable=False, default=VerificationStatus.UNKNOWN
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    provenance_investigation_url: Mapped[str] = mapped_column(Text, nullable=False)
    provenance_dataset_url: Mapped[str] = mapped_column(Text, nullable=False)
    provenance_retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    investigation: Mapped["PSIInvestigation"] = relationship("PSIInvestigation", back_populates="datasets")
    schemas: Mapped[list["DatasetSchema"]] = relationship("DatasetSchema", back_populates="dataset", lazy="selectin")
    profile: Mapped[Optional["DatasetProfile"]] = relationship("DatasetProfile", back_populates="dataset", uselist=False)
    embeddings: Mapped[list["DatasetEmbedding"]] = relationship("DatasetEmbedding", back_populates="dataset", lazy="selectin")

    # Indexes
    __table_args__ = (
        Index("ix_datasets_psi_id", "psi_id"),
        Index("ix_datasets_verification", "verification_status"),
        Index("ix_datasets_format", "format"),
        Index("ix_datasets_tags", "tags", postgresql_using="gin"),
        Index("ix_datasets_numeric_columns", "numeric_columns", postgresql_using="gin"),
        Index("ix_datasets_catalog_version", "catalog_version"),
    )


class DatasetSchema(Base):
    """Dataset schema (column metadata)."""

    __tablename__ = "dataset_schemas"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    dataset_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    column_name: Mapped[str] = mapped_column(String(255), nullable=False)
    column_type: Mapped[ColumnType] = mapped_column(SQLEnum(ColumnType), nullable=False, default=ColumnType.UNKNOWN)
    description: Mapped[Optional[str]] = mapped_column(Text)
    unit: Mapped[Optional[str]] = mapped_column(String(100))
    nullable: Mapped[bool] = mapped_column(nullable=False, default=True)
    sample_values: Mapped[Optional[dict]] = mapped_column(JSON)
    statistics: Mapped[Optional[dict]] = mapped_column(JSON)
    ordinal_position: Mapped[int] = mapped_column(Integer, nullable=False)
    profiled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    profile_version: Mapped[str] = mapped_column(String(20), nullable=False)

    # Relationships
    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="schemas")

    # Constraints
    __table_args__ = (
        Index("ix_dataset_schemas_dataset", "dataset_id"),
        Index("ix_dataset_schemas_type", "column_type"),
        # Unique constraint on dataset_id + column_name
    )


class DatasetProfile(Base):
    """Dataset profiling metadata."""

    __tablename__ = "dataset_profiles"

    dataset_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), primary_key=True)
    row_count: Mapped[Optional[int]] = mapped_column(BigInteger)
    byte_size: Mapped[Optional[int]] = mapped_column(BigInteger)
    column_count: Mapped[Optional[int]] = mapped_column(Integer)
    profiled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    profile_version: Mapped[str] = mapped_column(String(20), nullable=False)
    profiling_duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    warnings: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)

    # Relationships
    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="profile")


class DatasetEmbedding(Base):
    """Dataset embeddings for vector search."""

    __tablename__ = "dataset_embeddings"

    dataset_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="embeddings")


# =============================================================================
# Pydantic Models for API/Serialization
# =============================================================================

class PSIInvestigationCreate(BaseModel):
    """Model for creating a PSI investigation."""

    psi_id: str = Field(..., pattern=r"^PSI-\d+$")
    title: str
    description: Optional[str] = None
    research_area: str = "Combustion Science"
    sub_research_area: Optional[str] = None
    scientific_focus: Optional[str] = None
    project_setting: Optional[str] = None
    record_type: str = "Investigation"
    doi: Optional[str] = None
    doi_url: Optional[HttpUrl] = None
    psi_record_url: HttpUrl
    objectives: Optional[str] = None
    approach: Optional[str] = None
    sources: list[HttpUrl] = Field(default_factory=list)
    metadata_status: VerificationStatus = VerificationStatus.UNKNOWN
    tags: list[str] = Field(default_factory=list)


class PSIInvestigationResponse(BaseModel):
    """Model for PSI investigation API response."""

    psi_id: str
    title: str
    description: Optional[str]
    research_area: str
    sub_research_area: Optional[str]
    scientific_focus: Optional[str]
    project_setting: Optional[str]
    record_type: str
    doi: Optional[str]
    doi_url: Optional[str]
    psi_record_url: str
    objectives: Optional[str]
    approach: Optional[str]
    sources: list[str]
    metadata_status: VerificationStatus
    verified_at: Optional[datetime]
    tags: list[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DatasetCreate(BaseModel):
    """Model for creating a dataset."""

    dataset_id: str
    psi_id: str
    name: str
    description: Optional[str] = None
    url: HttpUrl
    url_type: URLType = URLType.UNVERIFIED
    format: DataFormat = DataFormat.UNKNOWN
    numeric_columns: list[str] = Field(default_factory=list)
    source: Optional[str] = None
    license: Optional[str] = None
    access_policy: AccessPolicy = AccessPolicy.UNKNOWN
    coverage_temporal: Optional[str] = None
    coverage_geographic: Optional[str] = None
    catalog_version: str
    embedding_model: Optional[str] = None
    embedding_version: Optional[str] = None
    verification_status: VerificationStatus = VerificationStatus.UNKNOWN
    verified_at: Optional[datetime] = None
    tags: list[str] = Field(default_factory=list)
    provenance_investigation_url: HttpUrl
    provenance_dataset_url: HttpUrl


class DatasetResponse(BaseModel):
    """Model for dataset API response."""

    id: UUID
    dataset_id: str
    psi_id: str
    name: str
    description: Optional[str]
    url: str
    url_type: URLType
    format: DataFormat
    numeric_columns: list[str]
    source: Optional[str]
    license: Optional[str]
    access_policy: AccessPolicy
    coverage_temporal: Optional[str]
    coverage_geographic: Optional[str]
    catalog_version: str
    embedding_model: Optional[str]
    embedding_version: Optional[str]
    verification_status: VerificationStatus
    verified_at: Optional[datetime]
    tags: list[str]
    provenance_investigation_url: str
    provenance_dataset_url: str
    provenance_retrieved_at: datetime
    created_at: datetime
    updated_at: datetime
    investigation_title: Optional[str] = None

    class Config:
        from_attributes = True


class DatasetSchemaCreate(BaseModel):
    """Model for creating a dataset schema column."""

    column_name: str
    column_type: ColumnType = ColumnType.UNKNOWN
    description: Optional[str] = None
    unit: Optional[str] = None
    nullable: bool = True
    sample_values: Optional[dict] = None
    statistics: Optional[dict] = None
    ordinal_position: int


class DatasetSchemaResponse(BaseModel):
    """Model for dataset schema API response."""

    id: UUID
    dataset_id: UUID
    column_name: str
    column_type: ColumnType
    description: Optional[str]
    unit: Optional[str]
    nullable: bool
    sample_values: Optional[dict]
    statistics: Optional[dict]
    ordinal_position: int
    profiled_at: datetime
    profile_version: str

    class Config:
        from_attributes = True


class DatasetProfileResponse(BaseModel):
    """Model for dataset profile API response."""

    dataset_id: UUID
    row_count: Optional[int]
    byte_size: Optional[int]
    column_count: Optional[int]
    profiled_at: datetime
    profile_version: str
    profiling_duration_ms: Optional[int]
    warnings: list[str]

    class Config:
        from_attributes = True


class SearchResult(BaseModel):
    """Search result model."""

    id: UUID
    dataset_id: str
    psi_id: str
    name: str
    description: Optional[str]
    url: str
    format: DataFormat
    numeric_columns: list[str]
    score: float
    investigation_title: Optional[str]
    verification_status: VerificationStatus


# =============================================================================
# Constants
# =============================================================================

SOURCE_COLLECTION = "NASA PSI — Combustion Science: 26 Selected Investigations"
DATA_FILTER = "numeric_only"
CATALOG_VERSION = "1.0.0"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_VERSION = "1.0.0"
VECTOR_DIMENSIONS = 384