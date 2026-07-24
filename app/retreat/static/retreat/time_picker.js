/*
 * 커스텀 시간 피커 (바닐라 JS, 외부 라이브러리 없음)
 *
 * 네이티브 <input type="time"> 를 점진적으로 강화한다.
 * - 원본 input 은 DOM 에 그대로 두고(값 보관) 시각적으로 숨긴다.
 * - 클릭하기 좋은 "필드 버튼" + 24h 시·분 선택 팝업을 보여준다.
 * - 확인 시 원본 input.value 를 "HH:mm"(24h) 으로 채우고 change 이벤트를 발생시킨다.
 * - datetime_picker.js 의 .jcc-dtp-* 스타일을 재사용해 디자인을 일치시킨다.
 *
 * 대상: input[type="time"][data-tp]
 */
(function () {
  "use strict";

  let openController = null;

  function pad(n) {
    return String(n).padStart(2, "0");
  }

  function parseValue(v) {
    if (!v) return null;
    const m = /^(\d{1,2}):(\d{2})/.exec(v);
    if (!m) return null;
    return { hh: Number(m[1]), mm: Number(m[2]) };
  }

  function fmtValue(s) {
    return `${pad(s.hh)}:${pad(s.mm)}`;
  }

  function fmtDisplay(v) {
    const s = parseValue(v);
    if (!s) return "";
    return `${pad(s.hh)}:${pad(s.mm)}`;
  }

  function closeOpen() {
    if (openController) openController.close();
  }

  function enhance(input) {
    if (!input || input.__tpDone) return;
    input.__tpDone = true;

    input.classList.add("jcc-dtp-native");
    input.setAttribute("tabindex", "-1");
    input.setAttribute("aria-hidden", "true");

    const placeholder = input.getAttribute("data-placeholder") || "시간 선택";

    const field = document.createElement("button");
    field.type = "button";
    field.className = "jcc-dtp-field jcc-tp-field";
    const labelText = input.getAttribute("aria-label");
    if (labelText) field.setAttribute("aria-label", labelText);

    const valSpan = document.createElement("span");
    valSpan.className = "jcc-dtp-val";
    const icon = document.createElement("span");
    icon.className = "jcc-dtp-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = "🕐";
    field.appendChild(valSpan);
    field.appendChild(icon);

    input.insertAdjacentElement("afterend", field);

    function refresh() {
      const disp = fmtDisplay(input.value);
      if (disp) {
        valSpan.textContent = disp;
        valSpan.classList.remove("muted");
      } else {
        valSpan.textContent = placeholder;
        valSpan.classList.add("muted");
      }
      field.disabled = !!input.disabled;
    }

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
      /* noop */
    }

    field.addEventListener("click", function (e) {
      e.preventDefault();
      if (input.disabled) return;
      openPicker(input, field, refresh);
    });

    refresh();
  }

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
    return { wrap, inp, caret, dropdown: dd, setSelected };
  }

  function openPicker(input, field, refresh) {
    closeOpen();

    const initial = parseValue(input.value) || { hh: 9, mm: 0 };
    const draft = { hh: initial.hh, mm: initial.mm };

    const pop = document.createElement("div");
    pop.className = "jcc-dtp-pop jcc-tp-pop";
    pop.setAttribute("role", "dialog");

    const timeRow = document.createElement("div");
    timeRow.className = "jcc-dtp-time";
    const timeLbl = document.createElement("span");
    timeLbl.className = "jcc-dtp-timeLbl";
    timeLbl.textContent = "시간";

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

    const foot = document.createElement("div");
    foot.className = "jcc-dtp-foot";
    const clearBtn = document.createElement("button");
    clearBtn.type = "button";
    clearBtn.className = "jcc-dtp-text";
    clearBtn.textContent = "지우기";
    const okBtn = document.createElement("button");
    okBtn.type = "button";
    okBtn.className = "jcc-dtp-ok";
    okBtn.textContent = "확인";
    foot.appendChild(clearBtn);
    foot.appendChild(okBtn);
    pop.appendChild(foot);

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
    // 시간·분 목록은 항상 박스 위쪽.
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
    function armGhostClickGuard() {
      swallowClickUntil = Date.now() + 450;
    }
    function wireStepper(ctl, setter) {
      ctl.wrap.addEventListener("pointerdown", function (e) {
        if (e.target.closest(".jcc-dtp-opt")) return;
        if (e.target.closest(".jcc-dtp-dropdown")) return;
        e.preventDefault();
        const onInp = e.target === ctl.inp;
        if (openDd === ctl) {
          if (onInp) {
            try {
              ctl.inp.focus({ preventScroll: true });
            } catch (_err) {
              ctl.inp.focus();
            }
            return;
          }
          closeDropdown();
          return;
        }
        if (onInp) {
          try {
            ctl.inp.focus({ preventScroll: true });
          } catch (_err) {
            ctl.inp.focus();
          }
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

    function renderTime() {
      hourCtl.inp.value = pad(draft.hh);
      hourCtl.setSelected(draft.hh);
      minCtl.inp.value = pad(draft.mm);
      minCtl.setSelected(draft.mm);
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

    renderTime();
    hourCtl.inp.addEventListener("input", function () {
      const v = parseInt(hourCtl.inp.value.replace(/\D/g, ""), 10);
      if (!Number.isNaN(v)) {
        draft.hh = Math.min(23, Math.max(0, v));
      }
    });
    hourCtl.inp.addEventListener("blur", function () {
      renderTime();
    });
    minCtl.inp.addEventListener("input", function () {
      const v = parseInt(minCtl.inp.value.replace(/\D/g, ""), 10);
      if (!Number.isNaN(v)) draft.mm = Math.max(0, Math.min(59, v));
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

    function commit(value) {
      input.value = value;
      input.dispatchEvent(new Event("change", { bubbles: true }));
      ctrl.close();
    }

    okBtn.addEventListener("click", function () {
      commit(fmtValue(draft));
    });
    clearBtn.addEventListener("click", function () {
      commit("");
    });

    function position() {
      const r = field.getBoundingClientRect();
      const pw = pop.offsetWidth || 260;
      const ph = pop.offsetHeight || 120;
      let left = r.left;
      if (left + pw > window.innerWidth - 8) {
        left = Math.max(8, window.innerWidth - pw - 8);
      }
      let top = r.bottom + 6;
      if (top + ph > window.innerHeight - 8 && r.top - ph - 6 > 8) {
        top = r.top - ph - 6;
      }
      pop.style.left = `${Math.max(8, left)}px`;
      pop.style.top = `${Math.max(8, top)}px`;
    }
    position();

    function onDocClick(e) {
      if (Date.now() < swallowClickUntil) {
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      if (e.target.closest && e.target.closest(".jcc-dtp-dropdown")) return;
      if (pop.contains(e.target) || field.contains(e.target)) return;
      ctrl.close();
    }
    function onKey(e) {
      if (e.key === "Escape") {
        if (openDd) closeDropdown();
        else ctrl.close();
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
        if (pop.parentNode) pop.parentNode.removeChild(pop);
        if (openController === ctrl) openController = null;
      },
    };
    openController = ctrl;

    setTimeout(function () {
      document.addEventListener("click", onDocClick, true);
      document.addEventListener("keydown", onKey, true);
      window.addEventListener("resize", onScrollResize, true);
      window.addEventListener("scroll", onScrollResize, true);
    }, 0);
  }

  function enhanceAll(root) {
    const scope = root || document;
    scope.querySelectorAll('input[type="time"][data-tp]').forEach(enhance);
  }

  window.JccTimePicker = {
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
