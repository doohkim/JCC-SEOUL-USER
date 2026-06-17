(function () {
  "use strict";
  const ctx = window.RETREAT_ROSTERS_CTX || {};

  document.querySelectorAll(".jcc-retreat-rosterSelect").forEach((sel) => {
    sel.addEventListener("change", () => {
      if (sel.value) window.location.href = sel.value;
    });
  });

  if (!ctx.canManage) return;

  const modal = document.getElementById("rosterModal");
  const form = document.getElementById("rosterForm");
  const btnNew = document.getElementById("btnNewRoster");
  const btnCancel = document.getElementById("rosterCancel");

  function csrf() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  if (btnNew && modal) {
    btnNew.addEventListener("click", () => modal.showModal());
  }
  if (btnCancel && modal) {
    btnCancel.addEventListener("click", () => modal.close());
  }

  // 마감 일시는 항상 입력 가능 (UX). 백엔드에서 status=active면 자동 무시,
  // status=closed인데 비워두면 저장 시각으로 자동 기록한다.
  const statusSel = document.getElementById("rosterStatus");
  const closedAtInput = document.getElementById("rosterClosedAt");

  document.addEventListener("click", async (e) => {
    const closeBtn = e.target.closest("[data-session-close]");
    const reopenBtn = e.target.closest("[data-session-reopen]");
    const btn = closeBtn || reopenBtn;
    if (!btn) return;
    const id = btn.dataset.sessionId;
    const template = closeBtn ? ctx.closeTemplate : ctx.reopenTemplate;
    if (!id || !template) return;
    const message = closeBtn
      ? "출석부를 마감할까요? 조장들에게는 더 이상 보이지 않습니다."
      : "출석부를 다시 진행중으로 바꿀까요?";
    if (!window.confirm(message)) return;
    btn.disabled = true;
    try {
      const r = await fetch(template.replace("__id__", id), {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRFToken": csrf() },
      });
      if (!r.ok) throw new Error(await r.text());
      window.location.reload();
    } catch (err) {
      alert("상태 변경 실패");
      console.error(err);
      btn.disabled = false;
    }
  });

  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = document.getElementById("rosterName").value.trim();
      const occursAt = document.getElementById("rosterOccursAt").value;
      const location = document.getElementById("rosterLocation").value.trim();
      const eventSel = document.getElementById("rosterEvent");
      const statusValue = statusSel ? statusSel.value : "";
      const closedAtValue = closedAtInput ? closedAtInput.value : "";

      const body = { name, location };
      if (occursAt) body.occurs_at = new Date(occursAt).toISOString();
      if (statusValue) body.status = statusValue;
      if (statusValue === "closed" && closedAtValue) {
        body.closed_at = new Date(closedAtValue).toISOString();
      }

      // 선택한 집회 기준으로 API URL을 동적 구성. fallback은 현재 집회.
      let url = ctx.apiSessions;
      if (eventSel && eventSel.value && ctx.apiSessionsTemplate) {
        url = ctx.apiSessionsTemplate.replace("__id__", eventSel.value);
      }

      try {
        const r = await fetch(url, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrf(),
          },
          body: JSON.stringify(body),
        });
        if (!r.ok) throw new Error(await r.text());
        window.location.reload();
      } catch (err) {
        alert("저장 실패");
        console.error(err);
      }
    });
  }
})();
