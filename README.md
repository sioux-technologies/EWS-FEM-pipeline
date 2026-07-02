# EWS COMSOL Breast FEM Pipeline

Parametric COMSOL finite-element breast modelling pipeline for the Early Warning Scan (EWS) internship project.

The project builds and evaluates a reproducible breast FEM workflow for testing how anatomy, tissue layout, support structures, dynamic excitation, and tumor/lesion assumptions affect the mechanical response of the breast. The current focus is not a patient-specific final model, but a defensible COMSOL pipeline that can generate controlled model variants and compare their displacement and stress response.

## Current Scope

The active model pipeline supports:

- stage-based COMSOL case definitions using TOML files
- parametrized chest-wall geometry and breast volume controls
- realistic glandular reference layouts using lobe-based distributions
- nipple and asymmetry sensitivity cases
- Cooper-ligament support sensitivity cases
- tumor/lesion sensitivity cases using stiffness-overlay regions
- fixed-support acceleration pulse studies for dynamic response screening
- automated export of summary metrics, time-series tables, and report figures

The current dynamic reference input is a mild fixed-support acceleration pulse:

- acceleration amplitude: `0.25g`
- duration: `0.60 s`
- mass damping: `alpha = 60 1/s`

Higher acceleration amplitudes such as `0.50g`, `1.00g`, and `1.25g` are used as diagnostic excitation scouts, not as direct claims of a real jump.

## Repository Layout

- `README.md`
  - startpunt voor nieuwe gebruikers: projectdoel, mapstructuur, actieve commands en outputbeleid

- `src/ews_fem_pipeline_comsol/`
  - active COMSOL pipeline package
  - TOML loading, source-case preparation, Java builder generation, COMSOL batch execution, and post-processing

- `runs/comsol_runs/`
  - active COMSOL run definitions
  - TOML files are kept for provenance
  - generated build/solve artefacts are intentionally ignored by Git

- `runs/comsol_testcases/`
  - small settings templates and testcase references
  - `all_settings.toml` gives a readable overview of the main editable settings
  - `all_default_settings.toml` lists the raw default COMSOL pipeline settings

- `analysis_output/comsol_pipeline/`
  - lightweight report-oriented evaluation output
  - summary CSV/Markdown tables and comparison plots

- `docs/internship_deliverables/`
  - current internship report and presentation deliverables

- `docs/report_working_notes/`
  - compact handover notes, literature overviews, parameter summaries, and model-justification documents

- `docs/Literature/`
  - literature PDFs used for model assumptions and report justification

- `tools/`
  - evaluation and plotting utilities, including COMSOL comparison plots

- `pictures/`
  - local model screenshots and animations used while preparing report figures

## Where To Look First

For new users, the most useful entry points are:

1. `src/ews_fem_pipeline_comsol/README.md`
   - explains the COMSOL package structure and pipeline order

2. `runs/comsol_runs/geometry_stage5/`
   - current dynamic/material/skin sensitivity cases
   - most useful control route for recent model calibration work

3. `runs/comsol_runs/geometry_stage6/`
   - current tumor/lesion sensitivity TOMLs
   - use only matched control/tumor pairs when interpreting tumor effects

4. `analysis_output/comsol_pipeline/manual_postprocess/`
   - manually exported COMSOL Derived Values CSVs for solve-only scouts
   - useful when automated postprocess is slow or unreliable

5. `docs/report_working_notes/`
   - compact parameter overview, current limitations, literature overviews, and model-justification notes

6. `docs/report_working_notes/model_justification/`
   - model assumptions and literature justification notes

7. `pictures/`
   - screenshots and animations used to judge geometry and motion visually

## Active Stage Structure

The main COMSOL stage definitions are kept in:

- `runs/comsol_runs/geometry_stage1`
  - motion sanity baseline
  - simple baseline geometry for validating the 0.25g dynamic input

- `runs/comsol_runs/geometry_stage2_chestwall`
  - chest-wall geometry sensitivity
  - current report route uses transverse `xoffset055` curvature with volume preservation and auto-alignment

- `runs/comsol_runs/geometry_stage3`
  - realistic glandular reference spread
  - used to move from simple glandular fraction tests toward lobe-based tissue distributions

- `runs/comsol_runs/geometry_stage4`
  - asymmetry and nipple-position sensitivity cases
  - reference case is intentionally close to the Stage 3 realistic reference

- `runs/comsol_runs/geometry_stage5`
  - no-Cooper control and Cooper-ligament sensitivity cases
  - current no-Cooper control is the most stable mechanical reference for dynamic amplitude scouting

- `runs/comsol_runs/geometry_stage6`
  - tumor/lesion sensitivity cases
  - current route uses no-Cooper reference anatomy with tumor material overlay variants

## Typical Commands

Run these commands from the repository root in the configured `ews-fem` Anaconda environment.

The expected environment is a local Anaconda/Conda environment with the package
installed from this repository and the dependencies needed for TOML loading,
mesh/source-case preparation, plotting, and COMSOL batch orchestration. COMSOL
Multiphysics and a valid COMSOL license are required for build, solve, and
post-processing commands. If you recreate the environment, first confirm that:

- Python can import the local `src/` package, for example by running commands
  from an environment where `src` is on `PYTHONPATH`;
- the main Python packages are available: `numpy`, `pydantic`, `pydantic-core`,
  `gmsh`, `matplotlib`, and `Pillow`; these are also listed in
  `requirements.txt`;
- `python -m ews_fem_pipeline_comsol --help` works from the repository root;
- COMSOL batch is available through the configured TOML paths or system PATH;
- the relevant TOML case points to an accessible COMSOL/JDK installation when Java compilation is enabled.

For a temporary PowerShell session, the local source package can be exposed with:

```powershell
$env:PYTHONPATH = "$PWD\src"
```

Build one or more COMSOL cases without solving:

```powershell
python -m ews_fem_pipeline_comsol build-only runs\comsol_runs\geometry_stage6\stage6_tumor_medium_upper_outer_surface_proximal_xoffset055_125g_solve_only_preview.toml
```

Run one or more full COMSOL cases:

```powershell
python -m ews_fem_pipeline_comsol run runs\comsol_runs\geometry_stage5\stage5_reference_no_cooper_xoffset055_125g_solve_only_preview.toml
```

Run post-processing only on existing solved results:

```powershell
python -m ews_fem_pipeline_comsol postprocess-only --mode global runs\comsol_runs\geometry_stage5\stage5_reference_no_cooper_xoffset055_125g_solve_only_preview.toml
```

Regenerate lightweight evaluation plots and tables:

```powershell
python tools\make_comsol_evaluation_plots.py
```

Check CLI options:

```powershell
python -m ews_fem_pipeline_comsol --help
```

## Manual COMSOL Workflow

The normal route is to run COMSOL through the Python CLI. For diagnostic cases,
it is also acceptable to run or inspect a case manually in COMSOL, especially
when only a `result.mph` file or a quick Derived Values export is needed.

Manual solve from an existing built/generated model:

1. Open the generated or patched model in COMSOL:
   - `runs/comsol_runs/<stage>/outputs/<case>/build/*generated_Model.mph`
   - or `runs/comsol_runs/<stage>/outputs/<case>/build/*reuse_parameter_patched.mph`

2. Confirm the model setup:
   - geometry is present;
   - expected domains/selections exist;
   - Study 1 is the intended transient study;
   - dynamic parameters match the TOML.

3. Run `Study 1` manually in COMSOL.

4. Save the solved model as:
   - `runs/comsol_runs/<stage>/outputs/<case>/solve/<case>_result.mph`

5. Export manual Derived Values CSVs to:
   - `analysis_output/comsol_pipeline/manual_postprocess/<case_name>/`

Recommended manual Derived Values:

- Volume Maximum:
  - `solid.disp` for maximum displacement magnitude
  - `solid.mises` for maximum von Mises stress

- Volume Average:
  - `solid.disp` for average displacement magnitude
  - `solid.mises` for average von Mises stress

Use the breast-domain selection for whole-breast metrics. For visual validation,
also inspect a displacement surface plot and a von Mises stress plot at the peak
motion/stress time.

## Output Policy

This repository is set up so Git tracks source code, TOML provenance, documentation, report notes, small summary tables, and selected lightweight figures.

The following generated artefacts are intentionally not tracked:

- COMSOL `.mph` files
- COMSOL recovery/status files
- generated build folders
- generated solve folders
- COMSOL configuration caches
- FEBio/mesh exports such as `.vtk`, `.vtu`, `.feb`, `.xplt`, `.npy`, `.npz`, `.obj`, `.stl`
- large local run outputs

This keeps the GitHub repository usable while still preserving the case definitions needed to reproduce important runs.

## Current Evaluation Outputs

The most important lightweight evaluation folders are:

- `analysis_output/comsol_pipeline/tier1_comparison`
  - Stage 1 through Stage 5 comparison including the motion sanity baseline

- `analysis_output/comsol_pipeline/tier1_comparison_without_stage1`
  - anatomical comparison without the Stage 1 simple-geometry baseline

- `analysis_output/comsol_pipeline/stage5_dynamic_amplitude_scout`
  - comparison of stable no-Cooper dynamic amplitude scouts

- `analysis_output/comsol_pipeline/stage6_fast_tumor_screening`
  - early tumor-screening output; treat partial or zero-series cases carefully

## Interpretation Notes

Stage 1 is a motion sanity baseline and should not be interpreted as the final anatomical reference. It uses a simpler and larger baseline geometry, so its displacement and stress response are not directly comparable to the later anatomical stages.

Stage 2 is the first fair anatomical geometry baseline. Stage 3 adds the realistic glandular reference spread. Stage 4 and Stage 5 references are intentionally close to Stage 3 because they serve as controls for asymmetry and Cooper-ligament sensitivity.

Stage 6 tumor cases are currently designed as controlled sensitivity experiments. The initial tumor implementation is useful for studying whether a local stiffness perturbation changes surface displacement, landmark displacement, stress evolution, or local tumor-region response. It should not yet be over-interpreted as a patient-specific tumor reconstruction.

## Useful Report Notes

Start with:

- `docs/report_working_notes/parameter_overview.md`
- `docs/report_working_notes/current_limitations.md`
- `docs/report_working_notes/pipeline_notes/comsol_pipeline_guide.md`
- `docs/report_working_notes/model_justification/comsol_vs_febio_model_positioning.md`
- `docs/report_working_notes/model_justification/tumor_overlay_plan.md`
- `docs/report_working_notes/literature_overviews/material_parameter_literature_overview.md`

## Main Limitations

- The current COMSOL model is a controlled parametric model, not a patient-specific reconstruction.
- Stage 1 is useful for motion validation but is not the final anatomical reference.
- Cooper-ligament implementation is still a mechanical support sensitivity route, not a validated anatomical reconstruction.
- Tumor/lesion modelling currently uses simplified size, location, and stiffness assumptions.
- Long COMSOL runs can generate large local artefacts; use TOMLs and lightweight summaries as the primary tracked provenance.

## Recommended Working Pattern

1. Create or edit a TOML case in the relevant `runs/comsol_runs/geometry_stage*` folder.
2. Run `build-only` first and inspect geometry, selections, and material settings in COMSOL.
3. Only run full dynamics after geometry placement and assumptions are acceptable.
4. Use `postprocess-only --mode global` first for quick solved-case checks.
5. Run heavier surface/tumor post-processing only for cases that are worth keeping.
6. Regenerate `analysis_output/comsol_pipeline` summaries for report-ready comparisons.
