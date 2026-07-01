#!/usr/bin/env python3
"""Fetch FIFA World Cup data (1930 -> partial 2026) into data/worldcups.json.

Sourcing strategy (hybrid, all data derived from Wikipedia / Wikidata):

* Tournament-level facts (winner, host, dates) come from the edition's Wikidata
  entity JSON (https://www.wikidata.org/wiki/Special:EntityData/<QID>.json),
  which models these reliably. The QID is resolved from the Wikipedia article
  via the MediaWiki ``pageprops`` API.
* Match lists come from parsing the Wikipedia article wikitext. Matches live in
  per-edition sub-articles (e.g. "2018 FIFA World Cup Group A",
  "2018 FIFA World Cup knockout stage") that the main article links to. Each
  match uses either the ``{{Football box}}`` template or the
  ``{{#invoke:Football box|main|...}}`` module invocation; both share the same
  field names (date / team1 / score / team2).

The 2026 edition is in progress: only completed matches are present, so partial
results fall out of the same pipeline naturally.

Run:  python3 scripts/fetch_worldcups.py
Output: data/worldcups.json  (and a copy at _data/worldcups.json for Jekyll)
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

API = "https://en.wikipedia.org/w/api.php"
WD_ENTITY = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
UA = "pages-demo-01/0.1 (World Cup demo; https://github.com/)"

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE_DIR = os.path.join(HERE, ".cache")

# Editions to include. Article titles follow "<year> FIFA World Cup".
YEARS = [
    1930, 1934, 1938, 1950, 1954, 1958, 1962, 1966, 1970, 1974, 1978,
    1982, 1986, 1990, 1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022, 2026,
]

# The edition that is currently in progress (partial results expected).
IN_PROGRESS_YEAR = 2026

# FIFA/IOC 3-letter codes -> country display name (incl. historical teams).
TEAM_CODES = {
    "ALG": "Algeria", "ANG": "Angola", "ARG": "Argentina", "AUS": "Australia",
    "AUT": "Austria", "BEL": "Belgium", "BIH": "Bosnia and Herzegovina",
    "BOL": "Bolivia", "BRA": "Brazil", "BUL": "Bulgaria", "CMR": "Cameroon",
    "CAN": "Canada", "CHI": "Chile", "CHN": "China PR", "COL": "Colombia",
    "CRC": "Costa Rica", "CRO": "Croatia", "CUB": "Cuba", "CPV": "Cape Verde",
    "CUW": "Curaçao", "CZE": "Czech Republic", "TCH": "Czechoslovakia",
    "DEN": "Denmark", "GDR": "East Germany", "ECU": "Ecuador", "EGY": "Egypt",
    "SLV": "El Salvador", "ENG": "England", "FRA": "France",
    "FRG": "West Germany", "GER": "Germany", "GHA": "Ghana", "GRE": "Greece",
    "HAI": "Haiti", "HON": "Honduras", "HUN": "Hungary", "ISL": "Iceland",
    "IRN": "Iran", "IRQ": "Iraq", "ITA": "Italy", "CIV": "Ivory Coast",
    "JAM": "Jamaica", "JPN": "Japan", "JOR": "Jordan", "KOR": "South Korea",
    "PRK": "North Korea", "KUW": "Kuwait", "MEX": "Mexico", "MAR": "Morocco",
    "NED": "Netherlands", "NZL": "New Zealand", "NGA": "Nigeria",
    "NIR": "Northern Ireland", "NOR": "Norway", "PAN": "Panama",
    "PAR": "Paraguay", "PER": "Peru", "POL": "Poland", "POR": "Portugal",
    "IRL": "Republic of Ireland", "ROU": "Romania", "RUS": "Russia",
    "KSA": "Saudi Arabia", "SCO": "Scotland", "SEN": "Senegal", "SRB": "Serbia",
    "SCG": "Serbia and Montenegro", "SVK": "Slovakia", "SVN": "Slovenia",
    "RSA": "South Africa", "URS": "Soviet Union", "ESP": "Spain",
    "SWE": "Sweden", "SUI": "Switzerland", "TOG": "Togo",
    "TRI": "Trinidad and Tobago", "TUN": "Tunisia", "TUR": "Turkey",
    "UKR": "Ukraine", "USA": "United States", "URU": "Uruguay",
    "UAE": "United Arab Emirates", "UZB": "Uzbekistan", "QAT": "Qatar",
    "WAL": "Wales", "YUG": "Yugoslavia", "ZAI": "Zaire",
    "DEI": "Dutch East Indies", "CSK": "Czechoslovakia", "ROM": "Romania",
    "ISR": "Israel", "US": "United States", "TCH": "Czechoslovakia",
    "SPA": "Spain", "COD": "DR Congo", "COG": "Congo",
}

# Section headings in knockout articles that are NOT match stages.
NON_STAGE_HEADINGS = {
    "format", "qualified teams", "bracket", "seeding", "references",
    "notes", "external links", "see also", "overview", "summary",
}

unknown_codes: set = set()


# Known total match counts per completed edition (for validation).
EXPECTED_MATCHES = {
    1930: 18, 1934: 17, 1938: 18, 1950: 22, 1954: 26, 1958: 35, 1962: 32,
    1966: 32, 1970: 32, 1974: 38, 1978: 38, 1982: 52, 1986: 52, 1990: 52,
    1994: 52, 1998: 64, 2002: 64, 2006: 64, 2010: 64, 2014: 64, 2018: 64,
    2022: 64,
}


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


_last_request = [0.0]
MIN_INTERVAL = 0.5  # seconds between live network requests (be polite)


def _get(url: str) -> str:
    """HTTP GET with a small on-disk cache to avoid refetching during dev."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = hashlib.sha1(url.encode()).hexdigest()
    path = os.path.join(CACHE_DIR, key)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    data = None
    for attempt in range(6):
        wait = MIN_INTERVAL - (time.time() - _last_request[0])
        if wait > 0:
            time.sleep(wait)
        _last_request[0] = time.time()
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read().decode("utf-8")
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 5:
                backoff = 5 * (attempt + 1)
                log(f"  429 rate-limited, sleeping {backoff}s: {url}")
                time.sleep(backoff)
                continue
            raise
        except Exception as exc:  # noqa: BLE001
            if attempt == 5:
                raise
            log(f"  retry ({exc}) {url}")
            time.sleep(2 * (attempt + 1))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(data)
    return data


def api_query(**params) -> dict:
    params.setdefault("format", "json")
    params.setdefault("formatversion", "2")
    url = API + "?" + urllib.parse.urlencode(params)
    return json.loads(_get(url))


def get_wikitext(title: str):
    data = api_query(action="query", prop="revisions", rvprop="content",
                     rvslots="main", titles=title, redirects=1)
    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return None
    try:
        return pages[0]["revisions"][0]["slots"]["main"]["content"]
    except (KeyError, IndexError):
        return None


def get_wikibase_qid(title: str):
    data = api_query(action="query", prop="pageprops", ppprop="wikibase_item",
                     titles=title, redirects=1)
    pages = data.get("query", {}).get("pages", [])
    if not pages:
        return None
    return pages[0].get("pageprops", {}).get("wikibase_item")


def wd_entity(qid: str) -> dict:
    return json.loads(_get(WD_ENTITY.format(qid=qid)))["entities"][qid]


def wd_label(qid: str):
    try:
        return wd_entity(qid).get("labels", {}).get("en", {}).get("value")
    except Exception:  # noqa: BLE001
        return None


def wd_claim_ids(entity: dict, prop: str) -> list:
    out = []
    for stmt in entity.get("claims", {}).get(prop, []):
        val = stmt.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(val, dict) and "id" in val:
            out.append(val["id"])
    return out


def wd_claim_time(entity: dict, prop: str):
    for stmt in entity.get("claims", {}).get(prop, []):
        val = stmt.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(val, dict) and "time" in val:
            m = re.match(r"\+(\d{4})-(\d{2})-(\d{2})", val["time"])
            if m:
                y, mo, d = m.groups()
                if mo == "00":
                    return y
                if d == "00":
                    return f"{y}-{mo}"
                return f"{y}-{mo}-{d}"
    return None


# --------------------------- wikitext parsing ---------------------------

def strip_wiki(text: str) -> str:
    """Reduce wikitext fragments to plain readable text."""
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"\[\[(?:[^\[\]|]*\|)?([^\[\]|]+)\]\]", r"\1", text)
    text = re.sub(r"'''?", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


FLAG_NAME_FIXES = {
    "Dutch East India Company": "Dutch East Indies",
}


def team_name(code: str) -> str:
    code = code.strip()
    if code in FLAG_NAME_FIXES:
        return FLAG_NAME_FIXES[code]
    key = code.upper()
    if key in TEAM_CODES:
        return TEAM_CODES[key]
    if len(code) > 3 or " " in code or code[:1].islower():
        return strip_wiki(code)
    unknown_codes.add(code)
    return code


def parse_team(field):
    """Extract a country from a team1/team2 field value."""
    if field is None:
        return None
    # Modern flag helpers: {{#invoke:flagg|main|unpre|avar=fb|QAT}} and
    # {{#invoke:flag|fb-rt|MEX}} — the country code is the last real token.
    inv = re.search(r"\{\{\s*#invoke:\s*flagg?\b([^{}]*)\}\}", field,
                    re.IGNORECASE)
    if inv:
        parts = [p.strip() for p in inv.group(1).split("|") if p.strip()]
        drop = {"main", "unpre", "pre", "avar", "name", "size", "b", "fb",
                "fb-rt", "fb-al", "fb-big", "fbw", "rt", "fb-rt2"}
        cand = [p for p in parts if "=" not in p and p.lower() not in drop]
        if cand:
            return team_name(cand[-1])
    m = re.search(r"\{\{\s*fb(?:-rt|-big|w|u|-al)?\s*\|\s*([^|}]+)", field,
                  re.IGNORECASE)
    if m:
        return team_name(m.group(1))
    m = re.search(r"\{\{\s*(?:flagicon|flag|fbicon)\s*\|\s*([^|}]+)", field,
                  re.IGNORECASE)
    if m:
        return team_name(m.group(1))
    plain = strip_wiki(field)
    return plain or None


def parse_date(field):
    if not field:
        return None
    m = re.search(r"\{\{\s*(?:start date|dts)\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})"
                  r"\s*\|\s*(\d{1,2})", field, re.IGNORECASE)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        try:
            return dt.date(y, mo, d).isoformat()
        except ValueError:
            return None
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", strip_wiki(field))
    if m:
        try:
            return dt.datetime.strptime(
                f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %B %Y"
            ).date().isoformat()
        except ValueError:
            return None
    return None


SCORE_RE = re.compile(r"(\d{1,2})\s*[\u2013\-]\s*(\d{1,2})")


def parse_score(field):
    """Return (home, away) ints from a score field, or (None, None)."""
    if not field:
        return None, None
    link = re.search(r"\{\{\s*score\s*link\s*\|([^}]*)\}\}", field,
                     re.IGNORECASE)
    if link:
        for seg in link.group(1).split("|"):
            m = SCORE_RE.fullmatch(seg.strip())
            if m:
                return int(m.group(1)), int(m.group(2))
    m = SCORE_RE.search(field)
    if not m:
        m = SCORE_RE.search(strip_wiki(field))
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def split_template_fields(body: str) -> dict:
    """Split a template body into top-level ``|key=value`` pairs."""
    parts, depth_c, depth_b, buf = [], 0, 0, []
    for ch in body:
        if ch == "{":
            depth_c += 1
        elif ch == "}":
            depth_c -= 1
        elif ch == "[":
            depth_b += 1
        elif ch == "]":
            depth_b -= 1
        if ch == "|" and depth_c == 0 and depth_b == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    out = {}
    for part in parts:
        if "=" in part:
            k, _, v = part.partition("=")
            out[k.strip().lower()] = v.strip()
    return out


def find_match_templates(text: str):
    """Yield (start_index, fields) for each football-box template."""
    for m in re.finditer(r"\{\{\s*(?:#invoke:\s*)?[Ff]ootball box", text):
        i = m.end()
        depth, j = 2, i
        while j < len(text) and depth > 0:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        body = text[i:j - 2]
        body = re.sub(r"^\s*\|?\s*main", "", body)
        yield m.start(), split_template_fields(body)


def heading_at(text: str, pos: int):
    """Nearest preceding top-level (==) section heading before pos."""
    best = None
    for m in re.finditer(r"(?m)^==\s*([^=].*?)\s*==\s*$", text[:pos]):
        title = strip_wiki(m.group(1)).strip()
        if title.lower() not in NON_STAGE_HEADINGS:
            best = title
    return best


def nearest_heading(text: str, pos: int):
    """Immediately preceding heading of any level before pos."""
    best = None
    for m in re.finditer(r"(?m)^=+\s*([^=].*?)\s*=+\s*$", text[:pos]):
        best = strip_wiki(m.group(1)).strip()
    return best


def group_from_title(title: str):
    m = re.search(r"Group\s+([A-Z0-9]+)\b", title)
    if m:
        return f"Group {m.group(1)}"
    return None


def stage_from_title(title: str):
    """Some matches live in dedicated sub-articles whose stage is the title."""
    grp = group_from_title(title)
    if grp:
        return grp
    low = title.lower()
    if low.endswith(" final") and "knockout" not in low:
        return "Final"
    if "third place" in low:
        return "Third place play-off"
    m = re.search(r"round of (\d+)", low)
    if m:
        return f"Round of {m.group(1)}"
    return None


STAGE_ALIASES = {
    "match for third place": "Third place play-off",
    "third place play-off": "Third place play-off",
    "third place match": "Third place play-off",
}


def normalize_stage(stage: str) -> str:
    return STAGE_ALIASES.get(stage.lower(), stage)


def clean_team_label(name):
    """Turn a Wikidata national-team label into a plain country name."""
    if not name:
        return name
    for sep in (" men's national", " women's national", " national"):
        idx = name.find(sep)
        if idx > 0:
            return name[:idx].strip()
    return name.strip()



def wiki_url(title: str) -> str:
    return "https://en.wikipedia.org/wiki/" + urllib.parse.quote(
        title.replace(" ", "_"))


PLACEHOLDER_RE = re.compile(
    r"\b(winner|winners|loser|losers|runner|runners|third[- ]placed?|tbd|"
    r"to be determined|group\s+[a-l]\b|match\s*\d+|nd place|st place|"
    r"th place|play-?off)\b", re.IGNORECASE)


def is_placeholder_team(name: str) -> bool:
    return bool(name) and bool(PLACEHOLDER_RE.search(name))


def _match_from_box(f: dict, stage: str, url: str):
    home = parse_team(f.get("team1"))
    away = parse_team(f.get("team2"))
    if not home or not away:
        return None
    if is_placeholder_team(home) or is_placeholder_team(away):
        return None
    hs, as_ = parse_score(f.get("score"))
    pens = None
    pen_field = f.get("penaltyscore") or f.get("penalties")
    if pen_field:
        ph, pa = parse_score(pen_field)
        if ph is not None:
            pens = f"{ph}\u2013{pa}"
    completed = hs is not None and as_ is not None
    return {
        "date": parse_date(f.get("date")),
        "stage": normalize_stage(stage),
        "home": home,
        "away": away,
        "home_score": hs,
        "away_score": as_,
        "penalties": pens,
        "status": "completed" if completed else "scheduled",
        "wikipedia_url": url,
    }


def parse_matches_from_article(title: str, follow_mains: bool = True) -> list:
    text = get_wikitext(title)
    if not text:
        return []
    year_m = re.search(r"(\d{4})", title)
    year = year_m.group(1) if year_m else ""
    group_stage = stage_from_title(title)
    url = wiki_url(title)
    out = []
    for pos, f in find_match_templates(text):
        stage = group_stage or heading_at(text, pos) or "Match"
        match = _match_from_box(f, stage, url)
        if match:
            out.append(match)

    if not follow_mains or not year:
        return out

    # Some knockout matches have a dedicated article ("Team A v Team B
    # (YYYY FIFA World Cup)") and the stage section only carries {{main|...}}.
    marker = f"({year} FIFA World Cup"
    for m in re.finditer(r"\{\{\s*[Mm]ain\s*\|\s*([^|}]+)", text):
        linked = m.group(1).strip()
        prev = nearest_heading(text, m.start()) or ""
        looks_like_match = bool(re.search(r"\bvs?\b", prev, re.IGNORECASE))
        if marker not in linked and not looks_like_match:
            continue
        stage = group_stage or heading_at(text, m.start()) or "Match"
        for sub in parse_matches_from_article(linked, follow_mains=False):
            sub["stage"] = normalize_stage(stage)
            out.append(sub)
    return out


EXCLUDE_SUBARTICLE = (
    "qualif", "squad", "seed", "broadcast", "marketing", "controvers",
    "stadium", "final draw", "statistics", "officials", "opening ceremony",
    "closing ceremony", "bid", "mascot", "poster", "anthem", "sponsor",
    "referee", "goalscorer", "disciplinary", "prize", "song",
)


def discover_subarticles(main_title: str, year: int) -> list:
    """All main-namespace links from the edition article that look like
    match-bearing sub-articles (group / knockout / final), via the API."""
    prefix = f"{year} FIFA World Cup"
    titles = set()
    plcontinue = None
    while True:
        params = dict(action="query", prop="links", plnamespace=0,
                      pllimit="max", titles=main_title, redirects=1)
        if plcontinue:
            params["plcontinue"] = plcontinue
        data = api_query(**params)
        pages = data.get("query", {}).get("pages", [])
        for page in pages:
            for link in page.get("links", []):
                link_title = link["title"]
                if not link_title.startswith(prefix):
                    continue
                if any(x in link_title.lower() for x in EXCLUDE_SUBARTICLE):
                    continue
                titles.add(link_title)
        cont = data.get("continue", {}).get("plcontinue")
        if not cont:
            break
        plcontinue = cont
    titles.add(main_title)
    return sorted(titles)


def build_tournament(year: int) -> dict:
    main_title = f"{year} FIFA World Cup"
    log(f"[{year}] resolving {main_title}")
    qid = get_wikibase_qid(main_title)
    wd_winner = host = start = end = None
    if qid:
        ent = wd_entity(qid)
        winners = wd_claim_ids(ent, "P1346")
        if winners:
            wd_winner = clean_team_label(wd_label(winners[0]))
        host_labels = [wd_label(h) for h in wd_claim_ids(ent, "P17")]
        host_labels = [h for h in host_labels if h]
        if host_labels:
            host = ", ".join(host_labels)
        start = wd_claim_time(ent, "P580") or wd_claim_time(ent, "P585")
        end = wd_claim_time(ent, "P582")

    matches, seen = [], set()
    for sub in discover_subarticles(main_title, year):
        for match in parse_matches_from_article(sub):
            key = (match["date"], match["home"], match["away"],
                   match["home_score"], match["away_score"])
            if key in seen:
                continue
            seen.add(key)
            matches.append(match)
    matches.sort(key=lambda m: (m["date"] or "9999", m["stage"]))

    # Derive winner / runner-up from the final match when available (keeps the
    # names consistent with the match data, e.g. "West Germany"). Fall back to
    # the Wikidata winner for editions decided by a final round-robin (1950).
    winner, runner_up = wd_winner, None
    final = next((m for m in matches if m["stage"].lower() == "final"
                  and m["status"] == "completed"), None)
    if final:
        home_won = None
        if final["home_score"] != final["away_score"]:
            home_won = final["home_score"] > final["away_score"]
        elif final["penalties"]:
            ph, pa = parse_score(final["penalties"])
            if ph is not None and ph != pa:
                home_won = ph > pa
        if home_won is not None:
            winner = final["home"] if home_won else final["away"]
            runner_up = final["away"] if home_won else final["home"]

    status = "in_progress" if year == IN_PROGRESS_YEAR else "completed"
    log(f"[{year}] host={host} winner={winner} matches={len(matches)}")
    return {
        "year": year,
        "host": host,
        "status": status,
        "start_date": start,
        "end_date": end,
        "winner": winner,
        "runner_up": runner_up,
        "wikipedia_url": wiki_url(main_title),
        "matches": matches,
    }


def main() -> int:
    years = YEARS
    if len(sys.argv) > 1:
        years = [int(a) for a in sys.argv[1:]]
    tournaments = [build_tournament(y) for y in years]
    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": "Wikipedia / Wikidata",
        "tournaments": tournaments,
    }
    out_paths = [
        os.path.join(ROOT, "data", "worldcups.json"),
        os.path.join(ROOT, "_data", "worldcups.json"),
    ]
    for path in out_paths:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        log(f"wrote {path}")

    total = sum(len(t["matches"]) for t in tournaments)
    log(f"\nTotal matches: {total}")
    log("\nValidation (parsed vs expected):")
    for t in tournaments:
        exp = EXPECTED_MATCHES.get(t["year"])
        got = len(t["matches"])
        flag = ""
        if exp is not None and got != exp:
            flag = f"  <-- MISMATCH (expected {exp})"
        elif exp is None:
            flag = "  (in progress)"
        log(f"  {t['year']}: {got}{flag}")
    if unknown_codes:
        log(f"Unknown team codes ({len(unknown_codes)}): "
            f"{', '.join(sorted(unknown_codes))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
