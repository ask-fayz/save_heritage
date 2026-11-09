// Locally served orthographic globe: no tiles, API keys, or external requests.
(async () => {
  const root = document.querySelector('[data-globe]');
  if (!root) return;
  const canvas = root.querySelector('canvas');
  const sites = JSON.parse(document.getElementById('heritage-map-data').textContent);
  const error = root.querySelector('[data-globe-error]');
  try {
    if (!window.d3 || !window.topojson) throw new Error('Libraries unavailable');
    const response = await fetch('/static/vendor/land-110m.json');
    if (!response.ok) throw new Error('Land data unavailable');
    const world = await response.json();
    const land = topojson.feature(world, world.objects.land);
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Canvas unavailable');
    const projection = d3.geoOrthographic().rotate([-65,-25]).clipAngle(90);
    const path = d3.geoPath(projection,ctx);
    const grid = d3.geoGraticule10();
    const colors = {stable:'#65c89c',watch:'#e6c36f',at_risk:'#e79850',critical:'#ef7272',lost:'#c4c6cb',unknown:'#91a6b7'};
    let width, height, base, zoom = 1, filter = 'all', hits = [];
    const matches = site => filter === 'all' || (filter === 'endangered' ? ['watch','at_risk','critical'].includes(site.risk_status) : site.risk_status === filter);
    function draw() {
      ctx.clearRect(0,0,width,height);
      projection.scale(base*zoom).translate([width/2,height/2]);
      ctx.beginPath(); path({type:'Sphere'}); ctx.fillStyle='#163c49'; ctx.fill(); ctx.strokeStyle='#6b9994'; ctx.lineWidth=1; ctx.stroke();
      ctx.beginPath(); path(grid); ctx.strokeStyle='#315561'; ctx.lineWidth=.6; ctx.stroke();
      ctx.beginPath(); path(land); ctx.fillStyle='#779a86'; ctx.fill(); ctx.strokeStyle='#a9bfa2'; ctx.lineWidth=.4; ctx.stroke();
      hits=[];
      const center=projection.invert([width/2,height/2]);
      sites.forEach((site,index)=>{
        const coord=[site.longitude,site.latitude];
        if (!matches(site) || d3.geoDistance(coord,center)>Math.PI/2) return;
        const [x,y]=projection(coord); hits.push({x,y,index});
        ctx.beginPath(); ctx.arc(x,y,10,0,Math.PI*2); ctx.fillStyle='#081d3480';ctx.fill();
        ctx.beginPath(); ctx.arc(x,y,5,0,Math.PI*2);ctx.fillStyle=colors[site.risk_status]||colors.unknown;ctx.fill();ctx.strokeStyle='#fff';ctx.lineWidth=1.8;ctx.stroke();
      });
    }
    function resize() {
      const rect=canvas.getBoundingClientRect();width=rect.width;height=rect.height;base=Math.min(width,height)*.42;
      const ratio=Math.min(devicePixelRatio||1,2);canvas.width=width*ratio;canvas.height=height*ratio;ctx.setTransform(ratio,0,0,ratio,0,0);draw();
    }
    function scale(factor) { zoom=Math.max(.8,Math.min(4,zoom*factor));draw(); }
    function select(index) {
      const site=sites[index]; if (!site) return;
      projection.rotate([-site.longitude,-site.latitude]);
      root.querySelector('[data-globe-title]').textContent=site.title;
      root.querySelector('[data-globe-location]').textContent=site.location_label;
      root.querySelector('[data-globe-link]').href=`/site/${encodeURIComponent(site.slug)}?lang=${document.documentElement.lang}`;
      root.querySelector('[data-globe-card]').hidden=false;draw();
    }
    const points=new Map();let moved=0;
    canvas.addEventListener('pointerdown',e=>{ points.set(e.pointerId,[e.clientX,e.clientY]);moved=0;canvas.setPointerCapture(e.pointerId); });
    canvas.addEventListener('pointermove',e=>{
      if(!points.has(e.pointerId))return;
      const previous=points.get(e.pointerId), dx=e.clientX-previous[0],dy=e.clientY-previous[1];moved+=Math.abs(dx)+Math.abs(dy);
      if(points.size===2){
        const other=[...points.entries()].find(([id])=>id!==e.pointerId)[1];
        const old=Math.hypot(previous[0]-other[0],previous[1]-other[1]);
        if(old>5)scale(Math.hypot(e.clientX-other[0],e.clientY-other[1])/old);
      }else{ const r=projection.rotate();projection.rotate([r[0]+dx*90/(base*zoom),Math.max(-85,Math.min(85,r[1]-dy*90/(base*zoom)))]);draw(); }
      points.set(e.pointerId,[e.clientX,e.clientY]);
    });
    canvas.addEventListener('pointerup',e=>{
      if(moved<7&&points.size===1){ const rect=canvas.getBoundingClientRect();const hit=hits.find(h=>Math.hypot(h.x-e.clientX+rect.left,h.y-e.clientY+rect.top)<20);if(hit)select(hit.index); }
      points.delete(e.pointerId);
    });
    canvas.addEventListener('pointercancel',e=>points.delete(e.pointerId));
    canvas.addEventListener('wheel',e=>{if(document.activeElement!==canvas&&!e.ctrlKey)return;e.preventDefault();scale(Math.exp(-e.deltaY*.001));},{passive:false});
    canvas.addEventListener('keydown',e=>{
      const r=projection.rotate();
      if(e.key==='ArrowLeft')r[0]-=10;else if(e.key==='ArrowRight')r[0]+=10;else if(e.key==='ArrowUp')r[1]+=10;else if(e.key==='ArrowDown')r[1]-=10;else if(e.key==='+')scale(1.2);else if(e.key==='-')scale(1/1.2);else return;
      e.preventDefault();r[1]=Math.max(-85,Math.min(85,r[1]));projection.rotate(r);draw();
    });
    root.querySelectorAll('[data-globe-zoom]').forEach(b=>b.addEventListener('click',()=>scale(Number(b.dataset.globeZoom))));
    root.querySelector('[data-globe-reset]').addEventListener('click',()=>{zoom=1;projection.rotate([-65,-25]);root.querySelector('[data-globe-card]').hidden=true;draw();});
    root.querySelectorAll('[data-globe-site]').forEach(b=>b.addEventListener('click',()=>select(Number(b.dataset.globeSite))));
    root.querySelectorAll('[data-map-filter]').forEach(b=>b.addEventListener('click',()=>{
      filter=b.dataset.mapFilter;root.querySelectorAll('[data-map-filter]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));
      root.querySelectorAll('[data-globe-site]').forEach(x=>x.hidden=!matches(sites[Number(x.dataset.globeSite)]));root.querySelector('[data-globe-card]').hidden=true;draw();
    }));
    new ResizeObserver(resize).observe(canvas);resize();
  } catch(e) { error.hidden=false; console.error('Globe:', e); }
})();
