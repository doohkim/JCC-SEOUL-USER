/**
 * 숙소 배정 드롭다운 — 만실·성별 불일치 호실 필터
 */
(function () {
  "use strict";

  function isVisible(room, { gender, currentRoomId }) {
    if (!room) return false;
    const rg = room.recommended_gender || "";
    if (rg === "male" || rg === "female") {
      if (!gender || gender !== rg) return false;
    }
    const cap = Number(room.capacity) || 0;
    if (cap === 0) return true;
    const current = currentRoomId ? String(currentRoomId) : "";
    if (current && String(room.id) === current) return true;
    const occupied = Number(room.assigned_count) || 0;
    return occupied < cap;
  }

  function filterRooms(rooms, opts) {
    return (rooms || []).filter((room) => isVisible(room, opts));
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function applyToSelect(selectEl, rooms, { gender, selectedId, refreshRoot }) {
    if (!selectEl) return "";
    const selected = selectedId ? String(selectedId) : "";
    const visible = filterRooms(rooms, { gender, currentRoomId: selected });
    let value = selected;
    if (value && !visible.some((r) => String(r.id) === value)) {
      value = "";
    }
    selectEl.innerHTML =
      '<option value="">(미배정)</option>' +
      visible
        .map((r) => `<option value="${r.id}">${escapeHtml(r.label)}</option>`)
        .join("");
    selectEl.value = value;
    if (refreshRoot && window.JccCustomSelect) {
      window.JccCustomSelect.refresh(refreshRoot);
    }
    return value;
  }

  window.JccLodgingAssignOptions = {
    isVisible,
    filterRooms,
    applyToSelect,
  };
})();
