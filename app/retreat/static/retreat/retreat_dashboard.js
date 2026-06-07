(function () {
  "use strict";
  const ctx = window.RETREAT_DASHBOARD_CTX;
  if (!ctx) return;

  const statusEl = document.getElementById("dashboardStatus");
  const attendTotalEl = document.getElementById("attendTotal");
  const groupGrid = document.getElementById("groupGrid");
  const divBody = document.querySelector("#divisionTable tbody");
  const hourlyBody = document.querySelector("#hourlyTable tbody");
  const generatedAtEl = document.getElementById("dashGeneratedAt");
  const btnRefresh = document.getElementById("btnRefresh");
  const totalEls = {
    pending: document.querySelector("[data-total-pending]"),
    in: document.querySelector("[data-total-in]"),
    out: document.querySelector("[data-total-out]"),
    attended: document.querySelector("[data-total-attended]"),
  };

  const REFRESH_MS = 60000;

  async function load() {
    if (statusEl) statusEl.textContent = "불러오는 중…";
    try {
      const r = await fetch(ctx.apiDashboard, { credentials: "same-origin" });
      if (!r.ok) throw new Error(await r.text());
      const data = await r.json();
      renderAttendTotal(data.grand_total || {});
      renderGroups(data.by_group || []);
      renderDivisions(data.by_division || [], data.grand_total || {});
      renderHourly(data.hourly || []);
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

  function renderGroups(rows) {
    if (!groupGrid) return;
    groupGrid.innerHTML = "";
    const cols = 3;
    const perCol = Math.ceil(rows.length / cols) || 1;
    for (let c = 0; c < cols; c++) {
      const slice = rows.slice(c * perCol, (c + 1) * perCol);
      if (!slice.length && c > 0) continue;
      const col = document.createElement("div");
      col.className = "jcc-retreat-tripleCol";
      const table = document.createElement("table");
      table.className = "jcc-retreat-miniTable";
      table.innerHTML = "<thead><tr><th>조</th><th>참석</th></tr></thead>";
      const tb = document.createElement("tbody");
      slice.forEach((row) => {
        const tr = document.createElement("tr");
        // 조별 참석 = 현재 입실 상태 인원만.
        tr.innerHTML = `<td>${escapeHtml(row.name)}</td><td>${row.checked_in}</td>`;
        tb.appendChild(tr);
      });
      table.appendChild(tb);
      col.appendChild(table);
      groupGrid.appendChild(col);
    }
  }

  function renderDivisions(rows, grand) {
    if (!divBody) return;
    divBody.innerHTML = "";
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(row.region)}</td>
        <td>${escapeHtml(row.division)}</td>
        <td>${escapeHtml(row.group_range)}</td>
        <td>${row.pending}</td>
        <td>${row.checked_in}</td>
        <td>${row.checked_out}</td>
        <td>${row.attended}</td>`;
      divBody.appendChild(tr);
    });
    if (totalEls.pending) totalEls.pending.textContent = grand.pending ?? 0;
    if (totalEls.in) totalEls.in.textContent = grand.checked_in ?? 0;
    if (totalEls.out) totalEls.out.textContent = grand.checked_out ?? 0;
    if (totalEls.attended) totalEls.attended.textContent = grand.attended ?? 0;
  }

  function renderHourly(rows) {
    if (!hourlyBody) return;
    hourlyBody.innerHTML = "";
    if (!rows.length) {
      const tr = document.createElement("tr");
      tr.innerHTML = '<td colspan="3" class="muted">입·퇴실 기록이 없습니다.</td>';
      hourlyBody.appendChild(tr);
      return;
    }
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(row.label)}</td>
        <td>${row.checked_in}</td>
        <td>${row.checked_out}</td>`;
      hourlyBody.appendChild(tr);
    });
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

  if (btnRefresh) btnRefresh.addEventListener("click", load);
  load();
  setInterval(load, REFRESH_MS);
})();
