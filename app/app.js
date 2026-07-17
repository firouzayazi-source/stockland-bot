(function(){
'use strict';
var tg=window.Telegram&&window.Telegram.WebApp||null;
var inTG=!!(tg&&tg.initData);
if(inTG){document.documentElement.classList.add('in-telegram');try{tg.ready();tg.expand()}catch(e){}}
var initData=(tg&&tg.initData)||'';
var tgUser=(tg&&tg.initDataUnsafe&&tg.initDataUnsafe.user)||null;
var app=new Framework7({el:'#app',name:'استوک‌لند',theme:'ios',darkMode:'auto',popup:{closeByBackdropClick:true}});

function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function nl2br(s){return esc(s).replace(/\r?\n/g,'<br>')}
function fmt(n){return Number(n).toLocaleString('fa-IR')}
function skel(n){var o='';for(var i=0;i<(n||3);i++)o+='<div class="sl-skel"><div class="b w60"></div><div class="b w90"></div><div class="b w40"></div></div>';return o}
function api(p,a){var h={'Accept':'application/json'};if(a&&initData)h['X-Telegram-Init-Data']=initData;return fetch('/api/v1'+p,{headers:h}).then(function(r){if(!r.ok)throw r;return r.json()})}
function err(msg){return '<div class="sl-empty"><span class="sl-empty-e">📡</span>'+esc(msg||'خطا')+'</div>'}

var botUser='stock_land_ir';
api('/bot-info').then(function(d){if(d&&d.username)botUser=d.username}).catch(function(){});

try{document.getElementById('today-date').textContent=new Intl.DateTimeFormat('fa-IR-u-ca-persian',{weekday:'long',day:'numeric',month:'long'}).format(new Date())}catch(e){}

/* ═══ خانه ═══ */
var _h=0;
function loadHome(){
  if(_h)return;_h=1;
  var tr=document.getElementById('ticker-row'),nr=document.getElementById('news-row'),dp=document.getElementById('daily-post');
  tr.innerHTML=skel(1);nr.innerHTML=skel(1);

  api('/products?limit=20').then(function(d){
    var it=(d&&d.products)||[];
    if(!it.length){tr.innerHTML='<div class="sl-empty"><span class="sl-empty-e">📦</span>محصولی ثبت نشده</div>';return}
    var n=new Date();document.getElementById('ticker-time').textContent=('0'+n.getHours()).slice(-2)+':'+('0'+n.getMinutes()).slice(-2);
    tr.innerHTML=it.map(function(p){
      return '<div class="sl-tick" data-pid="'+p.id+'"><div class="sl-tick-n">'+esc(p.title)+'</div>'+
        '<div class="sl-tick-p">'+fmt(p.effective_price)+' <small>تومان</small></div>'+
        (p.flash_active?'<div class="sl-flash">⚡️ فروش فوری</div>':'')+'</div>';
    }).join('');
  }).catch(function(){_h=0;tr.innerHTML=err('خطا در دریافت قیمت‌ها')+'<button class="sl-retry" onclick="_h=0;loadHome()">تلاش مجدد</button>'});

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

  var colors=['linear-gradient(120deg,#123,#0A63FF)','linear-gradient(120deg,#1B2B1B,#30D158)',
    'linear-gradient(120deg,#2B1B2B,#BF5AF2)','linear-gradient(120deg,#2B1B1B,#FF453A)',
    'linear-gradient(120deg,#1B2B2B,#0A9396)','linear-gradient(120deg,#2B2B1B,#FF9F0A)'];
  api('/content?kind=news&limit=6').then(function(d){
    var it=(d&&d.items)||[];
    if(!it.length){nr.innerHTML='';return}
    nr.innerHTML=it.map(function(p,i){
      return '<div class="sl-mini" data-cid="'+p.id+'"><div class="sl-mini-cv" style="background:'+colors[i%colors.length]+'">'+
        (p.image_url?'<img src="'+esc(p.image_url)+'" alt="">':'📰')+'</div>'+
        '<div class="sl-mini-b"><div class="sl-mini-t">'+esc(p.title)+'</div><div class="sl-mini-m">'+esc(p.created_at)+'</div></div></div>';
    }).join('');
  }).catch(function(){nr.innerHTML=''});
}
window.loadHome=loadHome;loadHome();

/* ═══ فروشگاه ═══ */
var _s=0,cats=[],prods=[];
function loadShop(){
  if(_s)return;_s=1;
  var cl=document.getElementById('cat-chips'),pl=document.getElementById('prod-list');
  cl.innerHTML='';pl.innerHTML=skel(3);
  api('/categories').then(function(d){
    cats=(d&&d.categories)||[];prods=[];
    cats.forEach(function(c){
      (c.products||[]).forEach(function(p){p._c=c.name;p._e=c.emoji;prods.push(p)});
      (c.subcategories||[]).forEach(function(s){
        (s.products||[]).forEach(function(p){p._c=c.name;p._e=c.emoji;p._s=s.name;prods.push(p)});
      });
    });
    document.getElementById('shop-count').textContent=prods.length+' محصول فعال';
    var ch=[{s:'',n:'همه',e:'🏪'}];cats.forEach(function(c){ch.push({s:c.slug||c.name,n:c.name,e:c.emoji||''})});
    cl.innerHTML=ch.map(function(c,i){return '<span class="sl-chip'+(i===0?' on':'')+'" data-slug="'+esc(c.s)+'">'+(c.e?c.e+' ':'')+esc(c.n)+'</span>'}).join('');
    renderP('');
  }).catch(function(){_s=0;pl.innerHTML=err('خطا')+'<button class="sl-retry" onclick="_s=0;loadShop()">تلاش مجدد</button>'});
}
window.loadShop=loadShop;

function renderP(slug){
  var pl=document.getElementById('prod-list');
  var it=slug?prods.filter(function(p){return p._c===slug||p._s===slug}):prods;
  if(!it.length){pl.innerHTML='<div class="sl-empty"><span class="sl-empty-e">📦</span>محصولی نیست</div>';return}
  pl.innerHTML=it.map(function(p){
    var f=p.flash_active;
    return '<div class="sl-prod" data-pid="'+p.id+'"><div class="sl-pic">'+(p._e||'📦')+'</div>'+
      '<div class="sl-pinfo"><div class="sl-pt">'+esc(p.title)+'</div><div class="sl-pg">'+esc(p._c||'')+(p._s?' · '+esc(p._s):'')+'</div></div>'+
      '<div class="sl-pp">'+(f?'<div class="sl-old">'+fmt(p.price)+'</div>':'')+
      '<div class="sl-price">'+fmt(p.effective_price)+' <small>تومان</small></div>'+
      (f?'<div class="sl-flash">⚡️ فروش فوری</div>':'')+'<span class="sl-buy">مشاهده</span></div></div>';
  }).join('');
}

document.getElementById('cat-chips').addEventListener('click',function(e){
  var c=e.target.closest('.sl-chip');if(!c)return;
  document.querySelectorAll('.sl-chip').forEach(function(x){x.classList.remove('on')});c.classList.add('on');
  var s=c.dataset.slug;if(!s){renderP('');return}
  var cat=cats.find(function(x){return(x.slug||x.name)===s});renderP(cat?cat.name:'');
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
      (p.description?'<div class="sl-pp-desc">'+nl2br(p.description)+'</div>':'')+
      '<a class="sl-pp-btn'+(hs&&!ok?' sl-pp-btn-off':'')+'" href="https://t.me/'+botUser+'?start=buy_'+p.id+'" target="_blank">'+
      (hs&&!ok?'اطلاع‌رسانی موجود شدن':'خرید از ربات')+'</a>';
  }).catch(function(){b.innerHTML=err('خطا')});
}

/* ═══ آموزش ═══ */
var _lk={},_lc='tutorial';
function loadL(kind){
  _lc=kind;if(_lk[kind])return;_lk[kind]=1;
  var box=document.getElementById('learn-list');box.innerHTML=skel(2);
  var colors=['linear-gradient(120deg,#101826,#7C3AED)','linear-gradient(120deg,#0F172A,#0A63FF)',
    'linear-gradient(120deg,#1B2B1B,#30D158)','linear-gradient(120deg,#2B1B1B,#FF453A)',
    'linear-gradient(120deg,#1B2B2B,#0A9396)','linear-gradient(120deg,#2B2B1B,#FF9F0A)'];
  var LB={tutorial:'📚 آموزش',news:'📰 خبر',feature:'✨ امکانات'};
  var EM={tutorial:['📚','هنوز آموزشی منتشر نشده'],news:['📰','هنوز خبری منتشر نشده'],feature:['✨','به‌زودی…']};
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
function loadMe(){
  if(_m)return;_m=1;
  var body=document.getElementById('me-body'),nm=document.getElementById('me-name');
  var foot='<div class="sl-group" style="margin-top:12px"><a class="sl-row" href="https://t.me/'+botUser+'" target="_blank">'+
    '<span class="sl-ric" style="background:#54A9EB">🤖</span><span class="sl-row-grow">باز کردن ربات</span><span class="sl-chev">‹</span></a></div>'+
    '<div class="sl-foot">استوک‌لند · نسخه ۲.۰</div>';
  function row(c,i,l,cmd,x){return '<a class="sl-row" href="https://t.me/'+botUser+'?start='+cmd+'" target="_blank"><span class="sl-ric" style="background:'+c+'">'+i+'</span><span class="sl-row-grow">'+l+'</span>'+(x||'')+'<span class="sl-chev">‹</span></a>'}

  if(!initData){
    nm.textContent='حساب من';
    body.innerHTML='<div class="sl-login"><div class="sl-login-e">🔐</div><div class="sl-login-t">ورود به حساب</div>'+
      '<div class="sl-login-s">برای مشاهده کیف پول و سفارش‌ها<br>از داخل ربات تلگرام وارد شوید.</div>'+
      '<a class="sl-login-btn" href="https://t.me/'+botUser+'?start=app" target="_blank">📱 ورود از تلگرام</a></div>'+foot;
    return;
  }
  var un=(tgUser&&tgUser.first_name)||'کاربر',usr=(tgUser&&tgUser.username)||'';
  nm.textContent=un;
  body.innerHTML='<div class="sl-me"><div class="sl-ava">'+esc(un.charAt(0))+'</div><div>'+
    '<div class="sl-me-n">'+esc(un)+'</div><div class="sl-me-u">'+(usr?'@'+esc(usr)+' · ':'')+'ورود از تلگرام</div></div></div>'+
    '<div class="sl-wallet"><div class="sl-wallet-glow"></div><div class="sl-wallet-l">موجودی کیف پول</div>'+
    '<div class="sl-wallet-b" id="me-bal"><div class="sl-skel" style="margin:0;background:transparent"><div class="b w40" style="height:26px"></div></div></div>'+
    '<div class="sl-wallet-acts"><a class="sl-wallet-a" href="https://t.me/'+botUser+'?start=wallet" target="_blank">＋ شارژ</a>'+
    '<a class="sl-wallet-a" href="https://t.me/'+botUser+'?start=card2card" target="_blank">💳 کارت‌به‌کارت</a></div></div>'+
    '<div class="sl-group">'+row('#0A63FF','📦','سفارش‌های من','orders','')+
    row('#FF9F0A','🤝','پنل همکاری','partner','<span class="sl-badge" id="me-pb" style="display:none">فعال</span>')+
    row('#30D158','🎁','دعوت دوستان','invite','')+row('#8E8E93','💬','پشتیبانی','support','')+'</div>'+foot;

  api('/me/wallet',true).then(function(d){var e=document.getElementById('me-bal');if(e)e.innerHTML=fmt(d.balance||0)+' <small>تومان</small>'}).catch(function(){var e=document.getElementById('me-bal');if(e)e.textContent='—'});
  api('/me/partner',true).then(function(d){if(d.is_partner){var b=document.getElementById('me-pb');if(b)b.style.display=''}}).catch(function(){});
}
window.loadMe=loadMe;

/* ═══ جستجو ═══ */
document.getElementById('search-bar').addEventListener('click',function(){
  app.dialog.prompt('جستجو در محصولات و آموزش‌ها','جستجو',function(q){
    q=(q||'').trim().toLowerCase();if(!q)return;
    var res=prods.filter(function(p){return(p.title||'').toLowerCase().indexOf(q)>=0||(p._c||'').toLowerCase().indexOf(q)>=0});
    if(res.length){
      var lnk=document.querySelector('.tab-link[href="#tab-shop"]');if(lnk)lnk.click();
      setTimeout(function(){
        document.querySelectorAll('.sl-chip').forEach(function(x){x.classList.remove('on')});
        var pl=document.getElementById('prod-list');
        pl.innerHTML=res.map(function(p){
          var f=p.flash_active;
          return '<div class="sl-prod" data-pid="'+p.id+'"><div class="sl-pic">'+(p._e||'📦')+'</div>'+
            '<div class="sl-pinfo"><div class="sl-pt">'+esc(p.title)+'</div><div class="sl-pg">'+esc(p._c||'')+'</div></div>'+
            '<div class="sl-pp">'+(f?'<div class="sl-old">'+fmt(p.price)+'</div>':'')+
            '<div class="sl-price">'+fmt(p.effective_price)+' <small>تومان</small></div><span class="sl-buy">مشاهده</span></div></div>';
        }).join('');
      },100);
    }else{app.dialog.alert('نتیجه‌ای یافت نشد.','جستجو')}
  });
});

/* ═══ رویدادها ═══ */
app.on('tabShow',function(el){
  var id=el&&el.id;
  if(id==='tab-home')loadHome();if(id==='tab-shop')loadShop();
  if(id==='tab-learn'){var k=document.querySelector('#learn-seg button.on');loadL(k?k.dataset.k:'tutorial')}
  if(id==='tab-me')loadMe();
});
app.on('ptrRefresh',function(el,done){
  var t=document.querySelector('.tab.tab-active'),id=t&&t.id;
  if(id==='tab-home'){_h=0;loadHome()}if(id==='tab-shop'){_s=0;loadShop()}
  if(id==='tab-learn'){_lk={};loadL(_lc)}if(id==='tab-me'){_m=0;loadMe()}
  setTimeout(done,600);
});
document.addEventListener('click',function(e){
  var p=e.target.closest('[data-pid]');if(p){openP(p.dataset.pid);return}
  var c=e.target.closest('[data-cid]');if(c){openC(c.dataset.cid);return}
  var tb=e.target.closest('[data-tab]');if(tb){e.preventDefault();var l=document.querySelector('.tab-link[href="#'+tb.dataset.tab+'"]');if(l)l.click()}
});

if('serviceWorker' in navigator)window.addEventListener('load',function(){navigator.serviceWorker.register('sw.js').catch(function(){})});

var sa=window.matchMedia('(display-mode:standalone)').matches||window.navigator.standalone===true;
var di=false;try{di=sessionStorage.getItem('sl-hint-off')==='1'}catch(e){}
if(!inTG&&!sa&&!di){
  var h=document.getElementById('install-hint'),b=document.getElementById('install-btn'),tx=document.getElementById('install-hint-text'),dp2=null;
  window.addEventListener('beforeinstallprompt',function(e){e.preventDefault();dp2=e;b.style.display='';tx.textContent='با یک لمس نصب کنید'});
  b.addEventListener('click',function(){if(!dp2)return;dp2.prompt();dp2=null;h.style.display='none'});
  if(/iphone|ipad|ipod/i.test(navigator.userAgent))tx.innerHTML='در سافاری: <b>Share</b> → <b>Add to Home Screen</b>';
  else tx.textContent='برای نصب از منوی مرورگر استفاده کنید';
  h.style.display='';
  document.getElementById('install-close').addEventListener('click',function(){h.style.display='none';try{sessionStorage.setItem('sl-hint-off','1')}catch(e){}});
}
})();
