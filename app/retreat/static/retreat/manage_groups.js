/**
 * 조 관리 목록 — 조 추가 모달
 */
(function () {
  "use strict";

  const ctx = window.RETREAT_GROUPS_CTX;
  if (!ctx) return;

  const modal = window.RetreatGroupModal;
  if (!modal) return;

  const {
    fillDivisionSelect,
    appendExtraScopeRow,
    collectExtraScopesFromList,
    createUserPicker,
    escapeHtml,
  } = modal;

  const statusEl = document.getElementById("retreatStatus");

  function showStatus(msg, isError, modalStatusEl) {
    const inModal = modalStatusEl && modalStatusEl.offsetParent !== null;
    if (inModal) {
      if (statusEl) statusEl.textContent = "";
      modalStatusEl.textContent = msg || "";
      modalStatusEl.style.color = isError ? "var(--err, #fda4af)" : "";
      modalStatusEl.style.display = msg ? "block" : "none";
      return;
    }
    if (!statusEl) return;
    statusEl.textContent = msg || "";
    statusEl.style.color = isError ? "var(--err, #fda4af)" : "";
  }

  const overlay = document.getElementById("groupModalOverlay");
  const form = document.getElementById("groupForm");
  const btnAdd = document.getElementById("btnAddGroup");
  const btnAddRow = document.getElementById("btnAddGroupRow");
  const btnCancel = document.getElementById("groupModalCancel");
  const eventInput = document.getElementById("groupEventInput");
  const rowsList = document.getElementById("groupRowsList");
  const rowTemplate = document.getElementById("groupRowTemplate");
  const modalStatusEl = document.getElementById("groupModalStatus");
  const rowStates = [];

  function refreshRowDivisions(rowEl, selectedId) {
    const regionInput = rowEl.querySelector("[data-row-region]");
    const divisionInput = rowEl.querySelector("[data-row-division]");
    fillDivisionSelect(divisionInput, regionInput?.value || "", selectedId);
  }

  function addExtraScopeToRow(rowEl) {
    const list = rowEl.querySelector("[data-extra-scopes-list]");
    appendExtraScopeRow(list);
  }

  function roleOptionsHtml(selectedRole) {
    const labels = ctx.roleLabels || {};
    return Object.entries(labels)
      .map(
        ([code, label]) =>
          `<option value="${escapeHtml(code)}"${code === selectedRole ? " selected" : ""}>${escapeHtml(label)}</option>`
      )
      .join("");
  }

  function renderRowLeaders(state, highlightIdx) {
    const list = state.el.querySelector("[data-row-leaders-list]");
    if (!list) return;
    if (!state.leaders.length) {
      list.innerHTML = '<p class="muted">등록할 운영진이 없습니다.</p>';
      return;
    }
    list.innerHTML = state.leaders
      .map((e, i) => {
        const rowClass =
          highlightIdx === i
            ? "jcc-retreat-leaderDraftRow is-new"
            : "jcc-retreat-leaderDraftRow";
        return `<div class="${rowClass}">
            <span class="jcc-retreat-leaderDraftName">${escapeHtml(e.label)}</span>
            <select class="jcc-retreat-leaderRoleSelect" data-leader-role-idx="${i}" aria-label="역할" data-cselect>${roleOptionsHtml(e.role)}</select>
            <button type="button" class="jcc-retreat-rowDel" data-remove-leader="${i}">제거</button>
          </div>`;
      })
      .join("");
    if (window.JccCustomSelect) window.JccCustomSelect.init(list);
    if (highlightIdx != null) {
      requestAnimationFrame(() => {
        const row = list.querySelector(`[data-leader-role-idx="${highlightIdx}"]`)?.closest(
          ".jcc-retreat-leaderDraftRow"
        );
        row?.classList.remove("is-new");
      });
    }
  }

  function addRowLeader(state, user) {
    if (!user?.id) return;
    const leaderRoleInput = state.el.querySelector("[data-row-leader-role]");
    const role = leaderRoleInput?.value || "leader";
    if (state.leaders.some((e) => e.user_id === user.id)) {
      showStatus("이미 목록에 있는 사용자입니다.", true, modalStatusEl);
      return;
    }
    state.leaders.push({
      user_id: user.id,
      role,
      label: user.name || user.display_name || user.username,
    });
    renderRowLeaders(state, state.leaders.length - 1);
    showStatus("", false, modalStatusEl);
  }

  function updateRowLabels() {
    rowStates.forEach((state, idx) => {
      const label = state.el.querySelector("[data-row-label]");
      if (label) label.textContent = `조 ${idx + 1}`;
    });
  }

  function bindRowEvents(state) {
    const rowEl = state.el;
    const regionInput = rowEl.querySelector("[data-row-region]");
    const divisionInput = rowEl.querySelector("[data-row-division]");
    const btnRemove = rowEl.querySelector("[data-remove-row]");
    const btnAddScope = rowEl.querySelector("[data-add-extra-scope]");
    const leadersList = rowEl.querySelector("[data-row-leaders-list]");

    state.picker = createUserPicker(
      rowEl.querySelector("[data-user-picker]"),
      () => ({
        division: divisionInput?.value || "",
        region: regionInput?.value || "",
      }),
      (user) => addRowLeader(state, user)
    );

    if (regionInput) {
      regionInput.addEventListener("change", () => {
        refreshRowDivisions(rowEl);
        if (state.picker) state.picker.clear();
      });
    }
    if (divisionInput) {
      divisionInput.addEventListener("change", () => {
        if (state.picker) state.picker.clear();
      });
    }
    if (btnAddScope) {
      btnAddScope.addEventListener("click", () => addExtraScopeToRow(rowEl));
    }
    if (btnRemove) {
      btnRemove.addEventListener("click", () => {
        if (rowStates.length <= 1) {
          showStatus("최소 1개 행은 유지해야 합니다.", true, modalStatusEl);
          return;
        }
        const idx = rowStates.indexOf(state);
        if (idx >= 0) rowStates.splice(idx, 1);
        rowEl.remove();
        updateRowLabels();
        showStatus("", false, modalStatusEl);
      });
    }
    if (leadersList) {
      leadersList.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-remove-leader]");
        if (!btn) return;
        const idx = Number(btn.dataset.removeLeader);
        state.leaders.splice(idx, 1);
        renderRowLeaders(state);
      });
      leadersList.addEventListener("change", (e) => {
        const sel = e.target.closest("[data-leader-role-idx]");
        if (!sel) return;
        const idx = Number(sel.dataset.leaderRoleIdx);
        if (state.leaders[idx]) state.leaders[idx].role = sel.value;
      });
    }
    renderRowLeaders(state);
  }

  function addRow() {
    if (!rowTemplate || !rowsList) return null;
    const frag = rowTemplate.content.cloneNode(true);
    const rowEl = frag.querySelector("[data-group-row]");
    if (!rowEl) return null;
    rowsList.appendChild(rowEl);
    if (window.JccCustomSelect) window.JccCustomSelect.init(rowEl);
    const state = { el: rowEl, leaders: [], picker: null };
    rowStates.push(state);
    bindRowEvents(state);
    updateRowLabels();
    return state;
  }

  function resetRows() {
    rowStates.length = 0;
    if (rowsList) rowsList.innerHTML = "";
    addRow();
  }

  function openCreateModal() {
    if (!overlay) return;
    if (modalStatusEl) {
      modalStatusEl.textContent = "";
      modalStatusEl.style.display = "none";
    }
    if (eventInput) {
      eventInput.value = String(ctx.defaultEventId);
      if (window.JccCustomSelect) {
        window.JccCustomSelect.refresh(eventInput.closest(".jcc-cselect"));
      }
    }
    resetRows();
    overlay.hidden = false;
    overlay.setAttribute("aria-hidden", "false");
    requestAnimationFrame(() => {
      const firstName = rowsList?.querySelector("[data-row-name]");
      firstName?.focus();
    });
  }

  function closeCreateModal() {
    if (!overlay) return;
    overlay.hidden = true;
    overlay.setAttribute("aria-hidden", "true");
  }

  function collectGroupsPayload() {
    const groups = [];
    for (let i = 0; i < rowStates.length; i += 1) {
      const state = rowStates[i];
      const rowEl = state.el;
      const region = rowEl.querySelector("[data-row-region]")?.value;
      const division = rowEl.querySelector("[data-row-division]")?.value;
      const name = (rowEl.querySelector("[data-row-name]")?.value || "").trim();
      const order = Number(rowEl.querySelector("[data-row-order]")?.value || 0) || 0;
      if (!name && !region && !division) continue;
      if (!name || !region || !division) {
        return { error: `${i + 1}번째 조: 대표 지역·부서·조 이름을 모두 입력하세요.` };
      }
      const extra = collectExtraScopesFromList(
        rowEl.querySelector("[data-extra-scopes-list]"),
        `${i + 1}번째 조`
      );
      if (extra.error) return { error: extra.error };
      groups.push({
        region: Number(region),
        division: Number(division),
        name,
        order,
        scopes: extra.scopes || [],
        leaders: state.leaders.map((e) => ({ user_id: e.user_id, role: e.role })),
      });
    }
    if (!groups.length) {
      return { error: "추가할 조가 없습니다." };
    }
    return { groups };
  }

  async function onCreateSubmit(e) {
    e.preventDefault();
    const eventId = eventInput?.value;
    const collected = collectGroupsPayload();
    if (collected.error) {
      showStatus(collected.error, true, modalStatusEl);
      return;
    }
    const url = ctx.urls.eventGroupsTemplate.replace("__eid__", String(eventId));
    try {
      const r = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": ctx.csrfToken,
        },
        credentials: "same-origin",
        body: JSON.stringify({ groups: collected.groups }),
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
      showStatus(`${collected.groups.length}개 조가 추가되었습니다.`, false, null);
      window.location.reload();
    } catch (err) {
      showStatus(err.message || "저장 실패", true, modalStatusEl);
    }
  }

  if (btnAdd) btnAdd.addEventListener("click", openCreateModal);
  if (btnAddRow) btnAddRow.addEventListener("click", () => addRow());
  if (btnCancel) btnCancel.addEventListener("click", closeCreateModal);
  if (overlay) {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) closeCreateModal();
    });
  }
  if (form) form.addEventListener("submit", onCreateSubmit);

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (overlay && !overlay.hidden) closeCreateModal();
  });
})();
