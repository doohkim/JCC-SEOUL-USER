/**
 * 방배정 페이지 — 호실 → 지역·부서 매핑 변경 인라인 편집.
 *
 * 각 호실 row 에 두 개의 select (지역, 부서) + 적용 버튼이 있다.
 * 지역 select 가 변경되면 부서 select 가 동적으로 갱신되며 (해당 region 의 division 만 노출),
 * 적용 버튼이 PATCH /api/v1/retreat/lodging-rooms/<id>/ 로 region/division 을 저장한다.
 */
(function () {
  "use strict";

  const ctx = window.RETREAT_ASSIGN_CTX;
  if (!ctx) return;

  const toastEl = document.getElementById("retreatToast");
  const statusLineEl = document.getElementById("retreatStatus");

  let allDivisions = [];
  try {
    const raw = document.getElementById("retreatDivisionList")?.textContent || "[]";
    allDivisions = JSON.parse(raw);
  } catch (e) {
    allDivisions = [];
  }

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

  function csrf() {
    return ctx.csrfToken || "";
  }

  function refreshDivisionOptions(divisionSelect, regionId, selectedDivisionId) {
    if (!divisionSelect) return;
    divisionSelect.innerHTML = "";
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "(미배정)";
    divisionSelect.appendChild(empty);
    if (regionId == null || regionId === "") return;
    const ridNum = Number(regionId);
    allDivisions
      .filter((d) => d.region_id === ridNum)
      .forEach((d) => {
        const opt = document.createElement("option");
        opt.value = String(d.id);
        opt.textContent = d.name;
        if (selectedDivisionId != null && String(d.id) === String(selectedDivisionId)) {
          opt.selected = true;
        }
        divisionSelect.appendChild(opt);
      });
  }

  async function patchRoom(roomId, payload) {
    const url = ctx.urls.roomDetailTemplate.replace("__id__", String(roomId));
    const r = await fetch(url, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf(),
      },
      credentials: "same-origin",
      body: JSON.stringify(payload),
    });
    if (!r.ok) {
      let detail = "저장에 실패했습니다.";
      try {
        const j = await r.json();
        if (j.detail) detail = j.detail;
        else if (Array.isArray(j.region)) detail = j.region[0];
        else if (Array.isArray(j.division)) detail = j.division[0];
        else detail = JSON.stringify(j);
      } catch (e) {}
      throw new Error(detail);
    }
    return r.json();
  }

  function bindRow(tr) {
    const regionSel = tr.querySelector("[data-room-region]");
    const divisionSel = tr.querySelector("[data-room-division]");
    const saveBtn = tr.querySelector("[data-room-save]");
    if (!regionSel || !divisionSel || !saveBtn) return;

    const initialRegion = tr.dataset.roomRegionId || "";
    const initialDivision = tr.dataset.roomDivisionId || "";
    refreshDivisionOptions(divisionSel, initialRegion, initialDivision);

    regionSel.addEventListener("change", () => {
      refreshDivisionOptions(divisionSel, regionSel.value, null);
    });

    saveBtn.addEventListener("click", async () => {
      const roomId = Number(tr.dataset.roomId);
      const regionVal = regionSel.value || "";
      const divisionVal = divisionSel.value || "";
      const payload = {
        region: regionVal ? Number(regionVal) : null,
        division: divisionVal ? Number(divisionVal) : null,
      };
      saveBtn.disabled = true;
      try {
        await patchRoom(roomId, payload);
        showToast("호실 매핑이 변경되었습니다. 새로고침합니다.");
        setTimeout(() => window.location.reload(), 600);
      } catch (err) {
        showToast(err.message || "변경 실패", true);
      } finally {
        saveBtn.disabled = false;
      }
    });
  }

  function init() {
    if (!ctx.canManage) return;
    document.querySelectorAll("tr[data-room-id]").forEach((tr) => bindRow(tr));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
