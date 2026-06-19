(function () {
  "use strict";
  const ctx = window.RETREAT_DASHBOARD_CTX;
  if (!ctx) return;

  const statusEl = document.getElementById("dashboardStatus");
  const attendTotalEl = document.getElementById("attendTotal");
  const groupGrid = document.getElementById("groupGrid");
  const divBody = document.querySelector("#divisionTable tbody");
  const generatedAtEl = document.getElementById("dashGeneratedAt");
  const btnRefresh = document.getElementById("btnRefresh");
  const innerTabs = document.getElementById("dashboardInnerTabs");
  const panelStats = document.getElementById("dashboardPanelStats");
  const panelBoard = document.getElementById("dashboardPanelBoard");
  const summaryCards = document.getElementById("dashSummaryCards");
  const boardHost = document.getElementById("retreatGroupBoard");
  const boardTotalEl = document.getElementById("groupBoardTotal");
  const boardRegionFilter = document.getElementById("boardRegionFilter");

  let activeTab = "stats";
  let lastBoardGroups = [];
  let lastBoardGrand = {};
  // 합계 값은 상단 요약 알약([data-total-*])에 표시되므로 모두 갱신한다.
  const totalEls = {
    pending: document.querySelectorAll("[data-total-pending]"),
    in: document.querySelectorAll("[data-total-in]"),
    out: document.querySelectorAll("[data-total-out]"),
    attended: document.querySelectorAll("[data-total-attended]"),
  };

  const REFRESH_MS = 60000;

  async function load() {
    if (statusEl) statusEl.textContent = "불러오는 중…";
    try {
      const r = await fetch(ctx.apiDashboard, { credentials: "same-origin" });
      if (!r.ok) throw new Error(await r.text());
      const data = await r.json();
      renderSummary(data.summary || {});
      renderAttendTotal(data.grand_total || {});
      renderGroups(data.by_group || []);
      renderDivisions(data.by_division || [], data.grand_total || {});
      if (generatedAtEl) {
        generatedAtEl.textContent = data.generated_at
          ? `· ${formatStamp(data.generated_at)} 기준`
          : "";
      }
      if (statusEl) statusEl.textContent = "";
    } catch (e) {
      if (statusEl) statusEl.textContent = "로드 실패";
      console.error(e);
    }
  }

  function renderAttendTotal(grand) {
    if (attendTotalEl) attendTotalEl.textContent = grand.checked_in ?? 0;
  }

  function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  // 상단 요약 카드: 실시간 참석(입실/총참석, 전체 대비 %)·미배정·차량 지원
  function renderSummary(s) {
    setText("sumAttendIn", s.checked_in ?? 0);
    setText("sumAttendTotal", s.attended ?? 0);
    setText("sumAttendPct", `${s.attend_percent ?? 0}%`);
    setText("sumLodging", s.lodging_unassigned ?? 0);
    setText("sumCarToday", s.car_today ?? 0);
  }

  function buildAttRow(row) {
    const region = escapeHtml((row.region || "").trim());
    const division = escapeHtml((row.division || "").trim());
    const regionCell = division
      ? `${region}<span class="jcc-retreat-divSub">${division}</span>`
      : region;
    const count = row.checked_in ?? 0;
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${escapeHtml(row.name)}</td>` +
      `<td class="jcc-retreat-divRegionCell">${regionCell}</td>` +
      `<td>${count}</td>`;
    return tr;
  }

  function buildAttTable(rows) {
    const table = document.createElement("table");
    table.className = "jcc-table jcc-retreat-attTable";
    table.innerHTML =
      "<thead><tr><th>조</th><th>지역·부서</th><th>참석</th></tr></thead>";
    const tb = document.createElement("tbody");
    rows.forEach((row) => tb.appendChild(buildAttRow(row)));
    table.appendChild(tb);
    return table;
  }

  function renderGroups(rows) {
    if (!groupGrid) return;
    groupGrid.innerHTML = "";
    // 지역·부서별 인원체크 표와 동일한 테이블 UI (순서: 조 · 지역·부서 · 참석).
    // PC: 2열 그리드(두 개의 표), 모바일: 두 번째 표 헤더를 숨겨 단일 연속 표.
    const grid = document.createElement("div");
    grid.className = "jcc-retreat-attGrid";
    const mid = Math.ceil(rows.length / 2);
    grid.appendChild(buildAttTable(rows.slice(0, mid)));
    if (rows.length > mid) {
      grid.appendChild(buildAttTable(rows.slice(mid)));
    }
    groupGrid.appendChild(grid);
  }

  function renderDivisions(rows, grand) {
    if (!divBody) return;
    divBody.innerHTML = "";
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      const region = escapeHtml((row.region || "").trim());
      const division = escapeHtml((row.division || "").trim());
      const regionCell = division
        ? `${region}<span class="jcc-retreat-divSub">${division}</span>`
        : region;
      tr.innerHTML = `
        <td class="jcc-retreat-divRegionCell">${regionCell}</td>
        <td>${escapeHtml(row.group_range)}</td>
        <td>${row.pending}</td>
        <td>${row.checked_in}</td>
        <td>${row.checked_out}</td>
        <td>${row.attended}</td>`;
      divBody.appendChild(tr);
    });
    const setTotal = (nodes, val) => {
      nodes.forEach((n) => {
        n.textContent = val;
      });
    };
    setTotal(totalEls.pending, grand.pending ?? 0);
    setTotal(totalEls.in, grand.checked_in ?? 0);
    setTotal(totalEls.out, grand.checked_out ?? 0);
    setTotal(totalEls.attended, grand.attended ?? 0);
  }

  async function loadBoard() {
    if (!boardHost) return;
    if (statusEl) statusEl.textContent = "불러오는 중…";
    try {
      const r = await fetch(ctx.apiGroupBoard, { credentials: "same-origin" });
      if (!r.ok) throw new Error(await r.text());
      const data = await r.json();
      lastBoardGroups = data.groups || [];
      lastBoardGrand = data.grand_total || {};
      populateRegionFilter(lastBoardGroups);
      renderGroupBoard(lastBoardGroups, lastBoardGrand);
      if (generatedAtEl) {
        generatedAtEl.textContent = data.generated_at
          ? `· ${formatStamp(data.generated_at)} 기준`
          : "";
      }
      if (statusEl) statusEl.textContent = "";
    } catch (e) {
      if (statusEl) statusEl.textContent = "로드 실패";
      console.error(e);
    }
  }

  function regionLabel(group) {
    return (group.region || "").trim() || "(지역 미지정)";
  }

  function regionOrderFromGroups(groups) {
    const seen = new Set();
    const order = [];
    groups.forEach((g) => {
      const label = regionLabel(g);
      if (!seen.has(label)) {
        seen.add(label);
        order.push(label);
      }
    });
    return order;
  }

  function groupsByRegion(groups) {
    const map = new Map();
    groups.forEach((g) => {
      const label = regionLabel(g);
      if (!map.has(label)) map.set(label, []);
      map.get(label).push(g);
    });
    return map;
  }

  function divisionLabel(group) {
    return (group.division || "").trim() || "(부서 미지정)";
  }

  // 부서 등장 순서(백엔드 division__sort_order)를 유지하며 부서별로 묶는다.
  function groupsByDivision(regionGroups) {
    const map = new Map();
    regionGroups.forEach((g) => {
      const label = divisionLabel(g);
      if (!map.has(label)) map.set(label, []);
      map.get(label).push(g);
    });
    return map;
  }

  // 조 이름에서 앞쪽 숫자를 뽑아 1조부터 오름차순 정렬한다.
  function groupNumber(name) {
    const m = String(name == null ? "" : name).match(/\d+/);
    return m ? parseInt(m[0], 10) : Number.MAX_SAFE_INTEGER;
  }

  function sortGroupsByNumber(groups) {
    return groups.slice().sort((a, b) => {
      const na = groupNumber(a.name);
      const nb = groupNumber(b.name);
      if (na !== nb) return na - nb;
      return String(a.name || "").localeCompare(String(b.name || ""), "ko");
    });
  }

  // 부서 접힘 상태 (region + division 키). 재렌더링·새로고침에도 유지.
  const collapsedDivisions = new Set();
  function divisionKey(region, division) {
    return region + "\u0000" + division;
  }

  function sumRegionTotals(regionGroups) {
    return regionGroups.reduce(
      (acc, g) => {
        acc.attended += g.attended ?? 0;
        acc.pending += g.pending ?? 0;
        return acc;
      },
      { attended: 0, pending: 0 }
    );
  }

  function populateRegionFilter(groups) {
    if (!boardRegionFilter) return;
    const prev = boardRegionFilter.value;
    const regions = regionOrderFromGroups(groups);
    boardRegionFilter.innerHTML = '<option value="">전체</option>';
    regions.forEach((name) => {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      boardRegionFilter.appendChild(opt);
    });
    if (prev && regions.includes(prev)) {
      boardRegionFilter.value = prev;
    }
    if (window.JccCustomSelect) {
      window.JccCustomSelect.refresh(boardRegionFilter.closest(".jcc-cselect"));
    }
  }

  function createGroupColumn(g) {
    const col = document.createElement("div");
    col.className = "jcc-excel-col";
    const head = document.createElement("div");
    head.className = "jcc-excel-col-head";
    head.textContent = g.name || "조";
    const sub = document.createElement("div");
    sub.className = "jcc-excel-col-sub";
    sub.textContent = `참석 ${g.attended ?? 0}`;
    col.appendChild(head);
    col.appendChild(sub);
    const body = document.createElement("div");
    body.className = "jcc-excel-col-body";
    (g.members || []).forEach((m) => {
      const row = document.createElement("div");
      row.className = "jcc-excel-row";
      const name = document.createElement("span");
      name.className = "jcc-excel-name";
      name.textContent = m.name || "—";
      const mark = document.createElement("span");
      const muted = m.status === "pending";
      mark.className = "jcc-excel-mark" + (muted ? " jcc-excel-mark--muted" : "");
      mark.textContent = m.status_label || "";
      row.appendChild(name);
      row.appendChild(mark);
      body.appendChild(row);
    });
    col.appendChild(body);
    return col;
  }

  function renderGroupBoard(groups, grand) {
    if (!boardHost) return;
    boardHost.innerHTML = "";
    boardHost.classList.toggle("jcc-excel-board--grouped", groups.length > 0);

    const selectedRegion = boardRegionFilter ? boardRegionFilter.value : "";
    const regionOrder = regionOrderFromGroups(groups);
    const byRegion = groupsByRegion(groups);
    const visibleRegions = selectedRegion
      ? regionOrder.filter((r) => r === selectedRegion)
      : regionOrder;

    if (!groups.length || !visibleRegions.length) {
      const empty = document.createElement("div");
      empty.className = "muted";
      empty.textContent = selectedRegion
        ? "선택한 지역에 표시할 조가 없습니다."
        : "표시할 조가 없습니다.";
      boardHost.appendChild(empty);
    }

    visibleRegions.forEach((regionName) => {
      const regionGroups = byRegion.get(regionName) || [];
      if (!regionGroups.length) return;

      const section = document.createElement("section");
      section.className = "jcc-board-region";

      const regionHead = document.createElement("div");
      regionHead.className = "jcc-board-region-head";
      const totals = sumRegionTotals(regionGroups);
      regionHead.innerHTML = `
        <span class="jcc-board-region-name">${escapeHtml(regionName)}</span>
        <span class="jcc-board-region-meta">참석 ${totals.attended} · 입실전 ${totals.pending}</span>`;
      section.appendChild(regionHead);

      const byDivision = groupsByDivision(regionGroups);
      byDivision.forEach((divisionGroups, divisionName) => {
        const sorted = sortGroupsByNumber(divisionGroups);
        const block = document.createElement("div");
        block.className = "jcc-board-division";

        const key = divisionKey(regionName, divisionName);
        const collapsed = collapsedDivisions.has(key);

        const head = document.createElement("button");
        head.type = "button";
        head.className = "jcc-board-division-head";
        head.setAttribute("aria-expanded", collapsed ? "false" : "true");
        const divTotals = sumRegionTotals(sorted);
        head.innerHTML = `
          <span class="jcc-board-division-toggle" aria-hidden="true">▾</span>
          <span class="jcc-board-division-name">${escapeHtml(divisionName)}</span>
          <span class="jcc-board-division-meta">${sorted.length}개 조 · 참석 ${divTotals.attended} · 입실전 ${divTotals.pending}</span>`;
        block.appendChild(head);

        const colsWrap = document.createElement("div");
        colsWrap.className = "jcc-excel-board jcc-excel-board--cols";
        sorted.forEach((g) => {
          colsWrap.appendChild(createGroupColumn(g));
        });
        block.appendChild(colsWrap);

        if (collapsed) block.classList.add("is-collapsed");

        head.addEventListener("click", () => {
          const nowCollapsed = block.classList.toggle("is-collapsed");
          head.setAttribute("aria-expanded", nowCollapsed ? "false" : "true");
          if (nowCollapsed) collapsedDivisions.add(key);
          else collapsedDivisions.delete(key);
        });

        section.appendChild(block);
      });
      boardHost.appendChild(section);
    });

    if (boardTotalEl) {
      boardTotalEl.innerHTML = "";
      const strong = document.createElement("strong");
      if (selectedRegion && visibleRegions.length) {
        const filtered = groups.filter((g) => regionLabel(g) === selectedRegion);
        const filteredTotals = sumRegionTotals(filtered);
        strong.textContent = `${selectedRegion} · 참석 ${filteredTotals.attended} · 입실전 ${filteredTotals.pending}`;
      } else {
        strong.textContent = `전체 참석 ${grand.attended ?? 0} · 입실전 ${grand.pending ?? 0}`;
      }
      boardTotalEl.appendChild(strong);
    }
  }

  function applyTab() {
    if (panelStats) panelStats.style.display = activeTab === "board" ? "none" : "";
    if (panelBoard) panelBoard.style.display = activeTab === "board" ? "" : "none";
    // 요약 카드(실시간 참석·숙소 배정·차량 지원)는 '실시간' 탭에서만 노출
    if (summaryCards)
      summaryCards.style.display = activeTab === "board" ? "none" : "";
    if (innerTabs) {
      innerTabs.querySelectorAll("[data-dashboard-tab]").forEach((btn) => {
        btn.classList.toggle(
          "is-active",
          btn.getAttribute("data-dashboard-tab") === activeTab
        );
      });
    }
  }

  function refreshActive() {
    if (activeTab === "board") loadBoard();
    else load();
  }

  function setTab(tab) {
    activeTab = tab === "board" ? "board" : "stats";
    applyTab();
    refreshActive();
  }

  function formatStamp(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    const hh = String(d.getHours()).padStart(2, "0");
    const mi = String(d.getMinutes()).padStart(2, "0");
    return `${mm}/${dd} ${hh}:${mi}`;
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  if (btnRefresh) btnRefresh.addEventListener("click", refreshActive);
  if (boardRegionFilter) {
    boardRegionFilter.addEventListener("change", () => {
      renderGroupBoard(lastBoardGroups, lastBoardGrand);
    });
  }
  if (innerTabs) {
    innerTabs.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-dashboard-tab]");
      if (!btn) return;
      setTab(btn.getAttribute("data-dashboard-tab"));
    });
  }
  applyTab();
  load();
  setInterval(refreshActive, REFRESH_MS);
})();
