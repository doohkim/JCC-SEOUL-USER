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
  const modalTitle = document.getElementById("staffApplicationReviewTitle");
  const modalAvatar = document.getElementById("staffAppModalAvatar");
  const modalName = document.getElementById("staffAppModalName");
  const modalUsername = document.getElementById("staffAppModalUsername");
  const modalInfoGrid = document.getElementById("staffAppModalInfoGrid");
  const modalReadonly = document.getElementById("staffAppModalReadonly");
  const reviewFields = document.getElementById("staffAppModalReviewFields");
  const footReview = document.getElementById("staffAppModalFootReview");
  const footReadonly = document.getElementById("staffAppModalFootReadonly");
  const councilRoleField = document.getElementById("staffAppCouncilRoleField");
  const councilRoleSelect = document.getElementById("staffAppCouncilRole");
  const rejectInput = document.getElementById("staffAppRejectReason");
  const btnApprove = document.getElementById("btnStaffAppApprove");
  const btnReject = document.getElementById("btnStaffAppReject");

  let currentApp = null;
  let activeStatus = "pending";
  let applicationsById = {};

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

  function getCouncilRoleChoices() {
    let roles = ctx.councilRoles;
    if (typeof roles === "string") {
      try {
        roles = JSON.parse(roles);
      } catch (_err) {
        roles = [];
      }
    }
    return Array.isArray(roles) ? roles : [];
  }

  function statusBadgeClass(status) {
    if (status === "approved") return "jcc-retreat-staffAppStatusBadge--approved";
    if (status === "rejected") return "jcc-retreat-staffAppStatusBadge--rejected";
    return "jcc-retreat-staffAppStatusBadge--pending";
  }

  function applicationInfoText(app) {
    if (app.group_name) {
      return `${app.group_name} · ${app.group_role_display || ""}`.trim();
    }
    if (app.is_pastoral) return "목회자";
    return "—";
  }

  function avatarInitial(name) {
    const trimmed = String(name || "").trim();
    return trimmed ? trimmed.slice(0, 1) : "?";
  }

  function formatDateTime(value) {
    if (!value) return "—";
    return new Date(value).toLocaleString("ko-KR");
  }

  function renderInfoGrid(app) {
    return `
      <div class="jcc-retreat-staffAppModalInfoItem">
        <div class="jcc-retreat-staffAppModalInfoLabel">소속</div>
        <div class="jcc-retreat-staffAppModalInfoValue">${escapeHtml(app.region_name)} · ${escapeHtml(app.division_name)}</div>
      </div>
      <div class="jcc-retreat-staffAppModalInfoItem">
        <div class="jcc-retreat-staffAppModalInfoLabel">신청 정보</div>
        <div class="jcc-retreat-staffAppModalInfoValue">${escapeHtml(applicationInfoText(app))}</div>
      </div>
    `;
  }

  function renderReadonlyDetails(app) {
    const rows = [
      `<div class="jcc-retreat-staffAppModalReadonlyRow">
        <span class="jcc-retreat-staffAppModalReadonlyLabel">처리 상태</span>
        <span class="jcc-retreat-staffAppPill jcc-retreat-staffAppStatusBadge ${statusBadgeClass(app.status)}">${escapeHtml(app.status === "approved" ? "승인됨" : app.status === "rejected" ? "반려" : app.status_display || app.status)}</span>
      </div>`,
      `<div class="jcc-retreat-staffAppModalReadonlyRow">
        <span class="jcc-retreat-staffAppModalReadonlyLabel">처리 일시</span>
        <span>${escapeHtml(formatDateTime(app.reviewed_at))}</span>
      </div>`,
    ];
    if (app.is_pastoral && app.approved_council_role_display) {
      rows.push(`<div class="jcc-retreat-staffAppModalReadonlyRow">
        <span class="jcc-retreat-staffAppModalReadonlyLabel">승인 역할</span>
        <span>${escapeHtml(app.approved_council_role_display)}</span>
      </div>`);
    }
    if (app.status === "rejected" && app.rejection_reason) {
      rows.push(`<div class="jcc-retreat-staffAppModalReadonlyRow jcc-retreat-staffAppModalReadonlyRow--stack">
        <span class="jcc-retreat-staffAppModalReadonlyLabel">반려 사유</span>
        <p class="jcc-retreat-staffAppModalReadonlyText">${escapeHtml(app.rejection_reason)}</p>
      </div>`);
    }
    if (app.note) {
      rows.push(`<div class="jcc-retreat-staffAppModalReadonlyRow jcc-retreat-staffAppModalReadonlyRow--stack">
        <span class="jcc-retreat-staffAppModalReadonlyLabel">신청 메모</span>
        <p class="jcc-retreat-staffAppModalReadonlyText">${escapeHtml(app.note)}</p>
      </div>`);
    }
    return rows.join("");
  }

  function populateCouncilRoles(selected) {
    if (!councilRoleSelect) return;
    councilRoleSelect.querySelectorAll('option:not([value=""])').forEach((opt) => opt.remove());
    getCouncilRoleChoices().forEach(([value, label]) => {
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = label;
      if (selected && value === selected) opt.selected = true;
      councilRoleSelect.appendChild(opt);
    });
    if (!selected) councilRoleSelect.value = "";
  }

  function renderActionCell(app) {
    if (app.status === "pending") {
      return `<td class="jcc-retreat-staffAppActions">
        <button type="button" class="jcc-retreat-staffAppPill jcc-retreat-staffAppPill--review" data-open-app="${app.id}">검토</button>
      </td>`;
    }
    const label = app.status === "approved" ? "승인됨" : app.status === "rejected" ? "반려" : app.status_display || app.status;
    return `<td class="jcc-retreat-staffAppActions">
      <span class="jcc-retreat-staffAppPill jcc-retreat-staffAppStatusBadge ${statusBadgeClass(app.status)}">${escapeHtml(label)}</span>
    </td>`;
  }

  function openModal(app) {
    currentApp = app;
    if (!modal) return;

    const isPending = app.status === "pending";
    if (modalTitle) modalTitle.textContent = isPending ? "신청 검토" : "신청 정보";
    if (modalAvatar) modalAvatar.textContent = avatarInitial(app.user_display_name);
    if (modalName) modalName.textContent = app.user_display_name || "";
    if (modalUsername) modalUsername.textContent = app.user_username || "";
    if (modalInfoGrid) modalInfoGrid.innerHTML = renderInfoGrid(app);

    if (isPending) {
      if (modalReadonly) modalReadonly.hidden = true;
      if (reviewFields) reviewFields.hidden = false;
      if (footReview) footReview.hidden = false;
      if (footReadonly) footReadonly.hidden = true;
      if (app.is_pastoral) {
        councilRoleField.hidden = false;
        populateCouncilRoles(app.suggested_council_role || app.approved_council_role || "");
      } else {
        councilRoleField.hidden = true;
      }
      if (rejectInput) rejectInput.value = "";
    } else {
      if (modalReadonly) {
        modalReadonly.hidden = false;
        modalReadonly.innerHTML = renderReadonlyDetails(app);
      }
      if (reviewFields) reviewFields.hidden = true;
      if (footReview) footReview.hidden = true;
      if (footReadonly) footReadonly.hidden = false;
      councilRoleField.hidden = true;
    }

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
    if (action === "approve" && currentApp.is_pastoral && councilRoleSelect?.value) {
      payload.council_role = councilRoleSelect.value;
    }
    if (action === "reject") {
      payload.rejection_reason = rejectInput?.value.trim() || "";
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
        const detail = data.detail || data.non_field_errors;
        throw new Error(Array.isArray(detail) ? detail.join(" ") : detail || "처리에 실패했습니다.");
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
    btnReject.addEventListener("click", () => submitReview("reject"));
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

  tbody?.addEventListener("click", (e) => {
    const trigger = e.target.closest("[data-open-app]");
    if (!trigger) return;
    const app = applicationsById[String(trigger.getAttribute("data-open-app"))];
    if (app) openModal(app);
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
      applicationsById = Object.fromEntries(rows.map((a) => [String(a.id), a]));
      if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="5" class="muted">${escapeHtml(EMPTY_MESSAGES[status] || EMPTY_MESSAGES.all)}</td></tr>`;
        return;
      }
      tbody.innerHTML = rows
        .map((app) => {
          const groupPart = escapeHtml(applicationInfoText(app));
          const created = app.created_at ? formatDateTime(app.created_at) : "";
          return `<tr>
            <td>
              <button type="button" class="jcc-retreat-staffAppNameBtn" data-open-app="${app.id}">
                ${escapeHtml(app.user_display_name)}
              </button>
            </td>
            <td>${escapeHtml(app.region_name)} · ${escapeHtml(app.division_name)}</td>
            <td>${groupPart}</td>
            <td>${escapeHtml(created)}</td>
            ${renderActionCell(app)}
          </tr>`;
        })
        .join("");
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="5" class="error">${escapeHtml(err.message)}</td></tr>`;
    }
  }

  populateCouncilRoles("");
  loadApplications(activeStatus);
})();
