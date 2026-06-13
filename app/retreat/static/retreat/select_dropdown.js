/* 네이티브 <select> 를 Toss 스타일 커스텀 드롭다운으로 강화.
 * - 원본 select 는 숨겨두고 값/change 이벤트를 그대로 동기화한다.
 * - data-cselect 속성이 붙은 select 에만 적용된다.
 * - <optgroup> 라벨을 지원한다.
 * - 메뉴는 position:fixed 로 띄워 스크롤되는 표/모달의 overflow 에 잘리지 않는다.
 * - 모달처럼 나중에 값이 프로그램으로 설정되는 경우 JccCustomSelect.refresh(root) 로 라벨을 다시 맞춘다.
 */
(function () {
  var CARET =
    '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">' +
    '<path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var CHECK =
    '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">' +
    '<path d="M5 12.5l4.5 4.5L19 7" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  function enhance(select) {
    if (!select || select.dataset.cselectReady) return;
    select.dataset.cselectReady = "1";

    var wrap = document.createElement("div");
    wrap.className = "jcc-cselect";
    select.parentNode.insertBefore(wrap, select);
    wrap.appendChild(select);
    select.classList.add("jcc-cselect-native");

    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "jcc-cselect-btn";
    btn.setAttribute("aria-haspopup", "listbox");
    btn.setAttribute("aria-expanded", "false");
    if (select.id) {
      var lbl = document.querySelector('label[for="' + select.id + '"]');
      if (lbl && !lbl.id) lbl.id = select.id + "-label";
      if (lbl) btn.setAttribute("aria-labelledby", lbl.id);
    } else if (select.getAttribute("aria-label")) {
      btn.setAttribute("aria-label", select.getAttribute("aria-label"));
    }

    var label = document.createElement("span");
    label.className = "jcc-cselect-label";
    var caret = document.createElement("span");
    caret.className = "jcc-cselect-caret";
    caret.innerHTML = CARET;
    btn.appendChild(label);
    btn.appendChild(caret);
    wrap.appendChild(btn);

    var menu = document.createElement("ul");
    menu.className = "jcc-cselect-menu";
    menu.setAttribute("role", "listbox");
    menu.hidden = true;
    wrap.appendChild(menu);

    function appendOpt(opt) {
      var li = document.createElement("li");
      li.className = "jcc-cselect-opt";
      li.setAttribute("role", "option");
      li.dataset.index = String(opt.index);
      var txt = document.createElement("span");
      txt.textContent = opt.textContent;
      li.appendChild(txt);
      var ck = document.createElement("span");
      ck.className = "jcc-cselect-check";
      ck.innerHTML = CHECK;
      li.appendChild(ck);
      if (opt.disabled) li.classList.add("is-disabled");
      if (opt.index === select.selectedIndex) {
        li.classList.add("is-selected");
        li.setAttribute("aria-selected", "true");
      } else {
        li.setAttribute("aria-selected", "false");
      }
      menu.appendChild(li);
    }

    function buildOptions() {
      menu.innerHTML = "";
      Array.prototype.forEach.call(select.children, function (node) {
        if (node.tagName === "OPTGROUP") {
          var gl = document.createElement("li");
          gl.className = "jcc-cselect-group";
          gl.setAttribute("role", "presentation");
          gl.textContent = node.label;
          menu.appendChild(gl);
          Array.prototype.forEach.call(node.children, function (opt) {
            if (opt.tagName === "OPTION") appendOpt(opt);
          });
        } else if (node.tagName === "OPTION") {
          appendOpt(node);
        }
      });
    }

    function syncLabel() {
      var opt = select.options[select.selectedIndex];
      label.textContent = opt ? opt.textContent : "";
      wrap.classList.toggle("is-placeholder", !select.value);
      btn.disabled = !!select.disabled;
    }
    select._cselectSync = syncLabel;

    function opts() {
      return Array.prototype.slice.call(menu.querySelectorAll(".jcc-cselect-opt"));
    }
    function setFocus(list, idx) {
      list.forEach(function (o) {
        o.classList.remove("is-focus");
      });
      if (idx >= 0 && list[idx]) {
        list[idx].classList.add("is-focus");
        list[idx].scrollIntoView({ block: "nearest" });
      }
    }

    function position() {
      var r = btn.getBoundingClientRect();
      menu.style.position = "fixed";
      menu.style.left = r.left + "px";
      menu.style.right = "auto";
      menu.style.minWidth = r.width + "px";
      menu.style.maxWidth = Math.max(r.width, Math.min(window.innerWidth - 16, 360)) + "px";
      menu.style.top = "0px";
      var mh = menu.offsetHeight;
      var spaceBelow = window.innerHeight - r.bottom;
      if (spaceBelow < mh + 8 && r.top > spaceBelow) {
        menu.style.top = Math.max(8, r.top - mh - 6) + "px";
      } else {
        menu.style.top = r.bottom + 6 + "px";
      }
    }

    function open() {
      if (select.disabled) return;
      buildOptions();
      menu.hidden = false;
      wrap.classList.add("is-open");
      btn.setAttribute("aria-expanded", "true");
      position();
      var list = opts();
      var sel = list.findIndex(function (o) {
        return o.classList.contains("is-selected");
      });
      setFocus(list, sel < 0 ? 0 : sel);
      document.addEventListener("click", onDoc, true);
      document.addEventListener("keydown", onKey);
      window.addEventListener("resize", position);
      window.addEventListener("scroll", position, true);
    }
    function close() {
      menu.hidden = true;
      wrap.classList.remove("is-open");
      btn.setAttribute("aria-expanded", "false");
      document.removeEventListener("click", onDoc, true);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", position);
      window.removeEventListener("scroll", position, true);
    }
    function choose(i) {
      var opt = select.options[i];
      if (!opt || opt.disabled) return;
      if (select.selectedIndex !== i) {
        select.selectedIndex = i;
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }
      syncLabel();
      close();
      btn.focus();
    }
    function onDoc(e) {
      if (!wrap.contains(e.target) && !menu.contains(e.target)) close();
    }
    function move(dir) {
      var list = opts();
      var cur = list.findIndex(function (o) {
        return o.classList.contains("is-focus");
      });
      var n = cur;
      for (var step = 0; step < list.length; step++) {
        n = (n + dir + list.length) % list.length;
        if (!list[n].classList.contains("is-disabled")) break;
      }
      setFocus(list, n);
    }
    function onKey(e) {
      if (e.key === "Escape") {
        close();
        btn.focus();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        move(1);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        move(-1);
      } else if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        var f = menu.querySelector(".jcc-cselect-opt.is-focus");
        if (f) choose(Number(f.dataset.index));
      }
    }

    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      wrap.classList.contains("is-open") ? close() : open();
    });
    menu.addEventListener("click", function (e) {
      var li = e.target.closest(".jcc-cselect-opt");
      if (li && !li.classList.contains("is-disabled")) {
        choose(Number(li.dataset.index));
      }
    });
    select.addEventListener("change", syncLabel);

    syncLabel();
  }

  function init(root) {
    (root || document)
      .querySelectorAll("select[data-cselect]:not([data-cselect-ready])")
      .forEach(enhance);
  }

  function refresh(root) {
    (root || document)
      .querySelectorAll("select[data-cselect]")
      .forEach(function (s) {
        if (typeof s._cselectSync === "function") s._cselectSync();
      });
  }

  window.JccCustomSelect = { init: init, enhance: enhance, refresh: refresh };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      init(document);
    });
  } else {
    init(document);
  }
})();
