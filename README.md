# World Cup Results — GitHub Pages demo

A small [Jekyll](https://jekyllrb.com/) site for [GitHub Pages](https://pages.github.com/)
that shows **FIFA World Cup results from 1930 to the in‑progress 2026 edition**:
every match with its date, stage, teams, score (and penalty shoot‑outs), plus
links back to Wikipedia.

## How it works

- **Data** is fetched at runtime, in the browser, from a remote JSON file:
  <https://yoannchaudet.github.io/pages-demo-00/data/worldcups.json>. The URL is
  configured once as `data_url` in [`_config.yml`](_config.yml) and exposed to
  the client.
- **Rendering** is done client‑side by [`assets/worldcups.js`](assets/worldcups.js)
  (plain, dependency‑free JavaScript). No data is stored in this repository and
  nothing is fetched at build time.
- **Pages** are thin Markdown/Liquid stubs that provide containers for the JS to
  fill in:
  - [`index.md`](index.md) — a `#tournaments-app` container that becomes the
    summary table of every tournament (host, winner, runner‑up, match count).
  - `tournaments/<year>.md` — one lightweight stub per edition carrying its
    `year`; [`_layouts/tournament.html`](_layouts/tournament.html) renders a
    `#tournament-app` container that the JS fills with the full match list.

## Data source

The dataset is produced and hosted by a separate project
([`pages-demo-00`](https://github.com/yoannchaudet/pages-demo-00)) from
Wikipedia / Wikidata. This repository only consumes it. To point the site at a
different dataset, change `data_url` in [`_config.yml`](_config.yml).

## Run locally

```bash
bundle install
bundle exec jekyll serve
# open http://127.0.0.1:4000
```

The data loads from the remote URL, so an internet connection is required to see
results while running locally.

## Notes

- This is a demo; the underlying match data is parsed from Wikipedia and may
  contain minor gaps for the earliest tournaments (e.g. walkovers).
- The site uses no Jekyll plugins beyond the default GitHub Pages set, so it
  builds as‑is on GitHub Pages.

test
aa
