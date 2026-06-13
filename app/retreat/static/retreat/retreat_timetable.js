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
  const dayEl = document.getElementById("ttDay");
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

  function openModal(mode, data) {
    if (!overlay) return;
    data = data || {};
    const isEdit = mode === "edit";
    titleEl.textContent = isEdit ? "일정 수정" : "일정 추가";
    idEl.value = isEdit ? data.id || "" : "";

    if (data.day) {
      dayEl.value = data.day;
      // 행사 일자 범위 밖이면 첫 옵션으로
      if (dayEl.value !== data.day && dayEl.options.length) {
        dayEl.selectedIndex = 0;
      }
    } else if (dayEl.options.length) {
      dayEl.selectedIndex = 0;
    }
    startEl.value = data.start || "";
    endEl.value = data.end || "";
    titleInput.value = data.title || "";
    locationEl.value = data.location || "";
    descEl.value = data.description || "";
    if (window.JccCustomSelect) window.JccCustomSelect.refresh(document);

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
    return {
      day: dayEl.value,
      start_time: startEl.value || null,
      end_time: endEl.value || null,
      title: titleInput.value.trim(),
      location: locationEl.value.trim(),
      description: descEl.value.trim(),
    };
  }

  async function save() {
    const body = gatherBody();
    if (!body.day || !body.start_time || !body.title) {
      showStatus("날짜·시작 시각·프로그램명은 필수입니다.", true);
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
