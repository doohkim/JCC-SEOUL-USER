const API = "/api/v1";
const REL_LABEL = {
  father: "부",
  mother: "모",
  spouse: "배우자",
  elder_brother: "형/오빠",
  younger_brother: "남동생",
  elder_sister: "언니/누나",
  younger_sister: "여동생",
  son: "아들",
  daughter: "딸",
  other: "기타",
};
const VISIT_METHOD_LABEL = {
  phone: "전화",
  visit: "방문",
  other: "기타",
};

const familyEditState = {
  familyId: null,
};

const visitEditState = {
  visitId: null,
};

function setStatus(msg, isErr) {
  const el = document.getElementById("statusLine");
  const s = msg || "";
  el.textContent = String(s).length > 220 ? String(s).slice(0, 220) + "…" : s;
  el.className = "msg" + (isErr ? " err" : "");
}

function escapeHtml(s) {
  if (s === null || s === undefined) return "";
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function getCookie(name) {
  const v = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
  return v ? decodeURIComponent(v[2]) : "";
}

async function apiGet(path) {
  const r = await fetch(API + path, { credentials: "same-origin" });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json();
}

async function apiPost(path, payload) {
  const csrftoken = getCookie("csrftoken");
  const r = await fetch(API + path, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "content-type": "application/json",
      "X-CSRFToken": csrftoken,
    },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json();
}

async function apiPatch(path, payload) {
  const csrftoken = getCookie("csrftoken");
  const r = await fetch(API + path, {
    method: "PATCH",
    credentials: "same-origin",
    headers: {
      "content-type": "application/json",
      "X-CSRFToken": csrftoken,
    },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json();
}

async function apiDelete(path) {
  const csrftoken = getCookie("csrftoken");
  const r = await fetch(API + path, {
    method: "DELETE",
    credentials: "same-origin",
    headers: { "X-CSRFToken": csrftoken },
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json();
}

function fillSelect(selectEl, items, current) {
  selectEl.innerHTML = "";
  items.forEach((it) => {
    const opt = document.createElement("option");
    opt.value = it.value;
    opt.textContent = it.label;
    if (current && current === it.value) opt.selected = true;
    selectEl.appendChild(opt);
  });
}

function renderFamilyTable(family) {
  const tb = document.getElementById("tbodyFamily");
  tb.innerHTML = "";
  const rows = Array.isArray(family) ? family : [];
  if (!rows.length) {
    tb.innerHTML = `<tr><td colspan="6">가족 데이터가 없습니다.</td></tr>`;
    return;
  }

  rows.forEach((f) => {
    const relationshipText =
      f.relationship === "other" && f.relationship_note
        ? f.relationship_note
        : REL_LABEL[f.relationship] || f.relationship || "";
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(f.name || "")}</td>
      <td>${escapeHtml(relationshipText)}</td>
      <td>${escapeHtml(f.affiliation_text || "")}</td>
      <td>${escapeHtml(f.church_position || "")}</td>
      <td>${escapeHtml(f.remarks || "")}</td>
      <td>
        <button type="button" class="secondary" data-act="edit" data-id="${f.id}">수정</button>
        <button type="button" data-act="del" data-id="${f.id}" style="margin-left:0.5rem;background:#3a4556;color:#fff;border:none;padding:0.35rem 0.75rem;border-radius:6px;cursor:pointer;">삭제</button>
      </td>
    `;
    tb.appendChild(tr);
  });
}

function renderVisitsTable(visits) {
  const tb = document.getElementById("tbodyVisits");
  tb.innerHTML = "";
  const rows = Array.isArray(visits) ? visits : [];
  if (!rows.length) {
    tb.innerHTML = `<tr><td colspan="4">기록이 없습니다.</td></tr>`;
    return;
  }

  rows.forEach((v) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(v.visit_date || "")}</td>
      <td>${escapeHtml(VISIT_METHOD_LABEL[v.contact_method] || v.contact_method || "")}</td>
      <td>${escapeHtml(v.content || "")}</td>
      <td>
        <button type="button" class="secondary" data-act="editVisit" data-id="${v.id}">수정</button>
        <button type="button" data-act="delVisit" data-id="${v.id}" style="margin-left:0.5rem;background:#3a4556;color:#fff;border:none;padding:0.35rem 0.75rem;border-radius:6px;cursor:pointer;">삭제</button>
      </td>
    `;
    tb.appendChild(tr);
  });
}

async function loadDetail() {
  const memberId = window.__MEMBER_ID__;
  if (!memberId) throw new Error("member id missing");
  setStatus("불러오는 중…");
  const data = await apiGet(`/member/${memberId}/`);

  const m = data.member || {};
  const p = data.profile || {};

  document.getElementById("memberName").textContent = m.name || "";
  document.getElementById("memberPhone").textContent = p.phone || "";
  document.getElementById("memberAddress").textContent = p.address || "";
  document.getElementById("memberPosition").textContent =
    [p.church_position_display, p.workplace_display].filter(Boolean).join(" · ") || "";
  const aliasEl = document.getElementById("memberAlias");
  if (aliasEl) aliasEl.textContent = m.name_alias || "-";
  const pm = data.primary_membership || {};
  document.getElementById("memberDivision").textContent = pm.division_name || "";
  document.getElementById("memberTeam").textContent = pm.team_name || "";
  document.getElementById("memberActive").textContent = m.is_active ? "활성" : "비활성";
  const rn = data.recent_attendance || {};
  const recentEl = document.getElementById("memberRecentAttendance");
  if (recentEl) {
    const label = rn.label || "";
    const date = rn.date || "";
    recentEl.textContent = label && date ? `${label} · ${date}` : "-";
  }
  const memoEl = document.getElementById("memberStaffNotes");
  if (memoEl) memoEl.textContent = p.staff_notes || "-";

  const img = document.getElementById("memberPhotoPreview");
  if (img) {
    if (p.photo) img.src = p.photo;
  }

  document.getElementById("linkEdit").href = `/members/${memberId}/edit/`;

  renderFamilyTable(data.family || []);
  renderVisitsTable(data.visits || []);

  setStatus("");
}

function bindUi() {
  const relItems = [
    { value: "father", label: "부" },
    { value: "mother", label: "모" },
    { value: "spouse", label: "배우자" },
    { value: "elder_brother", label: "형/오빠" },
    { value: "younger_brother", label: "남동생" },
    { value: "elder_sister", label: "언니/누나" },
    { value: "younger_sister", label: "여동생" },
    { value: "son", label: "아들" },
    { value: "daughter", label: "딸" },
    { value: "other", label: "기타" },
  ];
  fillSelect(document.getElementById("f_rel"), relItems, null);
  fillSelect(document.getElementById("v_method"), [
    { value: "phone", label: "전화" },
    { value: "visit", label: "방문" },
    { value: "other", label: "기타" },
  ]);

  function showFamilyEditModal() {
    const ov = document.getElementById("familyEditOverlay");
    ov?.classList.add("show");
    ov?.setAttribute("aria-hidden", "false");
    const st = document.getElementById("familyEditStatus");
    if (st) st.textContent = "";
  }

  function hideFamilyEditModal() {
    const ov = document.getElementById("familyEditOverlay");
    ov?.classList.remove("show");
    ov?.setAttribute("aria-hidden", "true");
    familyEditState.familyId = null;
  }

  function showVisitEditModal() {
    const ov = document.getElementById("visitEditOverlay");
    ov?.classList.add("show");
    ov?.setAttribute("aria-hidden", "false");
    const st = document.getElementById("visitEditStatus");
    if (st) st.textContent = "";
  }

  function hideVisitEditModal() {
    const ov = document.getElementById("visitEditOverlay");
    ov?.classList.remove("show");
    ov?.setAttribute("aria-hidden", "true");
    visitEditState.visitId = null;
  }

  // 가족 수정 팝업: 관계/직책 옵션
  fillSelect(document.getElementById("e_rel"), relItems, null);

  // 방문/통화 기록 수정 팝업
  fillSelect(document.getElementById("e_v_method"), [
    { value: "phone", label: "전화" },
    { value: "visit", label: "방문" },
    { value: "other", label: "기타" },
  ]);

  document.getElementById("btnVisitEditCancel").onclick = () => hideVisitEditModal();
  document.getElementById("btnVisitEditSave").onclick = async () => {
    const visitId = visitEditState.visitId;
    if (!visitId) return setVisitEditStatus("수정할 기록을 찾을 수 없습니다.", true);

    try {
      const visit_date = document.getElementById("e_v_date").value;
      const contact_method = document.getElementById("e_v_method").value;
      const content = document.getElementById("e_v_content").value.trim();

      if (!visit_date) return setVisitEditStatus("날짜를 입력하세요.", true);
      if (!contact_method) return setVisitEditStatus("방식을 선택하세요.", true);
      if (!content) return setVisitEditStatus("내용을 입력하세요.", true);

      setVisitEditStatus("수정 중…");
      await apiPatch(`/visits/${visitId}/`, { visit_date, contact_method, content });
      hideVisitEditModal();
      await loadDetail();
      setVisitEditStatus("");
    } catch (e) {
      console.error(e);
      setVisitEditStatus("수정 실패: " + e.message, true);
    }
  };

  function setFamilyEditStatus(msg, isErr) {
    const el = document.getElementById("familyEditStatus");
    if (!el) return;
    const s = msg || "";
    el.textContent = String(s).length > 220 ? String(s).slice(0, 220) + "…" : s;
    el.className = "msg" + (isErr ? " err" : "");
  }

  function setVisitEditStatus(msg, isErr) {
    const el = document.getElementById("visitEditStatus");
    if (!el) return;
    const s = msg || "";
    el.textContent = String(s).length > 220 ? String(s).slice(0, 220) + "…" : s;
    el.className = "msg" + (isErr ? " err" : "");
  }

  (async () => {
    const posSel = document.getElementById("e_pos");
    if (!posSel) return;
    const data = await apiGet(`/member/roles/`);
    const roles = Array.isArray(data.roles) ? data.roles : [];
    const items = [
      { value: "", label: "-" },
      ...roles.map((r) => ({ value: r.name || "", label: r.name || "" })),
    ];
    fillSelect(posSel, items, null);
  })().catch((e) => {
    console.error(e);
  });

  document.getElementById("btnFamilyEditCancel").onclick = () => hideFamilyEditModal();
  document.getElementById("btnFamilyEditSave").onclick = async () => {
    const familyId = familyEditState.familyId;
    if (!familyId) return setFamilyEditStatus("수정할 가족을 찾을 수 없습니다.", true);

    try {
      setFamilyEditStatus("수정 중…");
      const name = document.getElementById("e_name").value.trim();
      const relationship = document.getElementById("e_rel").value;
      const affiliation_text = document.getElementById("e_aff").value.trim();
      const church_position = document.getElementById("e_pos").value.trim();
      const note = document.getElementById("e_note").value.trim();

      if (!name) return setFamilyEditStatus("이름을 입력하세요.", true);
      if (!relationship) return setFamilyEditStatus("관계를 선택하세요.", true);

      const payload = {
        name,
        relationship,
        affiliation_text,
        church_position,
        remarks: relationship === "other" ? "" : note,
        relationship_note: relationship === "other" ? note : "",
        sort_order: 0,
      };

      await apiPatch(`/family/${familyId}/`, payload);
      hideFamilyEditModal();
      await loadDetail();
      setFamilyEditStatus("");
    } catch (e) {
      console.error(e);
      setFamilyEditStatus("수정 실패: " + e.message, true);
    }
  };

  // 가족 추가: 직책(Role) 선택 옵션 로드
  (async () => {
    const posSel = document.getElementById("f_pos");
    if (!posSel) return;
    const data = await apiGet(`/member/roles/`);
    const roles = Array.isArray(data.roles) ? data.roles : [];
    const items = [
      { value: "", label: "-" },
      ...roles.map((r) => ({ value: r.name || "", label: r.name || "" })),
    ];
    fillSelect(posSel, items, null);
  })().catch((e) => {
    console.error(e);
    // 옵션 로드 실패해도 기본 입력 UI는 깨지지 않게 둡니다.
  });

  document.getElementById("btnFamilyAdd").onclick = async () => {
    const memberId = window.__MEMBER_ID__;
    const name = document.getElementById("f_name").value.trim();
    const relationship = document.getElementById("f_rel").value;
    const affiliation_text = document.getElementById("f_aff").value.trim();
    const church_position = document.getElementById("f_pos").value.trim();
    const note = document.getElementById("f_note").value.trim();

    if (!name) return setStatus("가족 이름을 입력하세요.", true);
    if (!relationship) return setStatus("가족 관계를 선택하세요.", true);

    const payload = {
      name,
      relationship,
      affiliation_text,
      church_position,
      remarks: relationship === "other" ? "" : note,
      relationship_note: relationship === "other" ? note : "",
      sort_order: 0,
    };

    try {
      await apiPost(`/member/${memberId}/family/`, payload);
      await loadDetail();
      document.getElementById("f_name").value = "";
      document.getElementById("f_note").value = "";
    } catch (e) {
      console.error(e);
      setStatus("추가 실패: " + e.message, true);
    }
  };

  document.getElementById("btnVisitAdd").onclick = async () => {
    const memberId = window.__MEMBER_ID__;
    const visit_date = document.getElementById("v_date").value;
    const contact_method = document.getElementById("v_method").value;
    const content = document.getElementById("v_content").value.trim();

    if (!visit_date || !content) return setStatus("날짜와 내용을 입력하세요.", true);

    const payload = { visit_date, contact_method, content };
    try {
      await apiPost(`/member/${memberId}/visits/`, payload);
      await loadDetail();
      document.getElementById("v_content").value = "";
    } catch (e) {
      console.error(e);
      setStatus("추가 실패: " + e.message, true);
    }
  };

  // event delegation for edit/delete buttons
  document.getElementById("tbodyFamily").onclick = async (e) => {
    const target = e.target;
    const btn = target && target.closest ? target.closest("button[data-id]") : null;
    if (!btn) return;
    const id = Number(btn.getAttribute("data-id"));
    const act = btn.getAttribute("data-act");
    if (act === "del") {
      if (!confirm("가족 항목을 삭제할까요?")) return;
      try {
        await apiDelete(`/family/${id}/`);
        await loadDetail();
      } catch (err) {
        console.error(err);
        setStatus("삭제 실패: " + err.message, true);
      }
    }
    if (act === "edit") {
      try {
        familyEditState.familyId = id;
      } catch (err) {
        // ignore
      }

      // 즉시 모달 열고, 테이블 값으로 fallback 채우기
      showFamilyEditModal();
      setFamilyEditStatus("");

      const row = btn.closest("tr");
      const name = row?.children?.[0]?.textContent?.trim() || "";
      const relText = row?.children?.[1]?.textContent?.trim() || "";
      const affText = row?.children?.[2]?.textContent?.trim() || "";
      const posText = row?.children?.[3]?.textContent?.trim() || "";
      const remarksText = row?.children?.[4]?.textContent?.trim() || "";

      const relCode =
        Object.keys(REL_LABEL).find((k) => REL_LABEL[k] === relText) || "other";

      document.getElementById("e_name").value = name;
      document.getElementById("e_rel").value = relCode;
      document.getElementById("e_aff").value = affText;

      const posSel = document.getElementById("e_pos");
      if (posSel) {
        const exists = Array.from(posSel.options).some((o) => o.value === posText);
        if (posText && !exists) {
          const opt = document.createElement("option");
          opt.value = posText;
          opt.textContent = posText;
          posSel.appendChild(opt);
        }
        posSel.value = posText;
      }

      // 비고 처리:
      // - 기타(other)면 관계(직접입력) 텍스트를 e_note에 넣음
      // - 그 외면 remarks 컬럼 텍스트를 e_note에 넣음
      document.getElementById("e_note").value = relCode === "other" ? relText : remarksText;

      // 정확한 값 덮어쓰기 시도 (실패해도 fallback 유지)
      (async () => {
        try {
          setFamilyEditStatus("불러오는 중…");
          const fam = await apiGet(`/family/${id}/`);

          const rel = fam.relationship || "";
          document.getElementById("e_name").value = fam.name || "";
          document.getElementById("e_rel").value = rel;
          document.getElementById("e_aff").value = fam.affiliation_text || "";

          const posSel2 = document.getElementById("e_pos");
          const posVal = fam.church_position || "";
          if (posSel2) {
            const exists = Array.from(posSel2.options).some((o) => o.value === posVal);
            if (posVal && !exists) {
              const opt = document.createElement("option");
              opt.value = posVal;
              opt.textContent = posVal;
              posSel2.appendChild(opt);
            }
            posSel2.value = posVal;
          }

          const noteValue =
            rel === "other" ? fam.relationship_note || "" : fam.remarks || "";
          document.getElementById("e_note").value = noteValue;

          setFamilyEditStatus("");
        } catch (err) {
          console.error(err);
          setFamilyEditStatus("불러오기 실패(대체값 사용).", false);
        }
      })();
    }
  };

  document.getElementById("tbodyVisits").onclick = async (e) => {
    const target = e.target;
    const btn = target && target.closest ? target.closest("button[data-id]") : null;
    if (!btn) return;
    const id = Number(btn.getAttribute("data-id"));
    const act = btn.getAttribute("data-act");
    if (act === "delVisit") {
      if (!confirm("심방 기록을 삭제할까요?")) return;
      try {
        await apiDelete(`/visits/${id}/`);
        await loadDetail();
      } catch (err) {
        console.error(err);
        setStatus("삭제 실패: " + err.message, true);
      }
    }
    if (act === "editVisit") {
      try {
        visitEditState.visitId = id;

        // 즉시 모달 열고 fallback 채움(서버 GET 실패해도 클릭 UX 유지)
        showVisitEditModal();
        setVisitEditStatus("");

        const row = btn.closest("tr");
        const v_date_text = row?.children?.[0]?.textContent?.trim() || "";
        const method_text = row?.children?.[1]?.textContent?.trim() || "";
        const content_text = row?.children?.[2]?.textContent?.trim() || "";

        // row의 방식 텍스트 -> contact_method code(phone/visit/other) 역매핑
        const methodCode =
          Object.keys(VISIT_METHOD_LABEL).find((k) => VISIT_METHOD_LABEL[k] === method_text) ||
          (method_text ? "other" : "phone");

        document.getElementById("e_v_date").value = v_date_text || "";
        document.getElementById("e_v_method").value = methodCode;
        document.getElementById("e_v_content").value = content_text || "";

        // 정확한 값 덮어쓰기(가능하면)
        (async () => {
          try {
            setVisitEditStatus("불러오는 중…");
            const v = await apiGet(`/visits/${id}/`);
            document.getElementById("e_v_date").value = v.visit_date || "";
            document.getElementById("e_v_method").value = v.contact_method || "";
            document.getElementById("e_v_content").value = v.content || "";
            setVisitEditStatus("");
          } catch (err) {
            console.error(err);
            setVisitEditStatus("불러오기 실패(대체값 사용).", true);
          }
        })();
      } catch (err) {
        console.error(err);
        setVisitEditStatus("수정 준비 실패: " + err.message, true);
      }
    }
  };
}

async function init() {
  bindUi();
  try {
    await loadDetail();
  } catch (e) {
    console.error(e);
    setStatus("초기화 실패: " + e.message, true);
  }
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
else init();

