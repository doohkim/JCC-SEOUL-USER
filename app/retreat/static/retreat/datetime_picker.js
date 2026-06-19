/*
 * 커스텀 날짜·시간 피커 (바닐라 JS, 외부 라이브러리 없음)
 *
 * 네이티브 <input type="datetime-local"> 을 점진적으로 강화한다.
 * - 원본 input 은 DOM 에 그대로 두고(값/클래스/data 속성 유지) 시각적으로만 숨긴다.
 * - 클릭하기 좋은 "필드 버튼" + 달력/시간 팝업을 보여준다.
 * - 확인 시 원본 input.value 를 "YYYY-MM-DDTHH:mm" 포맷으로 채우고 bubbling change 이벤트를 발생시킨다.
 *   (기존 PATCH/모달 저장 로직이 그대로 동작하도록)
 * - 외부 코드가 input.value 를 프로그램적으로 바꿔도 표시가 갱신되도록 value 접근자를 래핑한다.
 */
(function () {
  "use strict";

  const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];
  let openController = null;

  function pad(n) {
    return String(n).padStart(2, "0");
  }

  function parseValue(v) {
    if (!v) return null;
    const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(v);
    if (!m) return null;
    return {
      y: Number(m[1]),
      mo: Number(m[2]) - 1,
      d: Number(m[3]),
      hh: Number(m[4]),
      mm: Number(m[5]),
    };
  }

  function fmtValue(s) {
    return `${s.y}-${pad(s.mo + 1)}-${pad(s.d)}T${pad(s.hh)}:${pad(s.mm)}`;
  }

  // ymd24: 날짜(연도 4자리/2자리) + 24h 시각을 별도 span 으로 감싼다.
  function fmtDisplayYmd24(v) {
    const s = parseValue(v);
    if (!s) return "";
    const y4 = String(s.y);
    const y2 = pad(s.y % 100);
    const md = `-${pad(s.mo + 1)}-${pad(s.d)}`;
    const time = `${pad(s.hh)}:${pad(s.mm)}`;
    return (
      '<span class="jcc-stamp-date">' +
      '<span class="jcc-stamp-y4">' +
      y4 +
      "</span>" +
      '<span class="jcc-stamp-y2">' +
      y2 +
      "</span>" +
      md +
      "</span>" +
      " " +
      '<span class="jcc-stamp-time">' +
      time +
      "</span>"
    );
  }

  function fmtDisplay(v, input) {
    const s = parseValue(v);
    if (!s) return "";
    const now = new Date();
    const datePart =
      s.y === now.getFullYear()
        ? `${pad(s.mo + 1)}/${pad(s.d)}`
        : `${s.y}.${pad(s.mo + 1)}.${pad(s.d)}`;
    return `${datePart} ${pad(s.hh)}:${pad(s.mm)}`;
  }

  function isYmd24Format(input) {
    const fmt = input.dataset && input.dataset.dtpFormat;
    return fmt === "ymd24" || fmt === "ymdampm";
  }

  function roundMinute(m) {
    return Math.round(m / 5) * 5 === 60 ? 55 : Math.round(m / 5) * 5;
  }

  function closeOpen() {
    if (openController) openController.close();
  }

  function getViewportHeight() {
    if (window.visualViewport && window.visualViewport.height) {
      return window.visualViewport.height;
    }
    return window.innerHeight;
  }

  function shouldUseSheet() {
    // 모바일에서만 하단 시트(토스 스타일). PC 는 모달 안이라도 컴팩트 앵커 팝업.
    return window.matchMedia("(max-width: 640px)").matches;
  }

  function enhance(input) {
    if (!input || input.__dtpDone) return;
    input.__dtpDone = true;

    // 원본 datetime-local 숨김 (값 보관용)
    input.classList.add("jcc-dtp-native");
    input.setAttribute("tabindex", "-1");
    input.setAttribute("aria-hidden", "true");

    const field = document.createElement("button");
    field.type = "button";
    field.className = "jcc-dtp-field";
    const labelText = input.getAttribute("aria-label");
    if (labelText) field.setAttribute("aria-label", labelText);

    const valSpan = document.createElement("span");
    valSpan.className = "jcc-dtp-val";
    const icon = document.createElement("span");
    icon.className = "jcc-dtp-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = "📅";
    field.appendChild(valSpan);
    field.appendChild(icon);

    input.insertAdjacentElement("afterend", field);

    function refresh() {
      if (isYmd24Format(input)) {
        const html = fmtDisplayYmd24(input.value);
        if (html) {
          valSpan.innerHTML = html;
          valSpan.classList.remove("muted");
        } else {
          valSpan.textContent = "날짜·시간 선택";
          valSpan.classList.add("muted");
        }
        field.disabled = !!input.disabled;
        return;
      }
      const disp = fmtDisplay(input.value, input);
      if (disp) {
        valSpan.textContent = disp;
        valSpan.classList.remove("muted");
      } else {
        valSpan.textContent = "날짜·시간 선택";
        valSpan.classList.add("muted");
      }
      field.disabled = !!input.disabled;
    }

    // input.value 접근자 래핑: 외부에서 .value 를 바꿔도 표시 갱신
    const proto = Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value"
    );
    try {
      Object.defineProperty(input, "value", {
        configurable: true,
        get() {
          return proto.get.call(this);
        },
        set(v) {
          proto.set.call(this, v);
          refresh();
        },
      });
    } catch (_e) {
      /* 일부 환경에서 재정의 불가 시 무시 */
    }
    // disabled 변화도 반영
    const disabledDesc = Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "disabled"
    );
    try {
      Object.defineProperty(input, "disabled", {
        configurable: true,
        get() {
          return disabledDesc.get.call(this);
        },
        set(v) {
          disabledDesc.set.call(this, v);
          field.disabled = !!v;
        },
      });
    } catch (_e) {
      /* noop */
    }

    field.addEventListener("click", function (e) {
      e.preventDefault();
      if (input.disabled) return;
      openPicker(input, field, refresh);
    });

    refresh();
  }

  function openPicker(input, field, refresh) {
    closeOpen();

    const initial =
      parseValue(input.value) ||
      (function () {
        const now = new Date();
        return {
          y: now.getFullYear(),
          mo: now.getMonth(),
          d: now.getDate(),
          hh: now.getHours(),
          mm: roundMinute(now.getMinutes()),
        };
      })();

    const draft = Object.assign({}, initial);
    let viewY = draft.y;
    let viewMo = draft.mo;

    const useSheet = shouldUseSheet(field);
    let backdrop = null;

    const pop = document.createElement("div");
    pop.className = "jcc-dtp-pop";
    if (useSheet) pop.classList.add("jcc-dtp-pop--sheet");
    pop.setAttribute("role", "dialog");
    pop.setAttribute("aria-modal", "true");

    // 헤더 (월 이동)
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

    // 시간 영역 (시/분 스테퍼 + 직접 입력)
    const timeRow = document.createElement("div");
    timeRow.className = "jcc-dtp-time";
    const timeLbl = document.createElement("span");
    timeLbl.className = "jcc-dtp-timeLbl";
    timeLbl.textContent = "시간";

    // items: [{ value, label }]. opts.readonly=true 면 직접 입력 불가(목록 선택 전용)
    function buildSelect(ariaLabel, items, opts) {
      opts = opts || {};
      const wrap = document.createElement("div");
      wrap.className = "jcc-dtp-select";
      if (opts.wide) wrap.classList.add("jcc-dtp-select--wide");
      const inp = document.createElement("input");
      inp.className = "jcc-dtp-num";
      inp.type = "text";
      inp.setAttribute("aria-label", ariaLabel);
      inp.setAttribute("role", "combobox");
      inp.setAttribute("aria-haspopup", "listbox");
      if (opts.readonly) {
        inp.readOnly = true;
      } else {
        inp.setAttribute("inputmode", "numeric");
        inp.maxLength = 2;
        inp.size = 2;
      }
      const caret = document.createElement("span");
      caret.className = "jcc-dtp-caret";
      caret.setAttribute("aria-hidden", "true");
      caret.textContent = "▾";

      // 선택 드롭다운 (클릭/포커스 시 목록 표시)
      const dd = document.createElement("div");
      dd.className = "jcc-dtp-dropdown";
      dd.hidden = true;
      dd.setAttribute("role", "listbox");
      dd.setAttribute("aria-label", ariaLabel + " 선택");
      const optEls = new Map();
      (items || []).forEach(function (it) {
        const o = document.createElement("button");
        o.type = "button";
        o.className = "jcc-dtp-opt";
        o.textContent = it.label;
        o.dataset.value = String(it.value);
        o.setAttribute("role", "option");
        dd.appendChild(o);
        optEls.set(String(it.value), o);
      });

      wrap.appendChild(inp);
      wrap.appendChild(caret);
      wrap.appendChild(dd);

      function setSelected(value) {
        const key = String(value);
        optEls.forEach(function (el, k) {
          el.classList.toggle("is-sel", k === key);
        });
      }
      return {
        wrap: wrap,
        inp: inp,
        caret: caret,
        dropdown: dd,
        setSelected: setSelected,
      };
    }

    const HOUR_ITEMS = Array.from({ length: 24 }, function (_, i) {
      return { value: i, label: pad(i) };
    });
    const MINUTE_ITEMS = Array.from({ length: 12 }, function (_, i) {
      return { value: i * 5, label: pad(i * 5) };
    });

    const hourCtl = buildSelect("시", HOUR_ITEMS);
    const colon = document.createElement("span");
    colon.className = "jcc-dtp-colon";
    colon.textContent = ":";
    const minCtl = buildSelect("분", MINUTE_ITEMS);
    timeRow.appendChild(timeLbl);
    timeRow.appendChild(hourCtl.wrap);
    timeRow.appendChild(colon);
    timeRow.appendChild(minCtl.wrap);
    pop.appendChild(timeRow);

    // 푸터 (빠른 동작)
    const foot = document.createElement("div");
    foot.className = "jcc-dtp-foot";
    const clearBtn = document.createElement("button");
    clearBtn.type = "button";
    clearBtn.className = "jcc-dtp-text";
    clearBtn.textContent = "지우기";
    const nowBtn = document.createElement("button");
    nowBtn.type = "button";
    nowBtn.className = "jcc-dtp-text";
    nowBtn.textContent = "지금";
    const okBtn = document.createElement("button");
    okBtn.type = "button";
    okBtn.className = "jcc-dtp-ok";
    okBtn.textContent = "확인";
    foot.appendChild(clearBtn);
    foot.appendChild(nowBtn);
    foot.appendChild(okBtn);

    // 제약(입실<퇴실 등) 위반 시 팝업 안에 보여줄 안내문구.
    const errEl = document.createElement("div");
    errEl.className = "jcc-dtp-error";
    errEl.setAttribute("role", "alert");
    errEl.hidden = true;
    pop.appendChild(errEl);
    pop.appendChild(foot);

    // 형제 필드(같은 행 또는 같은 폼)에서 경계 시각을 읽어 제약을 검사한다.
    // - data-dtp-min-selector: 선택값이 이 시각보다 "무조건 뒤"여야 함 (퇴실)
    // - data-dtp-max-selector: 선택값이 이 시각보다 "무조건 앞"이어야 함 (입실)
    function readConstraint(attrKey) {
      const sel = input.dataset[attrKey];
      if (!sel) return null;
      const scope = input.closest("tr") || input.closest("form") || document;
      const src = scope.querySelector(sel);
      if (!src) return null;
      return parseValue(src.value);
    }
    function partMs(p) {
      return new Date(p.y, p.mo, p.d, p.hh, p.mm).getTime();
    }
    function constraintError() {
      const a = new Date(
        draft.y,
        draft.mo,
        draft.d,
        draft.hh,
        draft.mm
      ).getTime();
      const min = readConstraint("dtpMinSelector");
      if (min && a <= partMs(min)) {
        return input.dataset.dtpMinMessage || "더 뒤의 시각을 선택하세요.";
      }
      const max = readConstraint("dtpMaxSelector");
      if (max && a >= partMs(max)) {
        return input.dataset.dtpMaxMessage || "더 앞의 시각을 선택하세요.";
      }
      return "";
    }
    function updateValidity() {
      const msg = constraintError();
      if (msg) {
        errEl.textContent = msg;
        errEl.hidden = false;
        okBtn.disabled = true;
      } else {
        errEl.hidden = true;
        okBtn.disabled = false;
      }
    }

    if (useSheet) {
      backdrop = document.createElement("div");
      backdrop.className = "jcc-dtp-backdrop";
      backdrop.setAttribute("aria-hidden", "true");
      document.body.appendChild(backdrop);
      document.body.classList.add("jcc-dtp-open");
    }
    document.body.appendChild(pop);

    let openDd = null;
    function scrollSelIntoView(ctl) {
      if (openDd !== ctl || ctl.dropdown.hidden) return;
      const sel = ctl.dropdown.querySelector(".jcc-dtp-opt.is-sel");
      if (sel) sel.scrollIntoView({ block: "nearest" });
    }
    function closeDropdown() {
      if (openDd) {
        openDd.dropdown.hidden = true;
        openDd = null;
      }
    }
    function openDropdown(ctl) {
      if (openDd === ctl) {
        scrollSelIntoView(ctl);
        return;
      }
      closeDropdown();
      ctl.dropdown.hidden = false;
      openDd = ctl;
      scrollSelIntoView(ctl);
    }
    function wireStepper(ctl, setter) {
      ctl.inp.addEventListener("focus", function () {
        openDropdown(ctl);
      });
      ctl.inp.addEventListener("click", function () {
        openDropdown(ctl);
      });
      ctl.inp.addEventListener("blur", function () {
        setTimeout(function () {
          if (openDd === ctl && document.activeElement !== ctl.inp) {
            closeDropdown();
          }
        }, 120);
      });
      // ▾ 셰브론 클릭: 입력에 포커스 주고 목록 토글
      ctl.caret.addEventListener("mousedown", function (e) {
        e.preventDefault();
        if (openDd === ctl) {
          closeDropdown();
        } else {
          ctl.inp.focus();
          openDropdown(ctl);
        }
      });
      ctl.dropdown.addEventListener("mousedown", function (e) {
        const o = e.target.closest(".jcc-dtp-opt");
        if (!o) return;
        e.preventDefault(); // 포커스 유지(blur 방지)
        setter(o.dataset.value);
        closeDropdown();
      });
    }

    // draft.hh(0~23)/draft.mm 기준으로 시·분 컨트롤 표시 동기화
    function renderTime() {
      hourCtl.inp.value = pad(draft.hh);
      hourCtl.setSelected(draft.hh);
      minCtl.inp.value = pad(draft.mm);
      minCtl.setSelected(draft.mm);
      updateValidity();
    }
    function setHour(h) {
      h = Math.round(h);
      if (Number.isNaN(h)) return;
      draft.hh = Math.min(23, Math.max(0, h));
      renderTime();
      scrollSelIntoView(hourCtl);
    }
    function setMinute(m) {
      m = ((Math.round(m) % 60) + 60) % 60;
      draft.mm = m;
      renderTime();
      scrollSelIntoView(minCtl);
    }

    function renderGrid() {
      title.textContent = `${viewY}년 ${viewMo + 1}월`;
      grid.innerHTML = "";
      const first = new Date(viewY, viewMo, 1);
      const startDow = first.getDay();
      const gridStart = new Date(viewY, viewMo, 1 - startDow);
      const today = new Date();
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
          d.getFullYear() === today.getFullYear() &&
          d.getMonth() === today.getMonth() &&
          d.getDate() === today.getDate()
        ) {
          cell.classList.add("today");
        }
        if (
          d.getFullYear() === draft.y &&
          d.getMonth() === draft.mo &&
          d.getDate() === draft.d
        ) {
          cell.classList.add("selected");
        }
        cell.addEventListener("click", function () {
          draft.y = d.getFullYear();
          draft.mo = d.getMonth();
          draft.d = d.getDate();
          if (d.getMonth() !== viewMo) {
            viewY = d.getFullYear();
            viewMo = d.getMonth();
          }
          renderGrid();
        });
        grid.appendChild(cell);
      }
      updateValidity();
    }

    renderTime();
    hourCtl.inp.addEventListener("input", function () {
      const v = parseInt(hourCtl.inp.value.replace(/\D/g, ""), 10);
      if (!Number.isNaN(v)) {
        draft.hh = Math.min(23, Math.max(0, v));
        updateValidity();
      }
    });
    hourCtl.inp.addEventListener("blur", function () {
      renderTime();
    });
    minCtl.inp.addEventListener("input", function () {
      const v = parseInt(minCtl.inp.value.replace(/\D/g, ""), 10);
      if (!Number.isNaN(v)) {
        draft.mm = Math.max(0, Math.min(59, v));
        updateValidity();
      }
    });
    minCtl.inp.addEventListener("blur", function () {
      renderTime();
    });

    wireStepper(hourCtl, function (v) {
      setHour(Number(v));
    });
    wireStepper(minCtl, function (v) {
      setMinute(Number(v));
    });

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

    function commit(value) {
      input.value = value; // 래핑된 setter → 표시 갱신
      input.dispatchEvent(new Event("change", { bubbles: true }));
      ctrl.close();
    }

    okBtn.addEventListener("click", function () {
      commit(fmtValue(draft));
    });
    clearBtn.addEventListener("click", function () {
      commit("");
    });
    nowBtn.addEventListener("click", function () {
      const now = new Date();
      draft.y = now.getFullYear();
      draft.mo = now.getMonth();
      draft.d = now.getDate();
      draft.hh = now.getHours();
      draft.mm = roundMinute(now.getMinutes());
      renderTime();
      viewY = draft.y;
      viewMo = draft.mo;
      renderGrid();
    });

    renderGrid();

    function position() {
      if (useSheet) return;
      const margin = 8;
      const r = field.getBoundingClientRect();
      const vh = getViewportHeight();

      // 뷰포트보다 길면 내부 스크롤로 전환(최후 수단)하고, 그 높이로 위치 계산.
      pop.style.maxHeight = `${vh - margin * 2}px`;
      pop.style.overflowY = "auto";

      const pw = pop.offsetWidth || 280;
      const ph = pop.offsetHeight || 320;

      let left = r.left;
      if (left + pw > window.innerWidth - margin) {
        left = window.innerWidth - pw - margin;
      }
      left = Math.max(margin, left);

      // 아래 우선, 아래가 부족하면 위로 뒤집기.
      const spaceBelow = vh - r.bottom;
      const spaceAbove = r.top;
      let top;
      if (spaceBelow >= ph + margin || spaceBelow >= spaceAbove) {
        top = r.bottom + 6;
      } else {
        top = r.top - ph - 6;
      }
      // 어느 쪽이든 화면 안에 전체가 보이도록 clamp.
      top = Math.min(top, vh - ph - margin);
      top = Math.max(margin, top);

      pop.style.left = `${left}px`;
      pop.style.top = `${top}px`;
    }
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
      if (e.key === "Escape") {
        if (openDd) {
          closeDropdown();
        } else {
          ctrl.close();
        }
      }
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
        if (backdrop && backdrop.parentNode) backdrop.parentNode.removeChild(backdrop);
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
      if (useSheet) {
        okBtn.focus();
      }
    }, 0);
  }

  function enhanceAll(root) {
    const scope = root || document;
    const sel =
      'input.jcc-retreat-stampInput, #retreatAttExpectedIn, #retreatAttExpectedOut, input[data-dtp]';
    scope.querySelectorAll(sel).forEach(enhance);
  }

  window.JccDateTimePicker = {
    enhance: enhance,
    enhanceAll: enhanceAll,
    close: closeOpen,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      enhanceAll(document);
    });
  } else {
    enhanceAll(document);
  }
})();
