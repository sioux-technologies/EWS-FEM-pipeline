# Stage 1 Dynamic Motion Interpretation - 0.25g for 0.60 s

Deze notitie legt uit hoe de huidige mild dynamic Stage 1 beweging moet worden geinterpreteerd:

```text
stage1_fixed_support_acceleration_pulse_mild_025g.toml
```

De case gebruikt:

```toml
dynamic_motion_mode = "fixed_support_acceleration_pulse"
dynamic_acceleration_amplitude_g = 0.25
dynamic_acceleration_duration_s = 0.60
dynamic_mass_damping_alpha_s_inv = 60.0
```

## Wat wordt er opgelegd?

Er wordt geen lokale kracht, tik of klap op de borst gezet. Er wordt ook geen expliciete plaatverplaatsing als boundary condition opgelegd.

In plaats daarvan krijgt het borstweefsel een tijdelijke verticale inertiele versnelling in een fixed-torso/fixed-chestwall frame.

Conceptueel:

- de posterior support/chestwall blijft vast;
- gravity is al opgebouwd;
- daarna wordt het breast tissue tijdelijk versneld;
- de borst beweegt relatief ten opzichte van de vaste borstkas/support;
- de belangrijkste evaluatiemaat is signed vertical displacement:

```text
w(t) - w(t_dynamic_start)
```

waarbij:

- `w` de verticale COMSOL displacement is;
- negatieve `w` omlaag betekent;
- `t_dynamic_start` het startpunt is vlak voor de dynamische excitatie.

## Wat betekent 0.25g?

`0.25g` betekent dat de maximale extra versnelling gelijk is aan een kwart van de zwaartekrachtversnelling:

```text
g = 9.81 m/s2
0.25g = 0.25 * 9.81 = 2.45 m/s2
```

De 0.25 is dus geen kracht in Newton. Het is een versnelling als fractie van `g`.

De effectieve inertiele belasting hangt vervolgens af van de massa/dichtheid van het weefsel:

```text
F = m * a
```

COMSOL rekent dit lokaal via body acceleration/body load uit op basis van:

- tissue density;
- breast volume;
- materiaalstijfheid;
- support boundary;
- damping;
- geometrie.

## Hoe ziet de acceleration pulse eruit?

Voor de fixed-support acceleration pulse wordt een gladde sinusvormige versnelling gebruikt over de ingestelde duur `T`.

Voor de 0.25g case:

```text
a_max = 2.45 m/s2
T = 0.60 s
```

De gebruikte vorm is conceptueel vergelijkbaar met een full-sine pulse:

```text
a(t) = -a_max * sin(2*pi*(t - t_start)/T)
```

voor:

```text
t_start <= t <= t_start + T
```

Daarbuiten is de extra acceleration pulse nul.

Omdat het een full-sine is:

- de versnelling begint bij nul;
- gaat eerst in de ene richting;
- kruist halverwege weer nul;
- gaat daarna in de andere richting;
- eindigt weer bij nul.

Dat is gunstiger dan een abrupte blokpuls, omdat het geen harde sprong in acceleratie aan het model geeft.

## Platform-analogie

Een nuttige analogie is:

> De persoon staat op een verticaal bewegend platform. De torso/chestwall beweegt gecontroleerd, terwijl de borst door inertie relatief achterblijft en daardoor beweegt ten opzichte van de borstkas.

Maar belangrijk:

> In het COMSOL model wordt de plaatverplaatsing niet letterlijk opgelegd. De plaat is alleen een interpretatie van de inertiele versnelling.

Voor een full-sine acceleration pulse kun je de orde van grootte van een equivalente gladde platform-offset schatten met:

```text
s_peak ~= a_max * T^2 / (2*pi^2)
```

Voor 0.25g en 0.60 s:

```text
a_max = 2.45 m/s2
T = 0.60 s

s_peak ~= 2.45 * 0.60^2 / (2*pi^2)
s_peak ~= 2.45 * 0.36 / 19.739
s_peak ~= 0.0447 m
s_peak ~= 4.5 cm
```

Dus de beste praktische uitleg is:

> De 0.25g, 0.60 s input komt grofweg overeen met een zachte, gladde platformachtige versnelling met een equivalente verplaatsingsschaal van enkele centimeters, ongeveer 4-5 cm. Het is geen harde sprong van 14 cm en geen lokale impact.

## Waarom is lichaamsgewicht niet de hoofdparameter?

Bij een echte persoon is het lichaamsgewicht natuurlijk belangrijk voor hoe een platform of actuator ontworpen moet worden. Een platform dat een persoon van 60 kg of 100 kg met dezelfde versnelling beweegt, vraagt verschillende kracht:

```text
F_platform = m_person * a
```

Voor 0.25g:

```text
a = 2.45 m/s2
```

Voorbeelden:

```text
60 kg persoon:  F = 60 * 2.45 ~= 147 N extra dynamische kracht
75 kg persoon:  F = 75 * 2.45 ~= 184 N extra dynamische kracht
90 kg persoon:  F = 90 * 2.45 ~= 221 N extra dynamische kracht
100 kg persoon: F = 100 * 2.45 ~= 245 N extra dynamische kracht
```

Maar in dit COMSOL breast model wordt niet het hele lichaam gemodelleerd. Alleen de borst/geometrie en support worden gemodelleerd. Daarom is de patient body mass niet direct een input in deze Stage 1 case.

Wat wel direct relevant is:

- breast volume;
- tissue density;
- breast mass;
- support/chestwall boundary;
- material stiffness;
- damping.

Voor een groter breast volume is de effectieve inertiele belasting op het breast tissue groter, omdat er meer massa is:

```text
F_breast ~= m_breast * a
```

Dit is precies waarom een latere size/cup-size of patient-volume sweep nuttig is: dezelfde 0.25g input kan bij een grotere borst een grotere totale inertiele belasting geven.

## Orde van grootte voor borstvolume en massa

Als je patientvolumes beschikbaar hebt, kun je die gebruiken om de modelrange beter te onderbouwen.

Een ruwe omzetting:

```text
1 ml = 1e-6 m3
tissue density ~= 900-1100 kg/m3
```

Dus:

```text
breast mass ~= volume_m3 * density
```

Voorbeelden bij dichtheid ongeveer 950 kg/m3:

```text
250 ml  -> 0.00025 m3 * 950 ~= 0.24 kg
500 ml  -> 0.00050 m3 * 950 ~= 0.48 kg
750 ml  -> 0.00075 m3 * 950 ~= 0.71 kg
1000 ml -> 0.00100 m3 * 950 ~= 0.95 kg
```

Bij 0.25g geeft dat een ruwe totale inertiele kracht op het borstweefsel:

```text
250 ml:  0.24 kg * 2.45 ~= 0.6 N
500 ml:  0.48 kg * 2.45 ~= 1.2 N
750 ml:  0.71 kg * 2.45 ~= 1.7 N
1000 ml: 0.95 kg * 2.45 ~= 2.3 N
```

Dit zijn grove orde-grootte schattingen. COMSOL verdeelt de belasting over het volume en de uiteindelijke displacement hangt af van materiaal, geometrie en support.

## Resultaat van de huidige 0.25g case

Voor de huidige Stage 1 baseline gaf de 0.25g case ongeveer:

```text
outer-surface mean vertical dynamic response:
  min ~= -11.1 mm
  max ~= +9.4 mm
  peak-to-peak ~= 20.5 mm

nipple vertical dynamic response:
  min ~= -21.0 mm
  max ~= +16.4 mm
  peak-to-peak ~= 37.4 mm
```

Dit is veel rustiger dan de 0.75g case:

```text
0.75g nipple peak-to-peak ~= 165 mm
```

Daarom is de 0.25g case momenteel de beste kandidaat voor een standaard dynamische beweging:

- duidelijk zichtbaar;
- niet extreem;
- weinig vergeleken met de te agressieve 0.75g case;
- plausibel als zachte platform/bounce-achtige engineering sensitivity.

## Mogelijke mildere alternatieven

Als 0.25g alsnog te sterk of te oncomfortabel klinkt, zijn logische mildere opties:

```text
0.20g gedurende 0.60 s
0.15g gedurende 0.60 s
0.25g gedurende 0.50 s
0.25g gedurende 0.45 s
```

Ruwe equivalente platform-offsets:

```text
0.25g, 0.60 s -> ongeveer 4.5 cm
0.20g, 0.60 s -> ongeveer 3.6 cm
0.15g, 0.60 s -> ongeveer 2.7 cm
0.25g, 0.50 s -> ongeveer 3.1 cm
0.25g, 0.45 s -> ongeveer 2.5 cm
```

Let op: kortere duration verandert ook de frequentie-inhoud van de input. Dat kan het model soms juist dichter bij een eigenfrequentie brengen. Daarom is het vaak netter om eerst de amplitude te verlagen en de duur gelijk te houden.

## Hogere dynamic-amplitude sensitivity

De huidige 0.25g blijft de beste standaard voor rustige geometry-, tumor- en pipeline-validatie. Voor een echte beweeglijkheidsinterpretatie is het wel nuttig om later een aparte amplitude-sensitivity te doen, omdat literatuur over lopen, hardlopen en springen veel grotere borstverplaatsingen en versnellingen rapporteert dan de huidige realistische Stage 2-5 cases laten zien.

Aanbevolen volgorde:

```text
0.25g  -> standaard milde baseline
0.50g  -> eerste hogere amplitude
0.75g  -> alleen als 0.50g stabiel en fysisch rustig blijft
1.00g  -> bovengrens/diagnostic, niet meteen report default
```

Belangrijk voor de interpretatie:

- noem dit een `dynamic-amplitude sensitivity`;
- noem het niet direct een gevalideerde echte sprong;
- vergelijk bij voorkeur op dezelfde Stage 3/4/5 no-Cooper reference geometry;
- controleer of displacement ongeveer lineair schaalt met g;
- controleer of stress, time stepping en solver convergence niet plots ontsporen.

Als 0.25g ongeveer 3 mm review displacement geeft in de realistische Stage 2-5 route, dan zou een nette lineaire respons grofweg 6 mm bij 0.50g en 9 mm bij 0.75g kunnen geven. Een veel grotere sprong wijst eerder op solver-, contact-, materiaal- of pulse-vorm gevoeligheid dan op een zuivere amplitude-response.

## Damping sensitivity

De huidige mass damping is:

```text
dynamic_mass_damping_alpha_s_inv = 60.0
```

Deze waarde is een numerieke en fysische stabilisatieparameter. Hij bepaalt hoe snel vrije trillingen na de pulse uitdoven. Omdat demping sterke invloed kan hebben op peak displacement en stress, moet `alpha = 60 1/s` niet als universeel biologisch feit worden gepresenteerd.

Aanbevolen latere damping sweep:

```text
alpha = 30 1/s
alpha = 60 1/s
alpha = 90 1/s
```

Eerst alleen op een no-tumor reference case. Pas als de respons logisch is, dezelfde demping gebruiken voor tumor- en stage-effectcases. Voor het verslag is de juiste formulering: `alpha = 60 1/s was used as the current damped reference, with damping sensitivity identified as follow-up validation`.

## Aanbevolen formulering

Voor verslag/meeting:

> The final Stage 1 dynamic candidate applies a mild vertical inertial acceleration pulse of 0.25g over 0.60 s after gravity preload. This does not represent a local impact force, but a simplified fixed-torso inertial loading, comparable to a smooth platform-like vertical acceleration with an equivalent displacement scale of a few centimeters. The resulting nipple vertical response is approximately 37 mm peak-to-peak, which is much less excessive than the 0.75g diagnostic case and therefore more suitable as a canonical dynamic sensitivity input.

Nederlandse versie:

> De gekozen Stage 1 dynamische kandidaat gebruikt na gravity preload een milde verticale inertiele versnelling van 0.25g gedurende 0.60 s. Dit is geen lokale kracht of klap op de borst, maar een vereenvoudigde inertiele belasting in een fixed-torso frame, vergelijkbaar met een zachte platformachtige verticale versnelling met een equivalente verplaatsingsschaal van enkele centimeters. De nipple response is ongeveer 37 mm peak-to-peak en is daarmee veel realistischer dan de 0.75g diagnostic case.

## Stage 5.1 prescribed-support displacement scout

Naast de fixed-support acceleration route is nu een aparte Stage 5.1 motion-scout route toegevoegd. Het doel is niet om de huidige acceleration baseline direct te vervangen, maar om een fysisch intuitievere support-motion input te testen:

```text
runs/comsol_runs/geometry_stage5_1_motion_scout
```

Deze nieuwe route gebruikt:

```toml
dynamic_motion_mode = "prescribed_support_displacement"
dynamic_motion_profile = "smooth_c2_bump"
dynamic_support_displacement_amplitude_m = ...
dynamic_support_displacement_duration_s = 0.60
```

Belangrijk verschil met de bestaande acceleration baseline:

| Route | Wat beweegt er? | Interpretatie |
|---|---|---|
| `fixed_support_acceleration_pulse` | de support blijft vast; het borstvolume krijgt een tijdelijke inertiele versnelling | controlled diagnostic acceleration excitation |
| `prescribed_support_displacement` + `smooth_c2_bump` | de posterior attachment boundary `breast_attach_bnd` krijgt een expliciete verticale verplaatsing | platform/torso-motion scout |

De nieuwe `smooth_c2_bump` gebruikt een gladde bumpfunctie:

```text
s = (t - t_start) / T
z_support(t) = A * 64*s^3*(1-s)^3
```

voor:

```text
t_start <= t <= t_start + T
```

Daarbuiten is `z_support = 0`.

Deze vorm is gekozen omdat:

- de supportverplaatsing bij begin en einde nul is;
- de snelheid bij begin en einde nul is;
- de versnelling bij begin en einde nul is;
- de beweging daardoor minder abrupte pieken introduceert dan een korte parabolische jump.

Dit verschilt van de oudere FEBio/Femke-route. De FEBio-route gebruikte na gravity loading een parabolische prescribed displacement op de chest boundary. De default amplitude was ongeveer 10 mm, maar de actieve jumpduur was kort, ongeveer 0.09 s. De nieuwe COMSOL Stage 5.1 route houdt amplitude en duur expliciet gescheiden, zodat bijvoorbeeld 40 mm support motion over 0.60 s getest kan worden zonder dat de input automatisch een korte, felle jump wordt.

De eerste Stage 5.1 scouts zijn:

| Case | Support amplitude | Duration | Doel |
|---|---:|---:|---|
| `stage5_1_support20mm_060s_softskin_softint.toml` | 20 mm | 0.60 s | milde support-motion scout |
| `stage5_1_support40mm_060s_softskin_softint.toml` | 40 mm | 0.60 s | aanbevolen eerste solve scout |
| `stage5_1_support60mm_060s_softskin_softint.toml` | 60 mm | 0.60 s | sterkere diagnostic support-motion scout |

Alle drie gebruiken dezelfde eenvoudige scoutbasis:

- Stage 2 xoffset055 transverse chestwall;
- simple glandular structure;
- no Cooper scaffold;
- 1.5 mm volumetric skin;
- Femke/Ryan-like soft skin coefficients;
- soft adipose/glandular interior;
- postprocess uit in de TOML, zodat de result eerst visueel en handmatig gecontroleerd kan worden.

Voor evaluatie moet support motion apart worden gecontroleerd. Bij prescribed support displacement is absolute `w` op de outer surface niet genoeg, omdat een deel daarvan de opgelegde supportbeweging volgt. Daarom zijn de belangrijkste handmatige exports:

| Metric | Selection | Expression | Reden |
|---|---|---|---|
| imposed support displacement | `breast_attach_bnd` | `jump_z_t/1[mm]` | controle dat de support echt beweegt |
| support boundary displacement | `breast_attach_bnd` | `w/1[mm]` | controle dat COMSOL de boundary condition volgt |
| absolute surface vertical displacement | `outer_skin_free_bnd` | `w/1[mm]` | zichtbaar oppervlak |
| support-relative surface displacement | `outer_skin_free_bnd` | `(w-jump_z_t)/1[mm]` | werkelijke breast deformation t.o.v. de bewegende support |
| surface displacement magnitude | `outer_skin_free_bnd` | `solid.disp/1[mm]` | globale bewegingsgrootte |
| surface VM stress | `outer_skin_free_bnd` | `solid.mises/1[kPa]` | controle op stress-hotspots |

De support-relative maat `(w-jump_z_t)` is vooral belangrijk voor de EWS-interpretatie. Die geeft beter weer hoeveel de borstvorm verandert ten opzichte van de opgelegde torso/support motion.

Deze Stage 5.1 scouts moeten voorlopig als diagnostic motion scouts worden beschreven. Ze zijn bedoeld om te testen of een expliciet bewegende support visueel en numeriek beter interpreteerbare surface motion geeft dan de fixed-support acceleration pulse. Ze zijn nog geen gevalideerde patient- of EWS-device motion input.
