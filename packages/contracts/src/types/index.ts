/**
 * Shared type definitions for the Semantic Data Discovery & Interactive Dashboards project.
 * These types are used across all services to ensure consistency.
 */

// ============================================================================
// Core Domain Types
// ============================================================================

/** Unique identifier for a PSI investigation (e.g., "PSI-20") */
export type PSIId = `PSI-${number}`;

/** Unique identifier for a dataset */
export type DatasetId = string;

/** Supported data formats */
export type DataFormat = 'csv' | 'parquet' | 'json' | 'xlsx' | 'api' | 'sql' | 'unknown';

/** Column data types */
export type ColumnType = 'numeric' | 'categorical' | 'datetime' | 'text' | 'boolean' | 'unknown';

/** Verification status for metadata */
export type VerificationStatus = 'verified' | 'pending' | 'failed' | 'unknown';

/** Access policy for datasets */
export type AccessPolicy = 'public' | 'restricted' | 'authenticated' | 'unknown';

/** Source collection identifier */
export const SOURCE_COLLECTION = 'NASA PSI — Combustion Science: 26 Selected Investigations' as const;

// ============================================================================
// Dataset & Investigation Types
// ============================================================================

/** Represents a column in a dataset schema */
export interface DatasetColumn {
  name: string;
  type: ColumnType;
  description?: string;
  unit?: string;
  nullable: boolean;
  sampleValues?: unknown[];
  statistics?: ColumnStatistics;
}

/** Statistical profile for a numeric column */
export interface ColumnStatistics {
  count: number;
  nullCount: number;
  min: number;
  max: number;
  mean: number;
  median: number;
  stdDev: number;
  quartiles: {
    q1: number;
    q2: number;
    q3: number;
  };
  uniqueCount?: number;
}

/** Schema information for a dataset */
export interface DatasetSchema {
  columns: DatasetColumn[];
  rowCount?: number;
  byteSize?: number;
  profiledAt?: string;
  profileVersion?: string;
}

/** PSI Investigation metadata */
export interface PSIInvestigation {
  psiId: PSIId;
  title: string;
  description: string;
  researchArea: string;
  subResearchArea?: string;
  scientificFocus?: string;
  projectSetting?: string;
  recordType: string;
  doi?: string;
  doiUrl?: string;
  psiRecordUrl: string;
  objectives?: string;
  approach?: string;
  sources: string[];
  metadataStatus: VerificationStatus;
  verifiedAt?: string;
  tags: string[];
}

/** Dataset metadata in the catalog */
export interface Dataset {
  id: DatasetId;
  psiId: PSIId;
  name: string;
  description: string;
  url: string;
  urlType: 'investigation_page' | 'direct_download' | 'doi' | 'unverified';
  format: DataFormat;
  schema?: DatasetSchema;
  numericColumns: string[];
  source: string;
  license?: string;
  accessPolicy: AccessPolicy;
  coverage?: {
    temporal?: string;
    geographic?: string;
  };
  updatedAt?: string;
  catalogVersion: string;
  embeddingModel?: string;
  embeddingVersion?: string;
  verificationStatus: VerificationStatus;
  verifiedAt?: string;
  tags: string[];
  provenance: {
    investigationUrl: string;
    datasetUrl: string;
    retrievedAt: string;
  };
}

// ============================================================================
// Search Types
// ============================================================================

/** Search request payload */
export interface SearchRequest {
  query: string;
  filters?: SearchFilters;
  options?: SearchOptions;
}

/** Search filters */
export interface SearchFilters {
  psiIds?: PSIId[];
  tags?: string[];
  formats?: DataFormat[];
  hasNumericData?: boolean;
  verificationStatus?: VerificationStatus[];
}

/** Search options */
export interface SearchOptions {
  includeSchema?: boolean;
  includeStatistics?: boolean;
  maxResults?: number;
  minScore?: number;
}

/** Individual search result */
export interface SearchResult {
  id: DatasetId;
  psiId: PSIId;
  name: string;
  description: string;
  url: string;
  format: DataFormat;
  numericColumns: string[];
  score: number;
  investigationTitle?: string;
  verificationStatus: VerificationStatus;
}

/** Complete search response */
export interface SearchResponse {
  query: string;
  status: 'matches_found' | 'no_matches';
  source_collection: typeof SOURCE_COLLECTION;
  data_filter: 'numeric_only';
  total_matches: number;
  datasets: SearchResult[];
  searchMetadata: {
    catalogVersion: string;
    embeddingModel: string;
    embeddingVersion: string;
    queryEmbedding?: number[];
    retrievedAt: string;
    processingTimeMs: number;
  };
}

// ============================================================================
// Summary Types
// ============================================================================

/** Summary request */
export interface SummaryRequest {
  datasetId: DatasetId;
  options?: {
    includeStatistics?: boolean;
    maxLength?: number;
  };
}

/** Summary response */
export interface SummaryResponse {
  datasetId: DatasetId;
  title: string;
  executiveSummary: string;
  keyVariables: string[];
  coverage: {
    temporal?: string;
    geographic?: string;
    rowCount?: number;
  };
  findings: Array<{
    description: string;
    evidence: string;
    source: 'metadata' | 'computed_statistics';
  }>;
  limitations: string[];
  warnings: string[];
  sources: Array<{
    type: 'metadata' | 'statistics' | 'schema';
    reference: string;
  }>;
  generatedAt: string;
  catalogVersion: string;
  profilingVersion?: string;
}

// ============================================================================
// Visualization Types
// ============================================================================

/** Chart configuration request */
export interface ChartPreviewRequest {
  datasetId: DatasetId;
  chartType: 'bar' | 'line' | 'scatter' | 'histogram';
  xAxis: string;
  yAxis?: string;
  groupBy?: string;
  filters?: Record<string, unknown>;
  options?: ChartOptions;
}

/** Chart options */
export interface ChartOptions {
  title?: string;
  xLabel?: string;
  yLabel?: string;
  color?: string;
  width?: number;
  height?: number;
  aggregation?: 'none' | 'mean' | 'sum' | 'count' | 'min' | 'max';
  limit?: number;
  offset?: number;
}

/** Chart preview response */
export interface ChartPreviewResponse {
  datasetId: DatasetId;
  chartType: 'bar' | 'line' | 'scatter' | 'histogram';
  spec: Record<string, unknown>; // Vega-Lite or Plotly spec
  data: Record<string, unknown>[];
  columns: {
    x: DatasetColumn;
    y?: DatasetColumn;
    groupBy?: DatasetColumn;
  };
  warnings: string[];
  metadata: {
    rowCount: number;
    filteredRowCount: number;
    processingTimeMs: number;
    memoryUsedBytes: number;
  };
}

// ============================================================================
// Dataset Detail Types
// ============================================================================

/** Dataset detail response (GET /api/v1/datasets/{id}) */
export interface DatasetDetailResponse extends Dataset {
  investigation?: PSIInvestigation;
}

/** Dataset preview response (GET /api/v1/datasets/{id}/preview) */
export interface DatasetPreviewResponse {
  datasetId: DatasetId;
  columns: DatasetColumn[];
  rows: Record<string, unknown>[];
  totalRows: number;
  returnedRows: number;
  offset: number;
  limit: number;
  warnings: string[];
}

// ============================================================================
// Error Types
// ============================================================================

/** API error codes */
export type APIErrorCode =
  | 'VALIDATION_ERROR'
  | 'NOT_FOUND'
  | 'UNAUTHORIZED'
  | 'FORBIDDEN'
  | 'INTERNAL_ERROR'
  | 'SERVICE_UNAVAILABLE'
  | 'RATE_LIMITED'
  | 'SSRF_BLOCKED'
  | 'INVALID_URL'
  | 'DATA_ACCESS_ERROR'
  | 'PROFILING_ERROR'
  | 'SUMMARY_GENERATION_ERROR'
  | 'CHART_GENERATION_ERROR'
  | 'SEARCH_ERROR';

/** Standard API error response */
export interface APIErrorResponse {
  error: {
    code: APIErrorCode;
    message: string;
    details?: Record<string, unknown>;
    requestId: string;
    timestamp: string;
  };
}

/** Validation error detail */
export interface ValidationErrorDetail {
  field: string;
  message: string;
  code: string;
  value?: unknown;
}

// ============================================================================
// Health & Monitoring Types
// ============================================================================

/** Health check response */
export interface HealthCheckResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  services: Record<string, {
    status: 'healthy' | 'degraded' | 'unhealthy';
    latencyMs?: number;
    details?: Record<string, unknown>;
  }>;
  timestamp: string;
}

// ============================================================================
// Type Guards
// ============================================================================

export function isSearchResponse(obj: unknown): obj is SearchResponse {
  if (!obj || typeof obj !== 'object') return false;
  const resp = obj as Record<string, unknown>;
  return (
    typeof resp.query === 'string' &&
    (resp.status === 'matches_found' || resp.status === 'no_matches') &&
    resp.source_collection === SOURCE_COLLECTION &&
    resp.data_filter === 'numeric_only' &&
    typeof resp.total_matches === 'number' &&
    Array.isArray(resp.datasets)
  );
}

export function isDataset(obj: unknown): obj is Dataset {
  if (!obj || typeof obj !== 'object') return false;
  const d = obj as Record<string, unknown>;
  return (
    typeof d.id === 'string' &&
    typeof d.psiId === 'string' &&
    d.psiId.startsWith('PSI-') &&
    typeof d.name === 'string' &&
    typeof d.description === 'string' &&
    typeof d.url === 'string' &&
    typeof d.format === 'string' &&
    Array.isArray(d.numericColumns) &&
    typeof d.accessPolicy === 'string'
  );
}

export function isSearchResult(obj: unknown): obj is SearchResult {
  if (!obj || typeof obj !== 'object') return false;
  const r = obj as Record<string, unknown>;
  return (
    typeof r.id === 'string' &&
    typeof r.psiId === 'string' &&
    typeof r.name === 'string' &&
    typeof r.description === 'string' &&
    typeof r.url === 'string' &&
    typeof r.format === 'string' &&
    Array.isArray(r.numericColumns) &&
    typeof r.score === 'number'
  );
}