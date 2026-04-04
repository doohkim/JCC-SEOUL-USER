/**
 * 탭 출석부 프론트:
 * - 팀원 리스트(팀별 카드) 표시
 * - 팀원 클릭 → 팝업(주일: 다중선택 / 수·토: 참석/불참)
 * - 저장 후 리스트 갱신
 */

const API = "/api/v1";

const TEAM_ROSTER_ACCESS = (() => {
  const el = document.getElementById("teamRosterAccessData");
  if (!el) return { allowed_division_codes: [], is_superuser: false };
  try {
    return JSON.parse(el.textContent || "{}");
  } catch (e) {
    return { allowed_division_codes: [], is_superuser: false };
  }
})();

const SUNDAY_OPTIONS = [
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

const SUNDAY_SEOUL_KEYS = new Set(["seoul_1", "seoul_2", "seoul_3", "seoul_4"]);
const SUNDAY_INCHEON_KEYS = new Set(["incheon_1", "incheon_2", "incheon_3", "incheon_4"]);
const SUNDAY_VENUE_KEYS = new Set([...SUNDAY_SEOUL_KEYS, ...SUNDAY_INCHEON_KEYS]);
const SUNDAY_REMOTE_KEYS = new Set(["online", "branch"]);

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
 * 대시보드 주일 출석판과 동일: 서울/인천은 첫 줄 1·2부, 이후 들여쓰기 줄.
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

/** 팀 출석판과 동일: 미입력 → 서울 → 인천 → 온라인 → 지교회 → 불참 */
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

function setStatus(msg, isErr) {
  const el = document.getElementById("statusLine");
  if (!el) return;
  el.textContent = msg || "";
  el.className = "msg" + (isErr ? " err" : "");
}

function isDivisionAllowed(code) {
  if (TEAM_ROSTER_ACCESS.is_superuser) return true;
  const allowed = TEAM_ROSTER_ACCESS.allowed_division_codes;
  if (!Array.isArray(allowed)) return false;
  return allowed.includes(code);
}

function renderNoAccess() {
  const noAccessWrap = document.getElementById("noAccessWrap");
  if (noAccessWrap) noAccessWrap.style.display = "block";
  const boardWrap = document.getElementById("boardWrap");
  if (boardWrap) boardWrap.innerHTML = "";
  setStatus("");
  const hint = document.getElementById("teamRosterReadOnlyHint");
  if (hint) {
    hint.style.display = "none";
    hint.textContent = "";
  }
}

/** API의 can_edit과 동기화: 수정 불가 시 이유 안내 */
function updateReadOnlyHint() {
  const el = document.getElementById("teamRosterReadOnlyHint");
  if (!el) return;
  if (state.can_edit) {
    el.style.display = "none";
    el.textContent = "";
    return;
  }
  el.style.display = "block";
  el.textContent =
    "이 화면에서 수정할 수 있는 팀이 없습니다. 부서에 팀이 있는지, 또는 API 권한 오류인지 확인해 주세요.";
}

function renderAccessEmpty() {
  const noAccessWrap = document.getElementById("noAccessWrap");
  if (noAccessWrap) noAccessWrap.style.display = "none";
}

function getCookie(name) {
  const v = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
  return v ? decodeURIComponent(v[2]) : "";
}

/** API 오류 본문(JSON/HTML)에서 사용자에게 보여줄 문장만 추출 */
function humanizeApiErrorBody(raw) {
  if (raw == null) return "";
  const s = String(raw).trim();
  if (!s) return "";
  if (s.startsWith("{") || s.startsWith("[")) {
    try {
      const j = JSON.parse(s);
      if (Array.isArray(j)) {
        return j.map((x) => (typeof x === "string" ? x : JSON.stringify(x))).join(" ");
      }
      if (j && typeof j === "object") {
        if (Array.isArray(j.detail)) {
          return j.detail.map((x) => String(x)).filter(Boolean).join(" ");
        }
        if (typeof j.detail === "string") return j.detail;
        if (Array.isArray(j.non_field_errors)) {
          return j.non_field_errors.map((x) => String(x)).filter(Boolean).join(" ");
        }
        if (j.detail && typeof j.detail === "object" && !Array.isArray(j.detail)) {
          return Object.entries(j.detail)
            .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(" ") : v}`)
            .join(" ");
        }
        if (typeof j.message === "string") return j.message;
      }
    } catch (_) {
      return s;
    }
  }
  return s;
}

/** 모달 상태 줄: 일반 텍스트 또는 에러 알림 박스 */
function setModalStatus(el, text, variant) {
  if (!el) return;
  el.classList.remove("jcc-modal-status--error");
  el.innerHTML = "";
  if (variant === "error") {
    if (!text) return;
    el.classList.add("jcc-modal-status--error");
    const wrap = document.createElement("div");
    wrap.className = "jcc-modal-alert";
    wrap.setAttribute("role", "alert");
    const icon = document.createElement("span");
    icon.className = "jcc-modal-alert-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = "!";
    const p = document.createElement("p");
    p.className = "jcc-modal-alert-text";
    p.textContent = text;
    wrap.appendChild(icon);
    wrap.appendChild(p);
    el.appendChild(wrap);
    return;
  }
  el.textContent = text || "";
}

async function apiGet(path) {
  const r = await fetch(API + path, { credentials: "same-origin" });
  if (!r.ok) {
    const t = await r.text();
    const msg = humanizeApiErrorBody(t) || r.statusText || `요청 실패 (${r.status})`;
    throw new Error(msg);
  }
  return r.json();
}

async function apiPost(path, payload) {
  const csrftoken = getCookie("csrftoken");
  const r = await fetch(API + path, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "content-type": "application/json",
      "X-CSRFToken": csrftoken,
    },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    const t = await r.text();
    const msg = humanizeApiErrorBody(t) || r.statusText || `요청 실패 (${r.status})`;
    throw new Error(msg);
  }
  return r.json();
}

function addDaysToIsoDate(iso, n) {
  const [y, mo, d] = iso.split("-").map(Number);
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

function isoToLocalDateAtNoon(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  // DST 등으로 하루 경계가 흔들리지 않게 정오로 고정
  dt.setHours(12, 0, 0, 0);
  return dt;
}

function absDiffDaysIso(aIso, bIso) {
  const a = isoToLocalDateAtNoon(aIso);
  const b = isoToLocalDateAtNoon(bIso);
  return Math.abs(a - b) / 86400000;
}

function parseQuery() {
  const u = new URL(window.location.href);
  const division_code = u.searchParams.get("division_code") || "youth";
  const week_sunday = u.searchParams.get("week_sunday") || null;
  const service_type = u.searchParams.get("service_type") || "sunday";
  return { division_code, week_sunday, service_type };
}

function fillButtonSelected(btn, on) {
  if (!btn) return;
  btn.classList.toggle("secondary", !!on);
}

function renderTeamsSunday(teams) {
  const wrap = document.getElementById("boardWrap");
  wrap.innerHTML = "";

  if (!Array.isArray(teams) || !teams.length) {
    wrap.innerHTML = `<div class="msg">표시할 팀원이 없습니다.</div>`;
    return;
  }

  teams.forEach((t) => {
    const card = document.createElement("div");
    card.className = "card";
    card.style.marginBottom = "1.25rem";
    card.innerHTML = `
      <h2 style="margin-bottom:0.6rem;">${t.team_name || "팀"}</h2>
      <div class="team-roster-members" role="list"></div>
    `;

    const membersWrap = card.querySelector(".team-roster-members");
    const rosterMembers = [...(t.members || [])].sort(compareSundayMembersForBoard);
    rosterMembers.forEach((m) => {
      const selections = Array.isArray(m.selections) ? m.selections : [];
      const orderIdx = (k) => {
        const i = SUNDAY_OPTIONS.findIndex((o) => o.key === k);
        return i === -1 ? 999 : i;
      };
      const sortedKeys = [...selections].sort((a, b) => orderIdx(a) - orderIdx(b));

      const entryState = m.entry_state || (sortedKeys.length ? "present" : "unset");
      let disp = "";
      let isMuted = true;
      if (entryState === "unset") {
        disp = "미입력";
      } else if (entryState === "absent") {
        disp = "불참";
      } else if (sortedKeys.length) {
        isMuted = false;
      } else {
        disp = "미입력";
      }

      const row = document.createElement(state.can_edit ? "button" : "div");
      if (state.can_edit) {
        row.type = "button";
        row.addEventListener("click", () => openSundayModal(m, t));
      } else {
        row.setAttribute("role", "listitem");
      }
      row.className = "team-roster-memberRow" + (state.can_edit ? "" : " is-readonly");
      if (isMuted) row.classList.add("is-muted");

      const nameSpan = document.createElement("span");
      nameSpan.className = "team-roster-memberName";
      nameSpan.textContent = m.member_name || "—";
      const valSpan = document.createElement("span");
      valSpan.className = "team-roster-memberValue";
      if (isMuted) {
        valSpan.textContent = disp;
      } else {
        fillSundayMarkStructured(valSpan, sortedKeys);
      }
      row.appendChild(nameSpan);
      row.appendChild(valSpan);
      membersWrap.appendChild(row);
    });

    wrap.appendChild(card);
  });
}

function renderTeamsMidweek(teams) {
  const wrap = document.getElementById("boardWrap");
  wrap.innerHTML = "";

  if (!Array.isArray(teams) || !teams.length) {
    wrap.innerHTML = `<div class="msg">표시할 팀원이 없습니다.</div>`;
    return;
  }

  teams.forEach((t) => {
    const card = document.createElement("div");
    card.className = "card";
    card.style.marginBottom = "1.25rem";
    card.innerHTML = `
      <h2 style="margin-bottom:0.6rem;">${t.team_name || "팀"}</h2>
      <div class="team-roster-members" role="list"></div>
    `;

    const membersWrap = card.querySelector(".team-roster-members");
    (t.members || []).forEach((m) => {
      const row = document.createElement(state.can_edit ? "button" : "div");
      if (state.can_edit) {
        row.type = "button";
        row.addEventListener("click", () => openMidweekModal(m, t));
      } else {
        row.setAttribute("role", "listitem");
      }
      row.className = "team-roster-memberRow" + (state.can_edit ? "" : " is-readonly");

      if (m.entry_state === "unset") row.classList.add("is-muted");

      let st = "불참";
      if (m.entry_state === "unset") st = "미입력";
      else if (m.status === "online") st = "온라인";
      else if (m.status === "present") st = "참석";

      row.innerHTML = `
        <span class="team-roster-memberName">${m.member_name}</span>
        <span class="team-roster-memberValue">${st}</span>
      `;
      membersWrap.appendChild(row);
    });

    wrap.appendChild(card);
  });
}

let state = {
  division_code: "youth",
  week_sunday: null,
  service_type: "sunday", // sunday | wednesday | saturday
  filter_mode: "all", // all | unset
  can_edit: false,
  sundayMember: null,
  sundayTeam: null,
  midweekMember: null,
  midweekTeam: null,
};

function showOverlay(id) {
  const ov = document.getElementById(id);
  if (!ov) return;
  ov.classList.add("show");
  ov.setAttribute("aria-hidden", "false");
}

function hideOverlay(id) {
  const ov = document.getElementById(id);
  if (!ov) return;
  ov.classList.remove("show");
  ov.setAttribute("aria-hidden", "true");
}

function buildSundayOptionUI() {
  const seoul = document.getElementById("sundaySeoulOptions");
  const incheon = document.getElementById("sundayIncheonOptions");
  const remote = document.getElementById("sundayRemoteOptions");
  if (!seoul || !incheon || !remote) return;

  seoul.innerHTML = "";
  incheon.innerHTML = "";
  remote.innerHTML = "";

  SUNDAY_OPTIONS.forEach((opt) => {
    const container = SUNDAY_SEOUL_KEYS.has(opt.key)
      ? seoul
      : SUNDAY_INCHEON_KEYS.has(opt.key)
        ? incheon
        : remote;
    const id = "sundayOpt_" + opt.key;
    const chk = document.createElement("div");
    chk.innerHTML = `
      <label for="${id}" class="sunday-slotChip" style="gap:0.4rem;">
        <input type="checkbox" id="${id}" value="${opt.key}" />
        <span class="sunday-slotChipLabel">${opt.label}</span>
      </label>
    `;
    container.appendChild(chk);
  });

  bindSundayVenueRemoteExclusivity();
}

/**
 * 온라인·지교회 선택 시 서울/인천·상대 원격 옵션·불참 해제 (불참과 동일한 단일 모드).
 * 서울/인천 선택 시 온라인·지교회·불참 해제.
 */
function bindSundayVenueRemoteExclusivity() {
  const inputs = document.querySelectorAll("#sundayEditOverlay input[type='checkbox'][value]");
  inputs.forEach((el) => {
    el.addEventListener("change", () => {
      if (!el.checked) return;
      const key = el.value;
      const absentChk = document.getElementById("sundayAbsentChk");

      if (SUNDAY_REMOTE_KEYS.has(key)) {
        inputs.forEach((other) => {
          if (other !== el) other.checked = false;
        });
        if (absentChk && absentChk.checked) absentChk.checked = false;
        setSundayAbsentState(false);
        return;
      }

      if (SUNDAY_VENUE_KEYS.has(key)) {
        inputs.forEach((other) => {
          if (SUNDAY_REMOTE_KEYS.has(other.value)) other.checked = false;
        });
        if (absentChk && absentChk.checked) absentChk.checked = false;
        setSundayAbsentState(false);
      }
    });
  });
}

function getSundaySelectedKeys() {
  const absentChk = document.getElementById("sundayAbsentChk");
  const keys = [];
  if (absentChk && absentChk.checked) return keys;
  const checked = document.querySelectorAll("#sundayEditOverlay input[type='checkbox']:checked");
  checked.forEach((el) => {
    if (el && el.value) keys.push(el.value);
  });
  // absent 체크박스는 value가 없으니 제외됨.
  return keys;
}

function setSundayAbsentState(isAbsent) {
  const absentChk = document.getElementById("sundayAbsentChk");
  if (!absentChk) return;
  absentChk.checked = isAbsent;

  // 불참이면 다른 참석 선택(서울/인천/온라인)을 모두 해제하고 못 누르게
  const all = document.querySelectorAll(
    "#sundayEditOverlay input[type='checkbox'][value]"
  );
  all.forEach((el) => {
    if (isAbsent) el.checked = false;
    el.disabled = isAbsent;
  });
}

function openSundayModal(member, team) {
  if (!state.can_edit) return;
  state.sundayMember = member;
  state.sundayTeam = team;
  const weekSel = document.getElementById("weekId");
  const ws = (state.week_sunday || (weekSel ? weekSel.value : null) || "") + "";
  const nameEl = document.getElementById("sundayEditMemberName");
  if (nameEl) nameEl.textContent = member.member_name;

  const dateEl = document.getElementById("sundayEditServiceDate");
  if (dateEl) {
    dateEl.textContent = ws ? `${ws} · 주일예배` : "";
  }

  buildSundayOptionUI();

  const entryState = member.entry_state || "unset";
  const current = Array.isArray(member.selections) ? member.selections : [];
  const isAbsent = entryState === "absent";
  setSundayAbsentState(isAbsent);

  if (entryState === "present") {
    current.forEach((key) => {
      const chk = document.getElementById("sundayOpt_" + key);
      if (chk) chk.checked = true;
    });
  }

  const st = document.getElementById("sundayEditStatus");
  setModalStatus(
    st,
    isAbsent ? "불참을 선택했습니다. 다른 참석 선택은 해제됩니다." : "",
    "plain"
  );

  showOverlay("sundayEditOverlay");
}

function openMidweekModal(member, team) {
  if (!state.can_edit) return;
  state.midweekMember = member;
  state.midweekTeam = team;
  const weekSel = document.getElementById("weekId");
  const ws = (state.week_sunday || (weekSel ? weekSel.value : null) || "") + "";

  const nameEl = document.getElementById("midweekEditMemberName");
  if (nameEl) nameEl.textContent = member.member_name;

  const dateEl = document.getElementById("midweekEditServiceDate");
  if (dateEl) {
    const svc =
      state.service_type === "wednesday"
        ? addDaysToIsoDate(ws, -4)
        : addDaysToIsoDate(ws, -1);
    const label = state.service_type === "wednesday" ? "수요예배" : "토요예배";
    dateEl.textContent = svc ? `${svc} · ${label}` : "";
  }

  const st = document.getElementById("midweekEditStatus");
  setModalStatus(st, "", "plain");

  const presentBtn = document.getElementById("btnMidweekPresent");
  const absentBtn = document.getElementById("btnMidweekAbsent");
  const isPresent = member.status === "present";
  if (presentBtn && absentBtn) {
    if (member.entry_state === "unset") {
      presentBtn.classList.remove("secondary");
      absentBtn.classList.remove("secondary");
    } else {
      presentBtn.classList.toggle("secondary", isPresent);
      absentBtn.classList.toggle("secondary", !isPresent);
    }
  }

  showOverlay("midweekEditOverlay");
}

function getMidweekSelection() {
  const presentBtn = document.getElementById("btnMidweekPresent");
  const absentBtn = document.getElementById("btnMidweekAbsent");
  const isPresent = presentBtn && presentBtn.classList.contains("secondary");
  const isAbsent = absentBtn && absentBtn.classList.contains("secondary");
  if (isPresent) return "present";
  if (isAbsent) return "absent";
  return "unset";
}

async function saveSundayModal() {
  if (!state.sundayMember) return;
  const absentChk = document.getElementById("sundayAbsentChk");
  const isAbsent = absentChk && absentChk.checked;
  // 불참이면 서버에 참석 선택값을 절대 보내지 않도록 강제
  const keys = isAbsent ? [] : getSundaySelectedKeys();
  const member_id = Number(state.sundayMember.member_id);

  const entry_state = isAbsent ? "absent" : keys.length ? "present" : "unset";

  const statusEl = document.getElementById("sundayEditStatus");
  setModalStatus(statusEl, "저장 중…", "plain");

  const payload = {
    updates: [
      {
        member_id,
        entry_state,
        selections: keys,
      },
    ],
  };

  await apiPost(
    `/attendance/team/weeks/${encodeURIComponent(state.week_sunday)}/roster/sunday/?division_code=${encodeURIComponent(
      state.division_code
    )}`,
    payload
  );

  hideOverlay("sundayEditOverlay");
  await loadBoard();
}

async function saveMidweekModal() {
  if (!state.midweekMember) return;
  const member_id = Number(state.midweekMember.member_id);
  const statusKey = getMidweekSelection(); // present|absent|unset

  const statusEl = document.getElementById("midweekEditStatus");
  setModalStatus(statusEl, "저장 중…", "plain");

  const payload = {
    updates: [
      {
        member_id,
        status: statusKey,
      },
    ],
  };

  await apiPost(
    `/attendance/team/weeks/${encodeURIComponent(state.week_sunday)}/roster/midweek/?division_code=${encodeURIComponent(
      state.division_code
    )}&service_type=${encodeURIComponent(state.service_type)}`,
    payload
  );

  hideOverlay("midweekEditOverlay");
  await loadBoard();
}

async function loadDivisions() {
  const raw = await apiGet("/attendance/divisions/");
  const list = Array.isArray(raw) ? raw : [];
  const sel = document.getElementById("divisionCode");
  sel.innerHTML = "";
  list.forEach((d) => {
    const opt = document.createElement("option");
    opt.value = d.code;
    opt.textContent = d.name;
    if (!isDivisionAllowed(d.code)) opt.disabled = true;
    sel.appendChild(opt);
  });

  const curAllowed =
    state.division_code &&
    [...sel.options].some((o) => o.value === state.division_code && !o.disabled);
  if (curAllowed) {
    sel.value = state.division_code;
    return;
  }

  const firstAllowed = [...sel.options].find((o) => !o.disabled);
  sel.value = firstAllowed ? firstAllowed.value : "";

  // 읽기전용이므로 사용자 변경 이벤트 제거
  sel.disabled = true;
}

async function loadWeeks() {
  const sel = document.getElementById("weekId");
  sel.innerHTML = "";
  const division_code = document.getElementById("divisionCode").value;
  const listRaw = await apiGet(
    `/attendance/weeks/?division_code=${encodeURIComponent(division_code)}&limit=104`
  );
  const list = Array.isArray(listRaw) ? listRaw : [];

  // value: "<service_type>|<week_sunday>"
  const options = [];
  list.forEach((w) => {
    const ws = w.week_sunday;
    options.push({
      value: `sunday|${ws}`,
      label: `${ws} · 주일예배`,
      service_date: ws,
    });
    options.push({
      value: `wednesday|${ws}`,
      label: `${addDaysToIsoDate(ws, -4)} · 수요예배`,
      service_date: addDaysToIsoDate(ws, -4),
    });
    options.push({
      value: `saturday|${ws}`,
      label: `${addDaysToIsoDate(ws, -1)} · 토요예배`,
      service_date: addDaysToIsoDate(ws, -1),
    });
  });

  options.sort((a, b) => (a.service_date < b.service_date ? 1 : -1));

  options.forEach((o) => {
    const opt = document.createElement("option");
    opt.value = o.value;
    opt.textContent = o.label;
    sel.appendChild(opt);
  });

  const pickValue = () => {
    if (state.week_sunday && state.service_type) {
      const candidate = `${state.service_type}|${state.week_sunday}`;
      if ([...sel.options].some((opt) => opt.value === candidate)) return candidate;
    }
    // 기본값: "오늘"과 가장 가까운 예배일을 선택한다(과거/미래 모두 허용).
    // tie-break: 같은 거리면 미래(오늘 포함 이후)를 우선한다.
    const todayIso = isoDateTodayLocal();
    let best = null;
    let bestDiff = Infinity;
    let bestIsFuture = false;
    for (const o of options) {
      if (!o.service_date) continue;
      const diff = absDiffDaysIso(o.service_date, todayIso);
      const isFuture = o.service_date >= todayIso; // ISO 날짜 문자열은 사전식 비교가 날짜 순서와 일치
      if (diff < bestDiff || (diff === bestDiff && isFuture && !bestIsFuture)) {
        best = o.value;
        bestDiff = diff;
        bestIsFuture = isFuture;
      }
    }
    return best || (sel.options.length ? sel.options[0].value : "");
  };

  const chosen = pickValue();
  sel.value = chosen;
  if (chosen) {
    const [st, ws] = chosen.split("|");
    state.service_type = st;
    state.week_sunday = ws;
  } else {
    state.week_sunday = null;
  }
}

function bindUi() {
  document.getElementById("divisionCode").addEventListener("change", async () => {
    state.division_code = document.getElementById("divisionCode").value;
    state.week_sunday = null;
    await loadWeeks();
    if (!state.division_code || !isDivisionAllowed(state.division_code)) {
      renderNoAccess();
      return;
    }
    renderAccessEmpty();
    await loadBoard();
  });

  document.getElementById("weekId").addEventListener("change", async () => {
    const v = document.getElementById("weekId").value || "";
    const [st, ws] = v.split("|");
    if (st) state.service_type = st;
    state.week_sunday = ws || null;
    if (!state.division_code || !isDivisionAllowed(state.division_code)) {
      renderNoAccess();
      return;
    }
    renderAccessEmpty();
    await loadBoard();
  });

  const btnAll = document.getElementById("filterAll");
  const btnUnset = document.getElementById("filterUnset");
  if (btnAll && btnUnset) {
    btnAll.addEventListener("click", async () => {
      state.filter_mode = "all";
      btnAll.classList.remove("secondary");
      btnUnset.classList.add("secondary");
      await loadBoard();
    });
    btnUnset.addEventListener("click", async () => {
      state.filter_mode = "unset";
      btnUnset.classList.remove("secondary");
      btnAll.classList.add("secondary");
      await loadBoard();
    });
  }

  // Sunday modal events
  const absentChk = document.getElementById("sundayAbsentChk");
  if (absentChk) {
    absentChk.addEventListener("change", () => {
      const st = document.getElementById("sundayEditStatus");
      const isAbsent = absentChk.checked;

      if (isAbsent) {
        // 이미 선택된 참석칩이 있는지 체크 후 메시지 노출
        const anySelected = Array.from(
          document.querySelectorAll(
            "#sundayEditOverlay input[type='checkbox'][value]"
          )
        ).some((el) => el.checked);

        if (st) {
          setModalStatus(
            st,
            anySelected
              ? "불참을 선택하면 다른 참석 선택이 모두 해제됩니다."
              : "불참을 선택했습니다.",
            "plain"
          );
        }
      } else {
        if (st) setModalStatus(st, "", "plain");
      }

      setSundayAbsentState(isAbsent);
    });
  }

  const btnSundayCancel = document.getElementById("btnSundayEditCancel");
  if (btnSundayCancel) btnSundayCancel.addEventListener("click", () => hideOverlay("sundayEditOverlay"));
  const btnSundaySave = document.getElementById("btnSundayEditSave");
  if (btnSundaySave)
    btnSundaySave.addEventListener("click", async () => {
      try {
        await saveSundayModal();
      } catch (e) {
        console.error(e);
        const st = document.getElementById("sundayEditStatus");
        setModalStatus(st, e.message || "저장에 실패했습니다.", "error");
      }
    });

  // Midweek modal events
  const presentBtn = document.getElementById("btnMidweekPresent");
  const absentBtn = document.getElementById("btnMidweekAbsent");
  if (presentBtn && absentBtn) {
    presentBtn.addEventListener("click", () => {
      presentBtn.classList.add("secondary");
      absentBtn.classList.remove("secondary");
    });
    absentBtn.addEventListener("click", () => {
      absentBtn.classList.add("secondary");
      presentBtn.classList.remove("secondary");
    });
  }
  const btnMwCancel = document.getElementById("btnMidweekEditCancel");
  if (btnMwCancel) btnMwCancel.addEventListener("click", () => hideOverlay("midweekEditOverlay"));
  const btnMwSave = document.getElementById("btnMidweekEditSave");
  if (btnMwSave)
    btnMwSave.addEventListener("click", async () => {
      try {
        await saveMidweekModal();
      } catch (e) {
        console.error(e);
        const st = document.getElementById("midweekEditStatus");
        setModalStatus(st, e.message || "저장에 실패했습니다.", "error");
      }
    });
}

async function loadBoard() {
  if (!state.week_sunday) throw new Error("week_sunday missing");
  const division_code = document.getElementById("divisionCode").value || state.division_code;
  state.division_code = division_code;

  if (!division_code || !isDivisionAllowed(division_code)) {
    renderNoAccess();
    return;
  }

  setStatus("불러오는 중…");
  renderAccessEmpty();

  if (state.service_type === "sunday") {
    const data = await apiGet(
      `/attendance/team/weeks/${encodeURIComponent(state.week_sunday)}/roster/sunday/?division_code=${encodeURIComponent(
        division_code
      )}`
    );
    state.can_edit = data.can_edit === true;
    const teams = data.teams || [];
    if (state.filter_mode === "unset") {
      teams.forEach((t) => {
        t.members = (t.members || []).filter((m) => m.entry_state === "unset");
      });
    }
    renderTeamsSunday(teams);
    setStatus("");
    updateReadOnlyHint();
    return;
  }

  const data = await apiGet(
    `/attendance/team/weeks/${encodeURIComponent(state.week_sunday)}/roster/midweek/?division_code=${encodeURIComponent(
      division_code
    )}&service_type=${encodeURIComponent(state.service_type)}`
  );
  state.can_edit = data.can_edit === true;
  const teams = data.teams || [];
  if (state.filter_mode === "unset") {
    teams.forEach((t) => {
      t.members = (t.members || []).filter((m) => m.entry_state === "unset");
    });
  }
  renderTeamsMidweek(teams);
  setStatus("");
  updateReadOnlyHint();
}

async function init() {
  const q = parseQuery();
  state.division_code = q.division_code;
  state.week_sunday = q.week_sunday;
  state.service_type = q.service_type || "sunday";
  state.filter_mode = "all";

  bindUi();
  try {
    setStatus("");
    await loadDivisions();
    const curDivision =
      document.getElementById("divisionCode").value || state.division_code;
    if (!curDivision || !isDivisionAllowed(curDivision)) {
      renderNoAccess();
      return;
    }

    await loadWeeks();

    // filter 버튼 기본 스타일
    const btnAll = document.getElementById("filterAll");
    const btnUnset = document.getElementById("filterUnset");
    if (btnAll && btnUnset) {
      // 기본: 전체(all) = 파란색(secondary 제거)
      btnAll.classList.remove("secondary");
      btnUnset.classList.add("secondary");
    }

    await loadBoard();
  } catch (e) {
    console.error(e);
    setStatus("초기화 실패: " + e.message, true);
  }
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
else init();

