// Original Nara/Bimo vector cast and educational worlds. Data never becomes code.
export function createEducationRenderer(ctx,data) {
  const C={ink:'#203e50',muted:'#627d89',teal:'#298f86',coral:'#ed887a',blue:'#6daedd',gold:'#efbd58'};
  const font=(size,bold=false)=>`${bold?700:400} ${size}px "DejaVu Sans",sans-serif`;
  function rect(x,y,w,h,r,color,stroke=null){ctx.beginPath();ctx.roundRect(x,y,w,h,r);ctx.fillStyle=color;ctx.fill();if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=5;ctx.stroke();}}
  function ellipse(x,y,rx,ry,color){ctx.beginPath();ctx.ellipse(x,y,rx,ry,0,0,Math.PI*2);ctx.fillStyle=color;ctx.fill();}
  function path(points,color,width=8){ctx.beginPath();points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.strokeStyle=color;ctx.lineWidth=width;ctx.lineCap='round';ctx.lineJoin='round';ctx.stroke();}
  function polygon(points,color){ctx.beginPath();points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.closePath();ctx.fillStyle=color;ctx.fill();}
  function text(value,x,y,width,size=38,color=C.ink,bold=false,max=3){
    ctx.font=font(size,bold);ctx.textAlign='left';ctx.textBaseline='top';ctx.fillStyle=color;
    const rows=[];let row='';
    for(const word of String(value).split(/\s+/)){
      const next=row?row+' '+word:word;
      if(row&&ctx.measureText(next).width>width){rows.push(row);row=word;}else row=next;
    }
    if(row)rows.push(row);
    rows.slice(0,max).forEach((v,i)=>ctx.fillText(v,x,y+i*(size+12)));
  }
  function centered(value,x,y,size=48,color=C.ink){ctx.font=font(size,true);ctx.textAlign='center';ctx.textBaseline='top';ctx.fillStyle=color;ctx.fillText(value,x,y);}
  function character(name,x,y,t,point=false){
    const first=name==='Nara', shirt=first?C.teal:C.coral,bob=3*Math.sin(t*2.1),sy=y+bob;
    ellipse(x,sy+145,80,15,'#bad8cc');
    path([[x-24,sy+65],[x-35,sy+130]],C.ink,15);path([[x+24,sy+65],[x+35,sy+130]],C.ink,15);
    rect(x-48,sy-12,96,93,32,shirt);
    path([[x-40,sy],[x-75,sy+40]],shirt,18);
    const hand=point?[x+100,sy-90+6*Math.sin(t*1.3)]:[x+75,sy+35];
    path([[x+40,sy],[x+68,sy-20],hand],shirt,18);ellipse(hand[0],hand[1],13,13,'#e6b18a');
    ellipse(x,sy-83,64,69,first?'#754e3d':'#59473f');
    if(first){ellipse(x-57,sy-67,22,30,'#754e3d');ellipse(x+57,sy-67,22,30,'#754e3d');}
    ellipse(x,sy-70,53,56,'#f4c9a6');
    ellipse(x-17,sy-76,4,t%4.4<.12?1:6,C.ink);ellipse(x+17,sy-76,4,t%4.4<.12?1:6,C.ink);
    ctx.beginPath();ctx.arc(x,sy-58,16,.15,Math.PI-.15);ctx.strokeStyle=C.ink;ctx.lineWidth=4;ctx.stroke();
    ellipse(x-31,sy-56,10,5,'#eea18f');ellipse(x+31,sy-56,10,5,'#eea18f');
    centered(name,x,sy+163,25,C.muted);
  }
  function apple(x,y,active){
    ellipse(x,y+60,98,17,'#d7dec6');
    ellipse(x-26,y,53,63,active?C.coral:'#ecb5a5');ellipse(x+26,y,53,63,active?C.coral:'#ecb5a5');
    path([[x,y-50],[x+5,y-82]],'#896344',10);ellipse(x+28,y-73,27,12,C.teal);
    ellipse(x-38,y-18,9,19,'#ffded4');
    if(active){ellipse(x+58,y-55,22,22,C.teal);path([[x+48,y-55],[x+56,y-48],[x+69,y-64]],'#fff',5);}
  }
  function shape(kind,x,y,color,size=72,outline=false){
    ctx.beginPath();
    if(kind==='circle')ctx.arc(x,y,size,0,Math.PI*2);
    else if(kind==='triangle'){ctx.moveTo(x,y-size);ctx.lineTo(x+size,y+size*.8);ctx.lineTo(x-size,y+size*.8);ctx.closePath();}
    else ctx.roundRect(x-size,y-size,size*2,size*2,14);
    if(outline){ctx.strokeStyle=color;ctx.lineWidth=7;ctx.setLineDash([12,10]);ctx.stroke();ctx.setLineDash([]);}else{ctx.fillStyle=color;ctx.fill();}
  }
  function block(x,y,color=C.blue){
    rect(x-53,y-53,106,106,17,color);polygon([[x-53,y-53],[x-28,y-77],[x+75,y-77],[x+53,y-53]],'#a6cdea');polygon([[x+53,y-53],[x+75,y-77],[x+75,y+29],[x+53,y+53]],'#4e8eba');
  }
  function car(x,y){
    rect(x-93,y-32,186,65,23,C.gold);polygon([[x-59,y-32],[x-28,y-84],[x+38,y-84],[x+69,y-32]],C.coral);
    polygon([[x-37,y-39],[x-19,y-69],[x+29,y-69],[x+46,y-39]],'#d6eef3');
    for(const wx of [x-53,x+53]){ellipse(wx,y+32,27,27,C.ink);ellipse(wx,y+32,12,12,'#f1f4ed');}
  }
  function background(t){
    ctx.fillStyle=data.education.series==='nature'?'#f4f3dd':'#faf3e7';ctx.fillRect(0,0,1080,1920);
    ellipse(145,615,360,300,'#e5eee1');ellipse(1030,850,410,380,'#f4dfce');
    ellipse(540,1240,600,115,'#dbe6d2');
    rect(80,490,920,760,70,'#eef2e3');
    ellipse(925,435,48,48,C.gold);
    for(let i=0;i<5;i++)ellipse(116+i*200,465+10*Math.sin(t+i),4,4,'#bccdc1');
  }
  function activity(model,t){
    const topic=data.topic;
    if(topic==='count_objects'){
      rect(150,790,780,170,42,'#e7dabd');
      model.props.forEach(p=>apple(p.x,p.y,p.active));
      if(model.learning.count)centered(String(model.learning.count),540,1020,96,C.teal);
    }else if(topic==='shape_match'){
      rect(130,495,820,200,35,'#e1d7bc');
      ['circle','triangle','square'].forEach((kind,i)=>shape(kind,270+i*270,590,'#96ab9c',76,true));
      model.props.forEach((p,i)=>shape(p.kind,p.x,p.y,[C.coral,C.teal,C.gold][i]));
      if(model.complete)centered('Bentuk sama, pasangan tepat',540,920,35,C.teal);
    }else if(topic==='color_pattern'){
      model.props.filter(p=>p.visible).forEach((p,i)=>{ellipse(p.x,p.y,69,69,p.color);centered(String(i+1),p.x,p.y-18,32,'#fff');});
      centered('MERAH  •  BIRU',540,1010,35,C.teal);
    }else if(topic==='tidy_toys'){
      rect(600,850,220,170,24,'#d5c3a3');
      model.props.forEach(p=>block(p.x,p.y));
      polygon([[590,900],[830,900],[817,1035],[603,1035]],C.teal);centered('MAINAN',710,960,24,'#fff');
      if(model.complete)centered('Tiga balok kembali ke kotak',540,650,36,C.teal);
    }else if(topic==='take_turns'){
      path([[280,1010],[800,1010]],'#c2d4c4',8);model.props.forEach(p=>car(p.x,p.y));
      text(model.learning.owner+' sedang bermain',240,630,650,40,C.teal,true,2);
    }else if(topic==='plant_growth'){
      const {root,stem,leaves}=model.learning;
      rect(300,935,480,220,22,'#bd9576');rect(300,935,480,28,9,'#9b775e');
      ellipse(540,970,24,14,C.gold);
      path([[540,970],[535,970+125*root],[492,970+160*root]],'#f1dfbb',12);
      if(root>.2)path([[535,1000],[590,1000+90*root]],'#f1dfbb',8);
      path([[540,950],[540,950-310*stem]],C.teal,16);
      if(leaves>0){ellipse(540-65*leaves,950-220*stem,66*leaves,27*leaves,'#68aa71');ellipse(540+65*leaves,950-270*stem,66*leaves,27*leaves,'#459a72');}
      ellipse(840,610,56,56,C.gold);text('WAKTU DIPERCEPAT',290,525,640,27,C.teal,true,1);
      text('Pertumbuhan asli memerlukan waktu.',245,1340,650,27,C.muted,false,1);
      for(let i=0;i<4;i++)ellipse(360+i*42,790+(t*50+i*31)%110,5,9,'#70b3d0');
    }else if(topic==='shadow_light'){
      rect(850,620,50,400,8,'#fff','#bacdcc');
      polygon([[215,780],[850,640],[850,990],[215,850]],'#fff1b0');
      rect(125,785,100,70,15,C.gold);path([[165,855],[165,1000]],C.ink,12);
      model.props.forEach(p=>block(p.x,p.y));
      if(model.learning.shadow)rect(851,760,48,135,3,`rgba(42,65,74,${model.learning.blocking*.75})`);
      text('Lampu',100,700,200,27,C.muted);text('Benda',465,1160,200,27,C.muted);text('Layar',820,575,200,27,C.muted);
    }
  }
  return (t,index)=>{
    const model=data.frames[index];ctx.globalAlpha=1;background(t);
    text('RYUUNDY  /  BELAJAR BERSAMA',85,95,880,23,C.teal,true,1);
    text(data.title,85,160,900,62,C.ink,true,3);
    text(data.education.concept,85,370,880,28,C.muted,false,2);
    activity(model,t);
    if(data.topic==='take_turns'){
      character(model.characters[0],270,1160,t,model.learning.owner===model.characters[0]);
      character(model.characters[1],820,1160,t,model.learning.owner===model.characters[1]);
    }else{
      character(model.characters[0],180,1135,t,model.phase===1);
      character(model.characters[1],900,1135,t,false);
    }
    // Captions sit in their own quiet plane below the complete animation world.
    const cue=data.captionCues.find(c=>c.start<=t&&t<c.end);
    if(cue){
      ctx.font=font(data.captionFontSize,true);ctx.textAlign='center';ctx.textBaseline='top';ctx.fillStyle=C.ink;
      cue.text.split('\n').forEach((v,i)=>ctx.fillText(v,540,1435+i*69));
    }
    ['KENALI','COBA BERSAMA','LIHAT HASIL'].forEach((label,i)=>{
      const x=100+i*300,active=model.phase===i;
      rect(x,1680,245,7,3,active?C.teal:'#cad8cf');text(label,x,1710,250,20,active?C.teal:C.muted,active,1);
    });
  };
}
