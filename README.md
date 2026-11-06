# eParkai įžvalgos

[![Patikra](https://github.com/Skirmantas-SK/eparkai-insights/actions/workflows/validate.yml/badge.svg)](https://github.com/Skirmantas-SK/eparkai-insights/actions/workflows/validate.yml)
[![Versija](https://img.shields.io/github/v/release/Skirmantas-SK/eparkai-insights)](https://github.com/Skirmantas-SK/eparkai-insights/releases/latest)
![Home Assistant](https://img.shields.io/badge/Home_Assistant-2026.11.0%2B-blue)
[![MIT](https://img.shields.io/badge/Licencija-MIT-green)](LICENSE)

<img src="custom_components/eparkai_insights/brand/icon.png" alt="eParkai integracijos piktograma" width="128" height="128">

„Home Assistant“ integracija, skirta [eParkai](https://www.eparkai.lt) saulės elektrinės pagamintos energijos duomenims stebėti.

[English documentation](README.en.md)

Kiekvienai elektrinės ir objekto porai sukuriami du jutikliai:

| Jutiklis | Reikšmė |
| --- | --- |
| Paskutinės pilnos dienos gamyba | Naujausios **pilnos dienos iki šiandien**, kuriai yra visi duomenys, energijos suma (kWh) |
| Paskutinės pilnos valandos gamyba | Naujausios **pasibaigusios valandos**, kuriai yra visi duomenys, energijos suma (kWh) |

Valanda parenkama nepriklausomai nuo dienos. Pavyzdžiui, jei lapkričio 5 d. paskelbtos tik trys valandos, o lapkričio 4 d. duomenys pilni, dienos jutiklis rodys lapkričio 4 d., o valandos jutiklis – naujausią pilną lapkričio 5 d. valandą. Nulinė gamyba yra tinkamas rodmuo, taip pat ir naktį. Trūkstami ar netinkami duomenys nuliais nekeičiami.

## Diegimas per HACS

HA 2026.11 turi integruotą „Marketplace“; taip pat galima naudoti HACS pasirinktinės saugyklos diegimą. Ši integracija dar nėra numatytajame kataloge.

[![Pridėti saugyklą](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Skirmantas-SK&repository=eparkai-insights&category=integration)
[![Pradėti sąranką](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=eparkai_insights)

1. Atidarykite HACS ir pasirinkite **Custom repositories** (pasirinktinės saugyklos).
2. Įveskite `https://github.com/Skirmantas-SK/eparkai-insights` ir pasirinkite tipą **Integration**.
3. Suraskite **eParkai** ir atsisiųskite integraciją.
4. Paleiskite „Home Assistant“ iš naujo.
5. Atidarykite **Nustatymai → Įrenginiai ir paslaugos → Pridėti integraciją** ir ieškokite **eParkai**.
6. Sąrankos vedlyje įveskite prisijungimo duomenis, kliento ID, elektrinės ID, tikslią objekto adreso parinkties reikšmę ir duomenų intervalą.

**`configuration.yaml` redaguoti nereikia.** Kiekvienai papildomai elektrinės ir objekto porai integraciją pridėkite dar kartą. Numatytasis intervalas – 60 minučių; taip pat palaikomi 15 ir 30 minučių intervalai.

Sąrankos vedlys, klaidų pranešimai ir jutiklių pavadinimai išversti į lietuvių kalbą. „Home Assistant“ profilyje pasirinkite lietuvių kalbą, kad būtų naudojamas šis vertimas. Anglų kalbos vertimas taip pat išsaugotas. Jau rankiniu būdu pervadintų jutiklių pavadinimai automatiškai nekeičiami.

### Rankinis diegimas

Integracijos piktograma pateikiama kartu su komponentu (`brand/` kataloge).
Ji rodoma HA įrenginių ir paslaugų lange įdiegus integraciją. Palaikomos šviesi ir
tamsi temos bei didelės raiškos ekranai. Tai šiai integracijai sukurta piktograma,
ne oficialus eParkai logotipas. Jutikliai naudoja `mdi:solar-power` piktogramą.

Nukopijuokite `custom_components/eparkai_insights` į „Home Assistant“ konfigūracijos aplanko `custom_components` katalogą. Įprastas galutinis kelias: `/config/custom_components/eparkai_insights/manifest.json`. Paleiskite „Home Assistant“ iš naujo ir pridėkite integraciją per tą patį sąrankos vedlį.

Reikalinga „Home Assistant“ 2026.11.0 arba naujesnė versija. Prisijungimo duomenys saugomi „Home Assistant“ konfigūracijos įraše; saugokite šį katalogą ir atsargines kopijas. Sesijos slapukai laikomi atmintyje, po paleidimo iš naujo prisijungiama pakartotinai. Į Git saugyklą prisijungimo duomenų nekelkite.

### Jei naudojote ankstesnę integraciją

Ši integracija naudoja atskirą domeną `eparkai_insights` ir nepakeičia `algirdasc/hass-eparkai` (`eparkai`) failų. Ji pateikia dienos ir valandos jutiklius, o ne importuoja išorinę energijos statistiką. Neoficialus bendruomenės projektas, nesusijęs su eParkai ar Ignitis.

Jei jau įdiegėte **mūsų 0.1.x versiją**: pasidarykite HA atsarginę kopiją, pašalinkite jos įrašą per „Įrenginiai ir paslaugos“ ir seną komponentą per HACS. Įdiekite naują saugyklą ir vieną kartą pakartokite sąranką. Senas domenas buvo `eparkai`, naujas – `eparkai_insights`; ankstesni įrašai, jutiklių ID ir podėlis automatiškai neperkeliami. Atnaujinkite korteles ir automatizacijas. Senojo GitHub adreso peradresavimas nepakeičia HA domeno.

Jei naudojate kito autoriaus integraciją, jos šalinti nereikia. Abi gali veikti atskirai, tačiau abi užklausia portalą. Esama istorija šiuo atnaujinimu neperrašoma.

### Kodėl HACS vis dar rodo „icon not available“?

Neįdiegtos pasirinktinės saugyklos piktograma ir įdiegtos HA integracijos piktograma įkeliamos skirtingai. `brand/` failai veikia įdiegus komponentą; prieš diegimą katalogo piktograma priklauso nuo katalogo ir jo vaizdų paslaugos. Senesnis HACS gali naudoti seną CDN net po diegimo. Vien README paveikslėlis, GitHub aprašas ar naujas leidimas to negarantuoja.

Atnaujinkite HA / HACS, įdiekite leidimą, paleiskite HA iš naujo ir tikrinkite **Įrenginiai ir paslaugos**. Jei ten piktogramos nėra, pateikite HA bei HACS versijas ir ekrano nuotrauką. [HA piktogramų dokumentacija](https://contributors.home-assistant.io/marketplace/guides/integrations/#brand-images).

## Kur rasti ID ir objekto adresą

Prisijunkite prie eParkai portalo ir atidarykite gamybos puslapį.

- Adrese `/user/12345/generation` skaičius `12345` yra kliento ID.
- Puslapio HTML šaltinyje raskite `generation_electricity` parinkčių lauką: pasirinktos elektrinės `option` elemento `value` yra elektrinės ID.
- Objekto adresui naudokite tikslią `address` / `edit-address` parinkties `value` reikšmę su visais tarpais ir skyrybos ženklais. Palikite tuščią tik tada, kai objekto rinktis nereikia.

ID laikomi tekstu, todėl pradžioje esantys nuliai išsaugomi.

## Duomenys ir jų atnaujinimas

Integracija užklausia portalo savaitės duomenis paleidimo metu ir kas valandą. Po laikinos ryšio klaidos bandoma po 5 minučių; pakartojimo intervalas dvigubinamas iki 60 minučių. Prisijungimo klaida įjungia pakartotinio autentifikavimo vedlį. Automatiniai slaptažodžio bandymai sustabdomi iki pakartotinio prisijungimo arba integracijos įkėlimo iš naujo. Jei portalas prašo patvirtinti kontaktinius duomenis, pirmiausia tai atlikite naršyklėje.

Dienos jutiklio atributai: `date`, `last_interval`, `interval_count`. Valandos jutiklio atributai: `start`, `end`, `source_labels`, `interval_count`. Abu taip pat pateikia `validated_at`, `last_successful_fetch`, `last_update_success`, `period_available_in_response`, `is_stale` ir `timezone`. Atributų raktai palikti stabilūs, kad juos būtų patogu naudoti automatizacijose.

Paskutiniai patikrinti rodmenys išsaugomi ir atkuriami po paleidimo iš naujo. Jei atsakyme nėra pilno laikotarpio arba užklausa nepavyksta, ankstesni rodmenys išlaikomi. Kol tinkamo rodmens nėra, atitinkamas jutiklis nepasiekiamas. Pradinė ryšio ar prisijungimo klaida atideda integracijos įkėlimą; saugoti duomenys įkeliami sėkmingai užbaigus sąranką. Valandos rodmuo gali būti pateikiamas ir neturint pilnos dienos. Pataisyti to paties laikotarpio duomenys pakeičia ankstesnius rodmenis ir nėra pridedami antrą kartą.

Dienos rodmuo laikomas pasenusiu, jei jo data ankstesnė nei vakar Lietuvoje. Valandos rodmuo pasenęs, jei nuo jos pabaigos praėjo daugiau nei trys valandos. Abiem atvejais rodmuo taip pat pažymimas pasenusiu, jei ilgiau nei tris valandas nebuvo patikrintas arba paskutinė užklausa nepavyko. Būsena perskaičiuojama atnaujinant duomenis. Net sėkmingai gauti duomenys gali būti pasenę dėl portalo vėlavimo.

## Laikas ir apribojimai

- Naudojama `Europe/Vilnius` laiko juosta, nepriklausomai nuo HA nustatymų.
- Pilnai dienai būtini visi tinkami intervalai; palaikomos ir 23 bei 25 valandų dienos, kai keičiamas laikas.
- Rudenį pasikartojančios valandos išsaugomos atskirai su skirtingais UTC poslinkiais. Jei nėra abiejų pasikartojančių žymų, dviprasmiška valanda neskelbiama.
- 15 ir 30 minučių intervalai sudedami į pilnos valandos energijos sumą.
- Jutikliai rodo **istorinio laikotarpio energiją**, o ne momentinę galią ar kaupiamąjį skaitiklį. Jie neturi statistikos būsenos klasės ir nėra skirti naudoti kaip `total_increasing` šaltiniai energijos skydelyje. Galima naudoti jutiklių kortelėse, istorijoje ir automatizacijose.
- Ieškoma tik grąžintame savaitės lange; senesnė istorija papildomai neužklausiama.
- Naudojamos portalo svetainės užklausos, o ne oficiali vieša API. Laiko žymos laikomos intervalų pradžia pagal pateiktą protokolo aprašą. Šią prielaidą ir matavimo vienetus reikia patvirtinti su tikra paskyra.

## Kūrimas ir patikra

Su Python 3.13 ir įdiegtu `requests` paleiskite:

```sh
python -m unittest discover -s tests -v
python -m compileall -q custom_components tests
```

„Windows“ aplinkoje taip pat reikia `tzdata`. Testai naudoja sintetinius atsakymus ir prie portalo nesijungia. Atskirame CI rinkinyje naudojama tikra „Home Assistant“ biblioteka (2026.11.0 ir naujausia stabili versija), tikrinama sąranka, koordinatorius, saugykla ir jutiklių metaduomenys. Portalo užklausos ir platformų persiuntimas imituojami. Gyva eParkai paskyra ir visas HA vartotojo sąsajos scenarijus dar nepatikrinti. Dabartiniai rezultatai – [Actions](https://github.com/Skirmantas-SK/eparkai-insights/actions).

[Pakeitimai](CHANGELOG.md) · [Prisidėjimas](CONTRIBUTING.md) · [Saugumas](SECURITY.md) · [MIT licencija](LICENSE)

Įgyvendinimas remiasi [algirdasc/hass-eparkai](https://github.com/algirdasc/hass-eparkai) protokolu (peržiūrėtas pakeitimas `cc05ea2af1f2ffd54f6f9c6ca4a502a3bf2175d5`) ir pateiktu [EPARKAI_INTEGRATION.md](EPARKAI_INTEGRATION.md) aprašu anglų kalba. Duomenų gavimo ir sumavimo kodas įgyvendintas iš naujo, griežčiau tikrinant duomenis ir nepriklausomai parenkant dienos bei valandos rodmenis.
