/**
 * 숙소·객실 관리 — 정원 상태 필터 (잔여 객실 / 만실, 상호 배타)
 */
(function () {
  "use strict";

  const lodgingList = document.querySelector(".jcc-retreat-lodgingList");
  if (!lodgingList) return;

  const roomRows = Array.from(
    lodgingList.querySelectorAll("tr[data-room-id][data-room-has-vacancy]")
  );
  if (roomRows.length === 0) return;

  const STORAGE_KEY = "retreatLodgingManageFilter:" + location.pathname;
  const filterBar = document.getElementById("lodgingManageFilterBar");
  const resetBtn = document.getElementById("lodgingManageFilterReset");
  const emptyMsg = document.getElementById("lodgingVacancyFilterEmpty");
  const vacancyChip = filterBar?.querySelector('[data-lodging-filter="vacancy"]');
  const fullChip = filterBar?.querySelector('[data-lodging-filter="full"]');
  const summaryVacancyBtn = document.getElementById("lodgingSummaryVacancy");
  const lodgingCards = Array.from(
    document.querySelectorAll(".jcc-retreat-lodgingCard")
  );

  /** @type {"all" | "vacancy" | "full"} */
  let filterMode = "all";

  function loadStored() {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (e) {
      return null;
    }
  }

  function persist() {
    try {
      sessionStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ mode: filterMode })
      );
    } catch (e) {}
  }

  function syncUrl() {
    const params = new URLSearchParams(location.search);
    params.delete("vacancy");
    params.delete("full");
    if (filterMode === "vacancy") params.set("vacancy", "1");
    else if (filterMode === "full") params.set("full", "1");
    const qs = params.toString();
    const next = qs ? `${location.pathname}?${qs}` : location.pathname;
    window.history.replaceState(null, "", next);
  }

  function setChipState(chip, active) {
    if (!chip) return;
    chip.classList.toggle("is-active", active);
    chip.setAttribute("aria-pressed", active ? "true" : "false");
  }

  function setActiveUI() {
    setChipState(vacancyChip, filterMode === "vacancy");
    setChipState(fullChip, filterMode === "full");
    if (summaryVacancyBtn) {
      summaryVacancyBtn.classList.toggle("is-active", filterMode === "vacancy");
      summaryVacancyBtn.setAttribute(
        "aria-pressed",
        filterMode === "vacancy" ? "true" : "false"
      );
    }
    if (resetBtn) resetBtn.disabled = filterMode === "all";
  }

  function cardVisibleRoomCount(card) {
    return card.querySelectorAll(
      'tr[data-room-id][data-room-has-vacancy]:not([hidden])'
    ).length;
  }

  function rowMatchesFilter(row) {
    const hasVacancy = row.dataset.roomHasVacancy === "1";
    if (filterMode === "vacancy") return hasVacancy;
    if (filterMode === "full") return !hasVacancy;
    return true;
  }

  function applyFilter() {
    roomRows.forEach((row) => {
      row.hidden = !rowMatchesFilter(row);
    });

    lodgingCards.forEach((card) => {
      const tbody = card.querySelector("tbody[data-rooms]");
      if (!tbody) return;
      const dataRows = tbody.querySelectorAll(
        "tr[data-room-id][data-room-has-vacancy]"
      );
      if (dataRows.length === 0) {
        card.hidden = false;
        return;
      }
      card.hidden = filterMode !== "all" && cardVisibleRoomCount(card) === 0;
    });

    const visibleRooms = roomRows.filter((row) => !row.hidden).length;
    if (emptyMsg) {
      emptyMsg.hidden = filterMode === "all" || visibleRooms > 0;
    }

    setActiveUI();
    persist();
    syncUrl();
  }

  function setFilterMode(next) {
    filterMode = next === "vacancy" || next === "full" ? next : "all";
    applyFilter();
  }

  function toggleFilter(mode) {
    if (filterMode === mode) setFilterMode("all");
    else setFilterMode(mode);
  }

  function clearFilter() {
    setFilterMode("all");
  }

  if (vacancyChip) {
    vacancyChip.addEventListener("click", () => toggleFilter("vacancy"));
  }
  if (fullChip) {
    fullChip.addEventListener("click", () => toggleFilter("full"));
  }
  if (summaryVacancyBtn) {
    summaryVacancyBtn.addEventListener("click", () => toggleFilter("vacancy"));
  }
  if (resetBtn) {
    resetBtn.addEventListener("click", clearFilter);
  }

  function initFromUrlOrStorage() {
    const params = new URLSearchParams(location.search);
    const stored = loadStored();
    if (params.get("full") === "1") {
      filterMode = "full";
    } else if (
      params.get("vacancy") === "1" ||
      (stored && stored.mode === "vacancy") ||
      (stored && stored.vacancy === true)
    ) {
      filterMode = "vacancy";
    } else if (stored && stored.mode === "full") {
      filterMode = "full";
    } else {
      filterMode = "all";
    }
    applyFilter();
  }

  initFromUrlOrStorage();
})();
