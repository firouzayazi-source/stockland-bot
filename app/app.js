(function(){
'use strict';
var tg=window.Telegram&&window.Telegram.WebApp||null;
var inTG=!!(tg&&tg.initData);
if(inTG){document.documentElement.classList.add('in-telegram');try{tg.ready();tg.expand()}catch(e){}}
var initData=(tg&&tg.initData)||'',tgUser=(tg&&tg.initDataUnsafe&&tg.initDataUnsafe.user)||null;
var app=new Framework7({el:'#app',name:'استوک‌لند',theme:'ios',darkMode:'auto',popup:{closeByBackdropClick:true}});

function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function nl2br(s){return esc(s).replace(/\r?\n/g,'<br>')}
function fmt(n){return Number(n).toLocaleString('fa-IR')}
function skel(n){var o='';for(var i=0;i<(n||3);i++)o+='<div class="sl-skel"><div class="b w60"></div><div class="b w90"></div><div class="b w40"></div></div>';return o}
function api(p,a){var h={'Accept':'application/json'};if(a&&initData)h['X-Telegram-Init-Data']=initData;return fetch('/api/v1'+p,{headers:h}).then(function(r){if(!r.ok)throw r;return r.json()})}
function err(m){return '<div class="sl-empty"><span class="sl-empty-e">📡</span>'+esc(m||'خطا')+'</div>'}

var botUser='stock_land_ir';
api('/bot-info').then(function(d){if(d&&d.username)botUser=d.username}).catch(function(){});
try{document.getElementById('today-date').textContent=new Intl.DateTimeFormat('fa-IR-u-ca-persian',{weekday:'long',day:'numeric',month:'long'}).format(new Date())}catch(e){}

/* ── دسته‌بندی دایره‌ای ── */
var cats=[],prods=[];
function renderCircles(el,withAll){
  var items=withAll?[{id:0,name:'همه',emoji:'🏪',slug:''}].concat(cats):cats;
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

  // اخبار
  nr.innerHTML=skel(1);
  // آخرین آموزش
  loadLearnCard();

  var colors=['linear-gradient(120deg,#123,#0A63FF)','linear-gradient(120deg,#1B2B1B,#22C55E)',
    'linear-gradient(120deg,#2B1B2B,#A855F7)','linear-gradient(120deg,#2B1B1B,#EF4444)',
    'linear-gradient(120deg,#1B2B2B,#06B6D4)','linear-gradient(120deg,#2B2B1B,#F59E0B)'];
  api('/content?kind=news&limit=6').then(function(d){
    var it=(d&&d.items)||[];
    var ns=document.getElementById('news-sec');
    if(!it.length){nr.innerHTML='';if(ns)ns.style.display='none';return}
    if(ns)ns.style.display='';
    nr.innerHTML=it.map(function(p,i){
      return '<div class="sl-mini" data-cid="'+p.id+'"><div class="sl-mini-cv" style="background:'+colors[i%colors.length]+'">'+
        (p.image_url?'<img src="'+esc(p.image_url)+'" alt="">':'📰')+'</div>'+
        '<div class="sl-mini-b"><div class="sl-mini-t">'+esc(p.title)+'</div><div class="sl-mini-m">'+esc(p.created_at)+'</div></div></div>';
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
      '<div class="sl-feat-img">'+(p._e||'📦')+
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
  var kinds=['tutorial','news','feature'];
  var idx=0;
  function tryNext(){
    if(idx>=kinds.length){lc.style.display='none';if(ls)ls.style.display='none';return}
    api('/content?kind='+kinds[idx]+'&limit=1').then(function(d){
      var it=(d&&d.items&&d.items[0]);
      if(!it){idx++;tryNext();return}
      var labels={tutorial:'📚 آموزش',news:'📰 خبر',feature:'✨ امکانات'};
      lc.innerHTML='<div class="sl-learn-card" data-cid="'+it.id+'">'+
        '<div class="sl-learn-img">'+(it.image_url?'<img src="'+esc(it.image_url)+'" alt="">':'📚')+'</div>'+
        '<div class="sl-learn-body">'+
          '<div class="sl-learn-tag">'+(labels[kinds[idx]]||'آموزش')+'</div>'+
          '<div class="sl-learn-title">'+esc(it.title)+'</div>'+
          '<div class="sl-learn-meta"><span>'+esc(it.created_at||'')+'</span></div>'+
        '</div></div>';
    }).catch(function(){idx++;tryNext();});
    idx++;
  }
  tryNext();
}
window.loadLearnCard=loadLearnCard;

loadHome();

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
    return '<div class="sl-prod" data-pid="'+p.id+'"><div class="sl-pic">'+(p._e||'📦')+'</div>'+
      '<div class="sl-pinfo"><div class="sl-pt">'+esc(p.title)+'</div>'+
      '<div class="sl-pg">'+esc(p._c||'')+(p._s?' · '+esc(p._s):'')+'</div>'+
      '<div class="sl-pprice-row">'+(f?'<span class="sl-old">'+fmt(p.price)+'</span>':'')+
      '<span class="sl-price">'+fmt(p.effective_price)+' <small>تومان</small></span></div>'+
      (f?'<div class="sl-flash">⚡️ فروش فوری</div>':'')+
      '<span class="sl-buy">مشاهده و خرید</span></div></div>';
  }).join('');
}

// کلیک دایره فروشگاه
document.getElementById('shop-cats').addEventListener('click',function(e){
  var c=e.target.closest('.sl-cat-c');if(!c)return;
  document.querySelectorAll('#shop-cats .sl-cat-c').forEach(function(x){x.classList.remove('on')});
  c.classList.add('on');
  var n=c.dataset.name;renderP(n==='همه'?'':n);
});

/* ═══ پاپ‌آپ محصول ═══ */
function openP(pid){
  var t=document.getElementById('pp-title'),b=document.getElementById('pp-body');
  t.textContent='…';b.innerHTML=skel(2);app.popup.open('#prod-popup');
  api('/products/'+pid).then(function(d){
    var p=d.product||{};t.textContent=p.title||'';
    var f=p.flash_active,e=p.effective_price,bs=p.price,hs=p.stock!=null,ok=p.stock>0;
    b.innerHTML='<div class="sl-pp-hero"><div class="sl-pp-emoji">'+(p._e||'📦')+'</div>'+
      '<div class="sl-pp-title">'+esc(p.title)+'</div>'+
      (f?'<div class="sl-pp-flash"><span class="old">'+fmt(bs)+' تومان</span> <span class="tag">⚡️ فروش فوری</span></div>':'')+
      '<div class="sl-pp-price">'+fmt(e)+' <small>تومان</small></div></div>'+
      (hs?'<div class="sl-pp-stock">'+(ok?'✅ موجود — '+p.stock+' عدد':'❌ ناموجود')+'</div>':'')+
      '<div class="sl-pp-divider"></div>'+
      (p.description?'<div class="sl-pp-desc">'+nl2br(p.description)+'</div>':'')+
      (initData&&ok!==false?
        '<button class="sl-pp-btn" id="sl-buy-'+p.id+'">🛒 خرید از اپ</button>':
        '<a class="sl-pp-btn'+(hs&&!ok?' sl-pp-btn-off':'')+'" href="https://t.me/'+botUser+'?start=buy_'+p.id+'" target="_blank">'+
        (hs&&!ok?'🔔 اطلاع‌رسانی موجود شدن':'🛒 خرید از ربات')+'</a>');
    setTimeout(function(){
      var bn=document.getElementById('sl-buy-'+p.id);
      if(!bn)return;
      bn.addEventListener('click',function(){
        app.popup.close('#prod-popup');
        setTimeout(function(){openCheckout(p.id)},350);
      });
    },150);
  }).catch(function(){b.innerHTML=err('خطا');});
}

/* ═══ آموزش ═══ */
var _lk={},_lc='tutorial';
function loadL(kind){_lc=kind;if(_lk[kind])return;_lk[kind]=1;
  var box=document.getElementById('learn-list');box.innerHTML=skel(2);
  var colors=['linear-gradient(120deg,#101826,#7C3AED)','linear-gradient(120deg,#0F172A,#0A63FF)',
    'linear-gradient(120deg,#1B2B1B,#22C55E)','linear-gradient(120deg,#2B1B1B,#EF4444)',
    'linear-gradient(120deg,#1B2B2B,#06B6D4)','linear-gradient(120deg,#2B2B1B,#F59E0B)'];
  var LB={tutorial:'📚 آموزش',news:'📰 خبر',feature:'✨ امکانات'};
  var EM={tutorial:['📚','هنوز آموزشی منتشر نشده'],news:['📰','هنوز خبری نیست'],feature:['✨','به‌زودی…']};
  api('/content?kind='+encodeURIComponent(kind)+'&limit=50').then(function(d){
    var it=(d&&d.items)||[];
    if(!it.length){var m=EM[kind]||EM.news;box.innerHTML='<div class="sl-empty"><span class="sl-empty-e">'+m[0]+'</span><b>'+m[1]+'</b></div>';return}
    box.innerHTML=it.map(function(p,i){
      return '<div class="sl-post" data-cid="'+p.id+'"><div class="sl-post-cv" style="background:'+colors[i%colors.length]+'">'+
        '<span class="sl-post-tag">'+(LB[kind]||kind)+'</span>'+
        (p.image_url?'<img src="'+esc(p.image_url)+'" alt="">':'')+
        '</div><div class="sl-post-bd"><div class="sl-post-t">'+esc(p.title)+'</div>'+
        '<div class="sl-post-x">'+esc(p.excerpt)+'</div><div class="sl-post-m">'+esc(p.created_at)+'</div></div></div>';
    }).join('');
  }).catch(function(){_lk[kind]=0;box.innerHTML=err('خطا')+'<button class="sl-retry" onclick="_lk={};loadL(\''+kind+'\')">تلاش مجدد</button>'});
}
window.loadL=loadL;
document.getElementById('learn-seg').addEventListener('click',function(e){
  var b=e.target.closest('button');if(!b)return;
  document.querySelectorAll('#learn-seg button').forEach(function(x){x.classList.remove('on')});b.classList.add('on');
  _lk={};loadL(b.dataset.k);
});
function openC(cid){
  var t=document.getElementById('post-title'),b=document.getElementById('post-body');
  t.textContent='…';b.innerHTML=skel(2);app.popup.open('#post-popup');
  api('/content/'+cid).then(function(d){
    var it=d.item||{};t.textContent=it.title||'';
    b.innerHTML=(it.image_url?'<img src="'+esc(it.image_url)+'" alt="">':'')+
      '<div class="sl-postf-title">'+esc(it.title)+'</div><div class="sl-postf-date">'+esc(it.created_at)+'</div>'+
      '<div class="sl-postf-text">'+nl2br(it.body)+'</div>';
  }).catch(function(){b.innerHTML=err('خطا')});
}

/* ═══ حساب ═══ */
var _m=0;
function loadMe(){if(_m)return;_m=1;
  var body=document.getElementById('me-body'),nm=document.getElementById('me-name');
  var foot='<div class="sl-group" style="margin-top:12px"><a class="sl-row" href="https://t.me/'+botUser+'" target="_blank">'+
    '<span class="sl-ric" style="background:#54A9EB">🤖</span><span class="sl-row-grow">باز کردن ربات</span><span class="sl-chev">‹</span></a></div>'+
    '<div class="sl-foot">استوک‌لند · نسخه ۲.۰</div>';
  function row(c,i,l,cmd,x){return '<a class="sl-row" href="https://t.me/'+botUser+'?start='+cmd+'" target="_blank"><span class="sl-ric" style="background:'+c+'">'+i+'</span><span class="sl-row-grow">'+l+'</span>'+(x||'')+'<span class="sl-chev">‹</span></a>'}
  if(!initData){nm.textContent='حساب من';body.innerHTML='<div class="sl-login"><div class="sl-login-e">🔐</div><div class="sl-login-t">ورود به حساب</div><div class="sl-login-s">برای مشاهده کیف پول و سفارش‌ها<br>از داخل ربات تلگرام وارد شوید.</div><a class="sl-login-btn" href="https://t.me/'+botUser+'?start=app" target="_blank">📱 ورود از تلگرام</a></div>'+foot;return}
  var un=(tgUser&&tgUser.first_name)||'کاربر',usr=(tgUser&&tgUser.username)||'';nm.textContent=un;
  body.innerHTML='<div class="sl-me"><div class="sl-ava">'+esc(un.charAt(0))+'</div><div><div class="sl-me-n">'+esc(un)+'</div><div class="sl-me-u">'+(usr?'@'+esc(usr)+' · ':'')+'ورود از تلگرام</div></div></div>'+
    '<div class="sl-wallet"><div class="sl-wallet-glow"></div><div class="sl-wallet-l">موجودی کیف پول</div>'+
    '<div class="sl-wallet-b" id="me-bal"><div class="sl-skel" style="margin:0;background:transparent"><div class="b w40" style="height:24px"></div></div></div>'+
    '<div class="sl-wallet-acts"><a class="sl-wallet-a" href="https://t.me/'+botUser+'?start=wallet" target="_blank">＋ شارژ</a>'+
    '<a class="sl-wallet-a" href="https://t.me/'+botUser+'?start=card2card" target="_blank">💳 کارت‌به‌کارت</a></div></div>'+
    '<div class="sl-group"><a class="sl-row" href="#" id="me-orders-row"><span class="sl-ric" style="background:#0A63FF">📦</span><span class="sl-row-grow">سفارش‌های من</span><span class="sl-chev">‹</span></a>'+
    row('#F59E0B','🤝','پنل همکاری','partner','<span class="sl-badge" id="me-pb" style="display:none">فعال</span>')+
    row('#22C55E','🎁','دعوت دوستان','invite','')+row('#6B7280','💬','پشتیبانی','support','')+'</div>'+foot;
  api('/me/wallet',true).then(function(d){var e=document.getElementById('me-bal');if(e)e.innerHTML=fmt(d.balance||0)+' <small>تومان</small>'}).catch(function(){var e=document.getElementById('me-bal');if(e)e.textContent='—'});
  api('/me/partner',true).then(function(d){if(d.is_partner){var b=document.getElementById('me-pb');if(b)b.style.display=''}}).catch(function(){});
  var or_=document.getElementById('me-orders-row');
  if(or_)or_.addEventListener('click',function(e){e.preventDefault();openOrders()});
}
window.loadMe=loadMe;

/* ═══ سفارش‌های من ═══ */
function openOrders(){
  var b=document.getElementById('orders-body');
  b.innerHTML=skel(3);
  app.popup.open('#orders-popup');
  api('/me/orders',true).then(function(d){
    var items=(d&&d.orders)||[];
    if(!items.length){b.innerHTML='<div class="sl-empty"><span class="sl-empty-e">📦</span>هنوز سفارشی ثبت نکرده‌اید.</div>';return}
    var ST={active:'تحویل‌شده',returned:'برگشتی'};
    b.innerHTML='<div class="sl-group" style="margin:12px">'+items.map(function(o){
      return '<div class="sl-row" style="cursor:default"><span class="sl-ric" style="background:#0A63FF">📦</span>'+
        '<span class="sl-row-grow"><div>'+esc(o.title)+'</div>'+
        '<div style="font-size:12px;color:var(--mu);margin-top:2px">'+esc(String(o.created_at||'').slice(0,16))+'</div></span>'+
        '<span style="text-align:left"><div style="font-weight:800">'+fmt(o.price)+' <small>تومان</small></div>'+
        '<div style="font-size:11px;color:var(--mu);margin-top:2px">'+esc(ST[o.status]||o.status||'')+'</div></span></div>';
    }).join('')+'</div>';
  }).catch(function(){b.innerHTML=err('خطا در دریافت سفارش‌ها')});
}
window.openOrders=openOrders;

/* ═══ جستجو ═══ */
document.getElementById('search-bar').addEventListener('click',function(){
  app.dialog.prompt('جستجو در محصولات','جستجو',function(q){
    q=(q||'').trim().toLowerCase();if(!q)return;
    var res=prods.filter(function(p){return(p.title||'').toLowerCase().indexOf(q)>=0||(p._c||'').toLowerCase().indexOf(q)>=0});
    if(res.length){
      var lnk=document.querySelector('.tab-link[href="#tab-shop"]');if(lnk)lnk.click();
      setTimeout(function(){
        document.querySelectorAll('#shop-cats .sl-cat-c').forEach(function(x){x.classList.remove('on')});
        var pl=document.getElementById('prod-list');
        pl.innerHTML=res.map(function(p){
          var f=p.flash_active;
          return '<div class="sl-prod" data-pid="'+p.id+'"><div class="sl-pic">'+(p._e||'📦')+'</div>'+
            '<div class="sl-pinfo"><div class="sl-pt">'+esc(p.title)+'</div><div class="sl-pg">'+esc(p._c||'')+'</div>'+
            '<div class="sl-pprice-row">'+(f?'<span class="sl-old">'+fmt(p.price)+'</span>':'')+
            '<span class="sl-price">'+fmt(p.effective_price)+' <small>تومان</small></span></div>'+
            '<span class="sl-buy">مشاهده و خرید</span></div></div>';
        }).join('');
      },100);
    }else{app.dialog.alert('نتیجه‌ای یافت نشد.','جستجو')}
  });
});

/* ═══ رویدادها ═══ */
app.on('tabShow',function(el){var id=el&&el.id;
  if(id==='tab-home')loadHome();if(id==='tab-shop')loadShop();
  if(id==='tab-learn'){var k=document.querySelector('#learn-seg button.on');loadL(k?k.dataset.k:'tutorial')}
  if(id==='tab-me')loadMe();
});
app.on('ptrRefresh',function(el,done){var t=document.querySelector('.tab.tab-active'),id=t&&t.id;
  if(id==='tab-home'){_h=0;cats=[];prods=[];loadHome()}if(id==='tab-shop'){_s=0;prods=[];loadShop()}
  if(id==='tab-learn'){_lk={};loadL(_lc)}if(id==='tab-me'){_m=0;loadMe()}
  setTimeout(done,600);
});
document.addEventListener('click',function(e){
  var p=e.target.closest('[data-pid]');if(p){openP(p.dataset.pid);return}
  var c=e.target.closest('[data-cid]');if(c){openC(c.dataset.cid);return}
  var co=e.target.closest('[data-checkout]');if(co){openCheckout(co.dataset.checkout);return}
  var tb=e.target.closest('[data-tab]');if(tb){e.preventDefault();var l=document.querySelector('.tab-link[href="#'+tb.dataset.tab+'"]');if(l)l.click()}
});

/* ═══ Mira-style scroll morph ═══ */
(function(){
  var nav=document.getElementById('sl-nav');
  var navTitle=document.getElementById('sl-nav-title');
  var hero=document.getElementById('sl-hero');
  var homeTab=document.getElementById('tab-home');
  if(!nav||!hero||!homeTab)return;
  var _dk=window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches;
  var HERO_TOP=_dk?'#232277':'#4340DE';
  var BAR_SOLID=_dk?'#1C1C1E':'#FFFFFF';
  var PAGE_BG=_dk?'#000000':'#F2F2F7';
  var INK=_dk?'#F5F5F7':'#0B0B0F';
  var _lastHex='';
  function setTgHeader(hex){if(hex===_lastHex)return;_lastHex=hex;try{if(tg&&tg.setHeaderColor)tg.setHeaderColor(hex)}catch(e){}}
  function mixHex(a,b,t){function h(c){return[parseInt(c.substr(1,2),16),parseInt(c.substr(3,2),16),parseInt(c.substr(5,2),16)]}
    var A=h(a),B=h(b),o='#';for(var i=0;i<3;i++){var v=Math.round(A[i]+(B[i]-A[i])*t);o+=('0'+v.toString(16)).slice(-2)}return o}
  function easeOut(t){return 1-Math.pow(1-t,3)}
  function smooth(t){t=Math.min(Math.max(t,0),1);return t*t*(3-2*t)}
  if(inTG){try{tg.setBackgroundColor(PAGE_BG)}catch(e){}setTgHeader(HERO_TOP)}
  navTitle.style.color=INK;
  var ticking=false;
  function onScroll(){
    if(ticking)return;ticking=true;
    requestAnimationFrame(function(){
      ticking=false;
      var activeTab=document.querySelector('.tab.tab-active');
      if(!activeTab||activeTab.id!=='tab-home'){
        nav.style.background='transparent';
        nav.style.backdropFilter='none';nav.style.webkitBackdropFilter='none';
        nav.style.boxShadow='none';navTitle.style.opacity='0';
        nav.classList.remove('sl-nav--solid');
        setTgHeader(PAGE_BG);
        return;
      }
      var heroH=hero.offsetHeight||1;
      var p=Math.min(Math.max(homeTab.scrollTop/(heroH*0.62),0),1);
      var pe=easeOut(p);
      var bar=_dk?'28,28,30':'255,255,255';
      nav.style.background='rgba('+bar+','+pe+')';
      var bl=(20*pe).toFixed(1);
      nav.style.backdropFilter='saturate('+(100+80*pe).toFixed(0)+'%) blur('+bl+'px)';
      nav.style.webkitBackdropFilter='saturate('+(100+80*pe).toFixed(0)+'%) blur('+bl+'px)';
      nav.style.boxShadow='0 2px 12px rgba(0,0,0,'+(0.06*pe).toFixed(3)+')';
      navTitle.style.opacity=smooth((p-0.5)/0.5).toFixed(3);
      if(p>0.04){nav.classList.add('sl-nav--solid')}else{nav.classList.remove('sl-nav--solid')}
      setTgHeader(mixHex(HERO_TOP,BAR_SOLID,pe));
    });
  }
  homeTab.addEventListener('scroll',onScroll,{passive:true});
  app.on('tabShow',function(){setTimeout(onScroll,50)});
  window.addEventListener('resize',onScroll,{passive:true});
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
var _checkoutPid=0,_checkoutProd=null,_checkoutWalBal=0,_checkoutBasePrice=0,
    _checkoutDiscountCode='',_checkoutDiscountAmount=0;

function openCheckout(pid){
  _checkoutPid=pid;_checkoutDiscountCode='';_checkoutDiscountAmount=0;
  var b=document.getElementById('checkout-body');
  b.innerHTML='<div class="sl-skel" style="margin:20px"><div class="b w60"></div><div class="b w90"></div><div class="b w40"></div></div>';
  app.popup.open('#checkout-popup');

  Promise.all([
    api('/products/'+pid),
    api('/me/wallet',true)
  ]).then(function(res){
    _checkoutProd=res[0].product||{};
    _checkoutWalBal=res[1].balance||0;
    _checkoutBasePrice=_checkoutProd.effective_price||_checkoutProd.price||0;
    _renderCheckoutBody();
  }).catch(function(){
    b.innerHTML='<div class="sl-empty"><span class="sl-empty-e">📡</span>خطا در دریافت اطلاعات</div>';
  });
}

window.openCheckout=openCheckout;

function _renderCheckoutBody(){
  var b=document.getElementById('checkout-body');
  var p=_checkoutProd,walBal=_checkoutWalBal;
  var price=Math.max(0,_checkoutBasePrice-_checkoutDiscountAmount);
  var canWallet=walBal>=price;
  var canCombined=walBal>0&&walBal<price;
  var emoji=p._e||'📦';

  var btns='';
  if(price<=0){
    btns='<button class="sl-checkout-btn sl-checkout-btn-wallet" onclick="_doPay(\'wallet\')">✅ دریافت رایگان</button>';
  }else{
    if(canWallet){
      btns+='<button class="sl-checkout-btn sl-checkout-btn-wallet" onclick="_doPay(\'wallet\')">👛 پرداخت از کیف‌پول ('+fmt(price)+' تومان)</button>';
    }
    if(canCombined){
      var gw=price-walBal;
      btns+='<button class="sl-checkout-btn sl-checkout-btn-combined" onclick="_doPay(\'combined\')">'+
        '💳 پرداخت ترکیبی (کیف‌پول '+fmt(walBal)+' + درگاه '+fmt(gw)+' تومان)</button>';
    }
    btns+='<button class="sl-checkout-btn sl-checkout-btn-gateway" onclick="_doPay(\'gateway\')">🌐 پرداخت کامل از درگاه ('+fmt(price)+' تومان)</button>';
  }

  var priceLine=_checkoutDiscountAmount>0?
    '<div class="sl-checkout-price"><s style="color:var(--mu)">'+fmt(_checkoutBasePrice)+'</s> <b>'+fmt(price)+' تومان</b></div>':
    '<div class="sl-checkout-price">قیمت: <b>'+fmt(price)+' تومان</b></div>';

  var discRow=_checkoutDiscountCode?
    '<div class="sl-checkout-wallet"><div class="sl-checkout-wallet-info">🎟 کد «'+esc(_checkoutDiscountCode)+'» اعمال شد <span style="color:var(--mu)">(−'+fmt(_checkoutDiscountAmount)+' تومان)</span></div>'+
    '<a href="#" id="discount-remove" style="color:var(--br);font-size:13px;font-weight:700">حذف</a></div>':
    '<a href="#" id="discount-apply" class="sl-checkout-wallet" style="display:flex;justify-content:space-between;align-items:center;text-decoration:none">'+
    '<span style="color:var(--mu)">🎟 کد تخفیف دارید؟</span><span style="color:var(--br);font-weight:700">وارد کنید ›</span></a>';

  b.innerHTML=
    '<div class="sl-checkout-prod">'+
      '<div class="sl-checkout-emoji">'+esc(emoji)+'</div>'+
      '<div><div class="sl-checkout-title">'+esc(p.title)+'</div>'+priceLine+'</div>'+
    '</div>'+
    '<div class="sl-checkout-sec">موجودی کیف‌پول شما</div>'+
    '<div class="sl-checkout-wallet">'+
      '<div class="sl-checkout-wallet-info">کیف پول</div>'+
      '<div class="sl-checkout-wallet-bal">'+fmt(walBal)+' تومان</div>'+
    '</div>'+
    '<div class="sl-checkout-sec">کد تخفیف</div>'+discRow+
    '<div class="sl-checkout-sec">روش پرداخت</div>'+
    '<div class="sl-checkout-btns" id="checkout-btns">'+btns+'</div>'+
    '<div class="sl-checkout-note">بعد از تایید پرداخت، سفارش شما به‌صورت خودکار ثبت و ارسال می‌شود.<br>در پرداخت از درگاه، قبل از ورود فیلترشکن (VPN) خود را خاموش کنید.</div>';

  var da=document.getElementById('discount-apply');
  if(da)da.addEventListener('click',function(e){e.preventDefault();_applyDiscount()});
  var dr=document.getElementById('discount-remove');
  if(dr)dr.addEventListener('click',function(e){e.preventDefault();_checkoutDiscountCode='';_checkoutDiscountAmount=0;_renderCheckoutBody()});
}

window._applyDiscount=function(){
  app.dialog.prompt('کد تخفیف را وارد کنید','کد تخفیف',function(code){
    code=(code||'').trim();if(!code)return;
    fetch('https://panel.stland.ir/api/v1/discount/validate',{
      method:'POST',
      headers:{'Content-Type':'application/json','X-Telegram-Init-Data':initData},
      body:JSON.stringify({product_id:_checkoutPid,code:code})
    }).then(function(r){return r.json()}).then(function(d){
      if(!d.ok){app.dialog.alert(d.error||'کد تخفیف نامعتبر است.','خطا');return}
      _checkoutDiscountCode=code;_checkoutDiscountAmount=d.discount_amount||0;
      _renderCheckoutBody();
    }).catch(function(){app.dialog.alert('خطا در بررسی کد تخفیف.','خطا')});
  });
};

window._doPay=function(method){
  var btns=document.getElementById('checkout-btns');
  if(btns) btns.querySelectorAll('button').forEach(function(x){x.disabled=true;x.textContent='⏳ در حال پردازش...'});

  fetch('https://panel.stland.ir/api/v1/checkout',{
    method:'POST',
    headers:{'Content-Type':'application/json','X-Telegram-Init-Data':initData},
    body:JSON.stringify({product_id:_checkoutPid,payment_type:method,discount_code:_checkoutDiscountCode||undefined})
  }).then(function(r){return r.json()}).then(function(d){
    var b=document.getElementById('checkout-body');
    if(!d.ok){
      b.innerHTML='<div class="sl-checkout-result"><div class="sl-checkout-result-e">❌</div>'+
        '<div class="sl-checkout-result-t">خطا</div>'+
        '<div class="sl-checkout-result-s">'+esc(d.detail||d.message||'خطا در پردازش')+'</div>'+
        '<button class="sl-checkout-close-btn" onclick="app.popup.close(\'#checkout-popup\')">بستن</button></div>';
      return;
    }
    if(d.method==='wallet'){
      _m=0;// ری‌فرش موجودی در تب حساب
      b.innerHTML='<div class="sl-checkout-result"><div class="sl-checkout-result-e">✅</div>'+
        '<div class="sl-checkout-result-t">خرید موفق!</div>'+
        '<div class="sl-checkout-result-s">'+esc(d.message||'سفارش شما ثبت شد.')+'<br>تحویل از طریق ربات ارسال می‌شود.</div>'+
        '<button class="sl-checkout-close-btn" onclick="app.popup.close(\'#checkout-popup\')">بستن</button></div>';
    } else if(d.redirect_url){
      // درگاه: در تلگرام با openLink باز کن
      if(tg&&tg.openLink){
        tg.openLink(d.redirect_url);
        b.innerHTML='<div class="sl-checkout-result"><div class="sl-checkout-result-e">🌐</div>'+
          '<div class="sl-checkout-result-t">انتقال به درگاه...</div>'+
          '<div class="sl-checkout-result-s">صفحه پرداخت باز شد.<br>بعد از پرداخت به ربات برگردید.</div>'+
          '<button class="sl-checkout-close-btn" onclick="app.popup.close(\'#checkout-popup\')">بستن</button></div>';
      } else {
        window.location.href=d.redirect_url;
      }
    }
  }).catch(function(e){
    var b=document.getElementById('checkout-body');
    b.innerHTML='<div class="sl-checkout-result"><div class="sl-checkout-result-e">❌</div>'+
      '<div class="sl-checkout-result-t">خطای شبکه</div>'+
      '<div class="sl-checkout-result-s">لطفاً دوباره امتحان کنید.</div>'+
      '<button class="sl-checkout-close-btn" onclick="app.popup.close(\'#checkout-popup\')">بستن</button></div>';
  });
};

/* بعد از بازگشت از درگاه — ?payment=canceled در URL */
(function(){
  var u=new URL(window.location.href);
  if(u.searchParams.get('payment')==='canceled'){
    app.dialog.alert('پرداخت لغو شد یا ناموفق بود.','نتیجه پرداخت');
    history.replaceState({},'',u.pathname);
  }
})();
