/*
 * 커스텀 시간 피커 (바닐라 JS, 외부 라이브러리 없음)
 *
 * 네이티브 <input type="time"> 를 점진적으로 강화한다.
 * - 원본 input 은 DOM 에 그대로 두고(값 보관) 시각적으로 숨긴다.
 * - 클릭하기 좋은 "필드 버튼" + 오전/오후·시·분 선택 팝업을 보여준다.
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

  function to12h(hh) {
    const isPm = hh >= 12;
    let h12 = hh % 12;
    if (h12 === 0) h12 = 12;
    return { h12: h12, mer: isPm ? "pm" : "am" };
  }
  function from12h(h12, mer) {
    let h = h12 % 12;
    if (mer === "pm") h += 12;
    return ((h % 24) + 24) % 24;
  }

  function fmtDisplay(v) {
    const s = parseValue(v);
    if (!s) return "";
    const t = to12h(s.hh);
    const merLabel = t.mer === "pm" ? "오후" : "오전";
    return `${merLabel} ${t.h12}:${pad(s.mm)}`;
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

    const HOUR_ITEMS = Array.from({ length: 12 }, function (_, i) {
      const h = i + 1;
      return { value: h, label: String(h) };
    });
    const MINUTE_ITEMS = Array.from({ length: 12 }, function (_, i) {
      return { value: i * 5, label: pad(i * 5) };
    });
    const MERIDIEM_ITEMS = [
      { value: "am", label: "오전" },
      { value: "pm", label: "오후" },
    ];

    const merCtl = buildSelect("오전·오후", MERIDIEM_ITEMS, {
      readonly: true,
      wide: true,
    });
    const hourCtl = buildSelect("시", HOUR_ITEMS);
    const colon = document.createElement("span");
    colon.className = "jcc-dtp-colon";
    colon.textContent = ":";
    const minCtl = buildSelect("분", MINUTE_ITEMS);
    timeRow.appendChild(timeLbl);
    timeRow.appendChild(merCtl.wrap);
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
        e.preventDefault();
        setter(o.dataset.value);
        closeDropdown();
      });
    }

    function renderTime() {
      const t = to12h(draft.hh);
      hourCtl.inp.value = String(t.h12);
      hourCtl.setSelected(t.h12);
      merCtl.inp.value = t.mer === "pm" ? "오후" : "오전";
      merCtl.setSelected(t.mer);
      minCtl.inp.value = pad(draft.mm);
      minCtl.setSelected(draft.mm);
    }
    function setHour12(h12) {
      h12 = Math.round(h12);
      if (Number.isNaN(h12)) return;
      h12 = Math.min(12, Math.max(1, h12));
      draft.hh = from12h(h12, to12h(draft.hh).mer);
      renderTime();
      scrollSelIntoView(hourCtl);
    }
    function setMeridiem(mer) {
      draft.hh = from12h(to12h(draft.hh).h12, mer === "pm" ? "pm" : "am");
      renderTime();
      scrollSelIntoView(merCtl);
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
        draft.hh = from12h(Math.min(12, Math.max(1, v)), to12h(draft.hh).mer);
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

    wireStepper(merCtl, function (v) {
      setMeridiem(v);
    });
    wireStepper(hourCtl, function (v) {
      setHour12(Number(v));
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
    }

    const ctrl = {
      close() {
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
