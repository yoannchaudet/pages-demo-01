---
layout: default
title: Home
---
# FIFA World Cup Results

A small [GitHub Pages](https://pages.github.com/) demo. Every tournament from
**1930** to the in‑progress **2026** edition, with full match lists, scores and
links to Wikipedia. All data lives in a single JSON file
(`_data/worldcups.json`) generated from Wikipedia / Wikidata, and these pages
read it through [Liquid](https://shopify.github.io/liquid/).

<table class="tournaments">
  <thead>
    <tr><th>Year</th><th>Host</th><th>Winner</th><th>Runner-up</th><th class="num">Matches</th></tr>
  </thead>
  <tbody>
  {%- assign tournaments = site.data.worldcups.tournaments | sort: "year" | reverse -%}
  {%- for t in tournaments -%}
    <tr>
      <td><a href="{{ '/tournaments/' | append: t.year | relative_url }}/">{{ t.year }}</a></td>
      <td>{{ t.host | default: "—" }}</td>
      <td>
        {%- if t.status == "in_progress" -%}
          <span class="badge badge-live">In progress</span>
        {%- else -%}
          🏆 {{ t.winner | default: "—" }}
        {%- endif -%}
      </td>
      <td>{{ t.runner_up | default: "—" }}</td>
      <td class="num">{{ t.matches | size }}</td>
    </tr>
  {%- endfor -%}
  </tbody>
</table>

<p class="meta">Data generated {{ site.data.worldcups.generated_at }} · source: {{ site.data.worldcups.source }}.</p>
