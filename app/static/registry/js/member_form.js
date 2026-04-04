const API = "/api/v1";

const REL_ITEMS = [
  { value: "father", label: "부" },
  { value: "mother", label: "모" },
  { value: "spouse", label: "배우자" },
  { value: "elder_brother", label: "형/오빠" },
  { value: "younger_brother", label: "남동생" },
  { value: "elder_sister", label: "언니/누나" },
  { value: "younger_sister", label: "여동생" },
  { value: "son", label: "아들" },
  { value: "daughter", label: "딸" },
  { value: "other", label: "기타" },
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
  /** @type {Array<Record<string, unknown>>} */
  initialFamily: [],
};

let cachedRoleList = null;

async function getRoleList() {
  if (cachedRoleList) return cachedRoleList;
  const data = await apiGet(`/member/roles/`);
  cachedRoleList = Array.isArray(data.roles) ? data.roles : [];
  return cachedRoleList;
}

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

async function apiPatchJson(path, payload) {
  const csrftoken = getCookie("csrftoken");
  const r = await fetch(API + path, {
    method: "PATCH",
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

async function apiDelete(path) {
  const csrftoken = getCookie("csrftoken");
  const r = await fetch(API + path, {
    method: "DELETE",
    credentials: "same-origin",
    headers: { "X-CSRFToken": csrftoken },
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  if (r.status === 204 || r.headers.get("content-length") === "0") return { ok: true };
  try {
    return await r.json();
  } catch {
    return { ok: true };
  }
}

async function loadPositionOptions(selectedValue) {
  const sel = document.getElementById("p_pos");
  if (!sel) return;

  const roles = await getRoleList();

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

function getFamilyRowsHost() {
  return document.getElementById("familyRowsHost");
}

function clearFamilyRows() {
  const host = getFamilyRowsHost();
  if (host) host.innerHTML = "";
}

function readFamilyRowEl(rowEl) {
  const idStr = rowEl.dataset.familyId || "";
  const id = idStr ? Number(idStr) : null;
  const name = rowEl.querySelector('[data-f="name"]')?.value ?? "";
  const relationship = rowEl.querySelector('[data-f="rel"]')?.value ?? "";
  const affiliation_text = rowEl.querySelector('[data-f="aff"]')?.value ?? "";
  const church_position = rowEl.querySelector('[data-f="pos"]')?.value ?? "";
  const note = rowEl.querySelector('[data-f="note"]')?.value ?? "";
  return { id, name, relationship, affiliation_text, church_position, note };
}

function buildFamilyApiPayload(row) {
  const name = row.name.trim();
  const relationship = row.relationship;
  const affiliation_text = row.affiliation_text.trim();
  const church_position = row.church_position.trim();
  const note = row.note.trim();
  return {
    name,
    relationship,
    affiliation_text,
    church_position,
    remarks: relationship === "other" ? "" : note,
    relationship_note: relationship === "other" ? note : "",
  };
}

async function createFamilyRowElement(fam) {
  const roles = await getRoleList();
  const row = document.createElement("div");
  row.className = "jcc-family-form-row toolbar jcc-detail-addToolbar";
  row.style.cssText =
    "padding:0; border:none; background:transparent; margin-bottom:0.65rem; flex-wrap:wrap; align-items:flex-end;";
  if (fam && fam.id) row.dataset.familyId = String(fam.id);

  function mkField(labelText, controlEl) {
    const wrap = document.createElement("div");
    wrap.className = "field";
    const lab = document.createElement("label");
    lab.textContent = labelText;
    wrap.appendChild(lab);
    wrap.appendChild(controlEl);
    return wrap;
  }

  const nameIn = document.createElement("input");
  nameIn.type = "text";
  nameIn.className = "jcc-reg-control";
  nameIn.setAttribute("data-f", "name");
  row.appendChild(mkField("이름", nameIn));

  const relSel = document.createElement("select");
  relSel.className = "jcc-reg-control";
  relSel.setAttribute("data-f", "rel");
  const relPlaceholder = document.createElement("option");
  relPlaceholder.value = "";
  relPlaceholder.textContent = "선택";
  relSel.appendChild(relPlaceholder);
  REL_ITEMS.forEach((x) => {
    const opt = document.createElement("option");
    opt.value = x.value;
    opt.textContent = x.label;
    relSel.appendChild(opt);
  });
  row.appendChild(mkField("관계", relSel));

  const affIn = document.createElement("input");
  affIn.type = "text";
  affIn.className = "jcc-reg-control";
  affIn.setAttribute("data-f", "aff");
  row.appendChild(mkField("소속", affIn));

  const posSel = document.createElement("select");
  posSel.className = "jcc-reg-control";
  posSel.setAttribute("data-f", "pos");
  const posEmpty = document.createElement("option");
  posEmpty.value = "";
  posEmpty.textContent = "-";
  posSel.appendChild(posEmpty);
  roles.forEach((r) => {
    const v = r.name || "";
    if (!v) return;
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = v;
    posSel.appendChild(opt);
  });
  row.appendChild(mkField("직책", posSel));

  const noteIn = document.createElement("input");
  noteIn.type = "text";
  noteIn.className = "jcc-reg-control";
  noteIn.setAttribute("data-f", "note");
  row.appendChild(mkField("비고", noteIn));

  const btnWrap = document.createElement("div");
  btnWrap.className = "field";
  btnWrap.style.alignSelf = "flex-end";
  const rm = document.createElement("button");
  rm.type = "button";
  rm.className = "secondary jcc-family-row-remove";
  rm.textContent = "삭제";
  rm.onclick = () => row.remove();
  btnWrap.appendChild(rm);
  row.appendChild(btnWrap);

  if (fam) {
    nameIn.value = fam.name || "";
    const rel = fam.relationship || "";
    relSel.value = rel;
    affIn.value = fam.affiliation_text || "";
    const posVal = fam.church_position || "";
    if (posVal && !Array.from(posSel.options).some((o) => o.value === posVal)) {
      const opt = document.createElement("option");
      opt.value = posVal;
      opt.textContent = posVal;
      posSel.appendChild(opt);
    }
    posSel.value = posVal;
    const noteVal = rel === "other" ? fam.relationship_note || "" : fam.remarks || "";
    noteIn.value = noteVal;
  }

  return row;
}

async function appendFamilyRow(fam) {
  const host = getFamilyRowsHost();
  if (!host) return;
  const row = await createFamilyRowElement(fam);
  host.appendChild(row);
}

async function fillFamilyFromApi(family) {
  clearFamilyRows();
  memberFormState.initialFamily = Array.isArray(family) ? family.slice() : [];
  const rows = memberFormState.initialFamily;
  for (let i = 0; i < rows.length; i++) {
    await appendFamilyRow(rows[i]);
  }
}

function collectFamilyRowsFromDom() {
  const host = getFamilyRowsHost();
  if (!host) return [];
  return Array.from(host.querySelectorAll(".jcc-family-form-row")).map(readFamilyRowEl);
}

function validateFamilyRows(rows) {
  for (let i = 0; i < rows.length; i++) {
    const r = rows[i];
    const name = r.name.trim();
    if (!name) continue;
    if (!r.relationship) {
      throw new Error("가족 정보: 이름이 있는 행은 관계를 선택해주세요.");
    }
  }
}

async function persistFamilyAfterCreate(memberId) {
  const rows = collectFamilyRowsFromDom();
  validateFamilyRows(rows);
  const named = rows.filter((r) => r.name.trim());
  for (let i = 0; i < named.length; i++) {
    const payload = buildFamilyApiPayload(named[i]);
    payload.sort_order = i;
    await apiPostJson(`/member/${memberId}/family/`, payload);
  }
}

async function persistFamilyOnEdit(memberId) {
  const initial = memberFormState.initialFamily || [];
  const initialIds = new Set(initial.map((f) => Number(f.id)));
  const rows = collectFamilyRowsFromDom();
  validateFamilyRows(rows);

  const deleteIds = new Set();
  const upserts = [];

  for (const r of rows) {
    const name = r.name.trim();
    if (!name) {
      if (r.id) deleteIds.add(Number(r.id));
      continue;
    }
    upserts.push({ ...r, sort_order: upserts.length });
  }

  for (const id of initialIds) {
    const stillPresent = upserts.some((u) => u.id && Number(u.id) === id);
    if (!stillPresent) deleteIds.add(id);
  }

  for (const id of deleteIds) {
    await apiDelete(`/family/${id}/`);
  }

  for (const r of upserts) {
    const p = buildFamilyApiPayload(r);
    p.sort_order = r.sort_order;
    if (r.id) {
      await apiPatchJson(`/family/${r.id}/`, p);
    } else {
      await apiPostJson(`/member/${memberId}/family/`, p);
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
    if (getFamilyRowsHost()) {
      await fillFamilyFromApi(data.family || []);
    } else {
      memberFormState.initialFamily = [];
    }
    setStatus("");
  } else {
    await loadPositionOptions("");

    // create: 기본값은 둘 다 "미정"(value="") 유지
    // (저장 시 부서만 필수, 팀은 optional(null) 허용)
    divSelect.value = "";
    await loadTeamOptions(divSelect.value, null);
    memberFormState.initialFamily = [];
    clearFamilyRows();
  }

  const btnAddFamily = document.getElementById("btnAddFamilyRow");
  if (btnAddFamily) {
    btnAddFamily.onclick = async () => {
      try {
        await appendFamilyRow(null);
      } catch (e) {
        console.error(e);
        setStatus("가족 행 추가 실패: " + e.message, true);
      }
    };
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

        await persistFamilyAfterCreate(Number(newId));

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

        if (getFamilyRowsHost()) {
          await persistFamilyOnEdit(Number(memberId));
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

