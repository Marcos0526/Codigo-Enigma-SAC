#!/usr/bin/env python3
"""
Generate synthetic CSV data files for NASA PSI Combustion Science investigations.

This script creates realistic synthetic datasets matching the schemas defined
in the seed data (03-seed-sample-datasets.sql) for testing and development.
"""

import os
import numpy as np
import pandas as pd
from pathlib import Path

# Set seed for reproducibility
np.random.seed(42)

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "synthetic"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_bre_temperature_data(n_rows: int = 5000) -> pd.DataFrame:
    """Generate BRE Flame Temperature Measurements (PSI-20)."""
    # Time series data for different experimental runs
    n_runs = 50
    run_ids = np.repeat(np.arange(1, n_runs + 1), n_rows // n_runs)
    
    # Ensure exact length
    if len(run_ids) < n_rows:
        run_ids = np.concatenate([run_ids, np.full(n_rows - len(run_ids), n_runs)])
    elif len(run_ids) > n_rows:
        run_ids = run_ids[:n_rows]
    
    # Time within each run (0-300 seconds)
    time_s = np.concatenate([np.linspace(0, 300, n_rows // n_runs) for _ in range(n_runs)])[:n_rows]
    
    # Temperature with realistic combustion dynamics
    base_temp = 1200 + np.random.normal(0, 50, n_rows)  # Base flame temp ~1200K
    oscillation = 50 * np.sin(2 * np.pi * time_s / 30)  # Oscillation from flow instabilities
    noise = np.random.normal(0, 15, n_rows)
    temperature_k = base_temp + oscillation + noise
    
    # Pressure (near constant with small variations)
    pressure_kpa = 101.3 + np.random.normal(0, 2, n_rows)
    
    # Flow rate variations
    flow_rate_slpm = np.random.choice([1.0, 2.0, 3.0, 4.0, 5.0], n_rows, p=[0.1, 0.2, 0.4, 0.2, 0.1])
    flow_rate_slpm += np.random.normal(0, 0.05, n_rows)
    
    # Oxygen percentage
    oxygen_percent = np.random.choice([21.0, 18.0, 15.0, 12.0, 9.0], n_rows, p=[0.3, 0.25, 0.2, 0.15, 0.1])
    oxygen_percent += np.random.normal(0, 0.5, n_rows)
    
    # Fuel type
    fuel_types = ['methane', 'ethylene', 'propane', 'hydrogen']
    fuel_type = np.random.choice(fuel_types, n_rows, p=[0.4, 0.3, 0.2, 0.1])
    
    return pd.DataFrame({
        'run_id': run_ids,
        'time_s': np.round(time_s, 2),
        'temperature_k': np.round(temperature_k, 1),
        'pressure_kpa': np.round(pressure_kpa, 2),
        'flow_rate_slpm': np.round(flow_rate_slpm, 3),
        'oxygen_percent': np.round(oxygen_percent, 1),
        'fuel_type': fuel_type
    })


def generate_cld_soot_data(n_rows: int = 3000) -> pd.DataFrame:
    """Generate CLD Flame Soot Volume Fraction Data (PSI-21)."""
    # Radial profiles at multiple axial positions
    axial_positions = np.array([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])  # mm
    n_axial = len(axial_positions)
    n_radial_per_axial = n_rows // n_axial
    
    axial_position_mm = np.repeat(axial_positions, n_radial_per_axial)
    if len(axial_position_mm) < n_rows:
        axial_position_mm = np.concatenate([axial_position_mm, np.full(n_rows - len(axial_position_mm), axial_positions[-1])])
    elif len(axial_position_mm) > n_rows:
        axial_position_mm = axial_position_mm[:n_rows]
    
    # Radial positions (0 to flame radius)
    max_radius = 15  # mm
    radial_position_mm = np.tile(np.linspace(0, max_radius, n_radial_per_axial), n_axial)[:n_rows]
    
    # Soot volume fraction - peaks off-center for diffusion flames
    centerline_soot = 2.0 * np.exp(-axial_position_mm / 150)  # Decreases with height
    radial_profile = np.exp(-(radial_position_mm / 3)**2) * (1 + 0.5 * radial_position_mm / max_radius)
    soot_volume_fraction_ppm = centerline_soot * radial_profile + np.random.exponential(0.1, n_rows)
    
    # Temperature - highest near centerline
    temp_base = 1800 * np.exp(-axial_position_mm / 200)
    temp_radial = np.exp(-(radial_position_mm / 4)**2)
    temperature_k = temp_base * temp_radial + np.random.normal(0, 50, n_rows)
    temperature_k = np.maximum(temperature_k, 300)  # Minimum temperature
    
    # Fuel flow rate
    fuel_flow_rate = np.random.choice([0.5, 1.0, 1.5, 2.0], n_rows, p=[0.1, 0.3, 0.4, 0.2])
    fuel_flow_rate += np.random.normal(0, 0.02, n_rows)
    
    return pd.DataFrame({
        'axial_position_mm': np.round(axial_position_mm, 1),
        'radial_position_mm': np.round(radial_position_mm, 2),
        'soot_volume_fraction_ppm': np.round(soot_volume_fraction_ppm, 3),
        'temperature_k': np.round(temperature_k, 1),
        'fuel_flow_rate': np.round(fuel_flow_rate, 3)
    })


def generate_flex_droplet_extinction_data(n_rows: int = 4000) -> pd.DataFrame:
    """Generate FLEX Droplet Extinction Measurements (PSI-69)."""
    # Different fuels
    fuels = ['heptane', 'methanol', 'ethanol', 'decane', 'hexadecane']
    n_fuels = len(fuels)
    
    # Oxygen concentrations
    oxygen_levels = [21, 19, 17, 15, 13, 11, 9]
    
    # Suppressants
    suppressants = ['none', 'CO2', 'He', 'N2', 'SF6']
    
    data = []
    for fuel in fuels:
        for o2 in oxygen_levels:
            for supp in suppressants:
                # Number of droplets per condition
                n_droplets = n_rows // (n_fuels * len(oxygen_levels) * len(suppressants))
                
                for _ in range(n_droplets):
                    initial_diameter = np.random.uniform(1.5, 4.0)  # mm
                    pressure_kpa = np.random.choice([100, 150, 200, 300], p=[0.4, 0.3, 0.2, 0.1])
                    
                    # Diameter follows d^2 law: d^2 = d0^2 - K*t
                    K = 0.05 * (o2 / 21) * (pressure_kpa / 100)  # Burning rate constant
                    if supp != 'none':
                        K *= 0.5  # Suppressant reduces burning rate
                    
                    extinction_time = (initial_diameter**2) / K
                    extinction_time = min(extinction_time, 30)  # Cap at 30s
                    
                    # Time series points
                    n_points = np.random.randint(10, 50)
                    for t in np.linspace(0, extinction_time, n_points):
                        diameter = np.sqrt(max(0, initial_diameter**2 - K * t))
                        data.append({
                            'fuel_type': fuel,
                            'initial_diameter_mm': round(initial_diameter, 3),
                            'oxygen_percent': o2,
                            'suppressant_type': supp,
                            'pressure_kpa': pressure_kpa,
                            'time_s': round(t, 2),
                            'diameter_mm': round(diameter, 3),
                            'extinction_time_s': round(extinction_time, 2)
                        })
    
    df = pd.DataFrame(data)
    if len(df) > n_rows:
        df = df.sample(n=n_rows, random_state=42)
    return df


def generate_cfi_cool_flame_data(n_rows: int = 3500) -> pd.DataFrame:
    """Generate CFI Cool Flame Droplet Temperature Data (PSI-39)."""
    fuels = ['n-heptane', 'n-decane', 'n-dodecane', 'PRF50', 'PRF80']
    n_fuels = len(fuels)
    
    data = []
    for fuel in fuels:
        n_per_fuel = n_rows // n_fuels
        for _ in range(n_per_fuel):
            initial_diameter = np.random.uniform(2.0, 5.0)
            pressure_kpa = np.random.choice([100, 200, 300, 400], p=[0.25, 0.35, 0.25, 0.15])
            ambient_temp = np.random.uniform(300, 500)
            
            # Hot flame phase then cool flame
            hot_flame_duration = np.random.uniform(5, 20)
            total_duration = hot_flame_duration + np.random.uniform(50, 200)
            
            n_points = np.random.randint(20, 80)
            for t in np.linspace(0, total_duration, n_points):
                if t < hot_flame_duration:
                    # Hot flame phase
                    surface_temp = np.random.uniform(1800, 2200)
                else:
                    # Cool flame phase - oscillatory
                    cool_time = t - hot_flame_duration
                    base_cool = 600 + 200 * np.exp(-cool_time / 50)
                    oscillation = 100 * np.sin(2 * np.pi * cool_time / 20)
                    surface_temp = base_cool + oscillation + np.random.normal(0, 20)
                    surface_temp = max(surface_temp, ambient_temp)
                
                droplet_diameter = initial_diameter * (1 - t / total_duration)**0.5
                
                data.append({
                    'fuel_type': fuel,
                    'time_s': round(t, 2),
                    'droplet_diameter_mm': round(droplet_diameter, 3),
                    'surface_temperature_k': round(surface_temp, 1),
                    'ambient_temperature_k': round(ambient_temp, 1),
                    'pressure_kpa': pressure_kpa
                })
    
    df = pd.DataFrame(data)
    if len(df) > n_rows:
        df = df.sample(n=n_rows, random_state=42)
    return df


def generate_spice_smoke_point_data(n_rows: int = 2000) -> pd.DataFrame:
    """Generate SPICE Smoke Point and Flame Length Data (PSI-107)."""
    # 526 flame conditions per NASA report
    burner_diameters = [2, 4, 6, 8, 10, 12]  # mm
    fuels = ['ethylene', 'propane', 'methane', 'hydrogen']
    coflow_velocities = np.linspace(10, 100, 20)  # cm/s
    
    data = []
    for bd in burner_diameters:
        for fuel in fuels:
            for cv in coflow_velocities:
                # Multiple fuel flow rates per condition
                n_flow_rates = 3
                for _ in range(n_flow_rates):
                    fuel_flow = np.random.uniform(0.5, 5.0)
                    
                    # Flame length correlates with fuel flow, inverse with coflow
                    flame_length = 50 * (fuel_flow / 2) * (50 / cv)**0.5 * (bd / 6)**0.3
                    flame_length += np.random.normal(0, flame_length * 0.1)
                    
                    # Smoke point - higher fuel flow and larger burner increase soot
                    smoke_tendency = fuel_flow * (bd / 6) * (1 / (cv / 50)**0.3)
                    smoke_point_flag = 1 if smoke_tendency > np.random.uniform(2, 4) else 0
                    
                    data.append({
                        'burner_diameter_mm': bd,
                        'coflow_velocity_cms': round(cv, 1),
                        'fuel_flow_rate_slpm': round(fuel_flow, 2),
                        'flame_length_mm': round(max(flame_length, 5), 1),
                        'smoke_point_flag': smoke_point_flag,
                        'fuel_type': fuel
                    })
    
    df = pd.DataFrame(data)
    if len(df) > n_rows:
        df = df.sample(n=n_rows, random_state=42)
    return df


def generate_bass_flame_spread_data(n_rows: int = 2500) -> pd.DataFrame:
    """Generate BASS Solid Fuel Flame Spread Rates (PSI-26)."""
    materials = ['PMMA', 'cotton', 'paper', 'filter_paper', 'polyethylene', 'sibal']
    thicknesses = [0.5, 1.0, 2.0, 3.0, 5.0]  # mm
    widths = [10, 20, 30, 50, 100]  # mm
    flow_velocities = [5, 10, 15, 20, 25, 30, 35, 40]  # cm/s
    oxygen_levels = [15, 17, 19, 21, 23, 25, 28, 30]
    
    # Material properties affect spread rate
    material_props = {
        'PMMA': {'base_spread': 2.5, 'thickness_exp': -0.3},
        'cotton': {'base_spread': 1.8, 'thickness_exp': -0.2},
        'paper': {'base_spread': 3.0, 'thickness_exp': -0.4},
        'filter_paper': {'base_spread': 2.2, 'thickness_exp': -0.3},
        'polyethylene': {'base_spread': 2.0, 'thickness_exp': -0.25},
        'sibal': {'base_spread': 1.5, 'thickness_exp': -0.15},
    }
    
    data = []
    for mat in materials:
        props = material_props[mat]
        for thick in thicknesses:
            for wid in widths:
                for fv in flow_velocities:
                    for o2 in oxygen_levels:
                        n_reps = 2
                        for _ in range(n_reps):
                            # Spread rate model
                            spread_rate = props['base_spread'] * (thick / 1.0)**props['thickness_exp']
                            spread_rate *= (fv / 20)**0.5 * (o2 / 21)**1.5
                            spread_rate *= (wid / 20)**0.1
                            spread_rate += np.random.normal(0, spread_rate * 0.15)
                            spread_rate = max(spread_rate, 0.1)
                            
                            # Flame length correlates with spread rate and oxygen
                            flame_length = 50 * (spread_rate / 2)**0.7 * (o2 / 21)**0.5
                            flame_length += np.random.normal(0, flame_length * 0.1)
                            flame_length = max(flame_length, 5)
                            
                            data.append({
                                'material': mat,
                                'thickness_mm': thick,
                                'width_mm': wid,
                                'flow_velocity_cms': fv,
                                'oxygen_percent': o2,
                                'spread_rate_mm_s': round(spread_rate, 2),
                                'flame_length_mm': round(flame_length, 1)
                            })
    
    df = pd.DataFrame(data)
    if len(df) > n_rows:
        df = df.sample(n=n_rows, random_state=42)
    return df


def generate_same_aerosol_data(n_rows: int = 2000) -> pd.DataFrame:
    """Generate SAME Smoke Aerosol Size Distribution Data (PSI-102)."""
    materials = ['kapton', 'teflon', 'silicone', 'pyrell', 'wire_insulation', 'circuit_board']
    heating_modes = ['smoldering', 'flaming', 'overheating']
    
    data = []
    for mat in materials:
        for mode in heating_modes:
            n_tests = n_rows // (len(materials) * len(heating_modes))
            for test_num in range(1, n_tests + 1):
                # Log-normal distribution parameters
                if mode == 'flaming':
                    cmd = np.random.uniform(100, 300)  # nm
                    gsd = np.random.uniform(1.5, 2.0)
                elif mode == 'smoldering':
                    cmd = np.random.uniform(300, 800)
                    gsd = np.random.uniform(1.8, 2.5)
                else:
                    cmd = np.random.uniform(50, 200)
                    gsd = np.random.uniform(1.3, 1.8)
                
                number_conc = np.random.lognormal(8, 1)  # cm^-3
                mass_conc = number_conc * (cmd**3) * gsd * 1e-15  # mg/m^3
                
                data.append({
                    'test_number': test_num,
                    'material': mat,
                    'heating_mode': mode,
                    'count_median_diameter_nm': round(cmd, 1),
                    'geometric_std_dev': round(gsd, 2),
                    'number_concentration_cm3': round(number_conc, 1),
                    'mass_concentration_mg_m3': round(mass_conc, 2)
                })
    
    df = pd.DataFrame(data)
    if len(df) > n_rows:
        df = df.sample(n=n_rows, random_state=42)
    return df


def generate_saffire_sensor_data(n_rows: int = 5000) -> pd.DataFrame:
    """Generate SAFFIRE-I Large Fabric Burn Sensor Data (PSI-98)."""
    # Time series from large fabric burn
    total_time = 600  # seconds
    time_s = np.linspace(0, total_time, n_rows)
    
    # Pre-ignition baseline
    pre_ignition = time_s < 60
    
    # Temperature: rises sharply at ignition, then decays
    temp_profile = np.where(
        pre_ignition,
        25 + np.random.normal(0, 1, n_rows),
        25 + 800 * (1 - np.exp(-(time_s - 60) / 30)) * np.exp(-(time_s - 60) / 200) + np.random.normal(0, 20, n_rows)
    )
    
    # Pressure: slight increase during burn
    pressure_base = 101.3
    pressure_kpa = pressure_base + np.where(
        pre_ignition,
        np.random.normal(0, 0.1, n_rows),
        2 * (1 - np.exp(-(time_s - 60) / 60)) * np.exp(-(time_s - 60) / 300) + np.random.normal(0, 0.2, n_rows)
    )
    
    # Oxygen: drops during combustion
    o2_base = 21.0
    oxygen_percent = o2_base - np.where(
        pre_ignition,
        np.random.normal(0, 0.05, n_rows),
        8 * (1 - np.exp(-(time_s - 60) / 40)) * np.exp(-(time_s - 60) / 250) + np.random.normal(0, 0.3, n_rows)
    )
    oxygen_percent = np.maximum(oxygen_percent, 10)
    
    # CO2: rises during combustion
    co2_base = 0.04
    co2_percent = co2_base + np.where(
        pre_ignition,
        np.random.normal(0, 0.01, n_rows),
        4 * (1 - np.exp(-(time_s - 60) / 50)) * np.exp(-(time_s - 60) / 200) + np.random.normal(0, 0.1, n_rows)
    )
    
    # CO: peaks early in combustion
    co_ppm = np.where(
        pre_ignition,
        np.random.normal(0, 1, n_rows),
        500 * np.exp(-(time_s - 60) / 30) * (1 - np.exp(-(time_s - 60) / 10)) + np.random.normal(0, 20, n_rows)
    )
    co_ppm = np.maximum(co_ppm, 0)
    
    # Flow velocity (forced flow)
    flow_velocity_cms = 20 + np.random.normal(0, 1, n_rows)
    
    # Radiative heat flux
    rad_flux = np.where(
        pre_ignition,
        np.random.normal(0, 0.1, n_rows),
        50 * (1 - np.exp(-(time_s - 60) / 20)) * np.exp(-(time_s - 60) / 150) + np.random.normal(0, 2, n_rows)
    )
    rad_flux = np.maximum(rad_flux, 0)
    
    return pd.DataFrame({
        'time_s': np.round(time_s, 1),
        'temperature_c': np.round(temp_profile, 1),
        'pressure_kpa': np.round(pressure_kpa, 2),
        'oxygen_percent': np.round(oxygen_percent, 2),
        'co2_percent': np.round(co2_percent, 3),
        'co_ppm': np.round(co_ppm, 1),
        'flow_velocity_cms': np.round(flow_velocity_cms, 1),
        'radiative_heat_flux_kw_m2': np.round(rad_flux, 1)
    })


def generate_cfig_cool_flame_data(n_rows: int = 3000) -> pd.DataFrame:
    """Generate CFI-G Gaseous Cool Flame Temperature Data (PSI-159)."""
    # Gaseous cool flames - different from droplet cool flames
    fuel_fractions = np.linspace(0.05, 0.3, 10)
    oxygen_fractions = np.linspace(0.1, 0.3, 8)
    pressures = [100, 200, 300, 400, 500]  # kPa
    
    data = []
    for fuel_frac in fuel_fractions:
        for oxy_frac in oxygen_fractions:
            for press in pressures:
                n_cond = n_rows // (len(fuel_fractions) * len(oxygen_fractions) * len(pressures))
                for _ in range(n_cond):
                    # Time evolution of cool flame
                    duration = np.random.uniform(50, 300)
                    n_points = np.random.randint(15, 40)
                    
                    for t in np.linspace(0, duration, n_points):
                        # Cool flame temperature oscillation
                        base_temp = 600 + 200 * fuel_frac / 0.15 * oxy_frac / 0.2
                        oscillation = 150 * np.sin(2 * np.pi * t / 15) * np.exp(-t / 100)
                        temp_noise = np.random.normal(0, 15)
                        temperature_k = base_temp + oscillation + temp_noise
                        temperature_k = max(temperature_k, 400)
                        
                        # Species concentrations
                        ch2o = 50 * fuel_frac * np.exp(-t / 80) * (1 + 0.5 * np.sin(2 * np.pi * t / 20))
                        co = 200 * fuel_frac * (1 - np.exp(-t / 50)) * np.exp(-t / 200)
                        
                        data.append({
                            'time_s': round(t, 2),
                            'temperature_k': round(temperature_k, 1),
                            'fuel_mole_fraction': round(fuel_frac, 3),
                            'oxygen_mole_fraction': round(oxy_frac, 3),
                            'pressure_kpa': press,
                            'ch2o_concentration_ppm': round(max(ch2o, 0), 1),
                            'co_concentration_ppm': round(max(co, 0), 1)
                        })
    
    df = pd.DataFrame(data)
    if len(df) > n_rows:
        df = df.sample(n=n_rows, random_state=42)
    return df


def generate_slice_liftoff_data(n_rows: int = 2000) -> pd.DataFrame:
    """Generate SLICE Flame Liftoff and Structure Data (PSI-106)."""
    burner_diameters = [2, 4, 6, 8, 10]  # mm
    fuels = ['methane', 'ethylene', 'hydrogen', 'propane']
    coflow_velocities = np.linspace(10, 100, 10)  # cm/s
    
    data = []
    for bd in burner_diameters:
        for fuel in fuels:
            for cv in coflow_velocities:
                n_flow_rates = 4
                for _ in range(n_flow_rates):
                    fuel_flow = np.random.uniform(0.5, 8.0)
                    
                    # Liftoff height correlates with fuel velocity and coflow
                    fuel_vel = fuel_flow / (np.pi * (bd/2)**2) * 1000  # approximate
                    liftoff_height = 10 * (fuel_vel / 50)**1.5 * (50 / cv)**0.5
                    liftoff_height += np.random.normal(0, liftoff_height * 0.2)
                    liftoff_height = max(liftoff_height, 1)
                    
                    # Liftoff velocity
                    liftoff_vel = fuel_vel * 0.8 + np.random.normal(0, fuel_vel * 0.1)
                    
                    # Flame length
                    flame_length = 30 * (fuel_flow / 4)**0.7 * (50 / cv)**0.3
                    flame_length += np.random.normal(0, flame_length * 0.15)
                    flame_length = max(flame_length, liftoff_height + 5)
                    
                    data.append({
                        'burner_diameter_mm': bd,
                        'fuel_flow_rate_slpm': round(fuel_flow, 2),
                        'coflow_velocity_cms': round(cv, 1),
                        'liftoff_height_mm': round(liftoff_height, 1),
                        'flame_length_mm': round(flame_length, 1),
                        'fuel_type': fuel,
                        'liftoff_velocity_cms': round(liftoff_vel, 1)
                    })
    
    df = pd.DataFrame(data)
    if len(df) > n_rows:
        df = df.sample(n=n_rows, random_state=42)
    return df


def main():
    """Generate all synthetic datasets."""
    print(f"Generating synthetic data in {OUTPUT_DIR}")
    
    datasets = [
        ("psi-20-bre-temperature-csv", generate_bre_temperature_data, 5000),
        ("psi-21-cld-soot-csv", generate_cld_soot_data, 3000),
        ("psi-69-flex-droplet-extinction-csv", generate_flex_droplet_extinction_data, 4000),
        ("psi-39-cfi-cool-flame-csv", generate_cfi_cool_flame_data, 3500),
        ("psi-107-spice-smoke-point-csv", generate_spice_smoke_point_data, 2000),
        ("psi-26-bass-solid-flame-spread-csv", generate_bass_flame_spread_data, 2500),
        ("psi-102-same-smoke-aerosol-csv", generate_same_aerosol_data, 2000),
        ("psi-98-saffire-i-fabric-burn-csv", generate_saffire_sensor_data, 5000),
        ("psi-159-cfig-gaseous-cool-flame-csv", generate_cfig_cool_flame_data, 3000),
        ("psi-106-slice-liftoff-csv", generate_slice_liftoff_data, 2000),
    ]
    
    for dataset_id, generator, n_rows in datasets:
        print(f"  Generating {dataset_id} ({n_rows} rows)...")
        df = generator(n_rows)
        output_path = OUTPUT_DIR / f"{dataset_id}.csv"
        df.to_csv(output_path, index=False)
        print(f"    Saved to {output_path} ({len(df)} rows, {len(df.columns)} columns)")
    
    print("\nAll synthetic datasets generated!")
    
    # Print summary
    print("\nDataset summary:")
    for dataset_id, _, _ in datasets:
        path = OUTPUT_DIR / f"{dataset_id}.csv"
        df = pd.read_csv(path)
        print(f"  {dataset_id}: {len(df)} rows x {len(df.columns)} cols")
        print(f"    Columns: {list(df.columns)}")
        print(f"    Numeric columns: {df.select_dtypes(include=[np.number]).columns.tolist()}")


if __name__ == "__main__":
    main()