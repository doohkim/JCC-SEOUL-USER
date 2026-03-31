const API = "/api/v1";
const TEAM_TONES = [
  { bar: "#35578e", card: "#2a446f" },
  { bar: "#2f6e67", card: "#275a54" },
  { bar: "#5c4e86", card: "#4a3f6b" },
  { bar: "#7a6845", card: "#66573a" },
  { bar: "#425775", card: "#354660" },
  { bar: "#4f4c74", card: "#403f5f" },
];

function setStatus(msg, isErr) {
  const el = document.getElementById("statusLine");
  el.textContent = msg || "";
  el.className = "msg" + (isErr ? " err" : "");
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

function fillSelect(selectEl, items, currentValue) {
  selectEl.innerHTML = "";
  items.forEach((it) => {
    const opt = document.createElement("option");
    opt.value = it.value;
    opt.textContent = it.label;
    if (currentValue !== undefined && String(currentValue) === String(it.value)) {
      opt.selected = true;
    }
    selectEl.appendChild(opt);
  });
}

async function apiGet(path) {
  const r = await fetch(API + path, { credentials: "same-origin" });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json();
}

function escapeHtml(s) {
  if (s === null || s === undefined) return "";
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function hrefDetail(id) {
  return `/members/${id}/`;
}

function formatMobilePhone(phone) {
  const raw = String(phone || "").trim();
  if (!raw) return "";
  const digits = raw.replace(/\D/g, "");
  if (digits.length === 11) {
    return `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7)}`;
  }
  return "";
}

function buildMemberAvatar(m) {
  const letter = escapeHtml((m.name || "?").trim().charAt(0) || "?");
  const img = m.photo_url
    ? `<img class="jcc-team-member-photo" src="${escapeHtml(m.photo_url)}" alt="${escapeHtml(
        m.name || "멤버"
      )}" loading="lazy" />`
    : "";
  return `
    <div class="jcc-team-member-photoWrap">
      ${img}
      <span class="jcc-team-member-photoFallback" aria-hidden="true">${letter}</span>
    </div>
  `;
}

const moveState = {
  memberId: null,
  divisionId: null,
  divisionCode: "",
  currentMembershipId: null,
  currentTeamId: null,
};

function showMoveModal() {
  const ov = document.getElementById("moveModalOverlay");
  ov.classList.add("show");
  ov.setAttribute("aria-hidden", "false");
}

function hideMoveModal() {
  const ov = document.getElementById("moveModalOverlay");
  ov.classList.remove("show");
  ov.setAttribute("aria-hidden", "true");
  const st = document.getElementById("moveModalStatus");
  if (st) st.textContent = "";
}

function setMoveStatus(msg, isErr) {
  const st = document.getElementById("moveModalStatus");
  if (!st) return;
  st.textContent = msg || "";
  st.className = "msg" + (isErr ? " err" : "");
}

async function loadDivisions() {
  const data = await apiGet(`/member/teams/accordion/?meta_only=1`);
  const items = [{ value: "", label: "전체" }];
  (Array.isArray(data.division_options) ? data.division_options : []).forEach((d) => {
    items.push({ value: d.code, label: d.name });
  });
  fillSelect(document.getElementById("fltDivision"), items);
}

async function loadTeams(divisionCode, currentTeamId) {
  const teamSel = document.getElementById("fltTeam");
  // team dropdown "전체"는 query param `team_id`를 보내지 않도록 value=""를 사용합니다.
  const url = `/member/teams/accordion/?meta_only=1${
    divisionCode ? `&division_code=${encodeURIComponent(divisionCode)}` : ""
  }`;
  const data = await apiGet(url);
  const items = [{ value: "", label: "전체" }];
  (Array.isArray(data.team_options) ? data.team_options : []).forEach((t) => {
    const v = t.id === null || t.id === undefined ? "" : t.id;
    if (divisionCode && t.division_code !== divisionCode) return;
    items.push({ value: v, label: t.name || t.label || "팀" });
  });
  fillSelect(teamSel, items, currentTeamId);
}

async function loadMoveTeams(divisionCode) {
  const sel = document.getElementById("moveTargetTeam");
  const teams = await apiGet(
    `/attendance/teams/?division_code=${encodeURIComponent(divisionCode)}`
  );
  const items = [{ value: "", label: "선택" }];
  (Array.isArray(teams) ? teams : []).forEach((t) => {
    items.push({ value: t.id, label: t.name });
  });
  fillSelect(sel, items, moveState.currentTeamId);
}

async function loadMembers() {
  const q = document.getElementById("fltQ").value.trim();
  const divisionCode = document.getElementById("fltDivision").value;
  const teamId = document.getElementById("fltTeam").value;
  setStatus("불러오는 중…");
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (divisionCode) params.set("division_code", divisionCode);
  if (teamId) params.set("team_id", teamId);

  const data = await apiGet(`/member/teams/accordion/?${params.toString()}`);

  const container = document.getElementById("teamGroups");
  if (!container) return;

  const groups = Array.isArray(data.groups) ? data.groups : [];
  container.innerHTML = "";

  if (!groups.length) {
    container.innerHTML = `<div class="msg">표시할 멤버가 없습니다.</div>`;
    setStatus("표시할 멤버가 없습니다.");
    return;
  }

  groups.forEach((g, idx) => {
    const groupId = `tg_${idx}`;
    const count = Array.isArray(g.members) ? g.members.length : 0;
    const bodyId = `${groupId}_body`;

    const members = (Array.isArray(g.members) ? g.members : []).slice().sort((a, b) => {
      return (a.name || "").localeCompare(b.name || "", "ko");
    });

    const membersHtml = members
      .map((m) => {
        const phoneText = formatMobilePhone(m.phone || "");
        return `
          <li class="jcc-team-member">
            <a class="jcc-team-member-cardLink${phoneText ? " has-phone" : ""}" href="${hrefDetail(m.id)}" aria-label="${escapeHtml(
              m.name || "멤버"
            )} 상세 보기">
              ${buildMemberAvatar(m)}
              <span class="jcc-team-member-name">${escapeHtml(m.name || "-")}</span>
              <span class="jcc-team-member-phone">${escapeHtml(phoneText)}</span>
            </a>
          </li>
        `;
      })
      .join("");

    const el = document.createElement("div");
    el.className = `jcc-team-group jcc-team-group-tone-${idx % 4}`;
    const tone = TEAM_TONES[idx % TEAM_TONES.length];
    if (tone) {
      el.style.setProperty("--jcc-team-tone-bar", tone.bar);
      el.style.setProperty("--jcc-team-tone-card", tone.card);
    }
    el.innerHTML = `
      <button type="button" class="jcc-team-group-toggle" aria-expanded="false" data-body-id="${bodyId}">
        <span class="jcc-team-group-title">${escapeHtml(g.team_name || "팀")}</span>
        <span class="jcc-team-group-count">${count}명</span>
        <span class="jcc-team-group-chevron" aria-hidden="true">▸</span>
      </button>
      <div class="jcc-team-group-body" id="${bodyId}" hidden>
        <ul class="jcc-team-memberList">${membersHtml}</ul>
      </div>
    `;
    container.appendChild(el);
  });

  const totalMembers = groups.reduce(
    (acc, g) => acc + (Array.isArray(g.members) ? g.members.length : 0),
    0
  );
  setStatus(totalMembers ? `총 ${totalMembers}명` : "표시할 멤버가 없습니다.");
}

async function refreshFiltersPreserveSelection() {
  const divSel = document.getElementById("fltDivision");
  const teamSel = document.getElementById("fltTeam");
  const curDiv = divSel ? divSel.value : "";
  const curTeam = teamSel ? teamSel.value : "";

  const divData = await apiGet(`/member/teams/accordion/?meta_only=1`);
  const divItems = [{ value: "", label: "전체" }];
  (Array.isArray(divData.division_options) ? divData.division_options : []).forEach((d) => {
    divItems.push({ value: d.code, label: d.name });
  });

  fillSelect(divSel, divItems, curDiv);

  const nextDivCode = divSel.value || "";
  await loadTeams(nextDivCode, curTeam);
}

function bindUi() {
  document.getElementById("btnRefresh").onclick = async () => {
    setStatus("필터 갱신 중…");
    await refreshFiltersPreserveSelection();
    await loadMembers();
  };
  document.getElementById("fltQ").onkeydown = (e) => {
    if (e.key === "Enter") loadMembers();
  };
  document.getElementById("fltDivision").onchange = async () => {
    const divCode = document.getElementById("fltDivision").value;
    await loadTeams(divCode, null);
    await loadMembers();
  };

  document.getElementById("btnMoveCancel").onclick = () => {
    hideMoveModal();
  };

  document.getElementById("btnMoveSubmit").onclick = async () => {
    try {
      setMoveStatus("이동 중…");
      const memberId = moveState.memberId;
      const divisionId = moveState.divisionId;
      const currentMembershipId = moveState.currentMembershipId;
      const targetTeamIdRaw = document.getElementById("moveTargetTeam").value;
      const targetTeamId = targetTeamIdRaw ? Number(targetTeamIdRaw) : null;

      if (!memberId || !divisionId || !targetTeamId) {
        setMoveStatus("부서/팀/멤버 값이 올바르지 않습니다.", true);
        return;
      }

      const payload = {
        member_id: Number(memberId),
        division_id: Number(divisionId),
        new_team_id: Number(targetTeamId),
        membership_id: currentMembershipId ? Number(currentMembershipId) : null,
        make_primary: document.getElementById("moveMakePrimary").checked,
      };

      await apiPost(`/org/change-team/`, payload);
      hideMoveModal();
      await loadMembers();
      setStatus("팀 이동 완료");
    } catch (e) {
      console.error(e);
      setMoveStatus("이동 실패: " + e.message, true);
    }
  };

  const teamGroupsEl = document.getElementById("teamGroups");
  if (teamGroupsEl) {
    teamGroupsEl.onclick = async (e) => {
    const toggleBtn = e.target.closest(".jcc-team-group-toggle");
    if (toggleBtn) {
      const bodyId = toggleBtn.getAttribute("data-body-id");
      const bodyEl = document.getElementById(bodyId);
      const isHidden = !bodyEl || bodyEl.hasAttribute("hidden");
      if (bodyEl) {
        if (isHidden) bodyEl.removeAttribute("hidden");
        else bodyEl.setAttribute("hidden", "hidden");
      }
      const chev = toggleBtn.querySelector(".jcc-team-group-chevron");
      if (chev) chev.textContent = isHidden ? "▾" : "▸";
      toggleBtn.setAttribute("aria-expanded", isHidden ? "true" : "false");
      return;
    }
    };
  }
}

async function init() {
  bindUi();
  try {
    await refreshFiltersPreserveSelection();
    await loadMembers();
  } catch (e) {
    console.error(e);
    setStatus("초기화 실패: " + e.message, true);
  }
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
else init();

