(function(){
'use strict';
var reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
var $=function(s,r){return (r||document).querySelector(s)},$$=function(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s))};

/* ---- CSRF: add the token to every POST form ---- */
var meta=$('meta[name="csrf-token"]'),token=meta?meta.content:'';
$$('form').forEach(function(f){
  if((f.getAttribute('method')||'get').toLowerCase()!=='post'||f.querySelector('input[name="_csrf"]'))return;
  var i=document.createElement('input');i.type='hidden';i.name='_csrf';i.value=token;f.appendChild(i);
});

/* ---- ambient particles (quiet, two-tone) ---- */
var c=$('#fx');
if(c&&!reduce){
  var x=c.getContext('2d'),w,h,P=[],M={x:-999,y:-999},cols=['#4f8cff','#22d3ee','#7c6cff','#e8b86a'];
  var size=function(){w=c.width=innerWidth;h=c.height=innerHeight;P=[];var n=Math.min(70,Math.floor(w*h/22000));
    for(var i=0;i<n;i++)P.push({x:Math.random()*w,y:Math.random()*h,vx:(Math.random()-.5)*.28,vy:(Math.random()-.5)*.28,r:Math.random()*1.5+.5,c:cols[i%cols.length],t:Math.random()*6})};
  addEventListener('resize',size);addEventListener('mousemove',function(e){M.x=e.clientX;M.y=e.clientY});size();
  (function loop(){
    if(document.hidden){requestAnimationFrame(loop);return}
    x.clearRect(0,0,w,h);
    for(var i=0;i<P.length;i++){var p=P[i];p.x+=p.vx;p.y+=p.vy;p.t+=.025;
      if(p.x<0||p.x>w)p.vx*=-1;if(p.y<0||p.y>h)p.vy*=-1;
      var dx=p.x-M.x,dy=p.y-M.y,d=Math.hypot(dx,dy);if(d<120&&d>0){p.x+=dx/d*1.1;p.y+=dy/d*1.1}
      x.shadowBlur=10;x.shadowColor=p.c;x.fillStyle=p.c;x.globalAlpha=.75;x.beginPath();x.arc(p.x,p.y,p.r*(1+Math.sin(p.t)*.2),0,6.3);x.fill();
      x.shadowBlur=0;
      for(var j=i+1;j<P.length;j++){var q=P[j],l=Math.hypot(p.x-q.x,p.y-q.y);
        if(l<120){x.globalAlpha=(1-l/120)*.22;x.strokeStyle=p.c;x.lineWidth=1;x.beginPath();x.moveTo(p.x,p.y);x.lineTo(q.x,q.y);x.stroke()}}}
    x.globalAlpha=1;requestAnimationFrame(loop)})();
}

/* ---- cursor spotlight ---- */
var sp=$('#spot');
if(sp)addEventListener('mousemove',function(e){sp.style.left=e.clientX+'px';sp.style.top=e.clientY+'px';sp.style.setProperty('--h',Math.round((e.clientX/innerWidth)*70+190))});

/* ---- count-up ---- */
$$('[data-count]').forEach(function(el){
  var t=+el.dataset.count||0,s=performance.now();
  if(reduce){el.textContent=t;return}
  (function f(n){var k=Math.min((n-s)/1000,1);el.textContent=Math.round(t*(1-Math.pow(1-k,3)));if(k<1)requestAnimationFrame(f)})(s);
});

/* ---- gentle 3D tilt on stat cards ---- */
if(!reduce)$$('.stat,.hero-box').forEach(function(el){
  el.addEventListener('mousemove',function(e){var r=el.getBoundingClientRect();
    el.style.transform='perspective(900px) rotateX('+(((e.clientY-r.top)/r.height-.5)*-5)+'deg) rotateY('+(((e.clientX-r.left)/r.width-.5)*5)+'deg) translateY(-3px)'});
  el.addEventListener('mouseleave',function(){el.style.transform=''});
});

/* ---- button ripple ---- */
document.addEventListener('click',function(e){
  var b=e.target.closest('.btn');if(!b)return;
  var r=b.getBoundingClientRect(),d=Math.max(r.width,r.height),s=document.createElement('span');
  s.className='rip';s.style.cssText='width:'+d+'px;height:'+d+'px;left:'+(e.clientX-r.left-d/2)+'px;top:'+(e.clientY-r.top-d/2)+'px';
  b.appendChild(s);setTimeout(function(){s.remove()},700);
});

/* ---- dialogs ---- */
document.addEventListener('click',function(e){
  var o=e.target.closest('[data-dialog]');
  if(o){var d=document.getElementById(o.getAttribute('data-dialog'));if(d&&d.showModal){d.showModal();var f=d.querySelector('input:not([type=hidden]),textarea');if(f)f.focus()}return}
  if(e.target.closest('[data-close]')){var dd=e.target.closest('dialog');if(dd)dd.close();return}
  if(e.target.tagName==='DIALOG'){var r=e.target.getBoundingClientRect();
    if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close()}
});

/* ---- confirm before destructive actions ---- */
var box=$('#confirmBox'),pending=null;
function ask(msg,go){pending=go;$('#confirmText').textContent=msg;box.showModal()}
if(box){
  $('#confirmOk').addEventListener('click',function(){var g=pending;pending=null;box.close();if(g)g()});
  box.addEventListener('close',function(){pending=null});
  document.addEventListener('submit',function(e){
    var f=e.target;if(!f.hasAttribute||!f.hasAttribute('data-confirm')||f.__ok)return;
    e.preventDefault();var sub=e.submitter;
    ask(f.getAttribute('data-confirm'),function(){f.__ok=true;sub?f.requestSubmit(sub):f.requestSubmit()});
  },true);
  document.addEventListener('click',function(e){
    var b=e.target.closest('button[data-confirm]');if(!b||!b.form||b.__ok)return;
    e.preventDefault();
    ask(b.getAttribute('data-confirm'),function(){b.__ok=true;b.form.requestSubmit(b)});
  });
}

/* ---- toasts ---- */
$$('.flash').forEach(function(t){
  var close=function(){t.classList.add('out');setTimeout(function(){t.remove()},400)};
  var x=t.querySelector('.x');if(x)x.addEventListener('click',close);
  setTimeout(close,t.classList.contains('error')?9000:5500);
});

/* ---- mobile menu ---- */
var mb=$('#menuBtn'),sc=$('#scrim');
if(mb)mb.addEventListener('click',function(){document.body.classList.toggle('nav-open')});
if(sc)sc.addEventListener('click',function(){document.body.classList.remove('nav-open')});

/* ---- insert canned reply ---- */
document.addEventListener('click',function(e){
  var b=e.target.closest('[data-insert-target]');if(!b)return;
  var t=document.getElementById(b.getAttribute('data-insert-target'));if(!t)return;
  t.value=(t.value?t.value.replace(/\s+$/,'')+'\n\n':'')+b.getAttribute('data-text');t.focus();
});

/* ---- character counter ---- */
$$('[data-counter]').forEach(function(t){
  var o=$(t.getAttribute('data-counter')),u=function(){if(o)o.textContent=t.value.length};
  t.addEventListener('input',u);u();
});
})();
