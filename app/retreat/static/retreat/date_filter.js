/*
 * 날짜 전용 필터 피커 (바닐라 JS)
 *
 * 기존 datetime_picker.js 의 커스텀 달력(.jcc-dtp-*) 모양을 그대로 재사용하되,
 * 시간 영역 없이 "날짜만" 고른다. PC 는 필드 아래 앵커 팝업, 모바일은 하단 시트.
 *
 * 사용법(HTML):
 *   <button data-date-filter="<hidden-input-id>" data-date-filter-form="<form-id>">…</button>
 *   <input type="hidden" id="<hidden-input-id>" value="YYYY-MM-DD 또는 빈값">
 * 날짜를 고르면 hidden input 값(YYYY-MM-DD, '전체'는 빈값)을 채우고 해당 form 을 제출한다.
 */
(function () {
  "use strict";

  const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];
  let openController = null;

  function pad(n) {
    return String(n).padStart(2, "0");
  }

  function parseDate(v) {
    if (!v) return null;
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(v);
    if (!m) return null;
    return { y: Number(m[1]), mo: Number(m[2]) - 1, d: Number(m[3]) };
  }

  function fmtDate(s) {
    return `${s.y}-${pad(s.mo + 1)}-${pad(s.d)}`;
  }

  function getViewportHeight() {
    if (window.visualViewport && window.visualViewport.height) {
      return window.visualViewport.height;
    }
    return window.innerHeight;
  }

  function shouldUseSheet() {
    return window.matchMedia("(max-width: 640px)").matches;
  }

  function closeOpen() {
    if (openController) openController.close();
  }

  function open(field) {
    closeOpen();

    const targetId = field.getAttribute("data-date-filter");
    const formId = field.getAttribute("data-date-filter-form");
    const hidden = targetId ? document.getElementById(targetId) : null;
    const form = formId ? document.getElementById(formId) : field.closest("form");
    if (!hidden || !form) return;

    const today = new Date();
    const initial = parseDate(hidden.value) || {
      y: today.getFullYear(),
      mo: today.getMonth(),
      d: today.getDate(),
    };
    const draft = parseDate(hidden.value); // null 이면 '전체'
    let viewY = initial.y;
    let viewMo = initial.mo;

    const useSheet = shouldUseSheet();
    let backdrop = null;

    const pop = document.createElement("div");
    pop.className = "jcc-dtp-pop jcc-dtp-pop--dateOnly";
    if (useSheet) pop.classList.add("jcc-dtp-pop--sheet");
    pop.setAttribute("role", "dialog");
    pop.setAttribute("aria-modal", "true");

    // 헤더(월 이동)
    const head = document.createElement("div");
    head.className = "jcc-dtp-head";
    const prev = document.createElement("button");
    prev.type = "button";
    prev.className = "jcc-dtp-nav";
    prev.textContent = "‹";
    prev.setAttribute("aria-label", "이전 달");
    const title = document.createElement("div");
    title.className = "jcc-dtp-title";
    const next = document.createElement("button");
    next.type = "button";
    next.className = "jcc-dtp-nav";
    next.textContent = "›";
    next.setAttribute("aria-label", "다음 달");
    head.appendChild(prev);
    head.appendChild(title);
    head.appendChild(next);
    pop.appendChild(head);

    // 요일
    const dow = document.createElement("div");
    dow.className = "jcc-dtp-dow";
    WEEKDAYS.forEach(function (w, i) {
      const c = document.createElement("span");
      c.textContent = w;
      if (i === 0) c.className = "sun";
      if (i === 6) c.className = "sat";
      dow.appendChild(c);
    });
    pop.appendChild(dow);

    // 날짜 그리드
    const grid = document.createElement("div");
    grid.className = "jcc-dtp-grid";
    pop.appendChild(grid);

    // 푸터(전체 / 오늘)
    const foot = document.createElement("div");
    foot.className = "jcc-dtp-foot";
    const allBtn = document.createElement("button");
    allBtn.type = "button";
    allBtn.className = "jcc-dtp-text";
    allBtn.textContent = "전체 날짜";
    const todayBtn = document.createElement("button");
    todayBtn.type = "button";
    todayBtn.className = "jcc-dtp-ok";
    todayBtn.textContent = "오늘";
    foot.appendChild(allBtn);
    foot.appendChild(todayBtn);
    pop.appendChild(foot);

    function commit(value) {
      hidden.value = value;
      if (typeof form.requestSubmit === "function") {
        form.requestSubmit();
      } else {
        form.submit();
      }
    }

    function renderGrid() {
      title.textContent = `${viewY}년 ${viewMo + 1}월`;
      grid.innerHTML = "";
      const first = new Date(viewY, viewMo, 1);
      const startDow = first.getDay();
      const gridStart = new Date(viewY, viewMo, 1 - startDow);
      const now = new Date();
      for (let i = 0; i < 42; i++) {
        const d = new Date(
          gridStart.getFullYear(),
          gridStart.getMonth(),
          gridStart.getDate() + i
        );
        const cell = document.createElement("button");
        cell.type = "button";
        cell.className = "jcc-dtp-day";
        cell.textContent = String(d.getDate());
        const dow0 = d.getDay();
        if (dow0 === 0) cell.classList.add("sun");
        if (dow0 === 6) cell.classList.add("sat");
        if (d.getMonth() !== viewMo) cell.classList.add("other");
        if (
          d.getFullYear() === now.getFullYear() &&
          d.getMonth() === now.getMonth() &&
          d.getDate() === now.getDate()
        ) {
          cell.classList.add("today");
        }
        if (
          draft &&
          d.getFullYear() === draft.y &&
          d.getMonth() === draft.mo &&
          d.getDate() === draft.d
        ) {
          cell.classList.add("selected");
        }
        cell.addEventListener("click", function () {
          commit(fmtDate({ y: d.getFullYear(), mo: d.getMonth(), d: d.getDate() }));
        });
        grid.appendChild(cell);
      }
    }

    prev.addEventListener("click", function () {
      viewMo -= 1;
      if (viewMo < 0) {
        viewMo = 11;
        viewY -= 1;
      }
      renderGrid();
    });
    next.addEventListener("click", function () {
      viewMo += 1;
      if (viewMo > 11) {
        viewMo = 0;
        viewY += 1;
      }
      renderGrid();
    });
    allBtn.addEventListener("click", function () {
      commit("");
    });
    todayBtn.addEventListener("click", function () {
      const n = new Date();
      commit(fmtDate({ y: n.getFullYear(), mo: n.getMonth(), d: n.getDate() }));
    });

    if (useSheet) {
      backdrop = document.createElement("div");
      backdrop.className = "jcc-dtp-backdrop";
      backdrop.setAttribute("aria-hidden", "true");
      document.body.appendChild(backdrop);
      document.body.classList.add("jcc-dtp-open");
    }
    document.body.appendChild(pop);

    function position() {
      if (useSheet) return;
      const margin = 8;
      const r = field.getBoundingClientRect();
      const vh = getViewportHeight();
      pop.style.maxHeight = `${vh - margin * 2}px`;
      pop.style.overflowY = "auto";
      const pw = pop.offsetWidth || 310;
      const ph = pop.offsetHeight || 340;
      let left = r.left;
      if (left + pw > window.innerWidth - margin) {
        left = window.innerWidth - pw - margin;
      }
      left = Math.max(margin, left);
      const spaceBelow = vh - r.bottom;
      const spaceAbove = r.top;
      let top;
      if (spaceBelow >= ph + margin || spaceBelow >= spaceAbove) {
        top = r.bottom + 6;
      } else {
        top = r.top - ph - 6;
      }
      top = Math.min(top, vh - ph - margin);
      top = Math.max(margin, top);
      pop.style.left = `${left}px`;
      pop.style.top = `${top}px`;
    }

    renderGrid();
    position();

    function onDocClick(e) {
      if (backdrop && e.target === backdrop) {
        ctrl.close();
        return;
      }
      if (pop.contains(e.target) || field.contains(e.target)) return;
      ctrl.close();
    }
    function onKey(e) {
      if (e.key === "Escape") ctrl.close();
    }
    function onScrollResize() {
      position();
    }

    const ctrl = {
      close() {
        document.removeEventListener("click", onDocClick, true);
        document.removeEventListener("keydown", onKey, true);
        window.removeEventListener("resize", onScrollResize, true);
        window.removeEventListener("scroll", onScrollResize, true);
        if (window.visualViewport) {
          window.visualViewport.removeEventListener("resize", onScrollResize);
        }
        if (backdrop && backdrop.parentNode) {
          backdrop.parentNode.removeChild(backdrop);
        }
        if (pop.parentNode) pop.parentNode.removeChild(pop);
        document.body.classList.remove("jcc-dtp-open");
        if (openController === ctrl) openController = null;
      },
    };
    openController = ctrl;

    setTimeout(function () {
      document.addEventListener("click", onDocClick, true);
      document.addEventListener("keydown", onKey, true);
      window.addEventListener("resize", onScrollResize, true);
      window.addEventListener("scroll", onScrollResize, true);
      if (window.visualViewport) {
        window.visualViewport.addEventListener("resize", onScrollResize);
      }
    }, 0);
  }

  function init(root) {
    const scope = root || document;
    scope.querySelectorAll("[data-date-filter]").forEach(function (field) {
      if (field.__dateFilterDone) return;
      field.__dateFilterDone = true;
      field.addEventListener("click", function (e) {
        e.preventDefault();
        open(field);
      });
    });
  }

  window.JccDateFilter = { init: init, close: closeOpen };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      init(document);
    });
  } else {
    init(document);
  }
})();
