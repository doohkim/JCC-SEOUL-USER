(function () {
  const ctx = window.RETREAT_PICKUP_CTX;
  if (!ctx || !ctx.canManage) return;

  const tbody = document.getElementById("pickupTbody");
  const statusEl = document.getElementById("pickupStatus");
  const btnAdd = document.getElementById("btnPickupAdd");
  const modalOverlay = document.getElementById("pickupModalOverlay");
  const form = document.getElementById("pickupForm");
  const modalCancel = document.getElementById("pickupModalCancel");
  const modalTitleEl = document.getElementById("pickupModalTitle");
  const modalSubmitBtn = document.getElementById("pickupModalSubmit");
  let editingId = null;

  const confirmOverlay = document.getElementById("retreatConfirmOverlay");
  const confirmTitleEl = document.getElementById("retreatConfirmTitle");
  const confirmMsgEl = document.getElementById("retreatConfirmMsg");
  const confirmOkBtn = document.getElementById("retreatConfirmOk");
  const confirmCancelBtn = document.getElementById("retreatConfirmCancel");
  let confirmResolve = null;

  const colCount = 11;

  const groupSelect = document.getElementById("pickupGroup");
  const regionSelect = document.getElementById("pickupRegion");
  const divisionSelect = document.getElementById("pickupDivision");

  let allDivisions = [];
  try {
    const raw =
      document.getElementById("retreatDivisionList")?.textContent || "[]";
    allDivisions = JSON.parse(raw);
  } catch (e) {
    allDivisions = [];
  }

  function fillDivisionSelect(regionId, selectedId) {
    if (!divisionSelect) return;
    divisionSelect.innerHTML = '<option value="">선택</option>';
    if (!regionId) return;
    allDivisions
      .filter((d) => d.region_id === Number(regionId))
      .forEach((d) => {
        const opt = document.createElement("option");
        opt.value = String(d.id);
        opt.textContent = d.name;
        if (selectedId != null && String(d.id) === String(selectedId)) {
          opt.selected = true;
        }
        divisionSelect.appendChild(opt);
      });
  }

  if (regionSelect) {
    regionSelect.addEventListener("change", () => {
      fillDivisionSelect(regionSelect.value, null);
    });
  }

  function isValidPhone(raw) {
    const digits = String(raw ?? "").replace(/\D/g, "");
    return /^01[016789]\d{7,8}$/.test(digits);
  }

  function escapeHtml(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function setStatus(msg, isError) {
    if (!statusEl) return;
    statusEl.textContent = msg || "";
    statusEl.classList.toggle("error", !!isError);
  }

  function csrfHeaders() {
    return {
      "Content-Type": "application/json",
      "X-CSRFToken": ctx.csrfToken,
    };
  }

  function openConfirm(message, title, okLabel, cancelLabel) {
    if (!confirmOverlay) return Promise.resolve(false);
    if (confirmResolve) confirmResolve(false);
    if (confirmTitleEl) confirmTitleEl.textContent = title || "확인";
    if (confirmMsgEl) confirmMsgEl.textContent = message || "";
    if (confirmOkBtn) confirmOkBtn.textContent = okLabel || "확인";
    if (confirmCancelBtn) confirmCancelBtn.textContent = cancelLabel || "취소";
    confirmOverlay.hidden = false;
    confirmOverlay.setAttribute("aria-hidden", "false");
    requestAnimationFrame(() => confirmOkBtn?.focus());
    return new Promise((resolve) => {
      confirmResolve = resolve;
    });
  }

  function resolveConfirm(value) {
    if (!confirmOverlay) return;
    confirmOverlay.hidden = true;
    confirmOverlay.setAttribute("aria-hidden", "true");
    const r = confirmResolve;
    confirmResolve = null;
    if (r) r(!!value);
  }

  if (confirmOkBtn) {
    confirmOkBtn.addEventListener("click", () => resolveConfirm(true));
  }
  if (confirmCancelBtn) {
    confirmCancelBtn.addEventListener("click", () => resolveConfirm(false));
  }
  if (confirmOverlay) {
    confirmOverlay.addEventListener("click", (e) => {
      if (e.target === confirmOverlay) resolveConfirm(false);
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !confirmOverlay.hidden) resolveConfirm(false);
    });
  }

  function setVal(id, value) {
    const el = document.getElementById(id);
    if (el) el.value = value || "";
  }

  function openModal(editItem) {
    if (!modalOverlay || !form) return;
    form.reset();
    editingId = editItem ? editItem.id : null;
    if (modalTitleEl)
      modalTitleEl.textContent = editItem ? "픽업 정보 수정" : "픽업 정보 추가";
    if (modalSubmitBtn)
      modalSubmitBtn.textContent = editItem ? "저장" : "등록";

    setVal("pickupName", editItem ? editItem.name : "");
    // datetime-local 피커 표시 갱신 (래핑된 value setter 트리거)
    setVal("pickupTrainTime", editItem ? editItem.trainTime : "");
    setVal("pickupBoardingPlace", editItem ? editItem.boardingPlace : "");
    setVal("pickupContact", editItem ? editItem.contact : "");
    setVal("pickupNote", editItem ? editItem.note : "");
    if (groupSelect) groupSelect.value = editItem ? editItem.group || "" : "";
    if (regionSelect) regionSelect.value = editItem ? editItem.region || "" : "";
    fillDivisionSelect(
      regionSelect ? regionSelect.value : "",
      editItem ? editItem.division : null
    );

    modalOverlay.hidden = false;
    modalOverlay.setAttribute("aria-hidden", "false");
    document.getElementById("pickupName")?.focus();
  }

  function closeModal() {
    if (!modalOverlay) return;
    modalOverlay.hidden = true;
    modalOverlay.setAttribute("aria-hidden", "true");
  }

  function removeEmptyRow() {
    const empty = document.getElementById("pickupEmptyRow");
    if (empty) empty.remove();
  }

  function rowHtml(item) {
    return `
      <td class="num">${escapeHtml(item.number)}</td>
      <td><button type="button" class="jcc-retreat-pickupNameBtn" data-pickup-edit>${escapeHtml(item.name)}</button></td>
      <td>${escapeHtml(item.group_name || "-")}</td>
      <td>${escapeHtml(item.region_name || "-")}</td>
      <td>${escapeHtml(item.division_name || "-")}</td>
      <td>${escapeHtml(item.train_time_display)}</td>
      <td>${escapeHtml(item.boarding_place)}</td>
      <td>${escapeHtml(item.contact)}</td>
      <td>${escapeHtml(item.applicant_name || "-")}</td>
      <td>${escapeHtml(item.note || "-")}</td>
      <td><button type="button" class="secondary jcc-retreat-pickupDelete" data-pickup-delete>제거</button></td>
    `;
  }

  function applyRowData(tr, item) {
    tr.dataset.pickupId = String(item.id);
    tr.dataset.name = item.name || "";
    tr.dataset.group = item.group != null ? String(item.group) : "";
    tr.dataset.region = item.region != null ? String(item.region) : "";
    tr.dataset.division = item.division != null ? String(item.division) : "";
    tr.dataset.trainTime = item.train_time_input || "";
    tr.dataset.boardingPlace = item.boarding_place || "";
    tr.dataset.contact = item.contact || "";
    tr.dataset.note = item.note || "";
    tr.innerHTML = rowHtml(item);
  }

  function appendRow(item) {
    if (!tbody) return;
    removeEmptyRow();
    const tr = document.createElement("tr");
    applyRowData(tr, item);
    tbody.appendChild(tr);
  }

  function updateRow(item) {
    if (!tbody) return;
    const tr = tbody.querySelector(`tr[data-pickup-id="${item.id}"]`);
    if (tr) applyRowData(tr, item);
  }

  if (btnAdd) btnAdd.addEventListener("click", () => openModal());
  if (modalCancel) modalCancel.addEventListener("click", closeModal);
  if (modalOverlay) {
    modalOverlay.addEventListener("click", (e) => {
      if (e.target === modalOverlay) closeModal();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !modalOverlay.hidden) closeModal();
    });
  }

  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = document.getElementById("pickupName")?.value.trim() || "";
      const trainTime =
        document.getElementById("pickupTrainTime")?.value.trim() || "";
      const boardingPlace =
        document.getElementById("pickupBoardingPlace")?.value.trim() || "";
      const contact =
        document.getElementById("pickupContact")?.value.trim() || "";
      const note = document.getElementById("pickupNote")?.value.trim() || "";
      const group = groupSelect?.value || "";
      const region = regionSelect?.value || "";
      const division = divisionSelect?.value || "";

      if (!name || !trainTime || !boardingPlace || !contact) {
        setStatus("이름, 열차 시각, 탑승장소, 연락처는 필수입니다.", true);
        return;
      }
      if (!isValidPhone(contact)) {
        setStatus(
          "올바른 휴대폰 번호 형식이 아닙니다. (예: 010-1234-5678)",
          true
        );
        return;
      }

      const isEdit = editingId != null;
      const failMsg = isEdit ? "수정에 실패했습니다." : "등록에 실패했습니다.";
      setStatus("");
      try {
        const payload = {
          name,
          group: group || null,
          region: region || null,
          division: division || null,
          train_time: trainTime,
          boarding_place: boardingPlace,
          contact,
          note,
        };
        if (!isEdit) payload.direction = ctx.direction;
        const r = await fetch(
          isEdit ? `${ctx.apiDetailBase}${editingId}/` : ctx.apiList,
          {
            method: isEdit ? "PATCH" : "POST",
            credentials: "same-origin",
            headers: csrfHeaders(),
            body: JSON.stringify(payload),
          }
        );
        if (!r.ok) {
          const err = await r.json().catch(() => ({}));
          const msg =
            err.detail ||
            Object.values(err)
              .flat()
              .join(" ") ||
            failMsg;
          throw new Error(msg);
        }
        const item = await r.json();
        if (isEdit) updateRow(item);
        else appendRow(item);
        closeModal();
        setStatus(isEdit ? "수정되었습니다." : "등록되었습니다.", false);
      } catch (err) {
        setStatus(err.message || failMsg, true);
      }
    });
  }

  if (tbody) {
    tbody.addEventListener("click", async (e) => {
      const editBtn = e.target.closest("[data-pickup-edit]");
      if (editBtn) {
        const tr = editBtn.closest("tr[data-pickup-id]");
        if (tr) {
          openModal({
            id: tr.dataset.pickupId,
            name: tr.dataset.name || "",
            trainTime: tr.dataset.trainTime || "",
            boardingPlace: tr.dataset.boardingPlace || "",
            contact: tr.dataset.contact || "",
            note: tr.dataset.note || "",
            group: tr.dataset.group || "",
            region: tr.dataset.region || "",
            division: tr.dataset.division || "",
          });
        }
        return;
      }

      const btn = e.target.closest("[data-pickup-delete]");
      if (!btn) return;
      const tr = btn.closest("tr[data-pickup-id]");
      if (!tr) return;
      const pickupId = tr.dataset.pickupId;
      const name = tr.children[1]?.textContent?.trim() || "";
      const ok = await openConfirm(
        `${name} 픽업 정보를 제거할까요?`,
        "픽업 정보 제거",
        "제거",
        "취소"
      );
      if (!ok) return;

      setStatus("");
      try {
        const r = await fetch(`${ctx.apiDetailBase}${pickupId}/`, {
          method: "DELETE",
          credentials: "same-origin",
          headers: { "X-CSRFToken": ctx.csrfToken },
        });
        if (!r.ok) throw new Error(await r.text());
        tr.remove();
        if (!tbody.querySelector("tr[data-pickup-id]")) {
          const empty = document.createElement("tr");
          empty.id = "pickupEmptyRow";
          empty.innerHTML = `<td colspan="${colCount}">등록된 픽업 정보가 없습니다.</td>`;
          tbody.appendChild(empty);
        }
        setStatus("제거되었습니다.", false);
      } catch (err) {
        setStatus(err.message || "제거에 실패했습니다.", true);
      }
    });
  }
})();
