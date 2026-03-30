# Flash Distillation Fundamentals

## When to use
- Separating a liquid mixture into vapor and liquid products
- Feed enters a drum where pressure/temperature causes partial vaporization
- Quick, single-stage separation (not multi-stage like distillation columns)

## Key equations

### Material balance
- Overall: F = L + V
- Component: F·z = L·x + V·y
- Rearranged: z = x·(1 - V/F) + y·(V/F)

### VLE relationship (Raoult's law for ideal systems)
- y_i = (P_sat_i / P) · x_i
- Where P_sat_i is from Antoine equation: log10(P_sat) = A - B/(C+T)

### Rachford-Rice equation
- Σ [z_i · (K_i - 1)] / [1 + (V/F)·(K_i - 1)] = 0
- Where K_i = y_i/x_i = P_sat_i/P (for Raoult's law)

## Solution strategy for T-unknown flash (given V/F)
1. Guess T
2. Calculate K_i values from Antoine equation at guessed T
3. Solve Rachford-Rice for compositions
4. Check if Σx_i = 1 and Σy_i = 1
5. Adjust T and repeat until converged

## Common pitfalls
- Antoine equation units vary by source (Pa vs mmHg, ln vs log10, K vs °C)
- Always verify material balance closure after solving
- Benzene/toluene is nearly ideal — Raoult's law is appropriate
- At high pressures or with polar species, need activity coefficients (NRTL, UNIFAC)
