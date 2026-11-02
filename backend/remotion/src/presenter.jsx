import React from 'react';
import {Img} from 'remotion';

const Symbol = ({kind, color, svg}) => {
  if (kind === 'custom' && svg) return <Img src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`} style={{width: 160, height: 160}}/>;
  const leaf = <><path d="M24 126 Q4 26 138 20 Q150 148 24 126Z" fill={color}/><path d="M25 126 L121 39 M55 97 L46 60 M79 74 L116 82" fill="none"/></>;
  const person = <><circle cx="80" cy="42" r="24" fill="#FFD8AE"/><path d="M36 143 V113 Q36 76 80 76 Q124 76 124 113 V143" fill={color}/><path d="M61 143 V117 M99 143 V117"/></>;
  const house = <><path d="M19 77 L80 22 L141 77" fill={color}/><path d="M32 69 V140 H128 V69" fill="#F0DEB9"/><path d="M66 140 V95 H95 V140" fill={color}/></>;
  const body = kind === 'leaf' ? leaf
    : kind === 'stomata' ? <><ellipse cx="47" cy="80" rx="31" ry="59" fill="#83D377" transform="rotate(-12 47 80)"/><ellipse cx="113" cy="80" rx="31" ry="59" fill="#83D377" transform="rotate(12 113 80)"/><ellipse cx="80" cy="80" rx="13" ry="42" fill="#20344B"/><circle cx="43" cy="70" r="8" fill="#CBEC7A"/><circle cx="117" cy="90" r="8" fill="#CBEC7A"/></>
    : kind === 'tree' ? <><path d="M80 144 V57 M80 110 L46 76 M80 93 L116 64" stroke="#B77C4B" strokeWidth="14"/><circle cx="49" cy="53" r="36" fill={color}/><circle cx="105" cy="52" r="39" fill={color}/><circle cx="79" cy="28" r="32" fill="#91D962"/></>
    : kind === 'sun' ? <><circle cx="80" cy="80" r="39" fill="#FFD34B"/>{Array.from({length: 8}, (_, i) => <path key={i} d="M80 8 V25" stroke="#FFD34B" transform={`rotate(${i*45} 80 80)`}/>)}</>
    : kind === 'moon' ? <path d="M111 15 A66 66 0 1 0 145 115 A62 62 0 0 1 111 15Z" fill="#FFF0BA"/>
    : kind === 'cloud' ? <path d="M37 125 Q-2 123 13 82 Q20 60 45 64 Q38 24 82 20 Q123 18 131 60 Q160 62 151 99 Q147 125 120 125Z" fill="#D8EDF7"/>
    : kind === 'water' ? <><path d="M80 13 Q30 79 30 103 A50 50 0 0 0 130 103 Q130 79 80 13Z" fill="#65D6FA"/><path d="M48 104 Q49 126 70 129" stroke="#D5F7FF"/></>
    : kind === 'gas' ? <><path d="M42 91 L90 51 L119 113" stroke="#D9EDF7"/><circle cx="42" cy="91" r="25" fill={color}/><circle cx="90" cy="51" r="29" fill="#F2F2DB"/><circle cx="119" cy="113" r="25" fill={color}/></>
    : kind === 'energy' ? <path d="M97 8 L33 91 H74 L60 152 L133 64 H88Z" fill="#FFE26B"/>
    : kind === 'phone' ? <><rect x="36" y="7" width="88" height="146" rx="18" fill="#F3F5E8"/><rect x="47" y="30" width="66" height="97" rx="7" fill={color}/><path d="M66 19 H94 M74 140 H86"/></>
    : kind === 'chip' ? <>{[32,58,84,110].map(v => <path key={v} d={`M${v} 13 V33 M${v} 128 V148 M13 ${v} H33 M128 ${v} H148`} stroke="#DBE4EC"/>)}<rect x="31" y="31" width="98" height="98" rx="17" fill={color}/><path d="M60 60 H100 V100 H60Z" fill="#233756"/></>
    : kind === 'battery' ? <><rect x="15" y="46" width="126" height="80" rx="12" fill="#F0F0DB"/><path d="M143 69 H151 V103 H143"/><rect x="27" y="58" width="82" height="56" rx="5" fill={color}/></>
    : kind === 'storage' || kind === 'server' ? <>{[25,65,105].map(y => <g key={y}><rect x="18" y={y} width="124" height="34" rx="9" fill={color}/><path d={`M33 ${y+17} H81`} stroke="#E8F7ED"/><circle cx="120" cy={y+17} r="4" fill="#FFDC6B"/></g>)}</>
    : kind === 'app' ? <>{[[20,20],[88,20],[20,88],[88,88]].map(([x,y],i) => <rect key={i} x={x} y={y} width="52" height="52" rx="13" fill={i%2 ? '#F7CF76' : color}/>)}</>
    : kind === 'network' ? <><path d="M30 35 L128 42 L80 126Z" fill="none" stroke="#D7E7F1"/>{[[30,35],[128,42],[80,126]].map(([x,y],i) => <circle key={i} cx={x} cy={y} r="23" fill={color}/>)}</>
    : kind === 'person' ? person
    : kind === 'group' ? <><g transform="translate(-13 18) scale(.78)">{person}</g><g transform="translate(60 3) scale(.78)">{person}</g></>
    : kind === 'house' || kind === 'school' ? house
    : kind === 'book' ? <><path d="M80 37 Q46 10 9 30 V134 Q48 116 80 143 Q112 116 151 134 V30 Q114 10 80 37Z" fill="#F0E8CE"/><path d="M80 37 V143 M29 54 L61 65 M99 65 L131 54 M29 84 L61 95 M99 95 L131 84" stroke={color}/></>
    : kind === 'car' ? <><path d="M12 85 L35 76 L55 39 H111 L133 76 L149 85 V125 H12Z" fill={color}/><path d="M57 48 L46 77 H118 L104 48Z" fill="#CAE7F4"/><circle cx="43" cy="126" r="18" fill="#27354B"/><circle cx="120" cy="126" r="18" fill="#27354B"/></>
    : kind === 'gear' ? <><path d={'M'+Array.from({length:32},(_,i) => {const r=i%4<2 ? 68 : 52;const a=i*Math.PI/16;return `${80+Math.cos(a)*r},${80+Math.sin(a)*r}`;}).join(' L')+'Z'} fill={color}/><circle cx="80" cy="80" r="24" fill="#263956"/></>
    : kind === 'factory' ? <><path d="M14 141 V69 L56 91 V55 L100 79 V40 H144 V141Z" fill={color}/><path d="M110 40 V12 H135 V40" fill="#DCEAF0"/><path d="M34 116 H48 M71 116 H85 M111 116 H125" stroke="#FFE383"/></>
    : kind === 'coin' ? <><circle cx="80" cy="80" r="65" fill="#F7CB55"/><circle cx="80" cy="80" r="48" fill="none" stroke="#B47B2D"/><path d="M96 54 Q58 38 59 65 Q60 82 85 83 Q110 85 100 106 Q90 121 61 107 M80 37 V126" fill="none" stroke="#865F32"/></>
    : kind === 'shield' ? <><path d="M80 13 L140 36 V80 Q138 127 80 149 Q22 127 20 80 V36Z" fill={color}/><path d="M49 80 L71 104 L113 57" fill="none" stroke="#E8F7E9"/></>
    : kind === 'clock' ? <><circle cx="80" cy="80" r="65" fill="#EFF0DA"/><path d="M80 33 V80 L112 99" stroke={color}/></>
    : kind === 'magnifier' ? <><circle cx="66" cy="63" r="47" fill="#9BE4DF" fillOpacity=".6"/><path d="M102 101 L146 147" stroke="#EFCB71" strokeWidth="20"/><circle cx="66" cy="63" r="23" fill={color}/></>
    : kind === 'globe' ? <><circle cx="80" cy="80" r="65" fill="#6FCDEE"/><ellipse cx="80" cy="80" rx="31" ry="65" fill="none"/><path d="M15 80 H145 M28 40 H132 M28 120 H132" stroke={color}/></>
    : kind === 'flower' ? <><path d="M80 144 V78" stroke="#74C585"/><path d="M80 119 Q22 98 30 130 Q58 149 80 119" fill="#74C585"/>{[0,1,2,3,4].map(i => <ellipse key={i} cx="80" cy="35" rx="21" ry="30" fill={color} transform={`rotate(${i*72} 80 66)`}/>)}<circle cx="80" cy="66" r="20" fill="#FFE166"/></>
    : kind === 'insect' ? <><ellipse cx="55" cy="52" rx="30" ry="22" fill="#D9F2F5"/><ellipse cx="105" cy="52" rx="30" ry="22" fill="#D9F2F5"/><ellipse cx="80" cy="96" rx="45" ry="29" fill="#F2CE58"/><path d="M66 74 V119 M89 74 V119"/><circle cx="32" cy="90" r="20" fill="#34465B"/></>
    : kind === 'heart' ? <path d="M80 139 L23 85 Q-8 42 27 22 Q60 4 80 38 Q100 4 133 22 Q168 42 137 85Z" fill="#EE8998"/>
    : kind === 'food' ? <><ellipse cx="80" cy="111" rx="67" ry="33" fill="#EEEBD4"/><path d="M38 107 Q21 60 61 65 Q64 22 100 43 Q141 43 126 107Z" fill={color}/></>
    : <><path d="M19 51 L80 20 L141 51 V122 L80 153 L19 122Z" fill={color}/><path d="M19 51 L80 83 L141 51 M80 83 V153" fill="none"/></>;
  return <svg width="160" height="160" viewBox="0 0 160 160" fill="none" stroke="#20344B" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round">{body}</svg>;
};

const objectPositions = (scene) => {
  const count = scene.objects.length;
  const centerLayout = ['focus','ecosystem','cycle'].includes(scene.layout) && count > 2;
  const focus = scene.objects.findIndex(o => o.id === scene.focus);
  const satellites = [[155,175],[685,175],[155,555],[685,555]];
  let satellite = 0;
  return scene.objects.map((object,index) => {
    let point;
    if (centerLayout) point = index === focus ? [420,365] : satellites[satellite++];
    else if (count <= 3) point = [140 + index * (560 / Math.max(1,count-1)), 355];
    else point = [index%3 * 270 + 150, index < 3 ? 215 : 535];
    return {...object, x:point[0], y:point[1]};
  });
};

export const PresenterSceneGraphic = ({beat, progress, localSeconds}) => {
  const scene = beat.presentationScene;
  const objects = objectPositions(scene);
  const night = beat.sceneTime === 'night';
  const rainy = beat.sceneWeather === 'rain';
  const pulse = (Math.sin(localSeconds*2.5)+1)/2;
  const accent = beat.accent || '#73DFC2';
  return <div style={{position:'relative', width:840, height:800, transform:`scale(${.96+Math.min(1,progress)*.04})`}}>
    <svg width="840" height="760" viewBox="0 0 840 760" style={{position:'absolute', overflow:'visible'}}>
      <defs>
        <linearGradient id="presenterSky" x2="0" y2="1"><stop stopColor={night ? '#182749' : rainy ? '#637D98' : '#A2DCE5'}/><stop offset="1" stopColor={night ? '#3B4267' : '#D8EBC5'}/></linearGradient>
      </defs>
      <rect x="6" y="6" width="828" height="740" rx="58" fill="url(#presenterSky)" stroke="#233B57" strokeWidth="8"/>
      {beat.sceneSetting === 'forest' ? <path d="M12 630 Q220 570 420 630 T828 625 V700 Q828 742 790 742 H50 Q12 742 12 700Z" fill="#65A47A" opacity=".7"/> : null}
      {night ? <>{[0,1,2,3,4].map(i=><circle key={i} cx={80+i*170} cy={55+(i%2)*45} r="4" fill="#F8EEC9"/>)}</> : null}
      {scene.relations.map((relation,index) => {
        const from = objects.find(o=>o.id===relation.from);
        const to = objects.find(o=>o.id===relation.to);
        if (!from || !to) return null;
        const dx=to.x-from.x, dy=to.y-from.y, length=Math.hypot(dx,dy)||1;
        const x1=from.x+dx/length*95, y1=from.y+dy/length*95;
        const x2=to.x-dx/length*95, y2=to.y-dy/length*95;
        const travel=(localSeconds*.28+index*.23)%1;
        const angle=Math.atan2(dy,dx)*180/Math.PI;
        return <g key={`${relation.from}-${relation.to}-${index}`}>
          <path d={`M${x1} ${y1} L${x2} ${y2}`} stroke="#284C63" strokeWidth="9" opacity=".65" strokeLinecap="round" strokeDasharray={relation.kind==='compare' ? '12 13' : undefined}/>
          <path d="M-15 -12 L0 0 L-15 12" transform={`translate(${x2} ${y2}) rotate(${angle})`} stroke="#284C63" strokeWidth="7" fill="none" strokeLinecap="round"/>
          {relation.kind==='exchange' ? <path d="M15 -12 L0 0 L15 12" transform={`translate(${x1} ${y1}) rotate(${angle})`} stroke="#284C63" strokeWidth="7" fill="none"/> : null}
          <circle cx={x1+(x2-x1)*travel} cy={y1+(y2-y1)*travel} r="11" fill="#FFE28A" stroke="#284C63" strokeWidth="3"/>
          {relation.label ? <text x={(x1+x2)/2} y={(y1+y2)/2-20} textAnchor="middle" fill={night ? '#F4F7E5' : '#1D3B52'} fontSize="23" fontWeight="800" stroke={night ? '#243451' : '#DCECCF'} strokeWidth="6" paintOrder="stroke">{relation.label}</text> : null}
        </g>;
      })}
      {rainy ? Array.from({length:14},(_,i)=><path key={i} d={`M${40+i*58} ${50+(localSeconds*190+i*47)%600} l-10 27`} stroke="#E5F7FF" strokeWidth="5" opacity=".6"/>) : null}
    </svg>
    {objects.map((object,index)=>{
      const enter=Math.min(1,Math.max(0,(localSeconds-index*.12)/.35));
      const motion=object.action;
      const rotate=motion==='rotate' ? localSeconds*23 : motion==='sway' ? Math.sin(localSeconds*1.8)*5 : motion==='shake' ? Math.sin(localSeconds*17)*3 : 0;
      const scale=motion==='grow' ? .78+Math.min(1,localSeconds/3)*.22 : motion==='pulse' ? .97+pulse*.05 : 1;
      const float=motion==='float' ? Math.sin(localSeconds*2+index)*8 : 0;
      return <div key={object.id} style={{position:'absolute',left:object.x-85,top:object.y-85,width:170,opacity:enter,transform:`translateY(${(1-enter)*24+float}px) scale(${scale})`}}>
        {object.id===scene.focus ? <div style={{position:'absolute',left:-14,top:-14,width:198,height:198,borderRadius:'50%',background:`${accent}30`,border:`2px solid ${accent}80`,transform:`scale(${1+pulse*.04})`}}/> : null}
        <div style={{position:'relative',transform:`rotate(${rotate}deg)`,filter:'drop-shadow(0 10px 8px rgba(0,0,0,.16))'}}><Symbol {...object} color={object.color || '#63C995'}/></div>
        <div style={{position:'absolute',top:175,left:-35,right:-35,textAlign:'center',fontSize:27,fontWeight:900,lineHeight:1.12,color:night ? '#F3F8EC' : '#1A354B',textShadow:night ? '0 2px 3px #17213D' : '0 2px 0 #E9F4D9',overflowWrap:'anywhere'}}>{object.label}</div>
      </div>;
    })}
  </div>;
};
