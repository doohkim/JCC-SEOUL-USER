/**
 * 수련회 관리 페이지 — 조 운영진(조장/부조장) 관리 모달.
 */
(function () {
  "use strict";

  const ctx = window.RETREAT_ADMIN_CTX || {};
  const overlay = document.getElementById("leaderModalOverlay");
  const tbody = document.getElementById("leaderModalTbody");
  const statusEl = document.getElementById("leaderModalStatus");
  const titleLabel = document.getElementById("leaderModalGroupLabel");
  const closeBtn = document.getElementById("leaderModalClose");
  const addForm = document.getElementById("leaderAddForm");
  const addUsername = document.getElementById("leaderAddUsername");
  const addRole = document.getElementById("leaderAddRole");
  const addSubmit = document.getElementById("leaderAddSubmit");
  const picker = addForm
    ? createUserPicker(addForm.querySelector("[data-user-picker]"))
    : null;

  let activeGroupId = null;
  let activeGroupLabel = "";
  let activeRow = null;

  function csrf() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function showStatus(msg, isError) {
    if (!statusEl) return;
    statusEl.textContent = msg || "";
    statusEl.style.color = isError ? "var(--err, #fda4af)" : "";
  }

  function openModal(groupId, label, row) {
    if (!overlay) return;
    activeGroupId = groupId;
    activeGroupLabel = label || "";
    activeRow = row || null;
    if (titleLabel) titleLabel.textContent = activeGroupLabel;
    overlay.hidden = false;
    overlay.setAttribute("aria-hidden", "false");
    if (picker) picker.clear();
    showStatus("");
    loadMemberships();
    requestAnimationFrame(() => addUsername && addUsername.focus());
  }

  function closeModal() {
    if (!overlay) return;
    overlay.hidden = true;
    overlay.setAttribute("aria-hidden", "true");
    activeGroupId = null;
    activeGroupLabel = "";
    activeRow = null;
  }

  async function loadMemberships() {
    if (!activeGroupId || !tbody) return;
    tbody.innerHTML = `<tr><td colspan="3" class="muted">불러오는 중…</td></tr>`;
    const url = ctx.groupMembershipsBase.replace("__gid__", String(activeGroupId));
    try {
      const res = await fetch(url, { credentials: "same-origin" });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      renderList(data);
      updateRowCell(data);
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="3" class="muted">목록을 불러오지 못했습니다.</td></tr>`;
      console.error(err);
    }
  }

  function renderList(items) {
    if (!tbody) return;
    if (!items || !items.length) {
      tbody.innerHTML = `<tr><td colspan="3" class="muted">등록된 운영진이 없습니다.</td></tr>`;
      return;
    }
    const rows = items
      .map((m) => {
        const roleOptions = Object.entries(ctx.roleLabels || {})
          .map(
            ([code, label]) =>
              `<option value="${escapeHtml(code)}"${
                code === m.role ? " selected" : ""
              }>${escapeHtml(label)}</option>`
          )
          .join("");
        const shown = m.name || m.display_name || m.username;
        const homeBadge =
          m.is_cross_group_leader && m.home_group_name
            ? ` <span class="jcc-retreat-pill jcc-retreat-pill--alt" title="소속 조">${escapeHtml(
                m.home_group_name
              )} 소속</span>`
            : "";
        return `
          <tr data-membership-id="${m.id}">
            <td>${escapeHtml(shown)}${homeBadge}</td>
            <td>
              <select class="leader-role-select" data-prev="${escapeHtml(m.role)}" data-cselect>
                ${roleOptions}
              </select>
            </td>
            <td>
              <button type="button" class="jcc-retreat-rowDel leader-delete">제거</button>
            </td>
          </tr>
        `;
      })
      .join("");
    tbody.innerHTML = rows;
    if (window.JccCustomSelect) window.JccCustomSelect.init(tbody);
  }

  function updateRowCell(items) {
    if (!activeRow) return;
    const cell = activeRow.querySelector("[data-leader-cell]");
    if (!cell) return;
    if (!items || !items.length) {
      cell.innerHTML = `<span class="jcc-retreat-empty">미지정</span>`;
      return;
    }
    cell.innerHTML = items
      .map((m) => {
        const home =
          m.is_cross_group_leader && m.home_group_name
            ? ` · ${m.home_group_name} 소속`
            : "";
        return `<span class="jcc-retreat-pill jcc-retreat-pill--alt">${escapeHtml(
          m.name || m.display_name || m.username
        )} · ${escapeHtml(m.role_display || m.role)}${escapeHtml(home)}</span>`;
      })
      .join(" ");
  }

  async function addMember(e) {
    e.preventDefault();
    if (!activeGroupId) return;
    const selected = picker && picker.getSelected();
    if (!selected || !selected.id) {
      showStatus("검색 결과에서 사용자를 선택하세요.", true);
      return;
    }
    const role = (addRole && addRole.value) || "leader";
    if (addSubmit) addSubmit.disabled = true;
    const url = ctx.groupMembershipsBase.replace("__gid__", String(activeGroupId));
    try {
      const res = await fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrf(),
        },
        body: JSON.stringify({ user_id: selected.id, role }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(body.user || body.detail || body.role || "추가 실패");
      }
      showStatus(body.message || "추가됨");
      if (picker) picker.clear();
      await loadMemberships();
    } catch (err) {
      showStatus(String(err.message || err), true);
    } finally {
      if (addSubmit) addSubmit.disabled = false;
    }
  }

  async function patchRole(membershipId, role, sel) {
    try {
      const res = await fetch(`${ctx.membershipDetailBase}${membershipId}/`, {
        method: "PATCH",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrf(),
        },
        body: JSON.stringify({ role }),
      });
      if (!res.ok) throw new Error(await res.text());
      if (sel) sel.dataset.prev = role;
      showStatus("저장됨");
      await loadMemberships();
    } catch (err) {
      if (sel) {
        sel.value = sel.dataset.prev || "leader";
        if (window.JccCustomSelect) window.JccCustomSelect.refresh(sel.closest(".jcc-cselect"));
      }
      showStatus("저장 실패", true);
      console.error(err);
    }
  }

  async function deleteMembership(membershipId) {
    if (!confirm("운영진에서 제거하시겠습니까?")) return;
    try {
      const res = await fetch(`${ctx.membershipDetailBase}${membershipId}/`, {
        method: "DELETE",
        credentials: "same-origin",
        headers: { "X-CSRFToken": csrf() },
      });
      if (!res.ok && res.status !== 204) throw new Error(await res.text());
      showStatus("제거됨");
      await loadMemberships();
    } catch (err) {
      showStatus("제거 실패", true);
      console.error(err);
    }
  }

  // 행의 '운영진' 버튼 위임.
  document.addEventListener("click", (e) => {
    const trigger = e.target.closest("[data-leader-edit]");
    if (trigger) {
      const row = trigger.closest("tr[data-group-id]");
      if (!row) return;
      const groupId = Number(row.dataset.groupId);
      const label = row.dataset.groupLabel || "";
      openModal(groupId, label, row);
    }
  });

  if (closeBtn) closeBtn.addEventListener("click", closeModal);
  if (overlay) {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) closeModal();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !overlay.hidden) closeModal();
    });
  }
  if (addForm) addForm.addEventListener("submit", addMember);

  if (tbody) {
    tbody.addEventListener("click", (e) => {
      const del = e.target.closest(".leader-delete");
      if (!del) return;
      const tr = del.closest("tr[data-membership-id]");
      if (!tr) return;
      deleteMembership(tr.dataset.membershipId);
    });
    tbody.addEventListener("change", (e) => {
      const sel = e.target.closest(".leader-role-select");
      if (!sel) return;
      const tr = sel.closest("tr[data-membership-id]");
      if (!tr) return;
      patchRole(tr.dataset.membershipId, sel.value, sel);
    });
  }

  /* ---------- 사용자 검색 자동완성 컴포넌트 ---------- */
  function createUserPicker(root) {
    if (!root) return null;
    const input = root.querySelector("[data-user-picker-input]");
    const list = root.querySelector("[data-user-picker-list]");
    const hidden = root.querySelector("[data-user-picker-id]");
    const hint = root.parentElement
      ? root.parentElement.querySelector("[data-user-picker-hint]")
      : null;
    if (!input || !list || !hidden) return null;

    let selected = null;
    let items = [];
    let activeIdx = -1;
    let timer = null;
    let lastQuery = "";

    function clear() {
      selected = null;
      hidden.value = "";
      input.value = "";
      closeList();
      setHint("아래 목록에서 선택해야 등록할 수 있어요.", false);
    }

    function setHint(msg, isError) {
      if (!hint) return;
      hint.textContent = msg || "";
      hint.classList.toggle("is-error", !!isError);
    }

    function closeList() {
      list.hidden = true;
      list.innerHTML = "";
      activeIdx = -1;
    }

    function renderList() {
      if (!items.length) {
        list.innerHTML = `<li class="muted" role="option" aria-disabled="true">결과 없음</li>`;
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
      try {
        const url = `${ctx.userSearchUrl}?q=${encodeURIComponent(q)}&limit=10`;
        const res = await fetch(url, { credentials: "same-origin" });
        if (!res.ok) throw new Error(await res.text());
        if (q !== lastQuery) return;
        items = await res.json();
        activeIdx = items.length ? 0 : -1;
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
      setHint("", false);
      closeList();
    }

    input.addEventListener("input", () => {
      selected = null;
      hidden.value = "";
      setHint("아래 목록에서 선택해야 등록할 수 있어요.", false);
      const q = input.value.trim();
      clearTimeout(timer);
      if (!q) {
        closeList();
        return;
      }
      timer = setTimeout(() => search(q), 180);
    });

    input.addEventListener("focus", () => {
      const q = input.value.trim();
      if (q) search(q);
    });

    input.addEventListener("keydown", (e) => {
      if (list.hidden) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (!items.length) return;
        activeIdx = (activeIdx + 1) % items.length;
        renderList();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (!items.length) return;
        activeIdx = (activeIdx - 1 + items.length) % items.length;
        renderList();
      } else if (e.key === "Enter") {
        if (activeIdx >= 0) {
          e.preventDefault();
          pick(activeIdx);
        }
      } else if (e.key === "Escape") {
        closeList();
      }
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
    };
  }
})();
