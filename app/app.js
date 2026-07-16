/* استوک‌لند PWA — فاز ۱ (محتوا) */
(function () {
  'use strict';

  var tg = window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData !== undefined
    ? window.Telegram.WebApp : null;
  var inTelegram = !!(tg && (tg.initData || tg.platform !== 'unknown'));

  if (inTelegram) {
    document.documentElement.classList.add('in-telegram');
    try { tg.ready(); tg.expand(); } catch (e) {}
  }

  var app = new Framework7({
    el: '#app',
    name: 'استوک‌لند',
    theme: 'ios',
    darkMode: 'auto',
    popup: { closeByBackdropClick: true }
  });

  /* ── ابزار ─────────────────────────────────────────────────────────── */
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function nl2br(s) { return esc(s).replace(/\r?\n/g, '<br>'); }

  function skeletons() {
    var one = '<div class="sl-skel"><div class="b w60"></div><div class="b w90"></div><div class="b w40"></div></div>';
    return one + one + one;
  }

  var EMPTY = {
    tutorial: ['📚', 'هنوز آموزشی منتشر نشده', 'به‌زودی آموزش‌های کاربردی این‌جا قرار می‌گیرد.'],
    news:     ['📰', 'هنوز خبری منتشر نشده', 'اخبار و اطلاعیه‌های استوک‌لند این‌جا نمایش داده می‌شود.'],
    feature:  ['✨', 'به‌زودی…', 'معرفی امکانات ربات این‌جا قرار می‌گیرد.']
  };

  /* ── بارگذاری محتوا ────────────────────────────────────────────────── */
  var loaded = {};

  function loadKind(kind) {
    if (loaded[kind]) return;
    loaded[kind] = true;
    var box = document.querySelector('#tab-' + kind + ' .sl-list');
    if (!box) return;
    box.innerHTML = skeletons();

    fetch('/api/v1/content?kind=' + encodeURIComponent(kind))
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (data) {
        var items = (data && data.items) || [];
        if (!items.length) {
          var e = EMPTY[kind] || EMPTY.news;
          box.innerHTML = '<div class="sl-empty"><span class="sl-emoji">' + e[0] + '</span>' +
            '<b>' + e[1] + '</b><br><span>' + e[2] + '</span></div>';
          return;
        }
        box.innerHTML = items.map(function (it) {
          var img = it.image_url
            ? '<img class="sl-cover" loading="lazy" src="' + esc(it.image_url) + '" alt="">'
            : '';
          return '<div class="sl-card" data-id="' + it.id + '">' + img +
            '<div class="sl-card-content">' +
              '<div class="sl-card-title">' + esc(it.title) + '</div>' +
              (it.excerpt ? '<div class="sl-card-excerpt">' + esc(it.excerpt) + '</div>' : '') +
              '<div class="sl-card-date">' + esc(it.created_at) + '</div>' +
            '</div></div>';
        }).join('');
      })
      .catch(function () {
        loaded[kind] = false; // اجازه‌ی تلاش مجدد
        box.innerHTML = '<div class="sl-empty"><span class="sl-emoji">📡</span>' +
          '<b>خطا در دریافت اطلاعات</b><br><span>اتصال اینترنت را بررسی و دوباره تلاش کنید.</span><br><br>' +
          '<button class="sl-install-btn" onclick="window.SLRetry(\'' + kind + '\')">تلاش مجدد</button></div>';
      });
  }
  window.SLRetry = function (kind) { loaded[kind] = false; loadKind(kind); };

  /* ── جزئیات پست (پاپ‌آپ) ───────────────────────────────────────────── */
  function openPost(id) {
    var titleEl = document.getElementById('post-title');
    var bodyEl  = document.getElementById('post-body');
    titleEl.textContent = '…';
    bodyEl.innerHTML = skeletons();
    app.popup.open('#post-popup');

    fetch('/api/v1/content/' + id)
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (data) {
        var it = data.item || {};
        titleEl.textContent = it.title || '';
        bodyEl.innerHTML =
          (it.image_url ? '<img class="sl-cover" src="' + esc(it.image_url) + '" alt="">' : '') +
          '<div class="sl-post-title">' + esc(it.title) + '</div>' +
          '<div class="sl-post-date">' + esc(it.created_at) + '</div>' +
          '<div class="sl-post-text">' + nl2br(it.body) + '</div>';
      })
      .catch(function () {
        bodyEl.innerHTML = '<div class="sl-empty"><span class="sl-emoji">📡</span><b>خطا در دریافت پست</b></div>';
      });
  }

  document.addEventListener('click', function (ev) {
    var card = ev.target.closest('.sl-card');
    if (card && card.dataset.id) openPost(card.dataset.id);
  });

  /* ── لود تب‌ها ─────────────────────────────────────────────────────── */
  app.on('tabShow', function (tabEl) {
    var kind = tabEl && tabEl.getAttribute && tabEl.getAttribute('data-kind');
    if (kind) loadKind(kind);
  });
  loadKind('tutorial'); // تب پیش‌فرض

  /* ── Service Worker ────────────────────────────────────────────────── */
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('sw.js').catch(function () {});
    });
  }

  /* ── راهنمای نصب (فقط خارج از تلگرام و خارج از حالت نصب‌شده) ───────── */
  var standalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  var dismissed = false;
  try { dismissed = sessionStorage.getItem('sl-hint-off') === '1'; } catch (e) {}

  if (!inTelegram && !standalone && !dismissed) {
    var hint = document.getElementById('install-hint');
    var btn  = document.getElementById('install-btn');
    var txt  = document.getElementById('install-hint-text');
    var deferredPrompt = null;

    window.addEventListener('beforeinstallprompt', function (e) {
      e.preventDefault();
      deferredPrompt = e;
      btn.style.display = '';
      txt.textContent = 'با یک لمس، استوک‌لند را روی گوشی نصب کنید';
    });
    btn.addEventListener('click', function () {
      if (!deferredPrompt) return;
      deferredPrompt.prompt();
      deferredPrompt = null;
      hint.style.display = 'none';
    });

    var isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
    if (isIOS) txt.innerHTML = 'در سافاری: دکمه <b>Share</b> → <b>Add to Home Screen</b>';
    hint.style.display = '';

    document.getElementById('install-close').addEventListener('click', function () {
      hint.style.display = 'none';
      try { sessionStorage.setItem('sl-hint-off', '1'); } catch (e) {}
    });
  }
})();
