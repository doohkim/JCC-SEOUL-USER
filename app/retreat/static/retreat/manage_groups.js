/**
 * 조 관리 목록 — 여러 조 일괄 추가 모달
 */
(function () {
  "use strict";

  const ctx = window.RETREAT_GROUPS_CTX;
  if (!ctx) return;

  const overlay = document.getElementById("groupModalOverlay");
  const form = document.getElementById("groupForm");
  const btnAdd = document.getElementById("btnAddGroup");
  const btnAddRow = document.getElementById("btnAddGroupRow");
  const btnCancel = document.getElementById("groupModalCancel");
  const eventInput = document.getElementById("groupEventInput");
  const rowsList = document.getElementById("groupRowsList");
  const rowTemplate = document.getElementById("groupRowTemplate");
  const statusEl = document.getElementById("retreatStatus");
  const modalStatusEl = document.getElementById("groupModalStatus");

  let allDivisions = [];
  try {
    const raw = document.getElementById("retreatDivisionList")?.textContent || "[]";
    allDivisions = JSON.parse(raw);
  } catch (e) {
    allDivisions = [];
  }

  /** @type {Array<{el: HTMLElement, leaders: Array, picker: object|null}>} */
  const rowStates = [];

  function showStatus(msg, isError) {
    const inModal = overlay && !overlay.hidden && modalStatusEl;
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

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function refreshRowDivisions(rowEl, selectedId) {
    const regionInput = rowEl.querySelector("[data-row-region]");
    const divisionInput = rowEl.querySelector("[data-row-division]");
    if (!divisionInput) return;
    const rid = regionInput?.value || "";
    divisionInput.innerHTML = '<option value="">선택</option>';
    if (!rid) return;
    const regionId = Number(rid);
    allDivisions
      .filter((d) => d.region_id === regionId)
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

  function renderRowLeaders(state) {
    const list = state.el.querySelector("[data-row-leaders-list]");
    if (!list) return;
    if (!state.leaders.length) {
      list.innerHTML = '<p class="muted">등록할 운영진이 없습니다.</p>';
      return;
    }
    list.innerHTML = state.leaders
      .map(
        (e, i) =>
          `<div class="jcc-retreat-leaderDraftRow">
            <span>${escapeHtml(e.label)} · ${escapeHtml(ctx.roleLabels[e.role] || e.role)}</span>
            <button type="button" class="jcc-retreat-rowDel" data-remove-leader="${i}">제거</button>
          </div>`
      )
      .join("");
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
    const btnAddLeader = rowEl.querySelector("[data-add-row-leader]");
    const leaderRoleInput = rowEl.querySelector("[data-row-leader-role]");
    const leadersList = rowEl.querySelector("[data-row-leaders-list]");

    state.picker = createUserPicker(
      rowEl.querySelector("[data-user-picker]"),
      () => ({
        division: divisionInput?.value || "",
        region: regionInput?.value || "",
      })
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
    if (btnRemove) {
      btnRemove.addEventListener("click", () => {
        if (rowStates.length <= 1) {
          showStatus("최소 1개 행은 유지해야 합니다.", true);
          return;
        }
        const idx = rowStates.indexOf(state);
        if (idx >= 0) rowStates.splice(idx, 1);
        rowEl.remove();
        updateRowLabels();
        showStatus("");
      });
    }
    if (btnAddLeader) {
      btnAddLeader.addEventListener("click", () => {
        const selected = state.picker && state.picker.getSelected();
        if (!selected || !selected.id) {
          showStatus("운영진으로 등록할 사용자를 검색에서 선택하세요.", true);
          return;
        }
        const role = leaderRoleInput?.value || "leader";
        if (state.leaders.some((e) => e.user_id === selected.id)) {
          showStatus("이미 목록에 있는 사용자입니다.", true);
          return;
        }
        state.leaders.push({
          user_id: selected.id,
          role,
          label: selected.name || selected.display_name || selected.username,
        });
        renderRowLeaders(state);
        if (state.picker) state.picker.clear();
        showStatus("");
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
    }

    renderRowLeaders(state);
  }

  function addRow() {
    if (!rowTemplate || !rowsList) return null;
    const frag = rowTemplate.content.cloneNode(true);
    const rowEl = frag.querySelector("[data-group-row]");
    if (!rowEl) return null;
    rowsList.appendChild(rowEl);
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

  function openModal() {
    if (!overlay) return;
    if (modalStatusEl) {
      modalStatusEl.textContent = "";
      modalStatusEl.style.display = "none";
    }
    if (eventInput) eventInput.value = String(ctx.defaultEventId);
    resetRows();
    overlay.hidden = false;
    overlay.setAttribute("aria-hidden", "false");
    requestAnimationFrame(() => {
      const firstName = rowsList?.querySelector("[data-row-name]");
      firstName?.focus();
    });
  }

  function closeModal() {
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
        return { error: `${i + 1}번째 행: 지역·부서·조 이름을 모두 입력하세요.` };
      }
      groups.push({
        region: Number(region),
        division: Number(division),
        name,
        order,
        leaders: state.leaders.map((e) => ({ user_id: e.user_id, role: e.role })),
      });
    }
    if (!groups.length) {
      return { error: "추가할 조가 없습니다." };
    }
    return { groups };
  }

  async function onSubmit(e) {
    e.preventDefault();
    const eventId = eventInput?.value;
    const collected = collectGroupsPayload();
    if (collected.error) {
      showStatus(collected.error, true);
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
          if (j.detail) {
            detail = j.detail;
          } else if (j && typeof j === "object") {
            const first = Object.values(j)[0];
            detail = Array.isArray(first) ? first[0] : first || JSON.stringify(j);
          }
        } catch (err) {}
        throw new Error(detail);
      }
      showStatus(`${collected.groups.length}개 조가 추가되었습니다.`);
      window.location.reload();
    } catch (err) {
      showStatus(err.message || "저장 실패", true);
    }
  }

  if (btnAdd) btnAdd.addEventListener("click", openModal);
  if (btnAddRow) btnAddRow.addEventListener("click", () => addRow());
  if (btnCancel) btnCancel.addEventListener("click", closeModal);
  if (overlay) {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) closeModal();
    });
  }
  if (form) form.addEventListener("submit", onSubmit);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && overlay && !overlay.hidden) closeModal();
  });

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
        list.innerHTML =
          '<li class="muted" role="option" aria-disabled="true">결과 없음</li>';
        list.hidden = false;
        return;
      }
      list.innerHTML = items
        .map((u, i) => {
          const shown = u.name || u.display_name || u.username;
          return `<li role="option" data-idx="${i}" class="${
            i === activeIdx ? "is-active" : ""
          }">${escapeHtml(shown)}</li>`;
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
        const url = `${ctx.urls.userSearchUrl}?${params.toString()}`;
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
})();
