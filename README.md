# Medieovervåkning

Dette prosjektet gir deg et enkelt program for medieovervåkning:

- Søk på et søkeord.
- Filtrer treff innenfor et gitt tidsrom.
- Lagre autosøk som kjøres daglig.
- Send rapport på e-post når autosøket trigges.
- Bruk et webgrensesnitt hvis du vil slippe terminalkommandoer.

## Krav

- Python 3.10+
- Internett-tilgang for å hente RSS fra Google News

## Start webgrensesnitt (anbefalt)

Kjør:

```bash
python web_ui.py
```

Åpne deretter i nettleseren:

```text
http://localhost:8080
```

I webgrensesnittet kan du:

- kjøre engangssøk,
- lagre daglig autosøk,
- se oversikt over lagrede autosøk.

## CLI (valgfritt)

Hvis du heller vil bruke kommandolinje kan du gjøre det slik:

### Kom i gang

```bash
python media_monitor.py init-db
```

### Engangssøk

```bash
python media_monitor.py search \
  --keyword "Equinor" \
  --start "2026-02-01T00:00:00+00:00" \
  --end "2026-02-19T23:59:00+00:00"
```

### Lagre daglig autosøk

Eksempel: send daglig rapport kl 07:30 UTC for siste 24 timer.

```bash
python media_monitor.py add-autosok \
  --keyword "Equinor" \
  --time "07:30" \
  --period-hours 24 \
  --email "deg@eksempel.no"
```

## Konfigurer e-post (for autosending)

Lag en `smtp_config.json`:

```json
{
  "smtp": {
    "host": "smtp.gmail.com",
    "port": 465,
    "user": "din-bruker@gmail.com",
    "password": "app-passord"
  }
}
```

## Kjør scheduler for daglig utsending

```bash
python media_monitor.py run-scheduler --config smtp_config.json
```

Scheduleren sjekker hvert minutt om noen regler skal kjøres.

## Merk

- Klokkeslett for autosøk lagres i UTC.
- Google News RSS har begrenset historikk. Programmet filtrerer tidsrommet på artiklene som faktisk kommer fra feeden.
