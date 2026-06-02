(function () {
  "use strict";
  const ctx = window.RETREAT_RESULTS_CTX;
  if (!ctx) return;

  const sessionEl = document.getElementById("sessionId");
  const statusEl = document.getElementById("resultsStatus");
  const grid = document.getElementById("resultsGrid");
  const grand = document.getElementById("resultsGrandTotal");
  const btnRefresh = document.getElementById("btnRefresh");

  async function load() {
    if (statusEl) statusEl.textContent = "불러오는 중…";
    try {
      let url = ctx.apiResults;
      const sid = sessionEl && sessionEl.value;
      if (sid) url += `?session_id=${encodeURIComponent(sid)}`;
      const r = await fetch(url, { credentials: "same-origin" });
      if (!r.ok) throw new Error(await r.text());
      const data = await r.json();
      render(data.by_group || []);
      if (grand) grand.textContent = `총합: ${data.grand_total ?? 0}명`;
      if (statusEl) statusEl.textContent = data.session ? `기준: ${data.session.name}` : "";
    } catch (e) {
      if (statusEl) statusEl.textContent = "로드 실패";
      console.error(e);
    }
  }

  function render(rows) {
    if (!grid) return;
    grid.innerHTML = "";
    const cols = 3;
    const perCol = Math.ceil(rows.length / cols) || 1;
    for (let c = 0; c < cols; c++) {
      const col = document.createElement("div");
      col.className = "jcc-retreat-tripleCol";
      const table = document.createElement("table");
      table.className = "jcc-retreat-miniTable";
      table.innerHTML = "<thead><tr><th>분류</th><th>인원수</th></tr></thead>";
      const tb = document.createElement("tbody");
      rows.slice(c * perCol, (c + 1) * perCol).forEach((row) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${row.name}</td><td>${row.count}</td>`;
        tb.appendChild(tr);
      });
      table.appendChild(tb);
      col.appendChild(table);
      grid.appendChild(col);
    }
  }

  if (sessionEl) sessionEl.addEventListener("change", load);
  if (btnRefresh) btnRefresh.addEventListener("click", load);
  load();
})();
