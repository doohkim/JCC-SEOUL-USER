/**
 * 조 상세 조원 목록 — 이름·전화번호 검색 + 입·퇴실 교통수단 태그 필터.
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
  const filterBar = document.getElementById("groupTravelFilterBar");
  const arrivalWrap = document.getElementById("groupFilterArrivalTravel");
  const departureWrap = document.getElementById("groupFilterDepartureTravel");
  const lodgingWrap = document.getElementById("groupFilterLodgingStay");
  const resetButton = document.getElementById("groupTravelFilterReset");
  const selectedArrival = new Set();
  const selectedDeparture = new Set();
  const selectedLodgingStay = new Set();
  let selectedSummaryPreset = "all";
  const STORAGE_KEY = "retreatGroupTravelFilter:" + location.pathname;
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

  function localMinute(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    const pad = (number) => String(number).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }

  function travelKey(row, direction) {
    const isArrival = direction === "arrival";
    const value = isArrival ? row.dataset.expectedInAt : row.dataset.expectedOutAt;
    const custom = isArrival
      ? row.dataset.arrivalTravelIsCustom
      : row.dataset.departureTravelIsCustom;
    if (!value) return "__unset__";
    if (custom === "1") return "__custom__";
    const minute = localMinute(value);
    const matched = (window.RETREAT_CTX?.travelPresets?.[direction] || []).find(
      (preset) => !preset.manual && localMinute(preset.occurs_at) === minute
    );
    return matched ? String(matched.id) : "__custom__";
  }

  function rowMatches(row, query) {
    const arrivalKey = travelKey(row, "arrival");
    const departureKey = travelKey(row, "departure");
    if (row.dataset.arrivalTravel !== arrivalKey) {
      row.dataset.arrivalTravel = arrivalKey;
    }
    if (row.dataset.departureTravel !== departureKey) {
      row.dataset.departureTravel = departureKey;
    }
    if (
      selectedArrival.size &&
      !selectedArrival.has(row.dataset.arrivalTravel || "__unset__")
    ) return false;
    if (
      selectedDeparture.size &&
      !selectedDeparture.has(row.dataset.departureTravel || "__unset__")
    ) return false;
    if (
      selectedLodgingStay.size &&
      !selectedLodgingStay.has(row.dataset.lodgingStayStatus || "")
    ) return false;
    if (selectedSummaryPreset !== "all") {
      const [kind, value] = selectedSummaryPreset.split(":");
      const participation = row.dataset.participation || "participating";
      const status = row.dataset.checkIn || "pending";
      if (kind === "participation" && participation !== value) return false;
      if (
        kind === "status" &&
        (participation === "absent" || status !== value)
      ) return false;
    }
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
    const visibleRows = [];
    let visibleCount = 0;

    rows.forEach((row) => {
      const visible = rowMatches(row, query);
      row.hidden = !visible;
      if (!visible) return;
      visibleRows.push(row);
      visibleCount += 1;
      const numberCell = row.querySelector("[data-row-num]");
      if (numberCell && numberCell.textContent !== String(visibleCount)) {
        numberCell.textContent = String(visibleCount);
      }
    });
    updateSummary(visibleRows);

    const hasTravelFilter =
      selectedArrival.size > 0 ||
      selectedDeparture.size > 0 ||
      selectedLodgingStay.size > 0;
    const hasSummaryFilter = selectedSummaryPreset !== "all";
    if (clearButton) clearButton.hidden = !query;
    if (resetButton) resetButton.hidden = !hasTravelFilter;
    if (countElement) {
      countElement.textContent = query || hasTravelFilter || hasSummaryFilter
        ? `${visibleCount} / ${rows.length}명`
        : `총 ${rows.length}명`;
    }
    if (emptyElement) {
      emptyElement.hidden =
        (!query && !hasTravelFilter && !hasSummaryFilter) || visibleCount > 0;
    }
    persist();
    syncUrl();
  }

  function updateSummary(rows) {
    const counts = {
      total: rows.length,
      participating: 0,
      absent: 0,
      pending: 0,
      in: 0,
      out: 0,
    };
    rows.forEach((row) => {
      const participation = row.dataset.participation || "participating";
      if (participation === "absent") {
        counts.absent += 1;
        return;
      }
      counts.participating += 1;
      const status = row.dataset.checkIn || "pending";
      if (status === "checked_in") counts.in += 1;
      else if (status === "checked_out") counts.out += 1;
      else counts.pending += 1;
    });
    Object.entries(counts).forEach(([key, count]) => {
      const target = document.querySelector(
        `#retreatSummaryBar [data-summary-${key}]`
      );
      if (target) target.textContent = String(count);
    });
  }

  function persist() {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
        arrival: Array.from(selectedArrival),
        departure: Array.from(selectedDeparture),
        lodgingStay: Array.from(selectedLodgingStay),
      }));
    } catch (e) {}
  }

  function syncUrl() {
    const params = new URLSearchParams(location.search);
    if (selectedLodgingStay.size) {
      params.set("lodgingStay", Array.from(selectedLodgingStay).join(","));
    } else {
      params.delete("lodgingStay");
    }
    if (selectedSummaryPreset === "all") {
      params.delete("participation");
      params.delete("status");
    } else {
      const [kind, value] = selectedSummaryPreset.split(":");
      params.delete(kind === "status" ? "participation" : "status");
      params.set(kind, value);
    }
    const query = params.toString();
    history.replaceState(
      null,
      "",
      query ? `${location.pathname}?${query}` : location.pathname
    );
  }

  function restore() {
    try {
      const value = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "{}");
      (value.arrival || []).forEach((key) => selectedArrival.add(String(key)));
      (value.departure || []).forEach((key) => selectedDeparture.add(String(key)));
      (value.lodgingStay || []).forEach((key) =>
        selectedLodgingStay.add(String(key))
      );
    } catch (e) {}
  }

  function filterOptions(direction) {
    const presets = window.RETREAT_CTX?.travelPresets?.[direction] || [];
    const options = presets
      .filter((preset) => !preset.manual && preset.occurs_at)
      .map((preset) => ({ value: String(preset.id), label: preset.label }));
    if (presets.length) options.push({ value: "__custom__", label: "자차" });
    return options;
  }

  function makeChip(option, selected, wrap) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "jcc-retreat-filterChip";
    chip.textContent = option.label;
    function sync() {
      const active = selected.has(option.value);
      chip.classList.toggle("is-active", active);
      chip.setAttribute("aria-pressed", active ? "true" : "false");
    }
    chip.addEventListener("click", () => {
      if (selected.has(option.value)) selected.delete(option.value);
      else selected.add(option.value);
      sync();
      applySearch();
    });
    sync();
    wrap.appendChild(chip);
  }

  restore();
  const urlParams = new URLSearchParams(location.search);
  if (urlParams.has("lodgingStay")) {
    selectedLodgingStay.clear();
    (urlParams.get("lodgingStay") || "")
      .split(",")
      .filter(Boolean)
      .forEach((value) => selectedLodgingStay.add(value));
  }
  const participationParam = urlParams.get("participation");
  const statusParam = urlParams.get("status");
  if (participationParam === "participating" || participationParam === "absent") {
    selectedSummaryPreset = `participation:${participationParam}`;
  } else if (
    statusParam === "pending" ||
    statusParam === "checked_in" ||
    statusParam === "checked_out"
  ) {
    selectedSummaryPreset = `status:${statusParam}`;
  }
  const arrivalOptions = filterOptions("arrival");
  const departureOptions = filterOptions("departure");
  const arrivalValues = new Set(arrivalOptions.map((option) => option.value));
  const departureValues = new Set(departureOptions.map((option) => option.value));
  Array.from(selectedArrival).forEach((value) => {
    if (!arrivalValues.has(value)) selectedArrival.delete(value);
  });
  Array.from(selectedDeparture).forEach((value) => {
    if (!departureValues.has(value)) selectedDeparture.delete(value);
  });
  arrivalOptions.forEach((option) => makeChip(option, selectedArrival, arrivalWrap));
  departureOptions.forEach((option) => makeChip(option, selectedDeparture, departureWrap));
  const arrivalRow = arrivalWrap?.closest("[data-filter-row]");
  const departureRow = departureWrap?.closest("[data-filter-row]");
  if (arrivalRow) arrivalRow.hidden = arrivalOptions.length === 0;
  if (departureRow) departureRow.hidden = departureOptions.length === 0;
  const lodgingValues = new Set([
    "active",
    "unassigned",
    "ended",
    "no_stay",
    "absent",
  ]);
  Array.from(selectedLodgingStay).forEach((value) => {
    if (!lodgingValues.has(value)) selectedLodgingStay.delete(value);
  });
  lodgingWrap?.querySelectorAll("[data-filter-value]").forEach((chip) => {
    const value = chip.dataset.filterValue;
    function sync() {
      const active = selectedLodgingStay.has(value);
      chip.classList.toggle("is-active", active);
      chip.setAttribute("aria-pressed", active ? "true" : "false");
    }
    chip.addEventListener("click", () => {
      if (selectedLodgingStay.has(value)) selectedLodgingStay.delete(value);
      else selectedLodgingStay.add(value);
      sync();
      applySearch();
    });
    sync();
  });
  const summaryButtons = document.querySelectorAll("[data-group-summary-preset]");
  function syncSummaryButtons() {
    summaryButtons.forEach((button) => {
      const active = button.dataset.groupSummaryPreset === selectedSummaryPreset;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
  }
  summaryButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const preset = button.dataset.groupSummaryPreset || "all";
      selectedSummaryPreset =
        preset === selectedSummaryPreset && preset !== "all" ? "all" : preset;
      syncSummaryButtons();
      applySearch();
    });
  });
  syncSummaryButtons();
  if (filterBar) {
    filterBar.hidden = false;
  }
  resetButton?.addEventListener("click", () => {
    selectedArrival.clear();
    selectedDeparture.clear();
    selectedLodgingStay.clear();
    filterBar?.querySelectorAll(".jcc-retreat-filterChip").forEach((chip) => {
      chip.classList.remove("is-active");
      chip.setAttribute("aria-pressed", "false");
    });
    applySearch();
  });

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
    attributes: true,
    attributeFilter: [
      "data-expected-in-at",
      "data-expected-out-at",
      "data-arrival-travel-is-custom",
      "data-departure-travel-is-custom",
      "data-lodging-stay-status",
      "data-participation",
      "data-check-in",
    ],
  });

  applySearch();
})();
