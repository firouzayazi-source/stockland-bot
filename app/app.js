(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const form = $("searchForm");
  const input = $("symbolInput");
  const statusEl = $("status");
  const resultEl = $("result");
  const installBtn = $("installBtn");

  let deferredPrompt = null;

  function setStatus(message, type = "") {
    statusEl.textContent = message || "";
    statusEl.className = `status ${type}`.trim();
  }

  function setResult(data) {
    if (data == null || data === "") {
      resultEl.classList.add("empty");
      resultEl.textContent = "هنوز داده‌ای دریافت نشده.";
      return;
    }
    resultEl.classList.remove("empty");
    resultEl.textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2);
  }

  async function fetchSymbol(symbol) {
    // مسیر API را در صورت نیاز با بک‌اند واقعی خودتان تنظیم کنید.
    // مثال: /api/symbol?query=
    const url = `/api/symbol?query=${encodeURIComponent(symbol)}`;
    const res = await fetch(url, { method: "GET", headers: { "Accept": "application/json" } });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("application/json")) return res.json();
    return res.text();
  }

  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const symbol = input.value.trim();
    if (!symbol) {
      setStatus("لطفاً نماد را وارد کنید.", "warn");
      return;
    }

    setStatus("در حال دریافت اطلاعات...", "");
    setResult("");

    const submitBtn = form.querySelector("button[type='submit']");
    submitBtn.disabled = true;

    try {
      const data = await fetchSymbol(symbol);
      setResult(data);
      setStatus("اطلاعات با موفقیت دریافت شد.", "ok");
      localStorage.setItem("lastSymbol", symbol);
    } catch (err) {
      console.error(err);
      setStatus("خطا در دریافت اطلاعات. اتصال یا API را بررسی کنید.", "err");
      setResult("دریافت داده انجام نشد.");
    } finally {
      submitBtn.disabled = false;
    }
  });

  // Restore last input
  const last = localStorage.getItem("lastSymbol");
  if (last) input.value = last;

  // PWA install prompt
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;
    installBtn.hidden = false;
  });

  installBtn?.addEventListener("click", async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    deferredPrompt = null;
    installBtn.hidden = true;
  });

  // SW registration
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("./sw.js").catch(console.error);
    });
  }
})();