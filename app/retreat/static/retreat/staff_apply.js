/**
 * 운영진 참가 신청 — 신청 유형별 조·직책 필드 토글 + 커스텀 select 동기화
 */
(function () {
  "use strict";

  const ctx = window.RETREAT_STAFF_APPLY_CTX || {};
  if (ctx.isPastoral) return;

  const readOnly = !!ctx.readOnly;
  const trackSelect = document.getElementById("id_application_track");
  const memberFields = document.getElementById("staffApplyMemberFields");
  const groupSelect = document.getElementById("id_group");
  const roleSelect = document.getElementById("id_group_role");

  function refreshCustomSelects() {
    if (!window.JccCustomSelect) return;
    [trackSelect, groupSelect, roleSelect].forEach((el) => {
      if (!el) return;
      const wrap = el.closest(".jcc-cselect");
      window.JccCustomSelect.refresh(wrap || el);
    });
  }

  function syncMemberFields() {
    const track = trackSelect?.value || "";
    const showGroup = track === "group_leadership";
    if (memberFields) memberFields.hidden = !showGroup;
    if (!readOnly) {
      if (groupSelect) {
        groupSelect.required = showGroup;
        if (!showGroup) groupSelect.value = "";
      }
      if (roleSelect) {
        roleSelect.required = showGroup;
        if (!showGroup) roleSelect.value = "";
      }
    }
    refreshCustomSelects();
  }

  trackSelect?.addEventListener("change", syncMemberFields);
  syncMemberFields();
})();
