(function () {
  const ctx = window.RETREAT_PICKUP_CTX;
  if (!ctx) return;

  let allLocations = [];
  try {
    allLocations = JSON.parse(
      document.getElementById("retreatPickupLocationList")?.textContent || "[]"
    );
  } catch (e) {
    allLocations = [];
  }
  function syncLocationsFromList(items) {
    allLocations = (items || []).map((loc) => ({
      id: loc.id,
      name: loc.name,
    }));
  }

  function fillBoardingPlaceSelect(selectedName) {
    const sel = document.getElementById("pickupBoardingPlace");
    const hint = document.getElementById("pickupBoardingHint");
    if (!sel) return;
    const list = allLocations;
    sel.innerHTML = '<option value="">선택</option>';
    list.forEach((loc) => {
      const opt = document.createElement("option");
      opt.value = loc.name;
      opt.textContent = loc.name;
      if (selectedName && loc.name === selectedName) opt.selected = true;
      sel.appendChild(opt);
    });
    const empty = list.length === 0;
    if (hint) hint.hidden = !empty;
    sel.disabled = empty;
    if (window.JccCustomSelect) window.JccCustomSelect.refresh(document);
  }

  function escapeHtml(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function csrfHeaders() {
    return {
      "Content-Type": "application/json",
      "X-CSRFToken": ctx.csrfToken,
    };
  }

  const regionSelect = document.getElementById("pickupRegion");
  const boardingSelect = document.getElementById("pickupBoardingPlace");

  const confirmOverlay = document.getElementById("retreatConfirmOverlay");
  const confirmTitleEl = document.getElementById("retreatConfirmTitle");
  const confirmMsgEl = document.getElementById("retreatConfirmMsg");
  const confirmOkBtn = document.getElementById("retreatConfirmOk");
  const confirmCancelBtn = document.getElementById("retreatConfirmCancel");
  let confirmResolve = null;

  function openConfirm(message, title, okLabel, cancelLabel) {
    if (!confirmOverlay) return Promise.resolve(false);
    if (confirmResolve) confirmResolve(false);
    if (confirmTitleEl) confirmTitleEl.textContent = title || "확인";
    if (confirmMsgEl) confirmMsgEl.textContent = message || "";
    if (confirmOkBtn) confirmOkBtn.textContent = okLabel || "확인";
    if (confirmCancelBtn) confirmCancelBtn.textContent = cancelLabel || "취소";
    confirmOverlay.hidden = false;
    confirmOverlay.setAttribute("aria-hidden", "false");
    requestAnimationFrame(() => confirmOkBtn?.focus());
    return new Promise((resolve) => {
      confirmResolve = resolve;
    });
  }

  function resolveConfirm(value) {
    if (!confirmOverlay) return;
    confirmOverlay.hidden = true;
    confirmOverlay.setAttribute("aria-hidden", "true");
    const r = confirmResolve;
    confirmResolve = null;
    if (r) r(!!value);
  }

  if (confirmOkBtn) {
    confirmOkBtn.addEventListener("click", () => resolveConfirm(true));
  }
  if (confirmCancelBtn) {
    confirmCancelBtn.addEventListener("click", () => resolveConfirm(false));
  }
  if (confirmOverlay) {
    confirmOverlay.addEventListener("click", (e) => {
      if (e.target === confirmOverlay) resolveConfirm(false);
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !confirmOverlay.hidden) resolveConfirm(false);
    });
  }

  if (ctx.canManage) {
  const tbody = document.getElementById("pickupTbody");
  const statusEl = document.getElementById("pickupStatus");
  const btnAdd = document.getElementById("btnPickupAdd");
  const modalOverlay = document.getElementById("pickupModalOverlay");
  const form = document.getElementById("pickupForm");
  const modalCancel = document.getElementById("pickupModalCancel");
  const modalTitleEl = document.getElementById("pickupModalTitle");
  const modalSubmitBtn = document.getElementById("pickupModalSubmit");
  let editingId = null;

  const colCount = 8;

  const groupSelect = document.getElementById("pickupGroup");
  const divisionSelect = document.getElementById("pickupDivision");
  const nameEl = document.getElementById("pickupName");
  // 회장단 캐스케이딩 플로우에서는 이름이 '조원 선택' select 로 동작한다.
  const memberSelect =
    nameEl && nameEl.tagName === "SELECT" && nameEl.hasAttribute("data-member-select")
      ? nameEl
      : null;
  const isLeaderMemberSelect =
    !!memberSelect && memberSelect.hasAttribute("data-leader-member-select");
  const isLeaderGroupSelect =
    !!groupSelect && groupSelect.hasAttribute("data-leader-group-select");
  const leaderGroupId = ctx.leaderGroupId != null ? String(ctx.leaderGroupId) : "";
  const leaderGroupIds = Array.isArray(ctx.leaderGroupIds)
    ? ctx.leaderGroupIds.map(String)
    : leaderGroupId
      ? [leaderGroupId]
      : [];
  const hasMultipleLeaderGroups =
    isLeaderMemberSelect && leaderGroupIds.length > 1;

  function parseJsonEl(id, fallback) {
    try {
      return JSON.parse(document.getElementById(id)?.textContent || fallback);
    } catch (e) {
      return JSON.parse(fallback);
    }
  }

  const allDivisions = parseJsonEl("retreatDivisionList", "[]");
  const allGroups = parseJsonEl("retreatPickupGroupList", "[]");
  const groupMembers = parseJsonEl("retreatPickupGroupMembers", "{}");

  // 현재 모달의 구분(입회/출회). 추가 시 활성 탭, 수정 시 항목의 구분을 따른다.
  let modalDirection = ctx.direction || "";

  /**
   * 구분에 따라 조원 노출 여부 결정.
   * - 입회(arrival): 입실 전(pending)만 — 아직 입실 안 한 조원
   * - 출회(departure): 입실 전(pending) + 입실(checked_in) — 퇴실만 제외
   * - 그 외(all 등): 전체 노출
   */
  function memberAllowedForDirection(status) {
    const st = status || "";
    if (modalDirection === "arrival") return st === "pending" || st === "";
    if (modalDirection === "departure") {
      return st === "checked_in" || st === "pending" || st === "";
    }
    return true;
  }

  // 실제 조가 존재하는 지역·부서만 노출해 선택 실수를 줄인다.
  const regionsWithGroups = new Set(allGroups.map((g) => Number(g.region_id)));
  const divisionsWithGroups = new Set(allGroups.map((g) => Number(g.division_id)));

  function refreshCustomSelects() {
    if (window.JccCustomSelect) window.JccCustomSelect.refresh(document);
  }

  // 지역 select: 조가 있는 지역만 남긴다 (캐스케이딩 플로우 한정)
  if (regionSelect && memberSelect) {
    Array.from(regionSelect.options).forEach((opt) => {
      if (opt.value && !regionsWithGroups.has(Number(opt.value))) opt.remove();
    });
  }

  function fillDivisionSelect(regionId, selectedId) {
    if (!divisionSelect) return;
    if (!regionId) {
      divisionSelect.innerHTML = '<option value="">지역을 먼저 선택</option>';
      divisionSelect.disabled = true;
      refreshCustomSelects();
      return;
    }
    divisionSelect.disabled = false;
    divisionSelect.innerHTML = '<option value="">선택</option>';
    allDivisions
      .filter(
        (d) =>
          d.region_id === Number(regionId) &&
          (!memberSelect || divisionsWithGroups.has(Number(d.id)))
      )
      .forEach((d) => {
        const opt = document.createElement("option");
        opt.value = String(d.id);
        opt.textContent = d.name;
        if (selectedId != null && String(d.id) === String(selectedId)) {
          opt.selected = true;
        }
        divisionSelect.appendChild(opt);
      });
    refreshCustomSelects();
  }

  function fillGroupSelect(regionId, divisionId, selectedId) {
    if (!groupSelect) return;
    if (!regionId || !divisionId) {
      groupSelect.innerHTML = '<option value="">부서를 먼저 선택</option>';
      groupSelect.disabled = true;
      refreshCustomSelects();
      return;
    }
    groupSelect.disabled = false;
    groupSelect.innerHTML = '<option value="">선택</option>';
    allGroups
      .filter(
        (g) =>
          Number(g.region_id) === Number(regionId) &&
          Number(g.division_id) === Number(divisionId)
      )
      .forEach((g) => {
        const opt = document.createElement("option");
        opt.value = String(g.id);
        opt.textContent = g.name;
        if (selectedId != null && String(g.id) === String(selectedId)) {
          opt.selected = true;
        }
        groupSelect.appendChild(opt);
      });
    refreshCustomSelects();
  }

  function fillMemberSelect(groupId, selectedName) {
    if (!memberSelect) return;
    if (!groupId) {
      memberSelect.innerHTML = '<option value="">조를 먼저 선택</option>';
      memberSelect.disabled = true;
      refreshCustomSelects();
      return;
    }
    memberSelect.disabled = false;
    memberSelect.innerHTML = '<option value="">선택</option>';
    const members = groupMembers[String(groupId)] || [];
    const takenNames = existingPickupNamesForGroup(groupId, editingId);
    let matched = false;
    members.forEach((m) => {
      const isSelected = selectedName != null && m.name === selectedName;
      // 구분(입회/출회)에 따른 입실 상태 필터. 단, 수정 중 선택된 조원은 항상 유지.
      if (!isSelected && !memberAllowedForDirection(m.check_in_status)) return;
      // 이미 차량 요청된 조원은 신규 등록 시 목록에서 제외
      if (!isSelected && takenNames.has(m.name)) return;
      const opt = document.createElement("option");
      opt.value = m.name;
      opt.textContent = m.name;
      opt.dataset.phone = m.phone || "";
      if (isSelected) {
        opt.selected = true;
        matched = true;
      }
      memberSelect.appendChild(opt);
    });
    refreshCustomSelects();
  }

  function autofillContactFromMember() {
    if (!memberSelect) return;
    const opt = memberSelect.options[memberSelect.selectedIndex];
    const phone = opt ? opt.dataset.phone || "" : "";
    if (phone) {
      const contactEl = document.getElementById("pickupContact");
      if (contactEl) {
        contactEl.value = phone;
        markInvalid("pickupContact", false);
      }
    }
  }

  if (regionSelect) {
    regionSelect.addEventListener("change", () => {
      fillDivisionSelect(regionSelect.value, null);
      fillGroupSelect(regionSelect.value, "", null);
      fillMemberSelect("", null);
    });
  }
  if (divisionSelect) {
    divisionSelect.addEventListener("change", () => {
      fillGroupSelect(
        regionSelect ? regionSelect.value : "",
        divisionSelect.value,
        null
      );
      fillMemberSelect("", null);
    });
  }
  if (groupSelect) {
    groupSelect.addEventListener("change", () => {
      fillMemberSelect(groupSelect.value, null);
    });
  }
  if (memberSelect) {
    memberSelect.addEventListener("change", autofillContactFromMember);
  }

  function isValidPhone(raw) {
    const digits = String(raw ?? "").replace(/\D/g, "");
    return /^01[016789]\d{7,8}$/.test(digits);
  }

  function setStatus(msg, isError) {
    if (!statusEl) return;
    statusEl.textContent = msg || "";
    statusEl.classList.toggle("error", !!isError);
  }

  // datetime-local 은 커스텀 피커 버튼(.jcc-dtp-field)이 실제로 보이므로
  // 표시는 그 버튼에, 포커스도 그 버튼으로 보낸다.
  function visibleControl(el) {
    if (el && el.classList.contains("jcc-dtp-native")) {
      return el.parentElement?.querySelector(".jcc-dtp-field") || el;
    }
    return el;
  }

  function markInvalid(id, invalid, message) {
    const el = document.getElementById(id);
    if (!el) return;
    const visible = visibleControl(el);
    el.classList.toggle("is-invalid", !!invalid);
    if (visible !== el) visible.classList.toggle("is-invalid", !!invalid);

    const field = el.closest(".field");
    if (field) {
      let hint = field.querySelector(".jcc-field-error");
      if (invalid) {
        if (!hint) {
          hint = document.createElement("small");
          hint.className = "jcc-field-error";
          field.appendChild(hint);
        }
        hint.textContent = message || "필수 입력 항목입니다.";
      } else if (hint) {
        hint.remove();
      }
    }

    if (invalid) {
      const clear = () => markInvalid(id, false);
      el.addEventListener("input", clear, { once: true });
      el.addEventListener("change", clear, { once: true });
    }
  }

  function clearInvalid(ids) {
    ids.forEach((id) => markInvalid(id, false));
  }

  function focusField(id) {
    const el = document.getElementById(id);
    if (el) visibleControl(el)?.focus();
  }

  function setVal(id, value) {
    const el = document.getElementById(id);
    if (el) el.value = value || "";
  }

  function resetStatusField() {
    const statusField = document.getElementById("pickupModalStatusField");
    const statusBadge = document.getElementById("pickupModalStatusBadge");
    if (statusField) statusField.hidden = true;
    if (statusBadge) {
      statusBadge.textContent = "";
      statusBadge.className = "jcc-retreat-checkInBadge";
    }
  }

  function existingPickupNamesForGroup(groupId, excludePickupId) {
    const names = new Set();
    if (!tbody || !groupId) return names;
    const dir = modalDirection || ctx.direction || "";
    tbody.querySelectorAll("tr[data-pickup-id]").forEach((tr) => {
      if (String(tr.dataset.group) !== String(groupId)) return;
      if ((tr.dataset.direction || ctx.direction) !== dir) return;
      if (
        excludePickupId != null &&
        String(tr.dataset.pickupId) === String(excludePickupId)
      ) {
        return;
      }
      const n = (tr.dataset.name || "").trim();
      if (n) names.add(n);
    });
    return names;
  }

  function isDuplicatePickupName(name, groupId, excludePickupId) {
    if (!tbody || !name) return false;
    const dir = modalDirection || ctx.direction || "";
    return Array.from(tbody.querySelectorAll("tr[data-pickup-id]")).some((tr) => {
      if ((tr.dataset.direction || ctx.direction) !== dir) return false;
      if (
        excludePickupId != null &&
        String(tr.dataset.pickupId) === String(excludePickupId)
      ) {
        return false;
      }
      if (groupId && String(tr.dataset.group) !== String(groupId)) return false;
      return (tr.dataset.name || "").trim() === name;
    });
  }

  function refreshPickupCount() {
    const el = document.querySelector(".jcc-retreat-pickupCount");
    if (!el || !tbody) return;
    const n = tbody.querySelectorAll("tr[data-pickup-id]").length;
    el.textContent = `총 ${n}건`;
  }

  function openModal(editItem) {
    if (!modalOverlay || !form) return;
    resetStatusField();
    form.reset();
    clearInvalid([
      "pickupRegion",
      "pickupDivision",
      "pickupGroup",
      "pickupName",
      "pickupTrainTime",
      "pickupBoardingPlace",
      "pickupContact",
    ]);
    editingId = editItem && editItem.id ? editItem.id : null;
    const isExistingPickup = editingId != null;
    // 조원 명단 필터 기준이 되는 구분 결정 (수정 시 항목 구분, 추가 시 활성 탭)
    modalDirection =
      editItem && editItem.direction ? editItem.direction : ctx.direction || "";
    if (modalTitleEl)
      modalTitleEl.textContent = isExistingPickup
        ? "픽업 정보 수정"
        : "픽업 정보 추가";
    if (modalSubmitBtn)
      modalSubmitBtn.textContent = isExistingPickup ? "저장" : "등록";

    // 기존 픽업 조회·수정 시에만 입실 상태 표시 (신규 차량 요청에는 미표시)
    if (isExistingPickup) {
      const statusField = document.getElementById("pickupModalStatusField");
      const statusBadge = document.getElementById("pickupModalStatusBadge");
      const retiredLabel = editItem.accountRetiredDisplay || editItem.account_retired_display || "";
      const stVal = editItem.checkInStatus || editItem.check_in_status || "";
      const stLabel = editItem.checkInStatusDisplay || editItem.check_in_status_display || "";
      if (statusField && statusBadge && retiredLabel) {
        statusBadge.textContent = retiredLabel;
        statusBadge.className =
          "jcc-retreat-checkInBadge jcc-retreat-checkInBadge--account_retired";
        statusField.hidden = false;
      } else if (statusField && statusBadge && stLabel) {
        statusBadge.textContent = stLabel;
        statusBadge.className = `jcc-retreat-checkInBadge jcc-retreat-checkInBadge--${stVal || "pending"}`;
        statusField.hidden = false;
      }
    }

    // datetime-local 피커 표시 갱신 (래핑된 value setter 트리거)
    setVal("pickupTrainTime", editItem ? editItem.trainTime : "");
    setVal("pickupContact", editItem ? editItem.contact : "");
    setVal("pickupNote", editItem ? editItem.note : "");

    const reg = editItem ? editItem.region || "" : "";
    const div = editItem ? editItem.division || "" : "";
    const grp = editItem ? editItem.group || "" : "";
    if (memberSelect) {
      if (isLeaderMemberSelect) {
        if (isLeaderGroupSelect) {
          const targetGroup = grp || "";
          if (groupSelect) {
            groupSelect.disabled = false;
            groupSelect.value = targetGroup;
          }
          if (targetGroup) {
            fillMemberSelect(targetGroup, editItem ? editItem.name : "");
          } else {
            fillMemberSelect("", null);
          }
        } else {
          fillMemberSelect(leaderGroupId, editItem ? editItem.name : "");
        }
      } else {
        // 캐스케이딩 플로우: 지역→부서→조→조원 순서로 복원
        if (regionSelect) regionSelect.value = reg;
        fillDivisionSelect(reg, div);
        fillGroupSelect(reg, div, grp);
        fillMemberSelect(grp, editItem ? editItem.name : "");
      }
    }
    fillBoardingPlaceSelect(editItem ? editItem.boardingPlace : null);

    modalOverlay.hidden = false;
    modalOverlay.setAttribute("aria-hidden", "false");
    document.getElementById("pickupName")?.focus();
  }

  function closeModal() {
    if (!modalOverlay) return;
    modalOverlay.hidden = true;
    modalOverlay.setAttribute("aria-hidden", "true");
    editingId = null;
    resetStatusField();
  }

  function removeEmptyRow() {
    const empty = document.getElementById("pickupEmptyRow");
    if (empty) empty.remove();
  }

  function rowHtml(item) {
    const dir = item.direction || ctx.direction;
    const dirLabel =
      item.direction_display ||
      (dir === "arrival" ? "입회" : dir === "departure" ? "출회" : "");
    const parts = String(item.train_time_display || "").split(" ");
    const date = parts[0] || "";
    const time = parts[1] || item.train_time_display || "";
    return `
      <td class="num">${escapeHtml(item.number)}</td>
      <td><span class="jcc-retreat-dirTag jcc-retreat-dirTag--${escapeHtml(dir)}">${escapeHtml(dirLabel)}</span></td>
      <td class="jcc-retreat-pickupParticipantName">
        <span class="jcc-retreat-pickupNameText">${escapeHtml(item.name)}</span>
        ${
          item.note
            ? `<span class="jcc-retreat-pickupMemo" title="${escapeHtml(item.note)}">${escapeHtml(item.note)}</span>`
            : ""
        }
      </td>
      <td class="jcc-retreat-pickupStatusCol">${
        item.account_retired_display
          ? `<span class="jcc-retreat-checkInBadge jcc-retreat-checkInBadge--account_retired">${escapeHtml(item.account_retired_display)}</span>`
          : item.check_in_status_display
          ? `<span class="jcc-retreat-checkInBadge jcc-retreat-checkInBadge--${escapeHtml(item.check_in_status || "pending")}">${escapeHtml(item.check_in_status_display)}</span>`
          : "-"
      }</td>
      <td class="jcc-retreat-pickupContactCol">${escapeHtml(item.contact)}</td>
      <td>
        <span class="jcc-retreat-pickupWhen">
          <span class="jcc-retreat-pickupWhen-time">${escapeHtml(time)}</span>
          <span class="jcc-retreat-pickupWhen-date">${escapeHtml(date)}</span>
        </span>
      </td>
      <td>${
        item.boarding_place
          ? `<span class="jcc-retreat-pickupPlaceTag">${escapeHtml(item.boarding_place)}</span>`
          : "-"
      }</td>
      ${
        ctx.canManage || ctx.canDelete
          ? `<td class="jcc-retreat-pickupManageCol">${
              ctx.canDelete
                ? `<button type="button" class="jcc-retreat-pickupDelete" data-pickup-delete aria-label="제거" title="제거"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18" /><path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2" /><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" /><path d="M10 11v6M14 11v6" /></svg></button>`
                : ""
            }</td>`
          : ""
      }
    `;
  }

  function applyRowData(tr, item) {
    tr.dataset.pickupId = String(item.id);
    tr.dataset.name = item.name || "";
    tr.dataset.group = item.group != null ? String(item.group) : "";
    tr.dataset.region = item.region != null ? String(item.region) : "";
    tr.dataset.division = item.division != null ? String(item.division) : "";
    tr.dataset.trainTime = item.train_time_input || "";
    tr.dataset.boardingPlace = item.boarding_place || "";
    tr.dataset.contact = item.contact || "";
    tr.dataset.note = item.note || "";
    tr.dataset.checkInStatus = item.check_in_status || "";
    tr.dataset.checkInStatusDisplay = item.check_in_status_display || "";
    tr.dataset.accountRetired = item.account_retired ? "true" : "false";
    tr.dataset.accountRetiredDisplay = item.account_retired_display || "";
    tr.dataset.direction = item.direction || ctx.direction || "";
    tr.innerHTML = rowHtml(item);
    syncPickupMemoWidth(tr);
  }

  function syncPickupMemoWidth(root) {
    if (!window.matchMedia("(max-width: 640px)").matches) return;
    const scope = root || tbody;
    scope?.querySelectorAll(".jcc-retreat-pickupParticipantName").forEach((cell) => {
      const name = cell.querySelector(".jcc-retreat-pickupNameText");
      const memo = cell.querySelector(".jcc-retreat-pickupMemo");
      if (!name || !memo) return;
      memo.style.maxWidth = `${Math.ceil(name.getBoundingClientRect().width)}px`;
    });
  }

  function appendRow(item) {
    if (!tbody) return;
    removeEmptyRow();
    const tr = document.createElement("tr");
    applyRowData(tr, item);
    tbody.appendChild(tr);
    refreshPickupCount();
    applyPickupSort();
  }

  function updateRow(item) {
    if (!tbody) return;
    const tr = tbody.querySelector(`tr[data-pickup-id="${item.id}"]`);
    if (tr) applyRowData(tr, item);
    applyPickupSort();
  }

  if (btnAdd) btnAdd.addEventListener("click", () => openModal());
  syncPickupMemoWidth();
  let memoResizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(memoResizeTimer);
    memoResizeTimer = setTimeout(() => {
      tbody?.querySelectorAll(".jcc-retreat-pickupMemo").forEach((memo) => {
        memo.style.removeProperty("max-width");
      });
      syncPickupMemoWidth();
    }, 100);
  });
  if (modalCancel) modalCancel.addEventListener("click", closeModal);
  if (modalOverlay) {
    modalOverlay.addEventListener("click", (e) => {
      if (e.target === modalOverlay) closeModal();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !modalOverlay.hidden) closeModal();
    });
  }

  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = document.getElementById("pickupName")?.value.trim() || "";
      const trainTime =
        document.getElementById("pickupTrainTime")?.value.trim() || "";
      const boardingPlace =
        document.getElementById("pickupBoardingPlace")?.value.trim() || "";
      const contact =
        document.getElementById("pickupContact")?.value.trim() || "";
      const note = document.getElementById("pickupNote")?.value.trim() || "";
      const group =
        groupSelect?.value ||
        (isLeaderMemberSelect && !isLeaderGroupSelect ? leaderGroupId : "");
      const region = regionSelect?.value || "";
      const division = divisionSelect?.value || "";

      const trainTimeLabel =
        document
          .querySelector('label[for="pickupTrainTime"]')
          ?.textContent?.replace(/\s*\*\s*$/, "")
          .trim() || "열차 시각";

      const missing = [];
      if (memberSelect && !isLeaderMemberSelect) {
        if (!region) missing.push(["pickupRegion", "지역을 선택해 주세요."]);
        if (!division) missing.push(["pickupDivision", "부서를 선택해 주세요."]);
        if (!group) missing.push(["pickupGroup", "조를 선택해 주세요."]);
      } else if (isLeaderMemberSelect && (isLeaderGroupSelect || hasMultipleLeaderGroups)) {
        if (!group) missing.push(["pickupGroup", "조를 선택해 주세요."]);
      }
      if (!name)
        missing.push([
          "pickupName",
          memberSelect ? "조원을 선택해 주세요." : "이름을 입력해 주세요.",
        ]);
      if (!trainTime)
        missing.push(["pickupTrainTime", `${trainTimeLabel}을(를) 선택해 주세요.`]);
      if (!boardingPlace)
        missing.push([
          "pickupBoardingPlace",
          allLocations.length
            ? "탑승장소를 선택해 주세요."
            : "등록된 탑승장소가 없습니다. 회장단에게 등록을 요청해 주세요.",
        ]);
      if (!contact) missing.push(["pickupContact", "연락처를 입력해 주세요."]);

      clearInvalid([
        "pickupRegion",
        "pickupDivision",
        "pickupGroup",
        "pickupName",
        "pickupTrainTime",
        "pickupBoardingPlace",
        "pickupContact",
      ]);

      if (missing.length) {
        missing.forEach(([id, msg]) => markInvalid(id, true, msg));
        focusField(missing[0][0]);
        return;
      }
      if (!isValidPhone(contact)) {
        markInvalid(
          "pickupContact",
          true,
          "올바른 휴대폰 번호 형식이 아닙니다. (예: 010-1234-5678)"
        );
        focusField("pickupContact");
        return;
      }

      const isEdit = editingId != null;
      if (!isEdit && isDuplicatePickupName(name, group || null, null)) {
        markInvalid(
          "pickupName",
          true,
          "이미 차량 요청이 등록된 조원입니다."
        );
        focusField("pickupName");
        return;
      }

      const failMsg = isEdit ? "수정에 실패했습니다." : "등록에 실패했습니다.";
      setStatus("");
      try {
        const payload = {
          name,
          group: group || null,
          region: region || null,
          division: division || null,
          train_time: trainTime,
          boarding_place: boardingPlace,
          contact,
          note,
        };
        if (!isEdit) payload.direction = ctx.direction;
        const r = await fetch(
          isEdit ? `${ctx.apiDetailBase}${editingId}/` : ctx.apiList,
          {
            method: isEdit ? "PATCH" : "POST",
            credentials: "same-origin",
            headers: csrfHeaders(),
            body: JSON.stringify(payload),
          }
        );
        if (!r.ok) {
          const err = await r.json().catch(() => ({}));
          const msg =
            err.detail ||
            Object.values(err)
              .flat()
              .join(" ") ||
            failMsg;
          throw new Error(msg);
        }
        const item = await r.json();
        if (isEdit) updateRow(item);
        else appendRow(item);
        closeModal();
        setStatus(isEdit ? "수정되었습니다." : "등록되었습니다.", false);
      } catch (err) {
        setStatus(err.message || failMsg, true);
      }
    });
  }

  function openEditFromRow(tr) {
    if (!tr) return;
    openModal({
      id: tr.dataset.pickupId,
      name: tr.dataset.name || "",
      trainTime: tr.dataset.trainTime || "",
      boardingPlace: tr.dataset.boardingPlace || "",
      contact: tr.dataset.contact || "",
      note: tr.dataset.note || "",
      group: tr.dataset.group || "",
      region: tr.dataset.region || "",
      division: tr.dataset.division || "",
      checkInStatus: tr.dataset.checkInStatus || "",
      checkInStatusDisplay: tr.dataset.checkInStatusDisplay || "",
      accountRetiredDisplay: tr.dataset.accountRetiredDisplay || "",
      direction: tr.dataset.direction || "",
    });
  }

  if (tbody) {
    tbody.addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-pickup-delete]");
      if (!btn) {
        // 제거 버튼이 아닌 행 클릭 → 수정 모달 바로 열기
        const row = e.target.closest("tr[data-pickup-id]");
        if (row) openEditFromRow(row);
        return;
      }
      e.stopPropagation();
      const tr = btn.closest("tr[data-pickup-id]");
      if (!tr) return;
      const pickupId = tr.dataset.pickupId;
      const name = tr.dataset.name || "";
      const ok = await openConfirm(
        `${name} 픽업 정보를 제거할까요?`,
        "픽업 정보 제거",
        "제거",
        "취소"
      );
      if (!ok) return;

      setStatus("");
      try {
        const r = await fetch(`${ctx.apiDetailBase}${pickupId}/`, {
          method: "DELETE",
          credentials: "same-origin",
          headers: { "X-CSRFToken": ctx.csrfToken },
        });
        if (!r.ok) throw new Error(await r.text());
        tr.remove();
        if (!tbody.querySelector("tr[data-pickup-id]")) {
          const empty = document.createElement("tr");
          empty.id = "pickupEmptyRow";
          empty.innerHTML = `<td colspan="${colCount}">등록된 픽업 정보가 없습니다.</td>`;
          tbody.appendChild(empty);
        }
        refreshPickupCount();
        setStatus("제거되었습니다.", false);
      } catch (err) {
        setStatus(err.message || "제거에 실패했습니다.", true);
      }
    });
  }
  }

  // --- 전체 탭: 컬럼 헤더 클릭 정렬 ----------------------------------------
  const pickupSortTbody = document.getElementById("pickupTbody");
  const PICKUP_STATUS_ORDER = { pending: 0, checked_in: 1, checked_out: 2 };
  let pickupSortKey = null;
  let pickupSortDir = "asc";

  function pickupSortValue(tr, key) {
    switch (key) {
      case "name":
        return (tr.dataset.name || "").trim();
      case "status":
        return PICKUP_STATUS_ORDER[tr.dataset.checkInStatus] ?? 99;
      case "train_time": {
        const iso = tr.dataset.trainTime || "";
        if (!iso) return Number.POSITIVE_INFINITY;
        const t = new Date(iso).getTime();
        return Number.isNaN(t) ? Number.POSITIVE_INFINITY : t;
      }
      case "boarding_place":
        return (tr.dataset.boardingPlace || "").trim();
      default:
        return 0;
    }
  }

  function comparePickupRows(a, b, key) {
    const va = pickupSortValue(a, key);
    const vb = pickupSortValue(b, key);
    if (typeof va === "number" && typeof vb === "number") {
      return va - vb;
    }
    return String(va).localeCompare(String(vb), "ko");
  }

  function renumberPickupRows() {
    if (!pickupSortTbody || ctx.direction !== "all") return;
    let n = 0;
    pickupSortTbody.querySelectorAll("tr[data-pickup-id]").forEach((tr) => {
      n += 1;
      const numCell = tr.querySelector("td.num");
      if (numCell) numCell.textContent = String(n);
    });
  }

  function applyPickupSort() {
    if (!pickupSortTbody || !pickupSortKey || ctx.direction !== "all") return;
    const rows = Array.from(
      pickupSortTbody.querySelectorAll("tr[data-pickup-id]")
    );
    const factor = pickupSortDir === "desc" ? -1 : 1;
    rows
      .sort((a, b) => {
        const c = comparePickupRows(a, b, pickupSortKey);
        if (c !== 0) return c * factor;
        const na = (a.dataset.name || "").trim();
        const nb = (b.dataset.name || "").trim();
        return na.localeCompare(nb, "ko");
      })
      .forEach((tr) => pickupSortTbody.appendChild(tr));
    renumberPickupRows();
  }

  function bindPickupSorting() {
    if (ctx.direction !== "all") return;
    const headers = document.querySelectorAll(
      "#pickupTable .jcc-retreat-sortable[data-sort-key]"
    );
    if (!headers.length) return;
    headers.forEach((th) => {
      th.addEventListener("click", (e) => {
        e.stopPropagation();
        const key = th.dataset.sortKey;
        if (pickupSortKey === key) {
          pickupSortDir = pickupSortDir === "asc" ? "desc" : "asc";
        } else {
          pickupSortKey = key;
          pickupSortDir = "asc";
        }
        headers.forEach((h) => {
          if (h === th) {
            h.dataset.sortDir = pickupSortDir;
            h.setAttribute(
              "aria-sort",
              pickupSortDir === "asc" ? "ascending" : "descending"
            );
          } else {
            delete h.dataset.sortDir;
            h.setAttribute("aria-sort", "none");
          }
        });
        applyPickupSort();
      });
    });
  }

  bindPickupSorting();

  if (ctx.canManageLocation) initLocationManagement();

  function initLocationManagement() {
    const btnManage = document.getElementById("btnPickupLocationManage");
    const locOverlay = document.getElementById("pickupLocationModalOverlay");
    const locClose = document.getElementById("pickupLocationModalClose");
    const locName = document.getElementById("pickupLocManageName");
    const locAddBtn = document.getElementById("pickupLocAddBtn");
    const locTbody = document.getElementById("pickupLocationTbody");
    const locStatus = document.getElementById("pickupLocationStatus");
    if (!btnManage || !locOverlay) return;

    function setLocStatus(msg, isError) {
      if (!locStatus) return;
      locStatus.textContent = msg || "";
      locStatus.classList.toggle("error", !!isError);
    }

    function renderLocationManageList() {
      if (!locTbody) return;
      if (!allLocations.length) {
        locTbody.innerHTML =
          '<tr id="pickupLocationEmptyRow"><td colspan="2">등록된 탑승장소가 없습니다.</td></tr>';
        return;
      }
      locTbody.innerHTML = allLocations
        .map(
          (loc) => `
        <tr data-location-id="${loc.id}">
          <td>${escapeHtml(loc.name)}</td>
          <td class="jcc-pickup-locActionsCell">
            <div class="jcc-pickup-locActions">
              <button type="button" class="jcc-pickup-locBtn" data-loc-edit>수정</button>
              <button type="button" class="jcc-pickup-locBtn jcc-pickup-locBtn--danger" data-loc-delete>삭제</button>
            </div>
          </td>
        </tr>`
        )
        .join("");
    }

    async function refreshLocationsFromApi() {
      const r = await fetch(ctx.apiLocationList, { credentials: "same-origin" });
      if (!r.ok) throw new Error("탑승장소 목록을 불러올 수 없습니다.");
      const items = await r.json();
      syncLocationsFromList(items);
      renderLocationManageList();
      fillBoardingPlaceSelect(boardingSelect?.value || null);
    }

    function openLocationModal() {
      locOverlay.hidden = false;
      locOverlay.setAttribute("aria-hidden", "false");
      setLocStatus("");
      renderLocationManageList();
    }

    function closeLocationModal() {
      locOverlay.hidden = true;
      locOverlay.setAttribute("aria-hidden", "true");
    }

    btnManage.addEventListener("click", openLocationModal);
    if (locClose) locClose.addEventListener("click", closeLocationModal);
    locOverlay.addEventListener("click", (e) => {
      if (e.target === locOverlay) closeLocationModal();
    });

    if (locAddBtn) {
      locAddBtn.addEventListener("click", async () => {
        const name = locName?.value.trim() || "";
        if (!name) {
          setLocStatus("탑승장소 이름을 입력하세요.", true);
          locName?.focus();
          return;
        }
        setLocStatus("");
        try {
          const r = await fetch(ctx.apiLocationList, {
            method: "POST",
            credentials: "same-origin",
            headers: csrfHeaders(),
            body: JSON.stringify({ name }),
          });
          if (!r.ok) {
            const err = await r.json().catch(() => ({}));
            throw new Error(
              err.detail ||
                Object.values(err).flat().join(" ") ||
                "추가에 실패했습니다."
            );
          }
          if (locName) locName.value = "";
          await refreshLocationsFromApi();
          setLocStatus("탑승장소가 추가되었습니다.", false);
          locName?.focus();
        } catch (err) {
          setLocStatus(err.message || "추가에 실패했습니다.", true);
        }
      });
    }

    if (locName) {
      locName.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          locAddBtn?.click();
        }
      });
    }

    if (locTbody) {
      locTbody.addEventListener("click", async (e) => {
        const editBtn = e.target.closest("[data-loc-edit]");
        const delBtn = e.target.closest("[data-loc-delete]");
        const tr = e.target.closest("tr[data-location-id]");
        if (!tr) return;
        const locId = tr.dataset.locationId;
        const currentName = tr.children[0]?.textContent?.trim() || "";

        if (editBtn) {
          const next = window.prompt("탑승장소 이름", currentName);
          if (next == null) return;
          const name = next.trim();
          if (!name) {
            setLocStatus("탑승장소 이름을 입력하세요.", true);
            return;
          }
          setLocStatus("");
          try {
            const r = await fetch(`${ctx.apiLocationDetailBase}${locId}/`, {
              method: "PATCH",
              credentials: "same-origin",
              headers: csrfHeaders(),
              body: JSON.stringify({ name }),
            });
            if (!r.ok) throw new Error("수정에 실패했습니다.");
            await refreshLocationsFromApi();
            setLocStatus("수정되었습니다.", false);
          } catch (err) {
            setLocStatus(err.message || "수정에 실패했습니다.", true);
          }
          return;
        }

        if (delBtn) {
          const ok = await openConfirm(
            `"${currentName}" 탑승장소를 삭제할까요?`,
            "탑승장소 삭제",
            "삭제",
            "취소"
          );
          if (!ok) return;
          setLocStatus("");
          try {
            const r = await fetch(`${ctx.apiLocationDetailBase}${locId}/`, {
              method: "DELETE",
              credentials: "same-origin",
              headers: { "X-CSRFToken": ctx.csrfToken },
            });
            if (!r.ok && r.status !== 204) throw new Error("삭제에 실패했습니다.");
            await refreshLocationsFromApi();
            setLocStatus("삭제되었습니다.", false);
          } catch (err) {
            setLocStatus(err.message || "삭제에 실패했습니다.", true);
          }
        }
      });
    }
  }
})();
