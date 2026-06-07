/**
 * 출석 프론트 — /api/v1/attendance/* (세션 쿠키)
 */
const API = "/api/v1";
const DASHBOARD_ACCESS = window.ATTENDANCE_DASHBOARD_ACCESS || { canChangeDivision: false };

/** 팀 출석판(주일) 슬롯 키 → 표시 라벨 (`attendance/team_roster_check.js` 와 동일 체계) */
const SUNDAY_BOARD_OPTIONS = [
  { key: "seoul_1", label: "서울 1부" },
  { key: "seoul_2", label: "서울 2부" },
  { key: "seoul_3", label: "서울 3부" },
  { key: "seoul_4", label: "서울 4부" },
  { key: "incheon_1", label: "인천 1부" },
  { key: "incheon_2", label: "인천 2부" },
  { key: "incheon_3", label: "인천 3부" },
  { key: "incheon_4", label: "인천 4부" },
  { key: "online", label: "온라인" },
  { key: "branch", label: "지교회" },
];

function sundayBoardKeyOrder(k) {
  const i = SUNDAY_BOARD_OPTIONS.findIndex((o) => o.key === k);
  return i === -1 ? 999 : i;
}

/** @param {string[]} keysSorted */
function parseSundayVenueKeys(keysSorted) {
  const seoul = [];
  const incheon = [];
  let hasOnline = false;
  let hasBranch = false;
  for (const k of keysSorted) {
    if (k === "online") hasOnline = true;
    else if (k === "branch") hasBranch = true;
    else if (String(k).startsWith("seoul_")) {
      const n = parseInt(String(k).replace("seoul_", ""), 10);
      if (!Number.isNaN(n)) seoul.push(n);
    } else if (String(k).startsWith("incheon_")) {
      const n = parseInt(String(k).replace("incheon_", ""), 10);
      if (!Number.isNaN(n)) incheon.push(n);
    }
  }
  const uniqSort = (arr) => [...new Set(arr)].sort((a, b) => a - b);
  return {
    seoul: uniqSort(seoul),
    incheon: uniqSort(incheon),
    hasOnline,
    hasBranch,
  };
}

/**
 * 서울/인천: 지역명과 첫 부 사이 공백 없음(서울1부, 2부). 이어지는 줄은 지역명 폭만큼
 * 숨김 스팬으로 맞춰 1부 열에 3부·4부가 맞춰짐.
 * @param {HTMLElement} el
 * @param {string[]} keysSorted
 */
function fillSundayMarkStructured(el, keysSorted) {
  el.textContent = "";
  const { seoul: sp, incheon: ip, hasOnline, hasBranch } = parseSundayVenueKeys(keysSorted);
  const stack = document.createElement("div");
  stack.className = "jcc-excel-mark-stack";

  function appendVenueBlock(regionName, parts) {
    const p = parts;
    if (!p.length) return;
    const block = document.createElement("div");
    block.className = "jcc-excel-venue-block";

    function addLine(partsText, { continuation } = { continuation: false }) {
      const line = document.createElement("div");
      line.className = "jcc-excel-venue-line";
      if (continuation) {
        const ghost = document.createElement("span");
        ghost.className = "jcc-excel-venue-region jcc-excel-venue-region--ghost";
        ghost.setAttribute("aria-hidden", "true");
        ghost.textContent = regionName;
        line.appendChild(ghost);
      } else {
        const reg = document.createElement("span");
        reg.className = "jcc-excel-venue-region";
        reg.textContent = regionName;
        line.appendChild(reg);
      }
      const rest = document.createElement("span");
      rest.className = "jcc-excel-venue-parts";
      rest.textContent = partsText;
      line.appendChild(rest);
      block.appendChild(line);
    }

    if (p.length === 1) {
      addLine(`${p[0]}부`, { continuation: false });
    } else {
      addLine(`${p[0]}부, ${p[1]}부`, { continuation: false });
      let idx = 2;
      while (idx < p.length) {
        const chunk = p.slice(idx, idx + 2);
        addLine(chunk.map((x) => `${x}부`).join(", "), { continuation: true });
        idx += chunk.length;
      }
    }
    stack.appendChild(block);
  }

  appendVenueBlock("서울", sp);
  appendVenueBlock("인천", ip);
  if (hasOnline) {
    const d = document.createElement("div");
    d.className = "jcc-excel-mark-line";
    d.textContent = "온라인";
    stack.appendChild(d);
  }
  if (hasBranch) {
    const d = document.createElement("div");
    d.className = "jcc-excel-mark-line";
    d.textContent = "지교회";
    stack.appendChild(d);
  }
  el.appendChild(stack);
}

/** @returns {{ muted: true, text: string } | { muted: false, keys: string[] }} */
function formatSundayBoardMemberCell(m) {
  const st = m.entry_state;
  const hasSel = Array.isArray(m.selections) && m.selections.length > 0;
  if (st === "unset" || (st == null && !hasSel && !m.selection)) {
    return { muted: true, text: "미입력" };
  }
  if (st === "absent" || m.selection === "absent") {
    return { muted: true, text: "불참" };
  }
  const keys = hasSel
    ? [...m.selections].sort((a, b) => sundayBoardKeyOrder(a) - sundayBoardKeyOrder(b))
    : m.selection && m.selection !== "absent"
      ? [m.selection]
      : [];
  if (!keys.length) {
    return { muted: true, text: "미입력" };
  }
  return { muted: false, keys };
}

function memberHasSundayOnSite(m) {
  const keys =
    Array.isArray(m.selections) && m.selections.length
      ? m.selections
      : m.selection && m.selection !== "absent"
        ? [m.selection]
        : [];
  return keys.some((k) => sundaySelectionOnSite(k));
}

/**
 * 팀 출석판 열 안 정렬: 미입력 → 서울 → 인천 → 온라인 → 지교회 → 불참, 같은 그룹은 이름 순.
 * @returns {number} 0..5
 */
function sundayMemberSortGroup(m) {
  const st = m.entry_state;
  const hasSel = Array.isArray(m.selections) && m.selections.length > 0;
  const keys = hasSel
    ? m.selections
    : m.selection && m.selection !== "absent"
      ? [m.selection]
      : [];
  if (st === "unset" || (st == null && !hasSel && !m.selection)) return 0;
  if (st === "absent" || m.selection === "absent") return 5;
  if (!keys.length) return 0;
  const hasSeoul = keys.some((k) => String(k).startsWith("seoul_"));
  const hasIncheon = keys.some((k) => String(k).startsWith("incheon_"));
  const hasOnline = keys.includes("online");
  const hasBranch = keys.includes("branch");
  if (hasSeoul) return 1;
  if (hasIncheon) return 2;
  if (hasOnline) return 3;
  if (hasBranch) return 4;
  return 0;
}

function compareSundayMembersForBoard(a, b) {
  const ga = sundayMemberSortGroup(a);
  const gb = sundayMemberSortGroup(b);
  if (ga !== gb) return ga - gb;
  return (a.member_name || "").localeCompare(b.member_name || "", "ko");
}

let charts = { sunVenue: null, sunPart: null, sunTeam: null, midweek: null };
/** @type {Record<string, object>} week_sunday → 주차 rollup API 한 행 */
let weekRollups = {};

const SERVICE_TYPE_LABELS = {
  sunday: "주일",
  wednesday: "수요",
  saturday: "토요",
};

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

function weekdayKoFromIso(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  const ko = ["일", "월", "화", "수", "목", "금", "토"];
  return ko[dt.getDay()];
}

function serviceDateForOption(serviceType, weekSunday) {
  if (serviceType === "wednesday") return addDaysToIsoDate(weekSunday, -4);
  if (serviceType === "saturday") return addDaysToIsoDate(weekSunday, -1);
  return weekSunday;
}

function presentCountForOption(serviceType, rollup) {
  if (!rollup) return 0;
  if (serviceType === "wednesday") return rollup.wednesday_record_count ?? 0;
  if (serviceType === "saturday") return rollup.saturday_record_count ?? 0;
  return rollup.sunday_present_count ?? 0;
}

function formatDayOption(serviceType, weekSunday, rollup) {
  const serviceDate = serviceDateForOption(serviceType, weekSunday);
  if (!serviceDate) return "—";
  const y = parseInt(serviceDate.slice(0, 4), 10);
  const m = parseInt(serviceDate.slice(5, 7), 10);
  const day = parseInt(serviceDate.slice(8, 10), 10);
  const wd = weekdayKoFromIso(serviceDate);
  const svcLabel = SERVICE_TYPE_LABELS[serviceType] || serviceType;
  const count = presentCountForOption(serviceType, rollup);
  return `${y}년 ${m}월 ${day}일 (${wd}) · ${svcLabel} · ${count}명`;
}

function parseWeekSelectValue(raw) {
  if (!raw) return { serviceType: "", weekSunday: "" };
  const pipe = raw.indexOf("|");
  if (pipe === -1) return { serviceType: "sunday", weekSunday: raw };
  return { serviceType: raw.slice(0, pipe), weekSunday: raw.slice(pipe + 1) };
}

function selectedWeekSunday() {
  return parseWeekSelectValue(document.getElementById("weekId").value).weekSunday;
}

function selectedServiceType() {
  return parseWeekSelectValue(document.getElementById("weekId").value).serviceType;
}

function syncWorshipTypeFromWeekSelect() {
  const st = selectedServiceType();
  const sel = document.getElementById("worshipType");
  if (!sel || !st) return;
  if ([...sel.options].some((o) => o.value === st)) sel.value = st;
}

function buildDayOptionsFromRollups(list) {
  const options = [];
  list.forEach((w) => {
    const ws = w.week_sunday;
    if (!ws) return;
    ["sunday", "wednesday", "saturday"].forEach((serviceType) => {
      options.push({
        value: `${serviceType}|${ws}`,
        label: formatDayOption(serviceType, ws, w),
        service_date: serviceDateForOption(serviceType, ws),
        service_type: serviceType,
        week_sunday: ws,
      });
    });
  });
  options.sort((a, b) => (a.service_date < b.service_date ? 1 : -1));
  return options;
}

function absDiffDaysIso(aIso, bIso) {
  const [y1, m1, d1] = aIso.split("-").map(Number);
  const [y2, m2, d2] = bIso.split("-").map(Number);
  const a = Date.UTC(y1, m1 - 1, d1);
  const b = Date.UTC(y2, m2 - 1, d2);
  return Math.abs(a - b) / 86400000;
}

function pickNearestDayOption(options) {
  if (!options.length) return "";
  const todayIso = isoDateTodayLocal();
  let best = null;
  let bestDiff = Infinity;
  let bestIsFuture = false;
  for (const o of options) {
    if (!o.service_date) continue;
    const diff = absDiffDaysIso(o.service_date, todayIso);
    const isFuture = o.service_date >= todayIso;
    if (diff < bestDiff || (diff === bestDiff && isFuture && !bestIsFuture)) {
      best = o.value;
      bestDiff = diff;
      bestIsFuture = isFuture;
    }
  }
  return best || options[0].value;
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
    const nextPath = location.pathname + location.search;
    window.location = "/login/?next=" + encodeURIComponent(nextPath);
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
  worshipTypes
    .filter((o) => ["sunday", "wednesday", "saturday"].includes(o.value))
    .forEach((o) => {
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
  const groups = new Map();
  list.forEach((d) => {
    const key = d.region_code || "_none";
    const label = d.region_name || "(지역 미지정)";
    if (!groups.has(key)) groups.set(key, { label, items: [] });
    groups.get(key).items.push(d);
  });
  const hasMultipleRegions = groups.size > 1;
  groups.forEach((group) => {
    const container = hasMultipleRegions
      ? document.createElement("optgroup")
      : sel;
    if (hasMultipleRegions) {
      container.label = group.label;
      sel.appendChild(container);
    }
    group.items.forEach((d) => {
      const opt = document.createElement("option");
      opt.value = d.code;
      opt.textContent = d.name + " (" + d.code + ")";
      container.appendChild(opt);
    });
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
  const prev = sel.value;
  sel.innerHTML = "";
  weekRollups = {};
  if (!code) {
    if (document.getElementById("divisionCode").options.length > 0) {
      setStatus("부서를 선택한 뒤 예배일을 불러옵니다.", true);
    }
    return;
  }
  const listRaw = await apiGet("/attendance/weeks/?division_code=" + encodeURIComponent(code));
  const list = Array.isArray(listRaw) ? listRaw : [];
  list.forEach((w) => {
    weekRollups[w.week_sunday] = w;
  });
  const options = buildDayOptionsFromRollups(list);
  options.forEach((o) => {
    const opt = document.createElement("option");
    opt.value = o.value;
    opt.textContent = o.label;
    sel.appendChild(opt);
  });
  if (options.length) {
    const keep = prev && [...sel.options].some((opt) => opt.value === prev) ? prev : pickNearestDayOption(options);
    sel.value = keep;
    syncWorshipTypeFromWeekSelect();
  }
  if (options.length === 0) setStatus("해당 부서에 집계할 출석 데이터가 없습니다.", true);
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
  const sun = wtype === "sunday";
  const mw = wtype === "wednesday" || wtype === "saturday";
  document.getElementById("cardSunVenue").style.display = sun ? "block" : "none";
  document.getElementById("cardSunPart").style.display = sun ? "block" : "none";
  document.getElementById("cardSunTeam").style.display = sun ? "block" : "none";
  document.getElementById("cardMw").style.display = mw ? "block" : "none";
  document.getElementById("panelSunday").style.display = sun ? "block" : "none";
  document.getElementById("panelMidweek").style.display = mw ? "block" : "none";
}

async function loadSummary() {
  syncWorshipTypeFromWeekSelect();
  const wid = selectedWeekSunday();
  const code = (document.getElementById("divisionCode").value || "").trim();
  const wtype = selectedServiceType();
  showChartCards(wtype);
  if (!wid || !code || !wtype) {
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
  const wid = selectedWeekSunday();
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
  const wid = selectedWeekSunday();
  if (!wid) return;
  const code = (document.getElementById("divisionCode").value || "").trim();
  if (!code) return;
  const wtype = selectedServiceType();
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
    else if (wtype === "wednesday" || wtype === "saturday") p.set("service_type", wtype);
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
    syncWorshipTypeFromWeekSelect();
    if (getDashboardTab() === "board") {
      await window.loadAttendanceExcelBoard();
      setStatus("");
      return;
    }
    await loadSummary();
    const wtype = selectedServiceType();
    if (wtype === "sunday") await loadSunTable();
    else document.getElementById("tbodySun").innerHTML = "";
    if (wtype === "wednesday" || wtype === "saturday") await loadMwTable();
    else document.getElementById("tbodyMw").innerHTML = "";
    const divSel = document.getElementById("divisionCode");
    const code = (divSel.value || "").trim();
    const wid = selectedWeekSunday();
    const w = weekRollups[wid];
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
    if (!wid || !wtype) {
      if (document.getElementById("weekId").options.length === 0) {
        setStatus("해당 부서에 집계할 출석 데이터가 없습니다.", true);
      } else {
        setStatus("예배일을 선택하세요.", true);
      }
      return;
    }
    if (w) {
      setStatus(formatDayOption(wtype, wid, w));
    } else {
      setStatus("예배일 정보를 불러오지 못했습니다.");
    }
  } catch (e) {
    console.error(e);
    setStatus("오류: " + e.message, true);
  }
}

function getDashboardTab() {
  const u = new URL(window.location.href);
  return u.searchParams.get("tab") === "board" ? "board" : "stats";
}

function applyDashboardTab() {
  const tab = getDashboardTab();
  const stats = document.getElementById("dashboardPanelStats");
  const board = document.getElementById("dashboardPanelBoard");
  const tabStats = document.getElementById("dashboardTabStats");
  const tabBoard = document.getElementById("dashboardTabBoard");
  if (!stats || !board) return;
  const isBoard = tab === "board";
  stats.style.display = isBoard ? "none" : "";
  board.style.display = isBoard ? "block" : "none";
  if (tabStats) tabStats.classList.toggle("is-active", !isBoard);
  if (tabBoard) tabBoard.classList.toggle("is-active", isBoard);
}

function setDashboardTab(tab) {
  const u = new URL(window.location.href);
  if (tab === "board") u.searchParams.set("tab", "board");
  else u.searchParams.delete("tab");
  window.history.replaceState({}, "", u);
  applyDashboardTab();
  refreshAll();
}

function sundaySelectionOnSite(sel) {
  if (!sel || sel === "absent") return false;
  return String(sel).startsWith("seoul_") || String(sel).startsWith("incheon_");
}

function renderExcelSundayBoard(data, host, totalEl, metaEl) {
  const teams = Array.isArray(data.teams) ? data.teams : [];
  let sumOnSite = 0;
  host.innerHTML = "";
  teams.forEach((t) => {
    const members = Array.isArray(t.members) ? [...t.members].sort(compareSundayMembersForBoard) : [];
    let onSite = 0;
    const col = document.createElement("div");
    col.className = "jcc-excel-col";
    const head = document.createElement("div");
    head.className = "jcc-excel-col-head";
    head.textContent = t.team_name || "팀";
    const sub = document.createElement("div");
    sub.className = "jcc-excel-col-sub";
    members.forEach((m) => {
      if (memberHasSundayOnSite(m)) onSite += 1;
    });
    sub.textContent = "현장 " + onSite;
    sumOnSite += onSite;
    col.appendChild(head);
    col.appendChild(sub);
    const body = document.createElement("div");
    body.className = "jcc-excel-col-body";
    members.forEach((m) => {
      const row = document.createElement("div");
      row.className = "jcc-excel-row";
      const name = document.createElement("span");
      name.className = "jcc-excel-name";
      name.textContent = m.member_name || "—";
      const mark = document.createElement("span");
      const cell = formatSundayBoardMemberCell(m);
      mark.className = "jcc-excel-mark" + (cell.muted ? " jcc-excel-mark--muted" : "");
      if (cell.muted) {
        mark.textContent = cell.text;
      } else {
        fillSundayMarkStructured(mark, cell.keys);
      }
      row.appendChild(name);
      row.appendChild(mark);
      body.appendChild(row);
    });
    col.appendChild(body);
    host.appendChild(col);
  });
  if (totalEl) {
    totalEl.innerHTML = "";
    const strong = document.createElement("strong");
    strong.textContent = "현장 합계 " + sumOnSite;
    totalEl.appendChild(strong);
  }
  if (metaEl && data.service_date) {
    metaEl.textContent = "예배일 " + data.service_date + " · 주일";
  }
}

function renderExcelMidweekBoard(data, host, totalEl, metaEl) {
  const teams = Array.isArray(data.teams) ? data.teams : [];
  let sumOnSite = 0;
  host.innerHTML = "";
  const stLabel = data.service_type === "wednesday" ? "수요" : "토요";
  teams.forEach((t) => {
    const members = Array.isArray(t.members) ? t.members : [];
    let onSite = 0;
    const col = document.createElement("div");
    col.className = "jcc-excel-col";
    const head = document.createElement("div");
    head.className = "jcc-excel-col-head";
    head.textContent = t.team_name || "팀";
    const sub = document.createElement("div");
    sub.className = "jcc-excel-col-sub";
    members.forEach((m) => {
      if (m.status === "present") onSite += 1;
    });
    sub.textContent = "현장 " + onSite;
    sumOnSite += onSite;
    col.appendChild(head);
    col.appendChild(sub);
    const body = document.createElement("div");
    body.className = "jcc-excel-col-body";
    members.forEach((m) => {
      const row = document.createElement("div");
      row.className = "jcc-excel-row";
      const name = document.createElement("span");
      name.className = "jcc-excel-name";
      name.textContent = m.member_name || "—";
      const mark = document.createElement("span");
      let txt = "불참";
      let muted = true;
      if (m.entry_state === "unset") {
        txt = "미입력";
      } else if (m.status === "online") {
        txt = "온라인";
        muted = false;
      } else if (m.status === "present") {
        txt = "참석";
        muted = false;
      }
      mark.className = "jcc-excel-mark" + (muted ? " jcc-excel-mark--muted" : "");
      mark.textContent = txt;
      row.appendChild(name);
      row.appendChild(mark);
      body.appendChild(row);
    });
    col.appendChild(body);
    host.appendChild(col);
  });
  if (totalEl) {
    totalEl.innerHTML = "";
    const strong = document.createElement("strong");
    strong.textContent = "현장 합계 " + sumOnSite;
    totalEl.appendChild(strong);
  }
  if (metaEl && data.service_date) {
    metaEl.textContent = "예배일 " + data.service_date + " · " + stLabel;
  }
}

window.loadAttendanceExcelBoard = async function loadAttendanceExcelBoard() {
  const host = document.getElementById("attendanceExcelBoard");
  const statusEl = document.getElementById("boardStatusLine");
  const totalEl = document.getElementById("excelBoardTotal");
  const metaEl = document.getElementById("excelBoardMeta");
  if (!host) return;
  syncWorshipTypeFromWeekSelect();
  const wid = selectedWeekSunday();
  const code = (document.getElementById("divisionCode").value || "").trim();
  const wtype = selectedServiceType();
  if (!code || !wid || !wtype) {
    host.innerHTML = "";
    if (totalEl) totalEl.textContent = "";
    if (metaEl) metaEl.textContent = "";
    if (statusEl) {
      statusEl.textContent = "부서와 예배일을 선택하세요.";
      statusEl.className = "msg err";
    }
    return;
  }
  if (statusEl) {
    statusEl.textContent = "불러오는 중…";
    statusEl.className = "msg";
  }
  try {
    if (wtype === "sunday") {
      const path =
        "/attendance/weeks/" +
        encodeURIComponent(wid) +
        "/roster/sunday/?division_code=" +
        encodeURIComponent(code);
      const data = await apiGet(path);
      if (!data.teams || !data.teams.length) {
        host.innerHTML = '<div class="msg">표시할 팀·멤버가 없습니다.</div>';
        if (totalEl) totalEl.textContent = "";
        if (metaEl) metaEl.textContent = "";
      } else {
        renderExcelSundayBoard(data, host, totalEl, metaEl);
      }
    } else {
      const path =
        "/attendance/weeks/" +
        encodeURIComponent(wid) +
        "/roster/midweek/?division_code=" +
        encodeURIComponent(code) +
        "&service_type=" +
        encodeURIComponent(wtype);
      const data = await apiGet(path);
      if (!data.teams || !data.teams.length) {
        host.innerHTML = '<div class="msg">표시할 팀·멤버가 없습니다.</div>';
        if (totalEl) totalEl.textContent = "";
        if (metaEl) metaEl.textContent = "";
      } else {
        renderExcelMidweekBoard(data, host, totalEl, metaEl);
      }
    }
    if (statusEl) {
      statusEl.textContent = "";
      statusEl.className = "msg";
    }
  } catch (e) {
    console.error(e);
    host.innerHTML = "";
    if (totalEl) totalEl.textContent = "";
    if (metaEl) metaEl.textContent = "";
    if (statusEl) {
      statusEl.textContent = "오류: " + e.message;
      statusEl.className = "msg err";
    }
  }
};

function bindUi() {
  document.getElementById("btnRefresh").onclick = refreshAll;
  document.getElementById("btnApplySun").onclick = () => loadSunTable();
  document.getElementById("btnApplyMw").onclick = () => loadMwTable();
  const tabStats = document.getElementById("dashboardTabStats");
  const tabBoard = document.getElementById("dashboardTabBoard");
  if (tabStats)
    tabStats.onclick = () => {
      setDashboardTab("stats");
    };
  if (tabBoard)
    tabBoard.onclick = () => {
      setDashboardTab("board");
    };
  document.getElementById("divisionCode").onchange = async () => {
    if (!DASHBOARD_ACCESS.canChangeDivision) return;
    await loadWeeks();
    await loadTeams();
    await refreshAll();
  };
  document.getElementById("weekId").onchange = () => {
    syncWorshipTypeFromWeekSelect();
    refreshAll();
  };
}

async function init() {
  bindUi();
  try {
    await loadMeta();
    await loadDivisions();
    await loadWeeks();
    await loadTeams();
    applyDashboardTab();
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
