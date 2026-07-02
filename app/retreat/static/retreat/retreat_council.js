(function () {
  "use strict";
  const ctx = window.RETREAT_COUNCIL_CTX;
  if (!ctx) return;

  const roleScopes = ctx.roleScopes || {};
  const statusEl = document.getElementById("staffRosterStatus");
  const rosterTbody = document.getElementById("staffRosterTbody");
  const rosterCards = document.getElementById("staffRosterCards");
  const waitingList = document.getElementById("staffWaitingList");
  const filterPills = document.getElementById("staffFilterPills");
  const modalOverlay = document.getElementById("staffModalOverlay");
  const modalForm = document.getElementById("staffModalForm");
  const modalTitle = document.getElementById("staffModalTitle");
  const modalSubtitle = document.getElementById("staffModalSubtitle");
  const modalStatus = document.getElementById("staffModalStatus");
  const confirmOverlay = document.getElementById("staffConfirmOverlay");
  const confirmMsg = document.getElementById("staffConfirmMsg");
  const confirmOk = document.getElementById("staffConfirmOk");
  const confirmCancel = document.getElementById("staffConfirmCancel");

  let rosterRows = [];
  let groupsCache = [];
  let activeFilter = "all";
  let editingRow = null;
  let modalMode = "council";
  let confirmResolve = null;

  function csrf() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function showStatus(msg, isError) {
    if (!statusEl) return;
    statusEl.textContent = msg || "";
    statusEl.style.color = isError ? "var(--err, #fda4af)" : "";
  }

  function showModalStatus(msg, isError) {
    if (!modalStatus) return;
    modalStatus.textContent = msg || "";
    modalStatus.style.color = isError ? "var(--err, #fda4af)" : "";
  }

  function scopeKind(role) {
    return roleScopes[role] || "event";
  }

  function rowCategory(row) {
    if (row.kind === "group") return "leader";
    if (row.role === "pickup_observer") return "pickup";
    if (row.role === "event_admin" || row.role === "event_observer") return "event";
    if (
      row.role === "region_admin" ||
      row.role === "region_observer" ||
      row.role === "division_admin" ||
      row.role === "division_observer"
    ) {
      return "region_division";
    }
    return "event";
  }

  function formatDate(value) {
    if (!value) return "—";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value).slice(0, 10);
    return d.toLocaleDateString("ko-KR");
  }

  function trashIconSvg() {
    return `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 7h16M9 7V5h6v2M10 11v6M14 11v6M6 7l1 13h10l1-13" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  }

  function phoneDisplay(raw) {
    const digits = String(raw || "").replace(/\D/g, "");
    if (digits.length === 11) {
      return `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7)}`;
    }
    if (digits.length === 10) {
      return `${digits.slice(0, 3)}-${digits.slice(3, 6)}-${digits.slice(6)}`;
    }
    return String(raw || "").trim();
  }

  function renderNameCell(row) {
    const retiredBadge = row.accountRetiredDisplay
      ? `<span class="jcc-retreat-checkInBadge jcc-retreat-checkInBadge--account_retired">${escapeHtml(row.accountRetiredDisplay)}</span>`
      : "";
    if (!ctx.canManage) {
      return `<td><span class="jcc-retreat-staffName">${escapeHtml(row.name)}</span>${retiredBadge}</td>`;
    }
    return `<td><button type="button" class="jcc-retreat-staffNameBtn staff-name-btn" data-row-id="${row.kind}-${row.id}">${escapeHtml(row.name)}</button>${retiredBadge}</td>`;
  }

  function renderDeleteAction(row) {
    if (!ctx.canManage) return "";
    return `<td class="jcc-retreat-staffColAction">
      <button type="button" class="jcc-retreat-staffDeleteBtn staff-delete-btn" data-row-id="${row.kind}-${row.id}" aria-label="${escapeHtml(row.name)} 삭제" title="삭제">
        ${trashIconSvg()}
      </button>
    </td>`;
  }

  function roleBadgeClass(role, kind) {
    if (kind === "group") {
      return role === "vice_leader"
        ? "jcc-retreat-staffRoleTag--vice_leader"
        : "jcc-retreat-staffRoleTag--leader";
    }
    return `jcc-retreat-staffRoleTag--${role}`;
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

  function toggleScopeFields(role, regionWrap, divisionWrap) {
    if (!role) {
      if (regionWrap) regionWrap.hidden = true;
      if (divisionWrap) divisionWrap.hidden = true;
      return;
    }
    const kind = scopeKind(role);
    if (regionWrap) regionWrap.hidden = kind !== "region" && kind !== "division";
    if (divisionWrap) divisionWrap.hidden = kind !== "division";
  }

  function scopeFieldElements() {
    return {
      regionWrap: document.querySelector("[data-staff-scope-region]"),
      divisionWrap: document.querySelector("[data-staff-scope-division]"),
      regionSel: document.getElementById("staffModalRegion"),
      divisionSel: document.getElementById("staffModalDivision"),
    };
  }

  function setScopeSelectsLocked(locked) {
    const { regionSel, divisionSel } = scopeFieldElements();
    [regionSel, divisionSel].forEach((sel) => {
      if (sel) sel.disabled = !!locked;
    });
    window.JccCustomSelect?.refresh?.(modalOverlay);
  }

  function userAffiliationFromSelection(selected) {
    if (!selected) return { region_id: null, division_id: null };
    return {
      region_id:
        selected.region_id != null
          ? Number(selected.region_id)
          : selected.userRegionId != null
            ? Number(selected.userRegionId)
            : null,
      division_id:
        selected.division_id != null
          ? Number(selected.division_id)
          : selected.userDivisionId != null
            ? Number(selected.userDivisionId)
            : null,
    };
  }

  function syncScopeFromUser(user, role) {
    const { regionWrap, divisionWrap, regionSel, divisionSel } = scopeFieldElements();
    if (!role) {
      toggleScopeFields("", regionWrap, divisionWrap);
      if (regionSel) regionSel.value = "";
      if (divisionSel) divisionSel.value = "";
      setScopeSelectsLocked(false);
      window.JccCustomSelect?.refresh?.(modalOverlay);
      return;
    }

    const kind = scopeKind(role);
    toggleScopeFields(role, regionWrap, divisionWrap);
    const { region_id: regionId, division_id: divisionId } = userAffiliationFromSelection(user);

    if (kind === "event") {
      if (regionSel) regionSel.value = "";
      if (divisionSel) divisionSel.value = "";
      setScopeSelectsLocked(true);
    } else if (kind === "region") {
      if (regionSel && regionId) regionSel.value = String(regionId);
      if (divisionSel) divisionSel.value = "";
      setScopeSelectsLocked(true);
    } else if (kind === "division") {
      if (regionSel && regionId) regionSel.value = String(regionId);
      filterDivisionsByRegion(divisionSel, regionId);
      if (divisionSel && divisionId) divisionSel.value = String(divisionId);
      setScopeSelectsLocked(true);
    } else {
      setScopeSelectsLocked(false);
    }
    window.JccCustomSelect?.refresh?.(modalOverlay);
  }

  function isCombinedGroupEdit() {
    return editingRow?.kind === "group";
  }

  function councilRowForUser(userId) {
    return rosterRows.find((row) => row.kind === "council" && row.userId === userId) || null;
  }

  function toggleModalPanels(mode) {
    modalMode = mode;
    const modalCard = modalOverlay?.querySelector(".jcc-retreat-modal--staff");
    const combined = isCombinedGroupEdit();
    if (modalCard) {
      modalCard.classList.toggle("jcc-retreat-modal--staffGroup", mode === "group" && !combined);
      modalCard.classList.toggle("jcc-retreat-modal--staffCouncil", mode === "council");
      modalCard.classList.toggle("jcc-retreat-modal--staffCombined", combined);
    }
    document.querySelectorAll('[data-staff-modal-panel="council"]').forEach((el) => {
      el.hidden = mode !== "council" && !combined;
    });
    document.querySelectorAll('[data-staff-modal-panel="group"]').forEach((el) => {
      el.hidden = mode !== "group";
    });
    const councilRole = document.getElementById("staffModalCouncilRole");
    const { regionWrap, divisionWrap } = scopeFieldElements();
    toggleScopeFields(councilRole?.value || "", regionWrap, divisionWrap);
    if (councilRole?.value) {
      syncScopeFromUser(userPicker?.getSelected(), councilRole.value);
    } else {
      setScopeSelectsLocked(false);
    }
  }

  function eligibleGroupsForUser(user) {
    if (!user?.division_id) return [];
    const divisionId = Number(user.division_id);
    const regionId = user.region_id != null ? Number(user.region_id) : null;
    return groupsCache.filter((g) => {
      if (Number(g.division) !== divisionId) return false;
      if (regionId != null && Number(g.region) !== regionId) return false;
      return true;
    });
  }

  function populateGroupSelect(user, selectedGroupId) {
    const groupSel = document.getElementById("staffModalGroup");
    if (!groupSel) return;
    if (editingRow?.kind === "group") return;

    if (!user?.division_id) {
      groupSel.innerHTML = '<option value="">사용자를 먼저 선택하세요</option>';
      groupSel.value = "";
      window.JccCustomSelect?.refresh?.(groupSel.closest(".jcc-cselect") || modalOverlay);
      return;
    }

    const eligible = eligibleGroupsForUser(user);
    const want = selectedGroupId ? String(selectedGroupId) : "";
    if (!eligible.length) {
      groupSel.innerHTML =
        '<option value="">소속 지역·부서에 배정된 조가 없습니다</option>';
      groupSel.value = "";
    } else {
      groupSel.innerHTML =
        '<option value="">선택</option>' +
        eligible
          .map((g) => {
            const scope =
              g.region_name && g.division_name
                ? `${g.region_name} · ${g.division_name}`
                : "";
            const label = scope ? `${g.name} (${scope})` : g.name;
            const selected = String(g.id) === want ? " selected" : "";
            return `<option value="${g.id}"${selected}>${escapeHtml(label)}</option>`;
          })
          .join("");
      if (want && eligible.some((g) => String(g.id) === want)) {
        groupSel.value = want;
      }
    }
    window.JccCustomSelect?.refresh?.(groupSel.closest(".jcc-cselect") || modalOverlay);
  }

  function onUserPicked(user) {
    const councilRole = document.getElementById("staffModalCouncilRole")?.value || "";
    if (councilRole) syncScopeFromUser(user, councilRole);
    if (modalMode === "group") {
      populateGroupSelect(user);
    }
  }

  function onUserCleared() {
    const councilRole = document.getElementById("staffModalCouncilRole")?.value || "";
    if (councilRole) syncScopeFromUser(null, councilRole);
    if (modalMode === "group") {
      populateGroupSelect(null);
    }
  }

  function applyUserAffiliationFromPick(user) {
    const councilRole = document.getElementById("staffModalCouncilRole")?.value || "";
    if (!councilRole) return;
    syncScopeFromUser(user, councilRole);
  }

  function createUserPicker(root, searchUrl, opts) {
    opts = opts || {};
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
        const hint = opts.emptyHint || "이름 또는 ID를 입력하세요";
        const msg = lastQuery ? "결과 없음" : hint;
        list.innerHTML =
          `<li class="muted" role="option" aria-disabled="true">${escapeHtml(msg)}</li>`;
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
        params.set("limit", q ? "30" : "100");
        if (ctx.eventId) {
          params.set("event_id", String(ctx.eventId));
          params.set("staff_pool", "1");
        }
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
      if (typeof opts.onPick === "function") opts.onPick(u);
    }

    function openList() {
      const q = input.value.trim();
      clearTimeout(timer);
      timer = setTimeout(() => search(q), q ? 120 : 0);
    }

    input.addEventListener("input", () => {
      selected = null;
      hidden.value = "";
      if (typeof opts.onClear === "function") opts.onClear();
      const q = input.value.trim();
      clearTimeout(timer);
      timer = setTimeout(() => search(q), 180);
    });

    input.addEventListener("click", () => {
      if (input.disabled || root.classList.contains("is-locked")) return;
      openList();
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
      setSelected(user) {
        selected = user;
        hidden.value = user?.id ? String(user.id) : "";
        input.value = user?.name || user?.display_name || user?.username || "";
        closeList();
      },
      clear() {
        selected = null;
        hidden.value = "";
        input.value = "";
        closeList();
      },
    };
  }

  const userPicker = ctx.canManage
    ? createUserPicker(
        document.getElementById("staffModalUserPicker"),
        ctx.userSearchUrl,
        {
          emptyHint: "집회 조 소속 계정이 없습니다",
          onPick: onUserPicked,
          onClear: onUserCleared,
        }
      )
    : null;

  function showConfirm(message) {
    return new Promise((resolve) => {
      if (!confirmOverlay || !confirmMsg) {
        resolve(window.confirm(message));
        return;
      }
      confirmResolve = resolve;
      confirmMsg.textContent = message;
      confirmOverlay.hidden = false;
      confirmOverlay.setAttribute("aria-hidden", "false");
    });
  }

  function closeConfirm(result) {
    if (confirmOverlay) {
      confirmOverlay.hidden = true;
      confirmOverlay.setAttribute("aria-hidden", "true");
    }
    if (confirmResolve) {
      confirmResolve(result);
      confirmResolve = null;
    }
  }

  confirmCancel?.addEventListener("click", () => closeConfirm(false));
  confirmOk?.addEventListener("click", () => closeConfirm(true));
  confirmOverlay?.addEventListener("click", (e) => {
    if (e.target === confirmOverlay) closeConfirm(false);
  });

  function openModal(preset) {
    if (!modalOverlay || !ctx.canManage) return;
    editingRow = preset?.row || null;
    showModalStatus("");
    modalForm?.reset();
    userPicker?.clear();

    const groupSel = document.getElementById("staffModalGroup");
    const councilRole = document.getElementById("staffModalCouncilRole");
    const groupRole = document.getElementById("staffModalGroupRole");
    const noteInput = document.getElementById("staffModalNote");
    const regionSel = document.getElementById("staffModalRegion");
    const divisionSel = document.getElementById("staffModalDivision");

    if (groupSel && editingRow?.kind === "group") {
      groupSel.innerHTML =
        '<option value="">선택</option>' +
        groupsCache
          .filter((g) => String(g.id) === String(editingRow.groupId))
          .map((g) => `<option value="${g.id}">${escapeHtml(g.name)}</option>`)
          .join("");
    }

    if (editingRow) {
      modalMode = editingRow.kind;
      modalTitle.textContent =
        editingRow.kind === "council" ? "집회 운영진 수정" : "조장·부조장 수정";
      document.getElementById("staffModalSubmit").textContent = "저장";
      modalSubtitle.textContent = editingRow.name || "";
      const linkedCouncil =
        editingRow.kind === "group" ? councilRowForUser(editingRow.userId) : null;
      if (editingRow.kind === "council") {
        if (councilRole) councilRole.value = editingRow.role;
        if (noteInput) noteInput.value = editingRow.note || "";
      } else {
        if (groupSel) groupSel.value = String(editingRow.groupId || "");
        if (groupRole) groupRole.value = editingRow.role;
        if (councilRole) councilRole.value = linkedCouncil?.role || "";
        if (noteInput) noteInput.value = linkedCouncil?.note || "";
      }
      userPicker?.setSelected({
        id: editingRow.userId,
        name: editingRow.name,
        username: editingRow.username,
        region_id: editingRow.userRegionId,
        division_id: editingRow.userDivisionId,
        userRegionId: editingRow.userRegionId,
        userDivisionId: editingRow.userDivisionId,
      });
      document.getElementById("staffModalUserPicker")?.classList.add("is-locked");
      if (editingRow.kind === "group" && groupSel) {
        groupSel.disabled = true;
      }
    } else {
      modalMode = preset?.mode || preset?.kind || "council";
      modalTitle.textContent =
        modalMode === "council" ? "집회 운영진 등록" : "조장·부조장 등록";
      document.getElementById("staffModalSubmit").textContent = "등록 완료";
      modalSubtitle.textContent =
        modalMode === "council"
          ? "집회 조가 배정된 지역·부서 소속 계정만 선택할 수 있습니다."
          : "조를 선택하고 조장 또는 부조장 역할을 지정하세요.";
      document.getElementById("staffModalUserPicker")?.classList.remove("is-locked");
      if (councilRole) councilRole.value = preset?.suggestedCouncilRole || "";
      if (preset?.user) {
        userPicker?.setSelected({
          id: preset.user.user_id || preset.user.id,
          name: preset.user.name,
          region_id: preset.user.region_id,
          division_id: preset.user.division_id,
          userRegionId: preset.user.region_id,
          userDivisionId: preset.user.division_id,
        });
      }
      if (modalMode === "group") {
        if (preset?.groupId && groupSel) {
          groupSel.value = String(preset.groupId);
        }
        if (groupRole && preset?.groupRole) {
          groupRole.value = preset.groupRole;
        }
      } else if (preset?.isPastoral || preset?.suggestedCouncilRole) {
        modalMode = "council";
        if (councilRole && preset?.suggestedCouncilRole) {
          councilRole.value = preset.suggestedCouncilRole;
        }
      }
    }

    toggleModalPanels(modalMode);
    const activeCouncilRole = document.getElementById("staffModalCouncilRole")?.value || "";
    if (activeCouncilRole && userPicker?.getSelected()) {
      syncScopeFromUser(userPicker.getSelected(), activeCouncilRole);
    }
    if (modalMode === "group" && !editingRow) {
      const picked = userPicker?.getSelected();
      populateGroupSelect(picked || preset?.user || null, preset?.groupId);
    } else if (!editingRow && userPicker?.getSelected()) {
      onUserPicked(userPicker.getSelected());
    }
    window.JccCustomSelect?.refresh?.(modalOverlay);
    modalOverlay.hidden = false;
    modalOverlay.setAttribute("aria-hidden", "false");
  }

  function closeModal() {
    if (!modalOverlay) return;
    modalOverlay.hidden = true;
    modalOverlay.setAttribute("aria-hidden", "true");
    editingRow = null;
    const groupSel = document.getElementById("staffModalGroup");
    if (groupSel) groupSel.disabled = false;
    setScopeSelectsLocked(false);
    document.getElementById("staffModalUserPicker")?.classList.remove("is-locked");
  }

  document.getElementById("btnStaffAddCouncil")?.addEventListener("click", () =>
    openModal({ mode: "council" })
  );
  document.getElementById("btnStaffAddGroup")?.addEventListener("click", () =>
    openModal({ mode: "group" })
  );
  document.getElementById("staffModalCancel")?.addEventListener("click", closeModal);
  modalOverlay?.addEventListener("click", (e) => {
    if (e.target === modalOverlay) closeModal();
  });

  document.getElementById("staffModalCouncilRole")?.addEventListener("change", (e) => {
    const selected = userPicker?.getSelected();
    syncScopeFromUser(selected, e.target.value);
  });

  document.getElementById("staffModalRegion")?.addEventListener("change", (e) => {
    filterDivisionsByRegion(
      document.getElementById("staffModalDivision"),
      e.target.value
    );
  });

  document.getElementById("staffModalDivision")?.addEventListener("change", (e) => {
    const opt = e.target.selectedOptions[0];
    const rid = opt?.dataset?.regionId;
    const regionSel = document.getElementById("staffModalRegion");
    if (rid && regionSel) {
      regionSel.value = rid;
      window.JccCustomSelect?.refresh?.(
        regionSel.closest(".jcc-cselect") || regionSel.parentNode
      );
    }
  });

  async function loadRoster() {
    try {
      const [councilRes, groupsRes] = await Promise.all([
        fetch(ctx.apiList, { credentials: "same-origin" }),
        fetch(ctx.apiGroups, { credentials: "same-origin" }),
      ]);
      if (!councilRes.ok) throw new Error(await councilRes.text());
      if (!groupsRes.ok) throw new Error(await groupsRes.text());
      const council = await councilRes.json();
      groupsCache = await groupsRes.json();

      const rows = [];
      council.forEach((m) => {
        rows.push({
          kind: "council",
          id: m.id,
          userId: m.user,
          username: m.user_username,
          name: m.user_display_name || m.user_username,
          realName: m.user_real_name || m.user_display_name || "",
          phone: m.user_phone || "",
          role: m.role,
          roleLabel: m.role_display,
          scopeLabel: m.scope_label || "전체",
          regionId: m.region,
          divisionId: m.division,
          userRegionId: m.user_region_id,
          userDivisionId: m.user_division_id,
          note: m.note || "",
          createdAt: m.created_at,
          accountRetired: !!m.user_account_retired,
          accountRetiredDisplay: m.user_account_retired_display || "",
        });
      });

      groupsCache.forEach((g) => {
        (g.memberships || []).forEach((m) => {
          rows.push({
            kind: "group",
            id: m.id,
            userId: m.user,
            username: m.username,
            name: m.display_name || m.name || m.username,
            realName: m.user_real_name || "",
            phone: m.user_phone || "",
            role: m.role,
            roleLabel: m.role_display || m.role,
            scopeLabel: g.name,
            groupId: g.id,
            groupName: g.name,
            userRegionId: m.user_region_id,
            userDivisionId: m.user_division_id,
            note: "",
            createdAt: m.created_at,
            accountRetired: !!m.user_account_retired,
            accountRetiredDisplay: m.user_account_retired_display || "",
          });
        });
      });

      rosterRows = rows;
      updateFilterCounts();
      renderRoster(activeFilter);
    } catch (err) {
      console.error(err);
      if (rosterTbody) {
        rosterTbody.innerHTML = `<tr><td colspan="${ctx.canManage ? 7 : 6}">목록을 불러오지 못했습니다.</td></tr>`;
      }
      showStatus("목록을 불러오지 못했습니다.", true);
    }
  }

  function updateFilterCounts() {
    const counts = { all: 0, event: 0, region_division: 0, leader: 0, pickup: 0 };
    rosterRows.forEach((row) => {
      counts.all += 1;
      counts[rowCategory(row)] += 1;
    });
    document.querySelectorAll("[data-count]").forEach((el) => {
      const key = el.dataset.count;
      el.textContent = String(counts[key] ?? 0);
    });
  }

  function filteredRows(filter) {
    if (filter === "all") return rosterRows;
    return rosterRows.filter((row) => rowCategory(row) === filter);
  }

  function renderRoster(filter) {
    activeFilter = filter;
    const rows = filteredRows(filter);
    const colSpan = ctx.canManage ? 7 : 6;

    if (!rows.length) {
      const empty = '<tr><td colspan="' + colSpan + '">등록된 운영진이 없습니다.</td></tr>';
      if (rosterTbody) rosterTbody.innerHTML = empty;
      if (rosterCards) rosterCards.innerHTML = '<p class="muted">등록된 운영진이 없습니다.</p>';
      return;
    }

    if (rosterTbody) {
      rosterTbody.innerHTML = rows
        .map((row) => {
          return (
            `<tr data-row-id="${row.kind}-${row.id}">` +
            renderNameCell(row) +
            `<td class="jcc-retreat-staffColPhone">${escapeHtml(phoneDisplay(row.phone) || "—")}</td>` +
            `<td>${escapeHtml(row.scopeLabel || "—")}</td>` +
            `<td><span class="jcc-retreat-staffRoleTag ${roleBadgeClass(row.role, row.kind)}">${escapeHtml(row.roleLabel)}</span></td>` +
            `<td>${escapeHtml(row.note || "—")}</td>` +
            `<td>${escapeHtml(formatDate(row.createdAt))}</td>` +
            renderDeleteAction(row) +
            `</tr>`
          );
        })
        .join("");
    }

    if (rosterCards) {
      rosterCards.innerHTML = rows
        .map((row) => {
          const deleteBtn = ctx.canManage
            ? `<button type="button" class="jcc-retreat-staffDeleteBtn staff-delete-btn" data-row-id="${row.kind}-${row.id}" aria-label="${escapeHtml(row.name)} 삭제" title="삭제">${trashIconSvg()}</button>`
            : "";
          const nameEl = ctx.canManage
            ? `<button type="button" class="jcc-retreat-staffNameBtn staff-name-btn" data-row-id="${row.kind}-${row.id}">${escapeHtml(row.name)}</button>`
            : `<div class="jcc-retreat-staffCardName">${escapeHtml(row.name)}</div>`;
          const retiredBadge = row.accountRetiredDisplay
            ? `<span class="jcc-retreat-checkInBadge jcc-retreat-checkInBadge--account_retired">${escapeHtml(row.accountRetiredDisplay)}</span>`
            : "";
          const metaParts = [phoneDisplay(row.phone) || "—", formatDate(row.createdAt)];
          return (
            `<article class="jcc-retreat-staffCard" data-row-id="${row.kind}-${row.id}">` +
            `<div class="jcc-retreat-staffCardMain">` +
            `<div class="jcc-retreat-staffCardAvatar" aria-hidden="true">${escapeHtml((row.name || "?").slice(0, 1))}</div>` +
            `<div class="jcc-retreat-staffCardBody">` +
            nameEl +
            retiredBadge +
            `<div class="jcc-retreat-staffCardMeta muted">${escapeHtml(row.scopeLabel || "—")}</div>` +
            `<div class="jcc-retreat-staffCardMeta muted">${escapeHtml(metaParts.join(" · "))}</div>` +
            `</div>` +
            `<span class="jcc-retreat-staffRoleTag ${roleBadgeClass(row.role, row.kind)}">${escapeHtml(row.roleLabel)}</span>` +
            deleteBtn +
            `</div>` +
            `</article>`
          );
        })
        .join("");
    }
  }

  function findRow(rowId) {
    const [kind, id] = String(rowId).split("-");
    return rosterRows.find((row) => row.kind === kind && String(row.id) === id);
  }

  filterPills?.addEventListener("click", (e) => {
    const btn = e.target.closest(".jcc-retreat-staffPill");
    if (!btn) return;
    filterPills.querySelectorAll(".jcc-retreat-staffPill").forEach((pill) => {
      const active = pill === btn;
      pill.classList.toggle("is-active", active);
      pill.setAttribute("aria-selected", active ? "true" : "false");
    });
    renderRoster(btn.dataset.filter || "all");
  });

  async function loadWaitingCandidates() {
    if (!waitingList || !ctx.apiStaffCandidates) return;
    try {
      const r = await fetch(ctx.apiStaffCandidates, { credentials: "same-origin" });
      if (!r.ok) throw new Error(await r.text());
      const candidates = await r.json();
      if (!candidates.length) {
        waitingList.innerHTML =
          '<li class="muted">배정 대기 중인 승인 신청자가 없습니다.</li>';
        return;
      }
      waitingList.innerHTML = candidates
        .map((c) => {
          const roleHint = c.is_pastoral
            ? "집회 운영진"
            : [c.group_name, c.group_role === "vice_leader" ? "부조장" : c.group_role === "leader" ? "조장" : ""]
                .filter(Boolean)
                .join(" · ");
          const subtitle = [roleHint || c.division_name, c.region_name ? c.division_name : ""]
            .filter(Boolean)
            .join(" · ") || c.division_name;
          const assignAttrs = [
            `data-user-id="${c.user_id}"`,
            `data-is-pastoral="${c.is_pastoral ? "1" : "0"}"`,
            c.group_id ? `data-group-id="${c.group_id}"` : "",
            c.suggested_council_role
              ? `data-suggested-council-role="${escapeHtml(c.suggested_council_role)}"`
              : "",
            c.group_role ? `data-group-role="${escapeHtml(c.group_role)}"` : "",
          ]
            .filter(Boolean)
            .join(" ");
          return `<li class="jcc-retreat-staffWaitingItem">
              <div class="jcc-retreat-staffWaitingPerson">
                <span class="jcc-retreat-staffCardAvatar" aria-hidden="true">${escapeHtml((c.name || "?").slice(0, 1))}</span>
                <div>
                  <div class="jcc-retreat-staffCardName">${escapeHtml(c.name)}</div>
                  <div class="muted">${escapeHtml(subtitle)}</div>
                </div>
              </div>
              ${
                ctx.canManage
                  ? `<button type="button" class="secondary jcc-retreat-staffAssignBtn" ${assignAttrs}>지금 배정</button>`
                  : ""
              }
            </li>`;
        })
        .join("");
    } catch (err) {
      console.error(err);
      waitingList.innerHTML = '<li class="muted">배정 대기 목록을 불러오지 못했습니다.</li>';
    }
  }

  waitingList?.addEventListener("click", async (e) => {
    const btn = e.target.closest(".jcc-retreat-staffAssignBtn");
    if (!btn) return;
    const userId = Number(btn.dataset.userId);
    const isPastoral = btn.dataset.isPastoral === "1";
    let name = "";
    let groupRole = btn.dataset.groupRole || "";
    let suggestedCouncilRole = btn.dataset.suggestedCouncilRole || "";
    let regionId = null;
    let divisionId = null;
    try {
      const r = await fetch(ctx.apiStaffCandidates, { credentials: "same-origin" });
      if (r.ok) {
        const candidates = await r.json();
        const found = candidates.find((c) => c.user_id === userId);
        name = found?.name || "";
        groupRole = groupRole || found?.group_role || "";
        suggestedCouncilRole =
          suggestedCouncilRole || found?.suggested_council_role || "";
        regionId = found?.region_id || null;
        divisionId = found?.division_id || null;
      }
    } catch (_) {
      /* ignore */
    }
    openModal({
      mode: isPastoral ? "council" : "group",
      groupId: btn.dataset.groupId ? Number(btn.dataset.groupId) : null,
      groupRole,
      suggestedCouncilRole,
      isPastoral,
      user: {
        user_id: userId,
        name,
        region_id: regionId,
        division_id: divisionId,
      },
    });
  });

  async function saveCouncilMembership({ userId, membershipId, role, note }) {
    const body = { role, note: note || "" };
    const scope = scopeKind(role);
    if (scope === "region") {
      const region = Number(document.getElementById("staffModalRegion")?.value);
      if (!region) throw new Error("담당 지역을 확인할 수 없습니다.");
      body.region = region;
    } else if (scope === "division") {
      const division = Number(document.getElementById("staffModalDivision")?.value);
      if (!division) throw new Error("담당 부서를 확인할 수 없습니다.");
      body.division = division;
    } else {
      body.region = null;
      body.division = null;
    }
    if (membershipId) {
      const r = await fetch(`${ctx.apiDetailBase}${membershipId}/`, {
        method: "PATCH",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.detail || err.scope || "운영 역할 저장 실패");
      }
      return;
    }
    body.user_id = userId;
    const r = await fetch(ctx.apiList, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      const msg = err.scope || err.region || err.division || err.user || err.detail || "운영 역할 등록 실패";
      throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
    }
  }

  async function submitModal(e) {
    e.preventDefault();
    if (!ctx.canManage) return;

    const kind = editingRow ? editingRow.kind : modalMode;
    const selected = userPicker?.getSelected();
    const userId = selected?.id || Number(document.querySelector("[data-user-picker-id]")?.value);

    if (!userId && !editingRow) {
      showModalStatus("사용자를 검색해서 선택하세요.", true);
      return;
    }

    try {
      if (editingRow) {
        if (editingRow.kind === "council") {
          const role = document.getElementById("staffModalCouncilRole")?.value;
          if (!role) {
            showModalStatus("운영 역할을 선택하세요.", true);
            return;
          }
          const note = document.getElementById("staffModalNote")?.value?.trim() || "";
          await saveCouncilMembership({
            userId: editingRow.userId,
            membershipId: editingRow.id,
            role,
            note,
          });
        } else {
          const role = document.getElementById("staffModalGroupRole")?.value || "leader";
          const r = await fetch(`${ctx.apiGroupMembershipDetailBase}${editingRow.id}/`, {
            method: "PATCH",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
            body: JSON.stringify({ role }),
          });
          if (!r.ok) {
            const err = await r.json().catch(() => ({}));
            throw new Error(err.detail || "저장 실패");
          }
          const councilRole = document.getElementById("staffModalCouncilRole")?.value || "";
          if (councilRole) {
            const linkedCouncil = councilRowForUser(editingRow.userId);
            const note = document.getElementById("staffModalNote")?.value?.trim() || "";
            await saveCouncilMembership({
              userId: editingRow.userId,
              membershipId: linkedCouncil?.id || null,
              role: councilRole,
              note,
            });
          }
        }
      } else if (kind === "council") {
        const role = document.getElementById("staffModalCouncilRole")?.value || "";
        if (!role) {
          showModalStatus("운영 역할을 선택하세요.", true);
          return;
        }
        const note = document.getElementById("staffModalNote")?.value?.trim() || "";
        await saveCouncilMembership({ userId, membershipId: null, role, note });
      } else {
        const groupId = document.getElementById("staffModalGroup")?.value;
        if (!groupId) {
          showModalStatus("조를 선택하세요.", true);
          return;
        }
        const role = document.getElementById("staffModalGroupRole")?.value || "leader";
        const r = await fetch(`${ctx.apiGroupMembershipBase}${groupId}/memberships/`, {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
          body: JSON.stringify({ role, user_id: userId }),
        });
        if (!r.ok) {
          const err = await r.json().catch(() => ({}));
          throw new Error(err.detail || err.user || "등록 실패");
        }
      }

      closeModal();
      showStatus(editingRow ? "저장됨" : "등록됨");
      await Promise.all([loadRoster(), loadWaitingCandidates()]);
    } catch (err) {
      showModalStatus(String(err.message || err), true);
    }
  }

  modalForm?.addEventListener("submit", submitModal);

  async function handleDelete(row) {
    const label = row.kind === "council" ? "운영진에서 제거" : "조 운영진에서 제거";
    const ok = await showConfirm(`${label}하시겠습니까?`);
    if (!ok) return;
    try {
      const url =
        row.kind === "council"
          ? `${ctx.apiDetailBase}${row.id}/`
          : `${ctx.apiGroupMembershipDetailBase}${row.id}/`;
      const r = await fetch(url, {
        method: "DELETE",
        credentials: "same-origin",
        headers: { "X-CSRFToken": csrf() },
      });
      if (!r.ok) throw new Error(await r.text());
      showStatus("명단에서 제거했습니다. 승인된 참가 신청은 유지되며 역할 배정 대기에 표시됩니다.");
      await Promise.all([loadRoster(), loadWaitingCandidates()]);
    } catch (err) {
      showStatus("삭제 실패", true);
      console.error(err);
    }
  }

  function bindRosterActions(root) {
    root?.addEventListener("click", (e) => {
      const nameBtn = e.target.closest(".staff-name-btn");
      if (nameBtn) {
        const row = findRow(nameBtn.dataset.rowId);
        if (row) openModal({ row });
        return;
      }
      const delBtn = e.target.closest(".staff-delete-btn");
      if (delBtn) {
        const row = findRow(delBtn.dataset.rowId);
        if (row) handleDelete(row);
      }
    });
  }

  bindRosterActions(rosterTbody);
  bindRosterActions(rosterCards);

  loadRoster();
  loadWaitingCandidates();
})();
