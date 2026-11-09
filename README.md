# MALA vs CP2K simulation reports

Presentation, plots and extracted SCF data comparing MALA density initialization with CP2K atomic guesses under Broyden mixing.

- [Presentation PDF](mala_cp2k_broyden/mala_cp2k_broyden.pdf)
- [Editable PowerPoint](mala_cp2k_broyden/mala_cp2k_broyden.pptx)
- [All slides at a glance](mala_cp2k_broyden/slide_overview.png)
- [Methods, sources and timing definitions](mala_cp2k_broyden/README.md)
- [Numerical summary](mala_cp2k_broyden/summary.csv)
- [Standalone plots](mala_cp2k_broyden/plots/)

The report covers Al near 298 K, liquid Al near 933 K and boron at 298 K. The archived counts are 15/17, 17/17 and 14/16 iterations (MALA/atomic), respectively. Aluminium used 11000 Ry; boron used 8000 Ry.

This repository contains report artifacts and analysis code. Raw simulation inputs and outputs are referenced in the methods document and remain in the original simulation workspace. Rebuilding from raw outputs requires that workspace; the PDFs, plots and extracted data can be read independently.

- [PP report](PP_report.md): density accuracy, basis/grid convergence and SCF initialization comparisons.
