/**
 * 숙소 상태(lodging_stay_status) pill 태그 — 전체 명단·조 관리 공용
 */
(function () {
  "use strict";

  const DEFAULT_LABELS = {
    active: "배정됨",
    unassigned: "미배정",
    ended: "숙박 종료",
    no_stay: "입실 예정 없음",
    absent: "불참",
  };

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function render(data) {
    const status = (data && data.lodging_stay_status) || "";
    if (!status) {
      return '<span class="muted">-</span>';
    }
    let text = (data && data.lodging_stay_display) || "";
    if (!text && status !== "active") {
      text = DEFAULT_LABELS[status] || "-";
    }
    if (status === "active" && !text && data && data.lodging_room_label) {
      text = data.lodging_room_label;
    }
    if (!text) {
      text = DEFAULT_LABELS[status] || "-";
    }
    return (
      '<span class="jcc-retreat-lodgingStayBadge jcc-retreat-lodgingStayBadge--' +
      escapeHtml(status) +
      '">' +
      escapeHtml(text) +
      "</span>"
    );
  }

  window.JccLodgingStayBadge = { render, DEFAULT_LABELS };
})();
