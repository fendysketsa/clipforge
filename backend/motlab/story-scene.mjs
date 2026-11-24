// Topic-driven story cards. All copy is JSON data; no external media or code.
const PALETTE = {
  dulu_sekarang:{ink:'#173B45',accent:'#168F85',soft:'#E4EFE5',warm:'#F4E2CD'},
  mitos_fakta:{ink:'#173B45',accent:'#4E8EBA',soft:'#E6EEF7',warm:'#F4DFCE'},
  salah_benar:{ink:'#173B45',accent:'#D9785F',soft:'#F7E6DF',warm:'#F6E0D6'},
  masalah_solusi:{ink:'#173B45',accent:'#C99433',soft:'#FAF0D9',warm:'#F4E2CD'},
  tiga_langkah:{ink:'#173B45',accent:'#168F85',soft:'#E4EFE5',warm:'#F4E2CD'},
  pilihan_a_b:{ink:'#173B45',accent:'#6C7BA8',soft:'#E9EBF4',warm:'#EDE6F0'},
  moral_anak:{ink:'#173B45',accent:'#3E8E6F',soft:'#E6F1E8',warm:'#F7E6D2'},
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
  function ellipse(x,y,rx,ry,color,stroke=null,line=2){
    ctx.beginPath();ctx.ellipse(x,y,rx,ry,0,0,Math.PI*2);ctx.fillStyle=color;ctx.fill();
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
  const SKIN='#f2c6a2', HAIR='#453a34';
  // Each topic gets a fitting little cast. Looks are data, never executable.
  const CAST={
    drink_choking:[{n:'Raka',s:'#3e8e7a',h:'#453a34'},{n:'Naya',s:'#e08a72',h:'#5b4638'}],
    sharing:[{n:'Sari',s:'#7c9b5b',h:'#4a3a30'},{n:'Bima',s:'#697db8',h:'#453a34'}],
    apology:[{n:'Dimas',s:'#588db7',h:'#3f352f'},{n:'Raka',s:'#3e8e7a',h:'#453a34'}],
    helping:[{n:'Naya',s:'#e08a72',h:'#5b4638'},{n:'Sari',s:'#7c9b5b',h:'#4a3a30'}],
    queueing:[{n:'Petugas',s:'#c28d54',h:'#3f352f',apron:true},{n:'Anak',s:'#3e8e7a',h:'#453a34'}],
    tidying:[{n:'Raka',s:'#3e8e7a',h:'#453a34'},{n:'Sari',s:'#7c9b5b',h:'#4a3a30'}],
    listening:[{n:'Guru',s:'#4b6f9c',h:'#45403a',glasses:true},{n:'Siswa',s:'#e08a72',h:'#453a34'}],
    gratitude:[{n:'Bima',s:'#697db8',h:'#3f352f'},{n:'Naya',s:'#e08a72',h:'#5b4638'}],
    greeting:[{n:'Tetangga',s:'#c99433',h:'#4a3a30'},{n:'Dimas',s:'#588db7',h:'#453a34'}],
    honesty:[{n:'Kasir',s:'#4b6f9c',h:'#3f352f',apron:true},{n:'Anak',s:'#7c9b5b',h:'#453a34'}],
    homework:[{n:'Sari',s:'#7c9b5b',h:'#4a3a30'},{n:'Raka',s:'#3e8e7a',h:'#453a34'}],
    then_now:[{n:'Dulu',s:'#c99433',h:'#4a3a30'},{n:'Sekarang',s:'#588db7',h:'#453a34'}],
    myth_fact:[{n:'Penyampai',s:'#e08a72',h:'#5b4638'},{n:'Pemeriksa',s:'#4b6f9c',h:'#3f352f',glasses:true}],
    wrong_right:[{n:'Tergesa',s:'#e08a72',h:'#5b4638'},{n:'Teliti',s:'#3e8e7a',h:'#453a34',glasses:true}],
    problem_solution:[{n:'Raka',s:'#3e8e7a',h:'#453a34'},{n:'Bima',s:'#697db8',h:'#3f352f'}],
    three_steps:[{n:'Panduan',s:'#4b6f9c',h:'#3f352f',glasses:true},{n:'Sari',s:'#7c9b5b',h:'#4a3a30'}],
    choice_ab:[{n:'Dimas',s:'#588db7',h:'#453a34'},{n:'Naya',s:'#e08a72',h:'#5b4638'}],
    cooking:[{n:'Ibu',s:'#c99433',h:'#4a3a30',apron:true},{n:'Anak',s:'#7c9b5b',h:'#453a34'}],
    card_game:[{n:'Rani',s:'#7c9b5b',h:'#4a3a30'},{n:'Dimas',s:'#588db7',h:'#453a34'}],
    everyday:[{n:'Raka',s:'#3e8e7a',h:'#453a34'},{n:'Naya',s:'#e08a72',h:'#5b4638'}],
  };
  const castOf=scene=>CAST[scene]||CAST.everyday;
  function dramaticBackdrop(t,pal,tense){
    const sky=ctx.createLinearGradient(0,300,0,1500);
    sky.addColorStop(0,tense?'#3d2f3a':'#f7f1e2');
    sky.addColorStop(.55,tense?'#7b5b57':'#eae9d7');
    sky.addColorStop(1,tense?'#c99a72':'#d9d2bd');
    ctx.fillStyle=sky;ctx.fillRect(0,0,1080,1920);
    const glow=ctx.createRadialGradient(540,760,60,540,760,760);
    glow.addColorStop(0,tense?'rgba(255,214,150,.42)':'rgba(255,250,225,.75)');
    glow.addColorStop(1,'rgba(0,0,0,0)');ctx.fillStyle=glow;ctx.fillRect(0,300,1080,1100);
    for(let i=0;i<7;i++){const x=90+i*150;path([[x,340],[x-40,1200]],'rgba(255,255,255,.07)',16);}
    const floor=ctx.createLinearGradient(0,1250,0,1920);
    floor.addColorStop(0,tense?'#a3765e':'#e2d7bd');floor.addColorStop(1,tense?'#5d4339':'#b8ab8f');
    ctx.fillStyle=floor;ctx.fillRect(0,1250,1080,670);
    for(let i=0;i<9;i++){const y=1290+i*i*8;path([[0,y],[1080,y]],'rgba(70,55,45,.13)',3);}
    ellipse(160,560,290,250,pal.soft);ellipse(1000,700,300,270,pal.warm);
  }
  function person(x,y,t,mood,shirt,scale=1,look={}){
    ctx.save();ctx.translate(x,y);ctx.scale(scale,scale);
    ctx.rotate(Math.sin(t*1.5)*.014+(mood==='cough'?Math.sin(t*19)*.015:0));
    const sy=3*Math.sin(t*2.1);
    const shadow=ctx.createRadialGradient(0,sy+150,10,0,sy+150,96);
    shadow.addColorStop(0,'rgba(35,45,40,.35)');shadow.addColorStop(1,'rgba(35,45,40,0)');
    ellipse(0,sy+150,96,18,shadow);
    path([[-20,sy+64],[-30,sy+132]],'#3b4a47',16);path([[20,sy+64],[30,sy+132]],'#3b4a47',16);
    rect(-34,sy+126,30,14,6,'#2b3633');rect(4,sy+126,30,14,6,'#2b3633');
    const torso=ctx.createLinearGradient(-50,sy-20,50,sy+80);
    torso.addColorStop(0,shirt);torso.addColorStop(1,'rgba(0,0,0,.22)');
    rect(-48,sy-16,96,96,30,torso);
    polygon([[-46,sy-14],[-10,sy+8],[-46,sy+34]],'rgba(255,255,255,.14)');
    if(look.apron){
      rect(-34,sy+4,68,76,10,'#e8dcc4');
      path([[-34,sy+4],[-20,sy-12]],'#c8b99c',5);path([[34,sy+4],[20,sy-12]],'#c8b99c',5);
      rect(-16,sy+38,32,20,4,'#d8c9ad');path([[-34,sy+26],[34,sy+26]],'#c8b99c',3);
    }
    if(look.badge)rect(28,sy+4,18,22,3,'#f4edd8');
    path([[-8,sy-16],[0,sy+12],[8,sy-16]],'rgba(255,255,255,.32)',4);
    const armL=mood==='cough'?[-14,sy-26]:mood==='drink'?[40,sy-72]:mood==='help'?[-82,sy-16]:[-68,sy+28];
    const armR=mood==='help'?[84,sy-16]:mood==='drink'?[8,sy-30]:[68,sy+28];
    for(const [hx,hy] of [armL,armR]){
      path([[hx>0?42:-42,sy-2],[hx*.72,hy+10],[hx,hy]],shirt,17);
      ellipse(hx,hy,12,12,SKIN);
      for(let f=0;f<3;f++)path([[hx+ (f-1)*5,hy+5],[hx+(f-1)*7,hy+16]],SKIN,3);
    }
    const hair=look.hair||HAIR;
    ellipse(0,sy-86,60,66,hair);ellipse(0,sy-73,49,52,SKIN);
    ellipse(-53,sy-70,13,24,hair);ellipse(53,sy-70,13,24,hair);
    if(look.cap){ellipse(0,sy-112,62,26,hair);rect(24,sy-116,58,10,5,hair);}
    const blink=t%4.4<.12?1:6;
    const eye=mood==='cough'?3:blink;
    ellipse(-17,sy-79,6,eye,'#fff');ellipse(17,sy-79,6,eye,'#fff');
    ellipse(-17,sy-79,2.6,Math.max(1.6,eye*.45),'#263a35');ellipse(17,sy-79,2.6,Math.max(1.6,eye*.45),'#263a35');
    const brow=(mood==='cough'||mood==='worried')?.14:-.05;
    path([[-28,sy-96+ brow*40],[-8,sy-98-brow*40]],'#3a3a35',4);
    path([[8,sy-98-brow*40],[28,sy-96+brow*40]],'#3a3a35',4);
    ellipse(-33,sy-59,9,5,'rgba(226,138,120,.55)');ellipse(33,sy-59,9,5,'rgba(226,138,120,.55)');
    if(look.glasses){
      ellipse(-18,sy-79,17,15,'rgba(255,255,255,.35)',look.hair||HAIR,3);
      ellipse(18,sy-79,17,15,'rgba(255,255,255,.35)',look.hair||HAIR,3);
      path([[-1,sy-79],[1,sy-79]],look.hair||HAIR,3);
    }
    if(look.n)text(look.n,-34,sy+172,70,18,'rgba(255,255,255,.8)',false,1);
    if(mood==='cough'||mood==='gasp'){
      ellipse(0,sy-48,15,mood==='cough'?14:11,'#8d4f4d');
      ellipse(0,sy-45,9,6,'#5c2f30');
    }else if(mood==='worried'||mood==='sad'){
      ctx.beginPath();ctx.arc(0,sy-36,14,Math.PI+.2,2*Math.PI-.2);ctx.strokeStyle='#7c5750';ctx.lineWidth=4;ctx.stroke();
    }else{
      ctx.beginPath();ctx.arc(0,sy-52,15,.25,Math.PI-.25);ctx.strokeStyle='#7c5750';ctx.lineWidth=4;ctx.stroke();
    }
    if(mood==='cough'){
      for(let i=0;i<4;i++){const a=t*6+i*1.7;path([[62+i*14,sy-88+Math.sin(a)*10],[88+i*16,sy-100+Math.sin(a)*14]],'rgba(160,210,225,.9)',5);}
      ellipse(52,sy-20,10,10,'rgba(233,169,162,.85)');
    }
    if(mood==='help'){path([[-70,sy-30],[-30,sy-18]],'rgba(255,255,255,.25)',6);}
    ctx.restore();
  }
  function glass(x,y,tilt=0){
    ctx.save();ctx.translate(x,y);ctx.rotate(tilt);
    polygon([[-26,-62],[26,-62],[18,46],[-18,46]],'#e6f5fb');
    polygon([[-22,-18],[22,-18],[17,43],[-17,43]],'#74c3e0');
    rect(-18,-44,15,15,3,'#d9f2fb');rect(6,-32,14,14,3,'#d9f2fb');rect(-4,-10,13,13,3,'#d9f2fb');
    path([[-28,-62],[28,-62]],'#8fd4e8',5);
    ctx.restore();
  }
  function bubble(x,y,mark,color){
    ellipse(x,y,42,42,'#fff',color,4);
    polygon([[x-14,y+30],[x+14,y+30],[x,y+54]],'#fff');
    if(mark==='?')text('?',x-11,y-25,40,44,color,true,1);
    else path([[x-16,y],[x-4,y+13],[x+18,y-15]],color,6);
  }
  function object(x,y,kind,color){
    if(kind==='book'){rect(x-40,y-30,80,60,8,color);path([[x,y-30],[x,y+30]],'#fff',4);}
    else if(kind==='box'){rect(x-45,y-35,90,70,8,color);rect(x-45,y-35,90,16,5,'#fff');}
    else if(kind==='phone'){rect(x-25,y-48,50,96,10,color);rect(x-18,y-36,36,66,6,'#eaf5f0');}
    else if(kind==='coin'){ellipse(x,y,34,34,'#efc65a',color,3);text('Rp',x-18,y-12,40,24,'#7a5b22',true,1);}
    else if(kind==='pan'){ellipse(x,y,56,28,'#4b5550');path([[x+52,y],[x+92,y]],'#4b5550',10);}
    else if(kind==='broom'){path([[x-38,y-62],[x+36,y+48]],'#a97c50',10);rect(x+22,y+30,54,16,4,'#d9c48a');}
    else if(kind==='cards'){for(let i=0;i<3;i++)rect(x-30+i*18,y-22+i*6,34,46,5,i%2?'#f6f0de':color,'#c9bda4',2);}
    else ellipse(x,y,40,40,color);
  }
  function personScene(model,t,pal){
    const stage=model.stage_starts||[0,4,8], phase=model.phase, scene=model.scene;
    const inCough=scene==='drink_choking'&&phase>=2&&phase<3&&t>stage[1]+(stage[2]-stage[1])*.4;
    const tense=scene==='drink_choking'&&(inCough||phase===2);
    dramaticBackdrop(t,pal,tense);
    ctx.save();
    const zoom=scene==='drink_choking'?(phase===1?1.18:phase===2?1.28:1.03):(phase===2?1.1:1.02);
    const shake=tense?Math.sin(t*23)*3.5:0;
    ctx.translate(540+shake,1000);ctx.scale(zoom,zoom);ctx.translate(-540,-1000);
    rect(110,930,860,26,12,'#c9b79a');rect(120,956,22,360,8,'#b5a184');rect(940,956,22,360,8,'#b5a184');
    const cast=castOf(scene), a=cast[0], b=cast[1]||cast[0];
    if(scene==='drink_choking'){
      const mood=phase===0?'curious':phase===1?'hold':inCough?'cough':phase===3?'calm':'gasp';
      person(inCough?420:360,1180,t,mood,a.s,inCough?1.5:1.2,a);
      if(inCough){
        glass(640,1050,0);
        for(let i=0;i<4;i++){const ang=t*5+i;ellipse(560+i*28,1000+Math.sin(ang)*14,5,9,'rgba(150,205,225,.8)');}
        path([[500,860],[560,900]],'rgba(255,220,160,.8)',6);
      }else if(phase<3)glass(mood==='gasp'?408:360,mood==='gasp'?1090:1030,mood==='gasp'?-.62:0);
      if(phase>=2||model.complete){
        person(790,1180,t,phase===3?'help':'worried',b.s,phase===3?1.15:1.02,b);
        if(inCough)path([[700,1120],[640,1120]],'#f0d3b0',16);
        if(phase===3){bubble(575,990,'check',pal.accent);ellipse(575,930,150,60,'rgba(255,220,150,.18)');}
      }
    }else if(scene==='then_now'||scene==='choice_ab'){
      person(320,1180,t,phase<2?'curious':'calm',a.s,1.12,a);
      person(800,1180,t,phase<2?'hold':'help',b.s,1.12,b);
      object(320,1240,scene==='then_now'?'book':'phone',pal.accent);
      object(800,1240,phase<2?'phone':'book',pal.warm);
      if(phase>=2)bubble(560,820,'check',pal.accent);
    }else if(scene==='myth_fact'||scene==='wrong_right'){
      person(340,1180,t,phase<2?'curious':phase===2?'worried':'calm',a.s,1.14,a);
      person(780,1180,t,phase<2?'hold':phase===2?'gasp':'help',b.s,1.14,b);
      bubble(340,880,phase<2?'?':'check',phase<2?'#d08a65':pal.accent);
      object(780,1240,'box',pal.warm);
    }else if(scene==='problem_solution'||scene==='three_steps'){
      const spots=[260,540,820],moods=['curious','hold',model.complete?'calm':'help'];
      spots.forEach((x,i)=>{
        const who=i===0?a:i===1?b:cast[i%cast.length];
        person(x,1180,t,moods[i],who.s,.86,who);
        ellipse(x,880,30,30,pal.accent);
        text(String(i+1),x-7,860,30,34,'#fff',true,1);
      });
      object(540,1240,'box',pal.warm);
    }else{
      person(360,1180,t,phase===0?'curious':phase===3?'calm':'help',a.s,1.18,a);
      person(790,1180,t,phase<2?'hold':'help',b.s,1.1,b);
      const prop=scene==='cooking'?'pan':scene==='honesty'||scene==='queueing'?'coin'
        :scene==='tidying'?'broom':scene==='card_game'?'cards':scene==='listening'?'book':'book';
      object(360,1240,prop,pal.accent);
      if(scene==='cooking')ellipse(790,1240,44,26,'rgba(255,220,160,.35)');
      if(phase>=2)bubble(600,830,'check',pal.accent);
    }
    ctx.restore();
    rect(60,1385,960,170,24,'rgba(255,250,238,.86)');
    const notes={drink_choking:'Minum pelan-pelan, sisipkan jeda.',sharing:'Berbagi membuat semua dapat kesempatan.',
      apology:'Mengakui kesalahan membuka jalan perbaikan.',helping:'Menolong dimulai dari satu tangan.',
      queueing:'Antre memberi giliran untuk semua.',tidying:'Merapikan membuat ruang nyaman.',
      listening:'Mendengarkan membuat jawaban lebih jelas.',gratitude:'Terima kasih membuat usaha terlihat.',
      greeting:'Sapa sederhana membuat orang merasa dikenal.',honesty:'Kejujuran menjaga kepercayaan.',
      homework:'Satu langkah kecil menyelesaikan tugas.',then_now:'Konteks berubah, tujuan tetap jelas.',
      myth_fact:'Cerita yang diulang belum tentu fakta.',wrong_right:'Urutan yang tepat membuat hasil lebih aman.',
      problem_solution:'Satu langkah kecil memulai perubahan.',three_steps:'Satu langkah demi langkah, tanpa terburu-buru.',
      choice_ab:'Pilih sesuai kebutuhan, bukan tekanan.',cooking:'Membantu di dapur dimulai dari langkah kecil.',
      card_game:'Bermain bersama lebih seru kalau bergiliran.',everyday:'Satu kebiasaan baik cukup untuk hari ini.'};
    text(notes[scene]||notes.everyday,150,640,780,36,pal.ink,true,2);
    if(model.complete)text('Cerita selesai. Tidak ada janji hasil untuk semua orang.',150,700,780,23,MUTED,false,1);
  }
  return (t,index)=>{
    const model=data.frames[index];
    const pal=PALETTE[model.style]||PALETTE.dulu_sekarang;
    ctx.globalAlpha=1;
    if(model.scene&&model.scene!=='cards'&&model.scene!=='steps'){
      personScene(model,t,pal);
      const tense=model.scene==='drink_choking'&&model.phase>=2&&model.phase<3;
      text('RYUUNDY  /  CERITA MORAL',85,95,880,23,tense?'#ffd9a0':pal.accent,true,1);
      text(data.title,85,150,900,52,tense?'#fff3d8':pal.ink,true,3);
      const cue=data.captionCues.find(c=>c.start<=t&&t<c.end);
      if(cue){ctx.font=font(data.captionFontSize,true);ctx.textAlign='center';ctx.textBaseline='top';ctx.fillStyle=pal.ink;
        cue.text.split('\n').forEach((v,i)=>ctx.fillText(v,540,1435+i*69));}
      ['KENALI','LIHAT','PERBAIKI','SIMPULKAN'].forEach((label,i)=>{
        const active=model.phase===i,x=90+i*250;rect(x,1668,210,7,3,active?pal.accent:'#D8D3C4');text(label,x,1698,220,19,active?pal.accent:MUTED,active,1);});
      return;
    }
    background(pal);
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
