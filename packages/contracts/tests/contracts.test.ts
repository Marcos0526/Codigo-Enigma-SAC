import { describe, it, expect } from 'vitest';
import {
  validateSearchRequest,
  validateSearchResponse,
  validateDataset,
  validateDatasetSchema,
  validateDatasetPreview,
  validateSummaryRequest,
  validateSummaryResponse,
  validateChartPreviewRequest,
  validateChartPreviewResponse,
  validateAPIError,
} from '@enigma-sac/contracts';

describe('Contracts Validation', () => {
  describe('SearchRequest', () => {
    it('validates a minimal valid request', () => {
      const result = validateSearchRequest({ query: 'test query' });
      expect(result.valid).toBe(true);
    });

    it('rejects empty query', () => {
      const result = validateSearchRequest({ query: '' });
      expect(result.valid).toBe(false);
    });

    it('rejects missing query', () => {
      const result = validateSearchRequest({});
      expect(result.valid).toBe(false);
    });

    it('validates with filters and options', () => {
      const result = validateSearchRequest({
        query: 'combustion temperature',
        filters: {
          psiIds: ['PSI-20', 'PSI-21'],
          hasNumericData: true,
        },
        options: {
          maxResults: 50,
          minScore: 0.5,
        },
      });
      expect(result.valid).toBe(true);
    });

    it('rejects invalid psiId format', () => {
      const result = validateSearchRequest({
        query: 'test',
        filters: { psiIds: ['INVALID-123'] },
      });
      expect(result.valid).toBe(false);
    });
  });

  describe('SearchResponse', () => {
    const validResponse = {
      query: 'test query',
      status: 'matches_found' as const,
      source_collection: 'NASA PSI — Combustion Science: 26 Selected Investigations',
      data_filter: 'numeric_only' as const,
      total_matches: 1,
      datasets: [{
        id: 'test-001',
        psiId: 'PSI-20',
        name: 'Test Dataset',
        description: 'Test description',
        url: 'https://example.com/data.csv',
        format: 'csv' as const,
        numericColumns: ['temperature'],
        score: 0.9,
        verificationStatus: 'verified' as const,
      }],
      searchMetadata: {
        catalogVersion: '1.0.0',
        embeddingModel: 'test-model',
        embeddingVersion: '1.0.0',
        retrievedAt: new Date().toISOString(),
        processingTimeMs: 100,
      },
    };

    it('validates a correct response', () => {
      const result = validateSearchResponse(validResponse);
      expect(result.valid).toBe(true);
    });

    it('rejects wrong source_collection', () => {
      const invalidResponse = { ...validResponse, source_collection: 'Wrong Collection' };
      const result = validateSearchResponse(invalidResponse);
      expect(result.valid).toBe(false);
    });

    it('rejects wrong data_filter', () => {
      const invalidResponse = { ...validResponse, data_filter: 'all_data' };
      const result = validateSearchResponse(invalidResponse);
      expect(result.valid).toBe(false);
    });

    it('validates no_matches status with empty datasets', () => {
      const noMatches = {
        ...validResponse,
        status: 'no_matches' as const,
        total_matches: 0,
        datasets: [],
      };
      const result = validateSearchResponse(noMatches);
      expect(result.valid).toBe(true);
    });

    it('Note: total_matches == datasets.length is an application-level check, not schema-enforced', () => {
      // This is a design decision: the schema doesn't enforce this relationship
      // because JSON Schema cannot express cross-field equality constraints
      // The application must validate this separately
      const mismatched = { ...validResponse, total_matches: 5 };
      const result = validateSearchResponse(mismatched);
      // Schema validation passes, but application should reject
      expect(result.valid).toBe(true);
    });
  });

  describe('Dataset', () => {
    const validDataset = {
      id: 'test-001',
      psiId: 'PSI-20',
      name: 'Test Dataset',
      description: 'Test description',
      url: 'https://example.com/data.csv',
      urlType: 'direct_download' as const,
      format: 'csv' as const,
      numericColumns: ['temperature', 'pressure'],
      source: 'NASA PSI',
      accessPolicy: 'public' as const,
      catalogVersion: '1.0.0',
      verificationStatus: 'verified' as const,
      tags: ['combustion', 'temperature'],
      provenance: {
        investigationUrl: 'https://psi.nasa.gov/physci/repo/data/investigations/PSI-20',
        datasetUrl: 'https://example.com/data.csv',
        retrievedAt: new Date().toISOString(),
      },
    };

    it('validates a correct dataset', () => {
      const result = validateDataset(validDataset);
      expect(result.valid).toBe(true);
    });

    it('rejects missing required fields', () => {
      const result = validateDataset({ ...validDataset, id: undefined });
      expect(result.valid).toBe(false);
    });

    it('rejects invalid psiId format', () => {
      const result = validateDataset({ ...validDataset, psiId: 'INVALID' });
      expect(result.valid).toBe(false);
    });

    it('rejects invalid urlType', () => {
      const result = validateDataset({ ...validDataset, urlType: 'invalid' as any });
      expect(result.valid).toBe(false);
    });

    it('validates urlType distinctions', () => {
      const investigationPage = { ...validDataset, urlType: 'investigation_page' as const };
      const directDownload = { ...validDataset, urlType: 'direct_download' as const };
      const doi = { ...validDataset, urlType: 'doi' as const };
      const unverified = { ...validDataset, urlType: 'unverified' as const };

      expect(validateDataset(investigationPage).valid).toBe(true);
      expect(validateDataset(directDownload).valid).toBe(true);
      expect(validateDataset(doi).valid).toBe(true);
      expect(validateDataset(unverified).valid).toBe(true);
    });
  });

  describe('DatasetSchema', () => {
    const validSchema = {
      datasetId: 'test-001',
      columns: [{
        name: 'temperature',
        type: 'numeric' as const,
        nullable: false,
        unit: 'K',
        statistics: {
          count: 100,
          nullCount: 0,
          min: 300,
          max: 2000,
          mean: 1200,
          median: 1150,
          stdDev: 300,
          quartiles: { q1: 900, q2: 1150, q3: 1400 },
        },
      }],
      rowCount: 100,
      profiledAt: new Date().toISOString(),
      profileVersion: '1.0.0',
    };

    it('validates a correct schema', () => {
      const result = validateDatasetSchema(validSchema);
      expect(result.valid).toBe(true);
    });

    it('rejects invalid column type', () => {
      const result = validateDatasetSchema({
        ...validSchema,
        columns: [{ ...validSchema.columns[0], type: 'invalid' as any }],
      });
      expect(result.valid).toBe(false);
    });
  });

  describe('SummaryRequest', () => {
    it('validates a correct request', () => {
      const result = validateSummaryRequest({
        datasetId: 'test-001',
        options: { includeStatistics: true, maxLength: 1000 },
      });
      expect(result.valid).toBe(true);
    });

    it('requires datasetId', () => {
      const result = validateSummaryRequest({ options: {} });
      expect(result.valid).toBe(false);
    });
  });

  describe('SummaryResponse', () => {
    const validResponse = {
      datasetId: 'test-001',
      title: 'Test Summary',
      executiveSummary: 'This is a test summary.',
      keyVariables: ['temperature', 'pressure'],
      coverage: { temporal: '2020-2021', rowCount: 100 },
      findings: [{
        description: 'Temperature varies',
        evidence: 'min=300, max=2000',
        source: 'computed_statistics' as const,
      }],
      limitations: ['Limited sample size'],
      warnings: ['Data may be incomplete'],
      sources: [{ type: 'statistics' as const, reference: 'temperature column' }],
      generatedAt: new Date().toISOString(),
      catalogVersion: '1.0.0',
    };

    it('validates a correct response', () => {
      const result = validateSummaryResponse(validResponse);
      expect(result.valid).toBe(true);
    });

    it('rejects invalid finding source', () => {
      const result = validateSummaryResponse({
        ...validResponse,
        findings: [{ ...validResponse.findings[0], source: 'invalid' as any }],
      });
      expect(result.valid).toBe(false);
    });
  });

  describe('ChartPreviewRequest', () => {
    it('validates a bar chart request', () => {
      const result = validateChartPreviewRequest({
        datasetId: 'test-001',
        chartType: 'bar',
        xAxis: 'category',
        yAxis: 'value',
      });
      expect(result.valid).toBe(true);
    });

    it('validates a histogram request without yAxis', () => {
      const result = validateChartPreviewRequest({
        datasetId: 'test-001',
        chartType: 'histogram',
        xAxis: 'value',
      });
      expect(result.valid).toBe(true);
    });

    it('validates bar chart without yAxis (schema allows, app validates)', () => {
      // Schema doesn't enforce yAxis requirement for bar/line/scatter
      // Application-level validation handles this
      const result = validateChartPreviewRequest({
        datasetId: 'test-001',
        chartType: 'bar',
        xAxis: 'category',
      });
      expect(result.valid).toBe(true);
    });

    it('rejects invalid chartType', () => {
      const result = validateChartPreviewRequest({
        datasetId: 'test-001',
        chartType: 'pie',
        xAxis: 'category',
      });
      expect(result.valid).toBe(false);
    });
  });

  describe('ChartPreviewResponse', () => {
    const validResponse = {
      datasetId: 'test-001',
      chartType: 'line' as const,
      spec: { mark: 'line', encoding: { x: { field: 'time' }, y: { field: 'temp' } } },
      data: [{ time: 1, temp: 100 }, { time: 2, temp: 200 }],
      columns: {
        x: { name: 'time', type: 'numeric' as const, nullable: false },
        y: { name: 'temp', type: 'numeric' as const, nullable: false },
      },
      warnings: [],
      metadata: {
        rowCount: 100,
        filteredRowCount: 50,
        processingTimeMs: 10,
        memoryUsedBytes: 1024,
      },
    };

    it('validates a correct response', () => {
      const result = validateChartPreviewResponse(validResponse);
      expect(result.valid).toBe(true);
    });
  });

  describe('APIError', () => {
    const validError = {
      error: {
        code: 'NOT_FOUND',
        message: 'Dataset not found',
        requestId: 'req-123',
        timestamp: new Date().toISOString(),
      },
    };

    it('validates a correct error', () => {
      const result = validateAPIError(validError);
      expect(result.valid).toBe(true);
    });

    it('rejects invalid error code', () => {
      const result = validateAPIError({
        error: { ...validError.error, code: 'INVALID_CODE' },
      });
      expect(result.valid).toBe(false);
    });
  });
});