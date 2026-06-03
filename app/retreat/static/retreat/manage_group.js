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

  const STATUS_LABELS = { present: "참석", absent: "결석" };

  const GENDER_LABELS = { male: "남성", female: "여성", "": "-" };

  const toastEl = document.getElementById("retreatToast");
  const statusLineEl = document.getElementById("retreatStatus");
  const attBody = document.getElementById("retreatAttBody");
  const addBtn = document.getElementById("btnAddAttendee");
  const summaryEls = {
    pending: document.querySelector("[data-summary-pending]"),
    in: document.querySelector("[data-summary-in]"),
    out: document.querySelector("[data-summary-out]"),
    total: document.querySelector("[data-summary-total]"),
  };

  const overlay = document.getElementById("retreatModalOverlay");
  const form = document.getElementById("retreatAttendeeForm");
  const nameInput = document.getElementById("retreatAttName");
  const genderInput = document.getElementById("retreatAttGender");
  const phoneInput = document.getElementById("retreatAttPhone");
  const memoInput = document.getElementById("retreatAttMemo");
  const expectedInInput = document.getElementById("retreatAttExpectedIn");
  const expectedOutInput = document.getElementById("retreatAttExpectedOut");
  const roleInput = document.getElementById("retreatAttRole");
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
  let attendeePicker = null;

  function recomputeSummary() {
    if (!attBody) return;
    let pending = 0;
    let inCount = 0;
    let outCount = 0;
    let total = 0;
    attBody.querySelectorAll("tr[data-attendee-id]").forEach((tr) => {
      total += 1;
      const s = tr.dataset.checkIn || "pending";
      if (s === "checked_in") inCount += 1;
      else if (s === "checked_out") outCount += 1;
      else pending += 1;
    });
    if (summaryEls.pending) summaryEls.pending.textContent = String(pending);
    if (summaryEls.in) summaryEls.in.textContent = String(inCount);
    if (summaryEls.out) summaryEls.out.textContent = String(outCount);
    if (summaryEls.total) summaryEls.total.textContent = String(total);
  }

  function init() {
    renderCheckInGroups();
    recomputeSummary();
    bindConfirm();
    bindHistory();
    if (ctx.canMutate) {
      bindCheckInClicks();
      bindLodgingSelects();
    }
    if (ctx.canEditAttendee) {
      bindAttendeeMutators();
      bindModal();
    }
  }

  function formatStamp(iso) {
    if (!iso) return "-";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "-";
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    const hh = String(d.getHours()).padStart(2, "0");
    const mi = String(d.getMinutes()).padStart(2, "0");
    return `${mm}/${dd} ${hh}:${mi}`;
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

  function renderCheckInGroups() {
    if (!attBody) return;
    attBody.querySelectorAll("tr[data-attendee-id]").forEach((tr) => {
      const groupEl = tr.querySelector("[data-check-in-group]");
      if (!groupEl) return;
      const current = tr.dataset.checkIn || "pending";
      groupEl.innerHTML = "";
      CHECK_IN_OPTIONS.forEach((opt) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "jcc-retreat-statusBtn jcc-retreat-checkInBtn";
        btn.dataset.checkInStatus = opt.code;
        btn.textContent = opt.label;
        if (current === opt.code) btn.classList.add("is-active");
        if (!ctx.canMutate) btn.disabled = true;
        if (current === "checked_in" && opt.code === "pending") btn.disabled = true;
        if (
          current === "checked_out" &&
          (opt.code === "pending" || opt.code === "checked_in")
        ) {
          btn.disabled = true;
        }
        groupEl.appendChild(btn);
      });
    });
  }

  function updateRowFromData(tr, data) {
    if (!tr || !data) return;
    tr.dataset.checkIn = data.check_in_status || "pending";
    if (data.checked_in_at) {
      tr.dataset.checkedInAt = data.checked_in_at;
    }
    if (data.checked_out_at) {
      tr.dataset.checkedOutAt = data.checked_out_at;
    }
    tr.dataset.expectedInAt = data.expected_check_in_at || "";
    tr.dataset.expectedOutAt = data.expected_check_out_at || "";

    if (data.member_role) {
      tr.dataset.memberRole = data.member_role;
      const roleCell = tr.querySelector(".jcc-retreat-attCol-role");
      if (roleCell && data.member_role_display)
        roleCell.textContent = data.member_role_display;
    }
    if ("user" in data) {
      tr.dataset.userId = data.user ? String(data.user) : "";
      tr.dataset.userLabel = data.user_label || "";
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
    if (phoneEl) phoneEl.textContent = data.phone ? data.phone : "-";

    const memoEl = tr.querySelector("[data-memo]");
    if (memoEl) {
      memoEl.textContent = data.memo || "";
      memoEl.hidden = !data.memo;
    }

    if (ctx.canEditTimestamps) {
      const inInput = tr.querySelector('[data-stamp-field="checked_in_at"]');
      const outInput = tr.querySelector('[data-stamp-field="checked_out_at"]');
      if (inInput) inInput.value = toDatetimeLocalValue(data.checked_in_at);
      if (outInput) outInput.value = toDatetimeLocalValue(data.checked_out_at);
    } else {
      const inDisp = tr.querySelector("[data-stamp-display-in]");
      const outDisp = tr.querySelector("[data-stamp-display-out]");
      if (inDisp) inDisp.textContent = formatStamp(data.checked_in_at);
      if (outDisp) outDisp.textContent = formatStamp(data.checked_out_at);
    }

    renderCheckInGroups();
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
        else if (Array.isArray(j.lodging_room)) detail = j.lodging_room[0];
        else if (typeof j.lodging_room === "string") detail = j.lodging_room;
        else detail = JSON.stringify(j);
      } catch (e) {}
      throw new Error(detail);
    }
    return res.json();
  }

  function bindCheckInClicks() {
    if (!attBody) return;
    attBody.addEventListener("click", async (e) => {
      const btn = e.target.closest(".jcc-retreat-checkInBtn");
      if (!btn || btn.disabled) return;
      const tr = btn.closest("tr[data-attendee-id]");
      if (!tr) return;
      const aid = Number(tr.dataset.attendeeId);
      const newStatus = btn.dataset.checkInStatus;
      const prev = tr.dataset.checkIn || "";
      if (prev === newStatus) return;

      const name = tr.querySelector("[data-name]")?.textContent?.trim() || "조원";
      const prevLabel = CHECK_IN_LABELS[prev] || prev || "-";
      const nextLabel = CHECK_IN_LABELS[newStatus] || newStatus;
      const ok = await openConfirm({
        title: `${nextLabel} 처리`,
        message: `${name} 님\n${prevLabel} → ${nextLabel}\n\n이대로 변경할까요?`,
        okLabel: "확인",
        cancelLabel: "취소",
      });
      if (!ok) return;

      try {
        const data = await patchAttendee(aid, { check_in_status: newStatus });
        updateRowFromData(tr, data);
        showToast("저장됨", false);
      } catch (err) {
        showToast(err.message || "저장 실패", true);
      }
    });
  }

  function bindStampInputs() {
    if (!ctx.canEditTimestamps || !attBody) return;
    attBody.addEventListener("change", async (e) => {
      const input = e.target.closest(".jcc-retreat-stampInput");
      if (!input) return;
      const tr = input.closest("tr[data-attendee-id]");
      if (!tr) return;
      const field = input.dataset.stampField;
      if (!field) return;
      const aid = Number(tr.dataset.attendeeId);
      const iso = isoFromDatetimeLocal(input.value);
      const payload = { [field]: iso };
      try {
        const data = await patchAttendee(aid, payload);
        updateRowFromData(tr, data);
        showToast("시각 저장됨", false);
      } catch (err) {
        showToast(err.message || "저장 실패", true);
      }
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
  }

  function bindAttendeeMutators() {
    if (!attBody) return;
    attBody.addEventListener("click", (e) => {
      const edit = e.target.closest("[data-edit]");
      const del = e.target.closest("[data-del]");
      const tr = e.target.closest("tr[data-attendee-id]");
      if (!tr) return;
      const aid = Number(tr.dataset.attendeeId);
      if (edit) {
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
          gender: tr.dataset.gender || "",
          expectedIn: tr.dataset.expectedInAt || "",
          expectedOut: tr.dataset.expectedOutAt || "",
          memberRole: tr.dataset.memberRole || "member",
          userId: tr.dataset.userId || "",
          userLabel: tr.dataset.userLabel || "",
        });
      } else if (del) {
        confirmDelete(aid);
      }
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

  function openModal(mode, payload) {
    if (!overlay) return;
    modalMode = mode;
    modalAttendeeId = payload?.id || null;
    if (titleEl) titleEl.textContent = mode === "edit" ? "조원 수정" : "조원 추가";
    if (submitBtn) submitBtn.textContent = mode === "edit" ? "수정" : "저장";
    if (nameInput) nameInput.value = payload?.name || "";
    if (phoneInput) phoneInput.value = payload?.phone === "-" ? "" : payload?.phone || "";
    if (genderInput) genderInput.value = payload?.gender || "";
    if (memoInput) memoInput.value = payload?.memo || "";
    if (expectedInInput)
      expectedInInput.value = toDatetimeLocalValue(payload?.expectedIn || "");
    if (expectedOutInput)
      expectedOutInput.value = toDatetimeLocalValue(payload?.expectedOut || "");
    if (roleInput) roleInput.value = payload?.memberRole || "member";
    if (attendeePicker) {
      if (payload?.userId) {
        attendeePicker.setSelected(payload.userId, payload.userLabel || "");
      } else {
        attendeePicker.clear();
      }
    }
    overlay.hidden = false;
    overlay.setAttribute("aria-hidden", "false");
    requestAnimationFrame(() => nameInput?.focus());
  }

  function closeModal() {
    if (!overlay) return;
    overlay.hidden = true;
    overlay.setAttribute("aria-hidden", "true");
    modalAttendeeId = null;
  }

  async function onSubmit(e) {
    e.preventDefault();
    if (!submitBtn) return;
    submitBtn.disabled = true;
    const linkedUserId = attendeePicker ? attendeePicker.getId() : "";
    const payload = {
      name: (nameInput?.value || "").trim(),
      gender: genderInput?.value || "",
      phone: (phoneInput?.value || "").trim(),
      memo: (memoInput?.value || "").trim(),
      expected_check_in_at: isoFromDatetimeLocal(expectedInInput?.value || ""),
      expected_check_out_at: isoFromDatetimeLocal(expectedOutInput?.value || ""),
      member_role: roleInput?.value || "member",
      user: linkedUserId ? Number(linkedUserId) : null,
    };
    if (!payload.name) {
      submitBtn.disabled = false;
      showToast("이름은 필수입니다.", true);
      return;
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

  function bindLodgingSelects() {
    if (!attBody) return;
    attBody.querySelectorAll("[data-lodging-select]").forEach((sel) => {
      sel.dataset.prevValue = sel.value || "";
      sel.addEventListener("change", async (e) => {
        const target = e.currentTarget;
        const tr = target.closest("tr[data-attendee-id]");
        if (!tr) return;
        const aid = Number(tr.dataset.attendeeId);
        const newVal = target.value || null;
        const prev = target.dataset.prevValue || "";
        target.disabled = true;
        try {
          const data = await patchAttendee(aid, { lodging_room: newVal });
          target.dataset.prevValue = data.lodging_room
            ? String(data.lodging_room)
            : "";
          const cell = tr.querySelector("[data-lodging-cell]");
          if (cell) {
            cell.dataset.lodgingRoom = data.lodging_room
              ? String(data.lodging_room)
              : "";
          }
          showToast(data.lodging_room ? "숙소 배정됨" : "숙소 해제됨", false);
        } catch (err) {
          target.value = prev;
          showToast(err.message || "배정 실패", true);
        } finally {
          target.disabled = false;
        }
      });
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
    let lastQuery = "";

    function filterParams() {
      const params = new URLSearchParams();
      if (ctx.groupDivisionId) params.set("division", String(ctx.groupDivisionId));
      else if (ctx.groupRegionId) params.set("region", String(ctx.groupRegionId));
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
