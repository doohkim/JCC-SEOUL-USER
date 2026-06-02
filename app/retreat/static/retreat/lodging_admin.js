/**
 * 숙소 관리 페이지 — 숙소/호실 CRUD 모달
 * 새로고침은 단순히 location.reload() 로 처리한다 (목록 일관성 우선).
 */
(function () {
  "use strict";

  const ctx = window.RETREAT_LODGING_CTX;
  if (!ctx) return;
  if (!ctx.canManage) return;

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

  // 호실 모달
  const roomOverlay = document.getElementById("roomModalOverlay");
  const roomForm = document.getElementById("roomForm");
  const roomTitle = document.getElementById("roomModalTitle");
  const roomSubmit = document.getElementById("roomModalSubmit");
  const roomCancel = document.getElementById("roomModalCancel");
  const roomNumberInput = document.getElementById("roomNumberInput");
  const roomCapacityInput = document.getElementById("roomCapacityInput");
  const roomRegionInput = document.getElementById("roomRegionInput");
  const roomDivisionInput = document.getElementById("roomDivisionInput");
  const roomGenderInput = document.getElementById("roomGenderInput");
  const roomMemoInput = document.getElementById("roomMemoInput");

  let allDivisions = [];
  try {
    const raw = document.getElementById("retreatDivisionList")?.textContent || "[]";
    allDivisions = JSON.parse(raw);
  } catch (e) {
    allDivisions = [];
  }

  function refreshDivisionOptions(selectedDivisionId) {
    if (!roomDivisionInput) return;
    const regionVal = (roomRegionInput?.value || "").trim();
    const regionId = regionVal ? Number(regionVal) : null;
    roomDivisionInput.innerHTML = "";
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "(미배정)";
    roomDivisionInput.appendChild(empty);
    if (regionId == null) return;
    allDivisions
      .filter((d) => d.region_id === regionId)
      .forEach((d) => {
        const opt = document.createElement("option");
        opt.value = String(d.id);
        opt.textContent = d.name;
        roomDivisionInput.appendChild(opt);
      });
    if (selectedDivisionId != null) {
      roomDivisionInput.value = String(selectedDivisionId);
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
    if (roomTitle) roomTitle.textContent = mode === "edit" ? "호실 수정" : "호실 추가";
    if (roomSubmit) roomSubmit.textContent = mode === "edit" ? "수정" : "저장";
    if (roomNumberInput) roomNumberInput.value = payload?.number || "";
    if (roomCapacityInput)
      roomCapacityInput.value = payload?.capacity != null ? payload.capacity : 0;
    if (roomRegionInput)
      roomRegionInput.value = payload?.region != null ? String(payload.region) : "";
    refreshDivisionOptions(payload?.division != null ? payload.division : null);
    if (roomGenderInput)
      roomGenderInput.value = payload?.recommended_gender || "";
    if (roomMemoInput) roomMemoInput.value = payload?.memo || "";
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

  function bindLodgingModal() {
    const addBtn = document.getElementById("btnAddLodging");
    if (addBtn) addBtn.addEventListener("click", () => openLodgingModal("create"));
    if (lodgingCancel) lodgingCancel.addEventListener("click", closeLodgingModal);
    if (lodgingOverlay) {
      lodgingOverlay.addEventListener("click", (e) => {
        if (e.target === lodgingOverlay) closeLodgingModal();
      });
    }
    if (lodgingForm) lodgingForm.addEventListener("submit", onLodgingSubmit);
  }

  function bindRoomModal() {
    if (roomCancel) roomCancel.addEventListener("click", closeRoomModal);
    if (roomOverlay) {
      roomOverlay.addEventListener("click", (e) => {
        if (e.target === roomOverlay) closeRoomModal();
      });
    }
    if (roomRegionInput) {
      roomRegionInput.addEventListener("change", () => refreshDivisionOptions());
    }
    if (roomForm) roomForm.addEventListener("submit", onRoomSubmit);
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
      const regionId = regionEl?.dataset?.lodgingRegionId || "";
      if (editLodging) {
        editLodging.addEventListener("click", () =>
          openLodgingModal("edit", {
            id: lid,
            name,
            region: regionId ? Number(regionId) : "",
            address,
            memo,
          })
        );
      }
      if (delLodging) {
        delLodging.addEventListener("click", () => confirmDeleteLodging(lid));
      }
      if (addRoom) {
        addRoom.addEventListener("click", () => openRoomModal("create", lid));
      }

      card.querySelectorAll("tr[data-room-id]").forEach((tr) => {
        const rid = Number(tr.dataset.roomId);
        const editBtn = tr.querySelector("[data-edit-room]");
        const delBtn = tr.querySelector("[data-del-room]");
        const number = tr.querySelector("[data-room-number]")?.textContent?.trim() || "";
        const capTxt = tr.querySelector("[data-room-capacity]")?.textContent?.trim() || "0";
        const cap = capTxt === "무제한" ? 0 : Number(capTxt);
        const genderText =
          tr.querySelector("[data-room-gender]")?.textContent?.trim() || "";
        const genderCode =
          {
            남성: "male",
            여성: "female",
            혼성: "mixed",
          }[genderText] || "";
        const roomRegionId = tr.dataset.roomRegionId
          ? Number(tr.dataset.roomRegionId)
          : null;
        const roomDivisionId = tr.dataset.roomDivisionId
          ? Number(tr.dataset.roomDivisionId)
          : null;
        if (editBtn) {
          editBtn.addEventListener("click", () =>
            openRoomModal("edit", lid, {
              id: rid,
              number,
              capacity: cap,
              recommended_gender: genderCode,
              region: roomRegionId,
              division: roomDivisionId,
            })
          );
        }
        if (delBtn) {
          delBtn.addEventListener("click", () => confirmDeleteRoom(rid));
        }
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
    const regionVal = (roomRegionInput?.value || "").trim();
    const divisionVal = (roomDivisionInput?.value || "").trim();
    const payload = {
      number: (roomNumberInput?.value || "").trim(),
      capacity: Number(roomCapacityInput?.value || 0) || 0,
      recommended_gender: roomGenderInput?.value || "",
      region: regionVal ? Number(regionVal) : null,
      division: divisionVal ? Number(divisionVal) : null,
      memo: (roomMemoInput?.value || "").trim(),
    };
    if (!payload.number) {
      roomSubmit.disabled = false;
      showToast("호수는 필수입니다.", true);
      return;
    }
    try {
      if (roomMode === "edit" && roomTargetId) {
        await api(
          ctx.urls.roomDetailTemplate.replace("__id__", String(roomTargetId)),
          "PATCH",
          payload
        );
        showToast("호실 수정됨");
      } else if (roomTargetLodgingId) {
        await api(
          ctx.urls.lodgingRoomsTemplate.replace(
            "__id__",
            String(roomTargetLodgingId)
          ),
          "POST",
          payload
        );
        showToast("호실 추가됨");
      }
      window.location.reload();
    } catch (err) {
      showToast(err.message || "저장 실패", true);
    } finally {
      roomSubmit.disabled = false;
    }
  }

  async function confirmDeleteLodging(lodgingId) {
    if (!window.confirm("숙소를 삭제할까요? 호실도 함께 삭제됩니다.")) return;
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
    if (!window.confirm("호실을 삭제할까요? 배정된 조원은 미배정으로 돌아갑니다."))
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
