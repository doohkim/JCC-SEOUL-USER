/**
 * 한국 휴대폰 번호 입력·표시 포맷 (010-1234-5678)
 */
(function (global) {
  "use strict";

  const MOBILE_RE = /^01[016789]\d{7,8}$/;

  function digitsOnly(raw) {
    let digits = String(raw ?? "").replace(/\D/g, "");
    if (digits.startsWith("82") && digits.length >= 10) {
      const body = digits.slice(2);
      digits = body.startsWith("0") ? body : "0" + body;
    }
    return digits.slice(0, 11);
  }

  function formatMobilePhone(raw) {
    const digits = digitsOnly(raw);
    if (!digits) return "";
    if (digits.length <= 3) return digits;
    if (digits.length <= 7) {
      return `${digits.slice(0, 3)}-${digits.slice(3)}`;
    }
    if (digits.length <= 10) {
      return `${digits.slice(0, 3)}-${digits.slice(3, 6)}-${digits.slice(6)}`;
    }
    return `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7, 11)}`;
  }

  function formatDisplay(raw) {
    const trimmed = String(raw ?? "").trim();
    if (!trimmed || trimmed === "-") return "-";
    const digits = digitsOnly(trimmed);
    if (MOBILE_RE.test(digits)) return formatMobilePhone(digits);
    return trimmed;
  }

  function normalizeForSubmit(raw) {
    const trimmed = String(raw ?? "").trim();
    if (!trimmed) return "";
    const digits = digitsOnly(trimmed);
    if (MOBILE_RE.test(digits)) return formatMobilePhone(digits);
    return trimmed;
  }

  function bindInput(input) {
    if (!input || input.dataset.phoneFormatBound) return;
    input.dataset.phoneFormatBound = "1";
    input.setAttribute("inputmode", "numeric");
    input.setAttribute("autocomplete", "tel");
    input.setAttribute("placeholder", "010-1234-5678");
    input.addEventListener("input", () => {
      const formatted = formatMobilePhone(input.value);
      if (input.value !== formatted) input.value = formatted;
    });
  }

  global.JccPhoneFormat = {
    digitsOnly,
    formatMobilePhone,
    formatDisplay,
    normalizeForSubmit,
    bindInput,
  };
})(typeof window !== "undefined" ? window : globalThis);
