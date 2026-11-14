-- ============================================================================
-- Enigma SAC - Seed Data: Sample Datasets for Testing
-- These are illustrative sample datasets for development and testing.
-- Real datasets should be ingested through the catalog ingestion pipeline.
-- ============================================================================

-- Insert sample datasets for verified investigations
-- Note: These use placeholder URLs. Real ingestion should discover actual data URLs.

INSERT INTO datasets (
    dataset_id, psi_id, name, description, url, url_type, format,
    numeric_columns, source, license, access_policy,
    coverage_temporal, coverage_geographic,
    catalog_version, embedding_model, embedding_version,
    verification_status, verified_at, tags,
    provenance_investigation_url, provenance_dataset_url, provenance_retrieved_at
) VALUES
-- PSI-20 BRE sample dataset
(
    'psi-20-bre-temperature-csv',
    'PSI-20',
    'BRE Flame Temperature Measurements',
    'Temperature measurements from Burning Rate Emulator (BRE) experiments on ISS. Includes time-series temperature data for various flow conditions and fuel types.',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-20/data/bre_temperature.csv',
    'direct_download',
    'csv',
    ARRAY['time_s', 'temperature_k', 'pressure_kpa', 'flow_rate_slpm', 'oxygen_percent'],
    'NASA Physical Sciences Informatics',
    'Public Domain',
    'public',
    '2019-2021',
    'ISS Microgravity',
    '1.0.0',
    'sentence-transformers/all-MiniLM-L6-v2',
    '1.0.0',
    'verified',
    NOW(),
    ARRAY['temperature', 'time-series', 'gaseous-fuels', 'bre', 'acme'],
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-20',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-20/data/bre_temperature.csv',
    NOW()
),

-- PSI-21 CLD Flame sample dataset
(
    'psi-21-cld-soot-csv',
    'PSI-21',
    'CLD Flame Soot Volume Fraction Data',
    'Soot volume fraction and temperature measurements from Coflow Laminar Diffusion Flame experiments. Includes radial profiles at multiple axial positions.',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-21/data/cld_soot_profiles.csv',
    'direct_download',
    'csv',
    ARRAY['axial_position_mm', 'radial_position_mm', 'soot_volume_fraction_ppm', 'temperature_k', 'fuel_flow_rate'],
    'NASA Physical Sciences Informatics',
    'Public Domain',
    'public',
    '2019-2021',
    'ISS Microgravity',
    '1.0.0',
    'sentence-transformers/all-MiniLM-L6-v2',
    '1.0.0',
    'verified',
    NOW(),
    ARRAY['soot', 'diffusion-flames', 'radial-profiles', 'cld-flame', 'acme'],
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-21',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-21/data/cld_soot_profiles.csv',
    NOW()
),

-- PSI-69 FLEX sample dataset
(
    'psi-69-flex-droplet-extinction-csv',
    'PSI-69',
    'FLEX Droplet Extinction Measurements',
    'Droplet diameter and extinction data from Flame Extinguishment Experiment. Includes various fuel types, oxygen concentrations, and suppressant gases.',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-69/data/flex_droplet_extinction.csv',
    'direct_download',
    'csv',
    ARRAY['time_s', 'diameter_mm', 'initial_diameter_mm', 'oxygen_percent', 'suppressant_type', 'pressure_kpa', 'extinction_time_s'],
    'NASA Physical Sciences Informatics',
    'Public Domain',
    'public',
    '2010-2017',
    'ISS Microgravity',
    '1.0.0',
    'sentence-transformers/all-MiniLM-L6-v2',
    '1.0.0',
    'verified',
    NOW(),
    ARRAY['droplets', 'extinction', 'suppressants', 'flex', 'liquid-fuels'],
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-69',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-69/data/flex_droplet_extinction.csv',
    NOW()
),

-- PSI-39 CFI sample dataset
(
    'psi-39-cfi-cool-flame-csv',
    'PSI-39',
    'CFI Cool Flame Droplet Temperature Data',
    'Temperature measurements showing cool flame behavior in liquid fuel droplets. Captures transition from hot flame to cool flame combustion.',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-39/data/cfi_cool_flame_temperature.csv',
    'direct_download',
    'csv',
    ARRAY['time_s', 'droplet_diameter_mm', 'surface_temperature_k', 'ambient_temperature_k', 'fuel_type', 'pressure_kpa'],
    'NASA Physical Sciences Informatics',
    'Public Domain',
    'public',
    '2010-2017',
    'ISS Microgravity',
    '1.0.0',
    'sentence-transformers/all-MiniLM-L6-v2',
    '1.0.0',
    'verified',
    NOW(),
    ARRAY['cool-flames', 'droplets', 'temperature', 'low-temperature-chemistry', 'cfi'],
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-39',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-39/data/cfi_cool_flame_temperature.csv',
    NOW()
),

-- PSI-107 SPICE sample dataset
(
    'psi-107-spice-smoke-point-csv',
    'PSI-107',
    'SPICE Smoke Point and Flame Length Data',
    'Smoke point measurements for laminar jet diffusion flames. 526 flame conditions with burner diameter, coflow velocity, and smoke onset data.',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-107/data/spice_smoke_point.csv',
    'direct_download',
    'csv',
    ARRAY['burner_diameter_mm', 'coflow_velocity_cms', 'fuel_flow_rate_slpm', 'flame_length_mm', 'smoke_point_flag', 'fuel_type'],
    'NASA Physical Sciences Informatics',
    'Public Domain',
    'public',
    '2015-2017',
    'ISS Microgravity',
    '1.0.0',
    'sentence-transformers/all-MiniLM-L6-v2',
    '1.0.0',
    'verified',
    NOW(),
    ARRAY['smoke-point', 'diffusion-flames', 'coflow', 'spice', 'soot-onset'],
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-107',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-107/data/spice_smoke_point.csv',
    NOW()
),

-- PSI-26 BASS sample dataset
(
    'psi-26-bass-solid-flame-spread-csv',
    'PSI-26',
    'BASS Solid Fuel Flame Spread Rates',
    'Flame spread rate measurements for various solid materials in microgravity. Includes PMMA, cotton, and other spacecraft materials.',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-26/data/bass_flame_spread.csv',
    'direct_download',
    'csv',
    ARRAY['material', 'thickness_mm', 'width_mm', 'flow_velocity_cms', 'oxygen_percent', 'spread_rate_mm_s', 'flame_length_mm'],
    'NASA Physical Sciences Informatics',
    'Public Domain',
    'public',
    '2011-2017',
    'ISS Microgravity',
    '1.0.0',
    'sentence-transformers/all-MiniLM-L6-v2',
    '1.0.0',
    'verified',
    NOW(),
    ARRAY['solid-fuels', 'flame-spread', 'bass', 'material-flammability', 'microgravity'],
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-26',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-26/data/bass_flame_spread.csv',
    NOW()
),

-- PSI-102 SAME sample dataset
(
    'psi-102-same-smoke-aerosol-csv',
    'PSI-102',
    'SAME Smoke Aerosol Size Distribution Data',
    'Particle size distribution measurements from Smoke Aerosol Measurement Experiment. Includes count median diameter and geometric standard deviation.',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-102/data/same_aerosol_sizing.csv',
    'direct_download',
    'csv',
    ARRAY['test_number', 'material', 'heating_mode', 'count_median_diameter_nm', 'geometric_std_dev', 'number_concentration_cm3', 'mass_concentration_mg_m3'],
    'NASA Physical Sciences Informatics',
    'Public Domain',
    'public',
    '2011-2017',
    'ISS Microgravity',
    '1.0.0',
    'sentence-transformers/all-MiniLM-L6-v2',
    '1.0.0',
    'verified',
    NOW(),
    ARRAY['smoke', 'aerosols', 'particle-size', 'same', 'detector-response'],
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-102',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-102/data/same_aerosol_sizing.csv',
    NOW()
),

-- PSI-98 SAFFIRE-I sample dataset
(
    'psi-98-saffire-i-fabric-burn-csv',
    'PSI-98',
    'SAFFIRE-I Large Fabric Burn Sensor Data',
    'Temperature, pressure, oxygen, and CO2 sensor data from the SAFFIRE-I large fabric burn experiment on Cygnus spacecraft.',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-98/data/saffire_i_sensor_data.csv',
    'direct_download',
    'csv',
    ARRAY['time_s', 'temperature_c', 'pressure_kpa', 'oxygen_percent', 'co2_percent', 'co_ppm', 'flow_velocity_cms', 'radiative_heat_flux_kw_m2'],
    'NASA Physical Sciences Informatics',
    'Public Domain',
    'public',
    '2016',
    'Cygnus Spacecraft Microgravity',
    '1.0.0',
    'sentence-transformers/all-MiniLM-L6-v2',
    '1.0.0',
    'verified',
    NOW(),
    ARRAY['saffire', 'fabric-burn', 'large-scale', 'cygnus', 'sensor-data', 'fire-safety'],
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-98',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-98/data/saffire_i_sensor_data.csv',
    NOW()
),

-- PSI-159 CFI-G sample dataset
(
    'psi-159-cfig-gaseous-cool-flame-csv',
    'PSI-159',
    'CFI-G Gaseous Cool Flame Temperature Data',
    'Temperature and species concentration data from Cool Flames Investigation with Gases. Shows stable low-temperature oxidation regimes.',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-159/data/cfig_gaseous_cool_flame.csv',
    'direct_download',
    'csv',
    ARRAY['time_s', 'temperature_k', 'fuel_mole_fraction', 'oxygen_mole_fraction', 'pressure_kpa', 'ch2o_concentration_ppm', 'co_concentration_ppm'],
    'NASA Physical Sciences Informatics',
    'Public Domain',
    'public',
    '2021-2022',
    'ISS Microgravity',
    '1.0.0',
    'sentence-transformers/all-MiniLM-L6-v2',
    '1.0.0',
    'verified',
    NOW(),
    ARRAY['cool-flames', 'gaseous-fuels', 'low-temperature-oxidation', 'cfig', 'acme'],
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-159',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-159/data/cfig_gaseous_cool_flame.csv',
    NOW()
),

-- PSI-10 SLICE sample dataset (using PSI-106 SLICE investigation)
(
    'psi-106-slice-liftoff-csv',
    'PSI-106',
    'SLICE Flame Liftoff and Structure Data',
    'Flame liftoff height and structure measurements for gas jet diffusion flames in microgravity. Various burner diameters and flow rates.',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-106/data/slice_liftoff_data.csv',
    'direct_download',
    'csv',
    ARRAY['burner_diameter_mm', 'fuel_flow_rate_slpm', 'coflow_velocity_cms', 'liftoff_height_mm', 'flame_length_mm', 'fuel_type', 'liftoff_velocity_cms'],
    'NASA Physical Sciences Informatics',
    'Public Domain',
    'public',
    '2015-2017',
    'ISS Microgravity',
    '1.0.0',
    'sentence-transformers/all-MiniLM-L6-v2',
    '1.0.0',
    'verified',
    NOW(),
    ARRAY['liftoff', 'diffusion-flames', 'gas-jet', 'slice', 'flame-structure'],
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-106',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-106/data/slice_liftoff_data.csv',
    NOW()
)
ON CONFLICT (dataset_id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    url = EXCLUDED.url,
    url_type = EXCLUDED.url_type,
    format = EXCLUDED.format,
    numeric_columns = EXCLUDED.numeric_columns,
    source = EXCLUDED.source,
    license = EXCLUDED.license,
    access_policy = EXCLUDED.access_policy,
    coverage_temporal = EXCLUDED.coverage_temporal,
    coverage_geographic = EXCLUDED.coverage_geographic,
    catalog_version = EXCLUDED.catalog_version,
    embedding_model = EXCLUDED.embedding_model,
    embedding_version = EXCLUDED.embedding_version,
    verification_status = EXCLUDED.verification_status,
    verified_at = EXCLUDED.verified_at,
    tags = EXCLUDED.tags,
    provenance_investigation_url = EXCLUDED.provenance_investigation_url,
    provenance_dataset_url = EXCLUDED.provenance_dataset_url,
    provenance_retrieved_at = EXCLUDED.provenance_retrieved_at,
    updated_at = NOW();

-- Verify sample datasets were inserted
DO $$
DECLARE
    count INTEGER;
BEGIN
    SELECT COUNT(*) INTO count FROM datasets;
    RAISE NOTICE 'Total sample datasets in catalog: %', count;
END $$;