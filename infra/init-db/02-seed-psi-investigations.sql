-- ============================================================================
-- Enigma SAC - Seed Data: 26 NASA PSI Combustion Science Investigations
-- Source: NASA_PSI_Combustion_Science_26_Investigations-2.md
-- ============================================================================

-- Insert all 26 PSI investigations
-- Note: PSI-68, PSI-181, PSI-108 have metadata pending verification

INSERT INTO psi_investigations (
    psi_id, title, description, research_area, sub_research_area,
    scientific_focus, project_setting, record_type, doi, doi_url,
    psi_record_url, objectives, approach, sources, metadata_status,
    verified_at, tags
) VALUES
-- 1. PSI-20: ACME — Burning Rate Emulator (BRE)
(
    'PSI-20',
    'ACME — Burning Rate Emulator (BRE)',
    'Determine how ventilation, oxygen availability, and fuel supply affect burning rates in low-gravity environments, including near-extinction behavior relevant to fire safety.',
    'Combustion Science',
    'Flames of Gaseous Fuels',
    'Gaseous combustion; flame burning rates and spacecraft material flammability',
    'ISS microgravity experiment',
    'Investigation',
    '10.60555/vb93-3y72',
    'https://doi.org/10.60555/vb93-3y72',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-20',
    'Determine how ventilation, oxygen availability, and fuel supply affect burning rates in low-gravity environments, including near-extinction behavior relevant to fire safety.',
    'Use an ACME modular burner in the ISS Combustion Integrated Rack to establish controlled, low-buoyancy flames. Change the gas flow and oxidizer conditions and observe flame stability and fuel consumption.',
    ARRAY[
        'https://psi.nasa.gov/physci/repo/data/investigations/PSI-20',
        'https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv',
        'https://www.nasa.gov/physical-sciences-informatics-psi/psi-investigations-by-research-area/',
        'https://www.nasa.gov/humans-in-space/space-stations-quest-for-the-secrets-of-fire/'
    ],
    'verified',
    NOW(),
    ARRAY['acme', 'gaseous-fuels', 'burning-rate', 'fire-safety', 'microgravity', 'iss']
),

-- 2. PSI-21: ACME — Coflow Laminar Diffusion Flame (CLD Flame)
(
    'PSI-21',
    'ACME — Coflow Laminar Diffusion Flame (CLD Flame)',
    'Acquire benchmark measurements of nonpremixed diffusion flames across sooty and highly diluted conditions and improve models of soot production and flame structure.',
    'Combustion Science',
    'Flames of gaseous fuel',
    'Gas-phase diffusion flames; soot formation and oxidation',
    'ISS microgravity experiment',
    'Investigation',
    '10.60555/23e1-9950',
    'https://doi.org/10.60555/23e1-9950',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-21',
    'Acquire benchmark measurements of nonpremixed diffusion flames across sooty and highly diluted conditions and improve models of soot production and flame structure.',
    'Burn gaseous fuel in a coflow burner under carefully controlled fuel and oxidizer flows. Record flame shape, luminosity, and soot-related behavior under microgravity so predictions can be compared with measurements.',
    ARRAY[
        'https://psi.nasa.gov/physci/repo/data/investigations/PSI-21',
        'https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv',
        'https://science.nasa.gov/physical-sciences-informatics-psi/nasa-psi-research-opportunity/',
        'https://www.nasa.gov/humans-in-space/space-stations-quest-for-the-secrets-of-fire/'
    ],
    'verified',
    NOW(),
    ARRAY['acme', 'diffusion-flames', 'soot', 'gaseous-fuels', 'microgravity', 'iss']
),

-- 3. PSI-159: ACME — Cool Flames Investigation with Gases (CFI-G)
(
    'PSI-159',
    'ACME — Cool Flames Investigation with Gases (CFI-G)',
    'Observe stable low-temperature, nonpremixed cool flames of gaseous fuels and characterize chemical regimes that are obscured by buoyancy on Earth.',
    'Combustion Science',
    'Flames of Gaseous Fuels',
    'Low-temperature oxidation; gaseous cool flames',
    'ISS microgravity experiment',
    'Investigation',
    '10.60555/cyt1-kh64',
    'https://doi.org/10.60555/cyt1-kh64',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-159',
    'Observe stable low-temperature, nonpremixed cool flames of gaseous fuels and characterize chemical regimes that are obscured by buoyancy on Earth.',
    'Establish nonpremixed gaseous flames in the ACME combustion facility with gravity-driven flow suppressed. Vary reactant composition and operating conditions to study weak, low-temperature flame structures.',
    ARRAY[
        'https://psi.nasa.gov/physci/repo/data/investigations/PSI-159',
        'https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv',
        'https://www.nasa.gov/humans-in-space/space-stations-quest-for-the-secrets-of-fire/'
    ],
    'verified',
    NOW(),
    ARRAY['acme', 'cool-flames', 'gaseous-fuels', 'low-temperature-oxidation', 'microgravity', 'iss']
),

-- 4. PSI-10: ACME — Flame Design
(
    'PSI-10',
    'ACME — Flame Design',
    'Improve control over flame structure and soot production and study quasi-steady spherical diffusion flames, especially extinction driven by radiation.',
    'Combustion Science',
    'Flames of Gaseous Fuels',
    'Nonpremixed gaseous flames; soot inception and radiative extinction',
    'ISS microgravity experiment',
    'Investigation',
    '10.60555/w4zy-bt45',
    'https://doi.org/10.60555/w4zy-bt45',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-10',
    'Improve control over flame structure and soot production and study quasi-steady spherical diffusion flames, especially extinction driven by radiation.',
    'Produce gas diffusion flames using interchangeable ACME burner hardware, adjust reactant streams, and document flame geometry, stability, and radiation-related extinction in microgravity.',
    ARRAY[
        'https://psi.nasa.gov/physci/repo/data/investigations/PSI-10',
        'https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv',
        'https://www.nasa.gov/humans-in-space/space-stations-quest-for-the-secrets-of-fire/'
    ],
    'verified',
    NOW(),
    ARRAY['acme', 'flame-design', 'soot', 'radiative-extinction', 'spherical-flames', 'microgravity', 'iss']
),

-- 5. PSI-22: ACME — Electric-Field Effects on Laminar Diffusion Flames (E-FIELD Flames)
(
    'PSI-22',
    'ACME — Electric-Field Effects on Laminar Diffusion Flames (E-FIELD Flames)',
    'Assess the ability of applied electric fields to change diffusion-flame shape, transport, and emissions, including soot-related processes.',
    'Combustion Science',
    'Laminar Flames',
    'Gaseous combustion; electric-field flame control and emissions',
    'ISS microgravity experiment',
    'Investigation',
    '10.60555/se5a-8c73',
    'https://doi.org/10.60555/se5a-8c73',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-22',
    'Assess the ability of applied electric fields to change diffusion-flame shape, transport, and emissions, including soot-related processes.',
    'Apply controlled electric fields to nonpremixed laminar flames in the ISS combustion chamber; compare observed flame responses with experiments without the field.',
    ARRAY[
        'https://psi.nasa.gov/physci/repo/data/investigations/PSI-22',
        'https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv',
        'https://science.nasa.gov/physical-sciences-informatics-psi/nasa-psi-research-opportunity/',
        'https://www.nasa.gov/humans-in-space/space-stations-quest-for-the-secrets-of-fire/'
    ],
    'verified',
    NOW(),
    ARRAY['acme', 'electric-field', 'laminar-flames', 'soot', 'emissions', 'microgravity', 'iss']
),

-- 6. PSI-23: ACME — Structure and Response of Spherical Diffusion Flames (s-Flames)
(
    'PSI-23',
    'ACME — Structure and Response of Spherical Diffusion Flames (s-Flames)',
    'Investigate the structure, response, and extinction behavior of spherical gas diffusion flames without the strong distortion caused by buoyancy.',
    'Combustion Science',
    'Flames of gaseous fuels',
    'Spherical diffusion flames; flame stability and extinction',
    'ISS microgravity experiment',
    'Investigation',
    '10.60555/k57n-p030',
    'https://doi.org/10.60555/k57n-p030',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-23',
    'Investigate the structure, response, and extinction behavior of spherical gas diffusion flames without the strong distortion caused by buoyancy.',
    'Stabilize approximately spherical nonpremixed flames in the ACME chamber and systematically adjust fuel/oxidizer flow and mixture composition. Measure changes in size, response, and stability.',
    ARRAY[
        'https://psi.nasa.gov/physci/repo/data/investigations/PSI-23',
        'https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv',
        'https://science.nasa.gov/physical-sciences-informatics-psi/nasa-psi-research-opportunity/',
        'https://www.nasa.gov/humans-in-space/space-stations-quest-for-the-secrets-of-fire/'
    ],
    'verified',
    NOW(),
    ARRAY['acme', 'spherical-flames', 'diffusion-flames', 'extinction', 'stability', 'microgravity', 'iss']
),

-- 7. PSI-26: Burning and Suppression of Solids (BASS)
(
    'PSI-26',
    'Burning and Suppression of Solids (BASS)',
    'Determine how solid materials ignite, spread flames, and extinguish under low-speed forced ventilation in microgravity.',
    'Combustion Science',
    'Spacecraft Fire Safety',
    'Spacecraft fire safety; solid-fuel flame spread and extinction',
    'ISS microgravity experiment',
    'Investigation',
    '10.60555/58h4-dy80',
    'https://doi.org/10.60555/58h4-dy80',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-26',
    'Determine how solid materials ignite, spread flames, and extinguish under low-speed forced ventilation in microgravity.',
    'Burn different solid samples in the Microgravity Science Glovebox with controlled airflow. Examine flame growth and suppression under varied sample geometries and flow conditions.',
    ARRAY[
        'https://psi.nasa.gov/physci/repo/data/investigations/PSI-26',
        'https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv',
        'https://www.nasa.gov/physical-sciences-informatics-psi/psi-investigations-by-research-area/',
        'https://www.nasa.gov/glenn/glenn-expertise-space-exploration/physical-sciences-program/combustion-science/'
    ],
    'verified',
    NOW(),
    ARRAY['bass', 'solid-fuels', 'flame-spread', 'extinction', 'fire-safety', 'microgravity', 'iss', 'glovebox']
),

-- 8. PSI-25: Burning and Suppression of Solids — II (BASS-II)
(
    'PSI-25',
    'Burning and Suppression of Solids — II (BASS-II)',
    'Characterize ignition, flame growth, spread, and extinction limits of solid fuels in weak forced flow; compare these results with normal-gravity flammability screening and provide data for future fire-safety experiments.',
    'Combustion Science',
    'Spacecraft Fire Safety',
    'Spacecraft Fire Safety',
    'Microgravity Investigation; ISS',
    'Investigation',
    '10.60555/4qc4-de67',
    'https://doi.org/10.60555/4qc4-de67',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-25',
    'Characterize ignition, flame growth, spread, and extinction limits of solid fuels in weak forced flow; compare these results with normal-gravity flammability screening and provide data for future fire-safety experiments.',
    'Carry out crew-assisted burning tests in a small wind tunnel installed inside the ISS Microgravity Science Glovebox. Mount rods, sheets, films, and other geometries; vary airflow up to approximately 40 cm/s and reduce oxygen concentration by nitrogen dilution. Image and assess flame appearance and spread in concurrent and opposed flow.',
    ARRAY[
        'https://psi.nasa.gov/physci/repo/data/investigations/PSI-25',
        'https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv'
    ],
    'verified',
    NOW(),
    ARRAY['bass-ii', 'solid-fuels', 'flame-spread', 'extinction', 'fire-safety', 'microgravity', 'iss', 'glovebox']
),

-- 9. PSI-60: Computational and Experimental Analysis of SPICE Data Sets
(
    'PSI-60',
    'Computational and Experimental Analysis of SPICE Data Sets',
    'Quantify soot temperatures, soot volume fractions, and the impact of radiation and reaction-model assumptions on computed coflow diffusion flames.',
    'Combustion Science',
    'Gaseous',
    'Gaseous combustion; flame pyrometry and soot-formation models',
    'Ground Investigation; PSI data reanalysis',
    'Investigation',
    '10.60555/mzjm-yv57',
    'https://doi.org/10.60555/mzjm-yv57',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-60',
    'Quantify soot temperatures, soot volume fractions, and the impact of radiation and reaction-model assumptions on computed coflow diffusion flames.',
    'Decode Nikon NEF images from SPICE into color channels, use color-ratio pyrometry and calibrated luminosity to derive soot temperature and concentration fields. Implement coupled flow, species, and soot simulations including radiation reabsorption and sectional aggregate formation; compare Yale and ACME burner cases in normal and reduced gravity.',
    ARRAY[
        'https://psi.nasa.gov/physci/repo/data/investigations/PSI-60',
        'https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv'
    ],
    'verified',
    NOW(),
    ARRAY['spice', 'soot', 'pyrometry', 'computational', 'ground-investigation', 'data-reanalysis']
),

-- 10. PSI-62: Concurrent Flame Spread Modeling using Flamelet Generated Manifolds
(
    'PSI-62',
    'Concurrent Flame Spread Modeling using Flamelet Generated Manifolds in Microgravity with Comparison to BASS Experiments using Two-Color Tomography',
    'Develop and validate unsteady flamelet generated manifold (UFGM) models for concurrent flame spread in microgravity, using BASS data to improve predictions of material flammability limits.',
    'Combustion Science',
    'Spacecraft Fire Safety',
    'Spacecraft Fire Safety',
    'Ground Investigation',
    'Investigation',
    '10.60555/e9xp-ex83',
    'https://doi.org/10.60555/e9xp-ex83',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-62',
    'Develop and validate unsteady flamelet generated manifold (UFGM) models for concurrent flame spread in microgravity, using BASS data to improve predictions of material flammability limits.',
    'Couple fluid/solid combustion simulations with unsteady flamelet-generated chemistry models. Use geometries from BASS/BASS-II (sheets, spheres, PMMA rods, and wax cylinders) and apply two-color tomography to archived flame imagery to compare predicted geometry, soot, temperature, and spread rates.',
    ARRAY[
        'https://psi.nasa.gov/physci/repo/data/investigations/PSI-62',
        'https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv'
    ],
    'verified',
    NOW(),
    ARRAY['flame-spread', 'modeling', 'ufgm', 'bass', 'tomography', 'ground-investigation', 'fire-safety']
),

-- 11. PSI-39: Cool Flames Investigation (CFI)
(
    'PSI-39',
    'Cool Flames Investigation (CFI)',
    'Understand low-temperature fuel-oxidation chemistry and persistent cool-flame burning after conventional hot flames become extinguished.',
    'Combustion Science',
    'Droplets',
    'Liquid-droplet combustion; cool flames and low-temperature chemistry',
    'ISS microgravity experiment',
    'Investigation',
    '10.60555/m6pj-a914',
    'https://doi.org/10.60555/m6pj-a914',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-39',
    'Understand low-temperature fuel-oxidation chemistry and persistent cool-flame burning after conventional hot flames become extinguished.',
    'Ignite liquid fuel droplets using combustion hardware aboard the ISS; change fuel and ambient gas conditions and track droplet lifetime, burning behavior, and transitions between hot flames and cool flames.',
    ARRAY[
        'https://psi.nasa.gov/physci/repo/data/investigations/PSI-39',
        'https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv',
        'https://www.nasa.gov/physical-sciences-informatics-psi/psi-investigations-by-research-area/',
        'https://www.nasa.gov/glenn/glenn-expertise-space-exploration/physical-sciences-program/combustion-science/'
    ],
    'verified',
    NOW(),
    ARRAY['cfi', 'cool-flames', 'droplets', 'low-temperature-chemistry', 'liquid-fuels', 'microgravity', 'iss']
),

-- 12. PSI-47: Dust and Aerosol Measurement Feasibility Test (DAFT) / DAFT-2
(
    'PSI-47',
    'Dust and Aerosol Measurement Feasibility Test (DAFT) / DAFT-2',
    'Validate aerosol particle-counting devices in microgravity before the SAME flight investigation; assess whether particle instruments behave reliably in orbit.',
    'Combustion Science',
    'Spacecraft Fire Safety',
    'Spacecraft fire safety; aerosol particle measurement instrument qualification',
    'Microgravity Investigation; ISS',
    'Investigation',
    '10.60555/ztgj-d202',
    'https://doi.org/10.60555/ztgj-d202',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-47',
    'Validate aerosol particle-counting devices in microgravity before the SAME flight investigation; assess whether particle instruments behave reliably in orbit.',
    'Modify a TSI P-Trak counter for microgravity by adapting its isopropyl-alcohol condenser and removing its gravity-dependent mercury orientation switch. Generate Arizona Red Dust (ARD) aerosols with gaseous nitrogen in Mylar sample bags, test on orbit, and compare P-Trak counts with DustTrak reference measurements.',
    ARRAY[
        'https://psi.nasa.gov/physci/repo/data/investigations/PSI-47',
        'https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv'
    ],
    'verified',
    NOW(),
    ARRAY['daft', 'aerosols', 'particle-measurement', 'instrument-qualification', 'fire-safety', 'microgravity', 'iss']
),

-- 13. PSI-117: Effect of External Thermo-Convective Perturbation on Cool Flame Dynamics
(
    'PSI-117',
    'Effect of External Thermo-Convective Perturbation on Cool Flame Dynamics: A Multidimensional Multi-Physics CFD Analysis',
    'Determine how weak convection, external heating, and their interaction influence initiation, oscillation, and extinction of microgravity droplet cool flames.',
    'Combustion Science',
    'Droplet',
    'Droplet cool flames; computational fluid dynamics and thermal perturbations',
    'Ground Investigation; numerical modeling',
    'Investigation',
    '10.60555/gz0q-b577',
    'https://doi.org/10.60555/gz0q-b577',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-117',
    'Determine how weak convection, external heating, and their interaction influence initiation, oscillation, and extinction of microgravity droplet cool flames.',
    'Develop a three-dimensional OpenFOAM CFD model of n-alkane droplets with fluid dynamics, low-temperature chemistry, transport, and radiation. Validate with ISS FLEX data, then test droplet drift, imposed heat flux, and combined forcing over multiple droplet sizes and ambient conditions to map cool-flame stability.',
    ARRAY[
        'https://psi.nasa.gov/physci/repo/data/investigations/PSI-117',
        'https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv'
    ],
    'verified',
    NOW(),
    ARRAY['cool-flames', 'droplets', 'cfd', 'openfoam', 'thermal-perturbations', 'ground-investigation', 'modeling']
),

-- 14. PSI-69: Flame Extinguishment Experiment (FLEX)
(
    'PSI-69',
    'Flame Extinguishment Experiment (FLEX)',
    'Map flammability and extinction limits for liquid-fuel droplets, assess gaseous suppressants including CO2, helium, and SF6, and improve predictive models for flame extinction in reduced gravity.',
    'Combustion Science',
    'Spacecraft Fire Safety',
    'Spacecraft Fire Safety',
    'Microgravity Investigation; ISS',
    'Investigation',
    '10.60555/mbq8-0451',
    'https://doi.org/10.60555/mbq8-0451',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-69',
    'Map flammability and extinction limits for liquid-fuel droplets, assess gaseous suppressants including CO2, helium, and SF6, and improve predictive models for flame extinction in reduced gravity.',
    'Ignite relatively large isolated liquid droplets under microgravity. Vary pressure, oxygen fraction, and suppressant gas concentrations; image the droplets and flames to quantify burning and extinction and estimate the limiting oxygen index.',
    ARRAY[
        'https://psi.nasa.gov/physci/repo/data/investigations/PSI-69',
        'https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv'
    ],
    'verified',
    NOW(),
    ARRAY['flex', 'droplets', 'extinction', 'flammability', 'suppressants', 'liquid-fuels', 'fire-safety', 'microgravity', 'iss']
),

-- 15. PSI-68: Official investigation title not verified (Metadata pending verification)
(
    'PSI-68',
    'Investigation PSI-68 — Official title pending verification',
    'Metadata pending verification from official NASA PSI record.',
    'Combustion Science',
    NULL,
    NULL,
    NULL,
    'Investigation',
    NULL,
    NULL,
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-68',
    'Pending verification from the official NASA PSI record. No objectives have been invented.',
    'Pending verification from the official NASA PSI record. No experimental methodology has been invented.',
    ARRAY['https://psi.nasa.gov/physci/repo/data/investigations/PSI-68'],
    'pending',
    NULL,
    ARRAY['pending-verification', 'metadata-pending']
),

-- 16. PSI-142: Quantitative Studies of Cool Flame Transitions at Radiation/Stretch Extinction Using Counterflow Flames
(
    'PSI-142',
    'Quantitative Studies of Cool Flame Transitions at Radiation/Stretch Extinction Using Counterflow Flames',
    'Characterize how oxygen concentration, stretch and radiative heat transfer shift cool-flame stability and extinction boundaries.',
    'Combustion Science',
    'Spacecraft Fire Safety',
    'Low-temperature flame transition; extinction and oxygen effects',
    'Ground Investigation; modeling and controlled flame studies',
    'Investigation',
    '10.60555/80qf-vj95',
    'https://doi.org/10.60555/80qf-vj95',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-142',
    'Characterize how oxygen concentration, stretch and radiative heat transfer shift cool-flame stability and extinction boundaries.',
    'Use FLEX flight conditions as a benchmark and compare three simulation methods: spark-assisted propagation in n-heptane/air, one-dimensional dimethyl ether flame propagation with arc-length continuation, and elevated-pressure dimethyl ether/air cool-flame computations up to approximately 20 atm.',
    ARRAY[
        'https://psi.nasa.gov/physci/repo/data/investigations/PSI-142',
        'https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv'
    ],
    'verified',
    NOW(),
    ARRAY['cool-flames', 'extinction', 'counterflow', 'radiation', 'stretch', 'oxygen', 'ground-investigation', 'modeling']
),

-- 17. PSI-101: Smoke Aerosol Measurement Experiment — Reflight (SAME-R)
(
    'PSI-101',
    'Smoke Aerosol Measurement Experiment — Reflight (SAME-R)',
    'Measure the sizes of liquid smoke particles in low gravity and relate droplet distributions to smoke generation and transport; improve measurements that were compromised in the initial SAME flight.',
    'Combustion Science',
    'Spacecraft Fire Safety',
    'Spacecraft Fire Safety',
    'Microgravity Investigation; ISS',
    'Investigation',
    '10.60555/2np7-jv14',
    'https://doi.org/10.60555/2np7-jv14',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-101',
    'Measure the sizes of liquid smoke particles in low gravity and relate droplet distributions to smoke generation and transport; improve measurements that were compromised in the initial SAME flight.',
    'Reuse SAME orbital hardware but change the test materials and heating/flow conditions, including use of Pyrell fire-retardant foam. Replace one diagnostics assembly with the NASA Glenn M-pass instrument. Execute 66 orbital test points and subsequent ground tests to support particle-size data analysis.',
    ARRAY[
        'https://psi.nasa.gov/physci/repo/data/investigations/PSI-101',
        'https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv'
    ],
    'verified',
    NOW(),
    ARRAY['same-r', 'smoke', 'aerosols', 'particle-size', 'fire-safety', 'microgravity', 'iss', 'reflight']
),

-- 18. PSI-102: Smoke Aerosol Measurement Experiment (SAME)
(
    'PSI-102',
    'Smoke Aerosol Measurement Experiment (SAME)',
    'Characterize microgravity smoke aerosol sizes, morphology, and detector response to help improve spacecraft fire detection.',
    'Combustion Science',
    'Spacecraft Fire Safety',
    'Spacecraft fire safety; smoke-particle size and detector response',
    'ISS microgravity experiment',
    'Investigation',
    '10.60555/gd4k-8h62',
    'https://doi.org/10.60555/gd4k-8h62',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-102',
    'Characterize microgravity smoke aerosol sizes, morphology, and detector response to help improve spacecraft fire detection.',
    'Generate smoke from heated or smoldering test materials aboard the ISS. Measure particle distributions with aerosol sensors and collect samples or measurements to compare against ground-based detector behavior.',
    ARRAY[
        'https://psi.nasa.gov/physci/repo/data/investigations/PSI-102',
        'https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv',
        'https://www.nasa.gov/physical-sciences-informatics-psi/psi-investigations-by-research-area/',
        'https://www.nasa.gov/glenn/glenn-expertise-space-exploration/physical-sciences-program/combustion-science/'
    ],
    'verified',
    NOW(),
    ARRAY['same', 'smoke', 'aerosols', 'particle-size', 'detector-response', 'fire-safety', 'microgravity', 'iss']
),

-- 19. PSI-107: Smoke Point in Co-flow Experiment (SPICE)
(
    'PSI-107',
    'Smoke Point in Co-flow Experiment (SPICE)',
    'Identify smoke-point properties of nonbuoyant laminar jet diffusion flames, including the effect of burner diameter and coflow velocity on luminous flame length and smoke onset.',
    'Combustion Science',
    'Fire Safety',
    'Fire Safety',
    'Microgravity Investigation; ISS',
    'Investigation',
    '10.60555/9kbh-e962',
    'https://doi.org/10.60555/9kbh-e962',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-107',
    'Identify smoke-point properties of nonbuoyant laminar jet diffusion flames, including the effect of burner diameter and coflow velocity on luminous flame length and smoke onset.',
    'Study laminar coflow diffusion flames under microgravity and analogous ground conditions. Systematically change burner diameter and coflow velocity and analyze flame length and smoking behavior; NASA reports 526 flames studied.',
    ARRAY[
        'https://psi.nasa.gov/physci/repo/data/investigations/PSI-107',
        'https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv'
    ],
    'verified',
    NOW(),
    ARRAY['spice', 'smoke-point', 'diffusion-flames', 'coflow', 'soot', 'fire-safety', 'microgravity', 'iss']
),

-- 20. PSI-99: Spacecraft Fire Safety Experiment — II (SAFFIRE-II)
(
    'PSI-99',
    'Spacecraft Fire Safety Experiment — II (SAFFIRE-II)',
    'Test the low-gravity flammability behavior of different spacecraft-relevant materials and determine how oxygen and material type affect ignition and flame spread.',
    'Combustion Science',
    'Surface Combustion',
    'Spacecraft fire safety; material flammability limits',
    'Microgravity experiment; uncrewed Cygnus spacecraft',
    'Investigation',
    '10.60555/2chp-m469',
    'https://doi.org/10.60555/2chp-m469',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-99',
    'Test the low-gravity flammability behavior of different spacecraft-relevant materials and determine how oxygen and material type affect ignition and flame spread.',
    'Conduct remotely initiated burning tests of several smaller material samples in a Cygnus vehicle after separation from the ISS; measure flame development and environmental conditions with onboard sensors.',
    ARRAY[
        'https://psi.nasa.gov/physci/repo/data/investigations/PSI-99',
        'https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv',
        'https://www.nasa.gov/physical-sciences-informatics-psi/psi-investigations-by-research-area/',
        'https://www.nasa.gov/centers-and-facilities/glenn/flame-burns-out-on-nasas-long-running-spacecraft-fire-experiment/'
    ],
    'verified',
    NOW(),
    ARRAY['saffire-ii', 'fire-safety', 'material-flammability', 'cygnus', 'uncrewed', 'microgravity', 'flame-spread']
),

-- 21. PSI-100: Spacecraft Fire Safety Experiment — III (SAFFIRE-III)
(
    'PSI-100',
    'Spacecraft Fire Safety Experiment — III (SAFFIRE-III)',
    'Extend the large-scale fabric-burning study from SAFFIRE-I by examining flame behavior at a different ventilation condition.',
    'Combustion Science',
    'Spacecraft Fire Safety',
    'Spacecraft fire safety; flow-dependent flame spread',
    'Microgravity experiment; uncrewed Cygnus spacecraft',
    'Investigation',
    '10.60555/040q-4h36',
    'https://doi.org/10.60555/040q-4h36',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-100',
    'Extend the large-scale fabric-burning study from SAFFIRE-I by examining flame behavior at a different ventilation condition.',
    'Burn a large fabric panel in a controlled airflow duct after Cygnus departs the ISS. Compare flame spread, heat release, and growth with SAFFIRE-I conditions.',
    ARRAY[
        'https://psi.nasa.gov/physci/repo/data/investigations/PSI-100',
        'https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv',
        'https://www.nasa.gov/physical-sciences-informatics-psi/psi-investigations-by-research-area/',
        'https://www.nasa.gov/centers-and-facilities/glenn/flame-burns-out-on-nasas-long-running-spacecraft-fire-experiment/'
    ],
    'verified',
    NOW(),
    ARRAY['saffire-iii', 'fire-safety', 'fabric-burning', 'cygnus', 'uncrewed', 'microgravity', 'flame-spread', 'ventilation']
),

-- 22. PSI-98: Spacecraft Fire Safety Experiment — I (SAFFIRE-I)
(
    'PSI-98',
    'Spacecraft Fire Safety Experiment — I (SAFFIRE-I)',
    'Measure growth and propagation of a large microgravity fire and compare low-gravity flammability limits with normal-gravity material screening tests.',
    'Combustion Science',
    'Spacecraft Fire, Smoke Distribution',
    'Spacecraft Fire, Smoke Distribution',
    'Microgravity Investigation; uncrewed Cygnus spacecraft',
    'Investigation',
    '10.60555/0t15-1z43',
    'https://doi.org/10.60555/0t15-1z43',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-98',
    'Measure growth and propagation of a large microgravity fire and compare low-gravity flammability limits with normal-gravity material screening tests.',
    'After Cygnus departed the ISS, ignite an approximately 0.94 m × 0.4 m cotton–fiberglass (SIBAL) panel inside a forced-flow duct, with air speed around 20 cm/s. Use two cameras plus thermal, radiative, pressure, oxygen, carbon-dioxide, and airflow sensors to observe the burn.',
    ARRAY[
        'https://psi.nasa.gov/physci/repo/data/investigations/PSI-98',
        'https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv'
    ],
    'verified',
    NOW(),
    ARRAY['saffire-i', 'fire-safety', 'large-scale', 'cygnus', 'uncrewed', 'microgravity', 'flame-spread', 'smoke-distribution']
),

-- 23. PSI-106: Structure and Liftoff in Combustion Experiment (SLICE)
(
    'PSI-106',
    'Structure and Liftoff in Combustion Experiment (SLICE)',
    'Understand stability, lift-off, and visible structure of gas jet diffusion flames without strong buoyancy effects, with an emphasis on computationally tractable configurations.',
    'Combustion Science',
    NULL,
    'Laminar diffusion flames; flame structure and liftoff',
    'ISS microgravity experiment',
    'Investigation',
    '10.60555/pm12-rg61',
    'https://doi.org/10.60555/pm12-rg61',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-106',
    'Understand stability, lift-off, and visible structure of gas jet diffusion flames without strong buoyancy effects, with an emphasis on computationally tractable configurations.',
    'Produce gas-fueled laminar coflow diffusion flames in microgravity and vary burner/flow conditions. Record flame shape and lift-off behavior for model comparisons.',
    ARRAY[
        'https://psi.nasa.gov/physci/repo/data/investigations/PSI-106',
        'https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv',
        'https://www.nasa.gov/physical-sciences-informatics-psi/psi-investigations-by-research-area/',
        'https://www.nasa.gov/glenn/glenn-expertise-space-exploration/physical-sciences-program/combustion-science/'
    ],
    'verified',
    NOW(),
    ARRAY['slice', 'lift-off', 'diffusion-flames', 'flame-structure', 'gas-jet', 'microgravity', 'iss']
),

-- 24. PSI-181: Official investigation title not verified (Metadata pending verification)
(
    'PSI-181',
    'Investigation PSI-181 — Official title pending verification',
    'Metadata pending verification from official NASA PSI record.',
    'Combustion Science',
    NULL,
    NULL,
    NULL,
    'Investigation',
    NULL,
    NULL,
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-181',
    'Pending verification from the official NASA PSI record. No objectives have been invented.',
    'Pending verification from the official NASA PSI record. No experimental methodology has been invented.',
    ARRAY['https://psi.nasa.gov/physci/repo/data/investigations/PSI-181'],
    'pending',
    NULL,
    ARRAY['pending-verification', 'metadata-pending']
),

-- 25. PSI-108: Official investigation title not verified (Metadata pending verification)
(
    'PSI-108',
    'Investigation PSI-108 — Official title pending verification',
    'Metadata pending verification from official NASA PSI record.',
    'Combustion Science',
    NULL,
    NULL,
    NULL,
    'Investigation',
    NULL,
    NULL,
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-108',
    'Pending verification from the official NASA PSI record. No objectives have been invented.',
    'Pending verification from the official NASA PSI record. No experimental methodology has been invented.',
    ARRAY['https://psi.nasa.gov/physci/repo/data/investigations/PSI-108'],
    'pending',
    NULL,
    ARRAY['pending-verification', 'metadata-pending']
),

-- 26. PSI-115: Utilization of SAME Data for Advanced Modeling and Simulation of Smoke Generation in Micro-Gravity
(
    'PSI-115',
    'Utilization of SAME Data for Advanced Modeling and Simulation of Smoke Generation in Micro-Gravity',
    'Use SAME-derived smoke-generation conditions to explain particle growth, settling, thermophoresis, and transport differences between Earth gravity and microgravity.',
    'Combustion Science',
    'Smoke Aerosol, Combustion Simulation',
    'Smoke aerosol dynamics and transport; numerical simulations',
    'Ground Investigation; archived data reanalysis',
    'Investigation',
    '10.60555/q0v5-1v28',
    'https://doi.org/10.60555/q0v5-1v28',
    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-115',
    'Use SAME-derived smoke-generation conditions to explain particle growth, settling, thermophoresis, and transport differences between Earth gravity and microgravity.',
    'Model dibutyl phthalate (DBP) smoke aerosols originating from a heated sample using direct numerical simulation with a Navier–Stokes nodal formulation. Compare two low-speed crossflow cases under buoyant and nonbuoyant conditions; examine how wake geometry and flow affect particle accumulation and size distributions.',
    ARRAY[
        'https://psi.nasa.gov/physci/repo/data/investigations/PSI-115',
        'https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv'
    ],
    'verified',
    NOW(),
    ARRAY['same', 'smoke', 'aerosols', 'modeling', 'simulation', 'dns', 'navier-stokes', 'ground-investigation', 'data-reanalysis']
)
ON CONFLICT (psi_id) DO UPDATE SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    sub_research_area = EXCLUDED.sub_research_area,
    scientific_focus = EXCLUDED.scientific_focus,
    project_setting = EXCLUDED.project_setting,
    doi = EXCLUDED.doi,
    doi_url = EXCLUDED.doi_url,
    objectives = EXCLUDED.objectives,
    approach = EXCLUDED.approach,
    sources = EXCLUDED.sources,
    metadata_status = EXCLUDED.metadata_status,
    verified_at = EXCLUDED.verified_at,
    tags = EXCLUDED.tags,
    updated_at = NOW();

-- Verify all 26 investigations were inserted
DO $$
DECLARE
    count INTEGER;
BEGIN
    SELECT COUNT(*) INTO count FROM psi_investigations;
    RAISE NOTICE 'Total PSI investigations in catalog: %', count;
    ASSERT count = 26, 'Expected 26 investigations, got ' || count;
END $$;