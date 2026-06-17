/**
 * 숙소 탭 전체 명단 — 입실·숙박·배정·지역·부서 칩 필터 + 이름 검색 + 요약 프리셋
 */
(function () {
  "use strict";

  const tbody = document.getElementById("lodgingRosterBody");
  if (!tbody) return;

  const rows = Array.from(tbody.querySelectorAll("tr[data-attendee-id]"));
  if (rows.length === 0) return;

  const STORAGE_KEY = "retreatLodgingRosterFilter:" + location.pathname;
  const emptyMsg = document.getElementById("lodgingRosterFilterEmpty");
  const resetBtn = document.getElementById("rosterFilterReset");
  const searchInput = document.getElementById("rosterNameSearch");
  const filterBar = document.getElementById("lodgingRosterFilterBar");
  const regionsWrap = document.getElementById("rosterFilterRegions");
  const divisionsWrap = document.getElementById("rosterFilterDivisions");
  const regionRow = filterBar?.querySelector('[data-filter-row="region"]');
  const divisionRow = filterBar?.querySelector('[data-filter-row="division"]');

  const selectedStatus = new Set();
  const selectedStay = new Set();
  const selectedAssign = new Set();
  const selectedRegions = new Set();
  const selectedDivisions = new Set();
  let nameQuery = "";

  function distinctValues(attr) {
    const seen = [];
    const set = new Set();
    rows.forEach((row) => {
      const v = (row.getAttribute(attr) || "").trim();
      if (v && !set.has(v)) {
        set.add(v);
        seen.push(v);
      }
    });
    return seen;
  }

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
        JSON.stringify({
          status: Array.from(selectedStatus),
          stay: Array.from(selectedStay),
          assign: Array.from(selectedAssign),
          regions: Array.from(selectedRegions),
          divisions: Array.from(selectedDivisions),
          name: nameQuery,
        })
      );
    } catch (e) {}
  }

  function syncUrl() {
    const params = new URLSearchParams();
    if (selectedStatus.size) params.set("status", Array.from(selectedStatus).join(","));
    if (selectedStay.size) params.set("stay", Array.from(selectedStay).join(","));
    if (selectedAssign.size) params.set("assign", Array.from(selectedAssign).join(","));
    if (selectedRegions.size) params.set("region", Array.from(selectedRegions).join(","));
    if (selectedDivisions.size) params.set("division", Array.from(selectedDivisions).join(","));
    if (nameQuery.trim()) params.set("q", nameQuery.trim());
    const qs = params.toString();
    const next = qs ? `${location.pathname}?${qs}` : location.pathname;
    window.history.replaceState(null, "", next);
  }

  function applyLegacyLodgingParam(values) {
    values.forEach((v) => {
      if (v === "eligible") selectedStay.add("eligible");
      else if (v === "na" || v === "ineligible") selectedStay.add("ineligible");
      else if (v === "assigned") selectedAssign.add("assigned");
      else if (v === "unassigned") selectedAssign.add("unassigned");
    });
  }

  function phoneDigits(value) {
    return (value || "").replace(/\D/g, "");
  }

  function rowMatches(row) {
    const status = row.dataset.checkInStatus || "";
    const stay = row.dataset.lodgingEligible || "";
    const assignment = row.dataset.lodgingAssignment || "";
    const region = row.dataset.regionName || "";
    const division = row.dataset.divisionName || "";
    const name = (row.dataset.name || "").toLowerCase();
    const phone = row.dataset.phone || "";

    if (selectedStatus.size > 0 && !selectedStatus.has(status)) return false;
    if (selectedStay.size > 0 && !selectedStay.has(stay)) return false;
    if (selectedAssign.size > 0 && !selectedAssign.has(assignment)) return false;
    if (selectedRegions.size > 0 && !selectedRegions.has(region)) return false;
    if (selectedDivisions.size > 0 && !selectedDivisions.has(division)) return false;
    if (nameQuery.trim()) {
      const q = nameQuery.trim().toLowerCase();
      const qDigits = phoneDigits(q);
      const nameMatch = name.includes(q);
      const phoneMatch = qDigits.length > 0 && phoneDigits(phone).includes(qDigits);
      if (!nameMatch && !phoneMatch) return false;
    }
    return true;
  }

  function renumberVisible() {
    let n = 0;
    rows.forEach((row) => {
      if (row.hidden) return;
      n += 1;
      const cell = row.querySelector("[data-row-num]");
      if (cell) cell.textContent = String(n);
    });
  }

  function applyFilter() {
    let visible = 0;
    rows.forEach((row) => {
      const show = rowMatches(row);
      row.hidden = !show;
      if (show) visible += 1;
    });
    renumberVisible();
    const hasFilter =
      selectedStatus.size > 0 ||
      selectedStay.size > 0 ||
      selectedAssign.size > 0 ||
      selectedRegions.size > 0 ||
      selectedDivisions.size > 0 ||
      !!nameQuery.trim();
    if (resetBtn) resetBtn.disabled = !hasFilter;
    if (emptyMsg) emptyMsg.hidden = visible > 0 || rows.length === 0;
    persist();
    syncUrl();
  }

  function setChipActive(chip, active) {
    chip.classList.toggle("is-active", active);
    chip.setAttribute("aria-pressed", active ? "true" : "false");
  }

  function chipSetForKind(kind) {
    if (kind === "status") return selectedStatus;
    if (kind === "stay") return selectedStay;
    if (kind === "assign") return selectedAssign;
    if (kind === "region") return selectedRegions;
    return selectedDivisions;
  }

  function isChipActive(kind, value) {
    return chipSetForKind(kind).has(value);
  }

  function bindPresetChip(chip) {
    chip.addEventListener("click", () => {
      const kind = chip.dataset.filterKind;
      const value = chip.dataset.filterValue;
      if (!kind || !value) return;
      const set = chipSetForKind(kind);
      if (set.has(value)) {
        set.delete(value);
        setChipActive(chip, false);
      } else {
        set.add(value);
        setChipActive(chip, true);
      }
      applyFilter();
    });
  }

  filterBar?.querySelectorAll("[data-filter-kind]").forEach(bindPresetChip);

  function makeDynamicChip(value, set, wrap) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "jcc-retreat-filterChip";
    chip.dataset.filterKind = wrap === regionsWrap ? "region" : "division";
    chip.dataset.filterValue = value;
    chip.textContent = value;
    const pre = set.has(value);
    setChipActive(chip, pre);
    chip.addEventListener("click", () => {
      if (set.has(value)) {
        set.delete(value);
        setChipActive(chip, false);
      } else {
        set.add(value);
        setChipActive(chip, true);
      }
      applyFilter();
    });
    wrap.appendChild(chip);
  }

  const regionValues = distinctValues("data-region-name");
  const divisionValues = distinctValues("data-division-name");

  if (regionsWrap && regionValues.length >= 1) {
    regionValues.forEach((v) => makeDynamicChip(v, selectedRegions, regionsWrap));
    if (regionRow) regionRow.hidden = false;
  }
  if (divisionsWrap && divisionValues.length >= 1) {
    divisionValues.forEach((v) => makeDynamicChip(v, selectedDivisions, divisionsWrap));
    if (divisionRow) divisionRow.hidden = false;
  }

  function syncChipStates() {
    filterBar?.querySelectorAll(".jcc-retreat-filterChip").forEach((chip) => {
      const kind = chip.dataset.filterKind;
      const value = chip.dataset.filterValue;
      setChipActive(chip, isChipActive(kind, value));
    });
  }

  function applyPreset(preset) {
    selectedStatus.clear();
    selectedStay.clear();
    selectedAssign.clear();
    selectedRegions.clear();
    selectedDivisions.clear();
    nameQuery = "";
    if (searchInput) searchInput.value = "";

    if (preset && preset !== "all") {
      const [kind, value] = preset.split(":");
      if (kind === "status" && value) selectedStatus.add(value);
      if (kind === "stay" && value) selectedStay.add(value);
      if (kind === "assign" && value) selectedAssign.add(value);
      if (kind === "lodging" && value) applyLegacyLodgingParam([value]);
    }

    syncChipStates();
    applyFilter();
  }

  document.querySelectorAll("[data-summary-preset]").forEach((btn) => {
    btn.addEventListener("click", () => {
      applyPreset(btn.dataset.summaryPreset || "all");
    });
  });

  let searchTimer = null;
  if (searchInput) {
    searchInput.addEventListener("input", () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        nameQuery = searchInput.value || "";
        applyFilter();
      }, 200);
    });
  }

  if (resetBtn) {
    resetBtn.addEventListener("click", () => applyPreset("all"));
  }

  function initFromUrlOrStorage() {
    const params = new URLSearchParams(location.search);
    const stored = loadStored();

    const statusParam = params.get("status") || (stored && stored.status?.join(","));
    const stayParam = params.get("stay") || (stored && stored.stay?.join(","));
    const assignParam = params.get("assign") || (stored && stored.assign?.join(","));
    const legacyLodgingParam = params.get("lodging");
    const regionParam = params.get("region") || (stored && stored.regions?.join(","));
    const divisionParam =
      params.get("division") || (stored && stored.divisions?.join(","));
    const qParam = params.get("q") || (stored && stored.name) || "";

    if (statusParam) statusParam.split(",").filter(Boolean).forEach((v) => selectedStatus.add(v));
    if (stayParam) stayParam.split(",").filter(Boolean).forEach((v) => selectedStay.add(v));
    if (assignParam) assignParam.split(",").filter(Boolean).forEach((v) => selectedAssign.add(v));
    if (legacyLodgingParam) applyLegacyLodgingParam(legacyLodgingParam.split(",").filter(Boolean));
    if (regionParam) regionParam.split(",").filter(Boolean).forEach((v) => selectedRegions.add(v));
    if (divisionParam)
      divisionParam.split(",").filter(Boolean).forEach((v) => selectedDivisions.add(v));
    nameQuery = qParam;
    if (searchInput && nameQuery) searchInput.value = nameQuery;

    syncChipStates();
    applyFilter();
  }

  initFromUrlOrStorage();
})();
