/**
 * 교적부 입력(출석 명단) - 목록 페이지 JS
 * - /attendance/roster/ 로 진입해서 division/week 선택 후 edit로 이동
 */
const API = "/api/v1";

function setStatus(msg, isErr) {
  const el = document.getElementById("statusLine");
  el.textContent = msg || "";
  el.className = "msg" + (isErr ? " err" : "");
}

async function apiGet(path) {
  const r = await fetch(API + path, { credentials: "same-origin" });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json();
}

function addDaysToIsoDate(iso, n) {
  const [y, mo, d] = iso.split("-").map(Number);
  // local date (브라우저 now 기준)
  const dt = new Date(y, mo - 1, d);
  dt.setDate(dt.getDate() + n);
  const yy = dt.getFullYear();
  const mm = String(dt.getMonth() + 1).padStart(2, "0");
  const dd = String(dt.getDate()).padStart(2, "0");
  return `${yy}-${mm}-${dd}`;
}

function isoDateTodayLocal() {
  const u = new Date();
  const yy = u.getFullYear();
  const mm = String(u.getMonth() + 1).padStart(2, "0");
  const dd = String(u.getDate()).padStart(2, "0");
  return `${yy}-${mm}-${dd}`;
}

function weekSundayOnOrAfterTodayLocal() {
  const todayIso = isoDateTodayLocal();
  const u = new Date();
  const jsDay = u.getDay(); // 0=Sun..6=Sat
  const pyWeekday = (jsDay + 6) % 7; // 0=Mon..6=Sun
  const offset = (6 - pyWeekday) % 7;
  return addDaysToIsoDate(todayIso, offset);
}

function getQueryParam(name) {
  const u = new URL(window.location.href);
  return u.searchParams.get(name);
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
  if ([...sel.options].some((o) => o.value === "youth")) sel.value = "youth";
}

async function loadWeeks() {
  const code = (document.getElementById("divisionCode").value || "").trim();
  const sel = document.getElementById("weekId");
  sel.innerHTML = "";

  if (!code) return;
  const listRaw = await apiGet("/attendance/weeks/?division_code=" + encodeURIComponent(code));
  const list = Array.isArray(listRaw) ? listRaw : [];
  list.forEach((w) => {
    const opt = document.createElement("option");
    opt.value = w.week_sunday;
    opt.textContent = w.week_sunday + " · " + w.division_name;
    sel.appendChild(opt);
  });

  if (!list.length) return;

  // 기본: 현재 날짜 기준 -1주차 (사용자 요구)
  const curWeekSunday = weekSundayOnOrAfterTodayLocal();
  const wantedPrev = addDaysToIsoDate(curWeekSunday, -7);
  const opts = [...sel.options].map((o) => o.value);
  const exact = opts.find((v) => v === wantedPrev);
  if (exact) {
    sel.value = exact;
    return;
  }
  let best = null;
  for (const v of opts) {
    if (v <= wantedPrev) {
      if (!best || v > best) best = v;
    }
  }
  sel.value = best || opts[opts.length - 1];
}

function navigateEdit({ mode, service_type }) {
  const code = document.getElementById("divisionCode").value;
  const wid = document.getElementById("weekId").value;
  const svc = service_type || document.getElementById("svcType").value;
  const url = new URL(window.location.origin + "/attendance/roster/edit/");
  url.searchParams.set("mode", mode);
  url.searchParams.set("division_code", code);
  url.searchParams.set("week_sunday", wid);
  if (mode === "midweek") url.searchParams.set("service_type", svc);
  window.location = url.toString();
}

function bindUi() {
  document.getElementById("btnSunday").onclick = () =>
    navigateEdit({ mode: "sunday" });
  document.getElementById("btnMidweek").onclick = () =>
    navigateEdit({ mode: "midweek" });
  document.getElementById("divisionCode").onchange = async () => {
    await loadWeeks();
  };
  document.getElementById("weekId").onchange = async () => {};
}

async function init() {
  bindUi();
  try {
    await loadDivisions();
    await loadWeeks();
  } catch (e) {
    console.error(e);
    setStatus("초기화 실패: " + e.message, true);
  }
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
else init();

