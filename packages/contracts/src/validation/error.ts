import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import apiErrorSchema from '../schemas/api-error.json';
import type { APIErrorResponse } from '../types';

const ajv = new Ajv({ strict: true, allErrors: true });
addFormats(ajv);

const validateAPIErrorFn = ajv.compile<APIErrorResponse>(apiErrorSchema);

export function validateAPIError(data: unknown): { valid: boolean; errors?: string } {
  const valid = validateAPIErrorFn(data);
  return {
    valid,
    errors: validateAPIErrorFn.errors?.map((e: any) => `${e.instancePath} ${e.message}`).join('; ')
  };
}

export { apiErrorSchema };