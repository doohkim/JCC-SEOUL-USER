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

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function createUserPicker(root, searchUrl, extraParams) {
    if (!root || !searchUrl) return null;
    extraParams = extraParams || {};
    const input = root.querySelector("[data-user-picker-input]");
    const list = root.querySelector("[data-user-picker-list]");
    const hidden = root.querySelector("[data-user-picker-id]");
    if (!input || !list || !hidden) return null;

    let selected = null;
    let items = [];
    let timer = null;
    let lastQuery = "";

    function clear() {
      selected = null;
      hidden.value = "";
      input.value = "";
      closeList();
    }

    function closeList() {
      list.hidden = true;
      list.innerHTML = "";
    }

    function renderList() {
      if (!items.length) {
        list.innerHTML = '<li class="muted" role="option" aria-disabled="true">결과 없음</li>';
        list.hidden = false;
        return;
      }
      list.innerHTML = items
        .map((u, i) => {
          const shown = u.name || u.display_name || u.username;
          return `<li role="option" data-idx="${i}">${escapeHtml(shown)}</li>`;
        })
        .join("");
      list.hidden = false;
    }

    async function search(q) {
      lastQuery = q;
      try {
        const params = new URLSearchParams();
        if (q) {
          params.set("q", q);
          params.set("limit", "30");
        } else {
          // 검색어가 없으면 전체 계정 노출.
          params.set("all", "1");
          params.set("limit", "1000");
        }
        Object.keys(extraParams).forEach((k) => {
          if (extraParams[k]) params.set(k, extraParams[k]);
        });
        const r = await fetch(`${searchUrl}?${params.toString()}`, {
          credentials: "same-origin",
        });
        if (!r.ok) throw new Error(await r.text());
        if (q !== lastQuery) return;
        items = await r.json();
        renderList();
      } catch (err) {
        console.error(err);
      }
    }

    function pick(idx) {
      const u = items[idx];
      if (!u) return;
      selected = u;
      hidden.value = String(u.id);
      input.value = u.name || u.display_name || u.username;
      closeList();
    }

    input.addEventListener("input", () => {
      selected = null;
      hidden.value = "";
      const q = input.value.trim();
      clearTimeout(timer);
      timer = setTimeout(() => search(q), 180);
    });

    input.addEventListener("focus", () => {
      if (!input.value.trim()) search("");
    });

    list.addEventListener("mousedown", (e) => {
      const li = e.target.closest("li[data-idx]");
      if (!li) return;
      e.preventDefault();
      pick(Number(li.dataset.idx));
    });

    document.addEventListener("click", (e) => {
      if (!root.contains(e.target)) closeList();
    });

    return {
      clear,
      getSelected: () => selected,
      getTypedValue: () => input.value.trim(),
    };
  }

  const userPicker = createUserPicker(
    document.getElementById("councilUserPicker"),
    ctx.userSearchUrl,
    { signup_source: "kakao" }
  );

  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const selected = userPicker && userPicker.getSelected();
      const typed = userPicker
        ? userPicker.getTypedValue()
        : document.getElementById("newUsername").value.trim();
      const role = document.getElementById("newRole").value;
      const note = document.getElementById("newNote").value.trim();
      const body = { role, note };
      if (selected && selected.id) {
        body.user_id = selected.id;
      } else if (typed) {
        body.username = typed;
      } else {
        showStatus("사용자를 검색해서 선택하세요.", true);
        return;
      }
      try {
        const r = await fetch(ctx.apiList, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrf(),
          },
          body: JSON.stringify(body),
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
        if (window.JccCustomSelect)
          window.JccCustomSelect.refresh(sel.closest(".jcc-cselect") || sel.parentNode);
        showStatus("저장 실패", true);
        console.error(err);
      }
    });
  }
})();
