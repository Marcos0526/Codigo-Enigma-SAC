import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import datasetSchema from '../schemas/dataset.json';
import datasetSchemaSchema from '../schemas/dataset-schema.json';
import datasetPreviewSchema from '../schemas/dataset-preview.json';
import type { Dataset, DatasetSchema, DatasetPreviewResponse } from '../types';

const ajv = new Ajv({ strict: true, allErrors: true });
addFormats(ajv);

const validateDatasetFn = ajv.compile<Dataset>(datasetSchema);
const validateDatasetSchemaFn = ajv.compile<DatasetSchema>(datasetSchemaSchema);
const validateDatasetPreviewFn = ajv.compile<DatasetPreviewResponse>(datasetPreviewSchema);

export function validateDataset(data: unknown): { valid: boolean; errors?: string } {
  const valid = validateDatasetFn(data);
  return {
    valid,
    errors: validateDatasetFn.errors?.map((e: any) => `${e.instancePath} ${e.message}`).join('; ')
  };
}

export function validateDatasetSchema(data: unknown): { valid: boolean; errors?: string } {
  const valid = validateDatasetSchemaFn(data);
  return {
    valid,
    errors: validateDatasetSchemaFn.errors?.map((e: any) => `${e.instancePath} ${e.message}`).join('; ')
  };
}

export function validateDatasetPreview(data: unknown): { valid: boolean; errors?: string } {
  const valid = validateDatasetPreviewFn(data);
  return {
    valid,
    errors: validateDatasetPreviewFn.errors?.map((e: any) => `${e.instancePath} ${e.message}`).join('; ')
  };
}

export { datasetSchema, datasetSchemaSchema, datasetPreviewSchema };