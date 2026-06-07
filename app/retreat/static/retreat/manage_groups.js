/**
 * 조 관리 목록 — 조 추가 모달
 */
(function () {
  "use strict";

  const ctx = window.RETREAT_GROUPS_CTX;
  if (!ctx) return;

  const overlay = document.getElementById("groupModalOverlay");
  const form = document.getElementById("groupForm");
  const btnAdd = document.getElementById("btnAddGroup");
  const btnCancel = document.getElementById("groupModalCancel");
  const eventInput = document.getElementById("groupEventInput");
  const regionInput = document.getElementById("groupRegionInput");
  const divisionInput = document.getElementById("groupDivisionInput");
  const nameInput = document.getElementById("groupNameInput");
  const orderInput = document.getElementById("groupOrderInput");
  const leadersList = document.getElementById("groupLeadersDraftList");
  const btnAddLeaderDraft = document.getElementById("btnAddLeaderDraft");
  const leaderRoleInput = document.getElementById("groupLeaderRoleInput");
  const statusEl = document.getElementById("retreatStatus");
  const modalStatusEl = document.getElementById("groupModalStatus");

  let allDivisions = [];
  try {
    const raw = document.getElementById("retreatDivisionList")?.textContent || "[]";
    allDivisions = JSON.parse(raw);
  } catch (e) {
    allDivisions = [];
  }

  const leaderDraft = [];
  const picker = createUserPicker(
    document.querySelector("#groupForm [data-user-picker]"),
    () => ({
      division: divisionInput?.value || "",
      region: regionInput?.value || "",
    })
  );

  function showStatus(msg, isError) {
    // 모달이 열려 있으면 모달 안에, 아니면 상단에 표시한다.
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

  function refreshDivisions(selectedId) {
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

  function renderLeaderDraft() {
    if (!leadersList) return;
    if (!leaderDraft.length) {
      leadersList.innerHTML = '<p class="muted">등록할 운영진이 없습니다.</p>';
      return;
    }
    leadersList.innerHTML = leaderDraft
      .map(
        (e, i) =>
          `<div class="jcc-retreat-leaderDraftRow">
            <span>${escapeHtml(e.label)} · ${escapeHtml(ctx.roleLabels[e.role] || e.role)}</span>
            <button type="button" class="jcc-retreat-rowDel" data-remove-leader="${i}">제거</button>
          </div>`
      )
      .join("");
  }

  function openModal() {
    if (!overlay) return;
    if (modalStatusEl) {
      modalStatusEl.textContent = "";
      modalStatusEl.style.display = "none";
    }
    leaderDraft.length = 0;
    renderLeaderDraft();
    if (picker) picker.clear();
    if (nameInput) nameInput.value = "";
    if (orderInput) orderInput.value = "0";
    if (eventInput) eventInput.value = String(ctx.defaultEventId);
    if (regionInput) regionInput.value = "";
    refreshDivisions();
    overlay.hidden = false;
    overlay.setAttribute("aria-hidden", "false");
    requestAnimationFrame(() => nameInput?.focus());
  }

  function closeModal() {
    if (!overlay) return;
    overlay.hidden = true;
    overlay.setAttribute("aria-hidden", "true");
  }

  async function onSubmit(e) {
    e.preventDefault();
    const eventId = eventInput?.value;
    const payload = {
      region: regionInput?.value ? Number(regionInput.value) : null,
      division: divisionInput?.value ? Number(divisionInput.value) : null,
      name: (nameInput?.value || "").trim(),
      order: Number(orderInput?.value || 0) || 0,
      leaders: leaderDraft.map((e) => ({ user_id: e.user_id, role: e.role })),
    };
    if (!payload.name || !payload.region || !payload.division) {
      showStatus("행사·지역·부서·조 이름을 확인하세요.", true);
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
        body: JSON.stringify(payload),
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
      showStatus("조가 추가되었습니다.");
      window.location.reload();
    } catch (err) {
      showStatus(err.message || "저장 실패", true);
    }
  }

  if (btnAdd) btnAdd.addEventListener("click", openModal);
  if (btnCancel) btnCancel.addEventListener("click", closeModal);
  if (overlay) {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) closeModal();
    });
  }
  if (regionInput) {
    regionInput.addEventListener("change", () => {
      refreshDivisions();
      if (picker) picker.clear();
    });
  }
  if (divisionInput) {
    divisionInput.addEventListener("change", () => {
      if (picker) picker.clear();
    });
  }
  if (form) form.addEventListener("submit", onSubmit);
  if (btnAddLeaderDraft) {
    btnAddLeaderDraft.addEventListener("click", () => {
      const selected = picker && picker.getSelected();
      if (!selected || !selected.id) {
        showStatus("운영진으로 등록할 사용자를 검색에서 선택하세요.", true);
        return;
      }
      const role = leaderRoleInput?.value || "leader";
      if (leaderDraft.some((e) => e.user_id === selected.id)) {
        showStatus("이미 목록에 있는 사용자입니다.", true);
        return;
      }
      leaderDraft.push({
        user_id: selected.id,
        role,
        label: selected.name || selected.display_name || selected.username,
      });
      renderLeaderDraft();
      if (picker) picker.clear();
      showStatus("");
    });
  }
  if (leadersList) {
    leadersList.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-remove-leader]");
      if (!btn) return;
      const idx = Number(btn.dataset.removeLeader);
      leaderDraft.splice(idx, 1);
      renderLeaderDraft();
    });
  }

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
      // 검색어도 부서·지역 필터도 없으면 호출하지 않는다.
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
      // 검색어가 비어도 부서·지역이 선택돼 있으면 소속 전체를 보여준다.
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
