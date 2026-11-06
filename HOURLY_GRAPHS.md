# Valandinis gamybos grafikas / Hourly production graph

## Paprasta sąranka / Easy setup (0.4.0)

**Lietuviškai:** HACS atnaujinkite iki **0.4.0** ir paleiskite HA iš naujo.
Įsitikinkite, kad integracija pridėta per **Nustatymai → Įrenginiai ir paslaugos**:
vien HACS atsisiuntimas paskyros nesukuria. Prie **eParkai įžvalgos** spauskite
**Konfigūruoti** ir pasirinkite energijos šaltinį. Integracija pati importuos
valandas, patikrins statistiką ir prijungs ją prie energijos skydelio. YAML nereikia.

- **Nutolusi elektrinė: gamyba + visas eksportas** – tik kai visa gamyba
  atiduodama į tinklą. Pridedama saulės gamyba ir atskira eksporto jungtis.
- **Tik saulės gamyba** arba **Tik atidavimas į tinklą** – pridedamas vienas šaltinis.
- **Tik importuoti istoriją** – atnaujinama statistika, energijos nustatymai nekeičiami.

Energijos skydelyje pasirinkite **vakarykštę arba paskutinę paskelbtą dieną**.
Įrenginio diagnostikos jutiklis **Istorijos importas** turi rodyti
**Paruošta energijos skydeliui**. Jei rodo klaidą ar nėra pilnų valandų, sąranka
nepridės netinkamo šaltinio. Parinktys pridedamos, o esami namų skaitikliai
nekeičiami; nereikalingus šaltinius šalinkite energijos skydelio nustatymuose.

**English:** Update to **0.4.0** in HACS and restart HA. Ensure the integration
is also added under **Settings → Devices & services**; downloading in HACS alone
does not create an account entry. Open **eParkai įžvalgos → Configure**, choose
the Energy connection, and submit. It imports, verifies and connects the series
automatically. No YAML, templates, utility meters or statistic IDs to copy.

Use **Remote plant: production + full export** only when all output goes to the
grid. This adds solar production and a separate export-only grid connection,
following [HA's dedicated solar export guidance](https://www.home-assistant.io/docs/energy/faq/#setting-up-a-dedicated-solar-export-connection-in-the-energy-dashboard).
Solar-only and export-only are also available. Existing household meters and
prices are preserved. Repeating setup does not duplicate sources. To remove an
added source, use Energy settings; the integration does not continually re-add it.

Open Energy and select **yesterday or the latest published day**. The diagnostic
**History import** sensor should read **Ready for Energy**. Delayed data is not
live power, and reporting delay does not determine whether it is export.
The steps below are only for an optional separate Statistics graph card.

## Lietuviškai

Nuo 0.3.0 eParkai įžvalgos importuoja visas pilnas valandas iš portalo savaitės
lango į HA ilgalaikę statistiką. Naktį gauti vakarykščiai rodmenys įrašomi prie
**vakarykščių gamybos valandų**, o ne prie atsisiuntimo laiko.

Atnaujinkite integraciją ir paleiskite HA iš naujo. Esamos sąrankos keisti nereikia.
Pirmas sėkmingas duomenų gavimas užpildys jau paskelbtas valandas. `recorder` turi
būti įjungtas; integracija jį deklaruoja kaip priklausomybę.

### Kortelė

1. Skydelyje pridėkite **Statistics graph** kortelę.
2. Statistikos pasirinkime raskite **jūsų elektrinės pavadinimas – Valandinė gamyba**.
3. Pasirinkite laikotarpį **hour**, statistikos tipą **change**, grafiko tipą
   **line** (kreivė) arba **bar** (stulpeliai).
4. Rodykite 2–7 dienas, kad matytųsi vėluojantys duomenys. Šiandienos valandos iki
   paskelbimo nebus užpildytos. Trūkstami duomenys nėra nulinė gamyba.

Suvestinės dienos ir valandos jutikliai lieka atskiroms skaitinėms kortelėms.
**Jų įprastas istorijos grafikas nerodo atgaline data importuotos statistikos.**
Valandinei kreivei būtina pasirinkti pirmiau nurodytą statistikos seriją.

Jei naudojate YAML, `PAKEISKITE` pakeiskite pagal jutiklio atributą `statistic_id`
(kopijuokite visą reikšmę, prasidedančią `eparkai_insights:`):

```yaml
type: statistics-graph
title: Valandinė saulės energijos gamyba
chart_type: line
period: hour
days_to_show: 7
stat_types:
  - change
entities:
  - entity: eparkai_insights:generation_PAKEISKITE
    name: Gamyba (kWh)
```

**Vienos dienos vaizdas:** energijos skydelio nustatymuose pridėkite tą pačią
**Valandinė gamyba** statistiką kaip saulės gamybos šaltinį. Pasirinkite dieną,
kurios duomenys jau paskelbti, ir matysite tos dienos valandinius stulpelius.
Nenaudokite suvestinės dienos jutiklio kaip kaupiamojo energijos skaitiklio.

HA grafikai naudoja naudotojo / HA laiko nustatymus. Norėdami sutapimo su portalu,
pasirinkite `Europe/Vilnius`. Importas saugo tikslius UTC momentus; rudenį dvi
pasikartojančios valandos išlieka atskiros. 15/30 minučių intervalai sumuojami į valandas.

### Būsena ir duomenų taisymai

- `statistics_import_status`: `pending` prieš pirmą importą, `imported` užbaigus
  importo operaciją, `failed` nepavykus (tikrinkite HA žurnalus).
- `last_statistics_import`: importo laikas, ne gamybos laikas.
- `statistic_id`: šios elektrinės ir objekto statistikos serijos identifikatorius.
- Dienos jutiklio `hours`: paskutinės pilnos dienos valandų pradžios ir kWh reikšmės
  individualioms kortelėms.

Pakartotinės užklausos ir paleidimas iš naujo tų pačių valandų neprideda antrą kartą.
Tiekėjo pataisyta valanda pakeičiama, o vėlesnės kaupiamosios sumos perskaičiuojamos.
Trūkstamas ar netinkamas naujas intervalas neištrina ankstesnio tinkamo rodmens.
Istorija lieka HA bazėje pasibaigus portalo savaitės langui. Ilgesnės nei grąžinamas
langas HA prastovos gali palikti tarpų; senesnė istorija papildomai neužklausiama.

## English

Version 0.3.0 imports all complete hours in the returned portal window into HA's
long-term statistics, using the **original production timestamps**. An overnight
batch fills yesterday's hours; it is not recorded as production at download time.

Update and restart HA; do not recreate the existing config entry. Keep recorder
enabled. Add a **Statistics graph**, select **your plant name – Valandinė gamyba**,
set **period: hour**, **statistic: change**, and **chart type: line** (or bar).
Show 2–7 days so delayed readings are visible. Missing current-day hours are not zero.

The summary sensors' normal history graphs will still show their state changes,
not backdated imports. Select the external statistic for the hourly curve.
For YAML, use the example above with the exact `statistic_id` sensor attribute.
Choose **change**, not cumulative **sum**, for the energy produced per hour.

For a single day's hourly bars, add the same statistic as a **solar source in the
Energy dashboard** and select a day whose data has been published. Use the
`Europe/Vilnius` display timezone to match the portal's clock labels. UTC storage
preserves both autumn hours; 15/30-minute samples are aggregated into full hours.

`statistics_import_status` shows `pending`, `imported`, or `failed`; consult HA
logs for a failure. `last_statistics_import` is fetch/import time, while each data
point retains its source timestamp. The daily sensor's `hours` attribute exposes
its latest complete day's curve for custom cards.

Reimports are idempotent. Corrections replace affected hours and recompute later
cumulative totals. Previously valid history survives missing new samples, and
recorded history remains when it leaves the provider's week window. Outages longer
than that window can leave gaps; this integration does not fetch older periods.

See [HA Statistics graph documentation](https://www.home-assistant.io/dashboards/statistics-graph/).
