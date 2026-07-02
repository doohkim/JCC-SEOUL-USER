(function () {
  "use strict";
  const ctx = window.RETREAT_COUNCIL_CTX;
  if (!ctx) return;

  const statusEl = document.getElementById("councilStatus");
  const tbody = document.getElementById("councilTbody");
  const form = document.getElementById("councilAddForm");
  const roleScopes = ctx.roleScopes || {};

  function csrf() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function showStatus(msg, isError) {
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

  function scopeKind(role) {
    return roleScopes[role] || "event";
  }

  function toggleScopeFields(role, regionWrap, divisionWrap) {
    const kind = scopeKind(role);
    if (regionWrap) regionWrap.hidden = kind !== "region" && kind !== "division";
    if (divisionWrap) divisionWrap.hidden = kind !== "division";
  }

  function filterDivisionsByRegion(selectEl, regionId) {
    if (!selectEl) return;
    Array.from(selectEl.options).forEach((opt, idx) => {
      if (idx === 0) {
        opt.hidden = false;
        return;
      }
      const rid = opt.dataset.regionId;
      opt.hidden = Boolean(regionId && rid && String(rid) !== String(regionId));
    });
    if (
      selectEl.value &&
      selectEl.selectedOptions[0] &&
      selectEl.selectedOptions[0].hidden
    ) {
      selectEl.value = "";
      window.JccCustomSelect?.refresh?.(
        selectEl.closest(".jcc-cselect") || selectEl.parentNode
      );
    }
  }

  function bindRowScopeEditors(tr) {
    if (!ctx.canManage || !tr) return;
    const roleSel = tr.querySelector(".council-role-select");
    const regionSel = tr.querySelector(".council-region-select");
    const divSel = tr.querySelector(".council-division-select");
    const scopeEdit = tr.querySelector(".jcc-retreat-staffScopeEdit");
    const scopeDisplay = tr.querySelector(".jcc-retreat-staffScopeDisplay");
    const saveBtn = tr.querySelector(".council-save-row");

    function syncRowScopeVisibility() {
      const kind = scopeKind(roleSel?.value || tr.dataset.role);
      if (scopeEdit) scopeEdit.hidden = kind === "event";
      if (scopeDisplay) scopeDisplay.hidden = kind !== "event";
      if (regionSel) regionSel.hidden = kind === "division" || kind === "event";
      if (divSel) divSel.hidden = kind !== "division";
      if (regionSel && kind === "division") {
        filterDivisionsByRegion(divSel, regionSel.value);
      }
    }

    roleSel?.addEventListener("change", () => {
      syncRowScopeVisibility();
      if (saveBtn) saveBtn.hidden = false;
    });
    regionSel?.addEventListener("change", () => {
      filterDivisionsByRegion(divSel, regionSel.value);
      if (saveBtn) saveBtn.hidden = false;
    });
    divSel?.addEventListener("change", () => {
      if (saveBtn) saveBtn.hidden = false;
    });
    tr.querySelector(".council-note-input")?.addEventListener("input", () => {
      if (saveBtn) saveBtn.hidden = false;
    });
    syncRowScopeVisibility();
  }

  function createUserPicker(root, searchUrl) {
    if (!root || !searchUrl) return null;
    const input = root.querySelector("[data-user-picker-input]");
    const list = root.querySelector("[data-user-picker-list]");
    const hidden = root.querySelector("[data-user-picker-id]");
    if (!input || !list || !hidden) return null;

    let selected = null;
    let items = [];
    let timer = null;
    let lastQuery = "";

    function closeList() {
      list.hidden = true;
      list.innerHTML = "";
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
          return `<li role="option" data-idx="${i}">${escapeHtml(shown)}</li>`;
        })
        .join("");
      list.hidden = false;
    }

    async function search(q) {
      lastQuery = q;
      try {
        const params = new URLSearchParams();
        if (q) params.set("q", q);
        params.set("limit", "30");
        const r = await fetch(`${searchUrl}?${params.toString()}`, {
          credentials: "same-origin",
        });
        if (!r.ok) throw new Error(await r.text());
        if (q !== lastQuery) return;
        items = await r.json();
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

    input.addEventListener("input", () => {
      selected = null;
      hidden.value = "";
      const q = input.value.trim();
      clearTimeout(timer);
      timer = setTimeout(() => search(q), 180);
    });

    input.addEventListener("focus", () => {
      if (!input.value.trim()) search("");
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

    return {
      getSelected: () => selected,
      getTypedValue: () => input.value.trim(),
    };
  }

  const addRole = document.querySelector("[data-staff-role]");
  const addRegionWrap = document.querySelector("[data-staff-scope-region]");
  const addDivisionWrap = document.querySelector("[data-staff-scope-division]");
  const addRegion = document.querySelector("[data-staff-region]");
  const addDivision = document.querySelector("[data-staff-division]");

  if (addRole) {
    addRole.addEventListener("change", () => {
      toggleScopeFields(addRole.value, addRegionWrap, addDivisionWrap);
    });
    toggleScopeFields(addRole.value, addRegionWrap, addDivisionWrap);
  }
  addRegion?.addEventListener("change", () => {
    filterDivisionsByRegion(addDivision, addRegion.value);
  });

  const userPicker = ctx.canManage
    ? createUserPicker(
        document.getElementById("councilUserPicker"),
        ctx.userSearchUrl
      )
    : null;

  if (ctx.canManage && form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const selected = userPicker && userPicker.getSelected();
      const typed = userPicker
        ? userPicker.getTypedValue()
        : document.getElementById("newUsername")?.value.trim();
      const role = addRole?.value || "event_admin";
      const note = document.getElementById("newNote")?.value.trim() || "";
      const body = { role, note };
      const kind = scopeKind(role);
      if (kind === "region") {
        body.region = addRegion?.value ? Number(addRegion.value) : null;
        if (!body.region) {
          showStatus("담당 지역을 선택하세요.", true);
          return;
        }
      }
      if (kind === "division") {
        body.division = addDivision?.value ? Number(addDivision.value) : null;
        if (!body.division) {
          showStatus("담당 부서를 선택하세요.", true);
          return;
        }
      }
      if (selected && selected.id) {
        body.user_id = selected.id;
      } else if (typed) {
        body.username = typed;
      } else {
        showStatus("사용자를 검색해서 선택하세요.", true);
        return;
      }
      try {
        const r = await fetch(ctx.apiList, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrf(),
          },
          body: JSON.stringify(body),
        });
        if (!r.ok) {
          const err = await r.json().catch(() => ({}));
          const msg =
            err.scope ||
            err.region ||
            err.division ||
            err.user ||
            err.detail ||
            "추가 실패";
          throw new Error(
            typeof msg === "string" ? msg : JSON.stringify(msg)
          );
        }
        window.location.reload();
      } catch (err) {
        showStatus(String(err.message || err), true);
      }
    });
  }

  const filterRole = document.getElementById("staffFilterRole");
  filterRole?.addEventListener("change", () => {
    const val = filterRole.value;
    tbody?.querySelectorAll("tr[data-membership-id]").forEach((tr) => {
      tr.hidden = Boolean(val && tr.dataset.role !== val);
    });
  });

  if (ctx.canManage && tbody) {
    tbody.querySelectorAll("tr[data-membership-id]").forEach(bindRowScopeEditors);

    tbody.addEventListener("click", async (e) => {
      const del = e.target.closest(".council-delete");
      if (del) {
        const tr = del.closest("tr[data-membership-id]");
        const mid = tr && tr.dataset.membershipId;
        if (!mid) return;
        if (!confirm("운영진에서 제거하시겠습니까?")) return;
        try {
          const r = await fetch(`${ctx.apiDetailBase}${mid}/`, {
            method: "DELETE",
            credentials: "same-origin",
            headers: { "X-CSRFToken": csrf() },
          });
          if (!r.ok) throw new Error(await r.text());
          tr.remove();
        } catch (err) {
          showStatus("삭제 실패", true);
          console.error(err);
        }
        return;
      }

      const save = e.target.closest(".council-save-row");
      if (!save) return;
      const tr = save.closest("tr[data-membership-id]");
      const mid = tr?.dataset.membershipId;
      if (!mid) return;
      const role = tr.querySelector(".council-role-select")?.value;
      const note = tr.querySelector(".council-note-input")?.value?.trim() || "";
      const body = { role, note };
      const kind = scopeKind(role);
      if (kind === "region") {
        const rid = tr.querySelector(".council-region-select")?.value;
        body.region = rid ? Number(rid) : null;
      } else if (kind === "division") {
        const did = tr.querySelector(".council-division-select")?.value;
        body.division = did ? Number(did) : null;
      } else {
        body.region = null;
        body.division = null;
      }
      try {
        const r = await fetch(`${ctx.apiDetailBase}${mid}/`, {
          method: "PATCH",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrf(),
          },
          body: JSON.stringify(body),
        });
        if (!r.ok) {
          const err = await r.json().catch(() => ({}));
          throw new Error(err.detail || err.scope || "저장 실패");
        }
        save.hidden = true;
        showStatus("저장됨");
        window.location.reload();
      } catch (err) {
        showStatus(String(err.message || err), true);
      }
    });
  }
})();
