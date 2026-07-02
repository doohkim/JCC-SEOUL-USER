/**
 * 운영진 참가 신청 — 성도 조·직책 select 스타일
 */
(function () {
  "use strict";

  const ctx = window.RETREAT_STAFF_APPLY_CTX || {};
  if (ctx.isPastoral || ctx.readOnly) return;

  const groupSelect = document.getElementById("id_group");
  const roleSelect = document.getElementById("id_group_role");
  [groupSelect, roleSelect].forEach((el) => {
    if (el) el.classList.add("jcc-retreat-staffApplySelect");
  });
})();
