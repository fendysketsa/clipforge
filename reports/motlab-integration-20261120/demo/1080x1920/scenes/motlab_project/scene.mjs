// Pure renderAt(t): footage + directed camera + a stable caption plane.
import {ease, spring, prog} from '/__motlab/motion.js';
import {openFootage} from '/__motlab/footage.js';

const canvas = document.querySelector('#c');
const ctx = canvas.getContext('2d');
const data = await (await fetch('./film.json')).json();
const W = data.width, H = data.height, fps = data.fps;
const portrait = H > W;
const safe = W * .075;
const assets = new Map();
let logo;
const bounce = spring({stiffness:130, damping:23});
const image = (src) => new Promise((resolve,reject) => {
  const img = new Image(); img.onload = () => resolve(img);
  img.onerror = () => reject(new Error('Visual asset could not load: ' + src)); img.src = src;
});

window.TOTAL = data.durationSeconds;
window.ready = (async () => {
  await document.fonts.ready;
  for (const shot of data.shots) {
    if (!assets.has(shot.asset)) assets.set(shot.asset, shot.kind === 'video'
      ? await openFootage('./assets/' + shot.asset) : await image('./assets/' + shot.asset));
  }
  if (data.watermarkAsset) logo = await image(data.watermarkAsset);
})();

function roundRect(x,y,w,h,r,fill) {
  ctx.beginPath(); ctx.roundRect(x,y,w,h,r); ctx.fillStyle=fill; ctx.fill();
}
function lines(text, maxWidth, font, maximum=3) {
  ctx.font=font;
  const result=[]; let current='';
  for (const word of text.split(/\s+/)) {
    const next = current ? current+' '+word : word;
    if (current && ctx.measureText(next).width > maxWidth) {result.push(current);current=word;}
    else current=next;
  }
  if (current) result.push(current);
  return result;
}
function fit(text,width,size,maximum,weight=800) {
  let font, result;
  for (;;) {
    font=`${weight} ${size}px "DejaVu Sans", "Noto Sans", sans-serif`;
    result=lines(text,width,font);
    if ((result.length<=maximum && result.every(line=>ctx.measureText(line).width<=width)) || size<W*.021) break;
    size*=.93;
  }
  return {font,size,text:result};
}
function cover(source, sourceW, sourceH, x,y,w,h, zoom=1, focusX=.5, focusY=.46) {
  const scale = Math.max(w/sourceW,h/sourceH)*zoom;
  const dw=sourceW*scale, dh=sourceH*scale;
  const dx=x-(dw-w)*focusX, dy=y-(dh-h)*focusY;
  ctx.save();ctx.beginPath();ctx.rect(x,y,w,h);ctx.clip();
  if (source.draw) source.draw(ctx,dx,dy,dw,dh);
  else ctx.drawImage(source,dx,dy,dw,dh);
  ctx.restore();
}
async function picture(shot,plan,frame,opacity) {
  const local=Math.max(0,(frame-shot.startFrame)/fps);
  const ratio= Math.min(1,local/(shot.bodyDurationInFrames/fps));
  const material=assets.get(shot.asset);
  let source=material, sw=material.naturalWidth, sh=material.naturalHeight;
  if (shot.kind==='video') {
    // Freeze only the picture handle after the real end; preserve source speed.
    const sample=await material.frame(Math.min(local,Math.max(0,material.duration-1/fps)));
    source=sample;sw=material.width;sh=material.height;
  }
  const camera = String(plan.camera);
  const drift = camera.includes('pan') ? (camera.includes('left') ? -.12 : .12)*ease.inOutSine(ratio) : 0;
  const push = camera.includes('pull') ? 1-ratio : ratio;
  const zoom=1+(plan.maxZoom-1)*ease.inOutSine(push);
  ctx.save();ctx.globalAlpha=opacity;
  const split=plan.layout==='editorial_split';
  const viewport = split ? [W*.34,0,W*.66,H] : [0,0,W,H];
  cover(source,sw,sh,...viewport,zoom,Math.max(0,Math.min(1,plan.focusX+drift)));
  const shade=ctx.createLinearGradient(0,0,0,H);
  shade.addColorStop(0,'rgba(4,8,15,.38)');shade.addColorStop(.4,'rgba(4,8,15,0)');
  shade.addColorStop(1,'rgba(4,8,15,.66)');ctx.fillStyle=shade;ctx.fillRect(0,0,W,H);
  if (split) {
    const panel=ctx.createLinearGradient(0,0,W*.47,0);
    panel.addColorStop(0,'#0c1421');panel.addColorStop(.72,'rgba(12,20,33,.97)');panel.addColorStop(1,'rgba(12,20,33,0)');
    ctx.fillStyle=panel;ctx.fillRect(0,0,W*.47,H);
  }
  if (plan.title && !plan.diagram.length) title(plan,local,split);
  ctx.restore();
}
function title(plan,local,split) {
  const enter=Math.min(1,bounce(Math.max(0,local-.12)));
  const alpha=ease.outCubic(prog(local,.1,.48));
  const maxWidth=split ? W*.285 : W*.78;
  const {font,size,text}=fit(plan.title,maxWidth,W*(portrait ? .061 : split ? .039 : .041),3);
  ctx.save();ctx.globalAlpha*=alpha;
  ctx.translate(safe, H*(split ? .28 : .14)+(1-enter)*H*.018);
  ctx.fillStyle=plan.accentColor;ctx.fillRect(0,-size*.65,Math.max(18,W*.055)*ease.outCubic(prog(local,.08,.5)),4);
  ctx.font=font;ctx.textBaseline='top';ctx.fillStyle='#fff';
  ctx.shadowColor='rgba(0,0,0,.65)';ctx.shadowBlur=16;
  text.forEach((line,i)=>ctx.fillText(line,0,i*size*1.22));ctx.restore();
}
function diagram(plan, frame) {
  if (!plan.diagram.length) return;
  const nodes=plan.diagram, y=H*(portrait ? .47 : .34), left=W*.14, space=W*.72/(nodes.length-1);
  const radius=W*(portrait ? .075 : .045);
  ctx.save();ctx.lineWidth=Math.max(3,W*.004);ctx.strokeStyle=plan.accentColor;
  for (let i=1;i<nodes.length;i++) {
    const p=ease.outCubic(prog(frame,nodes[i].atFrame,nodes[i].atFrame+fps*.5));
    ctx.beginPath();ctx.moveTo(left+(i-1)*space+radius,y);
    ctx.lineTo(left+(i-1)*space+radius+(space-2*radius)*p,y);ctx.stroke();
  }
  nodes.forEach((node,index)=>{
    const p=Math.min(1,bounce(Math.max(0,(frame-node.atFrame)/fps)));
    if (p<=0) return;
    const x=left+index*space;
    ctx.save();ctx.translate(x,y);ctx.scale(p,p);
    ctx.beginPath();ctx.arc(0,0,radius,0,Math.PI*2);ctx.fillStyle='rgba(8,17,31,.91)';ctx.fill();ctx.stroke();
    const {font,size,text}=fit(node.label,space*.86,W*(portrait ? .038 : .028),2);
    ctx.font=font;ctx.fillStyle='#fff';ctx.textAlign='center';ctx.textBaseline='top';
    text.forEach((line,i)=>ctx.fillText(line,0,radius+size*.5+i*size*1.2));
    // A persistent source-linked token follows the connection rather than a
    // generic text slide replacing the whole scene.
    ctx.fillStyle=plan.accentColor;
    const label=node.label.toLowerCase(), r=radius*.56;
    if (/air|water/.test(label)) {
      ctx.beginPath();ctx.moveTo(0,-r);ctx.bezierCurveTo(r,r*.1,r,r,0,r);
      ctx.bezierCurveTo(-r,r,-r,r*.1,0,-r);ctx.fill();
      ctx.fillStyle='#fff';ctx.beginPath();ctx.arc(-r*.22,r*.38,r*.12,0,Math.PI*2);ctx.fill();
    } else if (/turbin|generator/.test(label)) {
      ctx.rotate((frame-node.atFrame)/fps*1.45);
      for(let blade=0;blade<6;blade++) {
        ctx.rotate(Math.PI/3);ctx.beginPath();ctx.moveTo(0,0);
        ctx.quadraticCurveTo(r,-r*.6,r,r*.1);ctx.lineTo(r*.25,r*.3);ctx.fill();
      }
      ctx.fillStyle='#fff';ctx.beginPath();ctx.arc(0,0,r*.17,0,Math.PI*2);ctx.fill();
    } else if (/listrik|energi|lampu/.test(label)) {
      ctx.beginPath();ctx.moveTo(r*.24,-r);ctx.lineTo(-r*.6,r*.08);ctx.lineTo(-r*.05,r*.08);
      ctx.lineTo(-r*.24,r);ctx.lineTo(r*.6,-r*.08);ctx.lineTo(r*.05,-r*.08);ctx.closePath();ctx.fill();
    } else {
      ctx.beginPath();ctx.arc(0,0,r*.42,0,Math.PI*2);ctx.fill();
    }
    ctx.restore();
  });ctx.restore();
}
function caption(frame) {
  if (!data.captionsEnabled) return;
  const cue=data.captionCues.find(c=>frame>=c.startFrame && frame<c.endFrame);
  if (!cue) return;
  const size=W*(portrait ? .048 : .031);
  const font=`700 ${size}px "DejaVu Sans", "Noto Sans", sans-serif`;
  const text=lines(cue.text,W*.82,font,3), gap=size*1.28;
  ctx.save();ctx.font=font;ctx.textAlign='center';ctx.textBaseline='middle';
  const width=Math.max(...text.map(line=>ctx.measureText(line).width))+size*1.05;
  const boxHeight=text.length*gap+size*.55, y=H*(portrait ? .805 : .82);
  roundRect((W-width)/2,y,width,boxHeight,size*.18,'rgba(5,10,19,.79)');
  ctx.fillStyle='#fff';text.forEach((line,i)=>ctx.fillText(line,W/2,y+size*.28+gap*(i+.5)));
  ctx.restore();
}
function identity() {
  if (!logo) return;
  const w=W*(portrait ? .16 : .10), h=w*logo.naturalHeight/logo.naturalWidth;
  ctx.save();ctx.globalAlpha=.82;ctx.drawImage(logo,W-safe-w,H*.055,w,h);ctx.restore();
}
window.renderAt = async (t) => {
  await window.ready;
  const frame=Math.min(Math.round(data.durationSeconds*fps)-1,Math.max(0,Math.round(t*fps)));
  ctx.globalAlpha=1;ctx.fillStyle='#090d16';ctx.fillRect(0,0,W,H);
  // Render outgoing handles first, then incoming pictures. The caption plane is
  // drawn once afterwards: a transition can never double or fade a spoken cue.
  for (let index=0;index<data.shots.length;index++) {
    const shot=data.shots[index];
    if (frame < shot.startFrame || frame >= shot.startFrame+shot.durationInFrames) continue;
    const plan=data.motlabMotion[index];
    const incoming=shot.transitionInFrames || 0;
    const alpha=incoming ? ease.inOutCubic(Math.min(1,(frame-shot.startFrame)/incoming)) : 1;
    await picture(shot,plan,frame,alpha);
  }
  const active=data.shots.findIndex(shot=>frame>=shot.startFrame && frame<shot.startFrame+shot.bodyDurationInFrames);
  if (active>=0) diagram(data.motlabMotion[active],frame);
  caption(frame);identity();
};
await window.ready;
await window.renderAt(Number(new URLSearchParams(location.search).get('t')) || 0);
