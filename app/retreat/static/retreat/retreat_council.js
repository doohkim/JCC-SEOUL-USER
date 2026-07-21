(function () {
  "use strict";
  const ctx = window.RETREAT_COUNCIL_CTX;
  if (!ctx) return;

  const roleScopes = ctx.roleScopes || {};
  const statusEl = document.getElementById("staffRosterStatus");
  const rosterTbody = document.getElementById("staffRosterTbody");
  const rosterTheadRow = document.getElementById("staffRosterTheadRow");
  const rosterCards = document.getElementById("staffRosterCards");
  const rosterPager = document.getElementById("staffRosterPager");
  const filterPills = document.getElementById("staffFilterPills");
  const rosterSearchBlock = document.getElementById("staffRosterSearchBlock");
  const rosterSearchInput = document.getElementById("staffRosterSearch");
  const PAGE_SIZE = 10;
  const modalOverlay = document.getElementById("staffModalOverlay");
  const modalForm = document.getElementById("staffModalForm");
  const modalTitle = document.getElementById("staffModalTitle");
  const modalSubtitle = document.getElementById("staffModalSubtitle");
  const modalStatus = document.getElementById("staffModalStatus");
  const modalSubmitBtn = document.getElementById("staffModalSubmit");
  const confirmOverlay = document.getElementById("staffConfirmOverlay");
  const confirmMsg = document.getElementById("staffConfirmMsg");
  const confirmOk = document.getElementById("staffConfirmOk");
  const confirmCancel = document.getElementById("staffConfirmCancel");

  let rosterRows = [];
  let groupsCache = [];
  let activeFilter = "all";
  let sortKey = null;
  let sortDir = "asc";
  let rosterPage = 1;
  let searchQuery = "";
  let searchTimer = null;
  let editingRow = null;
  let modalMode = "council";
  let confirmResolve = null;
  let currentScopeAffiliations = [];
  let scopeBlocked = false;

  const NO_INTERSECTION_MSG =
    "이 사용자는 이 집회의 배정 부서와 겹치는 담당 부서가 없어 역할을 저장할 수 없습니다. 사용자 소속 또는 집회 배정 부서를 확인해 주세요.";

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

  function setScopeBlocked(blocked, message) {
    scopeBlocked = !!blocked;
    if (modalSubmitBtn) modalSubmitBtn.disabled = !!blocked;
    if (blocked) {
      showModalStatus(message || NO_INTERSECTION_MSG, true);
      return;
    }
    showModalStatus("");
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
      if (role === "vice_leader") return "jcc-retreat-staffRoleTag--vice_leader";
      if (role === "teacher") return "jcc-retreat-staffRoleTag--teacher";
      return "jcc-retreat-staffRoleTag--leader";
    }
    return `jcc-retreat-staffRoleTag--${role}`;
  }

  function renderRoleBadges(row) {
    const items =
      Array.isArray(row.roleBadges) && row.roleBadges.length
        ? row.roleBadges
        : [{ role: row.role, label: row.roleLabel }];
    const badges = items
      .map(
        (item) =>
          `<span class="jcc-retreat-staffRoleTag ${roleBadgeClass(item.role, row.kind)}">${escapeHtml(item.label)}</span>`
      )
      .join("");
    return `<span class="jcc-retreat-staffRoleBadges">${badges}</span>`;
  }

  function renderScopeBadges(row) {
    const items =
      Array.isArray(row.scopeBadges) && row.scopeBadges.length
        ? row.scopeBadges
        : [{ label: row.scopeLabel || "—", kind: "plain" }];
    const pills = items
      .map((item) => {
        const label = String(item.label || "").trim();
        if (!label || label === "—") return "";
        const kind = item.kind || "plain";
        const klass =
          kind === "region"
            ? "jcc-retreat-pill jcc-retreat-pill--scopeRegion"
            : kind === "division"
              ? "jcc-retreat-pill jcc-retreat-pill--scopeDivision"
              : "jcc-retreat-pill jcc-retreat-pill--scopeReadonly";
        return `<span class="${klass}">${escapeHtml(label)}</span>`;
      })
      .filter(Boolean)
      .join("");
    return `<span class="jcc-retreat-staffScopeBadges jcc-retreat-scopeTags">${pills || "—"}</span>`;
  }

  /** 사용자 계정(UserDivisionTeam) 지역·부서 태그. */
  function affiliationScopeBadges(affiliations) {
    const rows = Array.isArray(affiliations) ? affiliations : [];
    const badges = [];
    let lastRegion = "";
    rows.forEach((row) => {
      const region = String(row?.region_name || "").trim();
      const division = String(row?.division_name || "").trim();
      if (region && region !== lastRegion) {
        badges.push({ label: region, kind: "region" });
        lastRegion = region;
      }
      if (division) badges.push({ label: division, kind: "division" });
    });
    return badges.length ? badges : [{ label: "—", kind: "plain" }];
  }

  function affiliationScopeLabel(affiliations) {
    return (
      affiliationScopeBadges(affiliations)
        .map((b) => b.label)
        .filter((label) => label && label !== "—")
        .join(" · ") || "—"
    );
  }

  /** 겸직 조장은 사람당 1행으로 합친다 (소속/담당 표기). */
  function mergeGroupMembershipRows(rows) {
    const councilRows = [];
    const groupByUser = new Map();
    rows.forEach((row) => {
      if (row.kind !== "group") {
        councilRows.push(row);
        return;
      }
      const key = String(row.userId);
      if (!groupByUser.has(key)) groupByUser.set(key, []);
      groupByUser.get(key).push(row);
    });

    const mergedGroupRows = [];
    groupByUser.forEach((list) => {
      list.sort((a, b) => {
        if (!!a.isCrossGroupLeader !== !!b.isCrossGroupLeader) {
          return a.isCrossGroupLeader ? 1 : -1;
        }
        return String(a.groupName || "").localeCompare(
          String(b.groupName || ""),
          "ko"
        );
      });
      const primary =
        list.find((row) => !row.isCrossGroupLeader) || list[0];
      const assignments = list.map((row) => ({
        id: row.id,
        groupId: row.groupId,
        groupName: row.groupName,
        role: row.role,
        roleLabel: row.roleLabel,
        isCrossGroupLeader: !!row.isCrossGroupLeader,
        createdAt: row.createdAt,
      }));
      const scopeBadges =
        Array.isArray(primary.scopeBadges) && primary.scopeBadges.length
          ? primary.scopeBadges
          : affiliationScopeBadges(primary.affiliations);
      const scopeLabel =
        primary.scopeLabel && primary.scopeLabel !== "—"
          ? primary.scopeLabel
          : affiliationScopeLabel(primary.affiliations);
      const roleBadges = list.map((row) => ({
        role: row.role,
        label: `${row.groupName} ${row.roleLabel}`.trim(),
      }));
      const createdAt = list
        .map((row) => row.createdAt)
        .filter(Boolean)
        .sort()[0];
      mergedGroupRows.push({
        ...primary,
        scopeLabel,
        scopeBadges,
        affiliations: primary.affiliations || [],
        roleLabel: roleBadges.map((b) => b.label).join(" · "),
        roleBadges,
        groupAssignments: assignments,
        createdAt: createdAt || primary.createdAt,
      });
    });

    return councilRows.concat(mergedGroupRows);
  }

  function filterRegionsByAllowed(selectEl, allowedRegionIds) {
    if (!selectEl) return;
    const selected = selectEl.value;
    const allowed = allowedRegionIds || null;
    Array.from(selectEl.options).forEach((opt, idx) => {
      if (idx === 0) {
        opt.hidden = false;
        return;
      }
      const rid = Number(opt.value || 0);
      const blocked = allowed && !allowed.has(rid);
      opt.hidden = blocked && String(opt.value) !== String(selected);
    });
    if (
      selectEl.value &&
      selectEl.selectedOptions[0] &&
      selectEl.selectedOptions[0].hidden
    ) {
      selectEl.value = "";
    }
  }

  function filterDivisionsByRegion(selectEl, regionId, allowedDivisionIds) {
    if (!selectEl) return;
    const selected = selectEl.value;
    const allowed = allowedDivisionIds || null;
    Array.from(selectEl.options).forEach((opt, idx) => {
      if (idx === 0) {
        opt.hidden = false;
        return;
      }
      const rid = opt.dataset.regionId;
      const divisionId = Number(opt.value || 0);
      const blockedByRegion = Boolean(regionId && rid && String(rid) !== String(regionId));
      const blockedByAffiliation = Boolean(allowed && !allowed.has(divisionId));
      opt.hidden =
        (blockedByRegion || blockedByAffiliation) &&
        String(opt.value) !== String(selected);
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

  function userAffiliationsFromSelection(selected) {
    if (!selected) return [];
    const rows = Array.isArray(selected.affiliations) ? selected.affiliations : [];
    const normalized = rows
      .map((row) => ({
        region_id: row?.region_id != null ? Number(row.region_id) : null,
        division_id: row?.division_id != null ? Number(row.division_id) : null,
      }))
      .filter((row) => row.division_id != null);
    if (normalized.length) return normalized;
    const fallback = {
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
    return fallback.division_id != null ? [fallback] : [];
  }

  function eventDivisionIds() {
    const divisionSel = document.getElementById("staffModalDivision");
    if (!divisionSel) return new Set();
    const ids = new Set();
    Array.from(divisionSel.options).forEach((opt, idx) => {
      if (idx === 0) return;
      const did = Number(opt.value || 0);
      if (did) ids.add(did);
    });
    return ids;
  }

  function scopedAffiliationsForUser(selected) {
    const eventDivisionSet = eventDivisionIds();
    const all = userAffiliationsFromSelection(selected);
    const seen = new Set();
    const filtered = [];
    all.forEach((row) => {
      if (!row.division_id) return;
      if (eventDivisionSet.size && !eventDivisionSet.has(Number(row.division_id))) return;
      if (seen.has(row.division_id)) return;
      seen.add(row.division_id);
      filtered.push(row);
    });
    return filtered;
  }

  function syncScopeFromUser(user, role) {
    const { regionWrap, divisionWrap, regionSel, divisionSel } = scopeFieldElements();
    if (!role) {
      toggleScopeFields("", regionWrap, divisionWrap);
      if (regionSel) regionSel.value = "";
      if (divisionSel) divisionSel.value = "";
      currentScopeAffiliations = [];
      filterRegionsByAllowed(regionSel, null);
      filterDivisionsByRegion(divisionSel, null, null);
      setScopeBlocked(false);
      setScopeSelectsLocked(false);
      window.JccCustomSelect?.refresh?.(modalOverlay);
      return;
    }

    const kind = scopeKind(role);
    toggleScopeFields(role, regionWrap, divisionWrap);
    currentScopeAffiliations = scopedAffiliationsForUser(user);
    const hasScopedAffiliation = currentScopeAffiliations.length > 0;
    const allowedDivisionIds = new Set(
      currentScopeAffiliations.map((row) => Number(row.division_id)).filter(Boolean)
    );
    const allowedRegionIds = new Set(
      currentScopeAffiliations.map((row) => Number(row.region_id)).filter(Boolean)
    );
    const firstAffiliation = currentScopeAffiliations[0] || null;
    const firstRegionId = firstAffiliation?.region_id
      ? Number(firstAffiliation.region_id)
      : null;

    if (kind === "event") {
      if (regionSel) regionSel.value = "";
      if (divisionSel) divisionSel.value = "";
      filterRegionsByAllowed(regionSel, null);
      filterDivisionsByRegion(divisionSel, null, null);
      setScopeBlocked(false);
      setScopeSelectsLocked(true);
    } else if (kind === "region") {
      if (user && !hasScopedAffiliation) {
        if (regionSel) regionSel.value = "";
        if (divisionSel) divisionSel.value = "";
        filterRegionsByAllowed(regionSel, new Set());
        filterDivisionsByRegion(divisionSel, null, new Set());
        if (regionSel) regionSel.disabled = true;
        if (divisionSel) divisionSel.disabled = true;
        setScopeBlocked(true, NO_INTERSECTION_MSG);
        window.JccCustomSelect?.refresh?.(modalOverlay);
        return;
      }
      filterRegionsByAllowed(
        regionSel,
        hasScopedAffiliation ? allowedRegionIds : null
      );
      if (regionSel) {
        if (
          hasScopedAffiliation &&
          (regionSel.value === "" ||
            !allowedRegionIds.has(Number(regionSel.value || 0)))
        ) {
          regionSel.value =
            firstRegionId != null ? String(firstRegionId) : "";
        }
      }
      if (divisionSel) divisionSel.value = "";
      filterDivisionsByRegion(
        divisionSel,
        regionSel?.value || null,
        hasScopedAffiliation ? allowedDivisionIds : null
      );
      if (regionSel) {
        const lockRegion = hasScopedAffiliation && allowedRegionIds.size <= 1;
        regionSel.disabled = !!lockRegion;
      }
      if (divisionSel) divisionSel.disabled = true;
      setScopeBlocked(false);
    } else if (kind === "division") {
      if (user && !hasScopedAffiliation) {
        if (regionSel) regionSel.value = "";
        if (divisionSel) divisionSel.value = "";
        filterRegionsByAllowed(regionSel, new Set());
        filterDivisionsByRegion(divisionSel, null, new Set());
        if (regionSel) regionSel.disabled = true;
        if (divisionSel) divisionSel.disabled = true;
        setScopeBlocked(true, NO_INTERSECTION_MSG);
        window.JccCustomSelect?.refresh?.(modalOverlay);
        return;
      }
      filterRegionsByAllowed(
        regionSel,
        hasScopedAffiliation ? allowedRegionIds : null
      );
      if (regionSel) {
        if (
          hasScopedAffiliation &&
          (regionSel.value === "" ||
            !allowedRegionIds.has(Number(regionSel.value || 0)))
        ) {
          regionSel.value =
            firstRegionId != null ? String(firstRegionId) : "";
        }
      }
      filterDivisionsByRegion(
        divisionSel,
        regionSel?.value || null,
        hasScopedAffiliation ? allowedDivisionIds : null
      );
      if (divisionSel) {
        const visibleDivisionOptions = Array.from(divisionSel.options).filter(
          (opt, idx) => idx > 0 && !opt.hidden
        );
        const visibleDivisionIds = visibleDivisionOptions
          .map((opt) => Number(opt.value || 0))
          .filter(Boolean);
        if (
          hasScopedAffiliation &&
          !visibleDivisionIds.includes(Number(divisionSel.value || 0))
        ) {
          divisionSel.value = visibleDivisionIds.length
            ? String(visibleDivisionIds[0])
            : "";
        }
        const lockDivision = hasScopedAffiliation && visibleDivisionIds.length <= 1;
        divisionSel.disabled = !!lockDivision;
      }
      if (regionSel) {
        const lockRegion = hasScopedAffiliation && allowedRegionIds.size <= 1;
        regionSel.disabled = !!lockRegion;
      }
      setScopeBlocked(false);
    } else {
      filterRegionsByAllowed(regionSel, null);
      filterDivisionsByRegion(divisionSel, null, null);
      setScopeBlocked(false);
      setScopeSelectsLocked(false);
    }
    window.JccCustomSelect?.refresh?.(modalOverlay);
  }

  function toggleModalPanels(mode) {
    modalMode = mode;
    const modalCard = modalOverlay?.querySelector(".jcc-retreat-modal--staff");
    if (modalCard) {
      modalCard.classList.toggle("jcc-retreat-modal--staffGroup", mode === "group");
      modalCard.classList.toggle("jcc-retreat-modal--staffCouncil", mode === "council");
      modalCard.classList.remove("jcc-retreat-modal--staffCombined");
    }
    document.querySelectorAll('[data-staff-modal-panel="council"]').forEach((el) => {
      el.hidden = mode !== "council";
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
          params.set("staff_pool_kind", modalMode === "group" ? "group" : "council");
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
    setScopeBlocked(false);
    modalForm?.reset();
    userPicker?.clear();

    const groupSel = document.getElementById("staffModalGroup");
    const councilRole = document.getElementById("staffModalCouncilRole");
    const groupRole = document.getElementById("staffModalGroupRole");

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
        editingRow.kind === "council" ? "집회 운영진 수정" : "조 운영진 수정";
      document.getElementById("staffModalSubmit").textContent = "저장";
      modalSubtitle.textContent = editingRow.name || "";
      if (editingRow.kind === "council") {
        if (councilRole) councilRole.value = editingRow.role;
      } else {
        if (groupSel) groupSel.value = String(editingRow.groupId || "");
        if (groupRole) groupRole.value = editingRow.role;
      }
      userPicker?.setSelected({
        id: editingRow.userId,
        name: editingRow.name,
        username: editingRow.username,
        region_id: editingRow.userRegionId,
        division_id: editingRow.userDivisionId,
        userRegionId: editingRow.userRegionId,
        userDivisionId: editingRow.userDivisionId,
        affiliations: editingRow.affiliations || [],
      });
      document.getElementById("staffModalUserPicker")?.classList.add("is-locked");
      if (editingRow.kind === "group" && groupSel) {
        groupSel.disabled = true;
      }
    } else {
      modalMode = preset?.mode || preset?.kind || "council";
      modalTitle.textContent =
        modalMode === "council" ? "집회 운영진 등록" : "조 운영진 등록";
      document.getElementById("staffModalSubmit").textContent = "등록 완료";
      modalSubtitle.textContent =
        modalMode === "council"
          ? "집회 조가 배정된 지역·부서 소속 계정만 선택할 수 있습니다."
          : "조를 선택하고 조장·부조장·선생님 역할을 지정하세요.";
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
          affiliations: preset.user.affiliations || [],
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
    const allowedDivisionIds = currentScopeAffiliations.length
      ? new Set(
          currentScopeAffiliations
            .map((row) => Number(row.division_id))
            .filter(Boolean)
        )
      : null;
    filterDivisionsByRegion(
      document.getElementById("staffModalDivision"),
      e.target.value,
      allowedDivisionIds
    );
    const divisionSel = document.getElementById("staffModalDivision");
    if (divisionSel) {
      const visibleDivisionOptions = Array.from(divisionSel.options).filter(
        (opt, idx) => idx > 0 && !opt.hidden
      );
      const visibleDivisionIds = visibleDivisionOptions
        .map((opt) => Number(opt.value || 0))
        .filter(Boolean);
      if (!visibleDivisionIds.includes(Number(divisionSel.value || 0))) {
        divisionSel.value = visibleDivisionIds.length
          ? String(visibleDivisionIds[0])
          : "";
      }
      window.JccCustomSelect?.refresh?.(
        divisionSel.closest(".jcc-cselect") || divisionSel.parentNode
      );
    }
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
        const affiliations = Array.isArray(m.user_affiliations)
          ? m.user_affiliations
          : [];
        const scopeBadges = affiliationScopeBadges(affiliations);
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
          scopeLabel: affiliationScopeLabel(affiliations),
          scopeBadges,
          regionId: m.region,
          divisionId: m.division,
          regionName: m.region_name || "",
          divisionName: m.division_name || "",
          userRegionId: m.user_region_id,
          userDivisionId: m.user_division_id,
          affiliations,
          roleLevelName: m.user_role_level_name || "",
          roleLevel: m.user_role_level,
          note: m.note || "",
          createdAt: m.created_at,
          accountRetired: !!m.user_account_retired,
          accountRetiredDisplay: m.user_account_retired_display || "",
        });
      });

      groupsCache.forEach((g) => {
        (g.memberships || []).forEach((m) => {
          const homeName = m.home_group_name || "";
          const cross = !!m.is_cross_group_leader;
          const affiliations = Array.isArray(m.user_affiliations)
            ? m.user_affiliations
            : [];
          const scopeBadges = affiliationScopeBadges(affiliations);
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
            scopeLabel: affiliationScopeLabel(affiliations),
            scopeBadges,
            affiliations,
            groupId: g.id,
            groupName: g.name,
            homeGroupId: m.home_group_id || null,
            homeGroupName: homeName,
            isCrossGroupLeader: cross,
            userRegionId: m.user_region_id,
            userDivisionId: m.user_division_id,
            note: "",
            createdAt: m.created_at,
            accountRetired: !!m.user_account_retired,
            accountRetiredDisplay: m.user_account_retired_display || "",
          });
        });
      });

      rosterRows = mergeGroupMembershipRows(rows);
      updateFilterCounts();
      renderRoster(activeFilter, { resetPage: true });
    } catch (err) {
      console.error(err);
      if (rosterTbody) {
        rosterTbody.innerHTML = `<tr><td colspan="${ctx.canManage ? 7 : 6}">목록을 불러오지 못했습니다.</td></tr>`;
      }
      if (rosterPager) {
        rosterPager.hidden = true;
        rosterPager.innerHTML = "";
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

  function rowSearchText(row) {
    const parts = [
      row.name,
      row.realName,
      row.username,
      row.phone,
      String(row.phone || "").replace(/\D/g, ""),
      row.roleLabel,
      row.role,
      row.scopeLabel,
      row.groupName,
      row.homeGroupName,
      row.regionName,
      row.divisionName,
      row.note,
    ];
    if (Array.isArray(row.roleBadges)) {
      row.roleBadges.forEach((b) => parts.push(b.label, b.role));
    }
    if (Array.isArray(row.scopeBadges)) {
      row.scopeBadges.forEach((b) => parts.push(b.label));
    }
    if (Array.isArray(row.groupAssignments)) {
      row.groupAssignments.forEach((a) => {
        parts.push(a.groupName, a.roleLabel, a.role);
      });
    }
    return parts
      .map((v) => String(v || "").trim().toLowerCase())
      .filter(Boolean)
      .join(" ");
  }

  function matchesSearch(row, query) {
    const q = String(query || "").trim().toLowerCase();
    if (!q) return true;
    const hay = rowSearchText(row);
    if (hay.includes(q)) return true;
    const digits = q.replace(/\D/g, "");
    if (digits && hay.replace(/\D/g, "").includes(digits)) return true;
    return false;
  }

  function filteredRows(filter) {
    let rows =
      filter === "all"
        ? rosterRows.slice()
        : rosterRows.filter((row) => rowCategory(row) === filter);
    if (filter === "all" && searchQuery.trim()) {
      rows = rows.filter((row) => matchesSearch(row, searchQuery));
    }
    return rows;
  }

  function sortValue(row, key) {
    if (key === "scope") return String(row.scopeLabel || "").trim();
    if (key === "role") {
      if (Array.isArray(row.roleBadges) && row.roleBadges.length) {
        return row.roleBadges.map((b) => b.label || "").join(" ");
      }
      return String(row.roleLabel || row.role || "").trim();
    }
    if (key === "name") return String(row.name || "").trim();
    if (key === "title") return String(row.roleLevelName || "").trim();
    return "";
  }

  function isSortableFilter(filter) {
    return (
      filter === "all" ||
      filter === "event" ||
      filter === "region_division" ||
      filter === "leader"
    );
  }

  function filterColumnLayout(filter) {
    if (filter === "region_division") {
      return {
        showTitle: true,
        sortableKeys: ["scope", "role", "name", "title"],
        colSpan: ctx.canManage ? 8 : 7,
      };
    }
    if (filter === "leader") {
      return {
        showTitle: false,
        sortableKeys: ["scope", "role", "name"],
        colSpan: ctx.canManage ? 7 : 6,
      };
    }
    return {
      showTitle: false,
      sortableKeys: ["scope", "role", "name"],
      colSpan: ctx.canManage ? 7 : 6,
    };
  }

  function renderTitleCell(row) {
    const label = String(row.roleLevelName || "").trim();
    if (!label) return `<td>—</td>`;
    return `<td><span class="jcc-retreat-pill jcc-retreat-pill--scopeReadonly">${escapeHtml(label)}</span></td>`;
  }

  function renderTableHeader(filter) {
    if (!rosterTheadRow) return;
    const layout = filterColumnLayout(filter);
    const sortable = new Set(layout.sortableKeys);
    const sortTh = (key, label) => {
      if (!sortable.has(key)) {
        return `<th scope="col">${escapeHtml(label)}</th>`;
      }
      return (
        `<th class="jcc-retreat-sortable" data-sort-key="${key}" scope="col" aria-sort="none">` +
        `<span class="jcc-retreat-sortLabel">${escapeHtml(label)}</span></th>`
      );
    };
    let html =
      sortTh("scope", "소속") +
      sortTh("role", "역할") +
      sortTh("name", "이름") +
      `<th class="jcc-retreat-staffColPhone">연락처</th>`;
    if (layout.showTitle) {
      html += sortTh("title", "직책");
    }
    html += `<th>메모</th><th>등록일</th>`;
    if (ctx.canManage) {
      html += `<th class="jcc-retreat-staffColAction">Action</th>`;
    }
    rosterTheadRow.innerHTML = html;
  }

  function sortedRows(rows) {
    if (!sortKey || !isSortableFilter(activeFilter)) return rows;
    const layout = filterColumnLayout(activeFilter);
    if (!layout.sortableKeys.includes(sortKey)) return rows;
    const dir = sortDir === "desc" ? -1 : 1;
    return rows.slice().sort((a, b) => {
      if (sortKey === "title") {
        const la = a.roleLevel == null ? -1 : Number(a.roleLevel);
        const lb = b.roleLevel == null ? -1 : Number(b.roleLevel);
        if (la !== lb) return (la - lb) * dir;
      }
      const va = sortValue(a, sortKey);
      const vb = sortValue(b, sortKey);
      const cmp = va.localeCompare(vb, "ko", { sensitivity: "base", numeric: true });
      if (cmp !== 0) return cmp * dir;
      return String(a.name || "").localeCompare(String(b.name || ""), "ko");
    });
  }

  function syncSortHeaders() {
    const headers = document.querySelectorAll(
      ".jcc-retreat-staffRosterTable .jcc-retreat-sortable[data-sort-key]"
    );
    const sortingEnabled = isSortableFilter(activeFilter);
    const layout = filterColumnLayout(activeFilter);
    if (sortKey && !layout.sortableKeys.includes(sortKey)) {
      sortKey = null;
      sortDir = "asc";
    }
    headers.forEach((th) => {
      th.classList.toggle("is-disabled", !sortingEnabled);
      th.setAttribute("aria-disabled", sortingEnabled ? "false" : "true");
      if (!sortingEnabled) {
        delete th.dataset.sortDir;
        th.setAttribute("aria-sort", "none");
        return;
      }
      if (th.dataset.sortKey === sortKey) {
        th.dataset.sortDir = sortDir;
        th.setAttribute(
          "aria-sort",
          sortDir === "asc" ? "ascending" : "descending"
        );
      } else {
        delete th.dataset.sortDir;
        th.setAttribute("aria-sort", "none");
      }
    });
  }

  function renderPager(total, page, pageCount) {
    if (!rosterPager) return;
    if (total <= PAGE_SIZE) {
      rosterPager.hidden = true;
      rosterPager.innerHTML = "";
      return;
    }
    rosterPager.hidden = false;
    const start = (page - 1) * PAGE_SIZE + 1;
    const end = Math.min(page * PAGE_SIZE, total);
    const prevDisabled = page <= 1 ? " disabled" : "";
    const nextDisabled = page >= pageCount ? " disabled" : "";
    rosterPager.innerHTML =
      `<button type="button" class="secondary jcc-retreat-staffPagerBtn" data-staff-page="prev"${prevDisabled}>이전</button>` +
      `<span class="jcc-retreat-staffPagerInfo muted">${start}–${end} / ${total}</span>` +
      `<button type="button" class="jcc-retreat-staffPagerBtn" data-staff-page="next"${nextDisabled}>다음</button>`;
  }

  function renderRoster(filter, { resetPage } = {}) {
    const nextFilter = filter || activeFilter;
    if (resetPage || nextFilter !== activeFilter) {
      rosterPage = 1;
    }
    activeFilter = nextFilter;
    if (rosterSearchBlock) {
      rosterSearchBlock.hidden = activeFilter !== "all";
    }
    const layout = filterColumnLayout(activeFilter);
    renderTableHeader(activeFilter);
    const allRows = sortedRows(filteredRows(activeFilter));
    const colSpan = layout.colSpan;
    syncSortHeaders();

    if (!allRows.length) {
      const emptyMsg =
        activeFilter === "all" && searchQuery.trim()
          ? "검색 결과가 없습니다."
          : "등록된 운영진이 없습니다.";
      const empty = '<tr><td colspan="' + colSpan + '">' + emptyMsg + "</td></tr>";
      if (rosterTbody) rosterTbody.innerHTML = empty;
      if (rosterCards) rosterCards.innerHTML = '<p class="muted">' + emptyMsg + "</p>";
      renderPager(0, 1, 1);
      return;
    }

    const pageCount = Math.max(1, Math.ceil(allRows.length / PAGE_SIZE));
    if (rosterPage > pageCount) rosterPage = pageCount;
    if (rosterPage < 1) rosterPage = 1;
    const startIdx = (rosterPage - 1) * PAGE_SIZE;
    const rows = allRows.slice(startIdx, startIdx + PAGE_SIZE);
    renderPager(allRows.length, rosterPage, pageCount);

    if (rosterTbody) {
      rosterTbody.innerHTML = rows
        .map((row) => {
          return (
            `<tr data-row-id="${row.kind}-${row.id}">` +
            `<td>${renderScopeBadges(row)}</td>` +
            `<td>${renderRoleBadges(row)}</td>` +
            renderNameCell(row) +
            `<td class="jcc-retreat-staffColPhone">${escapeHtml(phoneDisplay(row.phone) || "—")}</td>` +
            (layout.showTitle ? renderTitleCell(row) : "") +
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
          if (layout.showTitle && row.roleLevelName) {
            metaParts.unshift(row.roleLevelName);
          }
          return (
            `<article class="jcc-retreat-staffCard" data-row-id="${row.kind}-${row.id}">` +
            `<div class="jcc-retreat-staffCardMain">` +
            `<div class="jcc-retreat-staffCardAvatar" aria-hidden="true">${escapeHtml((row.name || "?").slice(0, 1))}</div>` +
            `<div class="jcc-retreat-staffCardBody">` +
            nameEl +
            retiredBadge +
            `<div class="jcc-retreat-staffCardMeta">${renderScopeBadges(row)}</div>` +
            `<div class="jcc-retreat-staffCardMeta muted">${escapeHtml(metaParts.join(" · "))}</div>` +
            `</div>` +
            renderRoleBadges(row) +
            deleteBtn +
            `</div>` +
            `</article>`
          );
        })
        .join("");
    }
  }

  function bindStaffSorting() {
    const table = document.querySelector(".jcc-retreat-staffRosterTable");
    if (!table) return;
    table.addEventListener("click", (e) => {
      const th = e.target.closest(".jcc-retreat-sortable[data-sort-key]");
      if (!th || !table.contains(th)) return;
      if (!isSortableFilter(activeFilter)) return;
      const key = th.dataset.sortKey;
      const layout = filterColumnLayout(activeFilter);
      if (!layout.sortableKeys.includes(key)) return;
      if (sortKey === key) {
        sortDir = sortDir === "asc" ? "desc" : "asc";
      } else {
        sortKey = key;
        sortDir = "asc";
      }
      renderRoster(activeFilter, { resetPage: true });
    });
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
    renderRoster(btn.dataset.filter || "all", { resetPage: true });
  });

  if (rosterSearchInput) {
    rosterSearchInput.addEventListener("input", () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        searchQuery = rosterSearchInput.value || "";
        renderRoster("all", { resetPage: true });
      }, 150);
    });
  }

  rosterPager?.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-staff-page]");
    if (!btn || btn.disabled) return;
    if (btn.dataset.staffPage === "prev") {
      rosterPage = Math.max(1, rosterPage - 1);
    } else if (btn.dataset.staffPage === "next") {
      rosterPage += 1;
    }
    renderRoster(activeFilter);
  });

  bindStaffSorting();

  async function saveCouncilMembership({ userId, membershipId, role }) {
    const body = { role, note: "" };
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
        const msg =
          err.scope || err.region || err.division || err.user || err.detail || "운영 역할 저장 실패";
        throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
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
    if (scopeBlocked) {
      showModalStatus(NO_INTERSECTION_MSG, true);
      return;
    }

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
          await saveCouncilMembership({
            userId: editingRow.userId,
            membershipId: editingRow.id,
            role,
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
        }
      } else if (kind === "council") {
        const role = document.getElementById("staffModalCouncilRole")?.value || "";
        if (!role) {
          showModalStatus("운영 역할을 선택하세요.", true);
          return;
        }
        await saveCouncilMembership({ userId, membershipId: null, role });
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
        const body = await r.json().catch(() => ({}));
        if (!r.ok) {
          throw new Error(body.detail || body.user || "등록 실패");
        }
        closeModal();
        showStatus(body.message || (editingRow ? "저장됨" : "등록됨"));
        await loadRoster();
        return;
      }

      closeModal();
      showStatus(editingRow ? "저장됨" : "등록됨");
      await loadRoster();
    } catch (err) {
      showModalStatus(String(err.message || err), true);
    }
  }

  modalForm?.addEventListener("submit", submitModal);

  async function handleDelete(row) {
    const assignments =
      row.kind === "group" && Array.isArray(row.groupAssignments)
        ? row.groupAssignments
        : null;
    let confirmMsg;
    if (row.kind === "council") {
      confirmMsg = "운영진에서 제거하시겠습니까?";
    } else if (assignments && assignments.length > 1) {
      const groups = assignments.map((a) => a.groupName).join(", ");
      confirmMsg =
        `${row.name} 님의 조 운영진 권한을 모두 해제할까요?\n(${groups})`;
    } else {
      confirmMsg = "조 운영진에서 제거하시겠습니까?";
    }
    const ok = await showConfirm(confirmMsg);
    if (!ok) return;
    try {
      if (row.kind === "council") {
        const r = await fetch(`${ctx.apiDetailBase}${row.id}/`, {
          method: "DELETE",
          credentials: "same-origin",
          headers: { "X-CSRFToken": csrf() },
        });
        if (!r.ok) throw new Error(await r.text());
      } else {
        const ids = (assignments || [{ id: row.id }]).map((a) => a.id);
        for (const membershipId of ids) {
          const r = await fetch(
            `${ctx.apiGroupMembershipDetailBase}${membershipId}/`,
            {
              method: "DELETE",
              credentials: "same-origin",
              headers: { "X-CSRFToken": csrf() },
            }
          );
          if (!r.ok) throw new Error(await r.text());
        }
      }
      showStatus("명단에서 제거했습니다. 배정이 모두 해제되면 참가 신청서가 삭제되어 재신청할 수 있습니다.");
      await loadRoster();
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
})();
