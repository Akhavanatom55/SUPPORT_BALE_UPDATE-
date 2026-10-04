(function(){
var reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;

/* particles + constellation + shooting stars */
var c=document.getElementById('fx');
if(c&&!reduce){
var x=c.getContext('2d'),w,h,P=[],S=[],M={x:-999,y:-999},cols=['#00f0ff','#8b5cf6','#ff2bd6','#ffb02e','#3dffa0'];
function rs(){w=c.width=innerWidth;h=c.height=innerHeight;P=[];var n=Math.min(110,Math.floor(w*h/15000));
for(var i=0;i<n;i++)P.push({x:Math.random()*w,y:Math.random()*h,vx:(Math.random()-.5)*.5,vy:(Math.random()-.5)*.5,r:Math.random()*1.9+.6,c:cols[i%cols.length],t:Math.random()*6})}
addEventListener('resize',rs);addEventListener('mousemove',function(e){M.x=e.clientX;M.y=e.clientY});rs();
function shoot(){S.push({x:Math.random()*w,y:Math.random()*h*.4,vx:-(6+Math.random()*5),vy:3+Math.random()*3,l:0,c:cols[Math.floor(Math.random()*cols.length)]})}
setInterval(function(){if(!document.hidden&&Math.random()<.7)shoot()},2600);
(function loop(){x.clearRect(0,0,w,h);
for(var i=0;i<P.length;i++){var p=P[i];p.x+=p.vx;p.y+=p.vy;p.t+=.03;
if(p.x<0||p.x>w)p.vx*=-1;if(p.y<0||p.y>h)p.vy*=-1;
var dx=p.x-M.x,dy=p.y-M.y,d=Math.hypot(dx,dy);if(d<130&&d>0){p.x+=dx/d*1.5;p.y+=dy/d*1.5}
x.beginPath();x.arc(p.x,p.y,p.r*(1+Math.sin(p.t)*.25),0,6.3);x.fillStyle=p.c;x.shadowBlur=14;x.shadowColor=p.c;x.fill();
for(var j=i+1;j<P.length;j++){var q=P[j],l=Math.hypot(p.x-q.x,p.y-q.y);
if(l<125){x.shadowBlur=0;x.strokeStyle=p.c+Math.floor((1-l/125)*60).toString(16).padStart(2,'0');x.lineWidth=1;x.beginPath();x.moveTo(p.x,p.y);x.lineTo(q.x,q.y);x.stroke()}}}
for(var k=S.length-1;k>=0;k--){var s=S[k];s.x+=s.vx;s.y+=s.vy;s.l++;
var g=x.createLinearGradient(s.x,s.y,s.x-s.vx*9,s.y-s.vy*9);g.addColorStop(0,s.c);g.addColorStop(1,'transparent');
x.shadowBlur=14;x.shadowColor=s.c;x.strokeStyle=g;x.lineWidth=2;x.beginPath();x.moveTo(s.x,s.y);x.lineTo(s.x-s.vx*9,s.y-s.vy*9);x.stroke();
if(s.l>110||s.x<-50||s.y>h+50)S.splice(k,1)}
requestAnimationFrame(loop)})();
}

/* cursor spotlight with shifting hue */
var sp=document.getElementById('spot');
if(sp)addEventListener('mousemove',function(e){sp.style.left=e.clientX+'px';sp.style.top=e.clientY+'px';
sp.style.setProperty('--h',Math.round((e.clientX/innerWidth)*160+170))});

/* count-up numbers */
document.querySelectorAll('[data-count]').forEach(function(el){
var t=+el.dataset.count||0,s=performance.now();
(function f(n){var k=Math.min((n-s)/1100,1);el.textContent=Math.round(t*(1-Math.pow(1-k,3)));if(k<1)requestAnimationFrame(f)})(s)});

/* 3D tilt */
if(!reduce)document.querySelectorAll('.stat,.feature,.hero-box,.center-card').forEach(function(el){
el.addEventListener('mousemove',function(e){var r=el.getBoundingClientRect();
el.style.transform='perspective(900px) rotateX('+(((e.clientY-r.top)/r.height-.5)*-6)+'deg) rotateY('+(((e.clientX-r.left)/r.width-.5)*6)+'deg) translateZ(0)'});
el.addEventListener('mouseleave',function(){el.style.transform=''})});

/* button ripple */
document.addEventListener('click',function(e){var b=e.target.closest('button,.button');if(!b)return;
var r=b.getBoundingClientRect(),d=Math.max(r.width,r.height),s=document.createElement('span');
s.className='rip';s.style.cssText='width:'+d+'px;height:'+d+'px;left:'+(e.clientX-r.left-d/2)+'px;top:'+(e.clientY-r.top-d/2)+'px';
b.appendChild(s);setTimeout(function(){s.remove()},650)});

/* scroll reveal */
var rv=document.querySelectorAll('.panel,.reveal');
if('IntersectionObserver'in window&&!reduce){
var io=new IntersectionObserver(function(en){en.forEach(function(e){if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}})},{threshold:.08});
rv.forEach(function(el){if(!el.classList.contains('reveal')){el.classList.add('reveal')}io.observe(el)})}
else rv.forEach(function(el){el.classList.add('in')});
})();
