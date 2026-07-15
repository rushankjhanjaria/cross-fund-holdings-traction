const REPORT = __DATA__;
    let activeMonthId = REPORT.defaultMonthId || (REPORT.months[0] && REPORT.months[0].id);

    let filter = "all";
    let query = "";
    let searchDebounce = null;

    function monthData() {
      return REPORT.months.find((m) => m.id === activeMonthId) || REPORT.months[0];
    }
    function STOCKS() { return monthData().stocks || []; }
    function META() { return monthData().meta || {}; }

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

    function passesFilter(s) {
      if (filter === "added") return hasAdd(s) && !hasReduce(s);
      if (filter === "reduced") return hasReduce(s) && !hasAdd(s);
      if (filter === "new") return hasNew(s);
      if (filter === "mixed") return isMixed(s);
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
      if (!low && !high && !current) {
        return "";
      }
      const midNote = s.entryMid && s.pctVsMid
        ? `<span class="metric"><label>vs entry mid</label><strong>${Number(s.pctVsMid) >= 0 ? "+" : ""}${Number(s.pctVsMid).toFixed(1)}%</strong></span>`
        : "";
      return `<div class="price-row">
        <span class="metric"><label>Month low</label><strong>${low || "—"}</strong></span>
        <span class="metric"><label>Month high</label><strong>${high || "—"}</strong></span>
        <span class="metric"><label>Current price</label><strong>${current || "—"}</strong></span>
        ${midNote}
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
      return `<li class="stock-card">
        <div class="stock-head">
          <h2><span style="color:var(--ink-600);font-weight:500;margin-right:0.35rem">${rank}.</span>${s.stockName} ${ticker}</h2>
          ${dir}${fc}${sc}
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
      }

      updatePriceBanner(all);

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
      ["all", "All"],
      ["added", "Added only"],
      ["reduced", "Reduced only"],
      ["new", "New only"],
      ["mixed", "Mixed"],
    ];
    const filtersEl = document.getElementById("filters");
    filterDefs.forEach(([id, label]) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "pill-btn";
      b.textContent = label;
      b.dataset.filter = id;
      b.setAttribute("aria-pressed", id === "all" ? "true" : "false");
      if (id === "all") b.classList.add("active");
      b.onclick = () => applyFilter(id);
      filtersEl.appendChild(b);
    });

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
