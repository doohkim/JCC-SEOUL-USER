/**
 * 숙소 탭 전체 명단 — 칩 필터·이름 검색·컬럼 정렬·페이지네이션(20)
 */
(function () {
  "use strict";

  const tbody = document.getElementById("lodgingRosterBody");
  if (!tbody) return;

  const rows = Array.from(tbody.querySelectorAll("tr[data-attendee-id]"));
  if (rows.length === 0) return;

  const PAGE_SIZE = 20;
  const STORAGE_KEY = "retreatLodgingRosterFilter:" + location.pathname;
  const emptyMsg = document.getElementById("lodgingRosterFilterEmpty");
  const resetBtn = document.getElementById("rosterFilterReset");
  const searchInput = document.getElementById("rosterNameSearch");
  const filterBar = document.getElementById("lodgingRosterFilterBar");
  const regionsWrap = document.getElementById("rosterFilterRegions");
  const divisionsWrap = document.getElementById("rosterFilterDivisions");
  const regionRow = filterBar?.querySelector('[data-filter-row="region"]');
  const divisionRow = filterBar?.querySelector('[data-filter-row="division"]');
  const dateFromInput = document.getElementById("rosterDateFrom");
  const dateToInput = document.getElementById("rosterDateTo");
  const paginationBar = document.getElementById("lodgingRosterPagination");
  const paginationMeta = document.getElementById("lodgingRosterPaginationMeta");
  const paginationBtns = document.getElementById("lodgingRosterPaginationBtns");
  const sortHeaders = document.querySelectorAll(
    "#lodgingRosterTable .jcc-retreat-sortable[data-sort-key]"
  );

  const STATUS_ORDER = { pending: 0, checked_in: 1, checked_out: 2 };
  const ROLE_ORDER = {
    leader: 0,
    vice_leader: 1,
    teacher: 2,
    member: 3,
  };

  const selectedStatus = new Set();
  const selectedLodgingStay = new Set();
  const selectedGenders = new Set();
  const selectedNights = new Set();
  const selectedArrivalTravel = new Set();
  const selectedDepartureTravel = new Set();
  const selectedRegions = new Set();
  const selectedDivisions = new Set();
  const selectedMemo = new Set();
  const rosterTable = document.getElementById("lodgingRosterTable");
  let nameQuery = "";
  let dateFrom = "";
  let dateTo = "";
  let sortKey = null;
  let sortDir = "asc";
  let currentPage = 1;

  function memoFilterActive() {
    return selectedMemo.has("1");
  }

  function truncateMemoForDisplay(memo) {
    const full = String(memo || "").trim();
    if (!full) return "";
    if (memoFilterActive()) return full;
    return full.length > 5 ? full.slice(0, 5) + "…" : full;
  }

  function setMemoDisplay(memoEl, memo) {
    if (!memoEl) return;
    const full = String(memo || "").trim();
    memoEl.dataset.memoFull = full;
    if (full) {
      memoEl.title = full;
      memoEl.textContent = truncateMemoForDisplay(full);
      memoEl.hidden = false;
    } else {
      memoEl.removeAttribute("title");
      memoEl.textContent = "";
      memoEl.hidden = true;
    }
  }

  function syncRosterMemoDisplays() {
    rosterTable?.classList.toggle("is-memoFilterActive", memoFilterActive());
    rows.forEach((row) => {
      const memoEl = row.querySelector("[data-roster-memo]");
      setMemoDisplay(memoEl, row.dataset.memo || "");
    });
  }

  function distinctValues(attr) {
    const seen = [];
    const set = new Set();
    rows.forEach((row) => {
      const values = (row.getAttribute(attr) || "")
        .split("|")
        .map((value) => value.trim())
        .filter(Boolean);
      values.forEach((value) => {
        if (set.has(value)) return;
        set.add(value);
        seen.push(value);
      });
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
          lodgingStay: Array.from(selectedLodgingStay),
          genders: Array.from(selectedGenders),
          nights: Array.from(selectedNights),
          arrivalTravel: Array.from(selectedArrivalTravel),
          departureTravel: Array.from(selectedDepartureTravel),
          regions: Array.from(selectedRegions),
          divisions: Array.from(selectedDivisions),
          memo: Array.from(selectedMemo),
          name: nameQuery,
          dateFrom,
          dateTo,
          sortKey: sortKey,
          sortDir: sortDir,
          page: currentPage,
        })
      );
    } catch (e) {}
  }

  function syncUrl() {
    const params = new URLSearchParams();
    if (selectedStatus.size) params.set("status", Array.from(selectedStatus).join(","));
    if (selectedLodgingStay.size) {
      params.set("lodgingStay", Array.from(selectedLodgingStay).join(","));
    }
    if (selectedGenders.size) params.set("gender", Array.from(selectedGenders).join(","));
    if (selectedNights.size) params.set("nights", Array.from(selectedNights).join(","));
    if (selectedArrivalTravel.size) {
      params.set("arrivalTravel", Array.from(selectedArrivalTravel).join(","));
    }
    if (selectedDepartureTravel.size) {
      params.set("departureTravel", Array.from(selectedDepartureTravel).join(","));
    }
    if (selectedRegions.size) params.set("region", Array.from(selectedRegions).join(","));
    if (selectedDivisions.size) params.set("division", Array.from(selectedDivisions).join(","));
    if (dateFrom) params.set("dateFrom", dateFrom);
    if (dateTo) params.set("dateTo", dateTo);
    if (selectedMemo.size) params.set("memo", Array.from(selectedMemo).join(","));
    if (nameQuery.trim()) params.set("q", nameQuery.trim());
    if (sortKey) {
      params.set("sort", sortKey);
      params.set("dir", sortDir);
    }
    if (currentPage > 1) params.set("page", String(currentPage));
    const qs = params.toString();
    const next = qs ? `${location.pathname}?${qs}` : location.pathname;
    window.history.replaceState(null, "", next);
  }

  function applyLegacyParams(params) {
    const stayParam = params.get("stay");
    const assignParam = params.get("assign");
    const lodgingParam = params.get("lodging");

    if (stayParam) {
      stayParam.split(",").filter(Boolean).forEach((v) => {
        if (v === "eligible") {
          selectedLodgingStay.add("active");
          selectedLodgingStay.add("unassigned");
        } else if (v === "ineligible" || v === "na") {
          selectedLodgingStay.add("ended");
          selectedLodgingStay.add("no_stay");
          selectedLodgingStay.add("absent");
        }
      });
    }
    if (assignParam) {
      assignParam.split(",").filter(Boolean).forEach((v) => {
        if (v === "assigned") selectedLodgingStay.add("active");
        if (v === "unassigned") selectedLodgingStay.add("unassigned");
      });
    }
    if (lodgingParam) {
      lodgingParam.split(",").filter(Boolean).forEach((v) => {
        if (v === "assigned") selectedLodgingStay.add("active");
        if (v === "unassigned") selectedLodgingStay.add("unassigned");
        if (v === "eligible") {
          selectedLodgingStay.add("active");
          selectedLodgingStay.add("unassigned");
        }
        if (v === "na" || v === "ineligible") {
          selectedLodgingStay.add("ended");
          selectedLodgingStay.add("no_stay");
          selectedLodgingStay.add("absent");
        }
      });
    }
  }

  function phoneDigits(value) {
    return (value || "").replace(/\D/g, "");
  }

  function rowMatches(row) {
    const status = row.dataset.checkInStatus || "";
    const lodgingStay = row.dataset.lodgingStayStatus || "";
    const arrivalTravel = row.dataset.arrivalTravel || "";
    const departureTravel = row.dataset.departureTravel || "";
    const gender = row.dataset.gender || "__unset__";
    const nights = row.dataset.lodgingNights || "0";
    const regions = (row.dataset.regionNames || "").split("|").filter(Boolean);
    const divisions = (row.dataset.divisionNames || "").split("|").filter(Boolean);
    const name = (row.dataset.name || "").toLowerCase();
    const phone = row.dataset.phone || "";

    if (selectedStatus.size > 0 && !selectedStatus.has(status)) return false;
    if (selectedGenders.size > 0 && !selectedGenders.has(gender)) return false;
    if (selectedNights.size > 0) {
      const nightCount = Number(nights);
      const matchesExact = selectedNights.has(nights);
      const matchesTwoOrMore =
        selectedNights.has("2") &&
        Number.isFinite(nightCount) &&
        nightCount >= 2;
      if (!matchesExact && !matchesTwoOrMore) return false;
    }
    if (selectedLodgingStay.size > 0 && !selectedLodgingStay.has(lodgingStay)) {
      return false;
    }
    if (
      selectedArrivalTravel.size > 0 &&
      !selectedArrivalTravel.has(arrivalTravel)
    ) {
      return false;
    }
    if (
      selectedDepartureTravel.size > 0 &&
      !selectedDepartureTravel.has(departureTravel)
    ) {
      return false;
    }
    if (
      selectedRegions.size > 0 &&
      !regions.some((region) => selectedRegions.has(region))
    ) return false;
    if (
      selectedDivisions.size > 0 &&
      !divisions.some((division) => selectedDivisions.has(division))
    ) return false;
    if (dateFrom || dateTo) {
      const startsAt = parseIsoTime(row.dataset.expectedInAt);
      const endsAt = parseIsoTime(row.dataset.expectedOutAt);
      if (startsAt === null || endsAt === null) return false;
      const rangeStart = dateFrom ? new Date(`${dateFrom}T00:00:00`).getTime() : -Infinity;
      const rangeEnd = dateTo ? new Date(`${dateTo}T23:59:59.999`).getTime() : Infinity;
      if (startsAt > rangeEnd || endsAt < rangeStart) return false;
    }
    if (memoFilterActive()) {
      const memo = (row.dataset.memo || "").trim();
      if (!memo) return false;
    }
    if (nameQuery.trim()) {
      const q = nameQuery.trim().toLowerCase();
      const qDigits = phoneDigits(q);
      const nameMatch = name.includes(q);
      const phoneMatch = qDigits.length > 0 && phoneDigits(phone).includes(qDigits);
      if (!nameMatch && !phoneMatch) return false;
    }
    return true;
  }

  function parseIsoTime(value) {
    if (!value) return null;
    const parsed = new Date(value).getTime();
    return Number.isNaN(parsed) ? null : parsed;
  }

  function sortValue(row, key) {
    switch (key) {
      case "group":
        return (row.dataset.groupName || "").trim();
      case "name":
        return (row.dataset.name || "").trim();
      case "role":
        return ROLE_ORDER[row.dataset.memberRole] ?? 99;
      case "status":
        return STATUS_ORDER[row.dataset.checkInStatus] ?? 99;
      case "expectedIn": {
        const iso = row.dataset.expectedInAt || "";
        if (!iso) return Number.POSITIVE_INFINITY;
        const t = new Date(iso).getTime();
        return Number.isNaN(t) ? Number.POSITIVE_INFINITY : t;
      }
      case "expectedOut": {
        const iso = row.dataset.expectedOutAt || "";
        if (!iso) return Number.POSITIVE_INFINITY;
        const t = new Date(iso).getTime();
        return Number.isNaN(t) ? Number.POSITIVE_INFINITY : t;
      }
      case "lodging":
        return (row.dataset.lodgingSort || "").trim();
      case "nights":
        return Number(row.dataset.lodgingNights || 0);
      default:
        return 0;
    }
  }

  function compareRows(a, b, key) {
    const va = sortValue(a, key);
    const vb = sortValue(b, key);
    if (typeof va === "number" && typeof vb === "number") {
      return va - vb;
    }
    return String(va).localeCompare(String(vb), "ko", { numeric: true });
  }

  function sortedMatchedRows() {
    const matched = rows.filter(rowMatches);
    if (!sortKey) return matched;
    const factor = sortDir === "desc" ? -1 : 1;
    return matched.slice().sort((a, b) => {
      const c = compareRows(a, b, sortKey);
      if (c !== 0) return c * factor;
      const na = (a.dataset.name || "").trim();
      const nb = (b.dataset.name || "").trim();
      return na.localeCompare(nb, "ko");
    });
  }

  function syncSortHeaderStates() {
    sortHeaders.forEach((th) => {
      if (th.dataset.sortKey === sortKey) {
        th.dataset.sortDir = sortDir;
        th.setAttribute(
          "aria-sort",
          sortDir === "asc" ? "ascending" : "descending"
        );
      } else {
        delete th.dataset.sortDir;
        th.setAttribute("aria-sort", "none");
      }
    });
  }

  function renderPagination(total, totalPages) {
    if (!paginationBar || !paginationBtns || !paginationMeta) return;
    if (total === 0) {
      paginationBar.hidden = true;
      paginationBtns.innerHTML = "";
      paginationMeta.textContent = "";
      return;
    }
    paginationBar.hidden = false;
    const start = (currentPage - 1) * PAGE_SIZE + 1;
    const end = Math.min(currentPage * PAGE_SIZE, total);
    paginationMeta.textContent = `${start}–${end} / 총 ${total}건 · ${PAGE_SIZE}개씩`;

    if (totalPages <= 1) {
      paginationBtns.innerHTML = "";
      return;
    }

    const frag = document.createDocumentFragment();

    function addBtn(label, page, opts) {
      const { disabled, active, arrow } = opts || {};
      const el = document.createElement(disabled || active ? "span" : "button");
      el.className = "jcc-notice-pageBtn";
      if (arrow) el.classList.add("jcc-notice-pageBtn--arrow");
      if (disabled) el.classList.add("is-disabled");
      if (active) {
        el.classList.add("is-active");
        el.setAttribute("aria-current", "page");
      }
      el.textContent = label;
      if (!disabled && !active) {
        el.type = "button";
        el.addEventListener("click", () => {
          currentPage = page;
          applyView({ resetPage: false });
        });
      }
      frag.appendChild(el);
    }

    addBtn("‹", currentPage - 1, {
      arrow: true,
      disabled: currentPage <= 1,
    });

    const windowStart = Math.max(1, currentPage - 2);
    const windowEnd = Math.min(totalPages, currentPage + 2);
    for (let n = windowStart; n <= windowEnd; n += 1) {
      addBtn(String(n), n, { active: n === currentPage });
    }

    addBtn("›", currentPage + 1, {
      arrow: true,
      disabled: currentPage >= totalPages,
    });

    paginationBtns.innerHTML = "";
    paginationBtns.appendChild(frag);
  }

  function applyView({ resetPage = false } = {}) {
    if (resetPage) currentPage = 1;

    const matched = sortedMatchedRows();
    matched.forEach((row) => tbody.appendChild(row));

    rows.forEach((row) => {
      row.hidden = true;
    });

    const total = matched.length;
    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE) || 1);
    if (currentPage > totalPages) currentPage = totalPages;
    if (currentPage < 1) currentPage = 1;

    const startIdx = (currentPage - 1) * PAGE_SIZE;
    const pageRows = matched.slice(startIdx, startIdx + PAGE_SIZE);
    pageRows.forEach((row, i) => {
      row.hidden = false;
      const cell = row.querySelector("[data-row-num]");
      if (cell) cell.textContent = String(startIdx + i + 1);
    });
    tbody.classList.remove("is-initializing");

    renderPagination(total, totalPages);
    syncSortHeaderStates();
    syncRosterMemoDisplays();
    updateSummary(matched);

    const hasFilter =
      selectedStatus.size > 0 ||
      selectedLodgingStay.size > 0 ||
      selectedGenders.size > 0 ||
      selectedNights.size > 0 ||
      selectedArrivalTravel.size > 0 ||
      selectedDepartureTravel.size > 0 ||
      selectedRegions.size > 0 ||
      selectedDivisions.size > 0 ||
      selectedMemo.size > 0 ||
      !!dateFrom ||
      !!dateTo ||
      !!nameQuery.trim();
    if (resetBtn) resetBtn.disabled = !hasFilter && !sortKey && currentPage === 1;
    if (emptyMsg) emptyMsg.hidden = total > 0 || rows.length === 0;
    persist();
    syncUrl();
  }

  function updateSummary(matched) {
    const setText = (selector, count) => {
      const el = document.querySelector(selector);
      if (el) el.textContent = String(count);
    };
    setText("[data-summary-total]", matched.length);
    setText("[data-summary-pending]", matched.filter((row) => row.dataset.checkInStatus === "pending").length);
    setText("[data-summary-in]", matched.filter((row) => row.dataset.checkInStatus === "checked_in").length);
    setText("[data-summary-out]", matched.filter((row) => row.dataset.checkInStatus === "checked_out").length);
    setText("[data-summary-eligible]", matched.filter((row) => ["active", "unassigned"].includes(row.dataset.lodgingStayStatus)).length);
    setText("[data-summary-unassigned]", matched.filter((row) => row.dataset.lodgingStayStatus === "unassigned").length);
  }

  function applyFilter() {
    applyView({ resetPage: true });
  }

  function setChipActive(chip, active) {
    chip.classList.toggle("is-active", active);
    chip.setAttribute("aria-pressed", active ? "true" : "false");
  }

  function chipSetForKind(kind) {
    if (kind === "status") return selectedStatus;
    if (kind === "lodgingStay") return selectedLodgingStay;
    if (kind === "gender") return selectedGenders;
    if (kind === "nights") return selectedNights;
    if (kind === "arrivalTravel") return selectedArrivalTravel;
    if (kind === "departureTravel") return selectedDepartureTravel;
    if (kind === "region") return selectedRegions;
    if (kind === "division") return selectedDivisions;
    if (kind === "memo") return selectedMemo;
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

  const regionValues = distinctValues("data-region-names");
  const divisionValues = distinctValues("data-division-names");
  if (regionsWrap && regionValues.length >= 1) {
    regionValues.forEach((v) => makeDynamicChip(v, selectedRegions, regionsWrap));
    if (regionRow) regionRow.hidden = false;
  }
  if (divisionsWrap && divisionValues.length >= 1) {
    divisionValues.forEach((v) =>
      makeDynamicChip(v, selectedDivisions, divisionsWrap)
    );
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
    selectedLodgingStay.clear();
    selectedGenders.clear();
    selectedNights.clear();
    selectedArrivalTravel.clear();
    selectedDepartureTravel.clear();
    selectedRegions.clear();
    selectedDivisions.clear();
    selectedMemo.clear();
    nameQuery = "";
    dateFrom = "";
    dateTo = "";
    sortKey = null;
    sortDir = "asc";
    if (searchInput) searchInput.value = "";
    if (dateFromInput) dateFromInput.value = "";
    if (dateToInput) dateToInput.value = "";

    if (preset && preset !== "all") {
      const [kind, value] = preset.split(":");
      if (kind === "status" && value) selectedStatus.add(value);
      if (kind === "lodgingStay" && value) selectedLodgingStay.add(value);
      if (kind === "memo" && value) selectedMemo.add(value);
      if (kind === "stay" && value === "eligible") {
        selectedLodgingStay.add("active");
        selectedLodgingStay.add("unassigned");
      }
      if (kind === "assign" && value === "unassigned") {
        selectedLodgingStay.add("unassigned");
      }
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
  [dateFromInput, dateToInput].forEach((input) => {
    input?.addEventListener("change", () => {
      dateFrom = dateFromInput?.value || "";
      dateTo = dateToInput?.value || "";
      if (dateFrom && dateTo && dateFrom > dateTo) {
        if (input === dateFromInput) dateTo = dateFrom;
        else dateFrom = dateTo;
        if (dateFromInput) dateFromInput.value = dateFrom;
        if (dateToInput) dateToInput.value = dateTo;
      }
      applyFilter();
    });
  });

  if (resetBtn) {
    resetBtn.addEventListener("click", () => applyPreset("all"));
  }

  sortHeaders.forEach((th) => {
    th.addEventListener("click", (e) => {
      e.preventDefault();
      const key = th.dataset.sortKey;
      if (!key) return;
      if (sortKey === key) {
        sortDir = sortDir === "asc" ? "desc" : "asc";
      } else {
        sortKey = key;
        sortDir = "asc";
      }
      applyView({ resetPage: true });
    });
  });

  const SORT_KEYS = new Set([
    "group",
    "name",
    "role",
    "status",
    "expectedIn",
    "expectedOut",
    "lodging",
    "nights",
  ]);

  function initFromUrlOrStorage() {
    const params = new URLSearchParams(location.search);
    const stored = loadStored();

    const statusParam = params.get("status") || (stored && stored.status?.join(","));
    const lodgingStayParam =
      params.get("lodgingStay") || (stored && stored.lodgingStay?.join(","));
    const genderParam = params.get("gender") || (stored && stored.genders?.join(","));
    const nightsParam = params.get("nights") || (stored && stored.nights?.join(","));
    const arrivalTravelParam =
      params.get("arrivalTravel") || (stored && stored.arrivalTravel?.join(","));
    const departureTravelParam =
      params.get("departureTravel") || (stored && stored.departureTravel?.join(","));
    const regionParam = params.get("region") || (stored && stored.regions?.join(","));
    const divisionParam =
      params.get("division") || (stored && stored.divisions?.join(","));
    const memoParam = params.get("memo") || (stored && stored.memo?.join(","));
    const qParam = params.get("q") || (stored && stored.name) || "";
    dateFrom = params.get("dateFrom") || (stored && stored.dateFrom) || "";
    dateTo = params.get("dateTo") || (stored && stored.dateTo) || "";
    const sortParam = params.get("sort") || (stored && stored.sortKey) || "";
    const dirParam = params.get("dir") || (stored && stored.sortDir) || "asc";
    const pageParam = params.get("page") || (stored && stored.page) || "1";

    if (statusParam) statusParam.split(",").filter(Boolean).forEach((v) => selectedStatus.add(v));
    if (genderParam) genderParam.split(",").filter(Boolean).forEach((v) => selectedGenders.add(v));
    if (nightsParam) {
      nightsParam
        .split(",")
        .filter(Boolean)
        .forEach((value) => {
          const count = Number(value);
          if (value === "0" || value === "1") selectedNights.add(value);
          else if (Number.isFinite(count) && count >= 2) selectedNights.add("2");
        });
    }
    if (lodgingStayParam) {
      lodgingStayParam.split(",").filter(Boolean).forEach((v) => selectedLodgingStay.add(v));
    } else {
      applyLegacyParams(params);
      if (stored && stored.stay) {
        stored.stay.forEach((v) => {
          if (v === "eligible") {
            selectedLodgingStay.add("active");
            selectedLodgingStay.add("unassigned");
          } else if (v === "ineligible") {
            selectedLodgingStay.add("ended");
            selectedLodgingStay.add("no_stay");
            selectedLodgingStay.add("absent");
          }
        });
      }
      if (stored && stored.assign) {
        stored.assign.forEach((v) => {
          if (v === "assigned") selectedLodgingStay.add("active");
          if (v === "unassigned") selectedLodgingStay.add("unassigned");
        });
      }
    }
    if (arrivalTravelParam) {
      arrivalTravelParam
        .split(",")
        .filter(Boolean)
        .forEach((v) => selectedArrivalTravel.add(v));
    }
    if (departureTravelParam) {
      departureTravelParam
        .split(",")
        .filter(Boolean)
        .forEach((v) => selectedDepartureTravel.add(v));
    }
    if (regionParam) {
      regionParam.split(",").filter(Boolean).forEach((v) => selectedRegions.add(v));
    }
    if (divisionParam) {
      divisionParam
        .split(",")
        .filter(Boolean)
        .forEach((v) => selectedDivisions.add(v));
    }
    if (memoParam) {
      memoParam.split(",").filter(Boolean).forEach((v) => {
        if (v === "1") selectedMemo.add("1");
      });
    }
    nameQuery = qParam;
    if (searchInput && nameQuery) searchInput.value = nameQuery;
    if (dateFromInput) dateFromInput.value = dateFrom;
    if (dateToInput) dateToInput.value = dateTo;

    if (SORT_KEYS.has(sortParam)) {
      sortKey = sortParam;
      sortDir = dirParam === "desc" ? "desc" : "asc";
    }
    const parsedPage = parseInt(String(pageParam), 10);
    currentPage = Number.isFinite(parsedPage) && parsedPage > 0 ? parsedPage : 1;

    syncChipStates();
    applyView({ resetPage: false });
  }

  window.JccRetreatLodgingRosterFilter = {
    refreshAfterRowEdit() {
      syncRosterMemoDisplays();
      applyView({ resetPage: false });
    },
    setMemoDisplay,
  };

  initFromUrlOrStorage();
})();
