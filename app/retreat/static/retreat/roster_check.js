/**
 * 출석부 체크 (단일 세션) — 낙관적 upsert
 */
(function () {
  "use strict";
  const ctx = window.RETREAT_CTX;
  if (!ctx) return;

  const STATUSES = [
    { code: "present", label: "참석" },
    { code: "absent", label: "결석" },
  ];
  const UNAVAILABLE_CHECK_IN_STATUSES = new Set(["checked_out", "pending"]);

  let matrix = {};
  const sessionId = ctx.sessionId;
  const toastEl = document.getElementById("retreatToast");
  const statusLineEl = document.getElementById("retreatStatus");
  const attBody = document.getElementById("retreatAttBody");

  function init() {
    try {
      matrix = JSON.parse(
        document.getElementById("retreatInitialMatrix").textContent || "{}"
      );
    } catch (e) {
      matrix = {};
    }
    renderRows();
    if (ctx.canMutate) bindClicks();
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

  function csrf() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function renderRows() {
    if (!attBody) return;
    attBody.querySelectorAll("tr[data-attendee-id]").forEach((tr) => {
      const aid = Number(tr.dataset.attendeeId);
      const cell = tr.querySelector(".jcc-retreat-statusCell");
      if (!cell) return;
      cell.innerHTML = "";
      const isUnavailable = UNAVAILABLE_CHECK_IN_STATUSES.has(tr.dataset.checkIn);
      // 서버 매트릭스에 키가 없어도 화면은 기본 결석으로 표시한다.
      const current = isUnavailable
        ? "absent"
        : matrix[aid] || matrix[String(aid)] || "absent";
      STATUSES.forEach((st) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = `jcc-retreat-statusBtn jcc-retreat-status--${st.code}`;
        if (current === st.code) btn.classList.add("is-active");
        btn.textContent = st.label;
        btn.dataset.status = st.code;
        btn.dataset.attendeeId = String(aid);
        if (!ctx.canMutate) btn.disabled = true;
        // 입실전·퇴실 조원은 '참석'을 누를 수 없음.
        if (isUnavailable && st.code === "present") {
          btn.disabled = true;
          btn.title = "입실전·퇴실 상태인 조원은 참석으로 변경할 수 없습니다.";
        }
        cell.appendChild(btn);
      });
    });
  }

  function bindClicks() {
    if (!attBody) return;
    attBody.addEventListener("click", async (e) => {
      const btn = e.target.closest(".jcc-retreat-statusBtn");
      if (!btn || btn.disabled) return;
      const aid = Number(btn.dataset.attendeeId);
      const newStatus = btn.dataset.status;
      const prev = matrix[aid] || "";
      if (prev === newStatus) return;
      matrix[aid] = newStatus;
      renderRows();
      try {
        const r = await fetch(ctx.bulkUpsertUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrf(),
          },
          body: JSON.stringify({
            session_id: sessionId,
            rows: [{ enrollment_id: aid, status: newStatus }],
          }),
        });
        if (!r.ok) throw new Error(await r.text());
        showToast("저장됨");
      } catch (err) {
        matrix[aid] = prev;
        renderRows();
        showToast("저장 실패 — 되돌림", true);
        console.error(err);
      }
    });
  }

  init();
})();
