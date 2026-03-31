# Critical Properties and Equation of State Parameters

## Critical Properties of Common Compounds

| Compound | T_c (K) | P_c (atm) | P_c (bar) | V_c (cm³/mol) | ω (acentric) |
|----------|---------|-----------|-----------|----------------|--------------|
| Argon | 150.86 | 48.00 | 48.63 | 74.6 | 0.001 |
| Nitrogen | 126.20 | 33.50 | 33.94 | 89.8 | 0.039 |
| Oxygen | 154.58 | 49.77 | 50.43 | 73.4 | 0.022 |
| CO₂ | 304.25 | 72.90 | 73.83 | 94.0 | 0.225 |
| Water | 647.14 | 217.75 | 220.64 | 55.9 | 0.344 |
| Methane | 190.56 | 45.39 | 45.99 | 98.6 | 0.012 |
| Ethane | 305.32 | 48.08 | 48.72 | 145.5 | 0.099 |
| Propane | 369.83 | 41.94 | 42.48 | 200.0 | 0.152 |
| n-Butane | 425.12 | 37.46 | 37.96 | 255.0 | 0.200 |
| Benzene | 562.05 | 48.31 | 48.98 | 259.0 | 0.210 |
| Toluene | 591.75 | 40.60 | 41.06 | 316.0 | 0.262 |
| Hexane | 507.60 | 29.70 | 30.25 | 368.0 | 0.301 |
| Acetone | 508.20 | 46.40 | 47.01 | 209.0 | 0.307 |
| Ethanol | 513.92 | 60.68 | 61.48 | 167.0 | 0.645 |
| Methanol | 512.64 | 79.78 | 80.84 | 118.0 | 0.564 |
| Ammonia | 405.40 | 111.30 | 112.80 | 72.5 | 0.253 |
| Hydrogen | 33.19 | 12.93 | 13.13 | 65.1 | -0.216 |

## Van der Waals Parameters

The van der Waals equation: P = RT/(V_m - b) - a/V_m²

Parameters can be calculated from critical properties:
- a = 27 R² T_c² / (64 P_c)
- b = R T_c / (8 P_c)

| Compound | a (bar·dm⁶·mol⁻²) | b (dm³·mol⁻¹) |
|----------|-------------------|----------------|
| Argon | 1.355 | 0.03201 |
| Nitrogen | 1.370 | 0.03870 |
| CO₂ | 3.658 | 0.04286 |
| Water | 5.537 | 0.03049 |
| Methane | 2.303 | 0.04310 |
| Benzene | 18.82 | 0.1193 |
| Toluene | 24.86 | 0.1497 |
| Ethanol | 12.56 | 0.08710 |

## Gas Constant in Various Units

| Value | Units |
|-------|-------|
| 8.31446 | J mol⁻¹ K⁻¹ |
| 8.31446 | Pa m³ mol⁻¹ K⁻¹ |
| 0.083145 | dm³ bar mol⁻¹ K⁻¹ |
| 0.08206 | L atm mol⁻¹ K⁻¹ |
| 82.06 | cm³ atm mol⁻¹ K⁻¹ |
| 1.987 | cal mol⁻¹ K⁻¹ |
| 62.36 | L mmHg mol⁻¹ K⁻¹ |

## Equation of State Selection Guide

| Conditions | Recommended EOS | Why |
|------------|----------------|-----|
| Low pressure, high temperature | Ideal gas (PV = nRT) | Intermolecular forces negligible |
| Moderate pressure, above T_c | Van der Waals or virial | Simple corrections sufficient |
| Near critical point | SRK or Peng-Robinson | Cubic EOS designed for this regime |
| High pressure, condensable | Peng-Robinson | Best general-purpose cubic EOS |
| Polar compounds | SRK with Mathias-Copeman alpha | Acentric factor correction for polarity |
| Associating compounds (water, alcohols) | CPA or SAFT | Handles hydrogen bonding |

## Notes

- Van der Waals is the simplest real-gas correction but performs poorly near the critical point
- The Pitzer acentric factor (ω) measures deviation from noble gas behavior — higher ω means more complex molecular interactions
- Always verify which units your equation expects for R, a, b, P, V, T — unit mismatches are the most common source of errors
