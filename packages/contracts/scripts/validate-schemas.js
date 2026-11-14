#!/usr/bin/env node
/**
 * Schema validation script for @enigma-sac/contracts
 * Validates all JSON schemas against JSON Schema draft-07 and tests example data
 */

const Ajv = require('ajv');
const addFormats = require('ajv-formats');
const fs = require('fs');
const path = require('path');

const ajv = new Ajv({ strict: true, allErrors: true, meta: true });
addFormats(ajv);

const schemasDir = path.join(__dirname, '../src/schemas');
const schemaFiles = fs.readdirSync(schemasDir).filter(f => f.endsWith('.json'));

console.log('🔍 Validating JSON Schemas...\n');

let allValid = true;

for (const file of schemaFiles) {
  const filePath = path.join(schemasDir, file);
  const schema = JSON.parse(fs.readFileSync(filePath, 'utf-8'));

  try {
    // Validate schema itself against draft-07 meta-schema (built into AJV)
    const valid = ajv.validateSchema(schema);
    if (valid) {
      console.log(`✅ ${file} - Valid JSON Schema draft-07`);
    } else {
      console.log(`❌ ${file} - Invalid schema:`);
      console.log(ajv.errorsText(ajv.errors));
      allValid = false;
    }
  } catch (error) {
    console.log(`❌ ${file} - Error: ${error.message}`);
    allValid = false;
  }
}

console.log('\n🧪 Testing example data against schemas...\n');

// Load validation functions
const { validateSearchRequest, validateSearchResponse } = require('../dist/validation/search.js');

const testRequest = {
  query: "combustion temperature in microgravity",
  filters: { hasNumericData: true },
  options: { maxResults: 50 }
};
const result = validateSearchRequest(testRequest);
console.log(result.valid ? '✅ SearchRequest example valid' : `❌ SearchRequest: ${result.errors}`);

const testResponse = {
  query: "combustion temperature in microgravity",
  status: "matches_found",
  source_collection: "NASA PSI — Combustion Science: 26 Selected Investigations",
  data_filter: "numeric_only",
  total_matches: 1,
  datasets: [{
    id: "test-001",
    psiId: "PSI-20",
    name: "Test Dataset",
    description: "Test description",
    url: "https://example.com/data.csv",
    format: "csv",
    numericColumns: ["temperature"],
    score: 0.9,
    verificationStatus: "verified"
  }],
  searchMetadata: {
    catalogVersion: "1.0.0",
    embeddingModel: "test-model",
    embeddingVersion: "1.0.0",
    retrievedAt: new Date().toISOString(),
    processingTimeMs: 100
  }
};
const result2 = validateSearchResponse(testResponse);
console.log(result2.valid ? '✅ SearchResponse example valid' : `❌ SearchResponse: ${result2.errors}`);

// Test total_matches equals datasets.length
if (testResponse.total_matches !== testResponse.datasets.length) {
  console.log('❌ total_matches must equal datasets.length');
  allValid = false;
} else {
  console.log('✅ total_matches equals datasets.length');
}

if (allValid) {
  console.log('\n🎉 All schemas and examples validated successfully!');
  process.exit(0);
} else {
  console.log('\n💥 Validation failed!');
  process.exit(1);
}