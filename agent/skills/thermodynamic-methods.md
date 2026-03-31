# Thermodynamic Methods and When to Use Them

## Vapor-Liquid Equilibrium (VLE)

### Raoult's Law (Ideal Solutions)

P_i = x_i · P_i_sat(T)

**When to use:** Binary or multicomponent mixtures of chemically similar, nonpolar compounds at low to moderate pressures. Classic examples: benzene/toluene, hexane/heptane, acetone/chloroform.

**When NOT to use:** Polar mixtures, associating compounds (alcohols + water), high pressures, or systems with strong positive/negative deviations from ideality.

### Modified Raoult's Law (Non-Ideal Solutions)

P_i = x_i · γ_i · P_i_sat(T)

Where γ_i is the activity coefficient from a model like NRTL, Wilson, or UNIQUAC.

**When to use:** Non-ideal liquid mixtures where Raoult's law gives poor results. Required for azeotropic systems.

### Henry's Law (Dilute Solutions)

P_i = x_i · H_i(T)

Where H_i is the Henry's law constant.

**When to use:** Dissolved gases at low concentration (e.g., CO₂ in water, O₂ in blood).

## Flash Calculations

### Problem Types

| Given | Unknown | Method |
|-------|---------|--------|
| T, P, z_i | V/F, x_i, y_i | Isothermal flash — solve Rachford-Rice |
| V/F, P, z_i | T, x_i, y_i | Adiabatic flash — iterate on T |
| V/F = 0, P, z_i | T (bubble point), y_i | Bubble point temperature |
| V/F = 0, T, z_i | P (bubble point), y_i | Bubble point pressure |
| V/F = 1, P, z_i | T (dew point), x_i | Dew point temperature |
| V/F = 1, T, z_i | P (dew point), x_i | Dew point pressure |

### Rachford-Rice Equation

Σ [ z_i · (K_i - 1) / (1 + ψ·(K_i - 1)) ] = 0

Where:
- z_i = feed mole fraction of component i
- K_i = equilibrium ratio = y_i / x_i = P_i_sat(T) / P (for Raoult's law)
- ψ = V/F = vapor fraction

Once ψ (or T, depending on problem type) is found:
- x_i = z_i / (1 + ψ·(K_i - 1))
- y_i = K_i · x_i

### Material Balance Verification

Always verify: z_i = x_i · (1 - ψ) + y_i · ψ for every component.
Also verify: Σ x_i = 1 and Σ y_i = 1.

## Equations of State

### Ideal Gas
PV = nRT

**Use when:** P < 5 atm, T >> T_c, gas phase only.

### Van der Waals
P = RT/(V_m - b) - a/V_m²

**Use when:** Teaching/understanding concepts. Poor quantitative accuracy near critical point.

**Physical meaning:**
- RT/(V_m - b): repulsive term (molecules have finite volume)
- a/V_m²: attractive term (intermolecular attraction reduces pressure)

### Soave-Redlich-Kwong (SRK)
P = RT/(V_m - b) - αa / [V_m(V_m + b)]

**Use when:** General-purpose process calculations. Good for hydrocarbon systems.

### Peng-Robinson
P = RT/(V_m - b) - αa / [V_m(V_m + b) + b(V_m - b)]

**Use when:** Most common in process simulation (Aspen, HYSYS, DWSIM). Best general-purpose cubic EOS. Slightly better than SRK for liquid density prediction.

## Energy Balances

### First Law (Closed System)
ΔU = Q - W

### First Law (Open System, Steady State)
Q - W_s = Σ(n_out · H_out) - Σ(n_in · H_in)

### Heat Capacity Relations
- Constant pressure: Q = n · C_p · ΔT
- Constant volume: Q = n · C_v · ΔT
- C_p - C_v = R (ideal gas)

### Clausius-Clapeyron Equation
ln(P2/P1) = -(ΔH_vap/R) · (1/T2 - 1/T1)

**Use when:** Estimating boiling point at non-standard pressures, or vapor pressure at non-standard temperatures. Assumes ΔH_vap is constant over the temperature range.
