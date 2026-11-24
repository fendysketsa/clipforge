// Topic-driven story cards. All copy is JSON data; no external media or code.
const PALETTE = {
  dulu_sekarang:{ink:'#173B45',accent:'#168F85',soft:'#E4EFE5',warm:'#F4E2CD'},
  mitos_fakta:{ink:'#173B45',accent:'#4E8EBA',soft:'#E6EEF7',warm:'#F4DFCE'},
  salah_benar:{ink:'#173B45',accent:'#D9785F',soft:'#F7E6DF',warm:'#F6E0D6'},
  masalah_solusi:{ink:'#173B45',accent:'#C99433',soft:'#FAF0D9',warm:'#F4E2CD'},
  tiga_langkah:{ink:'#173B45',accent:'#168F85',soft:'#E4EFE5',warm:'#F4E2CD'},
  pilihan_a_b:{ink:'#173B45',accent:'#6C7BA8',soft:'#E9EBF4',warm:'#EDE6F0'},
};
const MUTED = '#54767B';

export function createStoryRenderer(ctx, data) {
  const font=(size,bold=false)=>`${bold?700:400} ${size}px "DejaVu Sans",sans-serif`;
  function rect(x,y,w,h,r,color,stroke=null,line=2){
    ctx.beginPath();ctx.roundRect(x,y,w,h,r);ctx.fillStyle=color;ctx.fill();
    if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=line;ctx.stroke();}
  }
  function circle(x,y,r,color,stroke=null,line=2){
    ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fillStyle=color;ctx.fill();
    if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=line;ctx.stroke();}
  }
  function path(points,color,width=6){
    ctx.beginPath();points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));
    ctx.strokeStyle=color;ctx.lineWidth=width;ctx.lineCap='round';ctx.lineJoin='round';ctx.stroke();
  }
  function polygon(points,color){
    ctx.beginPath();points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));
    ctx.closePath();ctx.fillStyle=color;ctx.fill();
  }
  function text(value,x,y,width,size=32,color='#173B45',bold=false,max=3){
    ctx.font=font(size,bold);ctx.textAlign='left';ctx.textBaseline='top';
    const rows=[];let row='';
    for(const word of String(value).split(/\s+/)){
      const next=row?row+' '+word:word;
      if(row&&ctx.measureText(next).width>width){rows.push(row);row=word;}else row=next;
    }
    if(row)rows.push(row);
    ctx.fillStyle=color;rows.slice(0,max).forEach((v,i)=>ctx.fillText(v,x,y+i*(size+10)));
    return Math.min(rows.length,max);
  }
  function centered(value,cx,y,size=48,color='#173B45',bold=true){
    ctx.font=font(size,bold);ctx.textAlign='center';ctx.textBaseline='top';ctx.fillStyle=color;ctx.fillText(value,cx,y);
  }
  function icon(kind,x,y,r,color){
    ctx.save();
    if(kind==='clock'){
      circle(x,y,r,color);circle(x,y,r*.78,'#fff');path([[x,y-r*.5],[x,y],[x+r*.4,y+r*.22]],color,5);
    }else if(kind==='chat'){
      rect(x-r,y-r*.8,r*2,r*1.45,r*.35,color);polygon([[x-r*.5,y+r*.55],[x-r*.15,y+r*.55],[x-r*.45,y+r],[x-r*.5,y+r*.55]],color);
      for(const dx of [-.45,0,.45])circle(x+r*dx,y-r*.08,r*.1,'#fff');
    }else if(kind==='spark'){
      const pts=[];for(let i=0;i<8;i++){const a=Math.PI*2*i/8,rad=i%2?r*.36:r;pts.push([x+Math.cos(a)*rad,y+Math.sin(a)*rad]);}
      polygon(pts,color);
    }else if(kind==='alert'){
      polygon([[x,y-r],[x+r,y+r*.75],[x-r,y+r*.75]],color);text('!',x-6,y-r*.18,40,r*.85,'#fff',true,1);
    }else if(kind==='check'){
      circle(x,y,r,color);path([[x-r*.45,y],[x-r*.1,y+r*.34],[x+r*.5,y-r*.34]],'#fff',7);
    }else if(kind==='lightbulb'){
      circle(x,y-r*.1,r*.72,color);rect(x-r*.28,y+r*.5,r*.56,r*.35,5,color);
      path([[x-r*.45,y+r*.92],[x+r*.45,y+r*.92]],color,5);
      for(const d of [-.55,.55])path([[x+r*d,y-r*.2],[x+r*d*1.5,y-r*.55]],color,4);
    }else if(kind==='list'){
      for(let i=0;i<3;i++){circle(x-r*.7,y-r*.55+i*r*.55,r*.12,color);rect(x-r*.45,y-r*.63+i*r*.55,r*1.25,r*.16,r*.08,color);}
    }else if(kind==='hand'){
      rect(x-r*.55,y-r*.1,r*1.1,r*.95,r*.3,color);
      for(let i=0;i<4;i++)rect(x-r*.52+i*r*.27,y-r*.72,r*.18,r*.7,r*.09,color);
      rect(x-r*.85,y+r*.15,r*.32,r*.55,r*.16,color);
    }else if(kind==='star'){
      const pts=[];for(let i=0;i<10;i++){const a=-Math.PI/2+Math.PI*i/5,rad=i%2?r*.45:r;pts.push([x+Math.cos(a)*rad,y+Math.sin(a)*rad]);}
      polygon(pts,color);
    }else if(kind==='heart'){
      circle(x-r*.36,y-r*.2,r*.42,color);circle(x+r*.36,y-r*.2,r*.42,color);
      polygon([[x-r*.78,y-r*.05],[x+r*.78,y-r*.05],[x,y+r*.85]],color);
    }else if(kind==='book'){
      rect(x-r*.7,y-r*.8,r*1.4,r*1.6,r*.18,color);rect(x-r*.55,y-r*.65,r*1.1,r*1.3,r*.1,'#fff');
      path([[x,y-r*.65],[x,y+r*.65]],color,4);
    }else if(kind==='phone'){
      rect(x-r*.5,y-r*.85,r,r*1.7,r*.2,color);rect(x-r*.38,y-r*.6,r*.76,r*1.05,r*.08,'#fff');circle(x,y+r*.62,r*.09,'#fff');
    }else if(kind==='people'){
      circle(x-r*.35,y-r*.35,r*.3,color);circle(x+r*.4,y-r*.28,r*.27,color);
      rect(x-r*.75,y-r*.0,r*.8,r*.7,r*.28,color);rect(x+r*.0,y+r*.02,r*.78,r*.62,r*.26,color);
    }else{
      circle(x,y,r,color);text('?',x-r*.28,y-r*.55,40,r*1.05,'#fff',true,1);
    }
    ctx.restore();
  }
  function background(pal){
    ctx.fillStyle='#F6F4E9';ctx.fillRect(0,0,1080,1920);
    circle(150,560,360,pal.soft);circle(1000,830,400,pal.warm);
    rect(60,470,960,800,64,'#F1EFE4');
    circle(930,420,42,'#F8C262');
    for(let i=0;i<5;i++)circle(120+i*200,452,4,'#C6D3C8');
  }
  function panelCard(panel,x,y,w,h,pal,steps){
    const lift=44*(1-panel.reveal), alpha=Math.max(.25,panel.reveal);
    ctx.save();ctx.globalAlpha=alpha;
    rect(x,y+lift,w,h,36,'#FFFFFF',panel.active?pal.accent:'#D8D3C4',panel.active?5:2);
    icon(panel.icon,x+70,y+lift+78,38,pal.accent);
    text(panel.label,x+130,y+lift+46,w-170,34,pal.ink,true,2);
    text(panel.caption,x+40,y+lift+(steps?112:172),w-80,steps?27:29,MUTED,false,steps?2:4);
    if(panel.active){rect(x+40,y+lift+h-42,w-80,7,4,pal.accent);}
    else{rect(x+40,y+lift+h-42,w-80,7,4,'#E6E1D4');}
    ctx.restore();
  }
  return (t,index)=>{
    const model=data.frames[index];
    const pal=PALETTE[model.style]||PALETTE.dulu_sekarang;
    ctx.globalAlpha=1;background(pal);
    text('RYUUNDY  /  CERITA SEHARI-HARI',85,95,880,23,pal.accent,true,1);
    const titleRows=text(data.title,85,150,900,58,pal.ink,true,3);
    const chipY=150+titleRows*70+16;
    rect(85,chipY,910,54,27,pal.soft);
    text('TOPIK  ·  '+model.topic_text,110,chipY+13,860,23,pal.accent,true,1);
    if(model.layout==='steps'){
      model.panels.forEach((panel,i)=>panelCard(panel,90,chipY+120+i*205,900,178,pal,true));
    }else{
      model.panels.forEach((panel,i)=>panelCard(panel,60+i*490,chipY+120,460,620,pal,false));
    }
    if(model.complete){
      circle(112,1330,25,pal.accent);
      path([[123,1330],[133,1341],[151,1318]],'#fff',5);
      text('Ini cerita ringan, bukan patokan mutlak.',156,1312,640,27,pal.accent,true,2);
    }
    const cue=data.captionCues.find(c=>c.start<=t&&t<c.end);
    if(cue){
      ctx.font=font(data.captionFontSize,true);ctx.textBaseline='top';ctx.textAlign='center';ctx.fillStyle=pal.ink;
      cue.text.split('\n').forEach((v,i)=>ctx.fillText(v,540,1435+i*69));
    }
    const labels=model.layout==='steps'?['KENALI','LAKUKAN','PERIKSA']:['KENALI','BANDINGKAN','SIMPULKAN'];
    labels.forEach((label,i)=>{
      const active=model.phase===i||(model.complete&&i===2),x=100+i*300;
      rect(x,1668,245,7,3,active?pal.accent:'#D8D3C4');
      text(label,x,1698,250,21,active?pal.accent:MUTED,active,1);
    });
  };
}
