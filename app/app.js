(function(){
'use strict';
var tg=window.Telegram&&window.Telegram.WebApp||null;
var inTG=!!(tg&&tg.initData);
if(inTG){document.documentElement.classList.add('in-telegram');try{tg.ready();tg.expand()}catch(e){}}
var initData=(tg&&tg.initData)||'',tgUser=(tg&&tg.initDataUnsafe&&tg.initDataUnsafe.user)||null;
var app=new Framework7({el:'#app',name:'استوک‌لند',theme:'ios',darkMode:'auto',popup:{closeByBackdropClick:true}});
window._slApp=app;window._slApi=function(){return api.apply(null,arguments)};window._slEsc=function(){return esc.apply(null,arguments)};window._slFmt=function(){return fmt.apply(null,arguments)};window._slInitData=initData;window._slTg=tg;

/* هماهنگی تم روشن/تاریک با خود تلگرام — نه فقط با تنظیم سیستم‌عامل (این دو می‌تونن فرق کنن،
   مثلاً تلگرام تاریک باشه ولی گوشی روشن). tg.colorScheme همیشه اولویت داره وقتی داخل تلگراییم. */
function _slApplyTheme(){
  var isDark=(inTG&&tg.colorScheme)?(tg.colorScheme==='dark'):
    !!(window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches);
  try{app.setDarkMode(isDark)}catch(e){document.documentElement.classList.toggle('dark',isDark)}
}
_slApplyTheme();
if(inTG&&tg.onEvent){try{tg.onEvent('themeChanged',_slApplyTheme)}catch(e){}}

/* داخل مینی‌اپ تلگرام، navigation طبیعی a[target=_blank] قابل‌اعتماد نیست —
   همهٔ این لینک‌ها (خبر، دانلود، …) رو از طریق پل جاوااسکریپت تلگرام باز می‌کنیم.
   ⚠️ بیرون از تلگرام هم (یعنی وقتی اپ به‌صورت PWA نصب‌شده روی صفحهٔ اصلی گوشی با
   display:standalone باز می‌شه، نه در مرورگر معمولی) a[target=_blank] معمولاً کار
   نمی‌کنه — خیلی از مرورگرهای موبایل (خصوصاً iOS Safari) در حالت standalone اصلاً
   مفهوم «تب جدید» ندارن، پس کلیک روی لینک ساکت هیچ اتفاقی نمی‌افته (این دقیقاً همون
   باگ گزارش‌شده بود: کلیک روی خبر در PWA نصب‌شده چیزی باز نمی‌کرد). راه‌حل: همین
   interceptor بیرون از تلگرام هم فعاله؛ اول window.open رو امتحان می‌کنه، و اگه
   null برگردوند (یعنی مرورگر/PWA پشتیبانی نکرد یا پاپ‌آپ بلاک شد)، به ناوبری همون
   تب فعلی (location.href) برمی‌گرده — تضمین می‌کنه کاربر حتماً مقاله رو می‌بینه. */
document.addEventListener('click',function(ev){
  var a=ev.target.closest('a[target="_blank"]');
  if(!a)return;
  var href=a.getAttribute('href');
  if(!href||href==='#')return;
  ev.preventDefault();
  if(inTG){
    try{
      if(/^https:\/\/t\.me\//i.test(href)&&tg.openTelegramLink){tg.openTelegramLink(href)}
      else if(tg.openLink){tg.openLink(href,{try_instant_view:false})}
      else{window.open(href,'_blank')}
    }catch(e){window.open(href,'_blank')}
    return;
  }
  var w=null;
  try{w=window.open(href,'_blank')}catch(e){w=null}
  if(!w){try{window.location.href=href}catch(e2){}}
},true);

function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function nl2br(s){return esc(s).replace(/\r?\n/g,'<br>')}
/* قالب‌بندی سبک مقاله: **بولد**، خط‌های شروع‌شده با «- » به‌صورت بولت، لینک خودکار، شکست خط */
function formatBody(s){
  var t=esc(s);
  t=t.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>');
  t=t.replace(/(^|\n)-\s+(.*)/g,'$1• $2');
  t=t.replace(/(https?:\/\/[^\s<]+)/g,'<a href="$1" target="_blank" rel="noopener">$1</a>');
  return t.replace(/\r?\n/g,'<br>');
}
function fmt(n){return Number(n).toLocaleString('fa-IR')}
function starsHtml(avg,count,size){
  if(!count)return '';
  var full=Math.round(avg||0);
  var stars='';for(var i=1;i<=5;i++)stars+=(i<=full?'★':'☆');
  return '<span class="sl-stars'+(size==='sm'?' sl-stars-sm':'')+'"><span class="sl-stars-ico">'+stars+'</span> '+
    '<b>'+(avg||0).toFixed(1)+'</b> <small>('+fmt(count)+')</small></span>';
}
/* عکس واقعی محصول اگه ادمین آپلود کرده باشه، وگرنه همون آیکون ایموجی پیش‌فرض دسته‌بندی */
function prodImgHtml(p){
  return p.image_url?'<img src="'+esc(p.image_url)+'" alt="" loading="lazy">':(p._e||'📦');
}
function skel(n){var o='';for(var i=0;i<(n||3);i++)o+='<div class="sl-skel"><div class="b w60"></div><div class="b w90"></div><div class="b w40"></div></div>';return o}
function api(p,a){var h={'Accept':'application/json'};if(a&&initData)h['X-Telegram-Init-Data']=initData;return fetch('/api/v1'+p,{headers:h}).then(function(r){if(!r.ok)throw r;return r.json()})}
function err(m){return '<div class="sl-empty"><span class="sl-empty-e">📡</span>'+esc(m||'خطا')+'</div>'}

var botUser='stock_land_ir';
api('/bot-info').then(function(d){if(d&&d.username)botUser=d.username}).catch(function(){});

/* ─── ورود وب‌سایت (خارج از مینی‌اپ) — دیپ‌لینک به اپ واقعی تلگرام + تأیید داخل ربات ───
   داخل مینی‌اپ initData همیشه معتبره؛ رو وب‌سایت خالص، loggedIn بعد از تأیید در ربات
   یا کوکی سشن قبلی true می‌شه. همهٔ fetchهای app.js همین الان هم same-origin هستن،
   پس کوکی بدون هیچ تغییری در آپلودها/API خودکار می‌ره.
   عمداً از Telegram Login Widget استفاده نمی‌کنیم — اون یه پاپ‌آپ/صفحهٔ oauth.telegram.org
   باز می‌کنه که برای خیلی از کاربرها (به‌خصوص ایران) قابل‌اعتماد/در دسترس نیست و به‌جای
   ورود واقعی فقط صفحهٔ خالی/گیر می‌ده. این مسیر مستقیم اپ تلگرام رو با t.me باز می‌کنه —
   همون چیزی که همه‌جای این پروژه برای «باز کردن ربات» استفاده می‌شه و واقعاً کار می‌کنه. */
var loggedIn=inTG;
if(!inTG){
  fetch('/api/v1/auth/whoami').then(function(r){return r.ok?r.json():null}).then(function(d){
    if(d&&d.ok){
      loggedIn=true;tgUser={first_name:d.full_name||'کاربر',username:''};
      if(_m){_m=0;loadMe()}
    }
  }).catch(function(){});
}
var _loginPoll=null;
function startWebLogin(containerId){
  var box=document.getElementById(containerId);
  if(!box)return;
  box.innerHTML='<button class="sl-login-btn" id="tg-login-start-btn" style="border:none;font-family:inherit;cursor:pointer;font-size:14px">🤖 ورود با ربات تلگرام</button>';
  var btn=document.getElementById('tg-login-start-btn');
  if(!btn)return;
  btn.addEventListener('click',function(){
    if(_loginPoll){clearInterval(_loginPoll);_loginPoll=null}
    box.innerHTML='<div class="sl-checkout-note">در حال اتصال…</div>';
    fetch('/api/v1/auth/start-login',{method:'POST'}).then(function(r){return r.json()}).then(function(d){
      if(!d||!d.ok){box.innerHTML='<div class="sl-checkout-note">خطا — دوباره تلاش کنید</div>';return}
      window.open(d.deep_link,'_blank');
      box.innerHTML='<div class="sl-checkout-note">⏳ منتظر تأیید در تلگرام هستیم…<br>'+
        '۱. اگه ربات باز نشد <a href="'+esc(d.deep_link)+'" target="_blank">اینجا رو بزنید</a><br>'+
        '۲. تو ربات پیام بفرستید یا فقط وارد چت بشید<br>'+
        '۳. برگردید همین صفحه — خودکار وارد می‌شید</div>';
      var tries=0;
      _loginPoll=setInterval(function(){
        tries++;
        if(tries>150){clearInterval(_loginPoll);_loginPoll=null;
          box.innerHTML='<div class="sl-checkout-note">زمان تمام شد — دوباره تلاش کنید</div>';return}
        fetch('/api/v1/auth/poll-login?token='+encodeURIComponent(d.token)).then(function(r){return r.json()}).then(function(pd){
          if(pd&&pd.status==='confirmed'){
            clearInterval(_loginPoll);_loginPoll=null;
            loggedIn=true;tgUser={first_name:pd.full_name||'کاربر',username:''};
            _m=0;loadMe();
          }else if(pd&&pd.status==='expired'){
            clearInterval(_loginPoll);_loginPoll=null;
            box.innerHTML='<div class="sl-checkout-note">لینک منقضی شد — دوباره تلاش کنید</div>';
          }
        }).catch(function(){});
      },2000);
    }).catch(function(){box.innerHTML='<div class="sl-checkout-note">خطای شبکه</div>'});
  });
}

/* ── دسته‌بندی دایره‌ای ── */
var cats=[],prods=[];
// استاندارد ترتیب: همه ← اپل آیدی ← بقیهٔ دسته‌ها به همون ترتیب قبلی
// (دسته‌های جدید هم چون این تابع فقط "اپل آیدی" رو جدا می‌کنه، خودکار همین قانون رو می‌گیرن)
function orderCats(list){
  var apple=null,rest=[];
  list.forEach(function(c){
    var n=(c.name||'')+' '+(c.slug||'');
    if(!apple&&/اپل\s*آیدی|apple\s*id/i.test(n))apple=c;else rest.push(c);
  });
  return apple?[apple].concat(rest):rest;
}
function renderCircles(el,withAll){
  var items=withAll?[{id:0,name:'همه',emoji:'🏪',slug:''}].concat(orderCats(cats)):orderCats(cats);
  el.innerHTML=items.map(function(c,i){
    return '<div class="sl-cat-c'+(withAll&&i===0?' on':'')+'" data-slug="'+esc(c.slug||c.name)+'" data-name="'+esc(c.name)+'">'+
      '<div class="sl-cat-c-icon">'+esc(c.emoji||'📦')+'</div>'+
      '<div class="sl-cat-c-name">'+esc(c.name)+'</div></div>';
  }).join('');
}

/* ═══ خانه ═══ */
var _h=0;
function loadHome(){
  if(_h)return;_h=1;
  var tr=document.getElementById('ticker-row'),nr=document.getElementById('news-row'),
      dp=document.getElementById('daily-post');

  // دسته‌بندی‌ها — فقط برای فروشگاه
  api('/categories').then(function(d){
    cats=(d&&d.categories)||[];prods=[];
    cats.forEach(function(c){
      (c.products||[]).forEach(function(p){p._c=c.name;p._e=c.emoji;prods.push(p)});
      (c.subcategories||[]).forEach(function(s){
        (s.products||[]).forEach(function(p){p._c=c.name;p._e=c.emoji;p._s=s.name;prods.push(p)});
      });
    });
    var sc=document.getElementById('shop-cats');
    if(sc){renderCircles(sc,true);}
    document.getElementById('shop-count').textContent=prods.length+' محصول فعال';
    // ویژه امروز — فلش‌سیل یا ۴ محصول اول
    loadFeatured(prods);
  }).catch(function(){});

  // تیکر
  tr.innerHTML=skel(1);
  api('/products?limit=20').then(function(d){
    var it=(d&&d.products)||[];
    if(!it.length){tr.innerHTML='<div class="sl-empty"><span class="sl-empty-e">📦</span>محصولی ثبت نشده</div>';return}
    var n=new Date();document.getElementById('ticker-time').textContent=('0'+n.getHours()).slice(-2)+':'+('0'+n.getMinutes()).slice(-2);
    tr.innerHTML=it.map(function(p){
      return '<div class="sl-tick" data-pid="'+p.id+'"><div class="sl-tick-n">'+esc(p.title)+'</div>'+
        '<div class="sl-tick-p">'+fmt(p.effective_price)+' <small>تومان</small></div>'+
        (p.flash_active?'<div class="sl-flash">⚡️ فروش فوری</div>':'')+'</div>';
    }).join('');
  }).catch(function(){_h=0;tr.innerHTML=err('خطا')+'<button class="sl-retry" onclick="_h=0;loadHome()">تلاش مجدد</button>'});

  // پست روزانه
  api('/content/daily').then(function(d){
    if(!d||!d.item){dp.innerHTML='';return}
    var it=d.item;
    dp.innerHTML='<div class="sl-sec"><b>📋 لیست روزانه</b></div>'+
      '<div class="sl-post" data-cid="'+it.id+'" style="margin:0 20px">'+
      (it.image_url?'<div class="sl-post-cv" style="background:#0B1B4A"><img src="'+esc(it.image_url)+'" alt=""></div>':'')+
      '<div class="sl-post-bd"><div class="sl-post-t">'+esc(it.title)+'</div>'+
      '<div class="sl-post-x">'+esc((it.body||'').substring(0,160))+'</div>'+
      '<div class="sl-post-m">'+esc(it.created_at)+'</div></div></div>';
  }).catch(function(){dp.innerHTML=''});

  // اخبار تکنولوژی — از فید RSS زنده (نه محتوای داخلی)
  nr.innerHTML=skel(1);
  // آخرین آموزش
  loadLearnCard();

  var colors=['linear-gradient(120deg,#123,#0A63FF)','linear-gradient(120deg,#1B2B1B,#22C55E)',
    'linear-gradient(120deg,#2B1B2B,#A855F7)','linear-gradient(120deg,#2B1B1B,#EF4444)',
    'linear-gradient(120deg,#1B2B2B,#06B6D4)','linear-gradient(120deg,#2B2B1B,#F59E0B)'];
  api('/news/feed').then(function(d){
    var it=((d&&d.items)||[]).slice(0,6);
    var ns=document.getElementById('news-sec');
    if(!it.length){nr.innerHTML='';if(ns)ns.style.display='none';return}
    if(ns)ns.style.display='';
    nr.innerHTML=it.map(function(p,i){
      return '<a class="sl-mini" href="'+esc(p.link)+'" target="_blank" rel="noopener" style="text-decoration:none;color:inherit">'+
        '<div class="sl-mini-cv" style="background:'+colors[i%colors.length]+'">'+
        (p.image_url?'<img src="'+esc(p.image_url)+'" alt="">':'📰')+'</div>'+
        '<div class="sl-mini-b"><div class="sl-mini-t">'+esc(p.title)+'</div><div class="sl-mini-m">'+esc(p.pub_date)+'</div></div></a>';
    }).join('');
  }).catch(function(){nr.innerHTML=''});
}
window.loadHome=loadHome;

function loadFeatured(allProds){
  var fr=document.getElementById('featured-row');if(!fr)return;
  var featured=(allProds||[]).filter(function(p){return p.flash_active});
  if(!featured.length)featured=(allProds||[]).slice(0,4);
  if(!featured.length){fr.style.display='none';fr.previousElementSibling&&(fr.previousElementSibling.style.display='none');return}
  fr.innerHTML=featured.slice(0,6).map(function(p){
    var f=p.flash_active,e=p.effective_price,b=p.price;
    return '<div class="sl-feat" data-pid="'+p.id+'">'+
      '<div class="sl-feat-img">'+prodImgHtml(p)+
        (f?'<span class="sl-feat-badge">⚡️ فروش فوری</span>':'')+
      '</div>'+
      '<div class="sl-feat-body">'+
        '<div class="sl-feat-name">'+esc(p.title)+'</div>'+
        (f?'<div class="sl-feat-old">'+fmt(b)+' تومان</div>':'')+
        '<div class="sl-feat-price">'+fmt(e)+' <small>تومان</small></div>'+
        '<div class="sl-feat-btn">مشاهده و خرید</div>'+
      '</div></div>';
  }).join('');
}
window.loadFeatured=loadFeatured;

function loadLearnCard(){
  var lc=document.getElementById('learn-card');
  var ls=document.getElementById('learn-sec');
  if(!lc)return;
  api('/tutorials?limit=1&sort=newest').then(function(d){
    var it=(d&&d.items&&d.items[0]);
    if(!it){lc.style.display='none';if(ls)ls.style.display='none';return}
    lc.innerHTML='<div class="sl-learn-card" data-tid="'+it.id+'">'+
      '<div class="sl-learn-img">'+(it.cover_image?'<img src="'+esc(it.cover_image)+'" alt="">':'📚')+'</div>'+
      '<div class="sl-learn-body">'+
        '<div class="sl-learn-tag">'+(it.featured?'⭐️ ویژه':'📚 آموزش')+'</div>'+
        '<div class="sl-learn-title">'+esc(it.title)+'</div>'+
        '<div class="sl-learn-meta"><span>'+esc(it.publish_date||'')+'</span></div>'+
      '</div></div>';
  }).catch(function(){lc.style.display='none';if(ls)ls.style.display='none'});
}
window.loadLearnCard=loadLearnCard;

loadHome();
if(loggedIn)_checkMeBadge();

/* ═══ فروشگاه ═══ */
var _s=0;
function loadShop(){if(_s)return;_s=1;
  if(!prods.length){
    var pl=document.getElementById('prod-list');pl.innerHTML=skel(3);
    api('/categories').then(function(d){
      cats=(d&&d.categories)||[];prods=[];
      cats.forEach(function(c){
        (c.products||[]).forEach(function(p){p._c=c.name;p._e=c.emoji;prods.push(p)});
        (c.subcategories||[]).forEach(function(s){
          (s.products||[]).forEach(function(p){p._c=c.name;p._e=c.emoji;p._s=s.name;prods.push(p)});
        });
      });
      renderCircles(document.getElementById('shop-cats'),true);
      document.getElementById('shop-count').textContent=prods.length+' محصول فعال';
      renderP('');
    }).catch(function(){_s=0;pl.innerHTML=err('خطا')+'<button class="sl-retry" onclick="_s=0;loadShop()">تلاش مجدد</button>'});
  }else{renderP('')}
}
window.loadShop=loadShop;

function renderP(name){
  var pl=document.getElementById('prod-list');
  var it=name?prods.filter(function(p){return p._c===name||p._s===name}):prods;
  if(!it.length){pl.innerHTML='<div class="sl-empty"><span class="sl-empty-e">📦</span>محصولی نیست</div>';return}
  pl.innerHTML=it.map(function(p){
    var f=p.flash_active;
    return '<div class="sl-prod" data-pid="'+p.id+'"><div class="sl-pic">'+prodImgHtml(p)+'</div>'+
      '<div class="sl-pinfo"><div class="sl-pt">'+esc(p.title)+'</div>'+
      '<div class="sl-pg">'+esc(p._c||'')+(p._s?' · '+esc(p._s):'')+(p.rating_count?' · '+starsHtml(p.rating_avg,p.rating_count,'sm'):'')+'</div>'+
      '<div class="sl-pprice-row">'+(f?'<span class="sl-old">'+fmt(p.price)+'</span>':'')+
      '<span class="sl-price">'+fmt(p.effective_price)+' <small>تومان</small></span></div>'+
      (f?'<div class="sl-flash">⚡️ فروش فوری</div>':'')+
      '<span class="sl-buy">🛒 مشاهده و خرید</span></div></div>';
  }).join('');
}

// کلیک دایره فروشگاه
document.getElementById('shop-cats').addEventListener('click',function(e){
  var c=e.target.closest('.sl-cat-c');if(!c)return;
  document.querySelectorAll('#shop-cats .sl-cat-c').forEach(function(x){x.classList.remove('on')});
  c.classList.add('on');
  var n=c.dataset.name;renderP(n==='همه'?'':n);
});

/* ═══ اشتراک‌گذاری محصول ═══ */
function shareProduct(pid,title){
  var url='https://t.me/'+botUser+'?start=buy_'+pid;
  if(inTG&&tg.openTelegramLink){
    tg.openTelegramLink('https://t.me/share/url?url='+encodeURIComponent(url)+'&text='+encodeURIComponent(title||''));
  }else if(navigator.share){
    navigator.share({title:title||'',url:url}).catch(function(){});
  }else if(navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(url).then(function(){window._slApp.dialog.alert('لینک محصول کپی شد','اشتراک‌گذاری')});
  }
}
window.shareProduct=shareProduct;

/* ═══ پاپ‌آپ محصول ═══ */
function openP(pid){
  var b=document.getElementById('pp-body');
  b.innerHTML=skel(2);app.popup.open('#prod-popup');
  api('/products/'+pid,true).then(function(d){
    var p=d.product||{};
    var f=p.flash_active,e=p.effective_price,bs=p.price,hs=p.stock!=null,ok=p.stock>0;
    var priceBlock;
    if(f){
      priceBlock='<div class="sl-pp-flash"><span class="old">'+fmt(bs)+' تومان</span> <span class="tag">⚡️ فروش فوری</span></div>'+
        '<div class="sl-pp-price">'+fmt(e)+' <small>تومان</small></div>';
    }else if(p.show_partner_price){
      // دو قیمت: اصلی (خط‌خورده) + همکاری (برجسته) — دقیقاً همون منطق _show_order_summary در bot.py
      priceBlock='<div class="sl-pp-dualprice">'+
        '<div class="sl-pp-price-orig">قیمت اصلی: <s>'+fmt(bs)+' تومان</s></div>'+
        '<div class="sl-pp-price">'+fmt(p.partner_price)+' <small>تومان</small><span class="sl-pp-partner-badge">🤝 قیمت همکاری</span></div>'+
      '</div>';
    }else{
      priceBlock='<div class="sl-pp-price">'+fmt(e)+' <small>تومان</small></div>';
    }
    b.innerHTML='<div class="sl-pp-hero">'+
      (loggedIn?'<button class="sl-pp-fav'+(p.is_favorite?' on':'')+'" id="sl-fav-'+p.id+'" data-fav="'+(p.is_favorite?1:0)+'">'+(p.is_favorite?'♥':'♡')+'</button>':'')+
      '<button class="sl-pp-share" id="sl-share-'+p.id+'">↗</button>'+
      '<div class="sl-pp-emoji">'+prodImgHtml(p)+'</div>'+
      '<div class="sl-pp-title">'+esc(p.title)+'</div>'+
      priceBlock+
      (p.rating_count?'<div class="sl-pp-rating">'+starsHtml(p.rating_avg,p.rating_count)+'</div>':'')+
      '</div>'+
      (hs?'<div class="sl-pp-stock">'+(ok?'✅ موجود — '+p.stock+' عدد':'❌ ناموجود')+'</div>':'')+
      '<div class="sl-pp-divider"></div>'+
      (p.description?'<div class="sl-pp-desc">'+nl2br(p.description)+'</div>':'')+
      ((p.reviews&&p.reviews.length)?
        '<div class="sl-pp-reviews-title">نظرات خریداران</div>'+
        '<div class="sl-pp-reviews">'+p.reviews.map(function(rv){
          var st='';for(var i=1;i<=5;i++)st+=(i<=rv.rating?'★':'☆');
          return '<div class="sl-review"><div class="sl-review-top"><b>'+esc(rv.name)+'</b><span class="sl-review-st">'+st+'</span></div>'+
            (rv.comment?'<div class="sl-review-txt">'+esc(rv.comment)+'</div>':'')+'</div>';
        }).join('')+'</div>'
        :'')+
      ((p.related&&p.related.length)?
        '<div class="sl-pp-related-title">محصولات مشابه</div>'+
        '<div class="sl-pp-related">'+p.related.map(function(rp){
          return '<div class="sl-rp-card" data-pid="'+rp.id+'"><div class="sl-rp-t">'+esc(rp.title)+'</div>'+
            '<div class="sl-rp-p">'+fmt(rp.effective_price)+' <small>ت</small></div></div>';
        }).join('')+'</div>'
        :'')+
      (loggedIn&&ok!==false?
        '<button class="sl-pp-btn" id="sl-buy-'+p.id+'">🛒 خرید</button>':
        (hs&&!ok?
          (p.notify_on_restock?
            '<button class="sl-pp-btn sl-pp-btn-off" onclick="_notifyStock('+p.id+',\'pp-notify-'+p.id+'\')" id="pp-notify-'+p.id+'">🔔 موجود شد، اطلاع بده</button>':
            '<div class="sl-checkout-note">❌ موجودی این محصول در حال حاضر به پایان رسیده است.</div>'):
          (inTG?
            '<a class="sl-pp-btn" href="https://t.me/'+botUser+'?start=buy_'+p.id+'" target="_blank">🛒 خرید از ربات</a>':
            '<button class="sl-pp-btn" id="sl-login-prompt-'+p.id+'">🔐 ورود با تلگرام برای خرید</button>')));
    setTimeout(function(){
      var bn=document.getElementById('sl-buy-'+p.id);
      if(bn)bn.addEventListener('click',function(){
        app.popup.close('#prod-popup');
        setTimeout(function(){openCheckout(p.id)},350);
      });
      var lp=document.getElementById('sl-login-prompt-'+p.id);
      if(lp)lp.addEventListener('click',function(){
        app.popup.close('#prod-popup');
        setTimeout(function(){var l=document.querySelector('.tab-link[href="#tab-me"]');if(l)l.click()},350);
      });
      var fv=document.getElementById('sl-fav-'+p.id);
      if(fv)fv.addEventListener('click',function(){
        var on=fv.dataset.fav==='1';
        fetch('/api/v1/favorites/'+p.id,{method:on?'DELETE':'POST',headers:{'X-Telegram-Init-Data':initData}})
          .then(function(){
            fv.dataset.fav=on?'0':'1';
            fv.textContent=on?'♡':'♥';
            fv.classList.toggle('on',!on);
            if(window._slTg&&window._slTg.HapticFeedback)try{window._slTg.HapticFeedback.impactOccurred('light')}catch(e){}
          });
      });
      var shr=document.getElementById('sl-share-'+p.id);
      if(shr)shr.addEventListener('click',function(){shareProduct(p.id,p.title)});
      b.querySelectorAll('.sl-rp-card').forEach(function(card){
        card.addEventListener('click',function(){openP(card.dataset.pid)});
      });
    },150);
  }).catch(function(){b.innerHTML=err('خطا');});
}

/* ═══ آموزش — CMS داخلی کامل: جستجو، فیلتر دسته، مرتب‌سازی، Lazy Loading ═══ */
var _tutState={cat:'0',tag:'',q:'',sort:'newest',offset:0,limit:12,loading:false};
var _tutCatsLoaded=false,_tutLoaded=false;

function loadTutCats(){
  if(_tutCatsLoaded)return;_tutCatsLoaded=true;
  var box=document.getElementById('tut-cats');if(!box)return;
  api('/tutorials/categories').then(function(d){
    var cats=(d&&d.categories)||[];
    if(!cats.length){box.style.display='none';return}
    box.innerHTML='<div class="sl-chip on" data-cat="0">همه</div>'+
      cats.map(function(c){return '<div class="sl-chip" data-cat="'+c.id+'">'+esc(c.name)+'</div>'}).join('');
  }).catch(function(){});
}
window.loadTutCats=loadTutCats;

function loadTuts(reset){
  var box=document.getElementById('learn-list');if(!box)return;
  var moreWrap=document.getElementById('tut-more-wrap');
  if(reset){_tutState.offset=0;box.innerHTML=skel(3);if(moreWrap)moreWrap.hidden=true}
  if(_tutState.loading)return;_tutState.loading=true;
  var moreBtn=document.getElementById('tut-more-btn');
  if(moreBtn&&!reset)moreBtn.textContent='در حال بارگذاری…';
  var qs='/tutorials?sort='+_tutState.sort+'&limit='+_tutState.limit+'&offset='+_tutState.offset+
    (_tutState.cat&&_tutState.cat!=='0'?'&category='+_tutState.cat:'')+
    (_tutState.q?'&q='+encodeURIComponent(_tutState.q):'');
  api(qs).then(function(d){
    _tutState.loading=false;
    var items=(d&&d.items)||[];
    if(reset&&!items.length){box.innerHTML='<div class="sl-empty"><span class="sl-empty-e">📚</span>آموزشی یافت نشد</div>';if(moreWrap)moreWrap.hidden=true;return}
    var html=items.map(function(p){
      return '<div class="sl-post" data-tid="'+p.id+'"><div class="sl-post-cv" style="background:linear-gradient(120deg,#101826,#0A63FF)">'+
        '<span class="sl-post-tag">'+(p.featured?'⭐️ ویژه':'📚 آموزش')+'</span>'+
        (p.cover_image?'<img src="'+esc(p.cover_image)+'" alt="">':'')+
        '</div><div class="sl-post-bd"><div class="sl-post-t">'+esc(p.title)+'</div>'+
        '<div class="sl-post-x">'+esc(p.short_desc||'')+'</div>'+
        '<div class="sl-post-m">'+(p.category_name?esc(p.category_name)+' · ':'')+esc(p.publish_date||'')+'</div></div></div>';
    }).join('');
    if(reset)box.innerHTML=html;else box.insertAdjacentHTML('beforeend',html);
    _tutState.offset+=items.length;
    if(moreWrap)moreWrap.hidden=items.length<_tutState.limit;
    if(moreBtn)moreBtn.textContent='نمایش بیشتر';
  }).catch(function(){_tutState.loading=false;if(reset)box.innerHTML=err('خطا')+'<button class="sl-retry" onclick="loadTuts(true)">تلاش مجدد</button>'});
}
window.loadTuts=loadTuts;

document.getElementById('tut-cats').addEventListener('click',function(e){
  var c=e.target.closest('[data-cat]');if(!c)return;
  document.querySelectorAll('#tut-cats [data-cat]').forEach(function(x){x.classList.remove('on')});c.classList.add('on');
  _tutState.cat=c.dataset.cat;loadTuts(true);
});
document.getElementById('tut-sort-seg').addEventListener('click',function(e){
  var b=e.target.closest('button');if(!b)return;
  document.querySelectorAll('#tut-sort-seg button').forEach(function(x){x.classList.remove('on')});b.classList.add('on');
  _tutState.sort=b.dataset.s;loadTuts(true);
});
document.getElementById('tut-more-btn').addEventListener('click',function(){loadTuts(false)});
var _tutSearchTimer=null;
document.getElementById('tut-search-input').addEventListener('input',function(e){
  clearTimeout(_tutSearchTimer);
  var v=e.target.value;
  _tutSearchTimer=setTimeout(function(){_tutState.q=v.trim();loadTuts(true)},350);
});

function videoEmbedHtml(link){
  if(!link)return '';
  var yt=link.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([\w-]+)/);
  if(yt)return '<div class="sl-video-wrap"><iframe src="https://www.youtube.com/embed/'+yt[1]+'" allowfullscreen frameborder="0"></iframe></div>';
  var ap=link.match(/aparat\.com\/v\/([\w-]+)/);
  if(ap)return '<div class="sl-video-wrap"><iframe src="https://www.aparat.com/video/video/embed/videohash/'+ap[1]+'/vt/frame" allowfullscreen frameborder="0"></iframe></div>';
  return '<video controls class="sl-tut-video" src="'+esc(link)+'"></video>';
}

function openTutorial(tid){
  var t=document.getElementById('post-title'),b=document.getElementById('post-body');
  t.textContent='…';b.innerHTML=skel(2);app.popup.open('#post-popup');
  api('/tutorials/'+tid).then(function(d){
    var it=d.item||{};t.textContent=it.title||'';
    var tags=it.tags||[];
    var tagsHtml=tags.length?'<div class="sl-tut-tags">'+tags.map(function(tg){return '<span class="sl-tut-tag">'+esc(tg)+'</span>'}).join('')+'</div>':'';
    var gallery=it.gallery||[];
    var galleryHtml=gallery.length?'<div class="sl-tut-gallery">'+gallery.map(function(g){return '<img src="'+esc(g)+'" alt="">'}).join('')+'</div>':'';
    var videoHtml=it.video_upload?'<video controls class="sl-tut-video" src="'+esc(it.video_upload)+'"></video>':videoEmbedHtml(it.video_link);
    var downloadHtml=it.download_file?'<a class="sl-pp-btn" href="'+esc(it.download_file)+'" target="_blank" style="margin:14px 0 4px;width:100%;box-sizing:border-box">⬇️ '+esc(it.download_label||'دانلود فایل')+'</a>':'';
    b.innerHTML=(it.cover_image?'<img src="'+esc(it.cover_image)+'" alt="">':'')+
      '<div class="sl-postf-title">'+esc(it.title)+'</div>'+
      '<div class="sl-postf-date">'+(it.category_name?esc(it.category_name)+' · ':'')+esc(it.publish_date||'')+' · 👁 '+fmt(it.view_count||0)+'</div>'+
      tagsHtml+
      (it.short_desc?'<div class="sl-postf-text" style="color:var(--mu)">'+esc(it.short_desc)+'</div>':'')+
      videoHtml+
      '<div class="sl-postf-text">'+(it.body||'')+'</div>'+
      galleryHtml+downloadHtml;
  }).catch(function(){b.innerHTML=err('خطا')});
}
window.openTutorial=openTutorial;

/* ═══ اخبار تکنولوژی — فقط فید RSS زندهٔ وبلاگ، بدون هیچ محتوای داخلی، بدون محدودیت تعداد ═══ */
var _nwLoaded=false;
var _newsState={offset:0,limit:20,loading:false};
var _newsColors=['linear-gradient(120deg,#101826,#7C3AED)','linear-gradient(120deg,#0F172A,#0A63FF)',
  'linear-gradient(120deg,#1B2B1B,#22C55E)','linear-gradient(120deg,#2B1B1B,#EF4444)',
  'linear-gradient(120deg,#1B2B2B,#06B6D4)','linear-gradient(120deg,#2B2B1B,#F59E0B)'];
function loadMoreNews(){
  if(_newsState.loading)return;
  _fetchNewsPage(false);
}
function loadNews(reset){
  if(_nwLoaded&&!reset)return;_nwLoaded=true;
  _fetchNewsPage(true);
}
function _fetchNewsPage(reset){
  var box=document.getElementById('news-list');if(!box)return;
  var moreWrap=document.getElementById('news-more-wrap');
  if(reset){_newsState.offset=0;box.innerHTML=skel(3);if(moreWrap)moreWrap.hidden=true}
  if(_newsState.loading)return;_newsState.loading=true;
  var moreBtn=document.getElementById('news-more-btn');
  if(moreBtn&&!reset)moreBtn.textContent='در حال بارگذاری…';
  api('/news/feed?limit='+_newsState.limit+'&offset='+_newsState.offset).then(function(d){
    _newsState.loading=false;
    var it=(d&&d.items)||[];
    if(reset&&!it.length){
      var msg=(d&&d.status==='unset')?'فید اخبار هنوز تنظیم نشده':'هنوز خبری نیست';
      box.innerHTML='<div class="sl-empty"><span class="sl-empty-e">📰</span>'+msg+'</div>';
      if(moreWrap)moreWrap.hidden=true;
      return;
    }
    var startI=_newsState.offset;
    var html=it.map(function(p,i){
      return '<a class="sl-post" href="'+esc(p.link)+'" target="_blank" rel="noopener" style="text-decoration:none;color:inherit">'+
        '<div class="sl-post-cv" style="background:'+_newsColors[(startI+i)%_newsColors.length]+'">'+
        (p.image_url?'<img src="'+esc(p.image_url)+'" alt="">':'')+
        '</div><div class="sl-post-bd"><div class="sl-post-t">'+esc(p.title)+'</div>'+
        '<div class="sl-post-x">'+esc(p.excerpt)+'</div><div class="sl-post-m">'+esc(p.pub_date)+'</div></div></a>';
    }).join('');
    if(reset)box.innerHTML=html;else box.insertAdjacentHTML('beforeend',html);
    _newsState.offset+=it.length;
    if(moreWrap)moreWrap.hidden=!(d&&d.has_more);
    if(moreBtn)moreBtn.textContent='نمایش بیشتر';
  }).catch(function(){_newsState.loading=false;_nwLoaded=false;if(reset)box.innerHTML=err('خطا')+'<button class="sl-retry" onclick="loadNews(true)">تلاش مجدد</button>'});
}
window.loadNews=loadNews;
var _newsMoreBtn=document.getElementById('news-more-btn');
if(_newsMoreBtn)_newsMoreBtn.addEventListener('click',loadMoreNews);
function openC(cid){
  var t=document.getElementById('post-title'),b=document.getElementById('post-body');
  t.textContent='…';b.innerHTML=skel(2);app.popup.open('#post-popup');
  api('/content/'+cid).then(function(d){
    var it=d.item||{};t.textContent=it.title||'';
    b.innerHTML=(it.image_url?'<img src="'+esc(it.image_url)+'" alt="">':'')+
      '<div class="sl-postf-title">'+esc(it.title)+'</div><div class="sl-postf-date">'+esc(it.created_at)+'</div>'+
      '<div class="sl-postf-text">'+formatBody(it.body)+'</div>'+
      (it.link_url?'<a class="sl-pp-btn" href="'+esc(it.link_url)+'" target="_blank" rel="noopener" style="margin:20px 0 4px;width:100%;box-sizing:border-box">🔗 مشاهده در تلگرام / اینستاگرام</a>':'');
  }).catch(function(){b.innerHTML=err('خطا')});
}
window.openC=openC;

/* ═══ حساب ═══ */
var _m=0;
function loadMe(){if(_m)return;_m=1;
  var body=document.getElementById('me-body');
  var foot='<div class="sl-group" style="margin-top:12px"><a class="sl-row" href="https://t.me/'+botUser+'" target="_blank">'+
    '<span class="sl-ric" style="background:#54A9EB">🤖</span><span class="sl-row-grow">باز کردن ربات</span><span class="sl-chev">‹</span></a></div>'+
    '<div class="sl-foot">استوک‌لند · نسخه ۲.۰</div>';
  function row(c,i,l,cmd,x){return '<a class="sl-row" href="https://t.me/'+botUser+'?start='+cmd+'" target="_blank"><span class="sl-ric" style="background:'+c+'">'+i+'</span><span class="sl-row-grow">'+l+'</span>'+(x||'')+'<span class="sl-chev">‹</span></a>'}
  if(!loggedIn){
    // این حالت فقط خارج از مینی‌اپ (وب‌سایت خالص) پیش میاد — داخل تلگرام initData همیشه معتبره
    body.innerHTML='<div class="sl-login"><div class="sl-login-e">🔐</div><div class="sl-login-t">ورود به حساب</div>'+
      '<div class="sl-login-s">برای مشاهده کیف پول، خرید و سفارش‌ها وارد شوید.</div>'+
      '<div id="tg-login-widget" style="margin-top:16px;display:flex;justify-content:center"></div></div>';
    startWebLogin('tg-login-widget');
    return;
  }
  var un=(tgUser&&tgUser.first_name)||'کاربر',usr=(tgUser&&tgUser.username)||'';
  body.innerHTML='<div class="sl-me sl-me-c">'+
    '<label class="sl-ava-wrap" id="me-ava-wrap" for="me-ava-input">'+
      '<div class="sl-ava" id="me-ava">🥉</div>'+
      '<img class="sl-ava-img" id="me-ava-img" style="display:none" alt="">'+
      '<div class="sl-ava-spin" id="me-ava-spin" style="display:none"><div class="sl-spin"></div></div>'+
      '<span class="sl-ava-edit" id="me-ava-edit" title="تغییر عکس پروفایل">📷</span>'+
      '<input type="file" id="me-ava-input" accept="image/*" style="display:none">'+
    '</label>'+
    '<div class="sl-me-n">'+esc(un)+'</div>'+
    '<div class="sl-me-u">'+(usr?'@'+esc(usr)+' · ':'')+'ورود از تلگرام</div>'+
    '</div>'+
    '<div id="me-checkin-card"></div>'+
    '<div class="sl-wallet"><div class="sl-wallet-glow"></div><div class="sl-wallet-l">موجودی کیف پول</div>'+
    '<div class="sl-wallet-b" id="me-bal"><div class="sl-skel" style="margin:0;background:transparent"><div class="b w40" style="height:24px"></div></div></div>'+
    '<div class="sl-wallet-acts"><a class="sl-wallet-a" href="#" id="me-wallet-charge" style="width:100%">＋ شارژ کیف‌پول</a></div></div>'+
    '<div class="sl-group"><a class="sl-row" href="#" id="me-notif-row"><span class="sl-ric" style="background:#7C3AED">🔔</span><span class="sl-row-grow">اعلان‌ها</span><span class="sl-badge" id="me-notif-badge" style="display:none">جدید</span><span class="sl-chev">‹</span></a>'+
    '<a class="sl-row" href="#" id="me-orders-row"><span class="sl-ric" style="background:#0A63FF">📦</span><span class="sl-row-grow">سفارش‌های من</span><span class="sl-chev">‹</span></a>'+
    '<a class="sl-row" href="#" id="me-favs-row"><span class="sl-ric" style="background:#EF4444">♥</span><span class="sl-row-grow">علاقه‌مندی‌ها</span><span class="sl-chev">‹</span></a>'+
    '<a class="sl-row" href="#" id="me-partner-row"><span class="sl-ric" style="background:#F59E0B">🤝</span><span class="sl-row-grow">پنل همکاری</span><span class="sl-badge" id="me-pb" style="display:none">فعال</span><span class="sl-chev">‹</span></a>'+
    '<a class="sl-row" href="#" id="me-support-row"><span class="sl-ric" style="background:#6B7280">💬</span><span class="sl-row-grow">پشتیبانی</span><span class="sl-chev">‹</span></a>'+
    '</div>'+
    (inTG?'':'<div class="sl-group" style="margin-top:12px"><a class="sl-row" href="#" id="me-logout-row"><span class="sl-ric" style="background:#EF4444">🚪</span><span class="sl-row-grow">خروج از حساب</span></a></div>')+
    foot;
  api('/me/wallet',true).then(function(d){var e=document.getElementById('me-bal');if(e)e.innerHTML=fmt(d.balance||0)+' <small>تومان</small>'}).catch(function(){var e=document.getElementById('me-bal');if(e)e.textContent='—'});
  api('/me/partner',true).then(function(d){
    if(d.is_partner){var b=document.getElementById('me-pb');if(b)b.style.display=''}
    if(d.is_partner&&d.tier)setTierAvatar(d.tier.name,d.tier.icon);
  }).catch(function(){});
  renderCheckinCard();
  initAvatarUpload();
  api('/me/profile',true).then(function(d){if(d&&d.avatar_url)setAvatarImg(d.avatar_url)}).catch(function(){});
  var lo_=document.getElementById('me-logout-row');
  if(lo_)lo_.addEventListener('click',function(e){e.preventDefault();
    fetch('/api/v1/auth/logout',{method:'POST'}).then(function(){loggedIn=false;tgUser=null;_m=0;loadMe()});
  });
  var nt_=document.getElementById('me-notif-row');
  if(nt_)nt_.addEventListener('click',function(e){e.preventDefault();openNotifications()});
  api('/me/notifications',true).then(function(d){
    var items=(d&&d.items)||[];
    var b=document.getElementById('me-notif-badge');
    if(b)b.style.display=items.some(function(n){return !n.is_read})?'':'none';
  }).catch(function(){});
  var or_=document.getElementById('me-orders-row');
  if(or_)or_.addEventListener('click',function(e){e.preventDefault();openOrders()});
  var fr_=document.getElementById('me-favs-row');
  if(fr_)fr_.addEventListener('click',function(e){e.preventDefault();openFavorites()});
  var wc_=document.getElementById('me-wallet-charge');
  if(wc_)wc_.addEventListener('click',function(e){e.preventDefault();startCharge()});
  var pr_=document.getElementById('me-partner-row');
  if(pr_)pr_.addEventListener('click',function(e){e.preventDefault();openPartner()});
  var sp_=document.getElementById('me-support-row');
  if(sp_)sp_.addEventListener('click',function(e){e.preventDefault();openSupport()});
}
window.loadMe=loadMe;

/* ─── عکس پروفایل ─── */
var TIER_GRADIENTS={
  'برنز':'linear-gradient(135deg,#C88A4A,#8B5A2B)',
  'نقره‌ای':'linear-gradient(135deg,#D6D9DD,#9AA0A6)',
  'طلایی':'linear-gradient(135deg,#F6D465,#D9A62A)',
  'الماس':'linear-gradient(135deg,#8FE3E8,#3AA7C4)'
};
function setTierAvatar(tierName,tierIcon){
  var ava=document.getElementById('me-ava');
  if(!ava)return;
  ava.textContent=tierIcon||'🥉';
  ava.style.background=TIER_GRADIENTS[tierName]||TIER_GRADIENTS['برنز'];
}
function setAvatarImg(url){
  var img=document.getElementById('me-ava-img'),lt=document.getElementById('me-ava');
  if(!img)return;
  img.onload=function(){img.style.display='block';if(lt)lt.style.display='none'};
  img.onerror=function(){img.style.display='none';if(lt)lt.style.display=''};
  img.src=url;
}
function initAvatarUpload(){
  var input=document.getElementById('me-ava-input');
  if(!input)return;
  // خودِ #me-ava-wrap یک <label for="me-ava-input"> است — دیگه نیازی به باز کردن دستی
  // input.click() از یک هندلر جدا نیست (اون روش روی WKWebView تلگرام آی‌اواس غیرقابل‌اعتماد بود؛
  // label با for، انتخابگر فایل رو به‌صورت بومی و همیشه‌قابل‌اعتماد در همهٔ مرورگرها باز می‌کنه)
  input.addEventListener('change',function(){
    var file=input.files&&input.files[0];if(!file){return}
    if(!/^image\//.test(file.type)){window._slApp.dialog.alert('فقط فایل عکس قابل قبوله','خطا');input.value='';return}
    if(file.size>15*1024*1024){window._slApp.dialog.alert('حجم عکس نباید بیشتر از ۱۵ مگابایت باشد','خطا');input.value='';return}
    var reader=new FileReader();
    reader.onload=function(){
      openAvatarCropper(reader.result,function(blob){uploadAvatarBlob(blob)});
      input.value='';
    };
    reader.onerror=function(){window._slApp.dialog.alert('خطا در خواندن فایل عکس','خطا');input.value=''};
    reader.readAsDataURL(file);
  });
}
function uploadAvatarBlob(blob){
  var spin=document.getElementById('me-ava-spin');
  if(spin)spin.style.display='grid';
  var fd=new FormData();fd.append('photo',blob,'avatar.jpg');
  fetch('/api/v1/me/avatar',{method:'POST',headers:{'X-Telegram-Init-Data':initData},body:fd})
    .then(function(r){return r.json()}).then(function(res){
      if(spin)spin.style.display='none';
      if(res&&res.ok&&res.avatar_url){
        setAvatarImg(res.avatar_url);
        if(window._slTg&&window._slTg.HapticFeedback)try{window._slTg.HapticFeedback.notificationOccurred('success')}catch(e){}
      }else{
        window._slApp.dialog.alert((res&&res.detail)||'آپلود عکس ناموفق بود','خطا');
      }
    }).catch(function(){
      if(spin)spin.style.display='none';
      window._slApp.dialog.alert('خطای شبکه در آپلود عکس','خطا');
    });
}
/* ─── پاپ‌آپ برش عکس (پن + زوم، خروجی مربع ۴۸۰×۴۸۰ روی canvas — بدون کتابخانهٔ خارجی) ─── */
function openAvatarCropper(dataUrl,onDone){
  _accPopup('برش عکس پروفایل',
    '<div class="sl-crop-view" id="crop-view"><img class="sl-crop-img" id="crop-img" src="'+dataUrl+'" alt=""></div>'+
    '<div class="sl-crop-zoom-row"><span class="sl-crop-zoom-i">－</span>'+
    '<input type="range" id="crop-zoom" class="sl-crop-zoom" min="100" max="300" value="100">'+
    '<span class="sl-crop-zoom-i">＋</span></div>'+
    '<div class="sl-checkout-btns"><button class="sl-checkout-btn sl-checkout-btn-combined" id="crop-confirm-btn">تأیید و آپلود</button></div>'+
    '<div class="sl-checkout-note">با کشیدن عکس جابه‌جا کنید و با اسلایدر بزرگ‌نمایی کنید</div>');
  var view=document.getElementById('crop-view'),img=document.getElementById('crop-img'),
      zoomInp=document.getElementById('crop-zoom'),confirmBtn=document.getElementById('crop-confirm-btn');
  if(!view||!img)return;
  var VP=240,nw=0,nh=0,baseScale=1,zoom=1,offX=0,offY=0,drag=null;
  function clamp(){
    var dw=nw*baseScale*zoom,dh=nh*baseScale*zoom;
    var maxX=Math.max(0,(dw-VP)/2),maxY=Math.max(0,(dh-VP)/2);
    if(offX>maxX)offX=maxX;if(offX<-maxX)offX=-maxX;
    if(offY>maxY)offY=maxY;if(offY<-maxY)offY=-maxY;
  }
  function render(){
    clamp();
    var dw=nw*baseScale*zoom,dh=nh*baseScale*zoom;
    img.style.width=dw+'px';img.style.height=dh+'px';
    img.style.transform='translate3d(calc(-50% + '+offX+'px), calc(-50% + '+offY+'px), 0)';
  }
  function onImgReady(){
    nw=img.naturalWidth;nh=img.naturalHeight;
    if(!nw||!nh)return;
    baseScale=VP/Math.min(nw,nh);zoom=1;offX=0;offY=0;
    if(zoomInp)zoomInp.value=100;
    render();
  }
  img.onload=onImgReady;
  if(img.complete&&img.naturalWidth)onImgReady();
  if(zoomInp)zoomInp.addEventListener('input',function(){zoom=(parseInt(zoomInp.value,10)||100)/100;render()});
  view.addEventListener('pointerdown',function(e){
    drag={sx:e.clientX,sy:e.clientY,ox:offX,oy:offY};
    try{view.setPointerCapture(e.pointerId)}catch(_e){}
  });
  view.addEventListener('pointermove',function(e){
    if(!drag)return;
    offX=drag.ox+(e.clientX-drag.sx);offY=drag.oy+(e.clientY-drag.sy);
    render();
  });
  function endDrag(){drag=null}
  view.addEventListener('pointerup',endDrag);
  view.addEventListener('pointercancel',endDrag);
  if(confirmBtn)confirmBtn.addEventListener('click',function(){
    if(!nw||!nh)return;
    var effScale=baseScale*zoom;
    var dw=nw*effScale,dh=nh*effScale;
    var imgLeft=(VP/2+offX)-dw/2,imgTop=(VP/2+offY)-dh/2;
    var sx=(-imgLeft)/effScale,sy=(-imgTop)/effScale,sSize=VP/effScale;
    var OUT=480;
    var cnv=document.createElement('canvas');cnv.width=OUT;cnv.height=OUT;
    var ctx=cnv.getContext('2d');
    ctx.drawImage(img,sx,sy,sSize,sSize,0,0,OUT,OUT);
    cnv.toBlob(function(blob){
      window._slApp.popup.close('#post-popup');
      if(blob)onDone(blob);
    },'image/jpeg',0.92);
  });
}

/* ─── پاداش سرزدن روزانه ─── */
function renderCheckinCard(){
  var c=document.getElementById('me-checkin-card');if(!c)return;
  api('/me/checkin',true).then(function(d){
    if(!d)return;
    if(d.available){
      c.innerHTML='<div class="sl-checkin-card"><span class="sl-checkin-e">🎁</span>'+
        '<div class="sl-checkin-txt"><b>پاداش سرزدن امروز رو بگیر</b>'+
        '<span>'+fmt(d.reward_amount||0)+' تومان هدیه'+(d.streak>0?' · رکورد '+fmt(d.streak)+' روزه':'')+'</span></div>'+
        '<button class="sl-checkin-btn" id="me-checkin-btn">دریافت</button></div>';
      var btn=document.getElementById('me-checkin-btn');
      if(btn)btn.addEventListener('click',function(){
        btn.disabled=true;btn.textContent='…';
        fetch('/api/v1/me/checkin',{method:'POST',headers:{'X-Telegram-Init-Data':initData}})
          .then(function(r){return r.json()}).then(function(res){
            if(!res.ok){c.innerHTML='';return}
            if(window._slTg&&window._slTg.HapticFeedback)try{window._slTg.HapticFeedback.notificationOccurred('success')}catch(e){}
            c.innerHTML='<div class="sl-checkin-card sl-checkin-done"><span class="sl-checkin-e">✅</span>'+
              '<div class="sl-checkin-txt"><b>'+fmt(res.reward)+' تومان به کیف‌پولت اضافه شد</b>'+
              '<span>رکورد سرزدن: '+fmt(res.streak)+' روز پشت‌سرهم</span></div></div>';
            var e=document.getElementById('me-bal');if(e)e.innerHTML=fmt(res.balance||0)+' <small>تومان</small>';
            _clearMeBadge();
          }).catch(function(){btn.disabled=false;btn.textContent='دریافت'});
      });
    }else if(d.streak>0){
      c.innerHTML='<div class="sl-checkin-card sl-checkin-mini"><span class="sl-checkin-e">🔥</span>'+
        '<div class="sl-checkin-txt"><b>رکورد '+fmt(d.streak)+' روزه</b><span>فردا دوباره سر بزن برای ادامهٔ رکورد</span></div></div>';
    }else{c.innerHTML=''}
  }).catch(function(){c.innerHTML=''});
}

/* ─── بج «حساب» — پاداش سرزدن در دسترس، یا پاسخ جدید پشتیبانی ─── */
function _clearMeBadge(){var b=document.getElementById('me-tab-badge');if(b)b.hidden=true}
function _checkMeBadge(){
  if(!loggedIn)return;
  var show=false;
  api('/me/checkin',true).then(function(d){
    if(d&&d.available){show=true;_applyMeBadge(show)}
  }).catch(function(){});
  fetch('https://panel.stland.ir/api/v1/support/ticket',{headers:{'X-Telegram-Init-Data':initData}})
    .then(function(r){return r.json()}).then(function(d){
      if(!d||!d.ok||!d.ticket)return;
      var msgs=d.messages||[];
      if(!msgs.length)return;
      var last=msgs[msgs.length-1];
      var seenKey='sl_sp_seen_'+d.ticket.id;
      var seenCount=parseInt(localStorage.getItem(seenKey)||'0',10);
      if(last.sender!=='user'&&msgs.length>seenCount)_applyMeBadge(true);
    }).catch(function(){});
  api('/me/notifications',true).then(function(d){
    var items=(d&&d.items)||[];
    if(items.some(function(n){return !n.is_read}))_applyMeBadge(true);
  }).catch(function(){});
}
function _applyMeBadge(v){var b=document.getElementById('me-tab-badge');if(b)b.hidden=!v}
window._slCheckMeBadge=_checkMeBadge;

/* ─── تاریخچهٔ اعلان‌ها ─── */
function openNotifications(){
  _accPopup('اعلان‌ها',skel(3));
  var nb=document.getElementById('me-notif-badge');if(nb)nb.style.display='none';
  api('/me/notifications',true).then(function(d){
    var items=(d&&d.items)||[];
    var b=_accBody();if(!b)return;
    if(!items.length){b.innerHTML='<div class="sl-empty"><span class="sl-empty-e">🔔</span>هنوز اعلانی ندارید.</div>';return}
    b.innerHTML='<div class="sl-group" style="margin:12px">'+items.map(function(n){
      return '<div class="sl-row" style="cursor:default'+(n.is_read?'':';background:var(--accent-soft,rgba(10,99,255,.05))')+'">'+
        '<span class="sl-ric" style="background:#7C3AED">'+esc(n.icon||'🔔')+'</span>'+
        '<span class="sl-row-grow"><div style="font-weight:'+(n.is_read?'500':'800')+'">'+esc(n.title)+'</div>'+
        (n.body?'<div style="font-size:12px;color:var(--mu);margin-top:2px">'+esc(n.body)+'</div>':'')+
        '<div style="font-size:11px;color:var(--mu);margin-top:2px">'+esc(String(n.created_at||'').slice(0,16))+'</div></span></div>';
    }).join('')+'</div>';
    fetch('/api/v1/me/notifications/read',{method:'POST',headers:{'X-Telegram-Init-Data':initData}}).then(function(){_clearMeBadge()});
  }).catch(function(){var b=_accBody();if(b)b.innerHTML=err('خطا در دریافت اعلان‌ها')});
}
window.openNotifications=openNotifications;

/* ═══ سفارش‌های من ═══ */
function openOrders(){
  var b=document.getElementById('orders-body');
  b.innerHTML=skel(3);
  document.getElementById('orders-popup').querySelector('.title').textContent='سفارش‌های من';
  app.popup.open('#orders-popup');
  api('/me/orders',true).then(function(d){
    var items=(d&&d.orders)||[];
    if(!items.length){b.innerHTML='<div class="sl-empty"><span class="sl-empty-e">📦</span>هنوز سفارشی ثبت نکرده‌اید.</div>';return}
    var ST={active:'تحویل‌شده',returned:'برگشتی'};
    b.innerHTML='<div class="sl-group" style="margin:12px">'+items.map(function(o){
      var hasData=!!o.delivered_data;
      var expandable=hasData||o.can_rate||o.has_rated;
      var row='<a href="#" class="sl-row" data-oid="'+o.id+'" style="cursor:pointer">'+
        '<span class="sl-ric" style="background:#0A63FF">📦</span>'+
        '<span class="sl-row-grow"><div>'+esc(o.title)+'</div>'+
        '<div style="font-size:12px;color:var(--mu);margin-top:2px">'+esc(String(o.created_at||'').slice(0,16))+'</div></span>'+
        '<span style="text-align:left"><div style="font-weight:800">'+fmt(o.price)+' <small>تومان</small></div>'+
        '<div style="font-size:11px;color:var(--mu);margin-top:2px">'+esc(ST[o.status]||o.status||'')+'</div></span>'+
        (expandable?'<span class="sl-chev" style="margin-right:4px">‹</span>':'')+'</a>';
      var detail='<div class="sl-order-detail" id="od-'+o.id+'" hidden style="padding:0 14px 14px">'+
        (hasData?
          '<div class="sl-checkout-wallet" style="direction:ltr;text-align:right;word-break:break-all;font-size:13px;white-space:pre-wrap">'+nl2br(o.delivered_data)+'</div>'+
          '<div class="sl-wal-acts" style="margin-top:8px"><button class="sl-checkout-btn sl-checkout-btn-wallet" data-copy="'+o.id+'">📋 کپی مشخصات</button></div>'
          :
          (o.has_rated?'':'<div class="sl-checkout-note">مشخصات این سفارش هنوز ثبت نشده — یا از طریق چت ربات ارسال شده، یا هنوز در صف تحویله.</div>')
        )+
        (o.has_rated?'<div class="sl-checkout-note" style="margin-top:8px">✅ نظرتون برای این محصول ثبت شده — ممنون از وقتی که گذاشتید.</div>':'')+
        (o.can_rate?
          '<div class="sl-rate-box" id="rate-box-'+o.id+'">'+
            '<div class="sl-rate-label">این محصول رو چطور دیدید؟</div>'+
            '<div class="sl-rate-stars" data-oid="'+o.id+'">'+[1,2,3,4,5].map(function(n){return '<span class="sl-rate-star" data-n="'+n+'">☆</span>'}).join('')+'</div>'+
            '<textarea class="sl-rate-comment" id="rate-comment-'+o.id+'" rows="2" placeholder="نظرتون (اختیاری)…"></textarea>'+
            '<button class="sl-checkout-btn sl-checkout-btn-combined" id="rate-submit-'+o.id+'" style="margin-top:8px" disabled>ثبت نظر</button>'+
          '</div>'
          :'')+
        '</div>';
      return row+detail;
    }).join('')+'</div>';
    b.querySelectorAll('.sl-row[data-oid]').forEach(function(rowEl){
      rowEl.addEventListener('click',function(e){
        e.preventDefault();
        var det=document.getElementById('od-'+rowEl.dataset.oid);
        if(det)det.hidden=!det.hidden;
      });
    });
    b.querySelectorAll('[data-copy]').forEach(function(btn){
      btn.addEventListener('click',function(e){
        e.preventDefault();e.stopPropagation();
        var det=document.getElementById('od-'+btn.dataset.copy);
        var txt=det?det.querySelector('.sl-checkout-wallet').textContent:'';
        var done=function(){btn.textContent='✅ کپی شد';setTimeout(function(){btn.textContent='📋 کپی مشخصات'},1500)};
        if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(txt).then(done).catch(done)}
        else{done()}
      });
    });
    b.querySelectorAll('.sl-rate-stars').forEach(function(starsEl){
      var oid=starsEl.dataset.oid,selected=0;
      var stars=starsEl.querySelectorAll('.sl-rate-star');
      function paint(n){stars.forEach(function(s){s.textContent=(+s.dataset.n<=n)?'★':'☆'})}
      stars.forEach(function(s){
        s.addEventListener('click',function(e){
          e.preventDefault();e.stopPropagation();
          selected=+s.dataset.n;paint(selected);
          var btn=document.getElementById('rate-submit-'+oid);if(btn)btn.disabled=false;
        });
      });
      var sb=document.getElementById('rate-submit-'+oid);
      if(sb)sb.addEventListener('click',function(e){
        e.preventDefault();e.stopPropagation();
        if(!selected)return;
        sb.disabled=true;sb.textContent='در حال ثبت…';
        var comment=(document.getElementById('rate-comment-'+oid).value||'').trim();
        fetch('/api/v1/orders/'+oid+'/rate',{method:'POST',headers:{'Content-Type':'application/json','X-Telegram-Init-Data':initData},
          body:JSON.stringify({rating:selected,comment:comment})
        }).then(function(r){return r.json().then(function(d){return {status:r.status,d:d}})}).then(function(res){
          var box=document.getElementById('rate-box-'+oid);
          if(res.status!==200||!res.d.ok){
            if(box)box.innerHTML='<div class="sl-checkout-note" style="margin-top:12px">'+esc((res.d&&res.d.detail)||'خطا در ثبت نظر')+'</div>';
            return;
          }
          if(box)box.innerHTML='<div class="sl-checkout-note" style="margin-top:12px">✅ نظرتون ثبت شد — ممنون از وقتی که گذاشتید.</div>';
        }).catch(function(){sb.disabled=false;sb.textContent='ثبت نظر'});
      });
    });
  }).catch(function(){b.innerHTML=err('خطا در دریافت سفارش‌ها')});
}
window.openOrders=openOrders;

/* ═══ علاقه‌مندی‌ها ═══ */
function openFavorites(){
  var b=document.getElementById('orders-body');
  b.innerHTML=skel(3);
  document.getElementById('orders-popup').querySelector('.title').textContent='علاقه‌مندی‌ها';
  app.popup.open('#orders-popup');
  api('/favorites',true).then(function(d){
    var items=(d&&d.products)||[];
    if(!items.length){b.innerHTML='<div class="sl-empty"><span class="sl-empty-e">♡</span>هنوز چیزی به علاقه‌مندی‌ها اضافه نکرده‌اید.<br><span style="font-size:12px">روی ♡ کنار هر محصول بزنید.</span></div>';return}
    b.innerHTML='<div class="sl-group" style="margin:12px">'+items.map(function(p){
      var f=p.flash_active;
      return '<a href="#" class="sl-row" data-favpid="'+p.id+'">'+
        '<span class="sl-ric" style="background:#0A63FF">'+(p._e||'📦')+'</span>'+
        '<span class="sl-row-grow">'+esc(p.title)+
        (p.rating_count?'<div style="margin-top:2px">'+starsHtml(p.rating_avg,p.rating_count,'sm')+'</div>':'')+'</span>'+
        '<span style="text-align:left"><div style="font-weight:800">'+fmt(p.effective_price)+' <small>تومان</small></div>'+
        (f?'<div class="sl-flash" style="font-size:10px;margin-top:2px">⚡️ فروش فوری</div>':'')+'</span>'+
        '<span class="sl-chev">‹</span></a>';
    }).join('')+'</div>';
    b.querySelectorAll('[data-favpid]').forEach(function(rowEl){
      rowEl.addEventListener('click',function(e){
        e.preventDefault();
        app.popup.close('#orders-popup');
        setTimeout(function(){openP(rowEl.dataset.favpid)},300);
      });
    });
  }).catch(function(){b.innerHTML=err('خطا در دریافت علاقه‌مندی‌ها')});
}
window.openFavorites=openFavorites;

/* ═══ صفحات حساب (کیف‌پول/همکاری/دعوت) — از post-popup به‌عنوان ظرف عمومی استفاده می‌کنند ═══ */
function _accPopup(title,html){
  var t=document.getElementById('post-title'),b=document.getElementById('post-body');
  t.textContent=title;b.innerHTML='<div class="sl-acc-page">'+html+'</div>';
  window._slApp.popup.open('#post-popup');
}
function _accBody(){return document.querySelector('#post-body .sl-acc-page')}

/* ─── کیف‌پول ─── */
function openWallet(){
  _accPopup('کیف پول',skel(2));
  window._slApi('/me/wallet',true).then(function(d){
    var b=_accBody();if(!b)return;
    b.innerHTML='<div class="sl-wal-big">'+window._slFmt(d.balance||0)+' <small>تومان</small></div>'+
      '<div class="sl-wal-acts"><button class="sl-checkout-btn sl-checkout-btn-wallet" id="wal-charge-btn">＋ شارژ کیف‌پول</button></div>'+
      '<div class="sl-checkout-note">بعد از پرداخت موفق، موجودی به‌صورت خودکار به‌روز می‌شود.</div>';
    var cb=document.getElementById('wal-charge-btn');
    if(cb)cb.addEventListener('click',startCharge);
  }).catch(function(){var b=_accBody();if(b)b.innerHTML=err('خطا در دریافت موجودی')});
}
window.openWallet=openWallet;

function startCharge(){
  // همیشه popup.open صدا زده می‌شه (نه فقط وقتی _accBody() چیزی برنمی‌گردونه) — چون
  // محتوای پاپ‌آپ قبلی حتی بعد از close() در DOM باقی می‌مونه (فقط مخفی می‌شه)، پس
  // چک «آیا _accBody() چیزی داره؟» نمی‌تونه تشخیص بده پاپ‌آپ واقعاً بازه یا بسته
  _accPopup('شارژ کیف‌پول','');
  var b=_accBody();if(!b)return;
  b.innerHTML='<div class="sl-checkout-sec">مبلغ شارژ (تومان)</div>'+
    '<div class="sl-pay-box"><input type="tel" inputmode="numeric" id="charge-amount" '+
    'class="sl-amount-input" placeholder="حداقل ۱۰٬۰۰۰ تومان" autocomplete="off"></div>'+
    '<div class="sl-checkout-btns"><button class="sl-checkout-btn sl-checkout-btn-combined" id="charge-next-btn">ادامه</button></div>';
  var inp=document.getElementById('charge-amount');
  var nb=document.getElementById('charge-next-btn');
  function goNext(){
    var amount=parseInt((inp.value||'').replace(/[^0-9]/g,''),10);
    if(!amount||amount<10000){window._slApp.dialog.alert('حداقل مبلغ شارژ ۱۰٬۰۰۰ تومان است','خطا');return}
    showPaymentMethods(amount);
  }
  if(nb)nb.addEventListener('click',goNext);
  if(inp){inp.addEventListener('keydown',function(e){if(e.key==='Enter')goNext()});setTimeout(function(){inp.focus()},200)}
}
window.startCharge=startCharge;

/* ─── انتخاب روش پرداخت — گیت‌وی / کارت‌به‌کارت / رمزارز ─── */
function showPaymentMethods(amount){
  var b=_accBody();if(!b)return;
  b.innerHTML='<div class="sl-checkout-sec">روش پرداخت — '+fmt(amount)+' <small>تومان</small></div>'+
    '<div class="sl-checkout-btns" id="pm-list">'+skel(2)+'</div>';
  api('/payment/methods').then(function(d){
    var list=document.getElementById('pm-list');if(!list)return;
    var html='<button class="sl-checkout-btn sl-checkout-btn-gateway" data-pm="gateway">🏦 درگاه پرداخت (زرین‌پال)</button>'+
      '<button class="sl-checkout-btn sl-checkout-btn-gateway" data-pm="card2card">💳 کارت‌به‌کارت</button>';
    if(d.crypto&&d.crypto.enabled&&(d.crypto.usdt_trc20||d.crypto.trx)){
      html+='<button class="sl-checkout-btn sl-checkout-btn-gateway" data-pm="crypto">₿ پرداخت رمزارز</button>';
    }
    list.innerHTML=html;
    list.querySelectorAll('[data-pm]').forEach(function(btn){
      btn.addEventListener('click',function(){
        var pm=btn.dataset.pm;
        if(pm==='gateway')payGateway(amount);
        else if(pm==='card2card')payCard2card(amount,d.card2card);
        else if(pm==='crypto')payCryptoPickNetwork(amount,d.crypto);
      });
    });
  }).catch(function(){var list=document.getElementById('pm-list');if(list)list.innerHTML=err('خطا در دریافت روش‌های پرداخت')});
}

function payGateway(amount){
  var b=_accBody();
  if(b)b.innerHTML='<div class="sl-checkout-note">⏳ در حال اتصال به درگاه...</div>';
  fetch('https://panel.stland.ir/api/v1/wallet/topup',{
    method:'POST',
    headers:{'Content-Type':'application/json','X-Telegram-Init-Data':window._slInitData},
    body:JSON.stringify({amount:amount})
  }).then(function(r){return r.json().then(function(d){return {status:r.status,d:d}})}).then(function(res){
    if(res.status!==200||!res.d.ok){
      window._slApp.dialog.alert((res.d&&(res.d.detail||res.d.error))||'خطا در شارژ کیف‌پول','خطا');
      openWallet();return;
    }
    if(window._slTg&&window._slTg.openLink)window._slTg.openLink(res.d.redirect_url);
    else window.open(res.d.redirect_url,'_blank');
  }).catch(function(){window._slApp.dialog.alert('خطای شبکه','خطا');openWallet()});
}

function showChargeDone(msg){
  var b=_accBody();if(!b)return;
  b.innerHTML='<div class="sl-checkout-result"><div class="sl-checkout-result-e">✅</div>'+
    '<div class="sl-checkout-result-t">ثبت شد</div><div class="sl-checkout-result-s">'+esc(msg)+'</div>'+
    '<button class="sl-checkout-close-btn" id="charge-done-btn">باشه</button></div>';
  var db_=document.getElementById('charge-done-btn');
  if(db_)db_.addEventListener('click',openWallet);
}

function payCard2card(amount,info){
  var b=_accBody();if(!b)return;
  info=info||{};
  b.innerHTML='<div class="sl-checkout-sec">کارت‌به‌کارت — '+fmt(amount)+' <small>تومان</small></div>'+
    '<div class="sl-pay-box"><div class="sl-checkout-wallet-info">این مبلغ رو به کارت زیر واریز کنید:</div>'+
    '<div class="sl-cc-num">'+esc(info.card_number||'')+'</div>'+
    '<div class="sl-checkout-wallet-info">به نام '+esc(info.card_name||'')+'</div></div>'+
    '<div class="sl-checkout-sec">عکس رسید واریز</div>'+
    '<div class="sl-pay-box"><label class="sl-file-btn" id="cc-photo-label">📎 انتخاب عکس رسید<input type="file" accept="image/*" id="cc-photo" hidden></label></div>'+
    '<div class="sl-checkout-btns"><button class="sl-checkout-btn sl-checkout-btn-combined" id="cc-submit-btn">ثبت رسید</button></div>'+
    '<div class="sl-checkout-note">بعد از تأیید ادمین، کیف‌پول شارژ می‌شود.</div>';
  var fileInp=document.getElementById('cc-photo'),lbl=document.getElementById('cc-photo-label');
  if(fileInp)fileInp.addEventListener('change',function(){
    if(fileInp.files[0]&&lbl)lbl.textContent='✅ '+fileInp.files[0].name;
  });
  var sb=document.getElementById('cc-submit-btn');
  if(sb)sb.addEventListener('click',function(){
    var f=fileInp&&fileInp.files[0];
    if(!f){window._slApp.dialog.alert('عکس رسید رو انتخاب کنید','خطا');return}
    sb.disabled=true;sb.textContent='در حال ارسال…';
    var fd=new FormData();fd.append('amount',amount);fd.append('photo',f);
    fetch('https://panel.stland.ir/api/v1/wallet/card2card',{
      method:'POST',headers:{'X-Telegram-Init-Data':window._slInitData},body:fd
    }).then(function(r){return r.json().then(function(d){return {status:r.status,d:d}})}).then(function(res){
      if(res.status!==200||!res.d.ok){
        window._slApp.dialog.alert((res.d&&(res.d.detail||res.d.error))||'خطا در ثبت رسید','خطا');
        sb.disabled=false;sb.textContent='ثبت رسید';return;
      }
      showChargeDone('رسید شما ثبت شد و در انتظار بررسی ادمینه.');
    }).catch(function(){window._slApp.dialog.alert('خطای شبکه','خطا');sb.disabled=false;sb.textContent='ثبت رسید'});
  });
}

function payCryptoPickNetwork(amount,info){
  var b=_accBody();if(!b)return;
  info=info||{};
  var nets=[];
  if(info.usdt_trc20)nets.push({k:'usdt',label:'💵 USDT (TRC20)',addr:info.usdt_trc20});
  if(info.trx)nets.push({k:'trx',label:'🔺 TRX (Tron)',addr:info.trx});
  b.innerHTML='<div class="sl-checkout-sec">شبکهٔ پرداخت رو انتخاب کنید</div>'+
    '<div class="sl-checkout-btns" id="net-list">'+nets.map(function(n){
      return '<button class="sl-checkout-btn sl-checkout-btn-gateway" data-net="'+n.k+'">'+n.label+'</button>';
    }).join('')+'</div>';
  document.getElementById('net-list').querySelectorAll('[data-net]').forEach(function(btn){
    btn.addEventListener('click',function(){
      var n=nets.filter(function(x){return x.k===btn.dataset.net})[0];
      payCryptoForm(amount,n,info.note);
    });
  });
}

function payCryptoForm(amount,net,note){
  var b=_accBody();if(!b)return;
  b.innerHTML='<div class="sl-checkout-sec">'+esc(net.label)+' — '+fmt(amount)+' <small>تومان</small></div>'+
    '<div class="sl-pay-box"><div class="sl-checkout-wallet-info">آدرس واریز:</div>'+
    '<div class="sl-cc-num">'+esc(net.addr)+'</div></div>'+
    (note?'<div class="sl-checkout-note">'+note+'</div>':'')+
    '<div class="sl-checkout-sec">TXID (هش تراکنش)</div>'+
    '<div class="sl-pay-box"><input type="text" id="crypto-txid" class="sl-amount-input" placeholder="TXID را اینجا وارد کنید" autocomplete="off"></div>'+
    '<div class="sl-checkout-btns"><button class="sl-checkout-btn sl-checkout-btn-combined" id="crypto-submit-btn">ثبت تراکنش</button></div>';
  var sb=document.getElementById('crypto-submit-btn'),tx=document.getElementById('crypto-txid');
  if(sb)sb.addEventListener('click',function(){
    var txid=(tx.value||'').trim();
    if(!txid){window._slApp.dialog.alert('TXID رو وارد کنید','خطا');return}
    sb.disabled=true;sb.textContent='در حال ثبت…';
    fetch('https://panel.stland.ir/api/v1/wallet/crypto',{
      method:'POST',
      headers:{'Content-Type':'application/json','X-Telegram-Init-Data':window._slInitData},
      body:JSON.stringify({amount:amount,network:net.k,txid:txid})
    }).then(function(r){return r.json().then(function(d){return {status:r.status,d:d}})}).then(function(res){
      if(res.status!==200||!res.d.ok){
        window._slApp.dialog.alert((res.d&&(res.d.detail||res.d.error))||'خطا در ثبت تراکنش','خطا');
        sb.disabled=false;sb.textContent='ثبت تراکنش';return;
      }
      showChargeDone('تراکنش ثبت شد. پس از تأیید (۱۵-۳۰ دقیقه)، کیف‌پول شارژ می‌شود.');
    }).catch(function(){window._slApp.dialog.alert('خطای شبکه','خطا');sb.disabled=false;sb.textContent='ثبت تراکنش'});
  });
}

/* ─── پنل همکاری — بازطراحی کامل به‌صورت پنل چندبخشی، مطابق داشبورد بات ───
   (_show_partner_dashboard) به‌جز «چت با پشتیبان» که چون اپ خودش گزینهٔ پشتیبانی
   مستقل داره حذف شده. «دعوت دوستان» هم دیگه ردیف مستقلی در تب حساب نداره — طبق
   دستور صریح مالک پروژه، فقط از داخل همین پنل (بخش دعوت و تبلیغ) در دسترسه.
   ساختار: openPartner (داشبورد اصلی: سطح+پیشرفت+لیست ناوبری ۴بخشی) → هر بخش
   (فروشندگان من/پروفایل/کیف‌پول/دعوت) صفحهٔ خودش رو همون‌جا داخل popup رندر
   می‌کنه، بدون بستن/بازکردن popup — با یه لینک «‹ بازگشت» بالای صفحه. */
function _ptTitle(t){var el=document.getElementById('post-title');if(el)el.textContent=t}
function _ptBackHtml(label){return '<a href="#" class="sl-pt-back" id="pt-back-link">‹ '+(label||'بازگشت به پنل همکاری')+'</a>'}
function _ptWireBack(target){var el=document.getElementById('pt-back-link');if(el)el.addEventListener('click',function(e){e.preventDefault();(target||openPartner)()})}
function _ptRow(icon,color,label,rowId,badgeHtml){
  return '<a class="sl-row" href="#" id="'+rowId+'"><span class="sl-ric" style="background:'+color+'">'+icon+'</span>'+
    '<span class="sl-row-grow">'+label+'</span>'+(badgeHtml||'')+'<span class="sl-chev">‹</span></a>';
}

function openPartner(){
  _accPopup('پنل همکاری',skel(2));
  window._slApi('/me/partner',true).then(function(d){
    var b=_accBody();if(!b)return;
    if(!d.is_partner){
      if(d.pending_status==='pending'){
        b.innerHTML='<div class="sl-empty"><span class="sl-empty-e">⏳</span>درخواست همکاری شما ثبت شده و در انتظار بررسی ادمینه.<br><span style="font-size:12px">معمولاً کمتر از ۲۴ ساعت طول می‌کشه.</span></div>';
        return;
      }
      if(d.pending_status==='rejected'){
        b.innerHTML='<div class="sl-empty"><span class="sl-empty-e">❌</span>درخواست قبلی شما رد شده.<br><span style="font-size:12px">برای بررسی مجدد با پشتیبانی در تماس باشید.</span></div>';
        return;
      }
      renderPartnerApplyForm(b);
      return;
    }
    _ptDashboard(d);
  }).catch(function(){var b=_accBody();if(b)b.innerHTML=err('خطا در دریافت اطلاعات همکاری')});
}
window.openPartner=openPartner;

function _ptDashboard(d){
  _ptTitle('پنل همکاری');
  var b=_accBody();if(!b)return;
  var tierName=(d.tier&&d.tier.name)||'—';
  var tierIcon=(d.tier&&d.tier.icon)||'🏅';
  var progressHtml='';
  if(d.next_tier){
    var cur=(d.tier&&d.tier.order_count)||0;
    var pct=Math.max(0,Math.min(100,Math.round(cur/d.next_tier.min_orders*100)));
    progressHtml='<div class="sl-tier-progress">'+
      '<div class="sl-tier-progress-top"><span>تا سطح '+window._slEsc(d.next_tier.icon||'')+' '+window._slEsc(d.next_tier.name)+'</span>'+
      '<b>'+window._slFmt(d.next_tier.orders_needed)+' سفارش دیگه</b></div>'+
      '<div class="sl-tier-progress-bar"><div class="sl-tier-progress-fill" style="width:'+pct+'%"></div></div>'+
    '</div>';
  }else{
    progressHtml='<div class="sl-checkout-note" style="margin-top:0">🎉 شما در بالاترین سطح همکاری هستید!</div>';
  }
  b.innerHTML='<div style="text-align:center;padding:8px 0">'+
    '<span style="font-size:44px">'+window._slEsc(tierIcon)+'</span>'+
    '<p style="margin:8px 0 0;font-size:16px;font-weight:800">سطح '+window._slEsc(tierName)+'</p>'+
    '<p style="margin:4px 0 0;font-size:12px;color:var(--mu)">'+window._slFmt((d.tier&&d.tier.order_count)||0)+' خرید همکاری</p></div>'+
    progressHtml+
    '<div class="sl-group">'+
      _ptRow('👥','#F59E0B','فروشندگان من','pt-team-row')+
      _ptRow('👤','#0A63FF','پروفایل فروشگاه','pt-profile-row')+
      _ptRow('💼','#22C55E','کیف‌پول همکاری','pt-wallet-row','<span class="sl-badge" id="pt-wallet-badge"></span>')+
      _ptRow('🔗','#7C3AED','دعوت و تبلیغ','pt-invite-row')+
    '</div>';
  var wb=document.getElementById('pt-wallet-badge');
  if(wb)wb.textContent=window._slFmt(d.balance||0)+' ت';
  var r1=document.getElementById('pt-team-row');if(r1)r1.addEventListener('click',function(e){e.preventDefault();_ptTeam()});
  var r2=document.getElementById('pt-profile-row');if(r2)r2.addEventListener('click',function(e){e.preventDefault();_ptProfile()});
  var r3=document.getElementById('pt-wallet-row');if(r3)r3.addEventListener('click',function(e){e.preventDefault();_ptWallet()});
  var r4=document.getElementById('pt-invite-row');if(r4)r4.addEventListener('click',function(e){e.preventDefault();_ptInvite()});
}

/* ─── فروشندگان من — تیم فروش دوسطحی ─── */
function _ptTeam(){
  _ptTitle('فروشندگان من');
  var b=_accBody();if(!b)return;
  b.innerHTML=_ptBackHtml()+skel(2);_ptWireBack();
  window._slApi('/partner/team',true).then(function(d){
    var b2=_accBody();if(!b2)return;
    var members=d.members||[];
    var html;
    if(!members.length){
      html='<div class="sl-empty" style="padding:40px 12px"><span class="sl-empty-e">👥</span>هنوز فروشنده‌ای ندارید.<br><span style="font-size:12px">لینک دعوت خودتون رو به اشتراک بذارید تا تیم فروش شما رشد کنه.</span></div>';
    }else{
      html='<div class="sl-group">'+members.map(function(m,i){
        var medal=(i===0&&m.order_count>0)?'🥇':(i===1&&m.order_count>0)?'🥈':(i===2&&m.order_count>0)?'🥉':'👤';
        var sub=(m.order_count>0
          ? window._slFmt(m.order_count)+' خرید · '+window._slFmt(m.total_spent)+' تومان'
          : 'بدون خرید')+(m.own_subs?' · 👥'+window._slFmt(m.own_subs):'');
        return '<div class="sl-row" style="cursor:default"><span class="sl-ric" style="background:#F59E0B">'+medal+'</span>'+
          '<div class="sl-row-grow"><div style="font-weight:700;font-size:13.5px">'+window._slEsc(m.name)+'</div>'+
          '<div style="font-size:11.5px;color:var(--mu);margin-top:2px">'+sub+'</div></div></div>';
      }).join('')+'</div>'+
      '<div class="sl-checkout-wallet" style="display:flex;justify-content:space-around;text-align:center;gap:8px">'+
        '<div><div class="sl-checkout-wallet-info">تعداد</div><div class="sl-checkout-wallet-bal">'+window._slFmt(d.total_members)+'</div></div>'+
        '<div><div class="sl-checkout-wallet-info">خرید</div><div class="sl-checkout-wallet-bal">'+window._slFmt(d.total_orders)+'</div></div>'+
        '<div><div class="sl-checkout-wallet-info">فروش (ت)</div><div class="sl-checkout-wallet-bal">'+window._slFmt(d.total_spent)+'</div></div>'+
      '</div>';
    }
    b2.innerHTML=_ptBackHtml()+html;_ptWireBack();
  }).catch(function(){var b2=_accBody();if(b2){b2.innerHTML=_ptBackHtml()+err('خطا در دریافت اطلاعات تیم');_ptWireBack()}});
}

/* ─── پروفایل فروشگاه — نام/فروشگاه/شهر/آدرس + اطلاعات بانکی، دقیقاً همون فیلدهای
   قابل‌ویرایش داشبورد بات (_show_partner_profile/_PEDIT_MAP)، در یک فرم واحد ─── */
function _ptProfile(){
  _ptTitle('پروفایل فروشگاه');
  var b=_accBody();if(!b)return;
  b.innerHTML=_ptBackHtml()+skel(3);_ptWireBack();
  window._slApi('/partner/profile',true).then(function(d){
    var p=(d&&d.profile)||{};
    var b2=_accBody();if(!b2)return;
    function field(id,label,val,ph,dir){
      return '<div class="sl-checkout-sec">'+label+'</div>'+
        '<div class="sl-pay-box"><input type="text" id="'+id+'" class="sl-amount-input" style="text-align:'+(dir==='ltr'?'left':'right')+'" '+(dir?'dir="'+dir+'"':'')+
        ' value="'+window._slEsc(val||'')+'" placeholder="'+(ph||'')+'" autocomplete="off"></div>';
    }
    b2.innerHTML=_ptBackHtml()+
      field('pf-name','نام و نام خانوادگی',p.name,'مثلاً علی رضایی')+
      field('pf-shop','نام فروشگاه',p.shop_name,'مثلاً فروشگاه من')+
      field('pf-city','شهر',p.city,'مثلاً تهران')+
      field('pf-address','آدرس',p.address,'آدرس کامل فروشگاه')+
      '<div class="sl-checkout-sec" style="padding-top:22px">💳 اطلاعات بانکی (برای تسویه)</div>'+
      field('pf-bankname','نام صاحب حساب',p.bank_owner_name,'مطابق کارت بانکی')+
      field('pf-card','شمارهٔ کارت',p.card_number,'۱۶ رقم','ltr')+
      field('pf-iban','شمارهٔ شبا',p.iban,'IR...','ltr')+
      '<div class="sl-checkout-btns"><button class="sl-checkout-btn sl-checkout-btn-combined" id="pf-save-btn">💾 ذخیرهٔ تغییرات</button></div>';
    _ptWireBack();
    var sb=document.getElementById('pf-save-btn');
    if(sb)sb.addEventListener('click',function(){
      var body={
        name:(document.getElementById('pf-name').value||'').trim(),
        shop_name:(document.getElementById('pf-shop').value||'').trim(),
        city:(document.getElementById('pf-city').value||'').trim(),
        address:(document.getElementById('pf-address').value||'').trim(),
        bank_owner_name:(document.getElementById('pf-bankname').value||'').trim(),
        card_number:(document.getElementById('pf-card').value||'').trim(),
        iban:(document.getElementById('pf-iban').value||'').trim()
      };
      Object.keys(body).forEach(function(k){if(!body[k])delete body[k]});
      if(!Object.keys(body).length){window._slApp.dialog.alert('حداقل یک فیلد رو تغییر بدید','خطا');return}
      sb.disabled=true;sb.textContent='در حال ذخیره…';
      fetch('https://panel.stland.ir/api/v1/partner/profile',{
        method:'POST',headers:{'Content-Type':'application/json','X-Telegram-Init-Data':window._slInitData},
        body:JSON.stringify(body)
      }).then(function(r){return r.json().then(function(dd){return {status:r.status,d:dd}})}).then(function(res){
        if(res.status!==200||!res.d.ok){
          window._slApp.dialog.alert((res.d&&res.d.detail)||'خطا در ذخیره','خطا');
          sb.disabled=false;sb.textContent='💾 ذخیرهٔ تغییرات';return;
        }
        sb.textContent='✅ ذخیره شد';
        setTimeout(function(){_ptProfile()},700);
      }).catch(function(){window._slApp.dialog.alert('خطای شبکه','خطا');sb.disabled=false;sb.textContent='💾 ذخیرهٔ تغییرات'});
    });
  }).catch(function(){var b2=_accBody();if(b2){b2.innerHTML=_ptBackHtml()+err('خطا در دریافت پروفایل');_ptWireBack()}});
}

/* ─── کیف‌پول همکاری — موجودی + تراکنش‌ها + انتقال به کیف‌پول اصلی + درخواست تسویه ─── */
function _ptWallet(){
  _ptTitle('کیف‌پول همکاری');
  var b=_accBody();if(!b)return;
  b.innerHTML=_ptBackHtml()+skel(2);_ptWireBack();
  window._slApi('/partner/wallet',true).then(function(d){
    var b2=_accBody();if(!b2)return;
    var typeMap={credit:'💚 واریز پورسانت',transfer_out:'🔄 انتقال به کیف‌پول اصلی',payout_request:'📤 درخواست تسویه',payout_rejected:'↩️ برگشت تسویه'};
    var txHtml=(d.transactions&&d.transactions.length)?'<div class="sl-group" style="margin-top:8px">'+d.transactions.map(function(tx){
      var plus=(tx.type==='credit'||tx.type==='payout_rejected');
      return '<div class="sl-row" style="cursor:default"><span class="sl-ric" style="background:'+(plus?'#22C55E':'#EF4444')+'">'+(plus?'+':'−')+'</span>'+
        '<div class="sl-row-grow"><div style="font-weight:700;font-size:13px">'+(typeMap[tx.type]||tx.type)+'</div>'+
        '<div style="font-size:11px;color:var(--mu);margin-top:2px">'+window._slEsc(tx.created_at||'')+'</div></div>'+
        '<div style="font-weight:800;font-size:13px;color:'+(plus?'#22C55E':'#EF4444')+'">'+(plus?'+':'−')+window._slFmt(tx.amount)+'</div></div>';
    }).join('')+'</div>':'<div class="sl-empty" style="padding:24px 12px"><span class="sl-empty-e">📋</span>هنوز تراکنشی ثبت نشده.</div>';
    b2.innerHTML=_ptBackHtml()+
      '<div class="sl-checkout-wallet"><div class="sl-checkout-wallet-info">موجودی کیف‌پول همکاری</div>'+
      '<div class="sl-checkout-wallet-bal" style="font-size:22px">'+window._slFmt(d.balance||0)+' تومان</div></div>'+
      '<div class="sl-checkout-btns"><button class="sl-checkout-btn sl-checkout-btn-wallet" id="pt-transfer-btn">🔄 انتقال به کیف‌پول اصلی</button>'+
      '<button class="sl-checkout-btn sl-checkout-btn-combined" id="pt-payout-btn">📤 درخواست تسویه</button></div>'+
      '<div class="sl-checkout-sec">📋 آخرین تراکنش‌ها</div>'+txHtml;
    _ptWireBack();
    var tb=document.getElementById('pt-transfer-btn');
    if(tb)tb.addEventListener('click',function(){_ptTransfer(d.balance||0)});
    var pb=document.getElementById('pt-payout-btn');
    if(pb)pb.addEventListener('click',function(){openPayoutRequest()});
  }).catch(function(){var b2=_accBody();if(b2){b2.innerHTML=_ptBackHtml()+err('خطا در دریافت کیف‌پول همکاری');_ptWireBack()}});
}

/* ─── انتقال کیف‌پول همکاری → کیف‌پول اصلی ─── */
function _ptTransfer(balance){
  _ptTitle('انتقال به کیف‌پول اصلی');
  var b=_accBody();if(!b)return;
  b.innerHTML=_ptBackHtml('بازگشت به کیف‌پول')+
    '<div class="sl-checkout-wallet"><div class="sl-checkout-wallet-info">موجودی کیف‌پول همکاری</div>'+
    '<div class="sl-checkout-wallet-bal">'+window._slFmt(balance)+' تومان</div></div>'+
    '<div class="sl-checkout-sec">مبلغ انتقال (تومان)</div>'+
    '<div class="sl-pay-box"><input type="tel" inputmode="numeric" id="pt-tr-amount" class="sl-amount-input" placeholder="مبلغ مورد نظر" autocomplete="off"></div>'+
    '<div class="sl-checkout-btns"><button class="sl-checkout-btn sl-checkout-btn-gateway" id="pt-tr-all-btn">انتقال کل موجودی</button>'+
    '<button class="sl-checkout-btn sl-checkout-btn-combined" id="pt-tr-submit-btn">انتقال</button></div>';
  _ptWireBack(_ptWallet);
  var inp=document.getElementById('pt-tr-amount');
  function doTransfer(body){
    var sb=document.getElementById('pt-tr-submit-btn'),ab=document.getElementById('pt-tr-all-btn');
    if(sb)sb.disabled=true;if(ab)ab.disabled=true;
    fetch('https://panel.stland.ir/api/v1/partner/wallet/transfer',{
      method:'POST',headers:{'Content-Type':'application/json','X-Telegram-Init-Data':window._slInitData},
      body:JSON.stringify(body)
    }).then(function(r){return r.json().then(function(dd){return {status:r.status,d:dd}})}).then(function(res){
      if(res.status!==200||!res.d.ok){
        window._slApp.dialog.alert((res.d&&res.d.detail)||'خطا در انتقال','خطا');
        if(sb)sb.disabled=false;if(ab)ab.disabled=false;return;
      }
      var b2=_accBody();if(!b2)return;
      b2.innerHTML=_ptBackHtml('بازگشت به کیف‌پول')+'<div class="sl-checkout-result"><div class="sl-checkout-result-e">✅</div>'+
        '<div class="sl-checkout-result-t">انجام شد</div>'+
        '<div class="sl-checkout-result-s">'+window._slFmt(res.d.transferred)+' تومان به کیف‌پول اصلی شما منتقل شد.</div>'+
        '<button class="sl-checkout-close-btn" id="pt-tr-done-btn">باشه</button></div>';
      _ptWireBack(_ptWallet);
      var db_=document.getElementById('pt-tr-done-btn');
      if(db_)db_.addEventListener('click',function(){_ptWallet()});
    }).catch(function(){window._slApp.dialog.alert('خطای شبکه','خطا');if(sb)sb.disabled=false;if(ab)ab.disabled=false});
  }
  var sb=document.getElementById('pt-tr-submit-btn');
  if(sb)sb.addEventListener('click',function(){
    var amount=parseInt((inp.value||'').replace(/[^0-9]/g,''),10);
    if(!amount||amount<=0){window._slApp.dialog.alert('مبلغ رو وارد کنید','خطا');return}
    doTransfer({amount:amount});
  });
  var ab=document.getElementById('pt-tr-all-btn');
  if(ab)ab.addEventListener('click',function(){doTransfer({all:true})});
}

/* ─── دعوت و تبلیغ — لینک اختصاصی + متن آماده + اشتراک‌گذاری تلگرام، معادل
   cb_partner_ref_link در بات. تنها راه دسترسی به لینک دعوت در مینی‌اپ همینه —
   ردیف مستقل «دعوت دوستان» طبق دستور مالک پروژه از تب حساب حذف شده. ─── */
function _ptInvite(){
  _ptTitle('دعوت و تبلیغ');
  var b=_accBody();if(!b)return;
  b.innerHTML=_ptBackHtml()+skel(2);_ptWireBack();
  window._slApi('/me/invite',true).then(function(d){
    var b2=_accBody();if(!b2)return;
    var link=d.referral_link||'';
    var promo=d.promo_text||'';
    var shareUrl='https://t.me/share/url?url='+encodeURIComponent(link)+'&text='+encodeURIComponent(promo);
    b2.innerHTML=_ptBackHtml()+
      '<div style="text-align:center;padding:8px 0 4px"><span style="font-size:40px">🔗</span>'+
      '<p style="margin:8px 0 0;font-size:13px;color:var(--mu)">لینک اختصاصی خودتون رو با مشتری‌ها و دوست‌ها به اشتراک بذارید</p></div>'+
      '<div class="sl-pay-box" style="direction:ltr;text-align:center;word-break:break-all;font-size:12px">'+window._slEsc(link)+'</div>'+
      '<div class="sl-checkout-btns"><button class="sl-checkout-btn sl-checkout-btn-wallet" id="pt-inv-copy-btn">📋 کپی لینک</button>'+
      '<a class="sl-checkout-btn sl-checkout-btn-combined" style="text-decoration:none;box-sizing:border-box" href="'+esc(shareUrl)+'" target="_blank" rel="noopener">📤 ارسال به دوستان و گروه‌ها</a></div>'+
      '<div class="sl-checkout-sec">📣 متن آماده تبلیغ</div>'+
      '<div class="sl-pay-box" style="white-space:pre-wrap;font-size:12.5px;line-height:1.9">'+nl2br(promo)+'</div>'+
      '<div class="sl-checkout-wallet" style="margin-top:14px"><div class="sl-checkout-wallet-info">جمع درآمد از دعوت</div>'+
      '<div class="sl-checkout-wallet-bal">'+window._slFmt((d.stats&&d.stats.earned)||0)+' تومان</div></div>';
    _ptWireBack();
    var cb=document.getElementById('pt-inv-copy-btn');
    if(cb)cb.addEventListener('click',function(){
      var done=function(){cb.textContent='✅ کپی شد';setTimeout(function(){cb.textContent='📋 کپی لینک'},1500)};
      if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(link).then(done).catch(done)}
      else{done()}
    });
  }).catch(function(){var b2=_accBody();if(b2){b2.innerHTML=_ptBackHtml()+err('خطا در دریافت لینک دعوت');_ptWireBack()}});
}

/* ─── درخواست تسویهٔ موجودی همکاری ─── */
function openPayoutRequest(){
  _accPopup('درخواست تسویه',_ptBackHtml('بازگشت به کیف‌پول')+skel(2));
  _ptWireBack(_ptWallet);
  window._slApi('/partner/payout-info',true).then(function(d){
    if(!d.is_active){var b=_accBody();if(b){b.innerHTML=_ptBackHtml('بازگشت به کیف‌پول')+'<div class="sl-empty"><span class="sl-empty-e">⏸</span>تسویه در حال حاضر غیرفعاله.<br><span style="font-size:12px">بعداً دوباره امتحان کنید.</span></div>';_ptWireBack(_ptWallet)}return}
    if(!d.bank_info){renderPayoutBankForm(d);return}
    renderPayoutAmountForm(d);
  }).catch(function(){var b=_accBody();if(b){b.innerHTML=_ptBackHtml('بازگشت به کیف‌پول')+err('خطا در دریافت اطلاعات تسویه');_ptWireBack(_ptWallet)}});
}
window.openPayoutRequest=openPayoutRequest;

function renderPayoutBankForm(info){
  var b=_accBody();if(!b)return;
  b.innerHTML=_ptBackHtml('بازگشت به کیف‌پول')+
    '<div class="sl-checkout-note" style="margin-bottom:10px">برای درخواست تسویه، اول اطلاعات حساب بانکی خودتون رو ثبت کنید.</div>'+
    '<div class="sl-checkout-sec">نام صاحب حساب</div>'+
    '<div class="sl-pay-box"><input type="text" id="pb-name" class="sl-amount-input" placeholder="مطابق کارت بانکی" autocomplete="off"></div>'+
    '<div class="sl-checkout-sec">شمارهٔ کارت</div>'+
    '<div class="sl-pay-box"><input type="tel" inputmode="numeric" id="pb-card" class="sl-amount-input" dir="ltr" placeholder="۱۶ رقم" autocomplete="off"></div>'+
    '<div class="sl-checkout-sec">شبا (اختیاری)</div>'+
    '<div class="sl-pay-box"><input type="text" id="pb-iban" class="sl-amount-input" dir="ltr" placeholder="IR..." autocomplete="off"></div>'+
    '<div class="sl-checkout-btns"><button class="sl-checkout-btn sl-checkout-btn-combined" id="pb-save-btn">ثبت و ادامه</button></div>';
  _ptWireBack(_ptWallet);
  var sb=document.getElementById('pb-save-btn');
  if(sb)sb.addEventListener('click',function(){
    var full_name=(document.getElementById('pb-name').value||'').trim();
    var card_number=(document.getElementById('pb-card').value||'').replace(/[^0-9]/g,'');
    var iban=(document.getElementById('pb-iban').value||'').trim();
    if(full_name.length<3){window._slApp.dialog.alert('نام صاحب حساب رو کامل وارد کنید','خطا');return}
    if(card_number.length<16){window._slApp.dialog.alert('شمارهٔ کارت باید ۱۶ رقم باشه','خطا');return}
    sb.disabled=true;sb.textContent='در حال ثبت…';
    fetch('https://panel.stland.ir/api/v1/partner/bank-info',{
      method:'POST',headers:{'Content-Type':'application/json','X-Telegram-Init-Data':window._slInitData},
      body:JSON.stringify({full_name:full_name,card_number:card_number,iban:iban})
    }).then(function(r){return r.json().then(function(dd){return {status:r.status,d:dd}})}).then(function(res){
      if(res.status!==200||!res.d.ok){
        window._slApp.dialog.alert((res.d&&res.d.detail)||'خطا در ثبت اطلاعات','خطا');
        sb.disabled=false;sb.textContent='ثبت و ادامه';return;
      }
      openPayoutRequest();
    }).catch(function(){window._slApp.dialog.alert('خطای شبکه','خطا');sb.disabled=false;sb.textContent='ثبت و ادامه'});
  });
}

function renderPayoutAmountForm(info){
  var b=_accBody();if(!b)return;
  var bank=info.bank_info||{};
  var hint='موجودی: '+fmt(info.balance||0)+' تومان';
  if(info.min_amount)hint+=' · حداقل: '+fmt(info.min_amount)+' تومان';
  b.innerHTML=_ptBackHtml('بازگشت به کیف‌پول')+
    '<div class="sl-checkout-wallet"><div class="sl-checkout-wallet-info">حساب مقصد</div>'+
    '<div style="font-size:13px;font-weight:700;margin-top:2px">'+esc(bank.full_name||'')+'</div>'+
    '<div style="font-size:12px;color:var(--mu);direction:ltr;text-align:right;margin-top:2px">'+esc(bank.card_number||'')+'</div></div>'+
    '<div class="sl-checkout-sec">مبلغ درخواست تسویه (تومان)</div>'+
    '<div class="sl-pay-box"><input type="tel" inputmode="numeric" id="po-amount" class="sl-amount-input" placeholder="'+esc(hint)+'" autocomplete="off"></div>'+
    '<div class="sl-checkout-btns"><button class="sl-checkout-btn sl-checkout-btn-combined" id="po-submit-btn">ثبت درخواست</button></div>';
  _ptWireBack(_ptWallet);
  var inp=document.getElementById('po-amount'),sb=document.getElementById('po-submit-btn');
  if(sb)sb.addEventListener('click',function(){
    var amount=parseInt((inp.value||'').replace(/[^0-9]/g,''),10);
    if(!amount||amount<=0){window._slApp.dialog.alert('مبلغ رو وارد کنید','خطا');return}
    sb.disabled=true;sb.textContent='در حال ثبت…';
    fetch('https://panel.stland.ir/api/v1/partner/payout',{
      method:'POST',headers:{'Content-Type':'application/json','X-Telegram-Init-Data':window._slInitData},
      body:JSON.stringify({amount:amount})
    }).then(function(r){return r.json().then(function(dd){return {status:r.status,d:dd}})}).then(function(res){
      if(res.status!==200||!res.d.ok){
        window._slApp.dialog.alert((res.d&&res.d.detail)||'خطا در ثبت درخواست','خطا');
        sb.disabled=false;sb.textContent='ثبت درخواست';return;
      }
      var b2=_accBody();if(!b2)return;
      b2.innerHTML=_ptBackHtml('بازگشت به کیف‌پول')+'<div class="sl-checkout-result"><div class="sl-checkout-result-e">✅</div>'+
        '<div class="sl-checkout-result-t">ثبت شد</div>'+
        '<div class="sl-checkout-result-s">درخواست تسویهٔ شما ثبت شد و توسط تیم مالی بررسی می‌شه.</div>'+
        '<button class="sl-checkout-close-btn" id="po-done-btn">باشه</button></div>';
      _ptWireBack(_ptWallet);
      var db_=document.getElementById('po-done-btn');
      if(db_)db_.addEventListener('click',function(){_ptWallet()});
    }).catch(function(){window._slApp.dialog.alert('خطای شبکه','خطا');sb.disabled=false;sb.textContent='ثبت درخواست'});
  });
}

/* ─── درخواست همکاری — فعلاً فقط از ربات (ویزارد کامل اونجاست)، اپ فقط ارجاع می‌ده ─── */
function renderPartnerApplyForm(b){
  b.innerHTML='<div class="sl-login"><div class="sl-login-e">🤝</div>'+
    '<div class="sl-login-t">ثبت‌نام همکاری</div>'+
    '<div class="sl-login-s">برای شروع همکاری، وارد ربات تلگرام بشید<br>و ویزارد ثبت‌نام رو کامل کنید.</div>'+
    '<a class="sl-login-btn" href="https://t.me/'+botUser+'?start=partner" target="_blank">🤖 ثبت‌نام در ربات</a></div>';
}

/* ─── پشتیبانی — همون منطق ticket_v2 ربات (سقف ۳ پیام تا پاسخ ادمین) ─── */
var _spPoll=null,_spLastCount=-1,_spPendingFile=null;
function openSupport(){
  _accPopup('پشتیبانی',skel(2));
  _spLastCount=-1;_spPendingFile=null;
  loadSupportTicket();
  if(_spPoll)clearInterval(_spPoll);
  _spPoll=setInterval(function(){
    var pop=document.getElementById('post-popup');
    if(!pop||!pop.classList.contains('modal-in')){clearInterval(_spPoll);_spPoll=null;return}
    var chat=document.getElementById('sp-chat');
    if(!chat)return; // فقط وقتی داخل صفحهٔ چت هستیم poll کن
    var inp=document.getElementById('sp-input');
    // وقتی کاربر داره تایپ می‌کنه، رندر نکن — وگرنه input عوض می‌شه، متن تایپ‌شده و
    // فوکوس/کیبورد از دست می‌ره (این دقیقاً همون باگی بود که گزارش شد)
    if(inp&&document.activeElement===inp)return;
    loadSupportTicket(true);
  },5000);
}
window.openSupport=openSupport;

function loadSupportTicket(silent){
  var b=_accBody();
  fetch('https://panel.stland.ir/api/v1/support/ticket',{
    headers:{'X-Telegram-Init-Data':window._slInitData}
  }).then(function(r){return r.json()}).then(function(d){
    if(!d||!d.ok)throw 0;
    if(d.ticket){
      var msgs=d.messages||[];
      // در حالت poll ساکت، فقط وقتی واقعاً چیزی عوض شده رندر کن (نه هر ۵ ثانیه بی‌دلیل)
      if(silent&&msgs.length===_spLastCount)return;
      _spLastCount=msgs.length;
      renderSupportChat(d.ticket,msgs);
    }else if(!silent)renderSupportStart();
  }).catch(function(){if(!silent&&b)b.innerHTML=err('خطا در اتصال به پشتیبانی')});
}

function renderSupportStart(){
  var b=_accBody();if(!b)return;
  b.innerHTML='<div class="sl-empty"><span class="sl-empty-e">💬</span>پشتیبانی آنلاین<br>'+
    '<span style="font-size:12px">پیام‌تون رو بفرستید، پشتیبانی در اولین فرصت پاسخ می‌ده.</span></div>'+
    '<div class="sl-checkout-btns"><button class="sl-checkout-btn sl-checkout-btn-combined" id="sp-start-btn">شروع گفتگو</button></div>';
  var sb=document.getElementById('sp-start-btn');
  if(sb)sb.addEventListener('click',function(){
    sb.disabled=true;sb.textContent='در حال شروع…';
    fetch('https://panel.stland.ir/api/v1/support/ticket',{
      method:'POST',headers:{'X-Telegram-Init-Data':window._slInitData}
    }).then(function(r){return r.json()}).then(function(d){
      if(!d||!d.ok)throw 0;
      _spLastCount=0;
      renderSupportChat(d.ticket,[]);
    }).catch(function(){window._slApp.dialog.alert('خطای شبکه','خطا');sb.disabled=false;sb.textContent='شروع گفتگو'});
  });
}

function renderSupportChat(ticket,messages){
  var b=_accBody();if(!b)return;
  try{localStorage.setItem('sl_sp_seen_'+ticket.id,String(messages.length))}catch(e){}
  _clearMeBadge();
  var remaining=Math.max(0,3-(ticket.user_msg_count||0));
  var closed=ticket.status==='closed';
  b.innerHTML='<div class="sl-sp-chat" id="sp-chat">'+
    (messages.length?messages.map(function(m){
      var mine=m.sender==='user';
      var img=m.image_url?'<img src="'+esc(m.image_url)+'" class="sl-sp-img" alt="">':'';
      var txt=m.text?'<div>'+esc(m.text)+'</div>':'';
      return '<div class="sl-sp-msg '+(mine?'sl-sp-mine':'sl-sp-theirs')+'">'+img+txt+'</div>';
    }).join(''):'<div class="sl-sp-hint">پیام خودتون رو بنویسید</div>')+
    '</div>'+
    (closed?
      '<div class="sl-checkout-note">این گفتگو بسته شده. برای گفتگوی جدید دوباره وارد این صفحه بشید.</div>'+
      '<div class="sl-checkout-btns"><button class="sl-checkout-btn sl-checkout-btn-gateway" id="sp-new-btn">شروع گفتگوی جدید</button></div>'
      :
      (remaining<=0?
        '<div class="sl-checkout-note">⏳ در انتظار پاسخ پشتیبانی — بعد از پاسخ می‌تونید ادامه بدید.</div>'
        :
        '<div class="sl-sp-attach" id="sp-attach-preview" hidden></div>'+
        '<div class="sl-sp-input-row">'+
        '<label class="sl-sp-attach-btn" id="sp-attach-label">📎<input type="file" accept="image/*" id="sp-photo" hidden></label>'+
        '<input type="text" id="sp-input" class="sl-sp-input" placeholder="پیام خود را بنویسید…" autocomplete="off">'+
        '<button class="sl-sp-send" id="sp-send-btn">ارسال</button></div>'+
        '<div class="sl-checkout-note" style="margin-top:6px">'+remaining+' پیام دیگر می‌تونید بفرستید</div>'
      )
    );
  var chatBox=document.getElementById('sp-chat');
  if(chatBox)chatBox.scrollTop=chatBox.scrollHeight;
  var nb=document.getElementById('sp-new-btn');
  if(nb)nb.addEventListener('click',renderSupportStart);

  var sendBtn=document.getElementById('sp-send-btn'),inp=document.getElementById('sp-input');
  var photoInp=document.getElementById('sp-photo'),preview=document.getElementById('sp-attach-preview');
  var attachLbl=document.getElementById('sp-attach-label');
  if(photoInp)photoInp.addEventListener('change',function(){
    _spPendingFile=photoInp.files[0]||null;
    if(preview){
      preview.hidden=!_spPendingFile;
      preview.textContent=_spPendingFile?'📷 '+_spPendingFile.name+'  ':'';
      if(_spPendingFile){
        var xBtn=document.createElement('span');xBtn.textContent='✕';xBtn.className='sl-sp-attach-x';
        xBtn.addEventListener('click',function(){_spPendingFile=null;photoInp.value='';preview.hidden=true});
        preview.appendChild(xBtn);
      }
    }
  });

  var sending=false;
  function setSending(on,label){
    sending=on;
    if(sendBtn){sendBtn.disabled=on;sendBtn.textContent=on?(label||'در حال ارسال…'):'ارسال'}
    if(inp)inp.disabled=on;
    if(photoInp)photoInp.disabled=on;
    if(attachLbl)attachLbl.classList.toggle('sl-sp-disabled',on);
  }

  function send(){
    if(sending)return; // جلوگیری از دبل‌کلیک حین ارسال
    var text=(inp.value||'').trim();
    if(!text&&!_spPendingFile)return;
    var hadPhoto=!!_spPendingFile;
    setSending(true,hadPhoto?'در حال آپلود عکس…':'در حال ارسال…');
    var fd=new FormData();
    fd.append('text',text);
    if(_spPendingFile)fd.append('photo',_spPendingFile);
    fetch('https://panel.stland.ir/api/v1/support/message',{
      method:'POST',headers:{'X-Telegram-Init-Data':window._slInitData},body:fd
    }).then(function(r){return r.json().then(function(d){return {status:r.status,d:d}})}).then(function(res){
      if(res.status!==200||!res.d.ok){
        window._slApp.dialog.alert((res.d&&(res.d.detail||res.d.error))||'خطا در ارسال پیام — دوباره تلاش کنید','خطا');
        setSending(false);return;
      }
      var newMsg={sender:'user',text:text};
      if(hadPhoto)newMsg.image_url=URL.createObjectURL(_spPendingFile);
      messages.push(newMsg);
      _spPendingFile=null;_spLastCount=messages.length;
      renderSupportChat(res.d.ticket,messages);
    }).catch(function(){
      window._slApp.dialog.alert('خطای شبکه — اتصال اینترنت را بررسی و دوباره تلاش کنید','خطا');
      setSending(false);
    });
  }
  if(sendBtn)sendBtn.addEventListener('click',send);
  if(inp)inp.addEventListener('keydown',function(e){if(e.key==='Enter')send()});
}

/* ═══ جستجو — درون همون فرم، بدون دیالوگ/تعویض صفحه ═══ */
(function(){
  var input=document.getElementById('search-input');
  var clearBtn=document.getElementById('search-clear');
  var panel=document.getElementById('search-results');
  var bar=document.getElementById('search-bar');
  var homeTab=document.getElementById('tab-home');
  if(!input||!panel||!bar||!homeTab)return;
  var timer=null,seq=0;

  function renderProd(p){
    var f=p.flash_active;
    return '<div class="sl-prod" data-pid="'+p.id+'"><div class="sl-pic">'+prodImgHtml(p)+'</div>'+
      '<div class="sl-pinfo"><div class="sl-pt">'+esc(p.title)+'</div></div>'+
      '<div class="sl-price">'+fmt(p.effective_price)+' <small>تومان</small></div></div>';
  }

  function positionPanel(){
    // مختصات نسبت به کل محتوای قابل‌اسکرول #tab-home حساب می‌شه (نه viewport)
    // تا پنل مثل بقیهٔ محتوا طبیعی با اسکرول بالا/پایین بره
    var barRect=bar.getBoundingClientRect();
    var containerRect=homeTab.getBoundingClientRect();
    panel.style.top=(barRect.bottom-containerRect.top+homeTab.scrollTop+8)+'px';
    panel.style.left=(barRect.left-containerRect.left)+'px';
    panel.style.right=(containerRect.right-barRect.right)+'px';
  }
  function showPanel(html){positionPanel();panel.innerHTML=html;panel.hidden=false}
  function hidePanel(){panel.hidden=true;panel.innerHTML=''}

  function runSearch(q){
    var mySeq=++seq;
    showPanel('<div class="sl-search-loading">در حال جستجو…</div>');
    api('/products?limit=20&q='+encodeURIComponent(q)).then(function(d){
      if(mySeq!==seq)return; // پاسخ دیرهنگام مربوط به کوئری قدیمی‌تر — نادیده گرفته می‌شه
      var items=(d&&d.products)||[];
      if(!items.length){showPanel('<div class="sl-search-empty">😕 نتیجه‌ای برای «'+esc(q)+'» یافت نشد</div>');return}
      showPanel(items.map(renderProd).join(''));
    }).catch(function(){
      if(mySeq!==seq)return;
      showPanel('<div class="sl-search-empty">📡 خطا در جستجو — دوباره تلاش کنید</div>');
    });
  }

  input.addEventListener('input',function(){
    var q=input.value.trim();
    clearBtn.hidden=!q;
    if(timer)clearTimeout(timer);
    if(!q){hidePanel();return}
    timer=setTimeout(function(){runSearch(q)},350);
  });
  input.addEventListener('focus',function(){if(input.value.trim())panel.hidden=false});
  input.addEventListener('blur',function(){
    setTimeout(function(){panel.hidden=true},200); // تأخیر تا تپ روی نتیجه قبلش ثبت بشه
  });
  clearBtn.addEventListener('click',function(){
    input.value='';clearBtn.hidden=true;hidePanel();input.focus();
  });
})();

/* ═══ رویدادها ═══ */
app.on('tabShow',function(el){var id=el&&el.id;
  if(id==='tab-home')loadHome();if(id==='tab-shop')loadShop();
  if(id==='tab-learn'){loadTutCats();if(!_tutLoaded){_tutLoaded=true;loadTuts(true)}}
  if(id==='tab-news')loadNews();
  if(id==='tab-me')loadMe();
  // «آموزش» حالا زیرمجموعهٔ تب «ابزار مفید»ه، نه یه تب مستقل توی نوار پایین —
  // پس وقتی از داخل کارت آموزش در همون تب (نه لینک نوار پایین) واردش می‌شیم،
  // باید دستی هایلایت نوار پایین رو روی «ابزار مفید» نگه داریم. setTimeout چون
  // F7 خودش بعد از رویداد tabShow هم کلاس‌های tab-link-active رو آپدیت می‌کنه —
  // باید بعد از اون تمومشدن اجرا بشیم، نه همزمانش.
  if(id==='tab-tools'||id==='tab-learn'){
    setTimeout(function(){
      var toolsLink=document.querySelector('.tabbar .tab-link[href="#tab-tools"]');
      if(!toolsLink)return;
      document.querySelectorAll('.tabbar .tab-link').forEach(function(l){l.classList.remove('tab-link-active')});
      toolsLink.classList.add('tab-link-active');
    },0);
  }
});
app.on('ptrRefresh',function(el,done){var t=document.querySelector('.tab.tab-active'),id=t&&t.id;
  if(id==='tab-home'){_h=0;cats=[];prods=[];loadHome()}if(id==='tab-shop'){_s=0;prods=[];loadShop()}
  if(id==='tab-learn')loadTuts(true);if(id==='tab-news')loadNews(true);if(id==='tab-me'){_m=0;loadMe()}
  setTimeout(done,600);
});
document.addEventListener('click',function(e){
  var p=e.target.closest('[data-pid]');if(p){openP(p.dataset.pid);return}
  var c=e.target.closest('[data-cid]');if(c){openC(c.dataset.cid);return}
  var tu=e.target.closest('[data-tid]');if(tu){openTutorial(tu.dataset.tid);return}
  var co=e.target.closest('[data-checkout]');if(co){openCheckout(co.dataset.checkout);return}
  var tb=e.target.closest('[data-tab]');if(tb){e.preventDefault();var l=document.querySelector('.tab-link[href="#'+tb.dataset.tab+'"]');if(l)l.click()}
});

/* ═══ Mira-style snap navbar ═══ */
(function(){
  var nav=document.getElementById('sl-nav');
  var navTitle=document.getElementById('sl-nav-title');
  var hero=document.getElementById('sl-hero');
  var homeTab=document.getElementById('tab-home');
  var meTab=document.getElementById('tab-me');
  if(!nav||!hero||!homeTab)return;
  // تب‌هایی که مثل خانه یک هیرو/کارت‌رنگی دقیقاً زیر نوار شناور دارن (بدون padding-top روی
  // خودِ تب) — رنگ هدر بومی تلگرام و شفافیت نوار برای همهٔ این‌ها یکسان محاسبه می‌شه، دقیقاً
  // همون مکانیزم خانه؛ تب حساب (sl-me-c) هم به همین لیست اضافه شد
  var HERO_TABS={'tab-home':homeTab};
  if(meTab)HERO_TABS['tab-me']=meTab;
  var _dk=window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches;
  var HERO_TOP=_dk?'#2838D8':'#4255FF';
  var BAR_SOLID=_dk?'#1C1C1E':'#FFFFFF';
  var PAGE_BG=_dk?'#000000':'#F2F2F7';
  var SNAP_PX=36;
  var _lastHex='';
  function setTgHeader(hex){if(hex===_lastHex)return;_lastHex=hex;try{if(tg&&tg.setHeaderColor)tg.setHeaderColor(hex)}catch(e){}}
  if(inTG){try{tg.setBackgroundColor(PAGE_BG)}catch(e){}setTgHeader(HERO_TOP)}
  var ticking=false;
  function onScroll(){
    if(ticking)return;ticking=true;
    requestAnimationFrame(function(){
      ticking=false;
      var activeTab=document.querySelector('.tab.tab-active');
      var heroEl=activeTab&&HERO_TABS[activeTab.id];
      if(!heroEl){
        nav.classList.remove('sl-nav--solid');
        setTgHeader(PAGE_BG);
        return;
      }
      // همیشه دوباره محاسبه/ست می‌شه (نه فقط وقتی حالت عوض شده) — چون setTgHeader خودش
      // با _lastHex از ارسال تکراری جلوگیری می‌کنه؛ قبلاً یه مقایسهٔ state اینجا بود که باعث
      // می‌شد برگشتن به خانه (بدون اسکرول) رنگ هدر بومی تلگرام رو دوباره نفرسته و همون‌جوری
      // که تب قبلی گذاشته بود (سفید/PAGE_BG) بمونه
      var solid=heroEl.scrollTop>SNAP_PX;
      if(solid){nav.classList.add('sl-nav--solid');setTgHeader(BAR_SOLID)}
      else{nav.classList.remove('sl-nav--solid');setTgHeader(HERO_TOP)}
    });
  }
  function onTabShow(){
    // دو-فریمی: صبر می‌کنیم لایوت/اسکرول واقعاً settle بشه، نه یه تایمر ثابت که ممکنه
    // زودتر یا دیرتر از انیمیشن واقعی سوییچ تب اجرا بشه و رنگ نوار با محتوا هم‌خوان نباشه
    requestAnimationFrame(function(){requestAnimationFrame(onScroll)});
    setTimeout(onScroll,350); // safety-net برای انیمیشن‌های کندتر
  }
  homeTab.addEventListener('scroll',onScroll,{passive:true});
  if(meTab)meTab.addEventListener('scroll',onScroll,{passive:true});
  app.on('tabShow',onTabShow);
  onScroll();
})();

if('serviceWorker' in navigator)window.addEventListener('load',function(){navigator.serviceWorker.register('sw.js').catch(function(){})});
var sa=window.matchMedia('(display-mode:standalone)').matches||window.navigator.standalone===true;
var di=false;try{di=sessionStorage.getItem('sl-hint-off')==='1'}catch(e){}
if(!inTG&&!sa&&!di){
  var h=document.getElementById('install-hint'),ib=document.getElementById('install-btn'),tx=document.getElementById('install-hint-text'),dp2=null;
  window.addEventListener('beforeinstallprompt',function(e){e.preventDefault();dp2=e;ib.style.display='';tx.textContent='با یک لمس نصب کنید'});
  ib.addEventListener('click',function(){if(!dp2)return;dp2.prompt();dp2=null;h.style.display='none'});
  if(/iphone|ipad|ipod/i.test(navigator.userAgent))tx.innerHTML='در سافاری: <b>Share</b> → <b>Add to Home Screen</b>';
  else tx.textContent='برای نصب از منوی مرورگر استفاده کنید';
  h.style.display='';
  document.getElementById('install-close').addEventListener('click',function(){h.style.display='none';try{sessionStorage.setItem('sl-hint-off','1')}catch(e){}});
}
})();

/* ═══ پاپ‌آپ خرید ═══ */
window._slCk={pid:0,prod:null,walBal:0,basePrice:0,discountCode:'',discountAmount:0};

function openCheckout(pid){
  window._slCk.pid=pid;window._slCk.discountCode='';window._slCk.discountAmount=0;
  window._slCk.termsAgreed=false;window._slCk.termsText='';
  var b=document.getElementById('checkout-body');
  b.innerHTML='<div class="sl-skel" style="margin:20px"><div class="b w60"></div><div class="b w90"></div><div class="b w40"></div></div>';
  window._slApp.popup.open('#checkout-popup');

  Promise.all([
    window._slApi('/products/'+pid,true),
    window._slApi('/me/wallet',true)
  ]).then(function(res){
    window._slCk.prod=res[0].product||{};
    window._slCk.walBal=res[1].balance||0;
    // منطق قیمت باید دقیقاً با صفحهٔ محصول/بات هماهنگ باشه — اگه قیمت همکاری
    // فعاله، همون رقم پایهٔ محاسبهٔ چک‌اوت می‌شه (سرور هم مستقل همین رو دوباره
    // حساب می‌کنه، اینجا فقط برای نمایش صحیحه)
    window._slCk.basePrice=window._slCk.prod.show_partner_price?window._slCk.prod.partner_price:
      (window._slCk.prod.effective_price||window._slCk.prod.price||0);
    if(window._slCk.prod.require_terms){
      window._slApi('/purchase-terms').then(function(d){
        window._slCk.termsText=(d&&d.text)||'';
        _renderCheckoutBody();
      }).catch(function(){_renderCheckoutBody()});
    }else{
      _renderCheckoutBody();
    }
  }).catch(function(){
    b.innerHTML='<div class="sl-empty"><span class="sl-empty-e">📡</span>خطا در دریافت اطلاعات</div>';
  });
}

window.openCheckout=openCheckout;

function _renderCheckoutBody(){
  var b=document.getElementById('checkout-body');
  var p=window._slCk.prod,walBal=window._slCk.walBal;
  var price=Math.max(0,window._slCk.basePrice-window._slCk.discountAmount);
  var canWallet=walBal>=price;
  var canCombined=walBal>0&&walBal<price;
  var emoji=p._e||'📦';

  var outOfStock=Number(p.stock||0)<=0;
  var needsTerms=!!p.require_terms;
  var termsDis=(needsTerms&&!window._slCk.termsAgreed)?' disabled':'';
  var btns='';
  if(outOfStock){
    if(p.notify_on_restock){
      btns='<button class="sl-checkout-btn sl-checkout-btn-wallet" onclick="_notifyStock('+p.id+')" id="notify-stock-btn">🔔 موجود شد، اطلاع بده</button>';
    }else{
      btns='<div class="sl-checkout-note" style="text-align:center;padding:12px;color:var(--mu)">❌ موجودی این محصول در حال حاضر به پایان رسیده است.</div>';
    }
  }else if(price<=0){
    btns='<button class="sl-checkout-btn sl-checkout-btn-wallet"'+termsDis+' onclick="_doPay(\'wallet\')">✅ دریافت رایگان</button>';
  }else{
    if(canWallet){
      btns+='<button class="sl-checkout-btn sl-checkout-btn-wallet"'+termsDis+' onclick="_doPay(\'wallet\')">👛 پرداخت از کیف‌پول ('+window._slFmt(price)+' تومان)</button>';
    }
    if(canCombined){
      var gw=price-walBal;
      btns+='<button class="sl-checkout-btn sl-checkout-btn-combined"'+termsDis+' onclick="_doPay(\'combined\')">'+
        '💳 پرداخت ترکیبی (کیف‌پول '+window._slFmt(walBal)+' + درگاه '+window._slFmt(gw)+' تومان)</button>';
    }
    btns+='<button class="sl-checkout-btn sl-checkout-btn-gateway"'+termsDis+' onclick="_doPay(\'gateway\')">🌐 پرداخت کامل از درگاه ('+window._slFmt(price)+' تومان)</button>';
  }
  var termsBox=(needsTerms&&!outOfStock)?
    '<div class="sl-terms-box">'+
      '<div class="sl-terms-text">'+window._slEsc(window._slCk.termsText||'با ادامهٔ خرید، قوانین و مقررات فروشگاه را می‌پذیرید.').replace(/\n/g,'<br>')+'</div>'+
      '<label class="sl-terms-chk"><input type="checkbox" id="terms-agree-chk"'+(window._slCk.termsAgreed?' checked':'')+'><span>قوانین بالا را مطالعه کردم و می‌پذیرم</span></label>'+
    '</div>':'';

  var partnerTag=(p.show_partner_price&&!window._slCk.discountCode)?' <span class="sl-partner-badge">🤝 قیمت همکاری</span>':'';
  var priceLine=window._slCk.discountAmount>0?
    '<div class="sl-checkout-price"><s style="color:var(--mu)">'+window._slFmt(window._slCk.basePrice)+'</s> <b>'+window._slFmt(price)+' تومان</b></div>':
    '<div class="sl-checkout-price">قیمت: <b>'+window._slFmt(price)+' تومان</b></div>'+partnerTag;

  var discRow=window._slCk.discountCode?
    '<div class="sl-checkout-wallet"><div class="sl-checkout-wallet-info">🎟 کد «'+window._slEsc(window._slCk.discountCode)+'» اعمال شد <span style="color:var(--mu)">(−'+window._slFmt(window._slCk.discountAmount)+' تومان)</span></div>'+
    '<a href="#" id="discount-remove" style="color:var(--br);font-size:13px;font-weight:700">حذف</a></div>':
    '<a href="#" id="discount-apply" class="sl-checkout-wallet" style="display:flex;justify-content:space-between;align-items:center;text-decoration:none">'+
    '<span style="color:var(--mu)">🎟 کد تخفیف دارید؟</span><span style="color:var(--br);font-weight:700">وارد کنید ›</span></a>';

  // ناموجود = اصلاً وارد چرخهٔ خرید نمی‌شیم — نه کیف‌پول، نه کد تخفیف، فقط پیام/دکمهٔ اطلاع‌رسانی
  b.innerHTML=outOfStock?
    '<div class="sl-checkout-prod">'+
      '<div class="sl-checkout-emoji">'+window._slEsc(emoji)+'</div>'+
      '<div><div class="sl-checkout-title">'+window._slEsc(p.title)+'</div></div>'+
    '</div>'+
    '<div class="sl-checkout-btns" id="checkout-btns">'+btns+'</div>'
    :
    '<div class="sl-checkout-prod">'+
      '<div class="sl-checkout-emoji">'+window._slEsc(emoji)+'</div>'+
      '<div><div class="sl-checkout-title">'+window._slEsc(p.title)+'</div>'+priceLine+'</div>'+
    '</div>'+
    '<div class="sl-checkout-sec">موجودی کیف‌پول شما</div>'+
    '<div class="sl-checkout-wallet">'+
      '<div class="sl-checkout-wallet-info">کیف پول</div>'+
      '<div class="sl-checkout-wallet-bal">'+window._slFmt(walBal)+' تومان</div>'+
    '</div>'+
    '<div class="sl-checkout-sec">کد تخفیف</div>'+discRow+
    termsBox+
    '<div class="sl-checkout-sec">روش پرداخت</div>'+
    '<div class="sl-checkout-btns" id="checkout-btns">'+btns+'</div>'+
    '<div class="sl-checkout-note">بعد از تایید پرداخت، سفارش شما به‌صورت خودکار ثبت و ارسال می‌شود.<br>در پرداخت از درگاه، قبل از ورود فیلترشکن (VPN) خود را خاموش کنید.</div>';

  var da=document.getElementById('discount-apply');
  if(da)da.addEventListener('click',function(e){e.preventDefault();_applyDiscount()});
  var dr=document.getElementById('discount-remove');
  if(dr)dr.addEventListener('click',function(e){e.preventDefault();window._slCk.discountCode='';window._slCk.discountAmount=0;_renderCheckoutBody()});
  var tc=document.getElementById('terms-agree-chk');
  if(tc)tc.addEventListener('change',function(){
    window._slCk.termsAgreed=tc.checked;
    var bb=document.getElementById('checkout-btns');
    if(bb)bb.querySelectorAll('button').forEach(function(x){x.disabled=!tc.checked});
  });
}

window._notifyStock=function(pid,btnId){
  var btn=document.getElementById(btnId||'notify-stock-btn');
  if(btn){btn.disabled=true;btn.textContent='در حال ثبت…'}
  fetch('/api/v1/products/'+pid+'/notify',{method:'POST',headers:{'X-Telegram-Init-Data':window._slInitData}})
    .then(function(r){return r.json()})
    .then(function(d){
      if(btn){btn.textContent=d&&d.added===false?'✅ قبلاً ثبت شده بود':'✅ ثبت شد — به‌محض موجود شدن اطلاع می‌دیم'}
    })
    .catch(function(){if(btn){btn.disabled=false;btn.textContent='🔔 موجود شد، اطلاع بده'}});
};

window._applyDiscount=function(){
  window._slApp.dialog.prompt('کد تخفیف را وارد کنید','کد تخفیف',function(code){
    code=(code||'').trim();if(!code)return;
    fetch('https://panel.stland.ir/api/v1/discount/validate',{
      method:'POST',
      headers:{'Content-Type':'application/json','X-Telegram-Init-Data':window._slInitData},
      body:JSON.stringify({product_id:window._slCk.pid,code:code})
    }).then(function(r){return r.json()}).then(function(d){
      if(!d.ok){window._slApp.dialog.alert(d.error||'کد تخفیف نامعتبر است.','خطا');return}
      window._slCk.discountCode=code;window._slCk.discountAmount=d.discount_amount||0;
      _renderCheckoutBody();
    }).catch(function(){window._slApp.dialog.alert('خطا در بررسی کد تخفیف.','خطا')});
  });
};

window._doPay=function(method){
  var btns=document.getElementById('checkout-btns');
  if(btns) btns.querySelectorAll('button').forEach(function(x){x.disabled=true;x.textContent='⏳ در حال پردازش...'});

  fetch('https://panel.stland.ir/api/v1/checkout',{
    method:'POST',
    headers:{'Content-Type':'application/json','X-Telegram-Init-Data':window._slInitData},
    body:JSON.stringify({product_id:window._slCk.pid,payment_type:method,discount_code:window._slCk.discountCode||undefined,agreed_terms:!!window._slCk.termsAgreed})
  }).then(function(r){return r.json()}).then(function(d){
    var b=document.getElementById('checkout-body');
    if(!d.ok){
      b.innerHTML='<div class="sl-checkout-result"><div class="sl-checkout-result-e">❌</div>'+
        '<div class="sl-checkout-result-t">خطا</div>'+
        '<div class="sl-checkout-result-s">'+window._slEsc(d.detail||d.message||'خطا در پردازش')+'</div>'+
        '<button class="sl-checkout-close-btn" onclick="window._slApp.popup.close(\'#checkout-popup\')">بستن</button></div>';
      return;
    }
    if(d.method==='wallet'){
      _m=0;// ری‌فرش موجودی در تب حساب
      b.innerHTML='<div class="sl-checkout-result"><div class="sl-checkout-result-e">✅</div>'+
        '<div class="sl-checkout-result-t">خرید موفق!</div>'+
        '<div class="sl-checkout-result-s">'+window._slEsc(d.message||'سفارش شما ثبت شد.')+'<br>تحویل از طریق ربات ارسال می‌شود.</div>'+
        '<button class="sl-checkout-close-btn" onclick="window._slApp.popup.close(\'#checkout-popup\')">بستن</button></div>';
    } else if(d.redirect_url){
      // درگاه: در تلگرام با openLink باز کن
      if(window._slTg&&window._slTg.openLink){
        window._slTg.openLink(d.redirect_url);
        b.innerHTML='<div class="sl-checkout-result"><div class="sl-checkout-result-e">🌐</div>'+
          '<div class="sl-checkout-result-t">انتقال به درگاه...</div>'+
          '<div class="sl-checkout-result-s">صفحه پرداخت باز شد.<br>بعد از پرداخت به ربات برگردید.</div>'+
          '<button class="sl-checkout-close-btn" onclick="window._slApp.popup.close(\'#checkout-popup\')">بستن</button></div>';
      } else {
        window.location.href=d.redirect_url;
      }
    }
  }).catch(function(e){
    var b=document.getElementById('checkout-body');
    b.innerHTML='<div class="sl-checkout-result"><div class="sl-checkout-result-e">❌</div>'+
      '<div class="sl-checkout-result-t">خطای شبکه</div>'+
      '<div class="sl-checkout-result-s">لطفاً دوباره امتحان کنید.</div>'+
      '<button class="sl-checkout-close-btn" onclick="window._slApp.popup.close(\'#checkout-popup\')">بستن</button></div>';
  });
};

/* بعد از بازگشت از درگاه — ?payment=canceled در URL */
(function(){
  var u=new URL(window.location.href);
  if(u.searchParams.get('payment')==='canceled'){
    window._slApp.dialog.alert('پرداخت لغو شد یا ناموفق بود.','نتیجه پرداخت');
    history.replaceState({},'',u.pathname);
  }
})();
