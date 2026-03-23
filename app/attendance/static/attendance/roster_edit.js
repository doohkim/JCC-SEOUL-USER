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

function getCookie(name) {
  const v = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
  return v ? decodeURIComponent(v[2]) : "";
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
    throw new Error(t || r.statusText);
  }
  return r.json();
}

function parseQuery() {
  const u = new URL(window.location.href);
  const mode = u.searchParams.get("mode") || "sunday";
  const division_code = u.searchParams.get("division_code") || "youth";
  const week_sunday = u.searchParams.get("week_sunday");
  const service_type = u.searchParams.get("service_type") || "wednesday";
  return { mode, division_code, week_sunday, service_type };
}

function renderMidweekBoard(payload) {
  const wrap = document.getElementById("boardWrap");
  wrap.innerHTML = "";

  const teams = payload.teams || [];
  teams.forEach((t) => {
    const card = document.createElement("div");
    card.className = "card";
    card.style.marginBottom = "1.25rem";
    card.innerHTML = `
      <h2 style="margin-bottom:0.6rem;">${t.team_name}</h2>
      <table>
        <thead>
          <tr>
            <th>이름</th>
            <th>출석</th>
          </tr>
        </thead>
        <tbody>
        ${t.members
          .map(
            (m) => `
          <tr>
            <td>${m.member_name}</td>
            <td>
              <select data-member-id="${m.member_id}" data-record-id="${m.record_id}">
                <option value="present" ${m.status === "present" ? "selected" : ""}>참석</option>
                <option value="online" ${m.status === "online" ? "selected" : ""}>온라인</option>
                <option value="absent" ${m.status === "absent" ? "selected" : ""}>불참</option>
              </select>
            </td>
          </tr>
        `
          )
          .join("")}
        </tbody>
      </table>
    `;
    wrap.appendChild(card);
  });
}

const SUNDAY_OPTIONS = [
  { key: "absent", label: "불참(아무것도 없음)" },
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

function renderSundayBoard(payload) {
  const wrap = document.getElementById("boardWrap");
  wrap.innerHTML = "";
  const teams = payload.teams || [];

  teams.forEach((t) => {
    const card = document.createElement("div");
    card.className = "card";
    card.style.marginBottom = "1.25rem";
    card.innerHTML = `
      <h2 style="margin-bottom:0.6rem;">${t.team_name}</h2>
      <table>
        <thead>
          <tr>
            <th>이름</th>
            <th>예배 슬롯</th>
          </tr>
        </thead>
        <tbody>
        ${t.members
          .map(
            (m) => `
          <tr>
            <td>${m.member_name}</td>
            <td>
              <select data-member-id="${m.member_id}" data-team-id="${m.team_id}">
                ${SUNDAY_OPTIONS.map(
                  (opt) =>
                    `<option value="${opt.key}" ${m.selection === opt.key ? "selected" : ""}>${opt.label}</option>`
                ).join("")}
              </select>
            </td>
          </tr>
        `
          )
          .join("")}
        </tbody>
      </table>
    `;
    wrap.appendChild(card);
  });
}

async function loadBoard() {
  const { mode, division_code, week_sunday, service_type } = parseQuery();
  if (!week_sunday) throw new Error("week_sunday missing");

  if (mode === "midweek") {
    const p = `/attendance/weeks/${encodeURIComponent(week_sunday)}/roster/midweek/?division_code=${encodeURIComponent(
      division_code
    )}&service_type=${encodeURIComponent(service_type)}`;
    const data = await apiGet(p);
    setStatus("");
    renderMidweekBoard(data);
    return { mode, division_code, week_sunday, service_type };
  }

  const p = `/attendance/weeks/${encodeURIComponent(week_sunday)}/roster/sunday/?division_code=${encodeURIComponent(
    division_code
  )}`;
  const data = await apiGet(p);
  setStatus("");
  renderSundayBoard(data);
  return { mode, division_code, week_sunday, service_type };
}

async function saveBoard() {
  const { mode, division_code, week_sunday, service_type } = parseQuery();
  setStatus("저장 중…");

  if (mode === "midweek") {
    const selects = document.querySelectorAll("select[data-record-id]");
    const updates = [];
    selects.forEach((sel) => {
      const rid = sel.getAttribute("data-record-id");
      updates.push({ record_id: Number(rid), status: sel.value });
    });
    const payload = { service_type, updates };
    const api = `/attendance/weeks/${encodeURIComponent(week_sunday)}/roster/midweek/?division_code=${encodeURIComponent(
      division_code
    )}`;
    const resp = await apiPost(api, payload);
    setStatus("저장 완료 (변경 " + resp.changed + "건).");
    return;
  }

  const selects = document.querySelectorAll("select[data-member-id][data-team-id]");
  const updates = [];
  selects.forEach((sel) => {
    updates.push({
      member_id: Number(sel.getAttribute("data-member-id")),
      team_id: Number(sel.getAttribute("data-team-id")),
      selection: sel.value,
    });
  });
  const payload = { updates };
  const api = `/attendance/weeks/${encodeURIComponent(week_sunday)}/roster/sunday/?division_code=${encodeURIComponent(
    division_code
  )}`;
  const resp = await apiPost(api, payload);
  setStatus("저장 완료 (변경 " + resp.changed + "건).");
}

function bindUi() {
  document.getElementById("btnBack").onclick = () => history.back();
  document.getElementById("btnSave").onclick = async () => {
    try {
      await saveBoard();
    } catch (e) {
      console.error(e);
      setStatus("저장 실패: " + e.message, true);
    }
  };
}

async function init() {
  bindUi();
  try {
    setStatus("불러오는 중…");
    await loadBoard();
  } catch (e) {
    console.error(e);
    setStatus("초기화 실패: " + e.message, true);
  }
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
else init();

