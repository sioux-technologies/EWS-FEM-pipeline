# Manual COMSOL Derived Values CSV Workflow

Korte fallback-workflow wanneer de automatische postprocess niet betrouwbaar loopt.

## Voorbereiding

1. Open de gewenste `*_result.mph` in COMSOL.
2. Controleer dat de juiste dataset actief is, meestal `Study 1/Solution 1`.
3. Gebruik voor globale borstwaarden de breast-union domain selection, bijvoorbeeld `Union 15` als dat in dit model de volledige breast union is.

## Derived Values Aanmaken

Maak onder `Results > Derived Values` deze waarden aan:

| Doel | Derived Value | Selection | Expression | Unit |
| --- | --- | --- | --- | --- |
| Breast volume | Volume Integration | Breast union domain | `1` | `1` |
| Avg displacement | Volume Average | Breast union domain | `solid.disp` | `mm` | # Kan samen met avg VM stress
| Max displacement | Volume Maximum | Breast union domain | `solid.disp` | `mm` | # Kan samen met max VM stress
| Avg VM stress | Volume Average | Breast union domain | `solid.mises` | `kPa` |
| Max VM stress | Volume Maximum | Breast union domain | `solid.mises` | `kPa` |

Voor volume geldt:

```text
volume_ml = volume_m3 * 1e6
```

## Tijdreeks Evalueren

1. Kies bij de Derived Value dezelfde dataset en dezelfde time selection voor alle cases.
2. Gebruik bij voorkeur alle opgeslagen solution times.
3. Klik `Evaluate`.
4. Controleer of de tabel een kolom `Time (s)` bevat.

## CSV Exporteren

1. Ga naar `Results > Tables`.
2. Selecteer de tabel die bij de Derived Value hoort.
3. Exporteer/sla op als CSV.
4. Bewaar de CSV onder:

```text
analysis_output\comsol_pipeline\manual_postprocess\tables\<case_id>\
```

Gebruik exact deze namen:

```text
<case_id>_avg_timeseries.csv
<case_id>_max_timeseries.csv
```

De `avg_timeseries` CSV bevat:

```text
time_s, avg_displacement_mm, avg_vm_kpa
```

De `max_timeseries` CSV bevat:

```text
time_s, max_displacement_mm, max_vm_kpa
```

Daarna kan de samenvatting opnieuw worden opgebouwd met:

```text
python tools\update_manual_postprocess_summary.py
```

## Let Op

- Gebruik per vergelijking exact dezelfde selection, expressions, units en time selection.
- Meerdere expressions in een Derived Value mag, maar COMSOL zoekt het maximum per expression apart.
- Exporteer liever CSV's dan alleen de `.mph` op te slaan; CSV's zijn kleiner en makkelijker terug te vinden.
