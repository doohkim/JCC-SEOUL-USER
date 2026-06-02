(function () {
  "use strict";
  const ctx = window.RETREAT_COUNCIL_CTX;
  if (!ctx || !ctx.canManage) return;

  const statusEl = document.getElementById("councilStatus");
  const tbody = document.getElementById("councilTbody");
  const form = document.getElementById("councilAddForm");

  function csrf() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function showStatus(msg, isError) {
    if (!statusEl) return;
    statusEl.textContent = msg || "";
    statusEl.style.color = isError ? "var(--err, #fda4af)" : "";
  }

  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const username = document.getElementById("newUsername").value.trim();
      const role = document.getElementById("newRole").value;
      const note = document.getElementById("newNote").value.trim();
      if (!username) return;
      try {
        const r = await fetch(ctx.apiList, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrf(),
          },
          body: JSON.stringify({ username, role, note }),
        });
        if (!r.ok) {
          const err = await r.json().catch(() => ({}));
          throw new Error(err.user || err.detail || "추가 실패");
        }
        window.location.reload();
      } catch (err) {
        showStatus(String(err.message || err), true);
      }
    });
  }

  if (tbody) {
    tbody.addEventListener("click", async (e) => {
      const btn = e.target.closest(".council-delete");
      if (!btn) return;
      const tr = btn.closest("tr[data-membership-id]");
      const mid = tr && tr.dataset.membershipId;
      if (!mid) return;
      if (!confirm("회장단에서 제거하시겠습니까?")) return;
      try {
        const r = await fetch(`${ctx.apiDetailBase}${mid}/`, {
          method: "DELETE",
          credentials: "same-origin",
          headers: { "X-CSRFToken": csrf() },
        });
        if (!r.ok) throw new Error(await r.text());
        tr.remove();
      } catch (err) {
        showStatus("삭제 실패", true);
        console.error(err);
      }
    });

    tbody.addEventListener("change", async (e) => {
      const sel = e.target.closest(".council-role-select");
      if (!sel) return;
      const tr = sel.closest("tr[data-membership-id]");
      const mid = tr && tr.dataset.membershipId;
      const role = sel.value;
      try {
        const r = await fetch(`${ctx.apiDetailBase}${mid}/`, {
          method: "PATCH",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrf(),
          },
          body: JSON.stringify({ role }),
        });
        if (!r.ok) throw new Error(await r.text());
        sel.dataset.prev = role;
        showStatus("저장됨");
      } catch (err) {
        sel.value = sel.dataset.prev;
        showStatus("저장 실패", true);
        console.error(err);
      }
    });
  }
})();
