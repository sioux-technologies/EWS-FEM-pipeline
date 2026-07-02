# COMSOL Extended Displacement and Stress Exports

Deze notitie beschrijft de nieuwe, FEBio-achtigere COMSOL-evaluatie die is voorbereid in de pipeline. Er zijn geen zware COMSOL solves uitgevoerd voor deze wijziging.

## Displacementmaat

- COMSOL gebruikt hier `x/u` als lateraal links-rechts, `y/v` als anterior-posterior en `z/w` als verticaal.
- De fysisch belangrijkste signed displacement voor de jump/load response is daarom `w`.
- Negatieve `w` betekent beweging omlaag; positieve `w` betekent terug omhoog.
- De oude `solid.disp`/`disp_mag` blijft alleen een magnitude-diagnostiek. Die kan golvend of minder intuïtief lijken omdat richting verloren gaat.

## Surface Selection

De nieuwe report-surface selectie is:

- `outer_skin_free_bnd`

Deze wordt in de Java builder gemaakt als:

- `geom1_breast_outer_bnd` minus `breast_attach_bnd`.

Doel: de vrije outer breast/skin surface evalueren zonder de posterior attachment/chestwall band mee te middelen. Als COMSOL in een bepaalde versie de boolean selection `Difference` niet accepteert, valt de builder defensief terug op `geom1_breast_outer_bnd`. Controleer dan de generated selection notes en selection hints voordat je de surface displacement als report-ready gebruikt.

## Landmark Displacement

De COMSOL landmark exports zijn patch-gemiddelden, geen enkele mesh-node waarden:

- `landmark_nipple_bnd`
- `landmark_left_bnd`
- `landmark_right_bnd`
- `landmark_superior_bnd`
- `landmark_inferior_bnd`

Dit is stabieler dan een enkel punt, maar moet in het verslag worden beschreven als landmark-patch displacement. De belangrijkste reportplot is nipple/outer-surface `w` over tijd.

## Stressstatistieken

De exporter bereidt nu per tissue voor:

- mean von Mises;
- std von Mises;
- max von Mises;
- hotspot factor `max / mean`.

Median, p95 en p99 zijn nog niet fysisch correct beschikbaar uit alleen volume-integralen. Daarvoor is een sampled/raw field export nodig per tissue en tijdstap. De pipeline vult die percentielen daarom niet kunstmatig.

## Nieuwe Outputs

Na een nieuwe COMSOL run/postprocess met de bijgewerkte exporter kan `solve/` extra bestanden bevatten:

- `*_surface_displacement.csv`
- `*_landmark_displacement.csv`
- `*_tissue_stress_stats.csv`

De gewone `*_time_series.csv` blijft backwards compatible en krijgt alleen extra kolommen als de metrics beschikbaar zijn.

De plotgenerator `tools/make_comsol_evaluation_plots.py` leest deze bestanden optioneel en maakt dan extra figuren in `analysis_output/comsol_pipeline/<stage>/figures/`:

- `surface_signed_vertical_response.png`
- `surface_displacement_statistics.png`
- `landmark_nipple_signed_vertical_response.png`

Als de nieuwe CSV's ontbreken, worden deze plots niet gemaakt.

## Volgende Run

Een veilige code/generator-check is al mogelijk zonder solve:

```powershell
& 'C:\Users\20223231\.conda\envs\ews-fem\python.exe' -m ews_fem_pipeline_comsol generate runs\comsol_runs\geometry_stage1\baseline_simple_gland_dynamic_solid_only.toml
```

Om de nieuwe metrics echt te vullen is een COMSOL postprocess op een bestaande result MPH genoeg, zolang de basisselecties in de MPH aanwezig zijn. Gebruik daarvoor:

```powershell
& 'C:\Users\20223231\.conda\envs\ews-fem\python.exe' -m ews_fem_pipeline_comsol postprocess-only runs\comsol_runs\report_fixed_material_suite\sensitivity_stage5b_fixed_materials_order2.toml
```

Dit start geen solve, maar gebruikt wel COMSOL batch/licentie om de bestaande result-MPH opnieuw te openen en metrics/plots te exporteren.

Als postprocess-only faalt omdat een oude MPH de benodigde basisselecties niet bevat, is daarna pas een volledige nieuwe run nodig:

```powershell
& 'C:\Users\20223231\.conda\envs\ews-fem\python.exe' -m ews_fem_pipeline_comsol run runs\comsol_runs\report_fixed_material_suite\sensitivity_stage5b_fixed_materials_order2.toml
```
