// Native canvas objects from the narration-timed Facebook semantic scene model.
// Fixed application code: narration, filenames and captions are JSON data only.
const canvas = document.querySelector('#c');
const ctx = canvas.getContext('2d');
const data = await (await fetch('./film.json')).json();
const educationRenderer = data.education ? (await import('./education-scene.mjs')).createEducationRenderer(ctx,data) : null;
const INK='#173B45', MUTED='#54767B', TEAL='#168F85', GOLD='#F8C262', CORAL='#E9947D';
window.TOTAL=data.durationSeconds;
window.ready=document.fonts.ready;
function rect(x,y,w,h,r,fill,stroke=null,line=2) {
  ctx.beginPath();ctx.roundRect(x,y,w,h,r);ctx.fillStyle=fill;ctx.fill();
  if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=line;ctx.stroke();}
}
function ellipse(x,y,w,h,fill,stroke=null,line=2) {
  ctx.beginPath();ctx.ellipse(x+w/2,y+h/2,w/2,h/2,0,0,2*Math.PI);ctx.fillStyle=fill;ctx.fill();
  if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=line;ctx.stroke();}
}
function line(points,color,width=3) {
  ctx.beginPath();points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));
  ctx.strokeStyle=color;ctx.lineWidth=width;ctx.lineJoin='round';ctx.stroke();
}
function polygon(points,color) {
  ctx.beginPath();points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));
  ctx.closePath();ctx.fillStyle=color;ctx.fill();
}
function font(size,bold=false){return `${bold?700:400} ${size}px "DejaVu Sans",sans-serif`;}
function text(value,x,y,width,size=32,color=INK,bold=false,max=3) {
  ctx.font=font(size,bold);ctx.textBaseline='top';ctx.textAlign='left';
  const rows=[];let row='';
  for(const word of String(value).replaceAll('_','_ ').split(/\s+/)) {
    const parts=ctx.measureText(word).width>width?[...word]:[word];
    for(const part of parts){
      const next=row+(row&&part.length>1?' ':'')+part;
      if(row&&ctx.measureText(next).width>width){rows.push(row);row=part;}else row=next;
    }
  }
  if(row)rows.push(row);
  if(rows.length>max){let last=rows[max-1];while(last&&ctx.measureText(last+'…').width>width)last=last.slice(0,-1);rows[max-1]=last+'…';}
  ctx.fillStyle=color;rows.slice(0,max).forEach((v,i)=>ctx.fillText(v,x,y+i*(size+9)));
}
function background(){
  ctx.fillStyle='#F6F4E9';ctx.fillRect(0,0,1080,1920);
  ellipse(-260,310,930,930,'#E4EFE5');ellipse(650,400,770,750,'#F4E2CD');
  rect(125,480,750,730,145,'#EDF1E4');ellipse(48,1135,892,135,'#DDE4D6');
  rect(65,1220,870,12,6,'#B8CEC1');
}
function folderBack(row){
  const {x,y,w,color}=row;
  rect(x+10,y-45,w*.5-10,60,20,color);rect(x,y,w,245,26,color);
  rect(x+16,y+20,w-32,205,18,'#FAF7ED');
}
function folderFront(row){
  const {x,y,w,color}=row, lift=24*row.open;
  polygon([[x,y+90-lift],[x+w,y+112-lift],[x+w-12,y+245],[x+12,y+245]],color);
  line([[x+16,y+112-lift],[x+w-16,y+132-lift]],'#fff',3);
  text(row.label,x+24,y+156,w-48,30,'#fff',true,1);
  text(`${row.count||0} berkas`,x+16,y+265,w-32,28,MUTED,false,1);
}
function documentObject(item){
  if(!item.visible)return;
  const {x,y,w,h}=item, tiny=w<150, kind=item.type;
  const accent=kind==='photo'?CORAL:kind==='video'?'#8F9CC3':TEAL;
  const label=kind==='photo'?'FOTO':kind==='video'?'VIDEO':'TXT';
  rect(x+7,y+12,w,h,18,'#C7D5C9');rect(x,y,w,h,18,'#fff',item.highlight?TEAL:'#A8C3BE',item.highlight?4:2);
  if(w>h*2){
    rect(x+16,y+18,69,h-36,10,accent);text(label,x+24,y+45,60,18,'#fff',true,1);
    text(item.label,x+110,y+27,w-135,27,INK,true,2);return;
  }
  rect(x+12,y+13,w-24,31,8,accent);text(label,x+20,y+18,w-40,tiny?15:18,'#fff',true,1);
  if(kind==='photo'||kind==='video'){
    ctx.fillStyle='#D8ECE6';ctx.fillRect(x+14,y+56,w-28,h*.6-56);
    ellipse(x+w*.62,y+65,w*.2,20,GOLD);
    polygon([[x+14,y+h*.6],[x+w*.43,y+65],[x+w-14,y+h*.6]],'#72B5A0');
  }else for(let i=0;i<3;i++)rect(x+17,y+60+i*(tiny?15:22),w-37-(i%2)*18,5,2,'#B6D7CE');
  let value=item.detail||item.label;
  if(tiny)value=kind==='photo'?'Foto':kind==='video'?'Video':'Catatan';
  else if(item.folder_item){
    if(item.detail){text(item.label,x+14,y+125,w-28,18,MUTED,false,1);text(item.detail,x+14,y+154,w-28,22,INK,true,2);value=null;}
    else value=kind==='document'?'Catatan':kind==='photo'?'Foto':'Video';
  }
  if(value!==null)text(value,x+14,y+Math.max(100,h*.59),w-28,tiny?18:w<300?24:34,INK,true,w<=240?2:3);
  if(item.role==='copy'){rect(x+25,y-42,w-50,34,12,TEAL);text('SALINAN',x+36,y-36,w-60,20,'#fff',true,1);}
}
function guide(t,target,active){
  const x=780,y=1300,hand=[x-95,y+(active?7:35)];
  if(active){line([hand,target],'#789D91',4);ellipse(target[0]-7,target[1]-7,14,14,GOLD);}
  line([[x-25,y+45],[x-80,y+45],hand],TEAL,14);ellipse(hand[0]-15,hand[1]-15,30,30,'#F0C59C',INK);
  rect(x-44,y,88,100,28,TEAL);ellipse(x-47,y-72,94,90,'#A9DCC7',INK,3);
  for(const eye of [x-17,x+17])ellipse(eye-4,y-39,8,t%4.7<.12?2:13,INK);
  ctx.beginPath();ctx.ellipse(x,y-18,18,11,0,0,Math.PI);ctx.strokeStyle=INK;ctx.lineWidth=3;ctx.stroke();
  line([[x-23,y+94],[x-28,y+119]],INK,7);line([[x+23,y+94],[x+28,y+119]],INK,7);
}
const results={copy:'Asal tetap ada. Salinan masuk tujuan.',group:'Jenis berkas terpisah. Jumlah tetap.',
  restore:'Berkas keluar dari Sampah.',search:'Filter bukan penghapusan.',paths:'Periksa lokasi dan isi.',
  extension:'Nama berubah. Format tetap.',rename:'Nama lebih jelas. Isi tetap sama.',
  size:'Urut ukuran. Belum ada yang dihapus.',date:'Pola tanggal konsisten.',number:'Dua digit, urutan lebih jelas.'};
window.renderAt=async(t)=>{
  await window.ready;
  const index=Math.min(data.frames.length-1,Math.max(0,Math.round(t*data.fps)));
  if(educationRenderer){educationRenderer(t,index);return;}
  const model=data.frames[index];
  ctx.globalAlpha=1;background();
  text('RYUUNDY  /  DIGITAL SEHARI-HARI',85,95,820,23,TEAL,true,1);
  text(data.title,85,155,790,57,INK,true,3);text('SIMULASI EDUKASI · DATA CONTOH',85,402,790,22,MUTED,false,1);
  const inspecting=data.topic==='copy'&&model.clock.inspect<=t&&t<model.clock.inspect+3;
  text(inspecting?'PERIKSA SALINANNYA':model.complete?'HASILNYA TERLIHAT':model.selected?'IKUTI PERGERAKANNYA':'PERHATIKAN OBJEKNYA',95,470,790,23,TEAL,true,1);
  if(!['size','date','number'].includes(data.topic))guide(t,model.focus,inspecting||!model.complete);
  model.folders.forEach(folderBack);
  if(model.selected&&['copy','group','restore'].includes(data.topic))for(let i=0;i<14;i++)ellipse(260+i*36,620-70*Math.sin(i/13*Math.PI),5,5,'#8FBEB1');
  if(data.topic==='search'){
    rect(130,545,720,90,28,'#fff',TEAL,3);ellipse(155,570,25,25,'#fff',TEAL,4);line([[178,593],[191,607]],TEAL,4);
    text(model.query||'Cari nama berkas…',215,568,600,31,model.query?TEAL:MUTED,false,1);
  }
  model.items.forEach(documentObject);model.folders.forEach(folderFront);
  if(model.editing!==null){rect(115,1060,755,115,24,'#fff',TEAL,3);text(model.editing,140,1080,700,29,INK,true,2);}
  if(model.complete){
    ellipse(110,1250,50,50,TEAL);line([[121,1274],[132,1285],[149,1264]],'#fff',5);
    text(results[data.topic],180,1254,530,27,TEAL,true,2);
  }
  // One caption plane, outside all object movement. No word flashes or fades.
  const cue=data.captionCues.find(c=>c.start<=t&&t<c.end);
  if(cue){
    ctx.font=font(data.captionFontSize,true);ctx.fillStyle=INK;ctx.textBaseline='top';ctx.textAlign='center';
    cue.text.split('\n').forEach((v,i)=>ctx.fillText(v,540,1435+i*69));
  }
  ['KENALI','LAKUKAN','PERIKSA'].forEach((label,i)=>{
    const active=i===(model.complete?2:model.selected?1:0),x=100+i*270;
    rect(x,1660,225,6,3,active?TEAL:'#C8D9D0');text(label,x,1683,240,21,active?TEAL:MUTED,active,1);
  });
};
await window.ready;
await window.renderAt(Number(new URLSearchParams(location.search).get('t'))||0);
