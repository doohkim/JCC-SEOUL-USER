const API = "/api/v1";

function setStatus(msg, isErr) {
  const el = document.getElementById("statusLine");
  el.textContent = msg || "";
  el.className = "msg" + (isErr ? " err" : "");
}

function getCookie(name) {
  const v = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
  return v ? decodeURIComponent(v[2]) : "";
}

async function apiGet(path) {
  const r = await fetch(API + path, { credentials: "same-origin" });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json();
}

async function apiSave(method, path, formData) {
  const csrftoken = getCookie("csrftoken");
  const r = await fetch(API + path, {
    method,
    credentials: "same-origin",
    headers: { "X-CSRFToken": csrftoken },
    body: formData,
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json();
}

function getElValue(id) {
  const el = document.getElementById(id);
  if (!el) return "";
  if (el.type === "checkbox") return el.checked;
  return el.value;
}

const memberFormState = {
  currentDivisionId: null,
  currentTeamId: null,
  currentMembershipId: null,
  isActive: true,
};

const divisionCodeToId = new Map();

async function apiPostJson(path, payload) {
  const csrftoken = getCookie("csrftoken");
  const r = await fetch(API + path, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "X-CSRFToken": csrftoken,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json();
}

async function loadPositionOptions(selectedValue) {
  const sel = document.getElementById("p_pos");
  if (!sel) return;

  // Ensure select exists (template will render it)
  const data = await apiGet(`/member/roles/`);
  const roles = Array.isArray(data.roles) ? data.roles : [];

  sel.innerHTML = `<option value="">-</option>`;
  roles.forEach((r) => {
    const opt = document.createElement("option");
    // Backend stores church_position_display as a string; use Role.name for both.
    opt.value = r.name || "";
    opt.textContent = r.name || "";
    if (opt.value) sel.appendChild(opt);
  });

  if (selectedValue) {
    const exists = Array.from(sel.options).some((o) => o.value === selectedValue);
    if (!exists) {
      const opt = document.createElement("option");
      opt.value = selectedValue;
      opt.textContent = selectedValue;
      sel.appendChild(opt);
    }
    sel.value = selectedValue;
  }
}

function fillForm(data) {
  const m = data.member || {};
  const p = data.profile || {};
  const pm = data.primary_membership || {};

  document.getElementById("m_name").value = m.name || "";
  document.getElementById("m_alias").value = m.name_alias || "";
  memberFormState.isActive = Boolean(m.is_active);

  memberFormState.currentDivisionId = pm.division_id ?? null;
  memberFormState.currentTeamId = pm.team_id ?? null;
  memberFormState.currentMembershipId = pm.membership_id ?? null;

  const divEl = document.getElementById("m_division");
  const teamEl = document.getElementById("m_team");
  const membershipEl = document.getElementById("m_membershipId");
  if (divEl) divEl.value = pm.division_code || "";
  if (teamEl) teamEl.value = pm.team_id ? String(pm.team_id) : "";
  if (membershipEl) membershipEl.value = pm.membership_id ? String(pm.membership_id) : "";

  if (p) {
    document.getElementById("p_birth").value = p.birth_date || "";
    document.getElementById("p_phone").value = p.phone || "";
    document.getElementById("p_address").value = p.address || "";
    document.getElementById("p_pos").value = p.church_position_display || "";
    document.getElementById("p_work").value = p.workplace_display || "";
    document.getElementById("p_staff_notes").value = p.staff_notes || "";

    // existing photos
    if (p.photo) {
      const el = document.getElementById("photoPreview");
      el.src = p.photo;
      const fn = document.getElementById("p_photoFileName");
      if (fn) fn.textContent = String(p.photo).split("/").pop().split("?")[0];
    }
    if (p.family_photo) {
      const el = document.getElementById("familyPhotoPreview");
      el.src = p.family_photo;
      const fn = document.getElementById("p_familyPhotoFileName");
      if (fn) fn.textContent = String(p.family_photo).split("/").pop().split("?")[0];
    }
  }
}

function bindFilePreview(inputId, previewId, fileNameId) {
  const input = document.getElementById(inputId);
  const preview = document.getElementById(previewId);
  const fileNameEl = document.getElementById(fileNameId);

  if (!input || !preview) return;

  input.addEventListener("change", () => {
    const file = input.files && input.files[0] ? input.files[0] : null;
    if (!file) return;

    // local preview
    const url = URL.createObjectURL(file);
    preview.src = url;
    if (fileNameEl) fileNameEl.textContent = file.name;
  });
}

async function init() {
  const mode = window.__MODE__ || "create";
  const rawMemberId = window.__MEMBER_ID__;
  const memberId =
    rawMemberId === undefined ||
    rawMemberId === null ||
    rawMemberId === "null" ||
    rawMemberId === ""
      ? null
      : Number(rawMemberId);

  document.getElementById("btnBack").onclick = () => history.back();

  bindFilePreview("p_photo", "photoPreview", "p_photoFileName");
  bindFilePreview("p_family_photo", "familyPhotoPreview", "p_familyPhotoFileName");

  const divSelect = document.getElementById("m_division");
  const teamSelect = document.getElementById("m_team");
  if (!divSelect || !teamSelect) throw new Error("부서/팀 select 엘리먼트가 없습니다.");

  async function loadDivisionOptions() {
    const data = await apiGet(`/member/teams/accordion/?meta_only=1`);
    divisionCodeToId.clear();

    // 신규 기본값은 "미정"(value="")으로 둔다.
    // 저장 시에는 "부서"만 필수로 검증한다.
    divSelect.innerHTML = `<option value="">미정</option>`;
    (data.division_options || []).forEach((d) => {
      divisionCodeToId.set(d.code, d.id);
      const opt = document.createElement("option");
      opt.value = d.code; // save/필터는 code 기반
      opt.textContent = d.name;
      divSelect.appendChild(opt);
    });
  }

  async function loadTeamOptions(divisionCode, selectedTeamId) {
    if (!divisionCode) {
      teamSelect.innerHTML = `<option value="">미정</option>`;
      return;
    }
    const data = await apiGet(
      `/member/teams/accordion/?meta_only=1&division_code=${encodeURIComponent(divisionCode)}`
    );
    teamSelect.innerHTML = `<option value="">미정</option>`;
    (data.team_options || []).forEach((t) => {
      const opt = document.createElement("option");
      opt.value = String(t.id);
      opt.textContent = t.name || t.label || "";
      teamSelect.appendChild(opt);
    });

    // selectedTeamId가 없으면 placeholder("미정")를 유지한다.
    if (selectedTeamId !== null && selectedTeamId !== undefined) {
      teamSelect.value = String(selectedTeamId);
    } else {
      teamSelect.value = "";
    }
  }

  await loadDivisionOptions();

  // 부서 변경 시 팀 옵션 갱신
  divSelect.addEventListener("change", async () => {
    await loadTeamOptions(divSelect.value, null);
  });

  if (mode === "edit" && memberId) {
    setStatus("불러오는 중…");
    const data = await apiGet(`/member/${memberId}/`);
    const pm = data.primary_membership || {};

    const selectedPos = (data.profile && data.profile.church_position_display) || "";
    await loadPositionOptions(selectedPos);

    divSelect.value = pm.division_code || "";
    await loadTeamOptions(pm.division_code || "", pm.team_id || null);
    fillForm(data);
    setStatus("");
  } else {
    await loadPositionOptions("");

    // create: 기본값은 둘 다 "미정"(value="") 유지
    // (저장 시 부서만 필수, 팀은 optional(null) 허용)
    divSelect.value = "";
    await loadTeamOptions(divSelect.value, null);
  }

  document.getElementById("btnSave").onclick = async () => {
    try {
      setStatus("저장 중…");
      const fd = new FormData();
      fd.set("name", getElValue("m_name"));
      fd.set("name_alias", getElValue("m_alias"));
      fd.set("is_active", memberFormState.isActive ? "true" : "false");

      fd.set("birth_date", getElValue("p_birth") || "");
      fd.set("phone", getElValue("p_phone") || "");
      fd.set("address", getElValue("p_address") || "");
      fd.set("church_position_display", getElValue("p_pos") || "");
      fd.set("workplace_display", getElValue("p_work") || "");
      fd.set("staff_notes", getElValue("p_staff_notes") || "");

      const photo = document.getElementById("p_photo").files[0];
      if (photo) fd.set("photo", photo);
      const familyPhoto = document.getElementById("p_family_photo").files[0];
      if (familyPhoto) fd.set("family_photo", familyPhoto);

      if (mode === "create") {
        const resp = await apiSave("POST", `/member/`, fd);
        const newId = resp.member_id;

        const divisionCode = divSelect.value;
        const teamIdStr = teamSelect.value;
        if (!divisionCode) throw new Error("부서를 선택해주세요.");

        const toDivisionId = divisionCodeToId.get(divisionCode);
        if (!toDivisionId) throw new Error("선택된 부서 정보를 불러오지 못했습니다.");

        const teamId = teamIdStr ? Number(teamIdStr) : null; // "미정" => null
        await apiPostJson(`/org/transfer-division/`, {
          member_id: Number(newId),
          from_division_id: null,
          to_division_id: Number(toDivisionId),
          team_id: teamId,
          remove_from_source: false,
          make_primary: true,
        });

        window.location = `/members/${newId}/`;
      } else {
        await apiSave("PUT", `/member/${memberId}/`, fd);

        const divisionCode = divSelect.value;
        const teamIdStr = teamSelect.value;
        if (!divisionCode) throw new Error("부서를 선택해주세요.");

        const toDivisionId = divisionCodeToId.get(divisionCode);
        if (!toDivisionId) throw new Error("선택된 부서 정보를 불러오지 못했습니다.");

        const selectedDivisionId = Number(toDivisionId);
        const selectedTeamId = teamIdStr ? Number(teamIdStr) : null;

        if (
          memberFormState.currentDivisionId !== null &&
          selectedDivisionId !== Number(memberFormState.currentDivisionId)
        ) {
          // 부서가 바뀌면 transfer-division으로 이동 (팀은 null 가능)
          await apiPostJson(`/org/transfer-division/`, {
            member_id: Number(memberId),
            from_division_id: Number(memberFormState.currentDivisionId),
            to_division_id: selectedDivisionId,
            team_id: selectedTeamId,
            remove_from_source: true,
            make_primary: true,
          });
        } else if (
          selectedTeamId !== memberFormState.currentTeamId
        ) {
          // 같은 부서에서 팀 변경(팀 null 가능)
          await apiPostJson(`/org/change-team/`, {
            member_id: Number(memberId),
            division_id: selectedDivisionId,
            new_team_id: selectedTeamId,
            membership_id: memberFormState.currentMembershipId,
            make_primary: true,
          });
        }

        window.location = `/members/${memberId}/`;
      }
    } catch (e) {
      console.error(e);
      setStatus("저장 실패: " + e.message, true);
    }
  };
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
else init();

