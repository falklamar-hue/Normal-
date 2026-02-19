# Kystvakt-varsling for oppdrettsanlegg

Dette er et enkelt Python-program som overvåker AIS-posisjoner og sender e-post når en kystvaktbåt nærmer seg valgte oppdrettsanlegg.

## Hva løsningen gjør

- Du legger inn **hvilke oppdrettsanlegg** som skal overvåkes (navn + koordinater).
- Programmet henter alle båter fra en AIS-kilde (`ais_endpoint`).
- Det filtrerer automatisk relevante båter (f.eks. navn/type som matcher `kystvakt`, `coast guard`, `KV`).
- Det måler avstand til hvert anlegg og sender e-post når avstanden er innenfor valgt terskel (`radius_km`).
- Den har `cooldown` for å unngå spam av samme hendelse.

## Kom i gang

1. Kopier eksempelkonfig:

```bash
cp config.example.json config.json
```

2. Fyll inn:

- riktige anlegg under `facilities`
- AIS-endepunkt under `watch.ais_endpoint`
- SMTP-innstillinger under `email`

3. Kjør en enkelt sjekk:

```bash
python3 kystvakt_varsel.py --config config.json --once
```

4. Kjør kontinuerlig:

```bash
python3 kystvakt_varsel.py --config config.json
```

## Konfig-felter

- `facilities`: Liste over oppdrettsanlegg med `name`, `latitude`, `longitude`
- `watch.radius_km`: Varslingsradius i kilometer (kan justeres)
- `watch.interval_seconds`: Hvor ofte AIS-data leses
- `watch.cooldown_seconds`: Minste tid mellom to varsler for samme båt/anlegg
- `watch.vessel_keywords`: Nøkkelord som brukes for å finne relevante kystvaktfartøy

## AIS-format som forventes

Endepunktet må returnere JSON med toppfelt `vessels`:

```json
{
  "vessels": [
    {
      "mmsi": "257123000",
      "name": "KV Sortland",
      "lat": 63.123,
      "lon": 8.456,
      "type": "Coast Guard"
    }
  ]
}
```

## Test

```bash
python3 -m unittest -v
```
