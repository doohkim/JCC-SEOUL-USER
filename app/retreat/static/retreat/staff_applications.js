/**
 * 관리 > 참가 신청 승인·반려
 */
(function () {
  "use strict";

  const ctx = window.RETREAT_STAFF_APPLICATIONS_CTX || {};
  const tbody = document.getElementById("staffApplicationsTbody");
  const statusEl = document.getElementById("staffApplicationsStatus");
  const statusPills = document.getElementById("staffAppStatusPills");
  const modal = document.getElementById("staffApplicationReviewModal");
  const reviewBody = document.getElementById("staffApplicationReviewBody");
  const councilRoleField = document.getElementById("staffAppCouncilRoleField");
  const councilRoleSelect = document.getElementById("staffAppCouncilRole");
  const rejectField = document.getElementById("staffAppRejectReasonField");
  const rejectInput = document.getElementById("staffAppRejectReason");
  const btnApprove = document.getElementById("btnStaffAppApprove");
  const btnReject = document.getElementById("btnStaffAppReject");

  let currentApp = null;
  let reviewMode = "approve";
  let activeStatus = "pending";

  const EMPTY_MESSAGES = {
    pending: "검토 대기 신청이 없습니다.",
    approved: "승인된 신청이 없습니다.",
    rejected: "반려된 신청이 없습니다.",
    all: "참가 신청이 없습니다.",
  };

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function setStatus(msg, isError) {
    if (!statusEl) return;
    statusEl.textContent = msg || "";
    statusEl.className = isError ? "msg msg--error" : "msg";
  }

  function reviewUrl(id) {
    return String(ctx.apiReviewUrlTemplate || "").replace("/0/", `/${id}/`);
  }

  function statusBadgeClass(status) {
    if (status === "approved") return "jcc-retreat-staffAppStatusBadge--approved";
    if (status === "rejected") return "jcc-retreat-staffAppStatusBadge--rejected";
    return "jcc-retreat-staffAppStatusBadge--pending";
  }

  function renderActionCell(app) {
    if (app.status === "pending") {
      return `<td class="jcc-retreat-staffAppActions">
        <button type="button" class="btn-link" data-review="${app.id}" data-mode="approve">검토</button>
      </td>`;
    }
    const label = app.status_display || app.status || "";
    return `<td class="jcc-retreat-staffAppActions">
      <span class="jcc-retreat-staffAppStatusBadge ${statusBadgeClass(app.status)}">${escapeHtml(label)}</span>
    </td>`;
  }

  function populateCouncilRoles(selected) {
    if (!councilRoleSelect) return;
    councilRoleSelect.innerHTML = "";
    (ctx.councilRoles || []).forEach(([value, label]) => {
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = label;
      if (selected && value === selected) opt.selected = true;
      councilRoleSelect.appendChild(opt);
    });
  }

  function openModal(app, mode) {
    currentApp = app;
    reviewMode = mode;
    if (!modal || !reviewBody) return;
    const groupPart = app.group_name
      ? `${escapeHtml(app.group_name)} · ${escapeHtml(app.group_role_display || "")}`
      : "—";
    reviewBody.innerHTML = `
      <p><strong>${escapeHtml(app.user_display_name)}</strong> (${escapeHtml(app.user_username)})</p>
      <p class="muted">${escapeHtml(app.region_name)} · ${escapeHtml(app.division_name)}</p>
      <p>조·역할: ${groupPart}</p>
      ${app.note ? `<p>메모: ${escapeHtml(app.note)}</p>` : ""}
    `;
    if (app.is_pastoral) {
      councilRoleField.hidden = false;
      populateCouncilRoles(app.suggested_council_role || "");
    } else {
      councilRoleField.hidden = true;
    }
    rejectField.hidden = mode !== "reject";
    rejectInput.value = "";
    modal.showModal();
  }

  function closeModal() {
    if (modal) modal.close();
    currentApp = null;
  }

  document.querySelectorAll("[data-close-modal]").forEach((btn) => {
    btn.addEventListener("click", closeModal);
  });

  async function submitReview(action) {
    if (!currentApp) return;
    const payload = { action };
    if (action === "approve" && currentApp.is_pastoral) {
      payload.council_role = councilRoleSelect.value;
    }
    if (action === "reject") {
      payload.rejection_reason = rejectInput.value.trim();
    }
    setStatus("처리 중…");
    try {
      const r = await fetch(reviewUrl(currentApp.id), {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": ctx.csrfToken,
        },
        body: JSON.stringify(payload),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        throw new Error(data.detail || data.non_field_errors || "처리에 실패했습니다.");
      }
      closeModal();
      setStatus(action === "approve" ? "승인되었습니다." : "반려되었습니다.");
      await loadApplications(activeStatus);
    } catch (err) {
      setStatus(err.message || "오류가 발생했습니다.", true);
    }
  }

  if (btnApprove) {
    btnApprove.addEventListener("click", () => submitReview("approve"));
  }
  if (btnReject) {
    btnReject.addEventListener("click", () => {
      if (reviewMode !== "reject") {
        openModal(currentApp, "reject");
        return;
      }
      submitReview("reject");
    });
  }

  statusPills?.addEventListener("click", (e) => {
    const btn = e.target.closest(".jcc-retreat-staffPill[data-status]");
    if (!btn) return;
    activeStatus = btn.dataset.status || "pending";
    statusPills.querySelectorAll(".jcc-retreat-staffPill").forEach((pill) => {
      const active = pill === btn;
      pill.classList.toggle("is-active", active);
      pill.setAttribute("aria-selected", active ? "true" : "false");
    });
    loadApplications(activeStatus);
  });

  async function loadApplications(statusFilter) {
    if (!tbody) return;
    const status = statusFilter || activeStatus || "pending";
    activeStatus = status;
    tbody.innerHTML = '<tr><td colspan="5">불러오는 중…</td></tr>';
    try {
      const r = await fetch(`${ctx.apiListUrl}?status=${encodeURIComponent(status)}`, {
        credentials: "same-origin",
      });
      const data = await r.json();
      if (!r.ok) throw new Error("목록을 불러오지 못했습니다.");
      const rows = data.results || [];
      if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="5" class="muted">${escapeHtml(EMPTY_MESSAGES[status] || EMPTY_MESSAGES.all)}</td></tr>`;
        return;
      }
      tbody.innerHTML = rows
        .map((app) => {
          const groupPart = app.group_name
            ? `${escapeHtml(app.group_name)} · ${escapeHtml(app.group_role_display || "")}`
            : app.is_pastoral
              ? "목회자"
              : "—";
          const created = app.created_at
            ? new Date(app.created_at).toLocaleString("ko-KR")
            : "";
          return `<tr>
            <td>${escapeHtml(app.user_display_name)}</td>
            <td>${escapeHtml(app.region_name)} · ${escapeHtml(app.division_name)}</td>
            <td>${groupPart}</td>
            <td>${escapeHtml(created)}</td>
            ${renderActionCell(app)}
          </tr>`;
        })
        .join("");
      const byId = Object.fromEntries(rows.map((a) => [String(a.id), a]));
      tbody.querySelectorAll("[data-review]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const app = byId[btn.getAttribute("data-review")];
          if (app) openModal(app, btn.getAttribute("data-mode") || "approve");
        });
      });
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="5" class="error">${escapeHtml(err.message)}</td></tr>`;
    }
  }

  loadApplications(activeStatus);
})();
