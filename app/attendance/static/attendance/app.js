/**
 * 출석 프론트 — /api/v1/attendance/* (세션 쿠키)
 */
const API = "/api/v1";
const DASHBOARD_ACCESS = window.ATTENDANCE_DASHBOARD_ACCESS || { canChangeDivision: false };

let charts = { sunVenue: null, sunPart: null, sunTeam: null, midweek: null };
/** @type {Record<string, object>} week_sunday → 주차 rollup API 한 행 */
let weekRollups = {};

/** 기준 일요일(ISO)에서 n일 후 날짜 ISO (UTC 날짜만 사용). */
function addDaysToIsoDate(iso, n) {
  const [y, mo, d] = iso.split("-").map(Number);
  const t = Date.UTC(y, mo - 1, d) + n * 86400000;
  const u = new Date(t);
  const yy = u.getUTCFullYear();
  const mm = String(u.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(u.getUTCDate()).padStart(2, "0");
  return `${yy}-${mm}-${dd}`;
}

function formatWeekRollupLine(w, wtype) {
  if (!w || typeof w.week_sunday !== "string" || !w.week_sunday) {
    return "—";
  }
  const sun = w.sunday_line_count ?? 0;
  const wed = w.wednesday_record_count ?? 0;
  const sat = w.saturday_record_count ?? 0;
  const total = sun + wed + sat;
  const y = parseInt(w.week_sunday.slice(0, 4), 10);
  const m = parseInt(w.week_sunday.slice(5, 7), 10);
  const idx = w.sunday_week_index_in_month ?? 1;

  if (wtype === "sunday") {
    return `${w.week_sunday} 주일 ${sun}명 · 예배: 주일`;
  }
  if (wtype === "wednesday") {
    const wd = addDaysToIsoDate(w.week_sunday, -4);
    return `${wd} 수요 ${wed}명 · 예배: 수요일`;
  }
  if (wtype === "saturday") {
    const sd = addDaysToIsoDate(w.week_sunday, -2);
    return `${sd} 토요 ${sat}명 · 예배: 토요일`;
  }
  if (wtype === "midweek") {
    return `${y}년 ${m}월 ${idx}주차 · 수요 ${wed} · 토요 ${sat} · 수·토 합 ${wed + sat} · 예배: 수·토 전체`;
  }
  return `${y}년 ${m}월 ${idx}주차 · 주일 ${sun} · 수요 ${wed} · 토요 ${sat} · 전체 ${total}`;
}

function repaintWeekSelectLabels() {
  const sel = document.getElementById("weekId");
  const wtype = document.getElementById("worshipType").value;
  const cur = sel.value;
  [...sel.options].forEach((opt) => {
    const w = weekRollups[opt.value];
    if (w) opt.textContent = formatWeekRollupLine(w, wtype);
  });
  if (cur && [...sel.options].some((o) => o.value === cur)) sel.value = cur;
}

function pathFromDrfUrl(url) {
  const u = new URL(url, window.location.origin);
  let p = u.pathname + u.search;
  if (p.startsWith("/api/v1")) p = p.slice("/api/v1".length);
  return p;
}

async function apiGet(path) {
  const r = await fetch(API + path, { credentials: "same-origin" });
  if (r.status === 401) {
    window.location = "/admin/login/?next=" + encodeURIComponent(location.pathname);
    throw new Error("unauthorized");
  }
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  const ct = r.headers.get("content-type") || "";
  if (ct.includes("application/json")) return r.json();
  return r.text();
}

function destroyChart(key) {
  if (charts[key]) {
    charts[key].destroy();
    charts[key] = null;
  }
}

function isoDateTodayLocal() {
  const u = new Date();
  const yy = u.getFullYear();
  const mm = String(u.getMonth() + 1).padStart(2, "0");
  const dd = String(u.getDate()).padStart(2, "0");
  return `${yy}-${mm}-${dd}`;
}

/** Python: week_sunday_on_or_after(d) = d + (6 - d.weekday) % 7 (weekday: Mon=0..Sun=6) */
function weekSundayOnOrAfterTodayLocal() {
  const todayIso = isoDateTodayLocal();
  const u = new Date();
  const jsDay = u.getDay(); // 0=Sun..6=Sat
  const pyWeekday = (jsDay + 6) % 7; // 0=Mon..6=Sun
  const offset = (6 - pyWeekday) % 7;
  return addDaysToIsoDate(todayIso, offset);
}

function resizeSunTeamChartWrap(teamCount) {
  const wrap = document.querySelector("#cardSunTeam .chart-wrap");
  if (!wrap) return;
  const minHeight = 360;
  const perRow = 30;
  wrap.style.height = `${Math.max(minHeight, teamCount * perRow)}px`;
}

function setStatus(msg, isErr) {
  const el = document.getElementById("statusLine");
  el.textContent = msg || "";
  el.className = "msg" + (isErr ? " err" : "");
}

async function loadMeta() {
  const meta = await apiGet("/attendance/meta/");
  const sel = document.getElementById("worshipType");
  sel.innerHTML = "";
  const worshipTypes = Array.isArray(meta.worship_types) ? meta.worship_types : [];
  worshipTypes.forEach((o) => {
    const opt = document.createElement("option");
    opt.value = o.value;
    opt.textContent = o.label;
    sel.appendChild(opt);
  });
  const fv = document.getElementById("fltVenue");
  while (fv.children.length > 1) fv.removeChild(fv.lastChild);
  const venues = Array.isArray(meta.venues) ? meta.venues : [];
  venues.forEach((o) => {
    const opt = document.createElement("option");
    opt.value = o.value;
    opt.textContent = o.label;
    fv.appendChild(opt);
  });
  const st = document.getElementById("fltMwStatus");
  while (st.children.length > 2) st.removeChild(st.lastChild);
  const mwSt = Array.isArray(meta.midweek_statuses) ? meta.midweek_statuses : [];
  mwSt.forEach((o) => {
    const opt = document.createElement("option");
    opt.value = o.value;
    opt.textContent = o.label;
    st.appendChild(opt);
  });
}

async function loadDivisions() {
  const raw = await apiGet("/attendance/divisions/");
  const list = Array.isArray(raw) ? raw : [];
  const sel = document.getElementById("divisionCode");
  sel.innerHTML = "";
  list.forEach((d) => {
    const opt = document.createElement("option");
    opt.value = d.code;
    opt.textContent = d.name + " (" + d.code + ")";
    sel.appendChild(opt);
  });
  sel.disabled = !DASHBOARD_ACCESS.canChangeDivision;
  if ([...sel.options].some((o) => o.value === "youth")) sel.value = "youth";
  if (list.length === 0) {
    setStatus(
      "출석을 볼 수 있는 부서가 없습니다. 이 계정에 UserDivisionTeam(소속 부서)이 연결되어 있는지 Admin에서 확인하세요.",
      true
    );
  }
}

async function loadWeeks() {
  const code = (document.getElementById("divisionCode").value || "").trim();
  const sel = document.getElementById("weekId");
  const wtype = document.getElementById("worshipType").value;
  sel.innerHTML = "";
  weekRollups = {};
  if (!code) {
    if (document.getElementById("divisionCode").options.length > 0) {
      setStatus("부서를 선택한 뒤 주차를 불러옵니다.", true);
    }
    return;
  }
  const listRaw = await apiGet("/attendance/weeks/?division_code=" + encodeURIComponent(code));
  const list = Array.isArray(listRaw) ? listRaw : [];
  list.forEach((w) => {
    weekRollups[w.week_sunday] = w;
  });
  list.forEach((w) => {
    const opt = document.createElement("option");
    opt.value = w.week_sunday;
    opt.textContent = formatWeekRollupLine(w, wtype);
    sel.appendChild(opt);
  });
  // 기본 선택: "현재 날짜 기준"으로 서버의 parse_week_rollup_key 로직과 동일하게 week_sunday-on-or-after를 선택
  if (list.length) {
    const opts = [...sel.options].map((o) => o.value);
    const curWeekSunday = weekSundayOnOrAfterTodayLocal();
    const wantedPrevWeekSunday = addDaysToIsoDate(curWeekSunday, -7); // -1 주차

    const exact = opts.find((v) => v === wantedPrevWeekSunday);
    if (exact) {
      sel.value = exact;
      return;
    }

    // 목록에 정확히 없으면, wantedPrevWeekSunday 이전(<=) 중 가장 가까운(=가장 최신) 주차 선택
    let best = null;
    for (const v of opts) {
      if (v <= wantedPrevWeekSunday) {
        if (!best || v > best) best = v;
      }
    }
    sel.value = best || opts[opts.length - 1]; // 그보다 더 과거에 데이터가 전혀 없으면 가장 오래된 주차
  }
  if (list.length === 0) setStatus("해당 부서에 집계할 출석 데이터가 없습니다.", true);
  else setStatus("");
}

function fillTeamSelect(sel, list) {
  sel.innerHTML = '<option value="">전체</option>';
  list.forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t.id;
    opt.textContent = t.name;
    sel.appendChild(opt);
  });
}

async function loadTeams() {
  const code = (document.getElementById("divisionCode").value || "").trim();
  if (!code) {
    fillTeamSelect(document.getElementById("fltTeam"), []);
    fillTeamSelect(document.getElementById("fltTeamMw"), []);
    return;
  }
  const raw = await apiGet("/attendance/teams/?division_code=" + encodeURIComponent(code));
  const list = Array.isArray(raw) ? raw : [];
  fillTeamSelect(document.getElementById("fltTeam"), list);
  fillTeamSelect(document.getElementById("fltTeamMw"), list);
}

function showChartCards(wtype) {
  const sun = wtype === "all" || wtype === "sunday";
  const mw =
    wtype === "all" || wtype === "midweek" || wtype === "wednesday" || wtype === "saturday";
  document.getElementById("cardSunVenue").style.display = sun ? "block" : "none";
  document.getElementById("cardSunPart").style.display = sun ? "block" : "none";
  document.getElementById("cardSunTeam").style.display = sun ? "block" : "none";
  document.getElementById("cardMw").style.display = mw ? "block" : "none";
  document.getElementById("panelSunday").style.display = sun ? "block" : "none";
  document.getElementById("panelMidweek").style.display = mw ? "block" : "none";
}

async function loadSummary() {
  const wid = document.getElementById("weekId").value;
  const code = (document.getElementById("divisionCode").value || "").trim();
  const wtype = document.getElementById("worshipType").value;
  showChartCards(wtype);
  if (!wid || !code) {
    destroyChart("sunVenue");
    destroyChart("sunPart");
    destroyChart("sunTeam");
    destroyChart("midweek");
    return;
  }
  const data = await apiGet(
    "/attendance/weeks/" +
      encodeURIComponent(wid) +
      "/summary/?division_code=" +
      encodeURIComponent(code) +
      "&worship_type=" +
      encodeURIComponent(wtype)
  );

  destroyChart("sunVenue");
  destroyChart("sunPart");
  destroyChart("sunTeam");
  destroyChart("midweek");

  if (data.sunday) {
    const bv = data.sunday.by_venue_display || {};
    const labels = Object.keys(bv);
    const values = Object.values(bv);
    charts.sunVenue = new Chart(document.getElementById("chartSunVenue"), {
      type: "doughnut",
      data: {
        labels: labels.length ? labels : ["데이터 없음"],
        datasets: [
          {
            data: labels.length ? values : [1],
            backgroundColor: labels.length
              ? ["#4a9eff", "#5ab87a", "#c9a227", "#a78bfa", "#f472b6", "#94a3b8"]
              : ["#2a3548"],
          },
        ],
      },
      options: { plugins: { legend: { position: "bottom", labels: { color: "#cbd5e1" } } } },
    });

    const parts = data.sunday.by_venue_part || [];
    charts.sunPart = new Chart(document.getElementById("chartSunPart"), {
      type: "bar",
      data: {
        labels: parts.length ? parts.map((p) => p.label) : ["—"],
        datasets: [
          {
            label: "인원",
            data: parts.length ? parts.map((p) => p.count) : [0],
            backgroundColor: "#4a9eff",
          },
        ],
      },
      options: {
        indexAxis: "y",
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: "#94a3b8" }, grid: { color: "#2a3548" } },
          y: { ticks: { color: "#94a3b8" }, grid: { color: "#2a3548" } },
        },
      },
    });

    const teams = data.sunday.by_team || [];
    resizeSunTeamChartWrap(teams.length);
    charts.sunTeam = new Chart(document.getElementById("chartSunTeam"), {
      type: "bar",
      data: {
        labels: teams.length ? teams.map((t) => t.team_name) : ["—"],
        datasets: [
          {
            label: "인원",
            data: teams.length ? teams.map((t) => t.count) : [0],
            backgroundColor: "#5ab87a",
          },
        ],
      },
      options: {
        indexAxis: "y",
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: "#94a3b8" }, grid: { color: "#2a3548" } },
          y: {
            ticks: {
              color: "#94a3b8",
              maxRotation: 0,
              autoSkip: false,
              padding: 10,
              font: { size: 12 },
            },
            grid: { color: "#2a3548" },
          },
        },
      },
    });
  }

  if (data.midweek && data.midweek.by_service) {
    const svcKeys = Object.keys(data.midweek.by_service);
    const statusSet = new Set();
    svcKeys.forEach((k) => {
      Object.keys(data.midweek.by_service[k].by_status || {}).forEach((s) => statusSet.add(s));
    });
    const statusLabels = [...statusSet];
    const palette = ["#5ab87a", "#f87171", "#4a9eff", "#c9a227", "#a78bfa", "#94a3b8"];
    if (svcKeys.length && statusLabels.length) {
      const datasets = statusLabels.map((st, i) => ({
        label: st,
        data: svcKeys.map((sk) => (data.midweek.by_service[sk].by_status || {})[st] || 0),
        backgroundColor: palette[i % palette.length],
      }));
      charts.midweek = new Chart(document.getElementById("chartMidweek"), {
        type: "bar",
        data: {
          labels: svcKeys.map((sk) => data.midweek.by_service[sk].label),
          datasets,
        },
        options: {
          responsive: true,
          scales: {
            x: { stacked: true, ticks: { color: "#94a3b8" }, grid: { color: "#2a3548" } },
            y: { stacked: true, ticks: { color: "#94a3b8" }, grid: { color: "#2a3548" } },
          },
          plugins: { legend: { position: "bottom", labels: { color: "#cbd5e1" } } },
        },
      });
    }
  }
}

function escapeHtml(s) {
  if (!s) return "";
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

async function loadSunTable(url) {
  const wid = document.getElementById("weekId").value;
  if (!wid) return;
  const code = (document.getElementById("divisionCode").value || "").trim();
  if (!code) return;
  let path;
  if (url && (url.startsWith("http") || url.startsWith("/"))) {
    path = pathFromDrfUrl(url);
  } else {
    const p = new URLSearchParams();
    p.set("division_code", code);
    const v = document.getElementById("fltVenue").value;
    const part = document.getElementById("fltPart").value;
    const tid = document.getElementById("fltTeam").value;
    const q = document.getElementById("fltSearchSun").value.trim();
    if (v) p.set("venue", v);
    if (part !== "") p.set("session_part", part);
    if (tid) p.set("team_id", tid);
    if (q) p.set("search", q);
    path = "/attendance/weeks/" + encodeURIComponent(wid) + "/sunday/?" + p.toString();
  }
  const data = await apiGet(path);
  paintSunTable(data);
}

function paintSunTable(payload) {
  const tb = document.getElementById("tbodySun");
  tb.innerHTML = "";
  (payload.results || []).forEach((r) => {
    const tr = document.createElement("tr");
    tr.innerHTML =
      "<td>" +
      escapeHtml(r.service_date || "—") +
      "</td><td>" +
      escapeHtml(r.member_name) +
      "</td><td><span class=\"tag\">" +
      escapeHtml(r.venue_label) +
      "</span></td><td>" +
      (r.session_part || "—") +
      "</td><td>" +
      escapeHtml(r.team_name || "—") +
      "</td>";
    tb.appendChild(tr);
  });
  const pg = document.getElementById("pagerSun");
  pg.innerHTML = "";
  const addBtn = (label, u) => {
    if (!u) return;
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    b.className = label === "이전" ? "secondary" : "";
    b.onclick = () => loadSunTable(u);
    pg.appendChild(b);
  };
  addBtn("이전", payload.previous);
  addBtn("다음", payload.next);
  if (payload.stats) {
    const st = payload.stats;
    const s = document.createElement("span");
    s.style.color = "#8b9cb3";
    s.style.fontSize = "0.85rem";
    s.textContent =
      "현장 참석 " +
      (st.on_site ?? 0) +
      "명 · 온라인 " +
      (st.online ?? 0) +
      "명 · 지교회 " +
      (st.branch ?? 0) +
      "명 · 불참 " +
      (st.absent ?? 0) +
      "명";
    pg.appendChild(s);
  } else if (payload.count != null) {
    const s = document.createElement("span");
    s.style.color = "#8b9cb3";
    s.style.fontSize = "0.85rem";
    s.textContent = "총 " + payload.count + "건";
    pg.appendChild(s);
  }
}

async function loadMwTable(url) {
  const wid = document.getElementById("weekId").value;
  if (!wid) return;
  const code = (document.getElementById("divisionCode").value || "").trim();
  if (!code) return;
  let path;
  if (url && (url.startsWith("http") || url.startsWith("/"))) {
    path = pathFromDrfUrl(url);
  } else {
    const p = new URLSearchParams();
    p.set("division_code", code);
    const svc = document.getElementById("fltSvc").value;
    const st = document.getElementById("fltMwStatus").value;
    const tid = document.getElementById("fltTeamMw").value;
    const q = document.getElementById("fltSearchMw").value.trim();
    if (svc) p.set("service_type", svc);
    if (st) p.set("status", st);
    if (tid) p.set("team_id", tid);
    if (q) p.set("search", q);
    path = "/attendance/weeks/" + encodeURIComponent(wid) + "/midweek/?" + p.toString();
  }
  const data = await apiGet(path);
  const tb = document.getElementById("tbodyMw");
  tb.innerHTML = "";
  (data.results || []).forEach((r) => {
    const tr = document.createElement("tr");
    tr.innerHTML =
      "<td>" +
      escapeHtml(r.service_date || "—") +
      "</td><td>" +
      escapeHtml(r.member_name) +
      "</td><td>" +
      escapeHtml(r.team_name || "—") +
      "</td><td>" +
      escapeHtml(r.service_label) +
      "</td><td>" +
      escapeHtml(r.status_label || "미입력") +
      "</td>";
    tb.appendChild(tr);
  });
  const pg = document.getElementById("pagerMw");
  pg.innerHTML = "";
  const addBtn = (label, u) => {
    if (!u) return;
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    b.className = label === "이전" ? "secondary" : "";
    b.onclick = () => loadMwTable(u);
    pg.appendChild(b);
  };
  addBtn("이전", data.previous);
  addBtn("다음", data.next);
  if (data.stats) {
    const st = data.stats;
    const s = document.createElement("span");
    s.style.color = "#8b9cb3";
    s.style.fontSize = "0.85rem";
    s.textContent =
      "현장 참석 " +
      (st.on_site ?? 0) +
      "명 · 온라인 " +
      (st.online ?? 0) +
      "명 · 지교회 " +
      (st.branch ?? 0) +
      "명 · 불참 " +
      (st.absent ?? 0) +
      "명";
    pg.appendChild(s);
  } else if (data.count != null) {
    const s = document.createElement("span");
    s.style.color = "#8b9cb3";
    s.style.fontSize = "0.85rem";
    s.textContent = "총 " + data.count + "건";
    pg.appendChild(s);
  }
}

async function refreshAll() {
  try {
    setStatus("불러오는 중…");
    await loadSummary();
    const wtype = document.getElementById("worshipType").value;
    if (wtype === "all" || wtype === "sunday") await loadSunTable();
    else document.getElementById("tbodySun").innerHTML = "";
    if (wtype === "all" || wtype === "midweek" || wtype === "wednesday" || wtype === "saturday")
      await loadMwTable();
    else document.getElementById("tbodyMw").innerHTML = "";
    const divSel = document.getElementById("divisionCode");
    const code = (divSel.value || "").trim();
    const wid = document.getElementById("weekId").value;
    const w = weekRollups[wid];
    const worshipLabel = document.getElementById("worshipType").selectedOptions[0]?.textContent || "";
    if (divSel.options.length === 0) {
      setStatus(
        "출석을 볼 수 있는 부서가 없습니다. 이 계정에 UserDivisionTeam(소속 부서)이 연결되어 있는지 Admin에서 확인하세요.",
        true
      );
      return;
    }
    if (!code) {
      setStatus("부서를 선택하세요.", true);
      return;
    }
    if (!wid) {
      if (document.getElementById("weekId").options.length === 0) {
        setStatus("해당 부서에 집계할 출석 데이터가 없습니다.", true);
      } else {
        setStatus("주차를 선택하세요.", true);
      }
      return;
    }
    if (w) {
      const line = formatWeekRollupLine(w, wtype);
      setStatus(wtype === "all" ? line + " · 예배: " + worshipLabel : line);
    } else {
      setStatus("주차 정보를 불러오지 못했습니다." + (worshipLabel ? " · 예배: " + worshipLabel : ""));
    }
  } catch (e) {
    console.error(e);
    setStatus("오류: " + e.message, true);
  }
}

function bindUi() {
  document.getElementById("btnRefresh").onclick = refreshAll;
  document.getElementById("btnApplySun").onclick = () => loadSunTable();
  document.getElementById("btnApplyMw").onclick = () => loadMwTable();
  document.getElementById("divisionCode").onchange = async () => {
    if (!DASHBOARD_ACCESS.canChangeDivision) return;
    await loadWeeks();
    await loadTeams();
    await refreshAll();
  };
  document.getElementById("weekId").onchange = refreshAll;
  document.getElementById("worshipType").onchange = async () => {
    repaintWeekSelectLabels();
    await refreshAll();
  };
}

async function init() {
  bindUi();
  try {
    await loadMeta();
    await loadDivisions();
    await loadWeeks();
    await loadTeams();
    await refreshAll();
  } catch (e) {
    console.error(e);
    setStatus("초기화 실패: " + e.message, true);
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
