/**
 * 수련회 조 상세 페이지 JS
 * - 출석 토글: 낙관적 업데이트(클릭 즉시 UI 반영, 실패 시 롤백 + 토스트)
 * - 조원 추가/수정/삭제: 모달
 */

(function () {
  "use strict";

  const ctx = window.RETREAT_CTX;
  if (!ctx) return;

  const STATUSES = [
    { code: "present", label: "참석" },
    { code: "absent", label: "결석" },
  ];

  const CHECK_IN_LABELS = {
    checked_in: "입실",
    checked_out: "퇴실",
    pending: "입실전",
  };
  const UNAVAILABLE_CHECK_IN_STATUSES = new Set(["checked_out", "pending"]);

  /** {sessionId: {attendeeId: status}} */
  let matrix = {};
  let enrollmentMatrix = {};
  let missingMatrix = {};
  let enrollmentCheckInMatrix = {};
  /** 현재 선택된 세션 id (number) */
  let activeSessionId = null;
  let activeSessionClosed = false;

  const toastEl = document.getElementById("retreatToast");
  const statusLineEl = document.getElementById("retreatStatus");
  const addHintEl = document.getElementById("retreatAddHint");
  const attBody = document.getElementById("retreatAttBody");
  const sessionBar = document.querySelector(".jcc-retreat-sessionBar");
  const addBtn = document.getElementById("btnAddAttendee");

  function init() {
    matrix = parseInitialMatrix();
    enrollmentMatrix = parseNestedJson("retreatEnrollmentMatrix");
    missingMatrix = parseNestedJson("retreatMissingMatrix");
    enrollmentCheckInMatrix = parseNestedJson("retreatEnrollmentCheckInMatrix");
    const firstTab =
      document.querySelector(".jcc-retreat-sessionTab.is-active") ||
      document.querySelector(".jcc-retreat-sessionTab");
    if (firstTab) {
      activeSessionId = Number(firstTab.dataset.sessionId) || null;
      activeSessionClosed = firstTab.dataset.sessionStatus === "closed";
    }
    bindSessionTabs();
    renderAllRows();
    syncAddButtonForActiveSession();
    if (ctx.canMutate || ctx.canManageSessions) {
      bindAttendeeMutators();
      bindModal();
    }
  }

  function syncAddButtonForActiveSession() {
    if (!addBtn) return;
    if (activeSessionClosed) {
      if (ctx.canManageSessions) {
        addBtn.disabled = false;
        addBtn.removeAttribute("aria-disabled");
        addBtn.title = "";
        if (addHintEl) {
          addHintEl.hidden = false;
          addHintEl.textContent =
            "이 출석부에만 추가되며 다른 출석부·현재 조 명단에는 영향이 없습니다.";
        }
      } else {
        addBtn.disabled = true;
        addBtn.setAttribute("aria-disabled", "true");
        addBtn.title =
          "마감된 출석부에는 추가할 수 없어요. 진행중 탭을 선택하세요.";
        if (addHintEl) {
          addHintEl.hidden = false;
          addHintEl.textContent = addBtn.title;
        }
      }
      return;
    }
    if (addHintEl) addHintEl.hidden = true;
    if (ctx.canMutate) {
      addBtn.disabled = false;
      addBtn.removeAttribute("aria-disabled");
      addBtn.title = "";
    } else {
      addBtn.disabled = true;
      addBtn.setAttribute("aria-disabled", "true");
      addBtn.title = "조원 추가는 조장·운영진만 가능합니다.";
    }
  }

  function parseNestedJson(id) {
    const el = document.getElementById(id);
    if (!el) return {};
    try {
      return JSON.parse(el.textContent || "{}");
    } catch (e) {
      return {};
    }
  }

  function parseInitialMatrix() {
    // {attendeeId: {sessionId: status}} 형태로 들어온 걸 그대로 사용.
    const el = document.getElementById("retreatInitialMatrix");
    if (!el) return {};
    try {
      const raw = JSON.parse(el.textContent || "{}");
      const out = {};
      Object.keys(raw).forEach((aid) => {
        out[aid] = {};
        const inner = raw[aid] || {};
        Object.keys(inner).forEach((sid) => {
          out[aid][sid] = inner[sid];
        });
      });
      return out;
    } catch (e) {
      return {};
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
    clearTimeout(toastEl._t);
    toastEl._t = setTimeout(() => {
      toastEl.hidden = true;
    }, 2200);
  }

  function bindSessionTabs() {
    if (!sessionBar) return;
    sessionBar.addEventListener("click", (e) => {
      const tab = e.target.closest(".jcc-retreat-sessionTab");
      if (!tab) return;
      const sid = Number(tab.dataset.sessionId);
      if (!sid || sid === activeSessionId) return;
      activeSessionId = sid;
      activeSessionClosed = tab.dataset.sessionStatus === "closed";
      sessionBar.querySelectorAll(".jcc-retreat-sessionTab").forEach((el) => {
        const isActive = Number(el.dataset.sessionId) === sid;
        el.classList.toggle("is-active", isActive);
        el.setAttribute("aria-selected", isActive ? "true" : "false");
      });
      renderAllRows();
      syncAddButtonForActiveSession();
    });
  }

  function renderAllRows() {
    if (!attBody) return;
    const sidKey = String(activeSessionId || "");
    attBody.querySelectorAll("tr[data-attendee-id]").forEach((tr) => {
      const aid = Number(tr.dataset.attendeeId);
      const aidKey = String(aid);
      const snapshotSessionAttr = tr.dataset.snapshotSessionId;
      if (snapshotSessionAttr) {
        const ownSessionId = Number(snapshotSessionAttr);
        const visible = ownSessionId === activeSessionId;
        tr.hidden = !visible;
        if (!visible) return;
      } else {
        // 마감 출석부 탭에서는 그 시점에 등록되지 않았던 조원 행을 숨긴다.
        const isMissing =
          missingMatrix[aidKey] && missingMatrix[aidKey][sidKey];
        if (activeSessionClosed && isMissing) {
          tr.hidden = true;
          return;
        }
        tr.hidden = false;
      }
      renderRowStatus(tr, aid);
    });
  }

  function renderRowStatus(tr, attendeeId) {
    const groupEl = tr.querySelector(".jcc-retreat-statusGroup");
    if (!groupEl) return;
    const aidKey = String(attendeeId);
    const sidKey = String(activeSessionId || "");
    const isMissing =
      missingMatrix[aidKey] && missingMatrix[aidKey][sidKey];
    if (isMissing) {
      groupEl.innerHTML = '<span class="muted">—</span>';
      return;
    }
    let currentStatus =
      (matrix[aidKey] && matrix[aidKey][sidKey]) || "";
    const snapshotCheckIn =
      (enrollmentCheckInMatrix[aidKey] && enrollmentCheckInMatrix[aidKey][sidKey]) ||
      tr.dataset.checkIn ||
      "pending";
    const isUnavailable = UNAVAILABLE_CHECK_IN_STATUSES.has(snapshotCheckIn);
    if (isUnavailable) currentStatus = "absent";

    groupEl.innerHTML = "";
    STATUSES.forEach((s) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "jcc-retreat-statusBtn";
      btn.dataset.status = s.code;
      btn.dataset.attendeeId = String(attendeeId);
      btn.textContent = s.label;
      if (currentStatus === s.code) btn.classList.add("is-active");
      if (!ctx.canMutate || activeSessionClosed) btn.disabled = true;
      // 입실전·퇴실 조원은 '참석'을 누를 수 없음.
      if (isUnavailable && s.code === "present") {
        btn.disabled = true;
        btn.title = "입실전·퇴실 상태인 조원은 참석으로 변경할 수 없습니다.";
      }
      groupEl.appendChild(btn);
    });
  }

  if (ctx.canMutate && attBody) {
    attBody.addEventListener("click", async (e) => {
      const btn = e.target.closest(".jcc-retreat-statusBtn");
      if (!btn || btn.disabled) return;
      const aid = Number(btn.dataset.attendeeId);
      const newStatus = btn.dataset.status;
      const sid = activeSessionId;
      if (!aid || !sid) return;
      await applyStatusOptimistic(aid, sid, newStatus, btn);
    });
  }

  async function applyStatusOptimistic(attendeeId, sessionId, newStatus, clickedBtn) {
    const aidKey = String(attendeeId);
    const sidKey = String(sessionId);
    const prev = (matrix[aidKey] && matrix[aidKey][sidKey]) || "";
    const enrollmentId =
      enrollmentMatrix[aidKey] && enrollmentMatrix[aidKey][sidKey];
    if (!enrollmentId) {
      showToast("이 출석부에는 포함되지 않은 조원입니다.", true);
      return;
    }

    // 낙관적: 즉시 UI 반영
    matrix[aidKey] = matrix[aidKey] || {};
    matrix[aidKey][sidKey] = newStatus;
    const tr = clickedBtn.closest("tr[data-attendee-id]");
    if (tr) renderRowStatus(tr, attendeeId);
    setRowPending(tr, true);

    try {
      const res = await fetch(ctx.urls.bulkUpsert, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": ctx.csrfToken,
        },
        credentials: "same-origin",
        body: JSON.stringify({
          session_id: sessionId,
          rows: [{ enrollment_id: enrollmentId, status: newStatus }],
        }),
      });
      if (!res.ok) {
        let detail = "출석 저장에 실패했습니다.";
        try {
          const j = await res.json();
          detail = j.detail || JSON.stringify(j);
        } catch (e) {}
        throw new Error(detail);
      }
      showToast("저장됨", false);
    } catch (err) {
      // 롤백
      if (prev) matrix[aidKey][sidKey] = prev;
      else delete matrix[aidKey][sidKey];
      if (tr) renderRowStatus(tr, attendeeId);
      showToast(err.message || "저장 실패", true);
    } finally {
      setRowPending(tr, false);
    }
  }

  function setRowPending(tr, pending) {
    if (!tr) return;
    tr.querySelectorAll(".jcc-retreat-statusBtn").forEach((b) => {
      b.classList.toggle("is-pending", !!pending);
      b.disabled = !!pending;
    });
  }

  /* ---------------- 조원 CRUD 모달 ---------------- */

  let modalMode = "create"; // "create" | "edit"
  let modalAttendeeId = null;
  let modalEnrollmentId = null;
  let modalSnapshotRow = false;
  const overlay = document.getElementById("retreatModalOverlay");
  const form = document.getElementById("retreatAttendeeForm");
  const nameInput = document.getElementById("retreatAttName");
  const genderInput = document.getElementById("retreatAttGender");
  const phoneInput = document.getElementById("retreatAttPhone");
  const memoInput = document.getElementById("retreatAttMemo");
  const checkInInput = document.getElementById("retreatAttCheckIn");
  const GENDER_LABELS = { male: "남성", female: "여성", "": "-" };
  const titleEl = document.getElementById("retreatModalTitle");
  const submitBtn = document.getElementById("retreatModalSubmit");
  const cancelBtn = document.getElementById("retreatModalCancel");
  function bindModal() {
    if (!overlay) return;
    if (addBtn) {
      addBtn.addEventListener("click", () => {
        if (activeSessionClosed && !ctx.canManageSessions) return;
        if (!activeSessionClosed && !ctx.canMutate) return;
        openModal("create", { checkIn: "pending" });
      });
    }
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
      const isSnapshot = tr.dataset.rowSnapshot === "1";
      const aid = Number(tr.dataset.attendeeId);
      const enrollmentId = Number(tr.dataset.enrollmentId) || null;
      if (edit) {
        const nameEl = tr.querySelector("[data-name]");
        // 이름 텍스트만 (배지 제외).
        const name = nameEl ? nameEl.childNodes[0]?.nodeValue?.trim() || "" : "";
        const phone = tr.querySelector("[data-phone]")?.textContent?.trim() || "";
        const memoEl = tr.querySelector("[data-memo]");
        const memo = memoEl && !memoEl.hidden ? memoEl.textContent.trim() : "";
        const checkIn = tr.dataset.checkIn || "pending";
        const gender = tr.dataset.gender || "";
        openModal("edit", {
          id: isSnapshot ? enrollmentId : aid,
          name,
          phone,
          memo,
          checkIn,
          gender,
          isSnapshot,
        });
      } else if (del) {
        confirmDelete(isSnapshot ? enrollmentId : aid, tr, isSnapshot);
      }
    });
  }

  function openModal(mode, payload) {
    if (!overlay) return;
    modalMode = mode;
    modalSnapshotRow = !!payload?.isSnapshot;
    modalEnrollmentId = modalSnapshotRow ? payload?.id || null : null;
    modalAttendeeId = modalSnapshotRow ? null : payload?.id || null;
    if (titleEl) {
      titleEl.textContent = mode === "edit" ? "조원 수정" : "조원 추가";
    }
    if (submitBtn) submitBtn.textContent = mode === "edit" ? "수정" : "저장";
    if (nameInput) nameInput.value = payload?.name || "";
    if (phoneInput) phoneInput.value = payload?.phone === "-" ? "" : payload?.phone || "";
    if (genderInput) genderInput.value = payload?.gender || "";
    if (memoInput) memoInput.value = payload?.memo || "";
    if (checkInInput) checkInInput.value = payload?.checkIn || "pending";
    overlay.hidden = false;
    overlay.setAttribute("aria-hidden", "false");
    requestAnimationFrame(() => nameInput?.focus());
  }

  function closeModal() {
    if (!overlay) return;
    overlay.hidden = true;
    overlay.setAttribute("aria-hidden", "true");
    modalAttendeeId = null;
    modalEnrollmentId = null;
    modalSnapshotRow = false;
  }

  async function onSubmit(e) {
    e.preventDefault();
    if (!submitBtn) return;
    submitBtn.disabled = true;
    const payload = {
      name: (nameInput?.value || "").trim(),
      gender: genderInput?.value || "",
      phone: (phoneInput?.value || "").trim(),
      memo: (memoInput?.value || "").trim(),
      check_in_status: checkInInput?.value || "pending",
    };
    if (!payload.name) {
      submitBtn.disabled = false;
      showToast("이름은 필수입니다.", true);
      return;
    }
    try {
      let res;
      if (modalMode === "edit" && modalSnapshotRow && modalEnrollmentId) {
        res = await fetch(
          ctx.urls.snapshotAttendeeDetailTemplate.replace(
            "__id__",
            String(modalEnrollmentId)
          ),
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json", "X-CSRFToken": ctx.csrfToken },
            credentials: "same-origin",
            body: JSON.stringify(payload),
          }
        );
      } else if (modalMode === "edit" && modalAttendeeId) {
        res = await fetch(
          ctx.urls.attendeeDetailTemplate.replace("__id__", String(modalAttendeeId)),
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json", "X-CSRFToken": ctx.csrfToken },
            credentials: "same-origin",
            body: JSON.stringify(payload),
          }
        );
      } else if (activeSessionClosed && ctx.canManageSessions) {
        const url = ctx.urls.snapshotAttendeesAdd.replace(
          "__sid__",
          String(activeSessionId)
        );
        res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": ctx.csrfToken },
          credentials: "same-origin",
          body: JSON.stringify(payload),
        });
      } else {
        res = await fetch(ctx.urls.attendeesList, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": ctx.csrfToken },
          credentials: "same-origin",
          body: JSON.stringify(payload),
        });
      }
      if (!res.ok) {
        let detail = "저장에 실패했습니다.";
        try {
          const j = await res.json();
          detail = j.detail || j.name?.[0] || JSON.stringify(j);
        } catch (e) {}
        throw new Error(detail);
      }
      const data = await res.json();
      if (modalMode === "edit" && !modalSnapshotRow) {
        updateRowInPlace(modalAttendeeId, data);
        showToast("수정됨", false);
      } else if (modalMode === "edit" && modalSnapshotRow) {
        showToast("수정됨", false);
        window.location.reload();
        return;
      } else {
        showToast("추가됨", false);
        window.location.reload();
        return;
      }
      closeModal();
    } catch (err) {
      showToast(err.message || "저장 실패", true);
    } finally {
      submitBtn.disabled = false;
    }
  }

  function updateRowInPlace(attendeeId, data) {
    const tr = attBody?.querySelector(
      `tr[data-attendee-id="${attendeeId}"]`
    );
    if (!tr) return;
    const nameEl = tr.querySelector("[data-name]");
    const phoneEl = tr.querySelector("[data-phone]");
    const memoEl = tr.querySelector("[data-memo]");
    if (nameEl) {
      const badge = nameEl.querySelector("[data-check-in-badge]");
      nameEl.textContent = data.name || "";
      if (badge) {
        nameEl.appendChild(document.createTextNode(" "));
        nameEl.appendChild(badge);
      } else if (data.check_in_status) {
        const newBadge = makeCheckInBadge(data.check_in_status);
        nameEl.appendChild(document.createTextNode(" "));
        nameEl.appendChild(newBadge);
      }
    }
    if (phoneEl) phoneEl.textContent = data.phone ? data.phone : "-";
    const genderEl = tr.querySelector("[data-gender-cell]");
    const genderCode = data.gender ?? tr.dataset.gender ?? "";
    if (genderEl) {
      genderEl.textContent =
        data.gender_display || GENDER_LABELS[genderCode] || "-";
    }
    if (data.gender !== undefined) {
      tr.dataset.gender = data.gender || "";
    }
    if (memoEl) {
      memoEl.textContent = data.memo || "";
      memoEl.hidden = !data.memo;
    }
    if (data.check_in_status) {
      tr.dataset.checkIn = data.check_in_status;
      const badge = tr.querySelector("[data-check-in-badge]");
      if (badge) {
        badge.className = `jcc-retreat-checkInBadge jcc-retreat-checkInBadge--${data.check_in_status}`;
        badge.textContent = CHECK_IN_LABELS[data.check_in_status] || "";
      }
    }
  }

  function makeCheckInBadge(code) {
    const span = document.createElement("span");
    span.className = `jcc-retreat-checkInBadge jcc-retreat-checkInBadge--${code}`;
    span.dataset.checkInBadge = "";
    span.textContent = CHECK_IN_LABELS[code] || "";
    return span;
  }

  function appendNewRow(data) {
    if (!attBody) return;
    // 빈 placeholder 행 제거.
    const placeholder = attBody.querySelector("tr td[colspan]");
    if (placeholder) placeholder.closest("tr").remove();
    const tr = document.createElement("tr");
    tr.dataset.attendeeId = String(data.id);
    tr.dataset.checkIn = data.check_in_status || "pending";
    tr.dataset.gender = data.gender || "";
    tr.innerHTML = `
      <td class="jcc-retreat-attCol-name">
        <div class="jcc-retreat-attName" data-name></div>
        <div class="jcc-retreat-attMemo" data-memo></div>
      </td>
      <td class="jcc-retreat-attCol-gender" data-gender-cell></td>
      <td class="jcc-retreat-attCol-phone" data-phone></td>
      <td class="jcc-retreat-attCol-status">
        <div class="jcc-retreat-statusGroup" data-attendee-id="${data.id}" role="group"></div>
      </td>
      <td class="jcc-retreat-attCol-actions">
        <button type="button" class="jcc-retreat-rowEdit" data-edit>수정</button>
        <button type="button" class="jcc-retreat-rowDel" data-del>삭제</button>
      </td>
    `;
    attBody.appendChild(tr);
    updateRowInPlace(data.id, data);
    renderRowStatus(tr, data.id);
  }

  async function confirmDelete(rowId, tr, isSnapshot) {
    if (!rowId) return;
    const msg = isSnapshot
      ? "이 출석부 전용 조원을 삭제할까요? 다른 출석부에는 영향이 없습니다."
      : "조원을 삭제할까요? 과거 출석 기록은 그대로 보존됩니다.";
    if (!window.confirm(msg)) return;
    const url = isSnapshot
      ? ctx.urls.snapshotAttendeeDetailTemplate.replace("__id__", String(rowId))
      : ctx.urls.attendeeDetailTemplate.replace("__id__", String(rowId));
    try {
      const res = await fetch(url, {
        method: "DELETE",
        headers: { "X-CSRFToken": ctx.csrfToken },
        credentials: "same-origin",
      });
      if (!res.ok && res.status !== 204) {
        let detail = "삭제 실패";
        try {
          const j = await res.json();
          detail = j.detail || JSON.stringify(j);
        } catch (e) {}
        throw new Error(detail);
      }
      showToast("삭제됨", false);
      window.location.reload();
    } catch (err) {
      showToast(err.message || "삭제 실패", true);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
