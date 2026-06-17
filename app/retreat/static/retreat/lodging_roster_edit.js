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
    "자동 퇴실 처리된 조원은 입·퇴실 시각을 수정할 수 없습니다.";

  function isExpectedTimestampsLocked(source) {
    if (!source) return false;
    if (source instanceof HTMLElement) {
      return source.dataset.expectedTimestampsLocked === "true";
    }
    return !!source.expected_timestamps_locked;
  }

  function syncModalExpectedInputs(locked) {
    [expectedInInput, expectedOutInput].forEach((input) => {
      if (!input) return;
      input.disabled = !!locked;
      input.classList.toggle("is-locked", !!locked);
      if (locked) input.title = STAMP_LOCK_MSG;
      else input.removeAttribute("title");
    });
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
    const mer = h24 < 12 ? "오전" : "오후";
    let h12 = h24 % 12;
    if (h12 === 0) h12 = 12;
    const mi = String(d.getMinutes()).padStart(2, "0");
    return (
      '<span class="jcc-stamp-date">' +
      y2 +
      "-" +
      mm +
      "-" +
      dd +
      "</span> " +
      '<span class="jcc-stamp-time">' +
      mer +
      " " +
      h12 +
      ":" +
      mi +
      "</span>"
    );
  }

  function lodgingKeysFromData(data) {
    const eligible =
      !!data.expected_check_in_at && data.check_in_status !== "checked_out";
    let eligibleKey = eligible ? "eligible" : "ineligible";
    let assignmentKey = "";
    let scope = "na";
    if (eligible) {
      if (data.lodging_room) {
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
    const { eligibleKey, scope } = lodgingKeysFromData(data);
    if (data.lodging_room && data.lodging_room_label && eligibleKey === "eligible") {
      return escapeHtml(data.lodging_room_label);
    }
    if (eligibleKey === "eligible") {
      return '<span class="jcc-retreat-rosterUnassigned">미배정</span>';
    }
    if (data.check_in_status === "checked_out") {
      return '<span class="jcc-retreat-rosterIneligible">숙박 종료</span>';
    }
    return '<span class="jcc-retreat-rosterIneligible">숙박 없음</span>';
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

  function openEditForRow(tr) {
    modalAttendeeId = Number(tr.dataset.attendeeId);
    modalGroupId = Number(tr.dataset.groupId);
    modalGroupRegionId = Number(tr.dataset.groupRegionId) || null;
    modalGroupDivisionId = Number(tr.dataset.groupDivisionId) || null;
    const checkIn = tr.dataset.checkIn || "pending";
    modalInitialCheckIn = checkIn;

    if (titleEl) titleEl.textContent = "조원 수정";
    if (nameInput) nameInput.value = tr.dataset.name || "";
    if (phoneInput) phoneInput.value = phoneInputValue(tr.dataset.phone || "");
    if (genderInput) genderInput.value = tr.dataset.gender || "";
    if (memoInput) memoInput.value = tr.dataset.memo || "";
    if (expectedInInput)
      expectedInInput.value = toDatetimeLocalValue(tr.dataset.expectedInAt || "");
    if (expectedOutInput)
      expectedOutInput.value = toDatetimeLocalValue(tr.dataset.expectedOutAt || "");
    syncModalExpectedInputs(isExpectedTimestampsLocked(tr));
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
    requestAnimationFrame(() => nameInput?.focus());
  }

  function closeModal() {
    window.JccDateTimePicker?.close?.();
    overlay.hidden = true;
    overlay.setAttribute("aria-hidden", "true");
    modalAttendeeId = null;
  }

  function updateRowFromData(tr, data) {
    if (!tr || !data) return;
    const keys = lodgingKeysFromData(data);

    tr.dataset.checkIn = data.check_in_status || "pending";
    tr.dataset.checkInStatus = data.check_in_status || "pending";
    tr.dataset.gender = data.gender || "";
    tr.dataset.memo = data.memo || "";
    tr.dataset.memberRole = data.member_role || "member";
    tr.dataset.name = data.name || "";
    tr.dataset.phone = data.phone || "";
    tr.dataset.expectedInAt = data.expected_check_in_at || "";
    tr.dataset.expectedOutAt = data.expected_check_out_at || "";
    if ("expected_timestamps_locked" in data) {
      tr.dataset.expectedTimestampsLocked = data.expected_timestamps_locked
        ? "true"
        : "false";
    }
    tr.dataset.lodgingRoom = data.lodging_room ? String(data.lodging_room) : "";
    tr.dataset.lodgingScope = keys.scope;
    tr.dataset.lodgingEligible = keys.eligibleKey;
    tr.dataset.lodgingAssignment = keys.assignmentKey;
    tr.classList.toggle(
      "jcc-retreat-rosterRow--unassigned",
      keys.scope === "unassigned"
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
    if (!submitBtn || !modalAttendeeId) return;
    submitBtn.disabled = true;

    const newCheckIn = checkInInput?.value || modalInitialCheckIn;
    const payload = {};

    if (ctx.canChangeStatus && checkInInput) {
      payload.check_in_status = newCheckIn;
    }
    payload.name = (nameInput?.value || "").trim();
    payload.gender = genderInput?.value || "";
    payload.phone = phoneSubmitValue(phoneInput?.value || "");
    payload.memo = (memoInput?.value || "").trim();
    payload.member_role = roleInput?.value || "member";
    payload.user = attendeePicker?.getId() ? Number(attendeePicker.getId()) : null;
    const timestampsLocked = expectedInInput?.disabled;
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
    if (!timestampsLocked && inVal && outVal && new Date(outVal) <= new Date(inVal)) {
      submitBtn.disabled = false;
      showToast("퇴실 시각은 입실 시각보다 뒤여야 합니다.", true);
      return;
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
