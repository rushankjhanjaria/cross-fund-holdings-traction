const REPORT = __DATA__;
    let activeMonthId = REPORT.defaultMonthId || (REPORT.months[0] && REPORT.months[0].id);

    let filter = "all";
    let query = "";
    let searchDebounce = null;
    const LS_WATCH = "mf-screener-watchlist";

    function monthData() {
      return REPORT.months.find((m) => m.id === activeMonthId) || REPORT.months[0];
    }
    function STOCKS() { return monthData().stocks || []; }
    function META() { return monthData().meta || {}; }
    function activeInsights() {
      const byMonth = REPORT.insightsByMonth;
      if (byMonth && activeMonthId && Array.isArray(byMonth[activeMonthId])) {
        return byMonth[activeMonthId];
      }
      return REPORT.insights || [];
    }
    function activeTopTraction() {
      const byMonth = REPORT.topTractionByMonth;
      if (byMonth && activeMonthId && Array.isArray(byMonth[activeMonthId])) {
        return byMonth[activeMonthId];
      }
      return REPORT.topTraction || [];
    }

    function fileWatchKeys() {
      const items = (REPORT.watchlist && REPORT.watchlist.items) || [];
      return new Set(items.map((i) => i.stockKey).filter(Boolean));
    }

    function loadLocalWatch() {
      try {
        const raw = localStorage.getItem(LS_WATCH);
        if (!raw) return {};
        const data = JSON.parse(raw);
        return data && typeof data === "object" ? data : {};
      } catch (e) {
        return {};
      }
    }

    function saveLocalWatch(map) {
      localStorage.setItem(LS_WATCH, JSON.stringify(map));
    }

    function effectiveWatchKeys() {
      const keys = fileWatchKeys();
      const local = loadLocalWatch();
      Object.keys(local).forEach((k) => {
        if (local[k]) keys.add(k);
        else keys.delete(k);
      });
      return keys;
    }

    function isWatched(s) {
      const key = s.stockKey || "";
      return key && effectiveWatchKeys().has(key);
    }

    function togglePin(stockKey) {
      if (!stockKey) return;
      const local = loadLocalWatch();
      const fileHas = fileWatchKeys().has(stockKey);
      const currently = effectiveWatchKeys().has(stockKey);
      if (currently) {
        if (fileHas) local[stockKey] = false;
        else delete local[stockKey];
      } else {
        local[stockKey] = true;
      }
      saveLocalWatch(local);
      render();
    }

    function hasAdd(s) { return s.addCount > 0; }
    function hasReduce(s) { return s.reduceCount > 0; }
    function hasHold(s) { return (s.holdCount || 0) > 0; }
    function hasNew(s) { return s.newCount > 0; }

    function isMixed(s) {
      if (typeof s.mixedSignal === "boolean") return s.mixedSignal;
      let kinds = 0;
      if (hasAdd(s)) kinds++;
      if (hasReduce(s)) kinds++;
      if (hasHold(s)) kinds++;
      return kinds >= 2;
    }

    function persistStatus(s) {
      return (s.persistence && s.persistence.status) || "";
    }

    function passesFilter(s) {
      if (filter === "added") return hasAdd(s) && !hasReduce(s);
      if (filter === "reduced") return hasReduce(s) && !hasAdd(s);
      if (filter === "new") return hasNew(s);
      if (filter === "mixed") return isMixed(s);
      if (filter === "still_adding") return persistStatus(s) === "still_adding";
      if (filter === "reversed") return persistStatus(s) === "reversed";
      if (filter === "new_this_month") return persistStatus(s) === "new_this_month";
      if (filter === "watchlist") return isWatched(s);
      return true;
    }

    function passesSearch(s) {
      if (!query) return true;
      const q = query.toLowerCase();
      return s.stockName.toLowerCase().includes(q) || (s.nse || "").toLowerCase().includes(q);
    }

    /* BEGIN SORT_UI — delete through END SORT_UI (and #sorts + .sorts CSS) to drop sort controls */
    const SORT_MODES = [
      ["score", "Traction score"],
      ["fund_breadth", "Most funds"],
    ];
    let sortMode = "score";

    function fundCount(s) {
      if (typeof s.fundCount === "number") return s.fundCount;
      return (s.addCount || 0) + (s.reduceCount || 0) + (s.holdCount || 0);
    }

    function compareStocksForSort(a, b) {
      if (sortMode === "fund_breadth") {
        const diff = fundCount(b) - fundCount(a);
        if (diff !== 0) return diff;
      }
      const scoreDiff = (b.score || 0) - (a.score || 0);
      if (scoreDiff !== 0) return scoreDiff;
      return a.stockName.localeCompare(b.stockName);
    }

    function initSortUi() {
      const el = document.getElementById("sorts");
      if (!el || !SORT_MODES.length) return;
      const label = document.createElement("span");
      label.className = "sort-label";
      label.textContent = "Sort:";
      el.appendChild(label);
      SORT_MODES.forEach(([id, text]) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "pill-btn";
        b.textContent = text;
        b.dataset.sort = id;
        b.setAttribute("aria-pressed", id === sortMode ? "true" : "false");
        if (id === sortMode) b.classList.add("active");
        b.onclick = () => {
          sortMode = id;
          el.querySelectorAll("button").forEach((x) => {
            x.classList.toggle("active", x.dataset.sort === id);
            x.setAttribute("aria-pressed", x.dataset.sort === id ? "true" : "false");
          });
          render();
        };
        el.appendChild(b);
      });
    }
    /* END SORT_UI */

    function fmtPrice(v) {
      if (!v) return "";
      const n = Number(v);
      return Number.isNaN(n) ? v : (n >= 100 ? n.toFixed(1) : n.toFixed(2));
    }

    function persistLabel(status) {
      const map = {
        still_adding: "Still adding",
        still_reducing: "Still reducing",
        reversed: "Reversed",
        new_this_month: "New this month",
        continued_mixed: "Continued mixed",
        unknown: "",
      };
      return map[status] || "";
    }

    function renderFundList(lines, side) {
      const labels = {
        adds: "adding",
        reduces: "reducing",
        holds: "with unchanged shares",
      };
      if (!lines.length) {
        return `<p class="empty">No funds ${labels[side] || side}</p>`;
      }
      return "<ul>" + lines.map((f) => {
        const aum = f.pctAum
          ? `<span class="aum">${f.pctAum} AUM</span>`
          : "";
        let act;
        if (side === "holds" || f.activity === "hold") {
          act = `<span class="pct">shares ${f.sharePctChange || "0%"}</span>`;
        } else if (f.activity === "new") {
          act = '<span class="act-new">new</span>';
        } else {
          act = `<span class="pct">shares ${f.sharePctChange || "—"}</span>`;
        }
        return `<li><strong>${f.fundName}</strong> ${aum} ${act}</li>`;
      }).join("") + "</ul>";
    }

    function renderPriceBlock(s) {
      const low = fmtPrice(s.monthLow);
      const high = fmtPrice(s.monthHigh);
      const current = fmtPrice(s.closeLatest);
      const sma = fmtPrice(s.sma30);
      if (!low && !high && !current && !sma) {
        return "";
      }
      const pctRaw = s.pctVsSma != null && s.pctVsSma !== "" ? s.pctVsSma : s.pctVsMid;
      const smaNote = sma && pctRaw !== "" && pctRaw != null
        ? `<span class="metric"><label>vs 30d SMA</label><strong>${Number(pctRaw) >= 0 ? "+" : ""}${Number(pctRaw).toFixed(1)}%</strong></span>`
        : "";
      return `<div class="price-row">
        <span class="metric"><label>Month low</label><strong>${low || "—"}</strong></span>
        <span class="metric"><label>Month high</label><strong>${high || "—"}</strong></span>
        <span class="metric"><label>30d SMA</label><strong>${sma || "—"}</strong></span>
        <span class="metric"><label>Current price</label><strong>${current || "—"}</strong></span>
        ${smaNote}
      </div>`;
    }

    function screenerCompanyUrl(ticker) {
      const sym = (ticker || "").trim();
      if (!sym) return "";
      return `https://www.screener.in/company/${encodeURIComponent(sym)}/consolidated/`;
    }

    function renderCard(s, rank) {
      const price = renderPriceBlock(s);
      const ticker = s.nse
        ? `<a class="tag" href="${screenerCompanyUrl(s.nse)}" target="_blank" rel="noopener noreferrer" title="Open on Screener.in (consolidated)">${s.nse}</a>`
        : "";
      const dir = s.stockDirection
        ? `<span class="dir" title="Composite score direction (not the Mixed filter)">score · ${s.stockDirection}</span>`
        : "";
      const sc = s.score ? `<span class="score">score ${s.score}</span>` : "";
      const fc = fundCount(s)
        ? `<span class="fund-count" title="Funds in this report">${fundCount(s)} funds</span>`
        : "";
      const pStatus = persistStatus(s);
      const pLabel = persistLabel(pStatus);
      const badge = pLabel
        ? `<span class="persist-badge ${pStatus}">${pLabel}</span>`
        : "";
      const watched = isWatched(s);
      const pin = s.stockKey
        ? `<button type="button" class="pin-btn${watched ? " pinned" : ""}" data-pin="${s.stockKey}" title="${watched ? "Unpin" : "Pin to watchlist"}" aria-pressed="${watched ? "true" : "false"}">${watched ? "★" : "☆"}</button>`
        : "";
      let delta = "";
      if (watched && s.persistence && s.persistence.priorMonthId && pStatus && pStatus !== "unknown") {
        const priorFc = s.persistence.priorFundCount || 0;
        delta = `<p class="persist-delta">prior ${priorFc} funds → ${fundCount(s)} · ${pLabel.toLowerCase()}</p>`;
      }
      return `<li class="stock-card" data-stock-key="${s.stockKey || ""}">
        <div class="stock-head">
          <h2><span style="color:var(--ink-600);font-weight:500;margin-right:0.35rem">${rank}.</span>${s.stockName} ${ticker}</h2>
          ${pin}${badge}${dir}${fc}${sc}
          ${delta}
        </div>
        ${price}
        <div class="cols">
          <div class="col adds"><h3>Funds adding</h3>${renderFundList(s.adds, "adds")}</div>
          <div class="col reduces"><h3>Funds reducing</h3>${renderFundList(s.reduces, "reduces")}</div>
          <div class="col holds"><h3>Funds unchanged</h3>${renderFundList(s.holds || [], "holds")}</div>
        </div>
      </li>`;
    }

    function visibleStocks() {
      const list = STOCKS().filter((s) => passesFilter(s) && passesSearch(s));
      if (typeof compareStocksForSort === "function") {
        return list.slice().sort(compareStocksForSort);
      }
      return list;
    }

    function renderListEmpty() {
      return `<div class="list-empty">
        <p>No stocks match this filter or search.</p>
        <button type="button" class="pill-btn" data-clear-search>Clear search</button>
        <button type="button" class="pill-btn" data-filter-all>Show all</button>
      </div>`;
    }

    function updatePriceBanner(all) {
      const el = document.getElementById("price-banner");
      if (!el) return;
      const anyPrice = all.some((s) => s.closeLatest || s.monthLow || s.monthHigh);
      if (anyPrice) {
        el.hidden = true;
        el.textContent = "";
      } else {
        el.hidden = false;
        el.textContent = "Price bands not loaded for this month (run screener with --enrich-prices).";
      }
    }

    function applyFilter(id) {
      filter = id;
      const filtersEl = document.getElementById("filters");
      filtersEl.querySelectorAll("button").forEach((x) => {
        x.classList.toggle("active", x.dataset.filter === id);
        x.setAttribute("aria-pressed", x.dataset.filter === id ? "true" : "false");
      });
      render();
    }

    function focusStockKey(stockKey) {
      if (!stockKey) return;
      query = "";
      const search = document.getElementById("search");
      if (search) search.value = "";
      applyFilter("all");
      const stock = STOCKS().find((s) => s.stockKey === stockKey);
      if (stock && stock.stockName) {
        query = stock.stockName;
        if (search) search.value = stock.stockName;
      }
      render();
      const card = document.querySelector(`[data-stock-key="${CSS.escape(stockKey)}"]`);
      if (card) card.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    function setInsightsCollapsed(collapsed) {
      const panel = document.getElementById("insights-panel");
      const toggle = document.getElementById("insights-toggle");
      const chevron = document.getElementById("insights-chevron");
      if (!panel || !toggle) return;
      panel.classList.toggle("is-collapsed", collapsed);
      toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
      if (chevron) chevron.textContent = collapsed ? "▶" : "▼";
      try {
        localStorage.setItem("mf-screener-insights-collapsed", collapsed ? "1" : "0");
      } catch (e) { /* ignore */ }
    }

    function initInsightsToggle() {
      const toggle = document.getElementById("insights-toggle");
      if (!toggle || toggle.dataset.bound) return;
      toggle.dataset.bound = "1";
      let collapsed = false;
      try {
        collapsed = localStorage.getItem("mf-screener-insights-collapsed") === "1";
      } catch (e) { /* ignore */ }
      setInsightsCollapsed(collapsed);
      toggle.onclick = () => {
        const panel = document.getElementById("insights-panel");
        setInsightsCollapsed(!(panel && panel.classList.contains("is-collapsed")));
      };
    }

    function renderInsights() {
      const panel = document.getElementById("insights-panel");
      const sectionsEl = document.getElementById("insights-sections");
      const topSection = document.getElementById("top-traction-section");
      const topList = document.getElementById("top-traction-list");
      if (!panel || !sectionsEl || !topSection || !topList) return;
      const insights = activeInsights();
      const topTraction = activeTopTraction();
      const titleEl = panel.querySelector(".insights-title");
      const monthLabel = (monthData() && monthData().label) || activeMonthId || "";
      if (titleEl) {
        titleEl.textContent = monthLabel ? `Insights · ${monthLabel}` : "Insights";
      }
      if (!insights.length && !topTraction.length) {
        panel.hidden = true;
        sectionsEl.innerHTML = "";
        topList.innerHTML = "";
        topSection.hidden = true;
        return;
      }
      panel.hidden = false;
      initInsightsToggle();

      if (topTraction.length) {
        topSection.hidden = false;
        topList.innerHTML = topTraction.map((row) => {
          const key = row.stockKey || "";
          const name = row.name || key;
          const pct = row.pctVsSma || row.pctVsMid;
          const pctBit = (pct !== "" && pct != null)
            ? ` · ${Number(pct) >= 0 ? "+" : ""}${Number(pct).toFixed(1)}% vs SMA`
            : "";
          const delta = row.fundDelta != null ? Number(row.fundDelta) : 0;
          const deltaBit = delta !== 0 ? ` · funds ${delta > 0 ? "+" : ""}${delta}` : "";
          return `<li>
            <span class="tt-rank">${row.rank || ""}</span>
            <button type="button" class="insight-link" data-focus-key="${key}">${name}</button>
            <span class="tt-meta">score ${Number(row.score || 0).toFixed(0)} · ${row.fundCount || 0} funds${deltaBit}${pctBit}</span>
          </li>`;
        }).join("");
      } else {
        topSection.hidden = true;
        topList.innerHTML = "";
      }

      const SECTION_ORDER = [
        { id: "still_early", title: "Still early" },
        { id: "exit_pressure", title: "Exit pressure" },
        { id: "debate", title: "Debate" },
        { id: "watchlist_delta", title: "Watchlist" },
      ];
      const bySection = {};
      insights.forEach((ins) => {
        const sec = ins.section || "still_early";
        (bySection[sec] = bySection[sec] || []).push(ins);
      });
      sectionsEl.innerHTML = SECTION_ORDER.map(({ id, title }) => {
        const items = bySection[id] || [];
        if (!items.length) return "";
        const lis = items.map((ins) => {
          const keys = ins.stockKeys || [];
          const links = keys.map((k) =>
            `<button type="button" class="insight-link" data-focus-key="${k}">${k}</button>`
          ).join(" · ");
          const action = ins.action || "monitor";
          return `<li>
            <span class="insight-action action-${action}">${action}</span>
            <strong>${ins.headline || ""}</strong>
            <div>${ins.body || ""}</div>
            ${links ? `<div>${links}</div>` : ""}
          </li>`;
        }).join("");
        return `<div class="insights-section">
          <h3 class="insights-section-title">${title}</h3>
          <ul class="insights-list">${lis}</ul>
        </div>`;
      }).join("");

      panel.querySelectorAll("[data-focus-key]").forEach((btn) => {
        btn.onclick = () => focusStockKey(btn.dataset.focusKey);
      });
    }

    function downloadWatchlistJson() {
      const fileItems = (REPORT.watchlist && REPORT.watchlist.items) || [];
      const local = loadLocalWatch();
      const byKey = {};
      fileItems.forEach((i) => {
        if (i.stockKey) byKey[i.stockKey] = { ...i };
      });
      Object.keys(local).forEach((k) => {
        if (local[k]) {
          const stock = STOCKS().find((s) => s.stockKey === k);
          byKey[k] = byKey[k] || {
            stockKey: k,
            name: stock ? stock.stockName : "",
            nse: stock ? stock.nse : "",
            pinnedAt: activeMonthId,
            source: "manual",
          };
        } else {
          delete byKey[k];
        }
      });
      const payload = { version: 1, items: Object.values(byKey) };
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "watchlist.json";
      a.click();
      URL.revokeObjectURL(a.href);
    }

    function render() {
      const all = STOCKS();
      const vis = visibleStocks();
      document.getElementById("countline").textContent =
        `Showing ${vis.length} of ${all.length} stocks`;
      const listEl = document.getElementById("list");
      if (!vis.length) {
        listEl.innerHTML = renderListEmpty();
        listEl.querySelector("[data-clear-search]")?.addEventListener("click", () => {
          query = "";
          document.getElementById("search").value = "";
          render();
        });
        listEl.querySelector("[data-filter-all]")?.addEventListener("click", () => applyFilter("all"));
      } else {
        listEl.innerHTML = vis.map((s, i) => renderCard(s, i + 1)).join("");
        listEl.querySelectorAll("[data-pin]").forEach((btn) => {
          btn.onclick = () => togglePin(btn.dataset.pin);
        });
      }

      updatePriceBanner(all);
      renderInsights();

      const withAdd = all.filter(hasAdd).length;
      const withReduce = all.filter(hasReduce).length;
      const withNew = all.filter(hasNew).length;
      const withMixed = all.filter(isMixed).length;
      document.getElementById("stats").innerHTML =
        `<span><strong>${all.length}</strong> stocks</span>` +
        `<span class="stat-chip" data-stat-filter="added"><strong>${withAdd}</strong> with adds</span>` +
        `<span class="stat-chip" data-stat-filter="reduced"><strong>${withReduce}</strong> with reduces</span>` +
        `<span class="stat-chip" data-stat-filter="new"><strong>${withNew}</strong> with new entries</span>` +
        `<span class="stat-chip" data-stat-filter="mixed"><strong>${withMixed}</strong> mixed</span>`;

      document.getElementById("stats").querySelectorAll("[data-stat-filter]").forEach((chip) => {
        chip.onclick = () => applyFilter(chip.dataset.statFilter);
      });

      const meta = META();
      document.getElementById("eyebrow").textContent = "Mutual fund holdings · " + (monthData().label || activeMonthId);
      let sub = meta.folder
        ? `Source: ${meta.folder}`
        : "Actionable holdings for selected month";
      if (meta.rankMode) sub += ` · rank: ${meta.rankMode}`;
      document.getElementById("subtitle").textContent = sub;
    }

    const monthTabsEl = document.getElementById("month-tabs");
    REPORT.months.forEach((m) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = m.label || m.id;
      b.dataset.monthId = m.id;
      b.setAttribute("aria-pressed", m.id === activeMonthId ? "true" : "false");
      if (m.id === activeMonthId) b.classList.add("active");
      b.onclick = () => {
        activeMonthId = m.id;
        monthTabsEl.querySelectorAll("button").forEach((x) => {
          x.classList.toggle("active", x.dataset.monthId === m.id);
          x.setAttribute("aria-pressed", x.dataset.monthId === m.id ? "true" : "false");
        });
        render();
      };
      monthTabsEl.appendChild(b);
    });

    const filterDefs = [
      ["all", "All", "All actionable stocks this month"],
      ["added", "Added only", "Funds added shares; none reduced"],
      ["reduced", "Reduced only", "Funds trimmed/closed; none added"],
      ["new", "New only", "At least one new fund position this month"],
      ["mixed", "Mixed", "Funds disagree (add + reduce and/or hold)"],
      ["still_adding", "Still adding", "Also added last month — persistence, not a one-off"],
      ["reversed", "Reversed", "Direction flipped vs prior month (add↔reduce)"],
      ["new_this_month", "New this month", "Not in the prior month’s traction report"],
      ["watchlist", "Watchlist", "Names you pinned (★)"],
    ];
    const filtersEl = document.getElementById("filters");
    filterDefs.forEach(([id, label, title]) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "pill-btn";
      b.textContent = label;
      b.title = title;
      b.dataset.filter = id;
      b.setAttribute("aria-pressed", id === "all" ? "true" : "false");
      if (id === "all") b.classList.add("active");
      b.onclick = () => applyFilter(id);
      filtersEl.appendChild(b);
    });

    const wlActions = document.createElement("div");
    wlActions.className = "wl-actions";
    const dl = document.createElement("button");
    dl.type = "button";
    dl.className = "pill-btn";
    dl.textContent = "Download watchlist.json";
    dl.onclick = downloadWatchlistJson;
    wlActions.appendChild(dl);
    filtersEl.parentNode.insertBefore(wlActions, filtersEl.nextSibling);

    if (typeof initSortUi === "function") initSortUi();

    document.getElementById("search").oninput = (e) => {
      const val = e.target.value.trim();
      if (searchDebounce) clearTimeout(searchDebounce);
      searchDebounce = setTimeout(() => {
        query = val;
        render();
      }, 200);
    };

    render();
