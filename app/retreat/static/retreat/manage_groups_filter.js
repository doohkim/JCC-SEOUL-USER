/*
 * 조 관리 목록 — 지역·부서 다중선택 칩 필터 (Notion 스타일, 클라이언트 즉시 필터)
 *
 * - 서버에서 렌더된 카드(.jcc-retreat-groupCardWrap)의 data-region-name /
 *   data-division-name 을 스캔해 distinct 칩을 만든다(첫 등장 순서 유지).
 * - 칩 다중선택 토글 → (지역 OR) AND (부서 OR) 교집합으로 카드 표시/숨김.
 * - 선택이 없으면 전체 표시. 일치 0개면 안내 메시지. 초기화 버튼으로 전체 해제.
 * - can_add_group 여부와 무관하게 모든 사용자에게 동작(별도 권한 불필요).
 */
(function () {
  "use strict";

  const grid = document.getElementById("retreatGroupGrid");
  const bar = document.getElementById("groupFilterBar");
  if (!grid || !bar) return;

  const regionsWrap = document.getElementById("groupFilterRegions");
  const divisionsWrap = document.getElementById("groupFilterDivisions");
  const resetBtn = document.getElementById("groupFilterReset");
  const emptyMsg = document.getElementById("groupFilterEmpty");

  const cards = Array.from(grid.querySelectorAll(".jcc-retreat-groupCardWrap"));
  if (cards.length === 0) return;

  const selectedRegions = new Set();
  const selectedDivisions = new Set();

  function distinctInOrder(attr) {
    const seen = [];
    const set = new Set();
    cards.forEach((card) => {
      const value = (card.getAttribute(attr) || "").trim();
      if (value && !set.has(value)) {
        set.add(value);
        seen.push(value);
      }
    });
    return seen;
  }

  function makeChip(value, selectedSet, groupEl) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "jcc-retreat-filterChip";
    chip.textContent = value;
    chip.setAttribute("aria-pressed", "false");
    chip.addEventListener("click", function () {
      if (selectedSet.has(value)) {
        selectedSet.delete(value);
        chip.classList.remove("is-active");
        chip.setAttribute("aria-pressed", "false");
      } else {
        selectedSet.add(value);
        chip.classList.add("is-active");
        chip.setAttribute("aria-pressed", "true");
      }
      applyFilter();
    });
    groupEl.appendChild(chip);
  }

  function applyFilter() {
    let visibleCount = 0;
    cards.forEach((card) => {
      const region = (card.getAttribute("data-region-name") || "").trim();
      const division = (card.getAttribute("data-division-name") || "").trim();
      const okRegion = selectedRegions.size === 0 || selectedRegions.has(region);
      const okDivision =
        selectedDivisions.size === 0 || selectedDivisions.has(division);
      const show = okRegion && okDivision;
      card.hidden = !show;
      if (show) visibleCount += 1;
    });
    const hasFilter = selectedRegions.size > 0 || selectedDivisions.size > 0;
    if (resetBtn) resetBtn.hidden = !hasFilter;
    if (emptyMsg) emptyMsg.hidden = visibleCount !== 0;
  }

  const regionValues = distinctInOrder("data-region-name");
  const divisionValues = distinctInOrder("data-division-name");

  const regionRow = regionsWrap
    ? regionsWrap.closest(".jcc-retreat-filterRow")
    : null;
  const divisionRow = divisionsWrap
    ? divisionsWrap.closest(".jcc-retreat-filterRow")
    : null;

  // 옵션이 2개 미만이면 해당 그룹은 필터링 의미가 없으므로 숨긴다.
  if (regionsWrap && regionValues.length >= 2) {
    regionValues.forEach(function (v) {
      makeChip(v, selectedRegions, regionsWrap);
    });
  } else if (regionRow) {
    regionRow.hidden = true;
  }

  if (divisionsWrap && divisionValues.length >= 2) {
    divisionValues.forEach(function (v) {
      makeChip(v, selectedDivisions, divisionsWrap);
    });
  } else if (divisionRow) {
    divisionRow.hidden = true;
  }

  // 지역·부서 모두 선택지가 1개 이하면 필터 바 자체를 숨긴다.
  if (regionValues.length < 2 && divisionValues.length < 2) return;

  bar.hidden = false;

  if (resetBtn) {
    resetBtn.addEventListener("click", function () {
      selectedRegions.clear();
      selectedDivisions.clear();
      bar
        .querySelectorAll(".jcc-retreat-filterChip.is-active")
        .forEach(function (chip) {
          chip.classList.remove("is-active");
          chip.setAttribute("aria-pressed", "false");
        });
      applyFilter();
    });
  }
})();
