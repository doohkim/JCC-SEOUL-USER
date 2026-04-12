/**
 * 라이트 / 다크 테마 전환. localStorage 키: jcc-theme ("light" | "dark")
 */
(function () {
  function apply(theme) {
    var t = theme === "light" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", t);
    try {
      localStorage.setItem("jcc-theme", t);
    } catch (e) {}

    var btn = document.getElementById("jccThemeToggle");
    if (!btn) return;

    var isDark = t === "dark";
    btn.setAttribute("aria-pressed", isDark ? "true" : "false");
    btn.setAttribute("aria-label", isDark ? "밝은 모드로 전환" : "어두운 모드로 전환");
    btn.title = isDark ? "밝은 모드" : "어두운 모드";

    var sun = btn.querySelector(".jcc-theme-icon--sun");
    var sunDark = btn.querySelector(".jcc-theme-icon--sun-dark");
    if (sun) sun.hidden = !isDark;
    if (sunDark) sunDark.hidden = isDark;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var btn = document.getElementById("jccThemeToggle");
    if (!btn) return;

    btn.addEventListener("click", function () {
      var cur = document.documentElement.getAttribute("data-theme") || "dark";
      apply(cur === "dark" ? "light" : "dark");
    });

    apply(document.documentElement.getAttribute("data-theme") || "dark");
  });
})();
