# World Cup Results — GitHub Pages demo

A small [Jekyll](https://jekyllrb.com/) site for [GitHub Pages](https://pages.github.com/)
that shows **FIFA World Cup results from 1930 to the in‑progress 2026 edition**:
every match with its date, stage, teams, score (and penalty shoot‑outs), plus
links back to Wikipedia.

## How it works

- **Data** lives in a single JSON file, [`data/worldcups.json`](data/worldcups.json)
  (a copy is written to `_data/worldcups.json` so Jekyll exposes it as
  `site.data.worldcups`).
- **Pages** are Markdown/Liquid templates that read that JSON — nothing is
  hand‑written per match:
  - [`index.md`](index.md) — summary table of every tournament (host, winner,
    runner‑up, match count).
  - `tournaments/<year>.md` — one lightweight stub per edition; all rendering is
    done by [`_layouts/tournament.html`](_layouts/tournament.html), which looks
    up the matching tournament in `site.data.worldcups` and prints the full
    match list.

## Data source

The dataset is generated from **Wikipedia / Wikidata** by
[`scripts/fetch_worldcups.py`](scripts/fetch_worldcups.py) (standard library
only, no dependencies):

- Tournament facts (host, dates) come from each edition's Wikidata entity;
  winner and runner‑up are derived from the final match.
- Match lists are parsed from the Wikipedia article wikitext (the group,
  knockout and dedicated‑match sub‑articles), handling the several
  `{{Football box}}` / `{{#invoke:Football box}}` template variants used across
  eras.
- The 2026 edition is in progress, so only completed matches carry a score;
  upcoming fixtures are omitted and the tournament is flagged `in_progress`.

Regenerate the data with:

```bash
python3 scripts/fetch_worldcups.py          # all editions
python3 scripts/fetch_worldcups.py 2026     # a single edition
```

Responses are cached under `scripts/.cache/` (git‑ignored); delete it to force a
fresh fetch.

## Run locally

```bash
bundle install
bundle exec jekyll serve
# open http://127.0.0.1:4000
```

## Notes

- This is a demo; match data is parsed from Wikipedia and may contain minor
  gaps for the earliest tournaments (e.g. walkovers).
- The site uses no Jekyll plugins beyond the default GitHub Pages set, so it
  builds as‑is on GitHub Pages.
