
### 1. Electronic density accuracy

All densities were compared on aligned periodic grids, using the same valence-density definition and without charge renormalization.

| Density | Global relative L2 error vs QE | Near nuclei (r < 0.75 Å) |
|---|---:|---:|
| **MALA prediction** | **0.401%** | **0.735%** |
| CP2K — DZVP | 1.823% | 5.920% |
| CP2K — vDZP (UZH) | 2.919% | — |

The most interesting observation is the **near-nucleus discrepancy**. Despite using the same UPF pseudopotential and XC functional, CP2K's converged DZVP density differs from QE by 5.92% near the nuclei, whereas MALA differs by only 0.735%.

Globally, MALA agrees with QE approximately **4.5 times better** than CP2K/DZVP; near nuclei, the difference is approximately **8 times**.

This suggests that the remaining mismatch is particularly pronounced around the atoms. Changing the Gaussian basis to vDZP actually worsened global agreement.

### 2. Basis and grid convergence

| Basis | Cutoff / REL_CUTOFF | Error vs QE | SCF steps | Full runtime |
|---|---|---:|---:|---:|
| DZVP | 800 / 60 Ry | 1.823% | 17 | 23.5 min |
| vDZP (UZH) | 800 / 60 Ry | 2.919% | 17 | 77.7 min |
| DZVP | 1000 / 80 Ry | 1.823% | 17 | 25.4 min |
| vDZP (UZH) | 1000 / 80 Ry | 2.919% | 17 | 77.4 min |

Increasing the grid resolution changes the density by only ~0.0015%, so the discrepancy is not explained by grid resolution.

The recommended `vDZP-GTH-q3` basis was also significantly more expensive, without improving agreement. Since both tested bases contain 13 functions per atom, this was a basis substitution rather than a systematic basis-convergence study.

### 3. SCF initialization

| Basis | Atomic guess | QE density guess | MALA guess |
|---|---:|---:|---:|
| DZVP | 17 | **14** | **14** |
| vDZP (UZH) | 17 | **15** | Not tested |

MALA essentially matches the convergence performance of the fully converged QE density under DZVP. However, even the exact QE density only saves 3 iterations relative to the atomic guess.

With vDZP, the improvement decreases to just 2 iterations.
