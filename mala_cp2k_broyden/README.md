# MALA-assisted CP2K: Broyden case-study presentation

The presentation compares **MALA external-density initialization followed by CP2K** with **CP2K's atomic density guess**. Both routes perform the final self-consistent calculation in CP2K. Eight main slides and two appendices use archived runs; no new simulations were submitted.

Open `mala_cp2k_broyden.pptx` to edit or present, or `mala_cp2k_broyden.pdf` to share. Each standalone plot is supplied as PNG, SVG and PDF in `plots/`. The deck includes speaker notes explaining interpretation and limits.

## Recorded results

Values are ordered MALA / atomic.

| Case | Cutoff (Ry) | SCF steps | CP2K invocation wall (s) | MALA preparation (s) | MALA + CP2K (s) | Final energy difference (meV/atom) |
|---|---:|---:|---:|---:|---:|---:|
| Al, 298 K model | 11000 | 15 / 17 | 2284.42 / 3279.80 | ≈558.65 | ≈2843.07 | +0.07860 |
| Liquid Al, 933 K model, snapshot 8 | 11000 | 17 / 17 | 2486.44 / 2411.64 | 697.00 | 3183.44 | +0.03251 |
| Boron, 298 K, snapshot 6 | 8000 | 14 / 16 | 504.88 / 581.04 | ≈484.23 | ≥989.11 | −0.11758 |

The Al 298 K total is approximately 13.3% faster than its atomic reference; liquid Al is 32.0% slower; boron is at least 70.2% slower. The Al and boron component sums omit unrecorded preparation overhead. Thus Al's saving is an estimate and boron's slowdown is a lower bound. CP2K wall-time savings alone are 30.3%, −3.1% and 13.1%, respectively. The iteration reductions are 11.8%, 0% and 12.5%.

The logs support **15 vs 17 for Al 298 K**, rather than the recalled 14 vs 16. Boron is **14 vs 16 at 8000 Ry**. Its initial 11000 Ry probe failed: CP2K generated 120×120×160 grid points whereas the MALA cube had 108×108×135. This report therefore does not describe all three cases as a uniform 11000 Ry benchmark.

## How to read the figures

- `energy_vs_iteration`: actual CP2K SCF table energy in Hartree, with separate axes for the three cells. Absolute energies across different materials are not a stability comparison.
- `energy_vs_time`: the same energy against the cumulative per-iteration `Time` column. This excludes initialization, finalization and MALA preparation. Printed times have 0.1 s precision.
- `residual_vs_iteration`: CP2K's printed `Convergence` metric, with the common `EPS_SCF = 1e-5` stopping threshold. This is not an energy error or a density RMSE.
- `time_budget`: full CP2K invocation wall time from launcher logs, plus fresh MALA preparation. Queue delays, failed probes and unrelated attempts are excluded.
- `step_cost_and_final_energy`: median step time excluding the first `NoMix/Diag.` step, and signed final MALA-minus-atomic energy differences.
- `energy_distance_vs_time`: absolute distance to **each route's own final printed energy**, converted with 1 Ha = 27211.386245988 meV and divided by atom count. Endpoints are omitted because rounded SCF table energies cannot resolve zero. This is not error against an independent tightly converged reference.

The first SCF energy is obtained after diagonalization; it is not the raw starting-density energy or a standalone MALA total-energy prediction. SCF traces overshoot and oscillate. The small endpoint differences are consistent with finite convergence accuracy, but tighter SCF calculations are required to establish that explanation.

## Timing accounting

For Al 298 K, preparation is the sum of descriptors (245.5095 s), LDOS inference (300.6021 s), density integration (2.5564 s) and cube writing (9.9774 s). The archived `timing_report.txt` omitted cube writing from `T_MALA_plus_SCF`; this report includes it.

For liquid Al, preparation is the **697 s complete pipeline wall** recorded in `pipeline.log`; its component sum is 679.6198 s. The difference is retained as other preparation overhead in the stacked plot.

For boron, preparation is the component sum: descriptors 459.4458 s, inference 18.0261 s, density 4.0730 s, cube writing 2.6896 s. No complete preparation wall value was found in the selected report. Descriptor generation alone exceeds the 76.16 s CP2K saving.

The condition for a fresh MALA initializer to improve total compute time is `T_preparation < T_atomic_CP2K − T_MALA_CP2K`. Totals represent sequential compute durations, not measured submission-to-completion latency or allocation cost. Preparation and CP2K may use different workers.

## Exact source selection

Paths are relative to the workspace root.

1. Al 298 K: `logs/mala_cp2k_validation/20260921_225223_562895_2960795/` — `cp2k_mala.out`, `cp2k_atomic.out`, `mala_artifacts.json`, launcher logs and `pipeline.log`.
2. Liquid Al: `933K_hybrid_0/logs/snapshot8_full/20260930_104300_575271_4126053/` — `cp2k_external_density.out`, `cp2k_atomic_guess.out`, `mala_metadata.json` and launcher logs. Fresh held-out liquid snapshot 8, actual temperature 931.5366 K, 256 atoms. CP2K job 575329; preparation job 575271.
3. Boron CP2K: `boron_298K/logs/boron_cp2k/20260922_230542_564624_3335371/`. Fresh MALA metadata: `boron_298K/logs/boron_validation/20260922_224905_564590_3331209/boron_metadata.json`. Snapshot 6, 144 atoms; CP2K job 564624.

The earlier liquid snapshot-7 precomputed-density pair (23 vs 17 iterations) is excluded, as are DIRECT_P_MIXING experiments, resampled-grid runs, failures and incomplete calculations. The separate fresh snapshot-7 continuation is not combined with the earlier atomic reference. All liquid plots consistently use the fresh snapshot-8 pair.

## Provenance and interpretation limits

- The Al 298 K archived `.inp` files were subsequently edited: they now contain `DIRECT_P_MIXING` and `CUTOFF 800`. The actual historical outputs show `BROYDEN_MIXING`; the historical pipeline records `cutoff=11000`, `rel_cutoff=60` and the accepted 200³ cube. These edited inputs cannot reproduce the historical run as-is. Hashes capture their present state and the supporting evidence.
- Al 298 K's metadata temperature is approximately 299.99 K and electronic smearing is 300 K. “298 K” identifies the model/regime. Its imported cube integrates to 768.2867545890 electrons versus a target of 768; its final SCF density is approximately 768 electrons. Normalization warrants further audit.
- Within each selected pair, the CP2K outputs confirm the same host, 32 MPI ranks and one thread. Al 298 K and boron use `gh003`; liquid Al uses `cge065`. Runtime comparisons between materials are not hardware-controlled scaling benchmarks.
- Liquid Al emits warnings that Fermi–Dirac smearing includes the last molecular orbital. Check additional unoccupied orbitals before drawing high-accuracy physical conclusions.
- The much lower Al 298 K per-step cost is observed, but one pair cannot establish its cause. Repeat timings before attributing it to the initializer.
- Material, geometry, model, smearing, grid and hardware vary between regimes. These results do not isolate temperature, establish average speedups or provide statistical error bars.

Broyden's stored history is documented in the official [CP2K MIXING reference](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/DFT/SCF/MIXING.html): `NBUFFER` specifies previous steps stored by the mixing scheme. This motivates the interpretation that initialization can alter the path while subsequent history also governs convergence; it does not explain a temperature trend from these data alone.

## Rebuild and numerical audit

```bash
MPLCONFIGDIR=/tmp/mala_report_mpl python reports/mala_cp2k_broyden/build_report.py
```

The script parses every selected SCF row, checks contiguous iteration numbers and reported converged counts, verifies Broyden in the executed outputs, checks final convergence below the tolerance, and verifies matched CP2K hosts/ranks/threads. `summary.csv`, `results.json` and the three `*_scf.csv` files retain numerical results. `source_sha256.json` records source-file fingerprints. No original simulation output is modified.

The script creates both the editable PowerPoint and the PDF from the same slide descriptions, embeds speaker notes in PowerPoint, and writes `speaker_notes.txt` separately. It also saves slide previews. Python dependencies are numpy, matplotlib, Pillow and python-pptx. For this workspace session, python-pptx was installed temporarily under `/tmp/mala_report_deps`; the script uses that path as a fallback. For a future environment, install it in the active Python environment.

The PDF was rendered directly with matplotlib and visually checked. The PowerPoint archive was validated but could not be rendered by the local LibreOffice installation, which failed to load presentation files. Font layout can vary slightly in another presentation application. After editing, an Impress-capable LibreOffice installation can regenerate the PDF:

```bash
libreoffice --headless --convert-to pdf --outdir reports/mala_cp2k_broyden reports/mala_cp2k_broyden/mala_cp2k_broyden.pptx
```
