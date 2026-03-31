# Antoine Equation Parameters

## Equation Form

log10(P_sat) = A - B / (C + T)

Where:
- P_sat = vapor pressure in mmHg
- T = temperature in degrees Celsius
- A, B, C = Antoine coefficients (compound-specific)

## Common Compounds

| Compound | A | B | C | Valid Range (°C) |
|----------|-------|---------|--------|------------------|
| Benzene | 6.90565 | 1211.033 | 220.790 | 8–80 |
| Toluene | 6.95464 | 1344.800 | 219.482 | 6–137 |
| Ethanol | 8.04494 | 1554.300 | 222.650 | -2–100 |
| Methanol | 8.08097 | 1582.271 | 239.726 | 15–84 |
| Acetone | 7.02447 | 1161.000 | 224.000 | -13–55 |
| Water | 8.07131 | 1730.630 | 233.426 | 1–100 |
| Hexane | 6.87776 | 1171.530 | 224.366 | -25–92 |
| Heptane | 6.89385 | 1264.370 | 216.640 | -2–124 |
| Octane | 6.91868 | 1351.990 | 209.150 | 19–152 |
| Propane | 6.82107 | 803.810 | 247.040 | -108–-2 |
| n-Butane | 6.80896 | 935.860 | 238.730 | -73–19 |
| Ethane | 6.80266 | 656.400 | 256.000 | -142–-44 |
| Chloroform | 6.95465 | 1170.966 | 226.232 | -10–60 |
| Diethyl ether | 6.92032 | 1064.066 | 228.799 | -60–20 |

## Unit Conversion

- To convert P_sat from mmHg to kPa: multiply by 0.133322
- To convert P_sat from mmHg to atm: divide by 760
- To convert P_sat from mmHg to bar: multiply by 0.00133322

## Notes

- Antoine parameters are empirical fits valid only within the stated temperature range
- Extrapolation outside the valid range can give large errors
- Different sources may use different forms of the equation (ln vs log10, K vs °C, Pa vs mmHg) — always check which form your parameters correspond to
- For high-accuracy work, use the NIST Chemistry WebBook as the primary reference
