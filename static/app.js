(function(){
var c=document.getElementById('fx');
if(c&&!matchMedia('(prefers-reduced-motion: reduce)').matches){
var x=c.getContext('2d'),w,h,P=[],M={x:-999,y:-999},cols=['#00f0ff','#8b5cf6','#ff2bd6'];
function rs(){w=c.width=innerWidth;h=c.height=innerHeight;P=[];var n=Math.min(90,Math.floor(w*h/16000));
for(var i=0;i<n;i++)P.push({x:Math.random()*w,y:Math.random()*h,vx:(Math.random()-.5)*.5,vy:(Math.random()-.5)*.5,r:Math.random()*1.8+.6,c:cols[i%3]});}
addEventListener('resize',rs);addEventListener('mousemove',function(e){M.x=e.clientX;M.y=e.clientY});rs();
(function loop(){x.clearRect(0,0,w,h);
for(var i=0;i<P.length;i++){var p=P[i];p.x+=p.vx;p.y+=p.vy;
if(p.x<0||p.x>w)p.vx*=-1;if(p.y<0||p.y>h)p.vy*=-1;
var dx=p.x-M.x,dy=p.y-M.y,d=Math.hypot(dx,dy);if(d<120){p.x+=dx/d*1.2;p.y+=dy/d*1.2}
x.beginPath();x.arc(p.x,p.y,p.r,0,6.3);x.fillStyle=p.c;x.shadowBlur=12;x.shadowColor=p.c;x.fill();
for(var j=i+1;j<P.length;j++){var q=P[j],l=Math.hypot(p.x-q.x,p.y-q.y);
if(l<130){x.shadowBlur=0;x.strokeStyle='rgba(0,240,255,'+(1-l/130)*.28+')';x.beginPath();x.moveTo(p.x,p.y);x.lineTo(q.x,q.y);x.stroke()}}}
requestAnimationFrame(loop)})();
}
document.querySelectorAll('[data-count]').forEach(function(el){
var t=+el.dataset.count||0,s=performance.now();
(function f(n){var k=Math.min((n-s)/900,1);el.textContent=Math.round(t*(1-Math.pow(1-k,3)));if(k<1)requestAnimationFrame(f)})(s)});
document.querySelectorAll('.panel,.stat').forEach(function(el){
el.addEventListener('mousemove',function(e){var r=el.getBoundingClientRect();
el.style.transform='perspective(900px) rotateX('+((e.clientY-r.top)/r.height-.5)*-3+'deg) rotateY('+((e.clientX-r.left)/r.width-.5)*3+'deg)'});
el.addEventListener('mouseleave',function(){el.style.transform=''})});
})();
