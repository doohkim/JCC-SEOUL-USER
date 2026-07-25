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

  function computeTravelLabel(input, valueOverride) {
    if (!input) return "";
    const val = String(
      valueOverride != null ? valueOverride : input.value || ""
    ).slice(0, 16);
    if (!val) return "";
    const direction = input.dataset.travelDirection || "";
    const presets =
      (direction &&
        window.RETREAT_CTX &&
        window.RETREAT_CTX.travelPresets &&
        window.RETREAT_CTX.travelPresets[direction]) ||
      [];
    if (input.dataset.travelIsCustom === "1") return "자차";
    for (let i = 0; i < presets.length; i++) {
      const p = presets[i];
      if (!p || p.manual || !p.occurs_at) continue;
      if (String(p.occurs_at).slice(0, 16) === val) {
        return p.label || "자차";
      }
    }
    return "자차";
  }

  function applyTravelLabelToInput(input, label) {
    if (!input) return;
    if (label) input.dataset.travelLabel = label;
    else delete input.dataset.travelLabel;
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
    if (input.dataset.travelDirection) {
      field.classList.add("jcc-dtp-field--travel");
    }
    const labelText = input.getAttribute("aria-label");
    if (labelText) field.setAttribute("aria-label", labelText);

    const travelChip = document.createElement("span");
    travelChip.className = "jcc-dtp-travel";
    travelChip.hidden = true;
    travelChip.setAttribute("aria-hidden", "true");

    const valSpan = document.createElement("span");
    valSpan.className = "jcc-dtp-val";
    const icon = document.createElement("span");
    icon.className = "jcc-dtp-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = "📅";
    if (input.dataset.travelDirection) {
      field.appendChild(travelChip);
    }
    field.appendChild(valSpan);
    field.appendChild(icon);

    input.insertAdjacentElement("afterend", field);

    function refreshTravelChip() {
      if (!input.dataset.travelDirection) return;
      let label = input.dataset.travelLabel || "";
      if (!label && input.value) {
        label = computeTravelLabel(input);
        applyTravelLabelToInput(input, label);
      }
      if (!input.value) {
        applyTravelLabelToInput(input, "");
        label = "";
      }
      if (label) {
        travelChip.textContent = label;
        travelChip.title = label;
        travelChip.hidden = false;
        travelChip.classList.toggle(
          "jcc-dtp-travel--custom",
          label === "자차"
        );
      } else {
        travelChip.textContent = "";
        travelChip.removeAttribute("title");
        travelChip.hidden = true;
        travelChip.classList.remove("jcc-dtp-travel--custom");
      }
    }

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
        refreshTravelChip();
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
      refreshTravelChip();
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

    input.__dtpRefresh = refresh;
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

    // 교통(입·퇴실) 프리셋 chip — RETREAT_CTX.travelPresets + data-travel-direction
    const travelDirection = input.dataset.travelDirection || "";
    const travelPresets =
      (travelDirection &&
        window.RETREAT_CTX &&
        window.RETREAT_CTX.travelPresets &&
        window.RETREAT_CTX.travelPresets[travelDirection]) ||
      [];
    let selectedPresetChip = null;
    // 명시 자차 의도: dataset "1"/"0"/없음(레거시=자동매칭)
    let sessionIsCustom =
      input.dataset.travelIsCustom === "1"
        ? true
        : input.dataset.travelIsCustom === "0"
          ? false
          : null;
    function writeTravelIsCustom(flag) {
      if (flag === true) input.dataset.travelIsCustom = "1";
      else if (flag === false) input.dataset.travelIsCustom = "0";
      else delete input.dataset.travelIsCustom;
    }
    function markPresetSelected(chip) {
      if (!chipsEl) return;
      chipsEl.querySelectorAll(".jcc-dtp-preset").forEach(function (el) {
        el.classList.toggle("is-sel", el === chip);
      });
      selectedPresetChip = chip || null;
    }
    let chipsEl = null;
    if (Array.isArray(travelPresets) && travelPresets.length) {
      const presetsRow = document.createElement("div");
      presetsRow.className = "jcc-dtp-presets";
      presetsRow.setAttribute("role", "group");
      presetsRow.setAttribute(
        "aria-label",
        travelDirection === "departure" ? "퇴실 교통" : "입실 교통"
      );

      const icon = document.createElement("span");
      icon.className = "jcc-dtp-presets-icon";
      icon.setAttribute("aria-hidden", "true");
      icon.innerHTML =
        '<svg viewBox="0 0 24 24" fill="none" focusable="false"><path d="M3 13l1.5-4.5A2 2 0 016.4 7h7.2a2 2 0 011.9 1.4L17 13M5 13h12v4H5v-4z" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><circle cx="7.5" cy="17.5" r="1.4" fill="currentColor"/><circle cx="14.5" cy="17.5" r="1.4" fill="currentColor"/></svg>';
      presetsRow.appendChild(icon);

      chipsEl = document.createElement("div");
      chipsEl.className = "jcc-dtp-presets-chips";
      const currentVal = String(input.value || "").slice(0, 16);
      let matchedChip = null;
      let defaultManualChip = null;
      travelPresets.forEach(function (p) {
        if (!p) return;
        const manual = !!p.manual;
        if (!manual && !p.occurs_at) return;
        const occurs = p.occurs_at ? String(p.occurs_at).slice(0, 16) : "";
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "jcc-dtp-preset";
        if (manual) chip.classList.add("jcc-dtp-preset--manual");
        chip.textContent = p.label || occurs || "자차";
        chip.dataset.manual = manual ? "1" : "0";
        if (occurs) chip.dataset.occursAt = occurs;
        if (occurs && occurs === currentVal) matchedChip = chip;
        if (manual && !defaultManualChip) defaultManualChip = chip;
        chip.addEventListener("click", function () {
          markPresetSelected(chip);
          if (manual) {
            // 자차: 달력·시간 유지, 닫지 않음
            sessionIsCustom = true;
            return;
          }
          sessionIsCustom = false;
          writeTravelIsCustom(false);
          commit(occurs);
        });
        chipsEl.appendChild(chip);
      });
      presetsRow.appendChild(chipsEl);
      pop.appendChild(presetsRow);
      // 명시 자차 우선, 아니면 시각 매칭(편의), 없으면 자차
      const initialChip =
        sessionIsCustom === true
          ? defaultManualChip
          : matchedChip ||
            (!currentVal ? defaultManualChip : null) ||
            defaultManualChip;
      if (initialChip) {
        markPresetSelected(initialChip);
        if (
          sessionIsCustom === null &&
          initialChip.dataset.manual === "1" &&
          !matchedChip
        ) {
          // 레거시·미매칭: 피커 세션만 자차로 두고, 저장 전엔 dataset을 건드리지 않음
          sessionIsCustom = true;
        } else if (sessionIsCustom === null && matchedChip) {
          sessionIsCustom = false;
        }
      }
    }

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

    // 시간 영역 (시/분 목록 선택 전용)
    const timeRow = document.createElement("div");
    timeRow.className = "jcc-dtp-time";
    const timeLbl = document.createElement("span");
    timeLbl.className = "jcc-dtp-timeLbl";
    timeLbl.textContent = "시간";

    // items: [{ value, label }]. 시·분은 직접 입력 없이 목록으로만 선택한다.
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
      inp.readOnly = true;
      inp.tabIndex = -1;
      inp.setAttribute("inputmode", "none");
      inp.setAttribute("aria-readonly", "true");
      inp.size = 2;
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
    let swallowClickUntil = 0;
    function clearDropdownPlacement(dd) {
      dd.style.top = "";
      dd.style.left = "";
      dd.style.width = "";
      dd.style.right = "";
      dd.style.bottom = "";
      dd.style.maxHeight = "";
    }
    function setDdOpenClass(on) {
      pop.classList.toggle("jcc-dtp-pop--ddOpen", !!on);
    }
    // 시간·분 목록은 항상 박스 위쪽(달력 쪽). 아래로 열리면 바깥 클릭으로 피커가 닫히기 쉬움.
    function positionDropdown(ctl) {
      const dd = ctl.dropdown;
      if (dd.hidden) return;
      const r = ctl.wrap.getBoundingClientRect();
      const margin = 8;
      const maxH = 168;
      const spaceAbove = Math.max(72, r.top - margin);
      const h = Math.min(maxH, spaceAbove);
      dd.style.left = `${Math.round(r.left)}px`;
      dd.style.width = `${Math.max(Math.round(r.width), 48)}px`;
      dd.style.right = "auto";
      dd.style.bottom = "auto";
      dd.style.maxHeight = `${h}px`;
      dd.style.top = `${Math.max(margin, Math.round(r.top - h - 6))}px`;
      const used = Math.min(h, dd.scrollHeight || h);
      dd.style.top = `${Math.max(margin, Math.round(r.top - used - 6))}px`;
    }
    function scrollSelIntoView(ctl) {
      if (openDd !== ctl || ctl.dropdown.hidden) return;
      const sel = ctl.dropdown.querySelector(".jcc-dtp-opt.is-sel");
      if (sel) sel.scrollIntoView({ block: "nearest" });
      positionDropdown(ctl);
    }
    function closeDropdown() {
      if (openDd) {
        openDd.dropdown.hidden = true;
        clearDropdownPlacement(openDd.dropdown);
        openDd = null;
      }
      // 목록이 사라진 직후에도 달력을 잠깐 막아 고스트 click 이 날짜로 안 가게 함.
      if (Date.now() < swallowClickUntil) {
        setDdOpenClass(true);
        const wait = Math.max(0, swallowClickUntil - Date.now()) + 30;
        setTimeout(function () {
          if (!openDd) setDdOpenClass(false);
        }, wait);
      } else {
        setDdOpenClass(false);
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
      setDdOpenClass(true);
      positionDropdown(ctl);
      scrollSelIntoView(ctl);
    }
    // 옵션 탭 직후 목록이 사라지면 같은 좌표 click 이 달력으로 통과(모바일 고스트 클릭).
    function armGhostClickGuard() {
      swallowClickUntil = Date.now() + 450;
    }
    function wireStepper(ctl, setter) {
      // 박스 전체(여백·▾ 포함)에서 열리게 — input 좁은 영역만 누르지 않아도 됨.
      // 숫자 input 을 직접 누를 때만 focus(타이핑/키보드). 그 외에는 목록만 연다.
      ctl.wrap.addEventListener("pointerdown", function (e) {
        if (e.target.closest(".jcc-dtp-opt")) return;
        if (e.target.closest(".jcc-dtp-dropdown")) return;
        e.preventDefault();
        if (openDd === ctl) {
          closeDropdown();
          return;
        }
        openDropdown(ctl);
      });
      ctl.inp.addEventListener("focus", function () {
        openDropdown(ctl);
      });
      ctl.inp.addEventListener("blur", function () {
        setTimeout(function () {
          if (openDd !== ctl) return;
          const ae = document.activeElement;
          if (ae === ctl.inp || ctl.wrap.contains(ae) || ctl.dropdown.contains(ae)) {
            return;
          }
          closeDropdown();
        }, 150);
      });
      // pointerdown: blur 레이스 전에 선택. 닫은 뒤 고스트 click 은 가드로 삼킴.
      ctl.dropdown.addEventListener(
        "pointerdown",
        function (e) {
          const o = e.target.closest(".jcc-dtp-opt");
          if (!o) return;
          e.preventDefault();
          e.stopPropagation();
          setter(o.dataset.value);
          armGhostClickGuard();
          closeDropdown();
        },
        true
      );
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
        cell.addEventListener(
          "pointerdown",
          function (e) {
            if (openDd || Date.now() < swallowClickUntil) {
              e.preventDefault();
              e.stopPropagation();
            }
          },
          true
        );
        cell.addEventListener("click", function (e) {
          // 시·분 옵션 탭 직후 합성 click 이 날짜로 떨어지지 않게
          if (openDd || Date.now() < swallowClickUntil) {
            e.preventDefault();
            e.stopPropagation();
            return;
          }
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
      if (!value) {
        writeTravelIsCustom(null);
        applyTravelLabelToInput(input, "");
      } else if (travelPresets.length) {
        // 버스 칩 경로에서 이미 false로 쓴 경우 유지; OK는 sessionIsCustom 반영
        if (sessionIsCustom === true) writeTravelIsCustom(true);
        else if (sessionIsCustom === false) writeTravelIsCustom(false);
        applyTravelLabelToInput(input, computeTravelLabel(input, value));
      } else {
        applyTravelLabelToInput(input, "자차");
      }
      input.value = value; // 래핑된 setter → 표시 갱신
      input.dispatchEvent(new Event("change", { bubbles: true }));
      ctrl.close();
    }

    okBtn.addEventListener("click", function () {
      if (travelPresets.length && selectedPresetChip) {
        sessionIsCustom = selectedPresetChip.dataset.manual === "1";
      }
      commit(fmtValue(draft));
    });
    clearBtn.addEventListener("click", function () {
      sessionIsCustom = null;
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
      if (Date.now() < swallowClickUntil) {
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      if (backdrop && e.target === backdrop) {
        ctrl.close();
        return;
      }
      // fixed 드롭다운 옵션 클릭 잔여 이벤트 — 팝업이 닫히지 않게
      if (e.target.closest && e.target.closest(".jcc-dtp-dropdown")) return;
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
      if (openDd) positionDropdown(openDd);
    }

    const ctrl = {
      close() {
        closeDropdown();
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
    computeTravelLabel: computeTravelLabel,
    applyTravelLabelToInput: applyTravelLabelToInput,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      enhanceAll(document);
    });
  } else {
    enhanceAll(document);
  }
})();
