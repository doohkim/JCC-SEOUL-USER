/**
 * 숙소 관리 페이지 — 숙소/객실 CRUD 모달
 */
(function () {
  "use strict";

  const ctx = window.RETREAT_LODGING_CTX;
  if (!ctx) return;

  const toastEl = document.getElementById("retreatToast");
  const statusLineEl = document.getElementById("retreatStatus");

  // 숙소 모달
  const lodgingOverlay = document.getElementById("lodgingModalOverlay");
  const lodgingForm = document.getElementById("lodgingForm");
  const lodgingTitle = document.getElementById("lodgingModalTitle");
  const lodgingSubmit = document.getElementById("lodgingModalSubmit");
  const lodgingCancel = document.getElementById("lodgingModalCancel");
  const lodgingNameInput = document.getElementById("lodgingNameInput");
  const lodgingRegionInput = document.getElementById("lodgingRegionInput");
  const lodgingAddressInput = document.getElementById("lodgingAddressInput");
  const lodgingMemoInput = document.getElementById("lodgingMemoInput");

  // 객실 모달
  const roomOverlay = document.getElementById("roomModalOverlay");
  const roomForm = document.getElementById("roomForm");
  const roomTitle = document.getElementById("roomModalTitle");
  const roomSubmit = document.getElementById("roomModalSubmit");
  const roomCancel = document.getElementById("roomModalCancel");
  const roomClose = document.getElementById("roomModalClose");
  const roomNumberInput = document.getElementById("roomNumberInput");
  const roomCapacityInput = document.getElementById("roomCapacityInput");
  const roomDivisionInput = document.getElementById("roomDivisionInput");
  const roomGroupInput = document.getElementById("roomGroupInput");
  const roomGenderInputs = Array.from(
    document.querySelectorAll('input[name="recommended_gender"]')
  );
  const roomMemoInput = document.getElementById("roomMemoInput");

  function selectMultiple(select, values) {
    if (!select) return;
    const selected = new Set((values || []).map(String));
    Array.from(select.options).forEach((option) => {
      option.selected = selected.has(option.value);
    });
  }

  function selectedIds(select) {
    if (!select) return [];
    return Array.from(select.selectedOptions).map((option) => Number(option.value));
  }

  function setRoomGender(value) {
    roomGenderInputs.forEach((input) => {
      input.checked = input.value === value;
    });
  }

  function getRoomGender() {
    return roomGenderInputs.find((input) => input.checked)?.value || "";
  }

  function syncTargetCheckboxes() {
    document.querySelectorAll("[data-room-scope-checkbox]").forEach((checkbox) => {
      checkbox.checked = Array.from(roomDivisionInput?.selectedOptions || []).some(
        (option) => option.value === checkbox.value
      );
    });
    document.querySelectorAll("[data-room-group-checkbox]").forEach((checkbox) => {
      checkbox.checked = Array.from(roomGroupInput?.selectedOptions || []).some(
        (option) => option.value === checkbox.value
      );
    });
    updateTargetSummary();
  }

  function syncSelectFromCheckboxes(select, selector) {
    const values = new Set(
      Array.from(document.querySelectorAll(selector))
        .filter((checkbox) => checkbox.checked)
        .map((checkbox) => checkbox.value)
    );
    Array.from(select?.options || []).forEach((option) => {
      option.selected = values.has(option.value);
    });
    updateTargetSummary();
  }

  function updateTargetSummary() {
    const divisionCount = document.querySelectorAll(
      "[data-room-scope-checkbox]:checked"
    ).length;
    const groupCount = document.querySelectorAll(
      "[data-room-group-checkbox]:checked"
    ).length;
    document.querySelectorAll("[data-room-target-panel]").forEach((panel) => {
      const kind = panel.dataset.roomTargetPanel;
      const count = kind === "division" ? divisionCount : groupCount;
      const countEl = panel.querySelector("[data-room-target-count]");
      if (countEl) countEl.textContent = `${count}개 선택`;
      panel.classList.toggle("has-selection", count > 0);
    });
    const summary = document.querySelector("[data-room-target-summary]");
    const summaryBox = document.getElementById("roomTargetSummary");
    if (!summary) return;
    if (divisionCount && groupCount) {
      summary.textContent = `선택한 지역·부서 ${divisionCount}개와 조 ${groupCount}개의 교집합에만 노출됩니다.`;
      summaryBox?.classList.add("is-active");
    } else if (divisionCount) {
      summary.textContent = `선택한 지역·부서 ${divisionCount}개의 모든 조에 노출됩니다.`;
      summaryBox?.classList.add("is-active");
    } else if (groupCount) {
      summary.textContent = `지역·부서와 관계없이 선택한 조 ${groupCount}개에만 노출됩니다.`;
      summaryBox?.classList.add("is-active");
    } else {
      summary.textContent = "대상을 선택하지 않으면 미배정 객실로 저장됩니다.";
      summaryBox?.classList.remove("is-active");
    }
  }

  let lodgingMode = "create";
  let lodgingTargetId = null;
  let roomMode = "create";
  let roomTargetLodgingId = null;
  let roomTargetId = null;

  function showToast(message, isError) {
    if (!toastEl) {
      if (statusLineEl) statusLineEl.textContent = message || "";
      return;
    }
    toastEl.textContent = message || "";
    toastEl.hidden = false;
    toastEl.classList.toggle("is-error", !!isError);
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => {
      toastEl.hidden = true;
    }, 2200);
  }

  function openLodgingModal(mode, payload) {
    if (!lodgingOverlay) return;
    lodgingMode = mode;
    lodgingTargetId = payload?.id || null;
    if (lodgingTitle) {
      lodgingTitle.textContent = mode === "edit" ? "숙소 수정" : "숙소 추가";
    }
    if (lodgingSubmit) lodgingSubmit.textContent = mode === "edit" ? "수정" : "저장";
    if (lodgingNameInput) lodgingNameInput.value = payload?.name || "";
    if (lodgingRegionInput)
      lodgingRegionInput.value = payload?.region != null ? String(payload.region) : "";
    if (lodgingAddressInput) lodgingAddressInput.value = payload?.address || "";
    if (lodgingMemoInput) lodgingMemoInput.value = payload?.memo || "";
    if (window.JccCustomSelect) window.JccCustomSelect.refresh(document);
    lodgingOverlay.hidden = false;
    lodgingOverlay.setAttribute("aria-hidden", "false");
    requestAnimationFrame(() => lodgingNameInput?.focus());
  }

  function closeLodgingModal() {
    if (!lodgingOverlay) return;
    lodgingOverlay.hidden = true;
    lodgingOverlay.setAttribute("aria-hidden", "true");
    lodgingTargetId = null;
  }

  function openRoomModal(mode, lodgingId, payload) {
    if (!roomOverlay) return;
    roomMode = mode;
    roomTargetLodgingId = lodgingId || null;
    roomTargetId = payload?.id || null;
    if (roomTitle) roomTitle.textContent = mode === "edit" ? "객실 수정" : "객실 추가";
    if (roomSubmit) roomSubmit.textContent = mode === "edit" ? "수정" : "저장";
    if (roomNumberInput) roomNumberInput.value = payload?.number || "";
    if (roomCapacityInput) {
      const capDefault = mode === "create" ? 1 : 0;
      roomCapacityInput.value =
        payload?.capacity != null ? payload.capacity : capDefault;
    }
    selectMultiple(roomDivisionInput, payload?.scope_divisions || []);
    selectMultiple(roomGroupInput, payload?.target_groups || []);
    syncTargetCheckboxes();
    document.querySelectorAll("[data-room-target-panel]").forEach((panel) => {
      const search = panel.querySelector("[data-room-target-search]");
      if (search) search.value = "";
      panel.querySelectorAll(".jcc-retreat-roomTargetOption").forEach((option) => {
        option.hidden = false;
      });
      const empty = panel.querySelector("[data-room-target-empty]");
      if (empty) empty.hidden = true;
    });
    setRoomGender(payload?.recommended_gender || "");
    if (roomMemoInput) roomMemoInput.value = payload?.memo || "";
    if (window.JccCustomSelect) window.JccCustomSelect.refresh(document);
    roomOverlay.hidden = false;
    roomOverlay.setAttribute("aria-hidden", "false");
    requestAnimationFrame(() => roomNumberInput?.focus());
  }

  function closeRoomModal() {
    if (!roomOverlay) return;
    roomOverlay.hidden = true;
    roomOverlay.setAttribute("aria-hidden", "true");
    roomTargetLodgingId = null;
    roomTargetId = null;
  }

  async function api(url, method, body) {
    const opts = {
      method,
      headers: {
        "X-CSRFToken": ctx.csrfToken,
      },
      credentials: "same-origin",
    };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const r = await fetch(url, opts);
    if (!r.ok && r.status !== 204) {
      let detail = "요청 실패";
      try {
        const j = await r.json();
        detail = j.detail || JSON.stringify(j);
      } catch (e) {}
      throw new Error(detail);
    }
    if (r.status === 204) return null;
    return r.json();
  }

  function bindOverlayDismiss(overlay, closeFn) {
    if (!overlay) return;
    let downOnOverlay = false;
    overlay.addEventListener("pointerdown", (e) => {
      downOnOverlay = e.target === overlay;
    });
    overlay.addEventListener("click", (e) => {
      if (downOnOverlay && e.target === overlay) closeFn();
      downOnOverlay = false;
    });
  }

  function bindLodgingModal() {
    const addBtn = document.getElementById("btnAddLodging");
    if (addBtn) addBtn.addEventListener("click", () => openLodgingModal("create"));
    if (lodgingCancel) lodgingCancel.addEventListener("click", closeLodgingModal);
    bindOverlayDismiss(lodgingOverlay, closeLodgingModal);
    if (lodgingForm) lodgingForm.addEventListener("submit", onLodgingSubmit);
  }

  function bindRoomModal() {
    if (roomCancel) roomCancel.addEventListener("click", closeRoomModal);
    if (roomClose) roomClose.addEventListener("click", closeRoomModal);
    bindOverlayDismiss(roomOverlay, closeRoomModal);
    document.querySelectorAll("[data-room-scope-checkbox]").forEach((checkbox) => {
      checkbox.addEventListener("change", () => {
        syncSelectFromCheckboxes(
          roomDivisionInput,
          "[data-room-scope-checkbox]"
        );
      });
    });
    document.querySelectorAll("[data-room-group-checkbox]").forEach((checkbox) => {
      checkbox.addEventListener("change", () => {
        syncSelectFromCheckboxes(roomGroupInput, "[data-room-group-checkbox]");
      });
    });
    document.querySelectorAll("[data-room-target-panel]").forEach((panel) => {
      const search = panel.querySelector("[data-room-target-search]");
      const options = Array.from(
        panel.querySelectorAll(".jcc-retreat-roomTargetOption")
      );
      const empty = panel.querySelector("[data-room-target-empty]");
      search?.addEventListener("input", () => {
        const query = search.value.trim().toLocaleLowerCase();
        let visible = 0;
        options.forEach((option) => {
          const matched = (option.dataset.searchText || "")
            .toLocaleLowerCase()
            .includes(query);
          option.hidden = !matched;
          if (matched) visible += 1;
        });
        if (empty) empty.hidden = visible !== 0;
      });
      panel.querySelector("[data-room-target-clear]")?.addEventListener("click", () => {
        options.forEach((option) => {
          const checkbox = option.querySelector("input[type='checkbox']");
          if (checkbox) checkbox.checked = false;
        });
        const kind = panel.dataset.roomTargetPanel;
        syncSelectFromCheckboxes(
          kind === "division" ? roomDivisionInput : roomGroupInput,
          kind === "division"
            ? "[data-room-scope-checkbox]"
            : "[data-room-group-checkbox]"
        );
      });
      panel
        .querySelector("[data-room-target-select-visible]")
        ?.addEventListener("click", () => {
          options.forEach((option) => {
            if (option.hidden) return;
            const checkbox = option.querySelector("input[type='checkbox']");
            if (checkbox) checkbox.checked = true;
          });
          const kind = panel.dataset.roomTargetPanel;
          syncSelectFromCheckboxes(
            kind === "division" ? roomDivisionInput : roomGroupInput,
            kind === "division"
              ? "[data-room-scope-checkbox]"
              : "[data-room-group-checkbox]"
          );
        });
    });
    if (roomForm) roomForm.addEventListener("submit", onRoomSubmit);
    roomOverlay?.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeRoomModal();
    });
  }

  function getRoomPayloadFromRow(tr) {
    const number =
      tr.dataset.roomNumber ||
      tr.querySelector("[data-room-number]")?.textContent?.trim() ||
      "";
    const capTxt = tr.querySelector("[data-room-capacity]")?.textContent?.trim() || "0";
    const cap = capTxt === "무제한" ? 0 : Number(capTxt);
    const genderText =
      tr.querySelector("[data-room-gender]")?.textContent?.trim() || "";
    const genderCode =
      {
        남성: "male",
        여성: "female",
      }[genderText] || "";
    const scopeDivisions = (tr.dataset.roomScopeIds || "")
      .split(",")
      .filter(Boolean)
      .map(Number);
    const targetGroups = (tr.dataset.roomGroupIds || "")
      .split(",")
      .filter(Boolean)
      .map(Number);
    return {
      id: Number(tr.dataset.roomId),
      number,
      capacity: cap,
      recommended_gender: genderCode,
      scope_divisions: scopeDivisions,
      target_groups: targetGroups,
    };
  }

  const COLLAPSE_STORAGE_KEY =
    "retreatLodgingCollapsed:" + location.pathname;

  function loadCollapsedIds() {
    try {
      const raw = sessionStorage.getItem(COLLAPSE_STORAGE_KEY);
      if (!raw) return new Set();
      const arr = JSON.parse(raw);
      return new Set(Array.isArray(arr) ? arr.map(String) : []);
    } catch (e) {
      return new Set();
    }
  }

  function persistCollapsedIds(ids) {
    try {
      sessionStorage.setItem(
        COLLAPSE_STORAGE_KEY,
        JSON.stringify(Array.from(ids))
      );
    } catch (e) {}
  }

  function setLodgingCollapsed(card, toggle, collapsed, collapsedIds) {
    card.classList.toggle("is-collapsed", collapsed);
    toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
    const id = String(card.dataset.lodgingId || "");
    if (!id) return;
    if (collapsed) collapsedIds.add(id);
    else collapsedIds.delete(id);
  }

  /** 숙소 카드 접기/펼치기 (조 참석현황 부서 접기와 동일 UX) */
  function bindLodgingCollapse() {
    const collapsedIds = loadCollapsedIds();
    document.querySelectorAll(".jcc-retreat-lodgingCard").forEach((card) => {
      const toggle = card.querySelector("[data-lodging-toggle]");
      if (!toggle) return;
      const id = String(card.dataset.lodgingId || "");
      const collapsed = id && collapsedIds.has(id);
      setLodgingCollapsed(card, toggle, collapsed, collapsedIds);
      toggle.addEventListener("click", () => {
        const nowCollapsed = !card.classList.contains("is-collapsed");
        setLodgingCollapsed(card, toggle, nowCollapsed, collapsedIds);
        persistCollapsedIds(collapsedIds);
      });
    });
  }

  function bindLodgingActions() {
    document.querySelectorAll(".jcc-retreat-lodgingCard").forEach((card) => {
      const lid = Number(card.dataset.lodgingId);
      const editLodging = card.querySelector("[data-edit-lodging]");
      const delLodging = card.querySelector("[data-del-lodging]");
      const addRoom = card.querySelector("[data-add-room]");
      const name = card.querySelector("[data-lodging-name]")?.textContent?.trim() || "";
      const address =
        card.querySelector("[data-lodging-address]")?.textContent?.trim() || "";
      const memo = card.querySelector("[data-lodging-memo]")?.textContent?.trim() || "";

      const regionEl = card.querySelector("[data-lodging-region-id]");
      const regionId = (regionEl?.dataset?.lodgingRegionId || "").trim();
      if (editLodging) {
        editLodging.addEventListener("click", (e) => {
          e.stopPropagation();
          openLodgingModal("edit", {
            id: lid,
            name,
            region: regionId ? Number(regionId) : "",
            address,
            memo,
          });
        });
      }
      if (delLodging) {
        delLodging.addEventListener("click", (e) => {
          e.stopPropagation();
          confirmDeleteLodging(lid);
        });
      }
      if (addRoom) {
        addRoom.addEventListener("click", () => openRoomModal("create", lid));
      }
    });
    bindRoomRowClicks();
  }

  function bindRoomRowClicks() {
    if (!ctx.canManage) return;
    document
      .querySelectorAll("tr.jcc-retreat-roomRow--clickable[data-room-id]")
      .forEach((tr) => {
        const lid = Number(tr.dataset.lodgingId);
        const rid = Number(tr.dataset.roomId);
        const delBtn = tr.querySelector("[data-del-room]");
        if (delBtn) {
          delBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            confirmDeleteRoom(rid);
          });
        }
        const openEdit = () => {
          const sel = window.getSelection?.();
          if (sel && sel.toString().trim()) return;
          openRoomModal("edit", lid, getRoomPayloadFromRow(tr));
        };
        tr.addEventListener("click", openEdit);
        tr.addEventListener("keydown", (e) => {
          if (e.key !== "Enter" && e.key !== " ") return;
          e.preventDefault();
          openEdit();
        });
      });
  }

  async function onLodgingSubmit(e) {
    e.preventDefault();
    if (!lodgingSubmit) return;
    lodgingSubmit.disabled = true;
    const regionVal = (lodgingRegionInput?.value || "").trim();
    const payload = {
      name: (lodgingNameInput?.value || "").trim(),
      region: regionVal ? Number(regionVal) : null,
      address: (lodgingAddressInput?.value || "").trim(),
      memo: (lodgingMemoInput?.value || "").trim(),
    };
    if (!payload.name) {
      lodgingSubmit.disabled = false;
      showToast("숙소 이름은 필수입니다.", true);
      return;
    }
    try {
      if (lodgingMode === "edit" && lodgingTargetId) {
        await api(
          ctx.urls.lodgingDetailTemplate.replace("__id__", String(lodgingTargetId)),
          "PATCH",
          payload
        );
        showToast("숙소 수정됨");
      } else {
        await api(ctx.urls.eventLodgings, "POST", payload);
        showToast("숙소 추가됨");
      }
      window.location.reload();
    } catch (err) {
      showToast(err.message || "저장 실패", true);
    } finally {
      lodgingSubmit.disabled = false;
    }
  }

  async function onRoomSubmit(e) {
    e.preventDefault();
    if (!roomSubmit) return;
    roomSubmit.disabled = true;
    const payload = {
      number: (roomNumberInput?.value || "").trim(),
      capacity: Number(roomCapacityInput?.value || 0) || 0,
      recommended_gender: getRoomGender(),
      scope_divisions: selectedIds(roomDivisionInput),
      target_groups: selectedIds(roomGroupInput),
      memo: (roomMemoInput?.value || "").trim(),
    };
    if (!payload.number) {
      roomSubmit.disabled = false;
      showToast("호수는 필수입니다.", true);
      return;
    }
    if (!payload.recommended_gender) {
      roomSubmit.disabled = false;
      showToast("호실 성별을 선택하세요.", true);
      return;
    }
    try {
      if (roomMode === "edit" && roomTargetId) {
        await api(
          ctx.urls.roomDetailTemplate.replace("__id__", String(roomTargetId)),
          "PATCH",
          payload
        );
        showToast("객실 수정됨");
      } else if (roomTargetLodgingId) {
        await api(
          ctx.urls.lodgingRoomsTemplate.replace(
            "__id__",
            String(roomTargetLodgingId)
          ),
          "POST",
          payload
        );
        showToast("객실 추가됨");
      }
      window.location.reload();
    } catch (err) {
      showToast(err.message || "저장 실패", true);
    } finally {
      roomSubmit.disabled = false;
    }
  }

  async function confirmDeleteLodging(lodgingId) {
    if (!window.confirm("숙소를 삭제할까요? 객실도 함께 삭제됩니다.")) return;
    try {
      await api(
        ctx.urls.lodgingDetailTemplate.replace("__id__", String(lodgingId)),
        "DELETE"
      );
      showToast("삭제됨");
      window.location.reload();
    } catch (err) {
      showToast(err.message || "삭제 실패", true);
    }
  }

  async function confirmDeleteRoom(roomId) {
    if (!window.confirm("객실을 삭제할까요? 배정된 조원은 미배정으로 돌아갑니다."))
      return;
    try {
      await api(
        ctx.urls.roomDetailTemplate.replace("__id__", String(roomId)),
        "DELETE"
      );
      showToast("삭제됨");
      window.location.reload();
    } catch (err) {
      showToast(err.message || "삭제 실패", true);
    }
  }

  function init() {
    bindLodgingCollapse();
    if (!ctx.canManage) return;
    bindLodgingModal();
    bindRoomModal();
    bindLodgingActions();
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      if (lodgingOverlay && !lodgingOverlay.hidden) closeLodgingModal();
      if (roomOverlay && !roomOverlay.hidden) closeRoomModal();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
