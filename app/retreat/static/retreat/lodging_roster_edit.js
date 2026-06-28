/**
 * 숙소 전체 명단 — 조원 수정 모달
 */
(function () {
  "use strict";

  const ctx = window.LODGING_ROSTER_CTX;
  if (!ctx) return;

  const tbody = document.getElementById("lodgingRosterBody");
  const overlay = document.getElementById("rosterEditOverlay");
  const form = document.getElementById("rosterEditForm");
  if (!tbody || !overlay || !form) return;

  const CHECK_IN_LABELS = {
    pending: "입실전",
    checked_in: "입실",
    checked_out: "퇴실",
  };

  const STAMP_LOCK_MSG =
    "퇴실 상태 조원은 정보를 수정할 수 없습니다.";

  function isProfileLocked(source) {
    if (!source) return false;
    if (source instanceof HTMLElement) {
      return (
        source.dataset.profileLocked === "true" ||
        source.dataset.checkIn === "checked_out" ||
        source.dataset.checkInStatus === "checked_out"
      );
    }
    return !!(
      source.profile_locked ||
      source.profileLocked ||
      source.checkIn === "checked_out" ||
      source.check_in_status === "checked_out"
    );
  }

  function isExpectedInLocked(source) {
    if (!source) return false;
    if (source instanceof HTMLElement) {
      return source.dataset.expectedInLocked === "true";
    }
    return !!source.expected_check_in_locked;
  }

  function isExpectedOutLocked(source) {
    if (!source) return false;
    if (source instanceof HTMLElement) {
      return source.dataset.expectedOutLocked === "true";
    }
    return !!source.expected_check_out_locked;
  }

  function isExpectedTimestampsLocked(source) {
    return isExpectedInLocked(source) && isExpectedOutLocked(source);
  }

  function isCheckOutAfterCheckIn(inVal, outVal) {
    if (!inVal || !outVal) return true;
    const ti = new Date(inVal).getTime();
    const to = new Date(outVal).getTime();
    if (Number.isNaN(ti) || Number.isNaN(to)) return true;
    return to > ti;
  }

  const titleEl = document.getElementById("rosterEditTitle");
  const submitBtn = document.getElementById("rosterEditSubmit");
  const cancelBtn = document.getElementById("rosterEditCancel");
  const nameInput = document.getElementById("rosterEditName");
  const genderInput = document.getElementById("rosterEditGender");
  const phoneInput = document.getElementById("rosterEditPhone");
  const memoInput = document.getElementById("rosterEditMemo");
  const expectedInInput = document.getElementById("rosterEditExpectedIn");
  const expectedOutInput = document.getElementById("rosterEditExpectedOut");
  const lodgingInput = document.getElementById("rosterEditLodging");
  const roleInput = document.getElementById("rosterEditRole");
  const checkInInput = document.getElementById("rosterEditCheckIn");
  const toastEl = document.getElementById("rosterEditToast");

  let modalAttendeeId = null;
  let modalGroupId = null;
  let modalGroupRegionId = null;
  let modalGroupDivisionId = null;
  let modalInitialCheckIn = "pending";
  let attendeePicker = null;

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function phoneInputValue(phone) {
    if (!phone) return "";
    if (window.JccPhoneFormat) return JccPhoneFormat.formatMobilePhone(phone);
    return phone;
  }

  function phoneSubmitValue(raw) {
    if (window.JccPhoneFormat) return JccPhoneFormat.normalizeForSubmit(raw);
    return String(raw ?? "").trim();
  }

  function toDatetimeLocalValue(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const off = d.getTimezoneOffset();
    const local = new Date(d.getTime() - off * 60000);
    return local.toISOString().slice(0, 16);
  }

  function isoFromDatetimeLocal(val) {
    if (!val) return null;
    const d = new Date(val);
    if (Number.isNaN(d.getTime())) return null;
    return d.toISOString();
  }

  function formatStampHtml(iso) {
    if (!iso) return "-";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "-";
    const y2 = String(d.getFullYear() % 100).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    const h24 = d.getHours();
    const mi = String(d.getMinutes()).padStart(2, "0");
    const time = `${String(h24).padStart(2, "0")}:${mi}`;
    return (
      '<span class="jcc-stamp-date">' +
      y2 +
      "-" +
      mm +
      "-" +
      dd +
      "</span> " +
      '<span class="jcc-stamp-time">' +
      time +
      "</span>"
    );
  }

  function lodgingKeysFromData(data) {
    const status = data.lodging_stay_status || "";
    const eligible = status === "active" || status === "unassigned";
    let eligibleKey = eligible ? "eligible" : "ineligible";
    let assignmentKey = "";
    let scope = "na";
    if (eligible) {
      if (status === "active") {
        assignmentKey = "assigned";
        scope = "assigned";
      } else {
        assignmentKey = "unassigned";
        scope = "unassigned";
      }
    }
    return { eligibleKey, assignmentKey, scope };
  }

  function lodgingCellHtml(data) {
    if (window.JccLodgingStayBadge) {
      return window.JccLodgingStayBadge.render(data);
    }
    const display = data.lodging_stay_display || "";
    if (!display) return '<span class="muted">-</span>';
    const status = data.lodging_stay_status || "";
    return (
      '<span class="jcc-retreat-lodgingStayBadge jcc-retreat-lodgingStayBadge--' +
      escapeHtml(status) +
      '">' +
      escapeHtml(display) +
      "</span>"
    );
  }

  function showToast(msg, isError) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.toggle("is-error", !!isError);
    toastEl.hidden = false;
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => {
      toastEl.hidden = true;
    }, 2800);
  }

  function setLodgingOptions(groupId, selectedId, gender) {
    if (!lodgingInput || !window.JccLodgingAssignOptions) return;
    const rooms = ctx.groupRooms[String(groupId)] || ctx.groupRooms[groupId] || [];
    window.JccLodgingAssignOptions.applyToSelect(lodgingInput, rooms, {
      gender: gender || "",
      selectedId: selectedId || "",
      refreshRoot: overlay,
    });
  }

  function createUserPicker(root) {
    if (!root || !ctx.urls.userSearchUrl) return null;
    const input = root.querySelector("[data-user-picker-input]");
    const list = root.querySelector("[data-user-picker-list]");
    const hidden = root.querySelector("[data-user-picker-id]");
    if (!input || !list || !hidden) return null;

    let selected = null;
    let items = [];
    let activeIdx = -1;
    let timer = null;

    function filterParams() {
      const params = new URLSearchParams();
      if (modalGroupDivisionId) params.set("division", String(modalGroupDivisionId));
      else if (modalGroupRegionId) params.set("region", String(modalGroupRegionId));
      return params;
    }

    function clear() {
      selected = null;
      hidden.value = "";
      input.value = "";
      list.hidden = true;
      list.innerHTML = "";
    }

    function setSelected(id, label) {
      selected = { id: Number(id), name: label || "" };
      hidden.value = String(id);
      input.value = label || "";
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
          return `<li role="option" data-idx="${i}" class="${
            i === activeIdx ? "is-active" : ""
          }">${escapeHtml(shown)}</li>`;
        })
        .join("");
      list.hidden = false;
    }

    async function search(q) {
      const params = filterParams();
      params.set("q", q);
      const res = await fetch(`${ctx.urls.userSearchUrl}?${params}`, {
        credentials: "same-origin",
      });
      if (!res.ok) throw new Error("검색 실패");
      items = await res.json();
      activeIdx = -1;
      renderList();
    }

    input.addEventListener("input", () => {
      clearTimeout(timer);
      const q = input.value.trim();
      if (!q) {
        clear();
        return;
      }
      timer = setTimeout(() => {
        search(q).catch(() => {
          list.innerHTML =
            '<li class="muted" role="option" aria-disabled="true">검색 실패</li>';
          list.hidden = false;
        });
      }, 200);
    });

    list.addEventListener("click", (e) => {
      const li = e.target.closest("[data-idx]");
      if (!li) return;
      const u = items[Number(li.dataset.idx)];
      if (u) setSelected(u.id, u.name || u.display_name || u.username);
    });

    return {
      clear,
      setSelected,
      getId: () => hidden.value || "",
    };
  }

  function setModalFieldDisabled(el, disabled) {
    if (!el) return;
    el.disabled = !!disabled;
    el.classList.toggle("is-readonly", !!disabled);
  }

  function applyModalProfileLock(profileLocked, viewOnly, statusOnlyEdit) {
    const profileReadOnly = !!profileLocked;
    if (viewOnly) {
      setModalFieldDisabled(expectedInInput, true);
      setModalFieldDisabled(expectedOutInput, true);
    } else if (statusOnlyEdit) {
      setModalFieldDisabled(expectedInInput, true);
      setModalFieldDisabled(expectedOutInput, false);
    } else {
      setModalFieldDisabled(expectedInInput, false);
      setModalFieldDisabled(expectedOutInput, false);
    }
    [
      nameInput,
      phoneInput,
      genderInput,
      memoInput,
      lodgingInput,
      roleInput,
    ].forEach((el) => setModalFieldDisabled(el, profileReadOnly));
    const pickerInput = form?.querySelector("[data-user-picker-input]");
    setModalFieldDisabled(pickerInput, profileReadOnly);
    if (checkInInput) setModalFieldDisabled(checkInInput, viewOnly);
    if (submitBtn) {
      submitBtn.hidden = !!viewOnly;
      submitBtn.disabled = !!viewOnly;
    }
  }

  function openEditForRow(tr) {
    modalAttendeeId = Number(tr.dataset.attendeeId);
    modalGroupId = Number(tr.dataset.groupId);
    modalGroupRegionId = Number(tr.dataset.groupRegionId) || null;
    modalGroupDivisionId = Number(tr.dataset.groupDivisionId) || null;
    const checkIn = tr.dataset.checkIn || "pending";
    modalInitialCheckIn = checkIn;
    const profileLocked = isProfileLocked(tr);
    const viewOnly = profileLocked && !ctx.canChangeStatus;
    const statusOnlyEdit = profileLocked && ctx.canChangeStatus;

    if (titleEl) {
      if (viewOnly) titleEl.textContent = "조원 보기";
      else if (statusOnlyEdit) titleEl.textContent = "입·퇴실 변경";
      else titleEl.textContent = "조원 수정";
    }
    if (submitBtn) {
      submitBtn.hidden = false;
      submitBtn.disabled = false;
    }
    if (nameInput) nameInput.value = tr.dataset.name || "";
    if (phoneInput) phoneInput.value = phoneInputValue(tr.dataset.phone || "");
    if (genderInput) genderInput.value = tr.dataset.gender || "";
    if (memoInput) memoInput.value = tr.dataset.memo || "";
    if (expectedInInput)
      expectedInInput.value = toDatetimeLocalValue(tr.dataset.expectedInAt || "");
    if (expectedOutInput)
      expectedOutInput.value = toDatetimeLocalValue(tr.dataset.expectedOutAt || "");
    applyModalProfileLock(profileLocked, viewOnly, statusOnlyEdit);
    if (roleInput) roleInput.value = tr.dataset.memberRole || "member";
    if (checkInInput) checkInInput.value = checkIn;

    setLodgingOptions(modalGroupId, tr.dataset.lodgingRoom || "", tr.dataset.gender || "");

    if (attendeePicker) {
      if (tr.dataset.userId) {
        attendeePicker.setSelected(tr.dataset.userId, tr.dataset.userLabel || "");
      } else {
        attendeePicker.clear();
      }
    }

    overlay.hidden = false;
    overlay.setAttribute("aria-hidden", "false");
    window.JccCustomSelect?.refresh?.(overlay);
    const focusEl = viewOnly
      ? cancelBtn
      : statusOnlyEdit
        ? checkInInput || expectedOutInput
        : nameInput;
    requestAnimationFrame(() => focusEl?.focus());
  }

  function closeModal() {
    window.JccDateTimePicker?.close?.();
    overlay.hidden = true;
    overlay.setAttribute("aria-hidden", "true");
    modalAttendeeId = null;
  }

  function updateRowFromData(tr, data) {
    if (!tr || !data) return;

    tr.dataset.checkIn = data.check_in_status || "pending";
    tr.dataset.checkInStatus = data.check_in_status || "pending";
    tr.dataset.gender = data.gender || "";
    tr.dataset.memo = data.memo || "";
    tr.dataset.memberRole = data.member_role || "member";
    tr.dataset.name = data.name || "";
    tr.dataset.phone = data.phone || "";
    tr.dataset.expectedInAt = data.expected_check_in_at || "";
    tr.dataset.expectedOutAt = data.expected_check_out_at || "";
    if ("expected_timestamps_locked" in data || "profile_locked" in data) {
      const locked = !!(data.profile_locked ?? data.expected_timestamps_locked);
      tr.dataset.expectedTimestampsLocked = locked ? "true" : "false";
      tr.dataset.profileLocked = locked ? "true" : "false";
      tr.dataset.expectedInLocked = locked ? "true" : "false";
      tr.dataset.expectedOutLocked =
        locked && !ctx.canChangeStatus ? "true" : "false";
    }
    tr.dataset.lodgingRoom = data.lodging_room ? String(data.lodging_room) : "";
    tr.dataset.lodgingStayStatus = data.lodging_stay_status || "";
    tr.classList.toggle(
      "jcc-retreat-rosterRow--unassigned",
      data.lodging_stay_status === "unassigned"
    );

    const nameEl = tr.querySelector("[data-name]");
    if (nameEl && data.name) nameEl.textContent = data.name;

    const roleTag = tr.querySelector("[data-role-tag]");
    if (roleTag && data.member_role) {
      roleTag.textContent = data.member_role_display || roleTag.textContent;
      roleTag.className = `jcc-retreat-roleTag jcc-retreat-roleTag--${data.member_role}`;
    }

    const badge = tr.querySelector("[data-status-badge]");
    if (badge) {
      badge.textContent =
        data.check_in_status_display || CHECK_IN_LABELS[data.check_in_status] || "";
      badge.className = `jcc-retreat-checkInBadge jcc-retreat-checkInBadge--${data.check_in_status}`;
    }

    const inLabel = tr.querySelector("[data-expected-in-label]");
    if (inLabel) {
      if (data.expected_check_in_at) {
        inLabel.innerHTML = formatStampHtml(data.expected_check_in_at);
      } else {
        inLabel.textContent = "-";
      }
      inLabel.classList.toggle("muted", !data.expected_check_in_at);
    }

    const outLabel = tr.querySelector("[data-expected-out-label]");
    if (outLabel) {
      if (data.expected_check_out_at) {
        outLabel.innerHTML = formatStampHtml(data.expected_check_out_at);
      } else {
        outLabel.textContent = "-";
      }
      outLabel.classList.toggle("muted", !data.expected_check_out_at);
    }

    const lodgingCell = tr.querySelector("[data-lodging-cell]");
    if (lodgingCell) lodgingCell.innerHTML = lodgingCellHtml(data);
  }

  async function patchAttendee(attendeeId, payload) {
    const res = await fetch(
      ctx.urls.attendeeDetailTemplate.replace("__id__", String(attendeeId)),
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": ctx.csrfToken,
        },
        credentials: "same-origin",
        body: JSON.stringify(payload),
      }
    );
    if (!res.ok) {
      let msg = "저장 실패";
      try {
        const err = await res.json();
        msg = Object.values(err).flat().join(" ") || msg;
      } catch (e) {}
      throw new Error(msg);
    }
    return res.json();
  }

  async function onSubmit(e) {
    e.preventDefault();
    if (!submitBtn || submitBtn.hidden || !modalAttendeeId) return;
    submitBtn.disabled = true;

    const tr = tbody.querySelector(`tr[data-attendee-id="${modalAttendeeId}"]`);
    const profileLocked = isProfileLocked(tr);
    const statusOnlyEdit = profileLocked && ctx.canChangeStatus;
    const newCheckIn = checkInInput?.value || modalInitialCheckIn;
    const payload = {};

    if (ctx.canChangeStatus && checkInInput) {
      payload.check_in_status = newCheckIn;
    }

    if (statusOnlyEdit) {
      payload.expected_check_out_at = isoFromDatetimeLocal(
        expectedOutInput?.value || ""
      );
      const inVal =
        expectedInInput?.value ||
        (tr?.dataset?.expectedInAt
          ? toDatetimeLocalValue(tr.dataset.expectedInAt)
          : "");
      const outVal = expectedOutInput?.value || "";
      if (!isCheckOutAfterCheckIn(inVal, outVal)) {
        submitBtn.disabled = false;
        showToast("퇴실 시각은 입실 시각보다 뒤여야 합니다.", true);
        expectedOutInput?.focus?.();
        return;
      }
    } else {
      payload.name = (nameInput?.value || "").trim();
      payload.gender = genderInput?.value || "";
      payload.phone = phoneSubmitValue(phoneInput?.value || "");
      payload.memo = (memoInput?.value || "").trim();
      payload.member_role = roleInput?.value || "member";
      payload.user = attendeePicker?.getId() ? Number(attendeePicker.getId()) : null;
      const timestampsLocked = isProfileLocked(tr) || expectedInInput?.disabled;
      if (!timestampsLocked) {
        payload.expected_check_in_at = isoFromDatetimeLocal(
          expectedInInput?.value || ""
        );
        payload.expected_check_out_at = isoFromDatetimeLocal(
          expectedOutInput?.value || ""
        );
      }
      payload.lodging_room =
        lodgingInput && lodgingInput.value ? Number(lodgingInput.value) : null;

      if (!payload.name) {
        submitBtn.disabled = false;
        showToast("실명은 필수입니다.", true);
        nameInput?.focus();
        return;
      }
      if (!payload.gender) {
        submitBtn.disabled = false;
        showToast("성별은 필수입니다.", true);
        genderInput?.focus();
        return;
      }

      const inVal = expectedInInput?.value || "";
      const outVal = expectedOutInput?.value || "";
      if (!timestampsLocked && inVal && outVal && !isCheckOutAfterCheckIn(inVal, outVal)) {
        submitBtn.disabled = false;
        showToast("퇴실 시각은 입실 시각보다 뒤여야 합니다.", true);
        return;
      }
    }

    if (
      ctx.canChangeStatus &&
      newCheckIn !== modalInitialCheckIn &&
      !window.confirm(
        `${CHECK_IN_LABELS[modalInitialCheckIn] || modalInitialCheckIn} → ${
          CHECK_IN_LABELS[newCheckIn] || newCheckIn
        }\n\n이대로 변경할까요?`
      )
    ) {
      submitBtn.disabled = false;
      return;
    }

    try {
      const data = await patchAttendee(modalAttendeeId, payload);
      const tr = tbody.querySelector(`tr[data-attendee-id="${modalAttendeeId}"]`);
      updateRowFromData(tr, data);
      showToast("수정됨", false);
      closeModal();
    } catch (err) {
      showToast(err.message || "저장 실패", true);
    } finally {
      submitBtn.disabled = false;
    }
  }

  tbody.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-roster-edit]");
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    const tr = btn.closest("tr[data-attendee-id]");
    if (tr) openEditForRow(tr);
  });

  if (cancelBtn) cancelBtn.addEventListener("click", closeModal);
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !overlay.hidden) closeModal();
  });
  form.addEventListener("submit", onSubmit);
  if (phoneInput && window.JccPhoneFormat) JccPhoneFormat.bindInput(phoneInput);
  if (genderInput) {
    genderInput.addEventListener("change", () => {
      if (!modalGroupId) return;
      setLodgingOptions(modalGroupId, lodgingInput?.value || "", genderInput.value || "");
    });
  }

  attendeePicker = createUserPicker(form.querySelector("[data-user-picker]"));

  const overlayObserver = new MutationObserver(() => {
    if (!overlay.hidden) window.JccCustomSelect?.refresh?.(overlay);
  });
  overlayObserver.observe(overlay, {
    attributes: true,
    attributeFilter: ["hidden", "aria-hidden"],
  });
})();
