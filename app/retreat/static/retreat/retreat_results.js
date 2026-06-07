(function () {
  "use strict";
  const ctx = window.RETREAT_RESULTS_CTX;
  if (!ctx) return;

  const sessionEl = document.getElementById("sessionId");
  const statusEl = document.getElementById("resultsStatus");
  const grid = document.getElementById("resultsGrid");
  const grand = document.getElementById("resultsGrandTotal");
  const btnRefresh = document.getElementById("btnRefresh");

  const groupChart = document.getElementById("groupChart");
  const regionChart = document.getElementById("regionChart");
  const regionLegend = document.getElementById("regionLegend");
  const hourlyChart = document.getElementById("hourlyChart");
  const hourlyLegend = document.getElementById("hourlyLegend");

  const PALETTE = [
    "#4f7cff", "#ff7a59", "#23c08a", "#f2c14e", "#9b6dff",
    "#ff5d8f", "#2bb6d6", "#8bc34a", "#ff9f1c", "#6c7a89",
    "#e8527a", "#3fc1c9", "#c97cf2", "#5b8def", "#d68a23",
  ];
  const COLOR_IN = "#4f7cff";
  const COLOR_OUT = "#ff7a59";

  let analytics = null;

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function selectedSession() {
    if (!analytics || !analytics.sessions.length) return null;
    const sid = sessionEl && sessionEl.value;
    if (sid) {
      const found = analytics.sessions.find((s) => String(s.id) === String(sid));
      if (found) return found;
    }
    return analytics.sessions[analytics.sessions.length - 1];
  }

  async function load() {
    if (statusEl) statusEl.textContent = "불러오는 중…";
    await Promise.all([loadAnalytics(), loadDashboard()]);
    if (statusEl) {
      const sess = selectedSession();
      statusEl.textContent = sess ? `기준: ${sess.name}` : "";
    }
  }

  // ---- 출석부(세션) 기반 조별 인원 표 ----
  async function loadAnalytics() {
    try {
      const r = await fetch(ctx.apiAnalytics, { credentials: "same-origin" });
      if (!r.ok) throw new Error(await r.text());
      analytics = await r.json();
      renderTable(selectedSession());
    } catch (e) {
      if (statusEl) statusEl.textContent = "로드 실패";
      console.error(e);
    }
  }

  function renderTable(sess) {
    if (!grid) return;
    grid.innerHTML = "";
    const groups = (analytics && analytics.groups) || [];
    const rows = groups.map((g) => {
      const d = (sess && sess.groups[String(g.group_id)]) || { present: 0 };
      return { name: g.name, count: d.present };
    });
    const total = rows.reduce((a, r) => a + r.count, 0);
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
        tr.innerHTML = `<td>${esc(row.name)}</td><td>${row.count}</td>`;
        tb.appendChild(tr);
      });
      table.appendChild(tb);
      col.appendChild(table);
      grid.appendChild(col);
    }
    if (grand) grand.textContent = `총합: ${total}명`;
  }

  // ---- 실시간 입실 기반 그래프 (대시보드 API) ----
  async function loadDashboard() {
    if (!groupChart && !regionChart && !hourlyChart) return;
    try {
      const r = await fetch(ctx.apiDashboard, { credentials: "same-origin" });
      if (!r.ok) throw new Error(await r.text());
      const data = await r.json();
      renderGroups(data.by_group || []);
      renderRegionDonut(data.by_group || []);
      renderHourly(data.hourly || []);
    } catch (e) {
      console.error(e);
    }
  }

  // 조별 참석 가로 막대 (attended = 입실 기록 있는 인원)
  function renderGroups(rows) {
    if (!groupChart) return;
    const items = rows
      .map((row, i) => ({
        name: row.name,
        value: row.attended ?? 0,
        color: PALETTE[i % PALETTE.length],
      }))
      .filter((r) => r.value > 0 || rows.length <= 20);

    if (!items.length) {
      groupChart.innerHTML = '<p class="jcc-retreat-chartEmpty">입실 기록이 없습니다.</p>';
      return;
    }

    const maxVal = Math.max(...items.map((r) => r.value), 1);
    let html = '<div class="jcc-retreat-rateList">';
    items.forEach((r) => {
      const pct = Math.round((r.value / maxVal) * 100);
      html += `
        <div class="jcc-retreat-rateRow">
          <div class="jcc-retreat-rateHead">
            <span class="jcc-retreat-rateName">${esc(r.name)}</span>
            <span class="jcc-retreat-rateVal">${r.value}명</span>
          </div>
          <div class="jcc-retreat-rateTrack">
            <div class="jcc-retreat-rateFill" style="width:${pct}%;background:${r.color}"></div>
          </div>
        </div>`;
    });
    html += "</div>";
    groupChart.innerHTML = html;
  }

  // 지역별 참석 도넛 (region별 attended 합산)
  function renderRegionDonut(rows) {
    if (!regionChart) return;
    const regionMap = {};
    rows.forEach((row) => {
      const key = row.region || "미지정";
      if (!regionMap[key]) regionMap[key] = 0;
      regionMap[key] += row.attended ?? 0;
    });

    const slices = Object.entries(regionMap)
      .map(([name, value], i) => ({
        name,
        value,
        color: PALETTE[i % PALETTE.length],
      }))
      .filter((s) => s.value > 0);

    const total = slices.reduce((a, s) => a + s.value, 0);

    if (!total) {
      regionChart.innerHTML = '<p class="jcc-retreat-chartEmpty">입실 기록이 없습니다.</p>';
      if (regionLegend) regionLegend.innerHTML = "";
      return;
    }

    const size = 220;
    const cx = size / 2;
    const cy = size / 2;
    const r = 92;
    const inner = 56;
    let angle = -Math.PI / 2;
    let paths = "";

    slices.forEach((s) => {
      const frac = s.value / total;
      const a2 = angle + frac * Math.PI * 2;
      const large = frac > 0.5 ? 1 : 0;
      const x1 = cx + r * Math.cos(angle);
      const y1 = cy + r * Math.sin(angle);
      const x2 = cx + r * Math.cos(a2);
      const y2 = cy + r * Math.sin(a2);
      const ix2 = cx + inner * Math.cos(a2);
      const iy2 = cy + inner * Math.sin(a2);
      const ix1 = cx + inner * Math.cos(angle);
      const iy1 = cy + inner * Math.sin(angle);
      if (slices.length === 1) {
        paths += `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${s.color}" />`;
        paths += `<circle cx="${cx}" cy="${cy}" r="${inner}" class="jcc-retreat-donutHole" />`;
      } else {
        paths += `<path d="M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${x2.toFixed(2)} ${y2.toFixed(2)} L ${ix2.toFixed(2)} ${iy2.toFixed(2)} A ${inner} ${inner} 0 ${large} 0 ${ix1.toFixed(2)} ${iy1.toFixed(2)} Z" fill="${s.color}" />`;
      }
      angle = a2;
    });

    let svg = `<svg viewBox="0 0 ${size} ${size}" class="jcc-retreat-svg jcc-retreat-donutSvg" role="img" aria-label="지역별 참석 비중">`;
    svg += paths;
    svg += `<text x="${cx}" y="${cy - 4}" class="jcc-retreat-donutCenter">${total}</text>`;
    svg += `<text x="${cx}" y="${cy + 16}" class="jcc-retreat-donutCenterSub">명</text>`;
    svg += "</svg>";
    regionChart.innerHTML = svg;

    if (regionLegend) {
      let lg = "";
      slices
        .slice()
        .sort((a, b) => b.value - a.value)
        .forEach((s) => {
          const pct = Math.round((s.value / total) * 100);
          lg += `<span class="jcc-retreat-legendItem"><span class="jcc-retreat-legendSw" style="background:${s.color}"></span>${esc(s.name)} <strong>${s.value}</strong> (${pct}%)</span>`;
        });
      regionLegend.innerHTML = lg;
    }
  }

  // 시간대별 입·퇴실 수직 막대 (checked_in_at / checked_out_at 기록)
  function renderHourly(rows) {
    if (!hourlyChart) return;
    if (!rows.length) {
      hourlyChart.innerHTML = '<p class="jcc-retreat-chartEmpty">입·퇴실 기록이 없습니다.</p>';
      if (hourlyLegend) hourlyLegend.innerHTML = "";
      return;
    }

    const W = Math.max(760, rows.length * 56);
    const H = 300;
    const padL = 44;
    const padR = 16;
    const padT = 16;
    const padB = 72;
    const plotW = W - padL - padR;
    const plotH = H - padT - padB;

    let ymax = 0;
    rows.forEach((row) => {
      ymax = Math.max(ymax, row.checked_in, row.checked_out);
    });
    ymax = Math.max(ymax, 1);
    const niceMax = Math.ceil(ymax / 4) * 4 || 4;

    const n = rows.length;
    const slotW = plotW / n;
    const barW = Math.min(18, slotW * 0.32);
    const gap = 4;
    const yFor = (v) => padT + plotH - (plotH * v) / niceMax;

    let svg = `<svg viewBox="0 0 ${W} ${H}" class="jcc-retreat-svg" role="img" aria-label="시간대별 입퇴실">`;

    const ticks = 4;
    for (let t = 0; t <= ticks; t++) {
      const val = (niceMax / ticks) * t;
      const y = yFor(val);
      svg += `<line x1="${padL}" y1="${y}" x2="${W - padR}" y2="${y}" class="jcc-retreat-grid" />`;
      svg += `<text x="${padL - 8}" y="${y + 4}" class="jcc-retreat-axisLbl jcc-retreat-axisLbl--y">${Math.round(val)}</text>`;
    }

    rows.forEach((row, i) => {
      const cx = padL + slotW * i + slotW / 2;
      const inH = plotH * (row.checked_in / niceMax);
      const outH = plotH * (row.checked_out / niceMax);
      const inX = cx - barW - gap / 2;
      const outX = cx + gap / 2;
      const inY = padT + plotH - inH;
      const outY = padT + plotH - outH;

      if (row.checked_in > 0) {
        svg += `<rect x="${inX}" y="${inY}" width="${barW}" height="${inH}" fill="${COLOR_IN}" rx="2" class="jcc-retreat-vbar jcc-retreat-vbar--in" />`;
        svg += `<text x="${inX + barW / 2}" y="${inY - 4}" class="jcc-retreat-barLbl">${row.checked_in}</text>`;
      }
      if (row.checked_out > 0) {
        svg += `<rect x="${outX}" y="${outY}" width="${barW}" height="${outH}" fill="${COLOR_OUT}" rx="2" class="jcc-retreat-vbar jcc-retreat-vbar--out" />`;
        svg += `<text x="${outX + barW / 2}" y="${outY - 4}" class="jcc-retreat-barLbl">${row.checked_out}</text>`;
      }

      const label = row.label.length > 12 ? row.label.slice(0, 11) + "…" : row.label;
      svg += `<text x="${cx}" y="${H - padB + 18}" class="jcc-retreat-axisLbl jcc-retreat-xlbl" transform="rotate(20 ${cx} ${H - padB + 18})">${esc(label)}</text>`;
    });

    svg += "</svg>";
    hourlyChart.innerHTML = svg;

    if (hourlyLegend) {
      hourlyLegend.innerHTML = `
        <span class="jcc-retreat-legendItem"><span class="jcc-retreat-legendSw" style="background:${COLOR_IN}"></span>입실</span>
        <span class="jcc-retreat-legendItem"><span class="jcc-retreat-legendSw" style="background:${COLOR_OUT}"></span>퇴실</span>`;
    }
  }

  if (sessionEl) {
    sessionEl.addEventListener("change", () => renderTable(selectedSession()));
  }
  if (btnRefresh) btnRefresh.addEventListener("click", load);
  load();
})();
