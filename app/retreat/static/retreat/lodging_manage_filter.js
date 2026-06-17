/**
 * 숙소·호수 관리 — 잔여 객실만 필터 (요약 바 + 칩 토글)
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
  const summaryVacancyBtn = document.getElementById("lodgingSummaryVacancy");
  const lodgingCards = Array.from(
    document.querySelectorAll(".jcc-retreat-lodgingCard")
  );

  let vacancyOnly = false;

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
        JSON.stringify({ vacancy: vacancyOnly })
      );
    } catch (e) {}
  }

  function syncUrl() {
    const params = new URLSearchParams(location.search);
    if (vacancyOnly) params.set("vacancy", "1");
    else params.delete("vacancy");
    const qs = params.toString();
    const next = qs ? `${location.pathname}?${qs}` : location.pathname;
    window.history.replaceState(null, "", next);
  }

  function setActiveUI(active) {
    if (vacancyChip) {
      vacancyChip.classList.toggle("is-active", active);
      vacancyChip.setAttribute("aria-pressed", active ? "true" : "false");
    }
    if (summaryVacancyBtn) {
      summaryVacancyBtn.classList.toggle("is-active", active);
      summaryVacancyBtn.setAttribute("aria-pressed", active ? "true" : "false");
    }
    if (resetBtn) resetBtn.disabled = !active;
  }

  function cardVisibleRoomCount(card) {
    return card.querySelectorAll(
      'tr[data-room-id][data-room-has-vacancy]:not([hidden])'
    ).length;
  }

  function applyFilter() {
    roomRows.forEach((row) => {
      const hasVacancy = row.dataset.roomHasVacancy === "1";
      row.hidden = vacancyOnly && !hasVacancy;
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
      card.hidden = vacancyOnly && cardVisibleRoomCount(card) === 0;
    });

    const visibleRooms = roomRows.filter((row) => !row.hidden).length;
    if (emptyMsg) {
      emptyMsg.hidden = !vacancyOnly || visibleRooms > 0;
    }

    setActiveUI(vacancyOnly);
    persist();
    syncUrl();
  }

  function setVacancyOnly(next) {
    vacancyOnly = !!next;
    applyFilter();
  }

  function toggleVacancy() {
    setVacancyOnly(!vacancyOnly);
  }

  function clearFilter() {
    setVacancyOnly(false);
  }

  if (vacancyChip) {
    vacancyChip.addEventListener("click", toggleVacancy);
  }
  if (summaryVacancyBtn) {
    summaryVacancyBtn.addEventListener("click", toggleVacancy);
  }
  if (resetBtn) {
    resetBtn.addEventListener("click", clearFilter);
  }

  function initFromUrlOrStorage() {
    const params = new URLSearchParams(location.search);
    const stored = loadStored();
    const vacancyParam = params.get("vacancy") || (stored && stored.vacancy);
    vacancyOnly =
      vacancyParam === "1" || vacancyParam === true || vacancyParam === "true";
    applyFilter();
  }

  initFromUrlOrStorage();
})();
