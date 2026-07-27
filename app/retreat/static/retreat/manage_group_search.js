/**
 * 조 상세 조원 목록 — 이름·전화번호 실시간 검색.
 * 조원 추가·수정·삭제 및 정렬로 tbody가 바뀌면 현재 검색어를 다시 적용한다.
 */
(function () {
  "use strict";

  const body = document.getElementById("retreatAttBody");
  const input = document.getElementById("groupAttendeeSearch");
  if (!body || !input) return;

  const clearButton = document.getElementById("groupAttendeeSearchClear");
  const countElement = document.getElementById("groupAttendeeSearchCount");
  const emptyElement = document.getElementById("groupAttendeeSearchEmpty");
  let scheduled = false;

  function normalizedText(value) {
    return String(value || "").trim().toLocaleLowerCase("ko");
  }

  function phoneDigits(value) {
    return String(value || "").replace(/\D/g, "");
  }

  function attendeeRows() {
    return Array.from(body.querySelectorAll("tr[data-attendee-id]"));
  }

  function rowMatches(row, query) {
    if (!query) return true;
    const name = normalizedText(row.querySelector("[data-name]")?.textContent);
    const phone = row.querySelector("[data-phone]")?.textContent || "";
    const queryDigits = phoneDigits(query);
    return (
      name.includes(query) ||
      (queryDigits.length > 0 && phoneDigits(phone).includes(queryDigits))
    );
  }

  function applySearch() {
    const rows = attendeeRows();
    const query = normalizedText(input.value);
    let visibleCount = 0;

    rows.forEach((row) => {
      const visible = rowMatches(row, query);
      row.hidden = !visible;
      if (!visible) return;
      visibleCount += 1;
      const numberCell = row.querySelector("[data-row-num]");
      if (numberCell && numberCell.textContent !== String(visibleCount)) {
        numberCell.textContent = String(visibleCount);
      }
    });

    if (clearButton) clearButton.hidden = !query;
    if (countElement) {
      countElement.textContent = query
        ? `${visibleCount} / ${rows.length}명`
        : `총 ${rows.length}명`;
    }
    if (emptyElement) {
      emptyElement.hidden = !query || visibleCount > 0;
    }
  }

  function scheduleSearch() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      applySearch();
    });
  }

  input.addEventListener("input", applySearch);
  clearButton?.addEventListener("click", () => {
    input.value = "";
    applySearch();
    input.focus();
  });

  new MutationObserver(scheduleSearch).observe(body, {
    childList: true,
    subtree: true,
  });

  applySearch();
})();
