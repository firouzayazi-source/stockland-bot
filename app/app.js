/* استوک‌لند PWA — فاز ۲ کامل */
(function(){
'use strict';

/* ── تلگرام ── */
var tg=window.Telegram&&window.Telegram.WebApp&&window.Telegram.WebApp.initData!==undefined?window.Telegram.WebApp:null;
var inTG=!!(tg&&(tg.initData||tg.platform!=='unknown'));
if(inTG){document.documentElement.classList.add('in-telegram');try{tg.ready();tg.expand();tg.enableClosingConfirmation()}catch(e){}}
var initData=(tg&&tg.initData)||'';
var tgUser=(tg&&tg.initDataUnsafe&&tg.initDataUnsafe.user)||null;

/* ── F7 ── */
var app=new Framework7({el:'#app',name:'استوک‌لند',theme:'ios',darkMode:'auto',
  popup:{closeByBackdropClick:true},dialog:{title:'استوک‌لند'}});

/* ── ابزار ── */
function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function nl2br(s){return esc(s).replace(/\r?\n/g,'<br>')}
function fmt(n){return Number(n).toLocaleString('fa-IR')}
function skel(n){var o='';for(var i=0;i<(n||3);i++)o+='<div class="sl-skel"><div class="b w60"></div><div class="b w90"></div><div class="b w40"></div></div>';return o}
function api(path,auth){
  var h={'Accept':'application/json'};
  if(auth&&initData)h['X-Telegram-Init-Data']=initData;
  return fetch('/api/v1'+path,{headers:h}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json()});
}

/* ── یوزرنیم ربات ── */
var botUser='stock_land_ir';
api('/bot-info').then(function(d){if(d.username)botUser=d.username}).catch(function(){});

/* ── تاریخ ── */
function persianDate(){try{return new Intl.DateTimeFormat('fa-IR-u-ca-persian',{weekday:'long',day:'numeric',month:'long'}).format(new Date())}catch(e){return''}}
var dd=document.getElementById('today-date');if(dd)dd.textContent=persianDate();

/* ═══════════════════════════════════════════════════════════════════════ */
/*  خانه                                                                   */
/* ═══════════════════════════════════════════════════════════════════════ */
var homeLoaded=false;
function loadHome(){
  if(homeLoaded)return;homeLoaded=true;
  var tr=document.getElementById('ticker-row');
  var nr=document.getElementById('news-row');
  var dp=document.getElementById('daily-post');
  tr.innerHTML=skel(1);nr.innerHTML=skel(1);

  // تیکر قیمت
  api('/products?limit=20').then(function(d){
    var items=(d&&d.products)||[];
    if(!items.length){tr.innerHTML='<div class="sl-empty"><span class="sl-empty-e">📦</span>محصولی ثبت نشده</div>';return}
    var now=new Date();
    document.getElementById('ticker-time').textContent=('0'+now.getHours()).slice(-2)+':'+('0'+now.getMinutes()).slice(-2);
    tr.innerHTML=items.map(function(it){
      return '<div class="sl-tick" data-pid="'+it.id+'">'+
        '<div class="sl-tick-n">'+esc(it.title)+'</div>'+
        '<div class="sl-tick-p">'+fmt(it.effective_price)+' <small>تومان</small></div>'+
        (it.flash_active?'<div class="sl-flash">⚡️ فروش فوری</div>':'')+
      '</div>';
    }).join('');
  }).catch(function(){homeLoaded=false;tr.innerHTML='<div class="sl-empty"><span class="sl-empty-e">📡</span>خطا<br><button class="sl-retry-btn" onclick="window._retryHome()">تلاش مجدد</button></div>'});

  // پست روزانه
  api('/content/daily').then(function(d){
    if(!d.item){dp.style.display='none';return}
    var it=d.item;
    dp.innerHTML=
      '<div class="sl-sec"><b>📋 لیست روزانه</b></div>'+
      '<div class="sl-post" data-cid="'+it.id+'" style="margin:0 20px">'+
        (it.image_url?'<div class="sl-post-cv" style="background:#0B1B4A"><img src="'+esc(it.image_url)+'" style="width:100%;height:100%;object-fit:cover" alt=""></div>':'')+
        '<div class="sl-post-bd"><div class="sl-post-t">'+esc(it.title)+'</div>'+
        '<div class="sl-post-x">'+esc((it.body||'').substring(0,160))+'</div>'+
        '<div class="sl-post-m">'+esc(it.created_at)+'</div></div></div>';
  }).catch(function(){dp.style.display='none'});

  // اخبار
  api('/content?kind=news&limit=6').then(function(d){
    var items=(d&&d.items)||[];
    if(!items.length){nr.innerHTML='';return}
    var colors=['linear-gradient(120deg,#123,#0A63FF)','linear-gradient(120deg,#1B2B1B,#30D158)',
      'linear-gradient(120deg,#2B1B2B,#BF5AF2)','linear-gradient(120deg,#2B1B1B,#FF453A)',
      'linear-gradient(120deg,#1B2B2B,#0A9396)','linear-gradient(120deg,#2B2B1B,#FF9F0A)'];
    nr.innerHTML=items.map(function(it,i){
      return '<div class="sl-mini" data-cid="'+it.id+'">'+
        '<div class="sl-mini-cv" style="background:'+colors[i%colors.length]+'">'+
          (it.image_url?'<img src="'+esc(it.image_url)+'" style="width:100%;height:100%;object-fit:cover" alt="">':'📰')+
        '</div><div class="sl-mini-b"><div class="sl-mini-t">'+esc(it.title)+'</div>'+
        '<div class="sl-mini-m">'+esc(it.created_at)+'</div></div></div>';
    }).join('');
  }).catch(function(){nr.innerHTML=''});
}
window._retryHome=function(){homeLoaded=false;loadHome()};
loadHome();

/* ═══════════════════════════════════════════════════════════════════════ */
/*  فروشگاه                                                               */
/* ═══════════════════════════════════════════════════════════════════════ */
var shopLoaded=false,shopData=[],allProds=[];
function loadShop(){
  if(shopLoaded)return;shopLoaded=true;
  var cl=document.getElementById('cat-chips');
  var pl=document.getElementById('prod-list');
  cl.innerHTML='';pl.innerHTML=skel(3);

  api('/categories').then(function(d){
    shopData=(d&&d.categories)||[];
    allProds=[];
    shopData.forEach(function(cat){
      (cat.products||[]).forEach(function(p){p._cat=cat.name;p._catEmoji=cat.emoji;allProds.push(p)});
      (cat.subcategories||[]).forEach(function(sub){
        (sub.products||[]).forEach(function(p){p._cat=cat.name;p._catEmoji=cat.emoji;p._sub=sub.name;allProds.push(p)});
      });
    });
    document.getElementById('shop-count').textContent=allProds.length+' محصول فعال';
    var chips=[{slug:'',name:'همه',emoji:'🏪'}];
    shopData.forEach(function(c){chips.push({slug:c.slug||c.name,name:c.name,emoji:c.emoji||''})});
    cl.innerHTML=chips.map(function(c,i){
      return '<span class="sl-chip'+(i===0?' on':'')+'" data-slug="'+esc(c.slug)+'">'+
        (c.emoji?c.emoji+' ':'')+esc(c.name)+'</span>';
    }).join('');
    renderProds('');
  }).catch(function(){shopLoaded=false;pl.innerHTML='<div class="sl-empty"><span class="sl-empty-e">📡</span>خطا<br><button class="sl-retry-btn" onclick="window._retryShop()">تلاش مجدد</button></div>'});
}
window._retryShop=function(){shopLoaded=false;loadShop()};

function renderProds(slug){
  var pl=document.getElementById('prod-list');
  var items=slug?allProds.filter(function(p){return p._cat===slug||p._sub===slug}):allProds;
  if(!items.length){pl.innerHTML='<div class="sl-empty"><span class="sl-empty-e">📦</span>محصولی در این دسته نیست</div>';return}
  pl.innerHTML=items.map(function(p){
    var flash=p.flash_active,eff=p.effective_price,base=p.price;
    var emoji=p._catEmoji||'📦';
    return '<div class="sl-prod" data-pid="'+p.id+'">'+
      '<div class="sl-pic">'+emoji+'</div>'+
      '<div class="sl-pinfo"><div class="sl-pt">'+esc(p.title)+'</div>'+
        '<div class="sl-pg">'+esc(p._cat||'')+(p._sub?' · '+esc(p._sub):'')+'</div></div>'+
      '<div class="sl-pp">'+
        (flash?'<div class="sl-old">'+fmt(base)+'</div>':'')+
        '<div class="sl-price">'+fmt(eff)+' <small>تومان</small></div>'+
        (flash?'<div class="sl-flash">⚡️ فروش فوری</div>':'')+
        '<span class="sl-buy">مشاهده</span>'+
      '</div></div>';
  }).join('');
}

document.getElementById('cat-chips').addEventListener('click',function(e){
  var ch=e.target.closest('.sl-chip');if(!ch)return;
  document.querySelectorAll('.sl-chip').forEach(function(x){x.classList.remove('on')});
  ch.classList.add('on');
  var slug=ch.dataset.slug;
  if(!slug){renderProds('');return}
  var cat=shopData.find(function(c){return(c.slug||c.name)===slug});
  renderProds(cat?cat.name:'');
});

/* ═══════════════════════════════════════════════════════════════════════ */
/*  پاپ‌آپ محصول                                                          */
/* ═══════════════════════════════════════════════════════════════════════ */
function openProduct(pid){
  var t=document.getElementById('pp-title');
  var b=document.getElementById('pp-body');
  t.textContent='…';b.innerHTML=skel(2);
  app.popup.open('#prod-popup');

  api('/products/'+pid).then(function(d){
    var p=d.product||{};
    t.textContent=p.title||'';
    var flash=p.flash_active,eff=p.effective_price,base=p.price;
    var hasStock=p.stock!=null,inStock=p.stock>0;
    b.innerHTML=
      '<div class="sl-pp-hero">'+
        '<div class="sl-pp-emoji">'+(p.category&&p.category.indexOf('اپل')>=0?'':'📦')+'</div>'+
        '<div class="sl-pp-title">'+esc(p.title)+'</div>'+
        (flash?'<div class="sl-pp-flash"><span class="old">'+fmt(base)+' تومان</span> <span class="tag">⚡️ فروش فوری</span></div>':'')+
        '<div class="sl-pp-price">'+fmt(eff)+' <small>تومان</small></div>'+
      '</div>'+
      (hasStock?'<div class="sl-pp-stock">'+(inStock?'✅ موجود — '+p.stock+' عدد':'❌ ناموجود')+'</div>':'')+
      (p.description?'<div class="sl-pp-desc">'+nl2br(p.description)+'</div>':'')+
      '<a class="sl-pp-btn'+(hasStock&&!inStock?' sl-pp-btn-off':'')+'" href="https://t.me/'+botUser+'?start=buy_'+p.id+'" target="_blank">'+
        (hasStock&&!inStock?'اطلاع‌رسانی موجود شدن':'خرید از ربات')+
      '</a>';
  }).catch(function(){b.innerHTML='<div class="sl-empty"><span class="sl-empty-e">📡</span>خطا در دریافت اطلاعات</div>'});
}

/* ═══════════════════════════════════════════════════════════════════════ */
/*  آموزش / اخبار                                                        */
/* ═══════════════════════════════════════════════════════════════════════ */
var learnLoaded={},learnKind='tutorial';
function loadLearn(kind){
  learnKind=kind;
  if(learnLoaded[kind])return;learnLoaded[kind]=true;
  var box=document.getElementById('learn-list');
  box.innerHTML=skel(2);
  var colors=['linear-gradient(120deg,#101826,#7C3AED)','linear-gradient(120deg,#0F172A,#0A63FF)',
    'linear-gradient(120deg,#1B2B1B,#30D158)','linear-gradient(120deg,#2B1B1B,#FF453A)',
    'linear-gradient(120deg,#1B2B2B,#0A9396)','linear-gradient(120deg,#2B2B1B,#FF9F0A)'];
  var LABELS={tutorial:'📚 آموزش',news:'📰 خبر',feature:'✨ امکانات'};

  api('/content?kind='+encodeURIComponent(kind)+'&limit=50').then(function(d){
    var items=(d&&d.items)||[];
    if(!items.length){
      var msgs={tutorial:['📚','هنوز آموزشی منتشر نشده','به‌زودی آموزش‌های کاربردی قرار می‌گیرد.'],
        news:['📰','هنوز خبری منتشر نشده','اخبار و اطلاعیه‌ها این‌جا نمایش داده می‌شود.'],
        feature:['✨','به‌زودی…','معرفی امکانات ربات این‌جا قرار می‌گیرد.']};
      var m=msgs[kind]||msgs.news;
      box.innerHTML='<div class="sl-empty"><span class="sl-empty-e">'+m[0]+'</span><b>'+m[1]+'</b><br>'+m[2]+'</div>';
      return;
    }
    box.innerHTML=items.map(function(it,i){
      var hasImg=it.image_url&&it.image_url.length>2;
      return '<div class="sl-post" data-cid="'+it.id+'">'+
        '<div class="sl-post-cv" style="background:'+colors[i%colors.length]+'">'+
          '<span class="sl-post-tag">'+(LABELS[kind]||kind)+'</span>'+
          (hasImg?'<img src="'+esc(it.image_url)+'" style="width:100%;height:100%;object-fit:cover;position:absolute;inset:0" alt="">':'')+
        '</div><div class="sl-post-bd"><div class="sl-post-t">'+esc(it.title)+'</div>'+
        '<div class="sl-post-x">'+esc(it.excerpt)+'</div>'+
        '<div class="sl-post-m">'+esc(it.created_at)+'</div></div></div>';
    }).join('');
  }).catch(function(){learnLoaded[kind]=false;box.innerHTML='<div class="sl-empty"><span class="sl-empty-e">📡</span>خطا<br><button class="sl-retry-btn" onclick="window._retryLearn()">تلاش مجدد</button></div>'});
}
window._retryLearn=function(){learnLoaded[learnKind]=false;loadLearn(learnKind)};

document.getElementById('learn-seg').addEventListener('click',function(e){
  var btn=e.target.closest('button');if(!btn)return;
  document.querySelectorAll('#learn-seg button').forEach(function(x){x.classList.remove('on')});
  btn.classList.add('on');
  learnLoaded={};
  loadLearn(btn.dataset.k);
});

function openPost(cid){
  var t=document.getElementById('post-title');
  var b=document.getElementById('post-body');
  t.textContent='…';b.innerHTML=skel(2);
  app.popup.open('#post-popup');
  api('/content/'+cid).then(function(d){
    var it=d.item||{};
    t.textContent=it.title||'';
    b.innerHTML=
      (it.image_url?'<img src="'+esc(it.image_url)+'" alt="">':'')+
      '<div class="sl-postf-title">'+esc(it.title)+'</div>'+
      '<div class="sl-postf-date">'+esc(it.created_at)+'</div>'+
      '<div class="sl-postf-text">'+nl2br(it.body)+'</div>';
  }).catch(function(){b.innerHTML='<div class="sl-empty"><span class="sl-empty-e">📡</span>خطا</div>'});
}

/* ═══════════════════════════════════════════════════════════════════════ */
/*  حساب                                                                  */
/* ═══════════════════════════════════════════════════════════════════════ */
var meLoaded=false;
function loadMe(){
  if(meLoaded)return;meLoaded=true;
  var body=document.getElementById('me-body');
  var nameEl=document.getElementById('me-name');

  if(!initData){
    nameEl.textContent='حساب من';
    body.innerHTML=
      '<div class="sl-login"><div class="sl-login-e">🔐</div>'+
      '<div class="sl-login-t">ورود به حساب</div>'+
      '<div class="sl-login-s">برای مشاهده کیف پول، سفارش‌ها و پنل همکاری<br>از داخل ربات تلگرام وارد شوید.</div>'+
      '<a class="sl-login-btn" href="https://t.me/'+botUser+'?start=app" target="_blank">📱 ورود از ربات تلگرام</a></div>'+
      _meFooter();
    return;
  }

  var uname=(tgUser&&tgUser.first_name)||'کاربر';
  var username=(tgUser&&tgUser.username)||'';
  var initial=uname.charAt(0);
  nameEl.textContent=uname;

  body.innerHTML=
    '<div class="sl-me"><div class="sl-ava">'+esc(initial)+'</div><div>'+
    '<div class="sl-me-n">'+esc(uname)+'</div>'+
    '<div class="sl-me-u">'+(username?'@'+esc(username)+' · ':'')+'ورود خودکار از تلگرام</div></div></div>'+
    '<div class="sl-wallet"><div class="sl-wallet-glow"></div>'+
      '<div class="sl-wallet-l">موجودی کیف پول</div>'+
      '<div class="sl-wallet-b" id="me-balance"><div class="sl-skel" style="margin:0;background:transparent"><div class="b w40" style="height:26px"></div></div></div>'+
      '<div class="sl-wallet-acts">'+
        '<a class="sl-wallet-a" href="https://t.me/'+botUser+'?start=wallet" target="_blank">＋ شارژ</a>'+
        '<a class="sl-wallet-a" href="https://t.me/'+botUser+'?start=card2card" target="_blank">💳 کارت‌به‌کارت</a>'+
      '</div></div>'+
    '<div class="sl-group">'+
      _meRow('#0A63FF','📦','سفارش‌های من','orders','')+
      _meRow('#FF9F0A','🤝','پنل همکاری','partner','<span class="sl-badge" id="me-partner-badge" style="display:none">فعال</span>')+
      _meRow('#30D158','🎁','دعوت دوستان','invite','')+
      _meRow('#8E8E93','💬','پشتیبانی','support','')+
    '</div>'+_meFooter();

  api('/me/wallet',true).then(function(d){
    var el=document.getElementById('me-balance');
    if(el)el.innerHTML=fmt(d.balance||0)+' <small>تومان</small>';
  }).catch(function(){var el=document.getElementById('me-balance');if(el)el.textContent='—'});

  api('/me/partner',true).then(function(d){
    if(d.is_partner){var b=document.getElementById('me-partner-badge');if(b)b.style.display=''}
  }).catch(function(){});
}
function _meRow(color,icon,label,cmd,extra){
  return '<a class="sl-row" href="https://t.me/'+botUser+'?start='+cmd+'" target="_blank">'+
    '<span class="sl-ric" style="background:'+color+'">'+icon+'</span>'+
    '<span class="sl-row-grow">'+label+'</span>'+extra+
    '<span class="sl-chev">‹</span></a>';
}
function _meFooter(){
  return '<div class="sl-group" style="margin-top:12px">'+
    '<a class="sl-row" href="https://t.me/'+botUser+'" target="_blank">'+
      '<span class="sl-ric" style="background:#54A9EB">🤖</span>'+
      '<span class="sl-row-grow">باز کردن ربات</span><span class="sl-chev">‹</span></a></div>'+
    '<div class="sl-foot">استوک‌لند · نسخه ۲.۰</div>';
}

/* ═══════════════════════════════════════════════════════════════════════ */
/*  جستجو                                                                 */
/* ═══════════════════════════════════════════════════════════════════════ */
document.getElementById('search-bar').addEventListener('click',function(){
  app.dialog.prompt('جستجو در محصولات و آموزش‌ها','جستجو',function(q){
    q=(q||'').trim().toLowerCase();if(!q)return;
    // فیلتر محصولات
    var results=allProds.filter(function(p){return(p.title||'').toLowerCase().indexOf(q)>=0||(p._cat||'').toLowerCase().indexOf(q)>=0});
    if(results.length){
      // نمایش نتایج در تب فروشگاه
      var link=document.querySelector('.tab-link[href="#tab-shop"]');if(link)link.click();
      setTimeout(function(){
        document.querySelectorAll('.sl-chip').forEach(function(x){x.classList.remove('on')});
        var pl=document.getElementById('prod-list');
        pl.innerHTML=results.map(function(p){
          var flash=p.flash_active,eff=p.effective_price,base=p.price,emoji=p._catEmoji||'📦';
          return '<div class="sl-prod" data-pid="'+p.id+'">'+
            '<div class="sl-pic">'+emoji+'</div>'+
            '<div class="sl-pinfo"><div class="sl-pt">'+esc(p.title)+'</div>'+
            '<div class="sl-pg">'+esc(p._cat||'')+'</div></div>'+
            '<div class="sl-pp">'+
              (flash?'<div class="sl-old">'+fmt(base)+'</div>':'')+
              '<div class="sl-price">'+fmt(eff)+' <small>تومان</small></div>'+
              '<span class="sl-buy">مشاهده</span></div></div>';
        }).join('');
      },100);
    }else{
      app.dialog.alert('نتیجه‌ای یافت نشد — کلمه‌ی دیگری امتحان کنید.','جستجو');
    }
  });
});

/* ═══════════════════════════════════════════════════════════════════════ */
/*  رویدادها                                                               */
/* ═══════════════════════════════════════════════════════════════════════ */
app.on('tabShow',function(el){
  var id=el&&el.id;
  if(id==='tab-home')loadHome();
  if(id==='tab-shop')loadShop();
  if(id==='tab-learn'){var k=document.querySelector('#learn-seg button.on');loadLearn(k?k.dataset.k:'tutorial')}
  if(id==='tab-me')loadMe();
});

// pull-to-refresh
app.on('ptrRefresh',function(el,done){
  var tab=document.querySelector('.tab.tab-active');
  if(!tab){done();return}
  var id=tab.id;
  if(id==='tab-home'){homeLoaded=false;loadHome()}
  if(id==='tab-shop'){shopLoaded=false;loadShop()}
  if(id==='tab-learn'){learnLoaded={};loadLearn(learnKind)}
  if(id==='tab-me'){meLoaded=false;loadMe()}
  setTimeout(done,600);
});

// کلیک‌ها
document.addEventListener('click',function(e){
  var prod=e.target.closest('[data-pid]');
  if(prod){openProduct(prod.dataset.pid);return}
  var post=e.target.closest('[data-cid]');
  if(post){openPost(post.dataset.cid);return}
  var tabNav=e.target.closest('[data-tab]');
  if(tabNav){e.preventDefault();var link=document.querySelector('.tab-link[href="#'+tabNav.dataset.tab+'"]');if(link)link.click()}
});

/* ── SW ── */
if('serviceWorker' in navigator)window.addEventListener('load',function(){navigator.serviceWorker.register('sw.js').catch(function(){})});

/* ── بنر نصب ── */
var standalone=window.matchMedia('(display-mode:standalone)').matches||window.navigator.standalone===true;
var dismissed=false;try{dismissed=sessionStorage.getItem('sl-hint-off')==='1'}catch(e){}
if(!inTG&&!standalone&&!dismissed){
  var hint=document.getElementById('install-hint');
  var btn=document.getElementById('install-btn');
  var txt=document.getElementById('install-hint-text');
  var dp=null;
  window.addEventListener('beforeinstallprompt',function(e){e.preventDefault();dp=e;btn.style.display='';txt.textContent='با یک لمس نصب کنید'});
  btn.addEventListener('click',function(){if(!dp)return;dp.prompt();dp=null;hint.style.display='none'});
  if(/iphone|ipad|ipod/i.test(navigator.userAgent))txt.innerHTML='در سافاری: دکمه <b>Share</b> → <b>Add to Home Screen</b>';
  hint.style.display='';
  document.getElementById('install-close').addEventListener('click',function(){hint.style.display='none';try{sessionStorage.setItem('sl-hint-off','1')}catch(e){}});
}
})();
