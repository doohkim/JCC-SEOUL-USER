/**
 * 조 관리(출석부 분리) — 입퇴실 토글·시각 표시/수정·조원 CRUD
 */
(function () {
  "use strict";

  const ctx = window.RETREAT_CTX;
  if (!ctx) return;

  const CHECK_IN_OPTIONS = [
    { code: "pending", label: "입실전" },
    { code: "checked_in", label: "입실" },
    { code: "checked_out", label: "퇴실" },
  ];

  const CHECK_IN_LABELS = {
    pending: "입실전",
    checked_in: "입실",
    checked_out: "퇴실",
  };

  const PARTICIPATION_LABELS = { participating: "참석", absent: "불참" };

  const STATUS_LABELS = { present: "참석", absent: "결석" };

  const GENDER_LABELS = { male: "남성", female: "여성", "": "-" };

  const STAMP_LOCK_MSG =
    "자동 퇴실 처리된 조원은 입·퇴실 시각을 수정할 수 없습니다.";

  function isExpectedTimestampsLocked(source) {
    if (!source) return false;
    if (source instanceof HTMLElement) {
      return source.dataset.expectedTimestampsLocked === "true";
    }
    return !!source.expected_timestamps_locked;
  }

  function syncRowExpectedInputs(tr) {
    if (!tr) return;
    const locked = isExpectedTimestampsLocked(tr);
    tr.querySelectorAll("[data-expected-field]").forEach((input) => {
      input.disabled = locked;
      input.classList.toggle("is-locked", locked);
      if (locked) input.title = STAMP_LOCK_MSG;
      else input.removeAttribute("title");
    });
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

  function formatPhoneDisplay(phone) {
    if (window.JccPhoneFormat) return JccPhoneFormat.formatDisplay(phone);
    const s = String(phone ?? "").trim();
    return s || "-";
  }

  function phoneInputValue(phone) {
    if (!phone || phone === "-") return "";
    if (window.JccPhoneFormat) return JccPhoneFormat.formatMobilePhone(phone);
    return phone;
  }

  function phoneSubmitValue(raw) {
    if (window.JccPhoneFormat) return JccPhoneFormat.normalizeForSubmit(raw);
    return String(raw ?? "").trim();
  }

  const toastEl = document.getElementById("retreatToast");
  const statusLineEl = document.getElementById("retreatStatus");
  const attBody = document.getElementById("retreatAttBody");
  const addBtn = document.getElementById("btnAddAttendee");
  const summaryEls = {
    total: document.querySelector("[data-summary-total]"),
    participating: document.querySelector("[data-summary-participating]"),
    absent: document.querySelector("[data-summary-absent]"),
    pending: document.querySelector("[data-summary-pending]"),
    in: document.querySelector("[data-summary-in]"),
    out: document.querySelector("[data-summary-out]"),
  };

  const overlay = document.getElementById("retreatModalOverlay");
  const form = document.getElementById("retreatAttendeeForm");
  const nameInput = document.getElementById("retreatAttName");
  const genderInput = document.getElementById("retreatAttGender");
  const phoneInput = document.getElementById("retreatAttPhone");
  const memoInput = document.getElementById("retreatAttMemo");
  const expectedInInput = document.getElementById("retreatAttExpectedIn");
  const expectedOutInput = document.getElementById("retreatAttExpectedOut");
  const lodgingInput = document.getElementById("retreatAttLodging");
  const roleInput = document.getElementById("retreatAttRole");
  const checkInInput = document.getElementById("retreatAttCheckIn");
  const participationInput = document.getElementById("retreatAttParticipation");
  const titleEl = document.getElementById("retreatModalTitle");
  const submitBtn = document.getElementById("retreatModalSubmit");
  const cancelBtn = document.getElementById("retreatModalCancel");

  const confirmOverlay = document.getElementById("retreatConfirmOverlay");
  const confirmTitleEl = document.getElementById("retreatConfirmTitle");
  const confirmMsgEl = document.getElementById("retreatConfirmMsg");
  const confirmOkBtn = document.getElementById("retreatConfirmOk");
  const confirmCancelBtn = document.getElementById("retreatConfirmCancel");
  let confirmResolve = null;

  const historyOverlay = document.getElementById("retreatHistoryOverlay");
  const historySubjectEl = document.getElementById("retreatHistorySubject");
  const historyCloseBtn = document.getElementById("retreatHistoryClose");
  const historyTabBtns = historyOverlay
    ? historyOverlay.querySelectorAll("[data-history-tab]")
    : [];
  const historyPanelCheckIn = document.getElementById(
    "retreatHistoryPanelCheckIn"
  );
  const historyPanelAttendance = document.getElementById(
    "retreatHistoryPanelAttendance"
  );

  let modalMode = "create";
  let modalAttendeeId = null;
  let modalInitialCheckIn = "pending";
  let attendeePicker = null;

  function recomputeSummary() {
    if (!attBody) return;
    let pending = 0;
    let inCount = 0;
    let outCount = 0;
    let roster = 0;
    let participating = 0;
    let absent = 0;
    attBody.querySelectorAll("tr[data-attendee-id]").forEach((tr) => {
      roster += 1;
      const part = tr.dataset.participation || "participating";
      if (part === "absent") {
        absent += 1;
        return;
      }
      participating += 1;
      const s = tr.dataset.checkIn || "pending";
      if (s === "checked_in") inCount += 1;
      else if (s === "checked_out") outCount += 1;
      else pending += 1;
    });
    if (summaryEls.total) summaryEls.total.textContent = String(roster);
    if (summaryEls.participating)
      summaryEls.participating.textContent = String(participating);
    if (summaryEls.absent) summaryEls.absent.textContent = String(absent);
    if (summaryEls.pending) summaryEls.pending.textContent = String(pending);
    if (summaryEls.in) summaryEls.in.textContent = String(inCount);
    if (summaryEls.out) summaryEls.out.textContent = String(outCount);
  }

  function syncParticipationRow(tr) {
    if (!tr) return;
    const isAbsent = (tr.dataset.participation || "participating") === "absent";
    tr.classList.toggle("is-absent", isAbsent);
    tr.querySelectorAll("[data-expected-field]").forEach((input) => {
      const locked = isExpectedTimestampsLocked(tr);
      input.disabled = isAbsent || locked;
      input.classList.toggle("is-locked", isAbsent || locked);
    });
  }

  function init() {
    renderStatusBadges();
    if (attBody) {
      attBody
        .querySelectorAll("tr[data-attendee-id]")
        .forEach((tr) => {
          syncRowExpectedInputs(tr);
          syncParticipationRow(tr);
        });
    }
    recomputeSummary();
    bindConfirm();
    bindHistory();
    bindSorting();
    if (ctx.canEditAttendee) {
      bindExpectedInputs();
      bindAttendeeMutators();
      bindModal();
    }
  }

  function formatStamp(iso) {
    if (!iso) return "-";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "-";
    const yy = String(d.getFullYear() % 100).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    const h24 = d.getHours();
    const mi = String(d.getMinutes()).padStart(2, "0");
    return `${yy}-${mm}-${dd} ${String(h24).padStart(2, "0")}:${mi}`;
  }

  // 입실/퇴실 라벨용: PC(4자리 연도·한 줄) / 모바일(2자리 연도·두 줄)을 CSS 로
  // 전환할 수 있도록 구조화된 마크업을 반환한다.
  function formatStampHtml(iso) {
    if (!iso) return "-";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "-";
    const y4 = String(d.getFullYear());
    const y2 = String(d.getFullYear() % 100).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    const h24 = d.getHours();
    const mi = String(d.getMinutes()).padStart(2, "0");
    const time = `${String(h24).padStart(2, "0")}:${mi}`;
    return (
      '<span class="jcc-stamp-date">' +
      '<span class="jcc-stamp-y4">' +
      y4 +
      "</span>" +
      '<span class="jcc-stamp-y2">' +
      y2 +
      "</span>" +
      "-" +
      mm +
      "-" +
      dd +
      "</span>" +
      " " +
      '<span class="jcc-stamp-time">' +
      time +
      "</span>"
    );
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

  const STAMP_ORDER_MSG = "퇴실 시각은 입실 시각보다 뒤여야 합니다.";

  // 입실·퇴실 둘 다 있을 때만 검사: 퇴실은 입실보다 무조건 커야 한다(같거나 작으면 오류).
  function isCheckOutAfterCheckIn(inVal, outVal) {
    if (!inVal || !outVal) return true;
    const ti = new Date(inVal).getTime();
    const to = new Date(outVal).getTime();
    if (Number.isNaN(ti) || Number.isNaN(to)) return true;
    return to > ti;
  }

  // datetime-local 은 커스텀 피커 버튼(.jcc-dtp-field)이 실제로 보이므로 거기에도 표시한다.
  function markStampInvalid(input, invalid) {
    if (!input) return;
    input.classList.toggle("is-invalid", !!invalid);
    const field = input.nextElementSibling;
    if (field && field.classList.contains("jcc-dtp-field")) {
      field.classList.toggle("is-invalid", !!invalid);
    }
  }

  function setFieldError(input, message) {
    if (!input) return;
    const field = input.closest(".field");
    if (!field) return;
    let hint = field.querySelector(".jcc-field-error");
    if (message) {
      if (!hint) {
        hint = document.createElement("small");
        hint.className = "jcc-field-error";
        field.appendChild(hint);
      }
      hint.textContent = message;
    } else if (hint) {
      hint.remove();
    }
  }

  function showToast(message, isError) {
    if (!toastEl) {
      if (statusLineEl) statusLineEl.textContent = message || "";
      return;
    }
    toastEl.textContent = message || "";
    toastEl.hidden = false;
    toastEl.classList.toggle("is-error", !!isError);
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => {
      toastEl.hidden = true;
    }, 2200);
  }

  function updateStatusBadge(tr) {
    if (!tr) return;
    const badge = tr.querySelector("[data-status-badge]");
    if (!badge) return;
    const current = tr.dataset.checkIn || "pending";
    badge.textContent = CHECK_IN_LABELS[current] || current;
    badge.className = `jcc-retreat-checkInBadge jcc-retreat-checkInBadge--${current}`;
  }

  function renderStatusBadges() {
    if (!attBody) return;
    attBody.querySelectorAll("tr[data-attendee-id]").forEach(updateStatusBadge);
  }

  function syncCheckInSelectOptions(current) {
    if (!checkInInput) return;
    // 회장단·슈퍼유저(canChangeStatus)는 입실 상태를 자유롭게 수정·정정할 수 있다.
    // 서버 전환 규칙(assert_check_in_status_transition)도 이들에게는 되돌리기를 허용한다.
    const canEditFreely = !!ctx.canChangeStatus;
    Array.from(checkInInput.options).forEach((opt) => {
      opt.disabled = false;
      if (canEditFreely) return;
      if (current === "checked_in" && opt.value === "pending") opt.disabled = true;
      if (
        current === "checked_out" &&
        (opt.value === "pending" || opt.value === "checked_in")
      ) {
        opt.disabled = true;
      }
    });
  }

  function updateRowFromData(tr, data) {
    if (!tr || !data) return;
    if (data.participation_status) {
      tr.dataset.participation = data.participation_status;
      syncParticipationRow(tr);
    }
    tr.dataset.checkIn = data.check_in_status || "pending";
    if (data.checked_in_at) {
      tr.dataset.checkedInAt = data.checked_in_at;
    }
    if (data.checked_out_at) {
      tr.dataset.checkedOutAt = data.checked_out_at;
    }
    tr.dataset.expectedInAt = data.expected_check_in_at || "";
    tr.dataset.expectedOutAt = data.expected_check_out_at || "";
    if ("expected_timestamps_locked" in data) {
      tr.dataset.expectedTimestampsLocked = data.expected_timestamps_locked
        ? "true"
        : "false";
    }

    if (data.member_role) {
      tr.dataset.memberRole = data.member_role;
      const roleTag = tr.querySelector(".jcc-retreat-attCol-role [data-role-tag]");
      if (roleTag) {
        if (data.member_role_display)
          roleTag.textContent = data.member_role_display;
        roleTag.className = `jcc-retreat-roleTag jcc-retreat-roleTag--${data.member_role}`;
      }
    }
    if ("user" in data) {
      tr.dataset.userId = data.user ? String(data.user) : "";
      tr.dataset.userLabel = data.user_label || "";
      const userCell = tr.querySelector("[data-user-cell]");
      if (userCell) {
        userCell.innerHTML = data.user
          ? '<span class="jcc-retreat-roleTag jcc-retreat-roleTag--linked">연동</span>'
          : '<span class="muted">미연동</span>';
      }
    }

    if ("lodging_room" in data) {
      tr.dataset.lodgingRoom = data.lodging_room ? String(data.lodging_room) : "";
      tr.dataset.lodgingLabel = data.lodging_room_label || "";
      const lodgingCell = tr.querySelector("[data-lodging-cell]");
      if (lodgingCell) {
        lodgingCell.innerHTML = data.lodging_room_label
          ? escapeHtml(data.lodging_room_label)
          : '<span class="muted">-</span>';
      }
    }

    const nameEl = tr.querySelector("[data-name]");
    if (nameEl && data.name) nameEl.textContent = data.name;

    const genderEl = tr.querySelector("[data-gender-cell]");
    if (genderEl) {
      genderEl.textContent =
        data.gender_display || GENDER_LABELS[data.gender || ""] || "-";
    }
    tr.dataset.gender = data.gender || "";

    const phoneEl = tr.querySelector("[data-phone]");
    if (phoneEl) phoneEl.textContent = data.phone ? formatPhoneDisplay(data.phone) : "-";

    const memoEl = tr.querySelector("[data-memo]");
    if (memoEl) {
      memoEl.textContent = data.memo || "";
      memoEl.hidden = !data.memo;
    }

    if ("expected_check_in_at" in data || "expected_check_out_at" in data) {
      const inInput = tr.querySelector('[data-expected-field="expected_check_in_at"]');
      const outInput = tr.querySelector('[data-expected-field="expected_check_out_at"]');
      if (inInput) inInput.value = toDatetimeLocalValue(data.expected_check_in_at);
      if (outInput) outInput.value = toDatetimeLocalValue(data.expected_check_out_at);
      const inLabel = tr.querySelector("[data-expected-in-label]");
      const outLabel = tr.querySelector("[data-expected-out-label]");
      if (inLabel) {
        if (data.expected_check_in_at) {
          inLabel.innerHTML = formatStampHtml(data.expected_check_in_at);
        } else {
          inLabel.textContent = "-";
        }
        inLabel.classList.toggle("muted", !data.expected_check_in_at);
      }
      if (outLabel) {
        if (data.expected_check_out_at) {
          outLabel.innerHTML = formatStampHtml(data.expected_check_out_at);
        } else {
          outLabel.textContent = "-";
        }
        outLabel.classList.toggle("muted", !data.expected_check_out_at);
      }
    }

    syncRowExpectedInputs(tr);
    updateStatusBadge(tr);
    recomputeSummary();
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
      let detail = "저장에 실패했습니다.";
      try {
        const j = await res.json();
        if (j.detail) detail = j.detail;
        else if (Array.isArray(j.expected_check_out_at)) detail = j.expected_check_out_at[0];
        else if (Array.isArray(j.lodging_room)) detail = j.lodging_room[0];
        else if (typeof j.lodging_room === "string") detail = j.lodging_room;
        else detail = JSON.stringify(j);
      } catch (e) {}
      throw new Error(detail);
    }
    return res.json();
  }

  function setRowStampError(tr, invalid) {
    if (!tr) return;
    const inInput = tr.querySelector('[data-expected-field="expected_check_in_at"]');
    const outInput = tr.querySelector('[data-expected-field="expected_check_out_at"]');
    markStampInvalid(inInput, invalid);
    markStampInvalid(outInput, invalid);
    const outCell = outInput
      ? outInput.closest("[data-expected-cell]")
      : null;
    if (outCell) {
      let hint = outCell.querySelector(".jcc-retreat-stampError");
      if (invalid) {
        if (!hint) {
          hint = document.createElement("small");
          hint.className = "jcc-retreat-stampError";
          outCell.appendChild(hint);
        }
        hint.textContent = "퇴실은 입실보다 뒤여야 함";
      } else if (hint) {
        hint.remove();
      }
    }
  }

  function bindExpectedInputs() {
    if (!attBody) return;
    attBody.addEventListener("change", async (e) => {
      const input = e.target.closest("[data-expected-field]");
      if (!input) return;
      const tr = input.closest("tr[data-attendee-id]");
      if (!tr) return;
      if (isExpectedTimestampsLocked(tr)) return;
      const field = input.dataset.expectedField;
      if (!field) return;
      const aid = Number(tr.dataset.attendeeId);

      const inInput = tr.querySelector('[data-expected-field="expected_check_in_at"]');
      const outInput = tr.querySelector('[data-expected-field="expected_check_out_at"]');
      if (!isCheckOutAfterCheckIn(inInput?.value || "", outInput?.value || "")) {
        setRowStampError(tr, true);
        showToast(STAMP_ORDER_MSG, true);
        return;
      }
      setRowStampError(tr, false);

      const iso = isoFromDatetimeLocal(input.value);
      input.disabled = true;
      try {
        const data = await patchAttendee(aid, { [field]: iso });
        updateRowFromData(tr, data);
        showToast("예상 시각 저장됨", false);
      } catch (err) {
        showToast(err.message || "저장 실패", true);
      } finally {
        syncRowExpectedInputs(tr);
      }
    });
  }

  // --- 컬럼 헤더 클릭 정렬 -------------------------------------------------
  const ROLE_ORDER = { leader: 0, vice_leader: 1, member: 2 };
  const STATUS_ORDER = { checked_in: 0, pending: 1, checked_out: 2 };
  let sortKey = null;
  let sortDir = "asc";

  function sortValue(tr, key) {
    switch (key) {
      case "role":
        return ROLE_ORDER[tr.dataset.memberRole] ?? 99;
      case "status":
        return STATUS_ORDER[tr.dataset.checkIn] ?? 99;
      case "gender": {
        const g = tr.dataset.gender || "";
        return g === "male" ? 0 : g === "female" ? 1 : 2;
      }
      case "name":
        return (tr.querySelector("[data-name]")?.textContent || "").trim();
      case "phone":
        return (tr.querySelector("[data-phone]")?.textContent || "").trim();
      case "expected_in":
      case "expected_out": {
        const iso =
          key === "expected_in"
            ? tr.dataset.expectedInAt
            : tr.dataset.expectedOutAt;
        if (!iso) return Number.POSITIVE_INFINITY;
        const t = new Date(iso).getTime();
        return Number.isNaN(t) ? Number.POSITIVE_INFINITY : t;
      }
      default:
        return 0;
    }
  }

  function compareRows(a, b, key) {
    const va = sortValue(a, key);
    const vb = sortValue(b, key);
    if (typeof va === "number" && typeof vb === "number") {
      return va - vb;
    }
    return String(va).localeCompare(String(vb), "ko");
  }

  function renumberRows() {
    if (!attBody) return;
    let n = 0;
    attBody.querySelectorAll("tr[data-attendee-id]").forEach((tr) => {
      n += 1;
      const numCell = tr.querySelector("[data-row-num]");
      if (numCell) numCell.textContent = String(n);
    });
  }

  function applySort() {
    if (!attBody || !sortKey) return;
    const rows = Array.from(attBody.querySelectorAll("tr[data-attendee-id]"));
    const factor = sortDir === "desc" ? -1 : 1;
    rows
      .sort((a, b) => {
        const c = compareRows(a, b, sortKey);
        if (c !== 0) return c * factor;
        // 동률이면 이름으로 안정 정렬.
        const na = (a.querySelector("[data-name]")?.textContent || "").trim();
        const nb = (b.querySelector("[data-name]")?.textContent || "").trim();
        return na.localeCompare(nb, "ko");
      })
      .forEach((tr) => attBody.appendChild(tr));
    renumberRows();
  }

  function bindSorting() {
    const headers = document.querySelectorAll(".jcc-retreat-sortable[data-sort-key]");
    if (!headers.length) return;
    headers.forEach((th) => {
      th.addEventListener("click", () => {
        const key = th.dataset.sortKey;
        if (sortKey === key) {
          sortDir = sortDir === "asc" ? "desc" : "asc";
        } else {
          sortKey = key;
          sortDir = "asc";
        }
        headers.forEach((h) => {
          if (h === th) {
            h.dataset.sortDir = sortDir;
            h.setAttribute(
              "aria-sort",
              sortDir === "asc" ? "ascending" : "descending"
            );
          } else {
            delete h.dataset.sortDir;
            h.setAttribute("aria-sort", "none");
          }
        });
        applySort();
      });
    });
  }

  function bindModal() {
    if (!overlay) return;
    attendeePicker = createUserPicker(
      form ? form.querySelector("[data-user-picker]") : null
    );
    if (addBtn)
      addBtn.addEventListener("click", () =>
        openModal("create", { checkIn: "pending" })
      );
    if (cancelBtn) cancelBtn.addEventListener("click", closeModal);
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) closeModal();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !overlay.hidden) closeModal();
    });
    if (form) form.addEventListener("submit", onSubmit);
    if (phoneInput && window.JccPhoneFormat) JccPhoneFormat.bindInput(phoneInput);
    if (genderInput) {
      genderInput.addEventListener("change", () => {
        refreshLodgingOptions(lodgingInput?.value || "");
      });
    }
  }

  function openEditForRow(tr) {
    if (!tr) return;
    const aid = Number(tr.dataset.attendeeId);
    const name = tr.querySelector("[data-name]")?.textContent?.trim() || "";
    const phone = tr.querySelector("[data-phone]")?.textContent?.trim() || "";
    const memoEl = tr.querySelector("[data-memo]");
    const memo = memoEl && !memoEl.hidden ? memoEl.textContent.trim() : "";
    openModal("edit", {
      id: aid,
      name,
      phone,
      memo,
      checkIn: tr.dataset.checkIn || "pending",
      participation: tr.dataset.participation || "participating",
      gender: tr.dataset.gender || "",
      expectedIn: tr.dataset.expectedInAt || "",
      expectedOut: tr.dataset.expectedOutAt || "",
      expectedTimestampsLocked: tr.dataset.expectedTimestampsLocked === "true",
      memberRole: tr.dataset.memberRole || "member",
      userId: tr.dataset.userId || "",
      userLabel: tr.dataset.userLabel || "",
      lodgingRoom: tr.dataset.lodgingRoom || "",
      checkedInAt: tr.dataset.checkedInAt || "",
      checkedOutAt: tr.dataset.checkedOutAt || "",
    });
  }

  function bindAttendeeMutators() {
    if (!attBody) return;
    attBody.addEventListener("click", (e) => {
      const tr = e.target.closest("tr[data-attendee-id]");
      if (!tr) return;
      const aid = Number(tr.dataset.attendeeId);

      const del = e.target.closest("[data-del]");
      if (del) {
        if (ctx.canDeleteAttendee) confirmDelete(aid);
        return;
      }
      // 이력 버튼은 별도 핸들러(bindHistory)에서 처리
      if (e.target.closest("[data-history]")) return;

      if (e.target.closest("[data-edit]")) {
        openEditForRow(tr);
        return;
      }
      // 이름·구분 셀을 클릭했을 때만 수정 모달 열기 (다른 셀/입력은 제외)
      const trigger = e.target.closest(
        "td.jcc-retreat-attCol-name, td.jcc-retreat-attCol-role"
      );
      if (trigger) openEditForRow(tr);
    });
  }

  function bindConfirm() {
    if (!confirmOverlay) return;
    if (confirmCancelBtn)
      confirmCancelBtn.addEventListener("click", () => resolveConfirm(false));
    if (confirmOkBtn)
      confirmOkBtn.addEventListener("click", () => resolveConfirm(true));
    confirmOverlay.addEventListener("click", (e) => {
      if (e.target === confirmOverlay) resolveConfirm(false);
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !confirmOverlay.hidden) resolveConfirm(false);
    });
  }

  function openConfirm({ title, message, okLabel, cancelLabel }) {
    if (!confirmOverlay) return Promise.resolve(window.confirm(message || ""));
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

  function bindHistory() {
    if (!historyOverlay || !attBody) return;
    attBody.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-history]");
      if (!btn) return;
      const tr = e.target.closest("tr[data-attendee-id]");
      if (!tr) return;
      const aid = Number(tr.dataset.attendeeId);
      const name = tr.querySelector("[data-name]")?.textContent?.trim() || "";
      openHistory(aid, name);
    });
    if (historyCloseBtn)
      historyCloseBtn.addEventListener("click", closeHistory);
    historyOverlay.addEventListener("click", (e) => {
      if (e.target === historyOverlay) closeHistory();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !historyOverlay.hidden) closeHistory();
    });
    historyTabBtns.forEach((btn) => {
      btn.addEventListener("click", () => switchHistoryTab(btn.dataset.historyTab));
    });
  }

  function switchHistoryTab(tab) {
    historyTabBtns.forEach((btn) =>
      btn.classList.toggle("is-active", btn.dataset.historyTab === tab)
    );
    if (historyPanelCheckIn)
      historyPanelCheckIn.hidden = tab !== "check_in";
    if (historyPanelAttendance)
      historyPanelAttendance.hidden = tab !== "attendance";
  }

  async function openHistory(attendeeId, displayName) {
    if (!historyOverlay) return;
    historyOverlay.hidden = false;
    historyOverlay.setAttribute("aria-hidden", "false");
    if (historySubjectEl)
      historySubjectEl.textContent = displayName ? `${displayName} 님` : "";
    if (historyPanelCheckIn)
      historyPanelCheckIn.innerHTML =
        '<div class="jcc-retreat-historyLoading">불러오는 중…</div>';
    if (historyPanelAttendance)
      historyPanelAttendance.innerHTML =
        '<div class="jcc-retreat-historyLoading">불러오는 중…</div>';
    switchHistoryTab("check_in");
    try {
      const url = (
        ctx.urls.attendeeHistoryTemplate || ""
      ).replace("__id__", String(attendeeId));
      const res = await fetch(url, { credentials: "same-origin" });
      if (!res.ok) throw new Error("이력을 불러올 수 없습니다.");
      const data = await res.json();
      renderCheckInHistory(data.check_in_history || []);
      renderAttendanceHistory(data.attendance_history || []);
    } catch (err) {
      const msg = err.message || "이력 조회 실패";
      if (historyPanelCheckIn)
        historyPanelCheckIn.innerHTML = `<div class="jcc-retreat-historyEmpty is-error">${escapeHtml(msg)}</div>`;
      if (historyPanelAttendance)
        historyPanelAttendance.innerHTML = `<div class="jcc-retreat-historyEmpty is-error">${escapeHtml(msg)}</div>`;
    }
  }

  function closeHistory() {
    if (!historyOverlay) return;
    historyOverlay.hidden = true;
    historyOverlay.setAttribute("aria-hidden", "true");
  }

  function renderCheckInHistory(entries) {
    if (!historyPanelCheckIn) return;
    if (!entries.length) {
      historyPanelCheckIn.innerHTML =
        '<div class="jcc-retreat-historyEmpty">입·퇴실 변경 이력이 없습니다.</div>';
      return;
    }
    const items = entries
      .map((e) => {
        const when = formatStamp(e.changed_at) || "";
        const actor = e.actor ? `· ${escapeHtml(e.actor)}` : "";
        let badge = "";
        if (e.action === "create") badge = "추가";
        else if (e.action === "delete") badge = "삭제";
        else badge = "변경";
        return `
          <li class="jcc-retreat-historyItem">
            <div class="jcc-retreat-historyMeta">
              <span class="jcc-retreat-historyBadge jcc-retreat-historyBadge--${e.action}">${badge}</span>
              <span class="jcc-retreat-historyWhen">${escapeHtml(when)}</span>
              <span class="jcc-retreat-historyActor">${actor}</span>
            </div>
            <div class="jcc-retreat-historySummary">${escapeHtml(e.summary || "")}</div>
          </li>`;
      })
      .join("");
    historyPanelCheckIn.innerHTML = `<ul class="jcc-retreat-historyList">${items}</ul>`;
  }

  function renderAttendanceHistory(sessions) {
    if (!historyPanelAttendance) return;
    if (!sessions.length) {
      historyPanelAttendance.innerHTML =
        '<div class="jcc-retreat-historyEmpty">세션별 출석 기록이 없습니다.</div>';
      return;
    }
    const blocks = sessions
      .map((s) => {
        const occursAt = formatStamp(s.occurs_at) || "";
        const cur = s.current_status
          ? `<span class="jcc-retreat-historyChip jcc-retreat-historyChip--${s.current_status}">${escapeHtml(
              s.current_status_label || STATUS_LABELS[s.current_status] || "-"
            )}</span>`
          : '<span class="jcc-retreat-historyChip jcc-retreat-historyChip--none">기록 없음</span>';
        const closed = s.session_status === "closed" ? " · 마감" : "";
        const entries = (s.entries || [])
          .map((e) => {
            const when = formatStamp(e.changed_at) || "";
            const actor = e.actor ? `· ${escapeHtml(e.actor)}` : "";
            let badge = "";
            if (e.action === "create") badge = e.auto_default ? "자동" : "기록";
            else badge = "변경";
            return `
              <li class="jcc-retreat-historyItem">
                <div class="jcc-retreat-historyMeta">
                  <span class="jcc-retreat-historyBadge jcc-retreat-historyBadge--${e.action}">${badge}</span>
                  <span class="jcc-retreat-historyWhen">${escapeHtml(when)}</span>
                  <span class="jcc-retreat-historyActor">${actor}</span>
                </div>
                <div class="jcc-retreat-historySummary">${escapeHtml(e.summary || "")}</div>
              </li>`;
          })
          .join("");
        const list = entries
          ? `<ul class="jcc-retreat-historyList">${entries}</ul>`
          : '<div class="jcc-retreat-historyEmpty muted">변경 기록 없음 (스냅샷 시점 기록)</div>';
        return `
          <section class="jcc-retreat-historySession">
            <header class="jcc-retreat-historySessionHead">
              <div class="jcc-retreat-historySessionTitle">${escapeHtml(s.session_name || "")}<small>${escapeHtml(occursAt + closed)}</small></div>
              <div class="jcc-retreat-historySessionStatus">현재: ${cur}</div>
            </header>
            ${list}
          </section>`;
      })
      .join("");
    historyPanelAttendance.innerHTML = blocks;
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function refreshLodgingOptions(selectedId) {
    if (!lodgingInput || !window.JccLodgingAssignOptions) return;
    const gender = genderInput?.value || "";
    window.JccLodgingAssignOptions.applyToSelect(
      lodgingInput,
      ctx.eventRooms || [],
      { gender, selectedId: selectedId || "", refreshRoot: overlay }
    );
  }

  function openModal(mode, payload) {
    if (!overlay) return;
    modalMode = mode;
    modalAttendeeId = payload?.id || null;
    const checkIn = payload?.checkIn || "pending";
    modalInitialCheckIn = checkIn;
    if (titleEl) {
      if (mode === "edit") {
        titleEl.textContent = ctx.canEditAttendee ? "조원 수정" : "입·퇴실 변경";
      } else {
        titleEl.textContent = "조원 추가";
      }
    }
    if (submitBtn) {
      submitBtn.textContent = mode === "edit" ? "수정" : "저장";
      submitBtn.disabled = false;
    }
    if (nameInput) nameInput.value = payload?.name || "";
    if (phoneInput) phoneInput.value = phoneInputValue(payload?.phone);
    if (genderInput) genderInput.value = payload?.gender || "";
    if (memoInput) memoInput.value = payload?.memo || "";
    if (expectedInInput)
      expectedInInput.value = toDatetimeLocalValue(payload?.expectedIn || "");
    if (expectedOutInput)
      expectedOutInput.value = toDatetimeLocalValue(payload?.expectedOut || "");
    markStampInvalid(expectedInInput, false);
    markStampInvalid(expectedOutInput, false);
    setFieldError(expectedOutInput, "");
    const timestampsLocked =
      isExpectedTimestampsLocked(payload) ||
      (modalAttendeeId &&
        isExpectedTimestampsLocked(
          attBody?.querySelector(`tr[data-attendee-id="${modalAttendeeId}"]`)
        ));
    syncModalExpectedInputs(timestampsLocked);
    refreshLodgingOptions(payload?.lodgingRoom || "");
    if (roleInput) roleInput.value = payload?.memberRole || "member";
    if (checkInInput) {
      checkInInput.value = checkIn;
      syncCheckInSelectOptions(checkIn);
    }
    if (participationInput) {
      participationInput.value = payload?.participation || "participating";
    }
    if (attendeePicker) {
      if (payload?.userId) {
        attendeePicker.setSelected(payload.userId, payload.userLabel || "");
      } else {
        attendeePicker.clear();
      }
    }
    const showProfileFields = ctx.canEditAttendee;
    form
      ?.querySelectorAll("[data-modal-profile-field]")
      .forEach((el) => {
        el.hidden = !showProfileFields;
      });
    overlay.hidden = false;
    overlay.setAttribute("aria-hidden", "false");
    const focusEl =
      showProfileFields && mode === "create" ? nameInput : checkInInput || nameInput;
    requestAnimationFrame(() => focusEl?.focus());
  }

  function closeDateTimePicker() {
    window.JccDateTimePicker?.close?.();
  }

  function closeModal() {
    if (!overlay) return;
    closeDateTimePicker();
    overlay.hidden = true;
    overlay.setAttribute("aria-hidden", "true");
    modalAttendeeId = null;
  }

  async function onSubmit(e) {
    e.preventDefault();
    closeDateTimePicker();
    if (!submitBtn) return;
    submitBtn.disabled = true;
    const linkedUserId = attendeePicker ? attendeePicker.getId() : "";
    const newCheckIn = checkInInput?.value || modalInitialCheckIn;
    const payload = {};

    if (ctx.canChangeStatus && checkInInput) {
      payload.check_in_status = newCheckIn;
    }
    const includeProfile = ctx.canEditAttendee;
    if (includeProfile) {
      payload.name = (nameInput?.value || "").trim();
      payload.gender = genderInput?.value || "";
      payload.phone = phoneSubmitValue(phoneInput?.value || "");
    }
    if (ctx.canEditAttendee) {
      payload.participation_status =
        participationInput?.value || "participating";
      payload.memo = (memoInput?.value || "").trim();
      payload.member_role = roleInput?.value || "member";
      payload.user = linkedUserId ? Number(linkedUserId) : null;
      const timestampsLocked =
        modalMode === "edit" &&
        (isExpectedTimestampsLocked({
          expected_timestamps_locked:
            attBody
              ?.querySelector(`tr[data-attendee-id="${modalAttendeeId}"]`)
              ?.dataset.expectedTimestampsLocked === "true",
        }) ||
          expectedInInput?.disabled);
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
    }
    if (includeProfile && !payload.name) {
      submitBtn.disabled = false;
      showToast("실명은 필수입니다.", true);
      nameInput?.focus();
      return;
    }
    if (includeProfile && modalMode === "create" && !payload.gender) {
      submitBtn.disabled = false;
      showToast("성별은 필수입니다.", true);
      genderInput?.focus();
      return;
    }
    if (ctx.canEditAttendee) {
      markStampInvalid(expectedInInput, false);
      markStampInvalid(expectedOutInput, false);
      setFieldError(expectedOutInput, "");
      const timestampsLocked =
        modalMode === "edit" &&
        (isExpectedTimestampsLocked({
          expected_timestamps_locked:
            attBody
              ?.querySelector(`tr[data-attendee-id="${modalAttendeeId}"]`)
              ?.dataset.expectedTimestampsLocked === "true",
        }) ||
          expectedInInput?.disabled);
      if (
        !timestampsLocked &&
        !isCheckOutAfterCheckIn(
          expectedInInput?.value || "",
          expectedOutInput?.value || ""
        )
      ) {
        submitBtn.disabled = false;
        markStampInvalid(expectedInInput, true);
        markStampInvalid(expectedOutInput, true);
        setFieldError(expectedOutInput, STAMP_ORDER_MSG);
        showToast(STAMP_ORDER_MSG, true);
        (expectedOutInput?.nextElementSibling || expectedOutInput)?.focus?.();
        return;
      }
    }
    if (!Object.keys(payload).length) {
      submitBtn.disabled = false;
      showToast("저장할 변경 사항이 없습니다.", true);
      return;
    }
    if (
      modalMode === "edit" &&
      ctx.canChangeStatus &&
      newCheckIn !== modalInitialCheckIn
    ) {
      const name =
        (nameInput?.value || "").trim() ||
        attBody
          ?.querySelector(`tr[data-attendee-id="${modalAttendeeId}"] [data-name]`)
          ?.textContent?.trim() ||
        "조원";
      const prevLabel = CHECK_IN_LABELS[modalInitialCheckIn] || modalInitialCheckIn;
      const nextLabel = CHECK_IN_LABELS[newCheckIn] || newCheckIn;
      const ok = await openConfirm({
        title: `${nextLabel} 처리`,
        message: `${name} 님\n${prevLabel} → ${nextLabel}\n\n이대로 변경할까요?`,
        okLabel: "확인",
        cancelLabel: "취소",
      });
      if (!ok) {
        submitBtn.disabled = false;
        return;
      }
    }
    try {
      let data;
      if (modalMode === "edit" && modalAttendeeId) {
        data = await patchAttendee(modalAttendeeId, payload);
        const tr = attBody?.querySelector(
          `tr[data-attendee-id="${modalAttendeeId}"]`
        );
        updateRowFromData(tr, data);
        showToast("수정됨", false);
        closeModal();
      } else {
        const res = await fetch(ctx.urls.attendeesList, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": ctx.csrfToken,
          },
          credentials: "same-origin",
          body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error("추가 실패");
        showToast("추가됨", false);
        window.location.reload();
      }
    } catch (err) {
      console.error("[retreat] 조원 저장 실패", err);
      showToast(err.message || "저장 실패", true);
    } finally {
      submitBtn.disabled = false;
    }
  }

  async function confirmDelete(attendeeId) {
    if (!window.confirm("조원을 삭제할까요? 과거 출석 기록은 보존됩니다.")) return;
    try {
      const res = await fetch(
        ctx.urls.attendeeDetailTemplate.replace("__id__", String(attendeeId)),
        {
          method: "DELETE",
          headers: { "X-CSRFToken": ctx.csrfToken },
          credentials: "same-origin",
        }
      );
      if (!res.ok && res.status !== 204) throw new Error("삭제 실패");
      showToast("삭제됨", false);
      window.location.reload();
    } catch (err) {
      showToast(err.message || "삭제 실패", true);
    }
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
    let lastQuery = "";

    function filterParams() {
      const params = new URLSearchParams();
      const ids = Array.isArray(ctx.groupDivisionIds) ? ctx.groupDivisionIds : [];
      if (ids.length) {
        ids.forEach((id) => params.append("division", String(id)));
      } else if (ctx.groupDivisionId) {
        params.set("division", String(ctx.groupDivisionId));
      } else if (ctx.groupRegionId) {
        params.set("region", String(ctx.groupRegionId));
      }
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
      lastQuery = q;
      const params = filterParams();
      if (q) params.set("q", q);
      params.set("limit", "30");
      const url = `${ctx.urls.userSearchUrl}?${params.toString()}`;
      const r = await fetch(url, { credentials: "same-origin" });
      if (!r.ok || q !== lastQuery) return;
      items = await r.json();
      activeIdx = items.length ? 0 : -1;
      renderList();
    }

    input.addEventListener("input", () => {
      selected = null;
      hidden.value = "";
      const q = input.value.trim();
      clearTimeout(timer);
      timer = setTimeout(() => search(q), 180);
    });

    // 포커스 시 같은 지역·부서 계정 목록을 바로 보여준다(글씨 없이도).
    input.addEventListener("focus", () => {
      if (!input.value.trim()) search("");
    });

    list.addEventListener("mousedown", (e) => {
      const li = e.target.closest("li[data-idx]");
      if (!li) return;
      e.preventDefault();
      const u = items[Number(li.dataset.idx)];
      if (!u) return;
      selected = u;
      hidden.value = String(u.id);
      input.value = u.name || u.display_name || u.username;
      list.hidden = true;
    });

    document.addEventListener("click", (e) => {
      if (!root.contains(e.target)) list.hidden = true;
    });

    return {
      clear,
      setSelected,
      getSelected: () => selected,
      getId: () => hidden.value || "",
    };
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
