/**
 * @enigma-sac/contracts - Shared contracts for Semantic Data Discovery & Interactive Dashboards
 *
 * This package provides:
 * - TypeScript type definitions for all domain objects
 * - JSON Schema definitions for API request/response validation
 * - OpenAPI specification for the REST API
 * - Type guards for runtime validation
 */

// Types
export * from './types';

// Schema validation utilities
export { validateSearchRequest, validateSearchResponse } from './validation/search';
export { validateDataset, validateDatasetSchema, validateDatasetPreview } from './validation/dataset';
export { validateSummaryRequest, validateSummaryResponse } from './validation/summary';
export { validateChartPreviewRequest, validateChartPreviewResponse } from './validation/chart';
export { validateAPIError } from './validation/error';

// Constants
export { SOURCE_COLLECTION } from './types';