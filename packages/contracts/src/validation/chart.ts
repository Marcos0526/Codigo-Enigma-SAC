import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import chartPreviewRequestSchema from '../schemas/chart-preview.json';
import chartPreviewResponseSchema from '../schemas/chart-preview-response.json';
import type { ChartPreviewRequest, ChartPreviewResponse } from '../types';

const ajv = new Ajv({ strict: true, allErrors: true });
addFormats(ajv);

const validateChartPreviewRequestFn = ajv.compile<ChartPreviewRequest>(chartPreviewRequestSchema);
const validateChartPreviewResponseFn = ajv.compile<ChartPreviewResponse>(chartPreviewResponseSchema);

export function validateChartPreviewRequest(data: unknown): { valid: boolean; errors?: string } {
  const valid = validateChartPreviewRequestFn(data);
  return {
    valid,
    errors: validateChartPreviewRequestFn.errors?.map((e: any) => `${e.instancePath} ${e.message}`).join('; ')
  };
}

export function validateChartPreviewResponse(data: unknown): { valid: boolean; errors?: string } {
  const valid = validateChartPreviewResponseFn(data);
  return {
    valid,
    errors: validateChartPreviewResponseFn.errors?.map((e: any) => `${e.instancePath} ${e.message}`).join('; ')
  };
}

export { chartPreviewRequestSchema, chartPreviewResponseSchema };