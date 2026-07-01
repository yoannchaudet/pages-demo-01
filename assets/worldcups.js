(function () {
  "use strict";

  var config = window.SITE || {};
  var DATA_URL = config.dataUrl;
  var BASEURL = config.baseurl || "";

  function joinUrl(path) {
    var base = BASEURL.replace(/\/$/, "");
    if (path.charAt(0) !== "/") path = "/" + path;
    return base + path;
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        if (key === "class") node.className = attrs[key];
        else if (key === "html") node.innerHTML = attrs[key];
        else if (key === "text") node.textContent = attrs[key];
        else node.setAttribute(key, attrs[key]);
      });
    }
    (children || []).forEach(function (child) {
      if (child == null) return;
      node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    });
    return node;
  }

  function setStatus(container, message) {
    container.innerHTML = "";
    container.appendChild(el("p", { class: "meta", text: message }));
  }

  function fetchData() {
    return fetch(DATA_URL, { mode: "cors" }).then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    });
  }

  function renderIndex(container, data) {
    var tournaments = (data.tournaments || []).slice().sort(function (a, b) {
      return b.year - a.year;
    });

    var thead = el("thead", null, [
      el("tr", null, [
        el("th", { text: "Year" }),
        el("th", { text: "Host" }),
        el("th", { text: "Winner" }),
        el("th", { text: "Runner-up" }),
        el("th", { class: "num", text: "Matches" })
      ])
    ]);

    var rows = tournaments.map(function (t) {
      var winnerCell;
      if (t.status === "in_progress") {
        winnerCell = el("td", null, [el("span", { class: "badge badge-live", text: "In progress" })]);
      } else {
        winnerCell = el("td", { text: "🏆 " + (t.winner || "—") });
      }

      var yearLink = el("a", { href: joinUrl("/tournaments/" + t.year + "/"), text: String(t.year) });

      return el("tr", null, [
        el("td", null, [yearLink]),
        el("td", { text: t.host || "—" }),
        winnerCell,
        el("td", { text: t.runner_up || "—" }),
        el("td", { class: "num", text: String((t.matches || []).length) })
      ]);
    });

    var table = el("table", { class: "tournaments" }, [thead, el("tbody", null, rows)]);

    container.innerHTML = "";
    container.appendChild(table);
    container.appendChild(
      el("p", {
        class: "meta",
        text: "Data generated " + (data.generated_at || "—") + " · source: " + (data.source || "—") + "."
      })
    );
  }

  function renderTournament(container, data, year) {
    var tournament = (data.tournaments || []).filter(function (t) {
      return String(t.year) === String(year);
    })[0];

    container.innerHTML = "";

    if (!tournament) {
      container.appendChild(el("p", { text: "No data found for " + year + "." }));
      return;
    }

    container.appendChild(
      el("p", { class: "back" }, [el("a", { href: joinUrl("/"), text: "← All tournaments" })])
    );

    container.appendChild(el("h1", { text: tournament.year + " FIFA World Cup" }));

    var facts = [];
    facts.push(el("li", { html: "<strong>Host:</strong> " }, [document.createTextNode(tournament.host || "—")]));
    if (tournament.start_date) {
      var dates = tournament.start_date + (tournament.end_date ? " → " + tournament.end_date : "");
      facts.push(el("li", { html: "<strong>Dates:</strong> " }, [document.createTextNode(dates)]));
    }
    if (tournament.status === "in_progress") {
      facts.push(
        el("li", null, [el("span", { class: "badge badge-live", text: "In progress" }), document.createTextNode(" — partial results")])
      );
    } else {
      facts.push(el("li", { html: "<strong>Winner:</strong> 🏆 " }, [document.createTextNode(tournament.winner || "—")]));
      facts.push(el("li", { html: "<strong>Runner-up:</strong> " }, [document.createTextNode(tournament.runner_up || "—")]));
    }
    if (tournament.wikipedia_url) {
      facts.push(el("li", null, [el("a", { href: tournament.wikipedia_url, text: "Wikipedia ↗" })]));
    }
    container.appendChild(el("ul", { class: "facts" }, facts));

    var matches = tournament.matches || [];
    container.appendChild(
      el("h2", null, [document.createTextNode("Matches "), el("span", { class: "count", text: "(" + matches.length + ")" })])
    );

    var thead = el("thead", null, [
      el("tr", null, [
        el("th", { text: "Date" }),
        el("th", { text: "Stage" }),
        el("th", { class: "home", text: "Home" }),
        el("th", { class: "score", text: "Score" }),
        el("th", { class: "away", text: "Away" }),
        el("th")
      ])
    ]);

    var rows = matches.map(function (m) {
      var scoreCell = el("td", { class: "score" });
      if (m.status === "completed") {
        scoreCell.appendChild(el("strong", { text: m.home_score + "–" + m.away_score }));
        if (m.penalties) {
          scoreCell.appendChild(el("br"));
          scoreCell.appendChild(el("span", { class: "pens", text: "(" + m.penalties + " pen.)" }));
        }
      } else {
        scoreCell.appendChild(el("span", { class: "tbd", text: "—" }));
      }

      var linkCell = el("td", { class: "link" });
      if (m.wikipedia_url) {
        linkCell.appendChild(el("a", { href: m.wikipedia_url, text: "↗" }));
      }

      return el("tr", null, [
        el("td", { class: "date", text: m.date || "—" }),
        el("td", { class: "stage", text: m.stage }),
        el("td", { class: "home", text: m.home }),
        scoreCell,
        el("td", { class: "away", text: m.away }),
        linkCell
      ]);
    });

    container.appendChild(el("table", { class: "matches" }, [thead, el("tbody", null, rows)]));
  }

  function init() {
    var indexApp = document.getElementById("tournaments-app");
    var tournamentApp = document.getElementById("tournament-app");
    var container = indexApp || tournamentApp;
    if (!container) return;

    if (!DATA_URL) {
      setStatus(container, "No data URL configured.");
      return;
    }

    setStatus(container, "Loading…");

    fetchData()
      .then(function (data) {
        if (indexApp) renderIndex(indexApp, data);
        else renderTournament(tournamentApp, data, tournamentApp.getAttribute("data-year"));
      })
      .catch(function (err) {
        setStatus(container, "Failed to load data: " + err.message);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
