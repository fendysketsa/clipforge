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
  const SKIN='#f2c6a2', HAIR='#453a34', SHIRT_A='#3e8e7a', SHIRT_B='#e08a72';
  function person(x,y,t,mood,shirt,scale=1){
    ctx.save();ctx.translate(x,y);ctx.scale(scale,scale);
    const bob=3*Math.sin(t*2.2), sy=bob;
    ellipse(0,sy+152,74,13,'#cdd8c8');
    path([[-22,sy+62],[-31,sy+126]],'#41524e',13);path([[22,sy+62],[31,sy+126]],'#41524e',13);
    rect(-46,sy-14,92,92,30,shirt);
    const handL=mood==='cough'?[-10,sy-28]:mood==='drink'?[38,sy-66]:mood==='help'?[84,sy-10]:[-70,sy+28];
    const handR=mood==='help'?[-84,sy-10]:[70,sy+28];
    for(const [hx,hy] of [handL,handR]){path([[hx>0?40:-40,sy-2],[hx*0.72,hy+8],[hx,hy]],shirt,14);ellipse(hx,hy,11,11,SKIN);}
    ellipse(0,sy-84,57,62,HAIR);ellipse(0,sy-73,49,51,SKIN);
    ellipse(-16,sy-78,4,mood==='cough'?1:5,'#33443f');ellipse(16,sy-78,4,mood==='cough'?1:5,'#33443f');
    if(mood==='cough'){
      ellipse(0,sy-50,13,10,'#8f5b5b');
      for(let i=0;i<3;i++){const a=t*5+i*2.1;path([[64+i*15,sy-86+Math.sin(a)*8],[86+i*16,sy-96+Math.sin(a)*12]],'#9fc6cf',4);}
    }else if(mood==='sad'){
      ctx.beginPath();ctx.arc(0,sy-38,13,Math.PI+0.25,2*Math.PI-0.25);ctx.strokeStyle='#6b5a52';ctx.lineWidth=4;ctx.stroke();
    }else{
      ctx.beginPath();ctx.arc(0,sy-52,14,0.2,Math.PI-0.2);ctx.strokeStyle='#6b5a52';ctx.lineWidth=4;ctx.stroke();
    }
    if(mood==='cough'){ellipse(48,sy-24,9,9,'#e9a9a2');}
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
    else ellipse(x,y,40,40,color);
  }
  function personScene(model,t,pal){
    const stage=model.stage_starts||[0,4,8], phase=model.phase, scene=model.scene;
    const inCough=scene==='drink_choking'&&phase>=2&&phase<3&&t>stage[1]+(stage[2]-stage[1])*.45;
    ctx.fillStyle='#f8f3e6';ctx.fillRect(0,0,1080,1920);
    ellipse(160,620,330,280,pal.soft);ellipse(1000,760,340,320,pal.warm);
    rect(110,930,860,26,12,'#c9b79a');rect(120,956,22,360,8,'#b5a184');rect(940,956,22,360,8,'#b5a184');
    if(scene==='drink_choking'){
      const mood=phase===0?'curious':phase===1?'hold':inCough?'cough':phase===3?'calm':'drink';
      person(360,1180,t,mood,SHIRT_A,1.15);
      const glassY=mood==='drink'?1090:mood==='hold'?1040:960;
      if(inCough)glass(600,1015,0);
      else if(phase<3)glass(mood==='drink'?408:360,glassY,mood==='drink'?-.55:0);
      if(phase>=2||model.complete){
        person(780,1180,t,phase===3?'help':'curious',SHIRT_B,1.05);
        if(phase===3)bubble(560,1010,'check',pal.accent);
      }
    }else if(scene==='then_now'||scene==='choice_ab'){
      person(320,1180,t,phase<2?'curious':'calm',SHIRT_A,1.08);
      person(800,1180,t,phase<2?'hold':'help',SHIRT_B,1.08);
      object(320,1010,scene==='then_now'?'book':'phone',pal.accent);
      object(800,1010,phase<2?'phone':'book',pal.warm);
      if(phase>=2)bubble(560,820,'check',pal.accent);
    }else if(scene==='myth_fact'||scene==='wrong_right'){
      person(340,1180,t,phase<2?'curious':phase===2?'hold':'calm',SHIRT_A,1.1);
      person(780,1180,t,phase<2?'hold':phase===2?'cough':'help',SHIRT_B,1.1);
      bubble(340,880,phase<2?'?':'check',phase<2?'#d08a65':pal.accent);
      object(780,1010,'box',pal.warm);
    }else if(scene==='problem_solution'||scene==='three_steps'){
      const spots=[260,540,820],moods=['curious','hold',model.complete?'calm':'help'];
      spots.forEach((x,i)=>{
        person(x,1180,t,moods[i],i===1?SHIRT_B:SHIRT_A,.82);
        ellipse(x,880,30,30,pal.accent);
        text(String(i+1),x-7,860,30,34,'#fff',true,1);
      });
      object(540,1010,'box',pal.warm);
    }else{
      person(360,1180,t,phase===0?'curious':phase===3?'calm':'help',SHIRT_A,1.12);
      person(790,1180,t,phase<2?'hold':'help',SHIRT_B,1.05);
      object(360,1010,'book',pal.accent);
      if(phase>=2)bubble(600,830,'check',pal.accent);
    }
    const notes={drink_choking:'Minum pelan-pelan, sisipkan jeda.',sharing:'Berbagi membuat semua dapat kesempatan.',
      apology:'Mengakui kesalahan membuka jalan perbaikan.',helping:'Menolong dimulai dari satu tangan.',
      queueing:'Antre memberi giliran untuk semua.',tidying:'Merapikan membuat ruang nyaman.',
      listening:'Mendengarkan membuat jawaban lebih jelas.',gratitude:'Terima kasih membuat usaha terlihat.',
      greeting:'Sapa sederhana membuat orang merasa dikenal.',honesty:'Kejujuran menjaga kepercayaan.',
      homework:'Satu langkah kecil menyelesaikan tugas.',then_now:'Konteks berubah, tujuan tetap jelas.',
      myth_fact:'Cerita yang diulang belum tentu fakta.',wrong_right:'Urutan yang tepat membuat hasil lebih aman.',
      problem_solution:'Satu langkah kecil memulai perubahan.',three_steps:'Satu langkah demi langkah, tanpa terburu-buru.',
      choice_ab:'Pilih sesuai kebutuhan, bukan tekanan.',everyday:'Satu kebiasaan baik cukup untuk hari ini.'};
    text(notes[scene]||notes.everyday,150,640,780,36,pal.ink,true,2);
    if(model.complete)text('Cerita selesai. Tidak ada janji hasil untuk semua orang.',150,700,780,23,MUTED,false,1);
  }
  return (t,index)=>{
    const model=data.frames[index];
    const pal=PALETTE[model.style]||PALETTE.dulu_sekarang;
    ctx.globalAlpha=1;
    if(model.scene&&model.scene!=='cards'&&model.scene!=='steps'){
      personScene(model,t,pal);
      text('RYUUNDY  /  CERITA MORAL',85,95,880,23,pal.accent,true,1);
      text(data.title,85,150,900,52,pal.ink,true,3);
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
