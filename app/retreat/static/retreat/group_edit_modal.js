/**
 * 조 정보 수정 모달 — 공용 헬퍼 + 편집 팝업
 */
(function () {
  "use strict";

  const editCtx = window.RETREAT_GROUP_EDIT_CTX || {};
  const extraScopeTemplate = document.getElementById("extraScopeRowTemplate");

  let allDivisions = [];
  try {
    const raw = document.getElementById("retreatDivisionList")?.textContent || "[]";
    allDivisions = JSON.parse(raw);
  } catch (e) {
    allDivisions = [];
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function fillDivisionSelect(divisionInput, regionId, selectedId) {
    if (!divisionInput) return;
    divisionInput.innerHTML = '<option value="">선택</option>';
    if (!regionId) return;
    allDivisions
      .filter((d) => d.region_id === Number(regionId))
      .forEach((d) => {
        const opt = document.createElement("option");
        opt.value = String(d.id);
        opt.textContent = d.name;
        if (selectedId != null && String(d.id) === String(selectedId)) {
          opt.selected = true;
        }
        divisionInput.appendChild(opt);
      });
  }

  function bindExtraScopeRow(scopeRow) {
    const regionInput = scopeRow.querySelector("[data-extra-region]");
    const btnRemove = scopeRow.querySelector("[data-remove-extra-scope]");
    if (regionInput) {
      regionInput.addEventListener("change", () => {
        fillDivisionSelect(scopeRow.querySelector("[data-extra-division]"), regionInput.value);
      });
    }
    if (btnRemove) {
      btnRemove.addEventListener("click", () => scopeRow.remove());
    }
  }

  function appendExtraScopeRow(listEl, regionId, divisionId) {
    if (!extraScopeTemplate || !listEl) return null;
    const frag = extraScopeTemplate.content.cloneNode(true);
    const scopeRow = frag.querySelector("[data-extra-scope-row]");
    if (!scopeRow) return null;
    listEl.appendChild(scopeRow);
    bindExtraScopeRow(scopeRow);
    if (regionId) {
      const regionInput = scopeRow.querySelector("[data-extra-region]");
      if (regionInput) regionInput.value = String(regionId);
      fillDivisionSelect(scopeRow.querySelector("[data-extra-division]"), regionId, divisionId);
    }
    return scopeRow;
  }

  function collectExtraScopesFromList(listEl, label) {
    const scopes = [];
    const scopeRows = listEl ? listEl.querySelectorAll("[data-extra-scope-row]") : [];
    for (let j = 0; j < scopeRows.length; j += 1) {
      const scopeRow = scopeRows[j];
      const region = scopeRow.querySelector("[data-extra-region]")?.value;
      const division = scopeRow.querySelector("[data-extra-division]")?.value;
      if (!region && !division) continue;
      if (!region || !division) {
        return { error: `${label}: 추가 지역·부서 ${j + 1}행에 지역과 부서를 모두 선택하세요.` };
      }
      scopes.push({ region: Number(region), division: Number(division) });
    }
    return { scopes };
  }

  function createUserPicker(root, getFilters) {
    if (!root) return null;
    const input = root.querySelector("[data-user-picker-input]");
    const list = root.querySelector("[data-user-picker-list]");
    const hidden = root.querySelector("[data-user-picker-id]");
    if (!input || !list || !hidden) return null;
    const filters = typeof getFilters === "function" ? getFilters : () => ({});

    let selected = null;
    let items = [];
    let activeIdx = -1;
    let timer = null;
    let lastQuery = "";

    function clear() {
      selected = null;
      hidden.value = "";
      input.value = "";
      closeList();
    }

    function closeList() {
      list.hidden = true;
      list.innerHTML = "";
      activeIdx = -1;
    }

    function renderList() {
      if (!items.length) {
        list.innerHTML = '<li class="muted" role="option" aria-disabled="true">결과 없음</li>';
        list.hidden = false;
        return;
      }
      list.innerHTML = items
        .map((u, i) => {
          const shown = u.name || u.display_name || u.username;
          return `<li role="option" data-idx="${i}" class="${i === activeIdx ? "is-active" : ""}">${escapeHtml(shown)}</li>`;
        })
        .join("");
      list.hidden = false;
    }

    async function search(q) {
      const { division, region } = filters() || {};
      if (!q && !division && !region) {
        closeList();
        return;
      }
      lastQuery = q;
      try {
        const params = new URLSearchParams();
        if (q) params.set("q", q);
        if (division) params.set("division", division);
        else if (region) params.set("region", region);
        params.set("limit", "30");
        const url = `${editCtx.urls.userSearchUrl}?${params.toString()}`;
        const r = await fetch(url, { credentials: "same-origin" });
        if (!r.ok) throw new Error(await r.text());
        if (q !== lastQuery) return;
        items = await r.json();
        activeIdx = items.length ? 0 : -1;
        renderList();
      } catch (err) {
        console.error(err);
      }
    }

    function pick(idx) {
      const u = items[idx];
      if (!u) return;
      selected = u;
      hidden.value = String(u.id);
      input.value = u.name || u.display_name || u.username;
      closeList();
    }

    function hasFilter() {
      const { division, region } = filters() || {};
      return Boolean(division || region);
    }

    input.addEventListener("input", () => {
      selected = null;
      hidden.value = "";
      const q = input.value.trim();
      clearTimeout(timer);
      if (!q && !hasFilter()) {
        closeList();
        return;
      }
      timer = setTimeout(() => search(q), 180);
    });

    input.addEventListener("focus", () => {
      if (!input.value.trim() && hasFilter()) search("");
    });

    list.addEventListener("mousedown", (e) => {
      const li = e.target.closest("li[data-idx]");
      if (!li) return;
      e.preventDefault();
      pick(Number(li.dataset.idx));
    });

    document.addEventListener("click", (e) => {
      if (!root.contains(e.target)) closeList();
    });

    return { clear, getSelected: () => selected };
  }

  /* ---------- 조 수정 모달 ---------- */
  const editOverlay = document.getElementById("groupEditModalOverlay");
  const editForm = document.getElementById("groupEditForm");
  const editName = document.getElementById("groupEditName");
  const editOrder = document.getElementById("groupEditOrder");
  const editRegion = document.getElementById("groupEditRegion");
  const editDivision = document.getElementById("groupEditDivision");
  const editExtraList = document.getElementById("groupEditExtraScopes");
  const editLeadersList = document.getElementById("groupEditLeadersList");
  const editLeadersAdd = document.getElementById("groupEditLeadersAdd");
  const editLeaderRole = document.getElementById("groupEditLeaderRole");
  const btnEditAddScope = document.getElementById("btnEditAddScope");
  const btnEditAddLeader = document.getElementById("btnEditAddLeader");
  const btnEditCancel = document.getElementById("groupEditModalCancel");
  const btnEditSubmit = document.getElementById("groupEditModalSubmit");
  const editModalStatus = document.getElementById("groupEditModalStatus");

  let editGroupId = null;
  let editMemberships = [];
  let editLeaderPicker = null;

  function showEditStatus(msg, isError) {
    if (!editModalStatus) return;
    editModalStatus.textContent = msg || "";
    editModalStatus.style.color = isError ? "var(--err, #fda4af)" : "";
    editModalStatus.style.display = msg ? "block" : "none";
  }

  function setEditReadOnly(readOnly) {
    [editName, editOrder, editRegion, editDivision].forEach((el) => {
      if (el) el.disabled = readOnly;
    });
    if (btnEditAddScope) btnEditAddScope.hidden = readOnly;
    if (editExtraList) {
      editExtraList.querySelectorAll("select, button").forEach((el) => {
        el.disabled = readOnly;
        if (readOnly && el.matches("[data-remove-extra-scope]")) el.hidden = true;
      });
    }
    if (editLeadersAdd) editLeadersAdd.hidden = readOnly;
    if (btnEditSubmit) btnEditSubmit.hidden = readOnly;
  }

  function renderEditLeaders() {
    if (!editLeadersList) return;
    if (!editMemberships.length) {
      editLeadersList.innerHTML = '<p class="muted">등록된 운영진이 없습니다.</p>';
      return;
    }
    editLeadersList.innerHTML = editMemberships
      .map(
        (m) =>
          `<div class="jcc-retreat-leaderDraftRow" data-membership-id="${m.id}">
            <span>${escapeHtml(m.display_name || m.username || m.name || "")} · ${escapeHtml(m.role_display || editCtx.roleLabels?.[m.role] || m.role)}</span>
            ${editCtx.canAddGroup ? `<button type="button" class="jcc-retreat-rowDel" data-remove-membership="${m.id}">제거</button>` : ""}
          </div>`
      )
      .join("");
  }

  function clearEditExtraScopes() {
    if (editExtraList) editExtraList.innerHTML = "";
  }

  function populateEditForm(data) {
    if (editName) editName.value = data.name || "";
    if (editOrder) editOrder.value = String(data.order ?? 0);
    if (editRegion) editRegion.value = String(data.region || "");
    fillDivisionSelect(editDivision, data.region, data.division);
    clearEditExtraScopes();
    (data.extra_scopes || []).forEach((s) => {
      appendExtraScopeRow(editExtraList, s.region, s.division);
    });
    editMemberships = data.memberships || [];
    renderEditLeaders();
  }

  function openEditModal(groupId) {
    if (!editOverlay) return;
    editGroupId = groupId;
    showEditStatus("", false);
    setEditReadOnly(!editCtx.canAddGroup);
    if (editLeaderPicker) editLeaderPicker.clear();

    const url = editCtx.urls.groupDetailTemplate.replace("__gid__", String(groupId));
    editOverlay.hidden = false;
    editOverlay.setAttribute("aria-hidden", "false");
    if (editLeadersList) editLeadersList.innerHTML = '<p class="muted">불러오는 중…</p>';

    fetch(url, { credentials: "same-origin" })
      .then((r) => {
        if (!r.ok) throw new Error("조 정보를 불러오지 못했습니다.");
        return r.json();
      })
      .then((data) => {
        populateEditForm(data);
        requestAnimationFrame(() => editName?.focus());
      })
      .catch((err) => {
        showEditStatus(err.message || "불러오기 실패", true);
      });
  }

  function closeEditModal() {
    if (!editOverlay) return;
    editOverlay.hidden = true;
    editOverlay.setAttribute("aria-hidden", "true");
    editGroupId = null;
    editMemberships = [];
  }

  function collectEditPayload() {
    const name = (editName?.value || "").trim();
    const region = editRegion?.value;
    const division = editDivision?.value;
    const order = Number(editOrder?.value || 0) || 0;
    if (!name || !region || !division) {
      return { error: "조 이름·대표 지역·부서를 모두 입력하세요." };
    }
    const extra = collectExtraScopesFromList(editExtraList, "조");
    if (extra.error) return { error: extra.error };
    return {
      payload: {
        name,
        region: Number(region),
        division: Number(division),
        order,
        scopes: extra.scopes || [],
      },
    };
  }

  async function onEditSubmit(e) {
    e.preventDefault();
    if (!editCtx.canAddGroup || !editGroupId) return;
    const collected = collectEditPayload();
    if (collected.error) {
      showEditStatus(collected.error, true);
      return;
    }
    const url = editCtx.urls.groupDetailTemplate.replace("__gid__", String(editGroupId));
    try {
      const r = await fetch(url, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": editCtx.csrfToken,
        },
        credentials: "same-origin",
        body: JSON.stringify(collected.payload),
      });
      if (!r.ok) {
        let detail = "저장 실패";
        try {
          const j = await r.json();
          if (j.detail) detail = j.detail;
          else if (j && typeof j === "object") {
            const first = Object.values(j)[0];
            detail = Array.isArray(first) ? first[0] : first || JSON.stringify(j);
          }
        } catch (err) {}
        throw new Error(detail);
      }
      window.location.reload();
    } catch (err) {
      showEditStatus(err.message || "저장 실패", true);
    }
  }

  async function addEditLeader() {
    if (!editCtx.canAddGroup || !editGroupId || !editLeaderPicker) return;
    const selected = editLeaderPicker.getSelected();
    if (!selected || !selected.id) {
      showEditStatus("운영진으로 등록할 사용자를 검색에서 선택하세요.", true);
      return;
    }
    const role = editLeaderRole?.value || "leader";
    const url = editCtx.urls.membershipsTemplate.replace("__gid__", String(editGroupId));
    try {
      const r = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": editCtx.csrfToken,
        },
        credentials: "same-origin",
        body: JSON.stringify({ user_id: selected.id, role }),
      });
      if (!r.ok) {
        let detail = "운영진 추가 실패";
        try {
          const j = await r.json();
          detail = j.detail || JSON.stringify(j);
        } catch (err) {}
        throw new Error(detail);
      }
      const membership = await r.json();
      editMemberships = editMemberships.filter((m) => m.user !== membership.user);
      editMemberships.push(membership);
      renderEditLeaders();
      editLeaderPicker.clear();
      showEditStatus("", false);
    } catch (err) {
      showEditStatus(err.message || "운영진 추가 실패", true);
    }
  }

  async function removeEditLeader(membershipId) {
    if (!editCtx.canAddGroup) return;
    const url = editCtx.urls.membershipDetailTemplate.replace("__mid__", String(membershipId));
    try {
      const r = await fetch(url, {
        method: "DELETE",
        headers: { "X-CSRFToken": editCtx.csrfToken },
        credentials: "same-origin",
      });
      if (!r.ok) throw new Error("운영진 제거 실패");
      editMemberships = editMemberships.filter((m) => m.id !== membershipId);
      renderEditLeaders();
      showEditStatus("", false);
    } catch (err) {
      showEditStatus(err.message || "운영진 제거 실패", true);
    }
  }

  if (editRegion) {
    editRegion.addEventListener("change", () => {
      fillDivisionSelect(editDivision, editRegion.value);
      if (editLeaderPicker) editLeaderPicker.clear();
    });
  }
  if (editDivision) {
    editDivision.addEventListener("change", () => {
      if (editLeaderPicker) editLeaderPicker.clear();
    });
  }
  if (btnEditAddScope) {
    btnEditAddScope.addEventListener("click", () => appendExtraScopeRow(editExtraList));
  }
  if (btnEditAddLeader) btnEditAddLeader.addEventListener("click", addEditLeader);
  if (btnEditCancel) btnEditCancel.addEventListener("click", closeEditModal);
  if (editForm) editForm.addEventListener("submit", onEditSubmit);
  if (editOverlay) {
    editOverlay.addEventListener("click", (e) => {
      if (e.target === editOverlay) closeEditModal();
    });
  }
  if (editLeadersList) {
    editLeadersList.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-remove-membership]");
      if (!btn) return;
      removeEditLeader(Number(btn.dataset.removeMembership));
    });
  }

  editLeaderPicker = createUserPicker(document.getElementById("groupEditUserPicker"), () => ({
    division: editDivision?.value || "",
    region: editRegion?.value || "",
  }));

  document.querySelectorAll("[data-group-edit-trigger][data-group-id]").forEach((trigger) => {
    trigger.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      openEditModal(trigger.dataset.groupId);
    });
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (editOverlay && !editOverlay.hidden) closeEditModal();
  });

  window.RetreatGroupModal = {
    escapeHtml,
    fillDivisionSelect,
    bindExtraScopeRow,
    appendExtraScopeRow,
    collectExtraScopesFromList,
    createUserPicker,
    getAllDivisions: () => allDivisions,
    openEditModal,
    closeEditModal,
  };
})();
