# Medieovervåkning (Desktop MVP)

Et komplett førsteutkast til en Windows desktop-app for medieovervåkning med PySide6 GUI, RSS-kilder, lagrede søk, rapportgenerator og SMTP-utsending.

## Arkitektur (moduler)

- `main.py` – oppstart av app, dependency wiring, scheduler-start/stopp.
- `app/database.py` – SQLite-oppsett + settings-lagring.
- `app/models.py` – dataklasser (`Article`, `SavedSearch`, `ReportConfig`).
- `app/sources.py` – RSS-kilde-lag (henting + normalisering til `Article`).
- `app/search_engine.py` – matchlogikk, fraser/ord-parser, deduplisering via cache-nøkler.
- `app/services.py` – CRUD for lagrede søk og rapportoppsett.
- `app/reporting.py` – generering/eksport av HTML-rapport med klikkbare lenker.
- `app/mailer.py` – SMTP-sending (HTML-epost) + test-epost.
- `app/scheduler_service.py` – APScheduler bakgrunnsjobber (daglig/ukentlig/månedlig).
- `app/ui/main_window.py` – GUI med fanene:
  - Søk & treff
  - Automatiske søk
  - Rapporter
  - Innstillinger

## Funksjoner i MVP

- Manuelt søk med inkluder-/ekskluder-ord.
- Støtte for fraser med `"anførselstegn"` og ellers splitting på komma/mellomrom.
- Case-insensitive match.
- Inkluder-logikk = AND (alle inkluder-ord må finnes i tittel/sammendrag).
- Ekskluder-logikk = NONE (ingen ekskluder-ord kan finnes).
- Deduplisering:
  - Primært på URL.
  - Hvis URL mangler: `title + dato + source`.
- Resultatgrid med dato, kilde, tittel, link.
- Dobbeltklikk på rad åpner link i nettleser.
- Sortering i tabell.
- Eksport til HTML-rapport.
- Lagring i SQLite (`media_monitor.db`).
- Rapportoppsett med frekvens, tidspunkt, mottaker og valgte lagrede søk.
- SMTP testknapp og scheduler som kjører mens appen er åpen.
- Logging til `logs/app.log`.

## Installasjon (Windows)

1. Installer Python 3.11+.
2. Åpne PowerShell i prosjektmappen.
3. Opprett virtuelt miljø:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

4. Installer avhengigheter:

```powershell
pip install -r requirements.txt
```

## Kjør appen

```powershell
python main.py
```

## Standard RSS-kilder (default)

Disse legges inn første gang:

- Reuters World
- BBC World
- AP Top News

De kan endres i **Innstillinger → RSS-kilder** med format per linje:

```text
Navn|https://feed-url|1
```

- `1` = aktiv, `0` = deaktivert.

Eksempel:

```text
Reuters World|https://feeds.reuters.com/Reuters/worldNews|1
NRK Siste nytt|https://www.nrk.no/toppsaker.rss|1
Min interne feed|https://example.com/rss.xml|0
```

## E-postoppsett

I **Innstillinger → E-post (SMTP)** legger du inn:

- Host (f.eks. `smtp.gmail.com`)
- Port (vanligvis `465` for SSL)
- Bruker
- App-passord
- Fra-adresse

Test med **Rapporter → Send test-epost**.

## Viktige notater

- Appen bruker RSS (ikke scraping bak betalingsmur).
- Scheduler kjører kun mens appen er åpen (MVP).
- PDF-eksport er ikke implementert i MVP; HTML-eksport er implementert.
