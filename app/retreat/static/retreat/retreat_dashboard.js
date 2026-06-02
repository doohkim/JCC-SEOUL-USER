(function () {
  "use strict";
  const ctx = window.RETREAT_DASHBOARD_CTX;
  if (!ctx) return;

  const sessionEl = document.getElementById("sessionId");
  const statusEl = document.getElementById("dashboardStatus");
  const groupGrid = document.getElementById("groupGrid");
  const groupGrand = document.getElementById("groupGrandTotal");
  const divBody = document.querySelector("#divisionTable tbody");
  const btnRefresh = document.getElementById("btnRefresh");

  function csrf() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  async function load() {
    const sid = sessionEl && sessionEl.value;
    if (!sid) {
      if (statusEl) statusEl.textContent = "출석부를 먼저 만드세요.";
      return;
    }
    if (statusEl) statusEl.textContent = "불러오는 중…";
    try {
      const url = `${ctx.apiDashboard}?session_id=${encodeURIComponent(sid)}`;
      const r = await fetch(url, { credentials: "same-origin" });
      if (!r.ok) throw new Error(await r.text());
      const data = await r.json();
      renderGroups(data.by_group || []);
      renderDivisions(data.by_division || []);
      const gt = data.grand_total || {};
      if (groupGrand) {
        groupGrand.textContent = `총합: ${gt.entered ?? 0}명`;
      }
      if (statusEl) statusEl.textContent = "";
    } catch (e) {
      if (statusEl) statusEl.textContent = "로드 실패";
      console.error(e);
    }
  }

  function renderGroups(rows) {
    if (!groupGrid) return;
    groupGrid.innerHTML = "";
    const cols = 3;
    const perCol = Math.ceil(rows.length / cols) || 1;
    for (let c = 0; c < cols; c++) {
      const col = document.createElement("div");
      col.className = "jcc-retreat-tripleCol";
      const table = document.createElement("table");
      table.className = "jcc-retreat-miniTable";
      table.innerHTML = "<thead><tr><th>분류</th><th>인원</th></tr></thead>";
      const tb = document.createElement("tbody");
      rows.slice(c * perCol, (c + 1) * perCol).forEach((row) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${escapeHtml(row.name)}</td><td>${row.present}</td>`;
        tb.appendChild(tr);
      });
      table.appendChild(tb);
      col.appendChild(table);
      groupGrid.appendChild(col);
    }
  }

  function renderDivisions(rows) {
    if (!divBody) return;
    divBody.innerHTML = "";
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(row.region)}</td>
        <td>${escapeHtml(row.division)}</td>
        <td>${escapeHtml(row.group_range)}</td>
        <td>${row.entered}</td>
        <td>${row.left_scheduled ?? 0}</td>
        <td>${row.current}</td>
        <td>${row.final_attendance}</td>`;
      divBody.appendChild(tr);
    });
  }

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  if (sessionEl) sessionEl.addEventListener("change", load);
  if (btnRefresh) btnRefresh.addEventListener("click", load);
  load();
})();
