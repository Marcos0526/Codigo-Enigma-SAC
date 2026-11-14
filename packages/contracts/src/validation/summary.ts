import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import summaryRequestSchema from '../schemas/summary.json';
import summaryResponseSchema from '../schemas/summary-response.json';
import type { SummaryRequest, SummaryResponse } from '../types';

const ajv = new Ajv({ strict: true, allErrors: true });
addFormats(ajv);

const validateSummaryRequestFn = ajv.compile<SummaryRequest>(summaryRequestSchema);
const validateSummaryResponseFn = ajv.compile<SummaryResponse>(summaryResponseSchema);

export function validateSummaryRequest(data: unknown): { valid: boolean; errors?: string } {
  const valid = validateSummaryRequestFn(data);
  return {
    valid,
    errors: validateSummaryRequestFn.errors?.map((e: any) => `${e.instancePath} ${e.message}`).join('; ')
  };
}

export function validateSummaryResponse(data: unknown): { valid: boolean; errors?: string } {
  const valid = validateSummaryResponseFn(data);
  return {
    valid,
    errors: validateSummaryResponseFn.errors?.map((e: any) => `${e.instancePath} ${e.message}`).join('; ')
  };
}

export { summaryRequestSchema, summaryResponseSchema };