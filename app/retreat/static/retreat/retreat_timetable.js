(function () {
  "use strict";
  const ctx = window.RETREAT_TIMETABLE_CTX;
  if (!ctx) return;

  const statusEl = document.getElementById("timetableStatus");
  const list = document.getElementById("timetableList");
  const addBtn = document.getElementById("ttAddBtn");

  const overlay = document.getElementById("ttModalOverlay");
  const form = document.getElementById("ttForm");
  const titleEl = document.getElementById("ttModalTitle");
  const idEl = document.getElementById("ttId");
  const startEl = document.getElementById("ttStart");
  const endEl = document.getElementById("ttEnd");
  const titleInput = document.getElementById("ttTitle");
  const locationEl = document.getElementById("ttLocation");
  const descEl = document.getElementById("ttDesc");
  const deleteBtn = document.getElementById("ttDeleteBtn");
  const cancelBtn = document.getElementById("ttCancelBtn");

  function csrf() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function showStatus(msg, isError) {
    if (!statusEl) return;
    statusEl.textContent = msg || "";
    statusEl.style.color = isError ? "var(--err, #fda4af)" : "";
  }

  // "YYYY-MM-DD" + "HH:mm" → "YYYY-MM-DDTHH:mm" (커스텀 달력 피커 값 포맷)
  function joinDateTime(day, time) {
    if (!day || !time) return "";
    return `${day}T${time.slice(0, 5)}`;
  }

  // "YYYY-MM-DDTHH:mm" → { date: "YYYY-MM-DD", time: "HH:mm" }
  function splitDateTime(value) {
    const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(value || "");
    return m ? { date: m[1], time: m[2] } : { date: null, time: null };
  }

  function openModal(mode, data) {
    if (!overlay) return;
    data = data || {};
    const isEdit = mode === "edit";
    titleEl.textContent = isEdit ? "일정 수정" : "일정 추가";
    idEl.value = isEdit ? data.id || "" : "";

    // 시작/종료는 "날짜+시간" 달력 피커. 수정 시 day + 시각을 합쳐 채운다.
    startEl.value = joinDateTime(data.day, data.start);
    endEl.value = joinDateTime(data.end_day || data.day, data.end);
    titleInput.value = data.title || "";
    locationEl.value = data.location || "";
    descEl.value = data.description || "";

    deleteBtn.hidden = !isEdit;

    overlay.hidden = false;
    overlay.setAttribute("aria-hidden", "false");
    setTimeout(function () {
      titleInput.focus();
    }, 30);
  }

  function closeModal() {
    if (!overlay) return;
    overlay.hidden = true;
    overlay.setAttribute("aria-hidden", "true");
  }

  function gatherBody() {
    const start = splitDateTime(startEl.value);
    const end = splitDateTime(endEl.value);
    const body = {
      day: start.date,
      start_time: start.time,
      title: titleInput.value.trim(),
      location: locationEl.value.trim(),
      description: descEl.value.trim(),
    };
    if (end.date && end.time) {
      body.end_day = end.date;
      body.end_time = end.time;
    }
    return body;
  }

  async function save() {
    const body = gatherBody();
    if (!body.day || !body.start_time || !body.title) {
      showStatus("시작 일시·프로그램명은 필수입니다.", true);
      return;
    }
    const id = idEl.value;
    const url = id ? `${ctx.apiDetailBase}${id}/` : ctx.apiList;
    const method = id ? "PATCH" : "POST";
    try {
      const r = await fetch(url, {
        method: method,
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrf(),
        },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        const msg =
          err.end_time || err.title || err.start_time || err.day || err.detail;
        throw new Error(msg || "저장 실패");
      }
      window.location.reload();
    } catch (err) {
      showStatus(String(err.message || err), true);
    }
  }

  async function remove() {
    const id = idEl.value;
    if (!id) return;
    if (!confirm("이 일정을 삭제하시겠습니까?")) return;
    try {
      const r = await fetch(`${ctx.apiDetailBase}${id}/`, {
        method: "DELETE",
        credentials: "same-origin",
        headers: { "X-CSRFToken": csrf() },
      });
      if (!r.ok && r.status !== 204) throw new Error(await r.text());
      window.location.reload();
    } catch (err) {
      showStatus("삭제 실패", true);
      console.error(err);
    }
  }

  if (ctx.canManage && form) {
    if (addBtn) {
      addBtn.addEventListener("click", function () {
        openModal("add");
      });
    }
    if (list) {
      list.addEventListener("click", function (e) {
        const btn = e.target.closest("[data-tt-edit]");
        if (!btn) return;
        openModal("edit", {
          id: btn.dataset.id,
          day: btn.dataset.day,
          start: btn.dataset.start,
          end_day: btn.dataset.endDay || "",
          end: btn.dataset.end,
          title: btn.dataset.title,
          location: btn.dataset.location,
          description: btn.dataset.description,
        });
      });
    }
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      save();
    });
    if (cancelBtn) cancelBtn.addEventListener("click", closeModal);
    if (deleteBtn) deleteBtn.addEventListener("click", remove);
    if (overlay) {
      overlay.addEventListener("click", function (e) {
        if (e.target === overlay) closeModal();
      });
    }
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && overlay && !overlay.hidden) closeModal();
    });
  }
})();
