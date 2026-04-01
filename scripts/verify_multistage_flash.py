#!/usr/bin/env python3
"""
Verify expected outputs for multistage-flash-01 fixture.

Problem: Two-stage flash cascade for benzene/toluene separation.
  Stage 1: Feed (100 kmol/h, 60% benzene) → Flash at T=365 K, P=101.325 kPa
  Stage 2: Liquid from Stage 1 → Flash at T=350 K, P=60 kPa

Uses Raoult's law with Perry's Antoine constants (log10, mmHg, °C).
"""

import json
from dataclasses import dataclass
from scipy.optimize import brentq

# Antoine constants (Perry's): log10(P_sat/mmHg) = A - B/(C + T/°C)
ANTOINE = {
    "benzene": (6.90565, 1211.033, 220.790),
    "toluene": (6.95464, 1344.800, 219.482),
}

MMHG_TO_KPA = 101.325 / 760.0


def psat_kpa(compound: str, T_K: float) -> float:
    """Saturation pressure in kPa from Antoine equation."""
    A, B, C = ANTOINE[compound]
    T_C = T_K - 273.15
    log10_p_mmhg = A - B / (C + T_C)
    return 10**log10_p_mmhg * MMHG_TO_KPA


def solve_flash(z_benzene: float, T_K: float, P_kPa: float):
    """
    Solve isothermal flash for binary benzene/toluene.
    Returns: (V_over_F, x_benzene, y_benzene)
    """
    z = [z_benzene, 1 - z_benzene]
    K = [
        psat_kpa("benzene", T_K) / P_kPa,
        psat_kpa("toluene", T_K) / P_kPa,
    ]

    # Check if mixture is subcooled or superheated
    bubble_sum = sum(z_i * K_i for z_i, K_i in zip(z, K))
    dew_sum = sum(z_i / K_i for z_i, K_i in zip(z, K))

    if bubble_sum < 1.0:
        raise ValueError(f"Subcooled liquid at T={T_K} K, P={P_kPa} kPa (bubble_sum={bubble_sum:.4f} < 1)")
    if dew_sum < 1.0:
        raise ValueError(f"Superheated vapor at T={T_K} K, P={P_kPa} kPa (dew_sum={dew_sum:.4f} < 1)")

    def rachford_rice(psi):
        return sum(z_i * (K_i - 1) / (1 + psi * (K_i - 1)) for z_i, K_i in zip(z, K))

    V_over_F = brentq(rachford_rice, 0.0, 1.0, xtol=1e-14)

    x = [z_i / (1 + V_over_F * (K_i - 1)) for z_i, K_i in zip(z, K)]
    y = [K_i * x_i for K_i, x_i in zip(K, x)]

    # Verify
    assert abs(sum(x) - 1.0) < 1e-10, f"sum(x) = {sum(x)}"
    assert abs(sum(y) - 1.0) < 1e-10, f"sum(y) = {sum(y)}"
    z_check = [x_i * (1 - V_over_F) + y_i * V_over_F for x_i, y_i in zip(x, y)]
    for z_orig, z_c in zip(z, z_check):
        assert abs(z_orig - z_c) < 1e-10, f"Material balance error: {z_orig} vs {z_c}"

    return V_over_F, x[0], y[0]


def main():
    # === STAGE 1 ===
    F1 = 100.0  # kmol/h
    z1_benz = 0.60
    T1 = 365.0  # K
    P1 = 101.325  # kPa

    print("=" * 60)
    print("STAGE 1: Flash at T=365 K, P=101.325 kPa")
    print("=" * 60)
    print(f"Feed: {F1} kmol/h, z_benzene = {z1_benz}")
    print(f"P_sat benzene at {T1} K: {psat_kpa('benzene', T1):.2f} kPa")
    print(f"P_sat toluene at {T1} K: {psat_kpa('toluene', T1):.2f} kPa")

    VF1, x1_benz, y1_benz = solve_flash(z1_benz, T1, P1)
    L1 = F1 * (1 - VF1)
    V1 = F1 * VF1

    print(f"\nV/F = {VF1:.6f}")
    print(f"x_benzene = {x1_benz:.6f}, x_toluene = {1 - x1_benz:.6f}")
    print(f"y_benzene = {y1_benz:.6f}, y_toluene = {1 - y1_benz:.6f}")
    print(f"L1 = {L1:.4f} kmol/h")
    print(f"V1 = {V1:.4f} kmol/h")

    # === STAGE 2 ===
    F2 = L1
    z2_benz = x1_benz
    T2 = 350.0  # K
    P2 = 60.0  # kPa

    print("\n" + "=" * 60)
    print("STAGE 2: Flash at T=350 K, P=60 kPa")
    print("=" * 60)
    print(f"Feed: {F2:.4f} kmol/h, z_benzene = {z2_benz:.6f}")
    print(f"P_sat benzene at {T2} K: {psat_kpa('benzene', T2):.2f} kPa")
    print(f"P_sat toluene at {T2} K: {psat_kpa('toluene', T2):.2f} kPa")

    VF2, x2_benz, y2_benz = solve_flash(z2_benz, T2, P2)
    L2 = F2 * (1 - VF2)
    V2 = F2 * VF2

    print(f"\nV/F = {VF2:.6f}")
    print(f"x_benzene = {x2_benz:.6f}, x_toluene = {1 - x2_benz:.6f}")
    print(f"y_benzene = {y2_benz:.6f}, y_toluene = {1 - y2_benz:.6f}")
    print(f"L2 = {L2:.4f} kmol/h")
    print(f"V2 = {V2:.4f} kmol/h")

    # === OVERALL ===
    print("\n" + "=" * 60)
    print("OVERALL RESULTS")
    print("=" * 60)

    # Total benzene in feed
    benz_feed = F1 * z1_benz

    # Benzene in V1
    benz_V1 = V1 * y1_benz
    # Benzene in V2
    benz_V2 = V2 * y2_benz
    # Benzene in final liquid L2
    benz_L2 = L2 * x2_benz

    total_benz_recovery = (benz_V1 + benz_V2) / benz_feed * 100

    print(f"Benzene in feed: {benz_feed:.4f} kmol/h")
    print(f"Benzene in V1:   {benz_V1:.4f} kmol/h")
    print(f"Benzene in V2:   {benz_V2:.4f} kmol/h")
    print(f"Benzene in L2:   {benz_L2:.4f} kmol/h")
    print(f"Balance check:   {benz_V1 + benz_V2 + benz_L2:.4f} kmol/h (should = {benz_feed:.4f})")
    print(f"\nOverall benzene recovery in vapor: {total_benz_recovery:.2f}%")
    print(f"Final liquid flow rate: {L2:.4f} kmol/h")
    print(f"Final liquid benzene fraction: {x2_benz:.6f}")

    # === Fixture values (rounded for fixture) ===
    print("\n" + "=" * 60)
    print("FIXTURE VALUES (for JSON)")
    print("=" * 60)
    results = {
        "stage1_vapor_fraction": round(VF1, 4),
        "stage1_liquid_benzene": round(x1_benz, 4),
        "stage1_vapor_benzene": round(y1_benz, 4),
        "stage1_liquid_flow": round(L1, 2),
        "stage1_vapor_flow": round(V1, 2),
        "stage2_vapor_fraction": round(VF2, 4),
        "stage2_liquid_benzene": round(x2_benz, 4),
        "stage2_vapor_benzene": round(y2_benz, 4),
        "stage2_liquid_flow": round(L2, 2),
        "stage2_vapor_flow": round(V2, 2),
        "overall_benzene_recovery_pct": round(total_benz_recovery, 1),
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
