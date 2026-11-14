import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import searchRequestSchema from '../schemas/search.json';
import searchResponseSchema from '../schemas/search-response.json';
import type { SearchRequest, SearchResponse } from '../types';

const ajv = new Ajv({ strict: true, allErrors: true });
addFormats(ajv);

const validateSearchRequestFn = ajv.compile<SearchRequest>(searchRequestSchema);
const validateSearchResponseFn = ajv.compile<SearchResponse>(searchResponseSchema);

export function validateSearchRequest(data: unknown): { valid: boolean; errors?: string } {
  const valid = validateSearchRequestFn(data);
  return {
    valid,
    errors: validateSearchRequestFn.errors?.map((e: any) => `${e.instancePath} ${e.message}`).join('; ')
  };
}

export function validateSearchResponse(data: unknown): { valid: boolean; errors?: string } {
  const valid = validateSearchResponseFn(data);
  return {
    valid,
    errors: validateSearchResponseFn.errors?.map((e: any) => `${e.instancePath} ${e.message}`).join('; ')
  };
}

export { searchRequestSchema, searchResponseSchema };