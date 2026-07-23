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
      dp=document.getElementById('daily-post'),hc=document.getElementById('home-cats');

  // دسته‌بندی‌ها
  api('/categories').then(function(d){
    cats=(d&&d.categories)||[];prods=[];
    cats.forEach(function(c){
      (c.products||[]).forEach(function(p){p._c=c.name;p._e=c.emoji;prods.push(p)});
      (c.subcategories||[]).forEach(function(s){
        (s.products||[]).forEach(function(p){p._c=c.name;p._e=c.emoji;p._s=s.name;prods.push(p)});
      });
    });
    renderCircles(hc,false);
    // کلیک دایره‌ها → تب فروشگاه
    hc.addEventListener('click',function(e){
      var c=e.target.closest('.sl-cat-c');if(!c)return;
      var lnk=document.querySelector('.tab-link[href="#tab-shop"]');if(lnk)lnk.click();
      setTimeout(function(){
        var slug=c.dataset.slug||c.dataset.name;
        document.querySelectorAll('#shop-cats .sl-cat-c').forEach(function(x){
          x.classList.toggle('on',(x.dataset.slug||x.dataset.name)===slug||(x.dataset.name==='همه'&&!slug));
        });
        renderP(c.dataset.name==='همه'?'':c.dataset.name);
      },100);
    });
    // فروشگاه هم آماده بشه
    var sc=document.getElementById('shop-cats');
    renderCircles(sc,true);
    document.getElementById('shop-count').textContent=prods.length+' محصول فعال';
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
  var colors=['linear-gradient(120deg,#123,#0A63FF)','linear-gradient(120deg,#1B2B1B,#22C55E)',
    'linear-gradient(120deg,#2B1B2B,#A855F7)','linear-gradient(120deg,#2B1B1B,#EF4444)',
    'linear-gradient(120deg,#1B2B2B,#06B6D4)','linear-gradient(120deg,#2B2B1B,#F59E0B)'];
  api('/content?kind=news&limit=6').then(function(d){
    var it=(d&&d.items)||[];if(!it.length){nr.innerHTML='';return}
    nr.innerHTML=it.map(function(p,i){
      return '<div class="sl-mini" data-cid="'+p.id+'"><div class="sl-mini-cv" style="background:'+colors[i%colors.length]+'">'+
        (p.image_url?'<img src="'+esc(p.image_url)+'" alt="">':'📰')+'</div>'+
        '<div class="sl-mini-b"><div class="sl-mini-t">'+esc(p.title)+'</div><div class="sl-mini-m">'+esc(p.created_at)+'</div></div></div>';
    }).join('');
  }).catch(function(){nr.innerHTML=''});
}
window.loadHome=loadHome;loadHome();

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
  t.textContent='…';b.innerHTML=skel(2);app.popup.open('#prod-popup'); setTimeout(function(){ var cb=document.querySelector('[data-checkout]'); if(cb) cb.addEventListener('click',function(){openCheckout(cb.dataset.checkout)}); },300);
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
        app.dialog.create({title:'پرداخت امن',text:'⚠️ لطفاً قبل از ورود به درگاه، فیلترشکن (VPN) خود را خاموش کنید؛ درگاه بانکی با فیلترشکن روشن پرداخت را رد می‌کند. پس از پرداخت موفق، سفارش به‌صورت خودکار ثبت می‌شود.',buttons:[{text:'انصراف'},{text:'ادامه به درگاه',bold:true,onClick:function(){_slGo()}}]}).open();
        function _slGo(){
        bn.textContent='⏳ صبر کنید...';bn.disabled=true;
        fetch('https://panel.stland.ir/api/v1/checkout',{
          method:'POST',
          headers:{'Content-Type':'application/json','X-Telegram-Init-Data':initData},
          body:JSON.stringify({product_id:p.id,payment_type:'gateway'})
        }).then(function(r){return r.json()}).then(function(d){
          if(d.redirect_url){if(tg&&tg.openLink)tg.openLink(d.redirect_url);else window.open(d.redirect_url,'_blank');}
          else if(d.method==='wallet'){bn.textContent='✅ خرید موفق!';}
          else{alert(d.detail||'خطا');bn.textContent='🛒 خرید از اپ';bn.disabled=false;}
        }).catch(function(err){alert('خطا: '+err.message);bn.textContent='🛒 خرید از اپ';bn.disabled=false;});
        }
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
    '<div class="sl-wallet-acts"><a class="sl-wallet-a" href="#" onclick="openWallet();return false">＋ شارژ</a>'+
    '<a class="sl-wallet-a" href="#" onclick="openC2C();return false">💳 کارت‌به‌کارت</a></div></div>'+
    '<div class="sl-group">'+row('#0A63FF','📦','سفارش‌های من','orders','')+
    '<a class="sl-row" href="#" onclick="openPartner();return false"><span class="sl-ric" style="background:#F59E0B">🤝</span><span class="sl-row-grow">پنل همکاری</span><span class="sl-badge" id="me-pb" style="display:none">فعال</span><span class="sl-chev">‹</span></a>'+
    '<a class="sl-row" href="#" onclick="openInvite();return false"><span class="sl-ric" style="background:#22C55E">🎁</span><span class="sl-row-grow">دعوت دوستان</span><span class="sl-chev">‹</span></a>'+'<a class="sl-row" href="#" onclick="openSupport();return false"><span class="sl-ric" style="background:#6B7280">💬</span><span class="sl-row-grow">پشتیبانی</span><span class="sl-chev">‹</span></a>'+'</div>'+foot;
  api('/me/wallet',true).then(function(d){var e=document.getElementById('me-bal');if(e)e.innerHTML=fmt(d.balance||0)+' <small>تومان</small>'}).catch(function(){var e=document.getElementById('me-bal');if(e)e.textContent='—'});
  api('/me/partner',true).then(function(d){if(d.is_partner){var b=document.getElementById('me-pb');if(b)b.style.display=''}}).catch(function(){});
}
window.loadMe=loadMe;
/* === صفحات حساب داخل اپ === */
function _accPopup(title,html){
  var pp=document.getElementById('post-popup');
  document.getElementById('post-title').textContent=title;
  document.getElementById('post-body').innerHTML='<div class="sl-acc-page">'+html+'</div>';
  app.popup.open('#post-popup');
}

function openWallet(){
  _accPopup('کیف پول','<div class="sl-skel"><div class="b w60"></div><div class="b w90"></div></div>');
  api('/me/wallet',true).then(function(d){
    var h='<div class="sl-wal-big">'+fmt(d.balance||0)+' <small>تومان</small></div>';
    h+='<div class="sl-wal-acts"><button class="sl-wal-charge" onclick="startCharge()">＋ شارژ کیف پول</button>';
    h+='<button class="sl-wal-c2c" onclick="openC2C()">💳 کارت‌به‌کارت</button></div>';
    if(d.transactions&&d.transactions.length){
      h+='<div class="sl-wal-txs">';
      d.transactions.forEach(function(t){
        var cls=t.amount>0?'plus':'minus';
        h+='<div class="sl-wal-tx"><div><div class="sl-wal-tx-t">'+esc(t.description||t.type||'تراکنش')+'</div>';
        h+='<div class="sl-wal-tx-d">'+esc(t.created_at||'')+'</div></div>';
        h+='<div class="sl-wal-tx-a '+cls+'">'+fmt(Math.abs(t.amount))+' ت</div></div>';
      });
      h+='</div>';
    }
    document.getElementById('post-body').querySelector('.sl-acc-page').innerHTML=h;
  }).catch(function(){
    document.getElementById('post-body').querySelector('.sl-acc-page').innerHTML='<div class="sl-acc-empty"><span>📡</span>خطا در دریافت اطلاعات</div>';
  });
}
window.openWallet=openWallet;

function startCharge(){
  app.dialog.prompt('مبلغ شارژ به تومان','شارژ کیف پول',function(val){
    var amount=parseInt((val||'').replace(/[^0-9]/g,''));
    if(!amount||amount<10000){app.dialog.alert('حداقل مبلغ شارژ ۱۰,۰۰۰ تومان است');return}
    fetch('/api/v1/checkout',{
      method:'POST',
      headers:{'Content-Type':'application/json','X-Telegram-Init-Data':initData},
      body:JSON.stringify({product_id:0,payment_type:'gateway',charge_amount:amount})
    }).then(function(r){return r.json()}).then(function(d){
      if(d.redirect_url){
        app.dialog.create({title:'پرداخت امن',
          text:'⚠️ لطفاً فیلترشکن (VPN) را خاموش کنید.',
          buttons:[{text:'انصراف'},{text:'ادامه',bold:true,onClick:function(){
            if(tg&&tg.openLink)tg.openLink(d.redirect_url);else window.open(d.redirect_url,'_blank');
          }}]}).open();
      }else{app.dialog.alert(d.detail||'خطا');}
    }).catch(function(){app.dialog.alert('خطای شبکه');});
  });
}
window.startCharge=startCharge;

function openC2C(){
  _accPopup('کارت\u200cبه\u200cکارت',
    '<div style="text-align:center;padding:20px 0">'+
    '<span style="font-size:48px">💳</span>'+
    '<p style="margin:16px 0;font-size:15px;font-weight:700">واریز به کارت زیر:</p>'+
    '<div style="direction:ltr;font-size:22px;font-weight:800;letter-spacing:2px;padding:16px;background:var(--card);border-radius:14px;box-shadow:var(--sh)">6037-9975-xxxx-xxxx</div>'+
    '<p style="margin-top:12px;font-size:13px;color:var(--mu)">به نام: فیروز آیازی</p>'+
    '<p style="margin-top:16px;font-size:13px;color:var(--mu);line-height:1.8">پس از واریز، رسید را از طریق<br>بخش پشتیبانی ارسال کنید.</p>'+
    '<button class="sl-inv-btn" onclick="openSupport()">💬 ارسال رسید</button>'+
    '</div>');
}
window.openC2C=openC2C;

function openOrders(){
  _accPopup('سفارش‌های من','<div class="sl-skel"><div class="b w90"></div><div class="b w60"></div></div>');
  api('/me/orders?limit=20',true).then(function(d){
    var ords=d.orders||[];
    if(!ords.length){
      document.getElementById('post-body').querySelector('.sl-acc-page').innerHTML='<div class="sl-acc-empty"><span>📦</span>هنوز سفارشی ثبت نشده</div>';
      return;
    }
    var h='<div class="sl-acc-title">سفارش‌های من</div>';
    ords.forEach(function(o){
      var st=o.status||'pending';
      var cls=st==='completed'||st==='delivered'?'done':st==='cancelled'?'cancel':'pending';
      var lb=st==='completed'||st==='delivered'?'تحویل شده':st==='cancelled'?'لغو شده':'در انتظار';
      h+='<div class="sl-ord"><div class="sl-ord-top"><span class="sl-ord-id">#'+o.id+'</span>';
      h+='<span class="sl-ord-st '+cls+'">'+lb+'</span></div>';
      h+='<div class="sl-ord-name">'+esc(o.product_title||o.title||'محصول')+'</div>';
      h+='<div class="sl-ord-price">'+fmt(o.amount||0)+' تومان</div>';
      h+='<div class="sl-ord-date">'+esc(o.created_at||'')+'</div></div>';
    });
    document.getElementById('post-body').querySelector('.sl-acc-page').innerHTML=h;
  }).catch(function(){
    document.getElementById('post-body').querySelector('.sl-acc-page').innerHTML='<div class="sl-acc-empty"><span>📡</span>خطا</div>';
  });
}
window.openOrders=openOrders;

function openPartner(){
  _accPopup('پنل همکاری','<div class="sl-skel"><div class="b w60"></div><div class="b w90"></div></div>');
  api('/me/partner',true).then(function(d){
    var h='<div class="sl-acc-title">پنل همکاری</div>';
    if(!d.is_partner){
      h+='<div class="sl-acc-empty"><span>🤝</span>شما هنوز همکار نیستید<br><small style="color:var(--mu)">برای ثبت‌نام همکاری با پشتیبانی تماس بگیرید</small></div>';
      h+='<button class="sl-inv-btn" onclick="openSupport()">💬 تماس با پشتیبانی</button>';
    }else{
      h+='<div class="sl-prt-card">';
      h+='<div class="sl-prt-row"><span class="sl-prt-k">وضعیت</span><span class="sl-prt-v" style="color:#22C55E">✅ فعال</span></div>';
      h+='<div class="sl-prt-row"><span class="sl-prt-k">سطح</span><span class="sl-prt-v">'+(d.tier||'پایه')+'</span></div>';
      h+='<div class="sl-prt-row"><span class="sl-prt-k">موجودی همکاری</span><span class="sl-prt-v">'+fmt(d.balance||0)+' ت</span></div>';
      h+='<div class="sl-prt-row"><span class="sl-prt-k">تعداد دعوت</span><span class="sl-prt-v">'+(d.referrals?d.referrals.total:0)+'</span></div>';
      h+='<div class="sl-prt-row"><span class="sl-prt-k">درآمد از دعوت</span><span class="sl-prt-v">'+fmt(d.referrals?d.referrals.earned:0)+' ت</span></div>';
      h+='</div>';
    }
    document.getElementById('post-body').querySelector('.sl-acc-page').innerHTML=h;
  }).catch(function(){
    document.getElementById('post-body').querySelector('.sl-acc-page').innerHTML='<div class="sl-acc-empty"><span>📡</span>خطا</div>';
  });
}
window.openPartner=openPartner;

function openInvite(){
  var code=tgUser?tgUser.id:'';
  var link='https://t.me/'+botUser+'?start=ref_'+code;
  _accPopup('دعوت دوستان',
    '<div class="sl-acc-title">دعوت دوستان</div>'+
    '<div style="text-align:center;font-size:48px;margin:16px 0">🎁</div>'+
    '<p style="text-align:center;font-size:14px;color:var(--mu);line-height:1.8;margin-bottom:16px">با دعوت دوستان، هر دو هدیه دریافت کنید!</p>'+
    '<div class="sl-inv-code">لینک دعوت شما:<b>'+esc(link)+'</b></div>'+
    '<button class="sl-inv-btn" onclick="copyInvite()">📋 کپی لینک دعوت</button>');
}
window.openInvite=openInvite;

function copyInvite(){
  var code=tgUser?tgUser.id:'';
  var link='https://t.me/'+botUser+'?start=ref_'+code;
  if(navigator.clipboard){navigator.clipboard.writeText(link).then(function(){app.dialog.alert('لینک کپی شد!')})}
  else{app.dialog.alert(link)}
}
window.copyInvite=copyInvite;

function openSupport(){
  _accPopup('پشتیبانی',
    '<div class="sl-acc-title">پشتیبانی</div>'+
    '<div class="sl-sup-item" onclick="openTicket()">'+
      '<span class="sl-sup-ic">📝</span><div><div class="sl-sup-t">ارسال پیام</div><div class="sl-sup-s">پیام خود را مستقیم ارسال کنید</div></div></div>'+
    '<div class="sl-sup-item" onclick="openFAQ()">'+
      '<span class="sl-sup-ic">❓</span><div><div class="sl-sup-t">سوالات متداول</div><div class="sl-sup-s">پاسخ سریع به سوالات رایج</div></div></div>');
}
window.openSupport=openSupport;

function openTicket(){
  _accPopup('ارسال پیام',
    '<div class="sl-acc-title">پیام به پشتیبانی</div>'+
    '<textarea id="sup-msg" rows="5" placeholder="پیام خود را بنویسید..." style="width:100%;box-sizing:border-box;border:2px solid var(--ln);border-radius:14px;padding:14px;font-family:inherit;font-size:14px;resize:none;background:var(--card);color:var(--ink)"></textarea>'+
    '<button class="sl-inv-btn" onclick="sendTicket()">📤 ارسال</button>');
}
window.openTicket=openTicket;

function sendTicket(){
  var msg=document.getElementById('sup-msg');
  if(!msg||!msg.value.trim()){app.dialog.alert('لطفا پیام خود را بنویسید');return}
  app.dialog.alert('پیام شما ارسال شد. به زودی پاسخ داده می\u200cشود.','ارسال شد');
  app.popup.close('#post-popup');
}
window.sendTicket=sendTicket;

function openFAQ(){
  _accPopup('سوالات متداول',
    '<div class="sl-acc-title">سوالات متداول</div>'+
    '<div class="sl-prt-card"><div class="sl-prt-row" style="display:block"><b>چطور خرید کنم؟</b><p style="margin-top:6px;font-size:13px;color:var(--mu);line-height:1.7">از تب فروشگاه محصول مورد نظر را انتخاب و روی دکمه خرید بزنید.</p></div></div>'+
    '<div class="sl-prt-card"><div class="sl-prt-row" style="display:block"><b>کیف پول چیست؟</b><p style="margin-top:6px;font-size:13px;color:var(--mu);line-height:1.7">با شارژ کیف پول می\u200cتوانید سریع\u200cتر خرید کنید بدون نیاز به درگاه بانکی.</p></div></div>'+
    '<div class="sl-prt-card"><div class="sl-prt-row" style="display:block"><b>گارانتی چطور کار می\u200cکنه؟</b><p style="margin-top:6px;font-size:13px;color:var(--mu);line-height:1.7">تمام محصولات دارای گارانتی هستند. در صورت مشکل با پشتیبانی تماس بگیرید.</p></div></div>');
}
window.openFAQ=openFAQ;


// لینک‌های صفحه حساب — WKWebView تلگرام target=_blank رو نمی‌شناسه
document.addEventListener('click',function(e){
  var a=e.target.closest('#me-body a[href], .sl-login-btn, .sl-wallet-a');
  if(!a)return;
  var url=a.getAttribute('href');
  if(!url||url==='#')return;
  e.preventDefault();
  if(tg&&tg.openLink){tg.openLink(url)}
  else{window.open(url,'_blank')}
});

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
var _checkoutPid=0,_checkoutProd=null;

function openCheckout(pid){
  _checkoutPid=pid;
  var b=document.getElementById('checkout-body');
  b.innerHTML='<div class="sl-skel" style="margin:20px"><div class="b w60"></div><div class="b w90"></div><div class="b w40"></div></div>';
  app.popup.open('#checkout-popup');

  Promise.all([
    api('/products/'+pid),
    api('/me/wallet',true)
  ]).then(function(res){
    var p=res[0].product||{}, walBal=res[1].balance||0;
    _checkoutProd=p;
    var price=p.effective_price||p.price||0;
    var canWallet=walBal>=price;
    var canCombined=walBal>0&&walBal<price;
    var emoji=p._e||'📦';

    var btns='';
    if(canWallet){
      btns+='<button class="sl-checkout-btn sl-checkout-btn-wallet" onclick="_doPay(\'wallet\')">👛 پرداخت از کیف‌پول ('+fmt(price)+' تومان)</button>';
    }
    if(canCombined){
      var gw=price-walBal;
      btns+='<button class="sl-checkout-btn sl-checkout-btn-combined" onclick="_doPay(\'combined\')">'+
        '💳 پرداخت ترکیبی (کیف‌پول '+fmt(walBal)+' + درگاه '+fmt(gw)+' تومان)</button>';
    }
    btns+='<button class="sl-checkout-btn sl-checkout-btn-gateway" onclick="_doPay(\'gateway\')">🌐 پرداخت کامل از درگاه ('+fmt(price)+' تومان)</button>';

    b.innerHTML=
      '<div class="sl-checkout-prod">'+
        '<div class="sl-checkout-emoji">'+esc(emoji)+'</div>'+
        '<div><div class="sl-checkout-title">'+esc(p.title)+'</div>'+
        '<div class="sl-checkout-price">قیمت: <b>'+fmt(price)+' تومان</b></div></div>'+
      '</div>'+
      '<div class="sl-checkout-sec">موجودی کیف‌پول شما</div>'+
      '<div class="sl-checkout-wallet">'+
        '<div class="sl-checkout-wallet-info">کیف پول</div>'+
        '<div class="sl-checkout-wallet-bal">'+fmt(walBal)+' تومان</div>'+
      '</div>'+
      '<div class="sl-checkout-sec">روش پرداخت</div>'+
      '<div class="sl-checkout-btns" id="checkout-btns">'+btns+'</div>'+
      '<div class="sl-checkout-note">بعد از تایید پرداخت، سفارش شما<br>به‌صورت خودکار ثبت و ارسال می‌شود.</div>';
  }).catch(function(){
    b.innerHTML='<div class="sl-empty"><span class="sl-empty-e">📡</span>خطا در دریافت اطلاعات</div>';
  });
}

window.openCheckout=openCheckout;

window._doPay=function(method){
  var btns=document.getElementById('checkout-btns');
  if(btns) btns.querySelectorAll('button').forEach(function(x){x.disabled=true;x.textContent='⏳ در حال پردازش...'});

  api('/checkout',true).then(function(){}).catch(function(){});// warming
  fetch('https://panel.stland.ir/api/v1/checkout',{
    method:'POST',
    headers:{'Content-Type':'application/json','X-Telegram-Init-Data':initData},
    body:JSON.stringify({product_id:_checkoutPid,payment_type:method})
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
