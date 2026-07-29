/*
 * 조 관리 목록 — 지역·부서 다중선택 칩 필터 (Notion 스타일, 클라이언트 즉시 필터)
 *
 * - 서버에서 렌더된 카드(.jcc-retreat-groupCardWrap)의 대표 지역·부서와
 *   추가 지역·부서(data-*-names)를 함께 스캔해 distinct 칩을 만든다(첫 등장 순서 유지).
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
  const lodgingWrap = document.getElementById("groupFilterLodgingStay");
  const resetBtn = document.getElementById("groupFilterReset");
  const emptyMsg = document.getElementById("groupFilterEmpty");

  const cards = Array.from(grid.querySelectorAll(".jcc-retreat-groupCardWrap"));
  if (cards.length === 0) return;

  const selectedRegions = new Set();
  const selectedDivisions = new Set();
  const selectedLodgingStay = new Set();

  // 선택 상태를 sessionStorage에 저장/복원 (조 생성·수정 시 location.reload() 후에도 유지).
  // 키에 location.pathname(=event_id 포함)을 넣어 집회별로 분리한다.
  const STORAGE_KEY = "retreatGroupFilter:" + location.pathname;

  function loadStored() {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      if (!raw) return { regions: [], divisions: [], lodgingStay: [] };
      const data = JSON.parse(raw);
      return {
        regions: Array.isArray(data.regions) ? data.regions : [],
        divisions: Array.isArray(data.divisions) ? data.divisions : [],
        lodgingStay: Array.isArray(data.lodgingStay) ? data.lodgingStay : [],
      };
    } catch (e) {
      return { regions: [], divisions: [], lodgingStay: [] };
    }
  }

  function persist() {
    try {
      sessionStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          regions: Array.from(selectedRegions),
          divisions: Array.from(selectedDivisions),
          lodgingStay: Array.from(selectedLodgingStay),
        })
      );
    } catch (e) {
      /* 스토리지 사용 불가 시 무시 */
    }
  }

  function syncUrl() {
    const params = new URLSearchParams();
    if (selectedRegions.size) {
      params.set("region", Array.from(selectedRegions).join(","));
    }
    if (selectedDivisions.size) {
      params.set("division", Array.from(selectedDivisions).join(","));
    }
    if (selectedLodgingStay.size) {
      params.set("lodgingStay", Array.from(selectedLodgingStay).join(","));
    }
    const query = params.toString();
    history.replaceState(null, "", query ? `${location.pathname}?${query}` : location.pathname);
  }

  function valuesFor(card, multiAttr, fallbackAttr) {
    const raw = (card.getAttribute(multiAttr) || "").trim();
    const values = raw
      ? raw
          .split("|")
          .map((v) => v.trim())
          .filter(Boolean)
      : [(card.getAttribute(fallbackAttr) || "").trim()].filter(Boolean);
    return Array.from(new Set(values));
  }

  function distinctInOrder(multiAttr, fallbackAttr) {
    const seen = [];
    const set = new Set();
    cards.forEach((card) => {
      valuesFor(card, multiAttr, fallbackAttr).forEach((value) => {
        if (!set.has(value)) {
          set.add(value);
          seen.push(value);
        }
      });
    });
    return seen;
  }

  function makeChip(value, selectedSet, groupEl) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "jcc-retreat-filterChip";
    chip.textContent = value;
    // 복원된 선택값이면 활성 상태로 렌더
    const preselected = selectedSet.has(value);
    chip.setAttribute("aria-pressed", preselected ? "true" : "false");
    if (preselected) chip.classList.add("is-active");
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
      persist();
      applyFilter();
    });
    groupEl.appendChild(chip);
  }

  function applyFilter() {
    let visibleCount = 0;
    const visibleCards = [];
    cards.forEach((card) => {
      const regions = valuesFor(card, "data-region-names", "data-region-name");
      const divisions = valuesFor(card, "data-division-names", "data-division-name");
      const okRegion =
        selectedRegions.size === 0 ||
        regions.some((region) => selectedRegions.has(region));
      const okDivision =
        selectedDivisions.size === 0 ||
        divisions.some((division) => selectedDivisions.has(division));
      const okLodging =
        selectedLodgingStay.size === 0 ||
        (selectedLodgingStay.has("unassigned") &&
          Number(card.dataset.lodgingUnassigned || 0) > 0);
      const show = okRegion && okDivision && okLodging;
      const detailLink = card.querySelector(".jcc-retreat-groupCard");
      if (detailLink) {
        const detailUrl = new URL(detailLink.href, location.origin);
        if (selectedLodgingStay.has("unassigned")) {
          detailUrl.searchParams.set("lodgingStay", "unassigned");
        } else {
          detailUrl.searchParams.delete("lodgingStay");
        }
        detailLink.href = `${detailUrl.pathname}${detailUrl.search}`;
      }
      card.hidden = !show;
      if (show) {
        visibleCount += 1;
        visibleCards.push(card);
      }
    });
    updateSummary(visibleCards);
    const hasFilter =
      selectedRegions.size > 0 ||
      selectedDivisions.size > 0 ||
      selectedLodgingStay.size > 0;
    if (resetBtn) resetBtn.hidden = !hasFilter;
    if (emptyMsg) emptyMsg.hidden = visibleCount !== 0;
    syncUrl();
  }

  function updateSummary(visibleCards) {
    const summaryFields = {
      total: "[data-summary-total]",
      participating: "[data-summary-participating]",
      absent: "[data-summary-absent]",
      pending: "[data-summary-pending]",
      in: "[data-summary-in]",
      out: "[data-summary-out]",
    };
    Object.entries(summaryFields).forEach(([key, selector]) => {
      const target = document.querySelector(`#retreatSummaryBar ${selector}`);
      if (!target) return;
      const datasetKey = `summary${key[0].toUpperCase()}${key.slice(1)}`;
      const total = visibleCards.reduce((sum, card) => {
        const value = Number(card.dataset[datasetKey] || 0);
        return sum + (Number.isFinite(value) ? value : 0);
      }, 0);
      target.textContent = String(total);
    });
  }

  const regionValues = distinctInOrder("data-region-names", "data-region-name");
  const divisionValues = distinctInOrder(
    "data-division-names",
    "data-division-name"
  );

  // 저장된 선택을 현재 카드에 실제 존재하는 값과 교집합으로 복원(사라진 값 정리).
  const stored = loadStored();
  const urlParams = new URLSearchParams(location.search);
  const initialRegions = urlParams.has("region")
    ? (urlParams.get("region") || "").split(",").filter(Boolean)
    : stored.regions;
  const initialDivisions = urlParams.has("division")
    ? (urlParams.get("division") || "").split(",").filter(Boolean)
    : stored.divisions;
  const regionSetAll = new Set(regionValues);
  const divisionSetAll = new Set(divisionValues);
  initialRegions.forEach((v) => {
    if (regionSetAll.has(v)) selectedRegions.add(v);
  });
  initialDivisions.forEach((v) => {
    if (divisionSetAll.has(v)) selectedDivisions.add(v);
  });
  const initialLodgingStay = urlParams.has("lodgingStay")
    ? (urlParams.get("lodgingStay") || "").split(",").filter(Boolean)
    : (stored.lodgingStay || []);
  initialLodgingStay.forEach((value) => {
    if (value === "unassigned") selectedLodgingStay.add(value);
  });

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

  lodgingWrap?.querySelectorAll("[data-filter-kind='lodgingStay']").forEach((chip) => {
    const value = chip.dataset.filterValue;
    const selected = selectedLodgingStay.has(value);
    chip.classList.toggle("is-active", selected);
    chip.setAttribute("aria-pressed", selected ? "true" : "false");
    chip.addEventListener("click", () => {
      if (selectedLodgingStay.has(value)) selectedLodgingStay.delete(value);
      else selectedLodgingStay.add(value);
      const active = selectedLodgingStay.has(value);
      chip.classList.toggle("is-active", active);
      chip.setAttribute("aria-pressed", active ? "true" : "false");
      persist();
      applyFilter();
    });
  });

  cards.forEach((card) => {
    const trigger = card.querySelector("[data-open-unassigned]");
    const detailLink = card.querySelector(".jcc-retreat-groupCard");
    if (!trigger || !detailLink) return;
    function openUnassigned(event) {
      event.preventDefault();
      event.stopPropagation();
      const detailUrl = new URL(detailLink.href, location.origin);
      detailUrl.searchParams.set("lodgingStay", "unassigned");
      location.href = `${detailUrl.pathname}${detailUrl.search}`;
    }
    trigger.addEventListener("click", openUnassigned);
  });

  bar.hidden = false;

  // 복원된 선택을 화면에 즉시 반영(상호작용 전에도 필터 적용).
  applyFilter();

  if (resetBtn) {
    resetBtn.addEventListener("click", function () {
      selectedRegions.clear();
      selectedDivisions.clear();
      selectedLodgingStay.clear();
      bar
        .querySelectorAll(".jcc-retreat-filterChip.is-active")
        .forEach(function (chip) {
          chip.classList.remove("is-active");
          chip.setAttribute("aria-pressed", "false");
        });
      persist();
      applyFilter();
    });
  }
})();
