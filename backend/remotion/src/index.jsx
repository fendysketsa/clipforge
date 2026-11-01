import React from 'react';
import {
  AbsoluteFill,
  Composition,
  Img,
  OffthreadVideo,
  Sequence,
  Easing,
  interpolate,
  registerRoot,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'};

const stableNumber = (value) => String(value || '').split('').reduce(
  (total, character) => ((total * 31) + character.charCodeAt(0)) % 997,
  17,
);

const cameraTransform = (motion, progress, portrait, intensity = 1) => {
  const translatesFrame = ['pan_left', 'pan_right', 'drift_up', 'tilt_down'].includes(motion);
  const safeIntensity = Math.max(.72, Math.min(1.2, intensity));
  const rawScaleStart = motion === 'pull_out' ? 1.14 : translatesFrame ? 1.13 : 1.025;
  const rawScaleEnd = motion === 'pull_out' ? 1.03 : translatesFrame ? 1.13 : 1.13;
  const scaleStart = 1 + (rawScaleStart - 1) * safeIntensity;
  const scaleEnd = 1 + (rawScaleEnd - 1) * safeIntensity;
  const scale = interpolate(progress, [0, 1], [scaleStart, scaleEnd], clamp);
  const distance = (portrait ? 4.5 : 3.0) * safeIntensity;
  const x = motion === 'pan_left'
    ? interpolate(progress, [0, 1], [distance, -distance], clamp)
    : motion === 'pan_right'
      ? interpolate(progress, [0, 1], [-distance, distance], clamp)
      : 0;
  const y = motion === 'drift_up'
    ? interpolate(progress, [0, 1], [distance, -distance], clamp)
    : motion === 'tilt_down'
      ? interpolate(progress, [0, 1], [-distance, distance], clamp)
      : 0;
  return `translate3d(${x}%, ${y}%, 0) scale(${scale})`;
};

const Atmosphere = ({shot}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const accent = shot.motionDesign?.accentColor || '#65B7FF';
  const seed = stableNumber(shot.id);
  const driftX = Math.sin((frame / fps) * .34 + seed) * 3;
  const driftY = Math.cos((frame / fps) * .27 + seed * .5) * 2;
  return (
    <AbsoluteFill style={{
      pointerEvents: 'none',
      opacity: .10,
      mixBlendMode: 'soft-light',
      transform: `translate3d(${driftX}%, ${driftY}%, 0)`,
      background: [
        `radial-gradient(circle at ${20 + seed % 45}% ${18 + seed % 30}%, ${accent}42 0%, transparent 34%)`,
        `radial-gradient(circle at ${76 - seed % 20}% ${66 + seed % 18}%, ${accent}22 0%, transparent 30%)`,
      ].join(','),
    }}/>
  );
};

const TransitionOverlay = ({design = {}}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const length = Math.max(4, Math.round(fps * .24));
  if (frame > length) return null;
  const p = interpolate(frame, [0, length], [0, 1], clamp);
  const accent = design.accentColor || '#65B7FF';
  const type = design.transition || 'directional_wipe';
  if (type === 'film_fade') {
    return <AbsoluteFill style={{background: '#030507', opacity: interpolate(p, [0, 1], [1, 0], clamp)}}/>;
  }
  if (type === 'match_flash') {
    return <AbsoluteFill style={{background: '#fff', opacity: interpolate(p, [0, .22, 1], [.62, .08, 0], clamp)}}/>;
  }
  if (type === 'aperture') {
    const radius = interpolate(p, [0, 1], [0, 78], clamp);
    return <AbsoluteFill style={{
      background: '#04070d',
      WebkitMaskImage: `radial-gradient(circle at 50% 50%, transparent ${radius}%, #000 ${radius + .8}%)`,
      maskImage: `radial-gradient(circle at 50% 50%, transparent ${radius}%, #000 ${radius + .8}%)`,
    }}/>
  }
  if (type === 'split_wipe') {
    const offset = interpolate(p, [0, 1], [0, 102], clamp);
    return (
      <AbsoluteFill>
        <div style={{position: 'absolute', inset: '0 50% 0 0', background: '#060912', transform: `translateX(-${offset}%)`}}/>
        <div style={{position: 'absolute', inset: '0 0 0 50%', background: accent, transform: `translateX(${offset}%)`, opacity: .92}}/>
      </AbsoluteFill>
    );
  }
  if (type === 'light_sweep') {
    return <AbsoluteFill style={{
      opacity: 1 - p,
      transform: `translateX(${interpolate(p, [0, 1], [-115, 115], clamp)}%) skewX(-12deg)`,
      background: `linear-gradient(90deg, transparent 18%, ${accent}CC 47%, #fff 50%, ${accent}99 53%, transparent 82%)`,
      mixBlendMode: 'screen',
    }}/>
  }
  if (type === 'brush_wipe') {
    return (
      <AbsoluteFill style={{overflow: 'hidden'}}>
        {[0, 1, 2, 3, 4].map((stripe) => (
          <div key={stripe} style={{
            position: 'absolute',
            left: '-12%',
            right: '-12%',
            top: `${stripe * 20 - 2}%`,
            height: '24%',
            background: stripe % 2 ? '#080b13' : accent,
            transform: `translateX(${interpolate(p, [0, 1], [0, 115 + stripe * 4], clamp)}%) rotate(-1.5deg)`,
          }}/>
        ))}
      </AbsoluteFill>
    );
  }
  return <AbsoluteFill style={{
    background: `linear-gradient(105deg, #050810 0%, ${accent} 52%, #050810 100%)`,
    transform: `translateX(${interpolate(p, [0, 1], [0, 108], clamp)}%) skewX(-8deg)`,
  }}/>;
};

const CinematicFinish = ({shot}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const seed = stableNumber(shot.id);
  const grainX = ((frame * 17 + seed) % 23) - 11;
  const grainY = ((frame * 29 + seed) % 19) - 9;
  const breathe = .018 + Math.sin((frame / fps) * .72 + seed) * .006;
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <AbsoluteFill style={{
        boxShadow: 'inset 0 0 150px rgba(0,0,0,.46)',
        background: `linear-gradient(180deg, rgba(255,244,226,${breathe}) 0%, transparent 38%, rgba(0,8,18,.055) 100%)`,
      }}/>
      <AbsoluteFill style={{
        inset: '-3%',
        opacity: .038,
        mixBlendMode: 'soft-light',
        transform: `translate3d(${grainX}px, ${grainY}px, 0)`,
        backgroundImage: [
          'repeating-radial-gradient(circle at 20% 30%, rgba(255,255,255,.85) 0 .7px, transparent .9px 3px)',
          'repeating-radial-gradient(circle at 70% 60%, rgba(0,0,0,.75) 0 .6px, transparent .8px 2.7px)',
        ].join(','),
        backgroundSize: '7px 9px, 9px 8px',
      }}/>
    </AbsoluteFill>
  );
};

const Shot = ({shot}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const duration = Math.max(1, Math.round(shot.duration * fps));
  const progress = interpolate(frame, [0, duration - 1], [0, 1], clamp);
  const reveal = spring({fps, frame, config: {damping: 18, stiffness: 115}});
  const portrait = height > width;
  const design = shot.motionDesign || {};
  const accent = design.accentColor || '#65B7FF';
  const titleOnRight = !portrait && shot.subjectPlacement === 'left_third';
  const mediaStyle = {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
    transform: cameraTransform(shot.cameraMotion, progress, portrait, design.intensity),
    filter: 'saturate(1.025) contrast(1.045) brightness(.995)',
  };
  const src = staticFile(`assets/${shot.asset}`);

  return (
    <AbsoluteFill style={{backgroundColor: '#05070b', overflow: 'hidden'}}>
      {shot.kind === 'video' ? (
        <OffthreadVideo src={src} muted loop style={mediaStyle}/>
      ) : (
        <Img src={src} style={mediaStyle}/>
      )}
      <AbsoluteFill style={{
        background: portrait
          ? 'linear-gradient(180deg, rgba(3,6,12,.10) 0%, rgba(3,6,12,.02) 48%, rgba(3,6,12,.78) 100%)'
          : 'linear-gradient(90deg, rgba(3,6,12,.24) 0%, rgba(3,6,12,.02) 52%, rgba(3,6,12,.38) 100%)',
      }}/>
      <AbsoluteFill style={{
        boxShadow: 'inset 0 0 120px rgba(0,0,0,.42)',
        border: '1px solid rgba(255,255,255,.035)',
      }}/>
      <Atmosphere shot={shot}/>
      {shot.onScreenText ? (
        <div style={{
          position: 'absolute',
          left: portrait ? 72 : titleOnRight ? '42%' : 96,
          right: portrait ? 72 : titleOnRight ? 96 : '42%',
          top: portrait ? 150 : 90,
          textAlign: titleOnRight ? 'right' : 'left',
          opacity: interpolate(progress, [0, .08, .72, .9], [0, 1, 1, 0], clamp),
          transform: `translateY(${(1 - reveal) * 24}px)`,
          color: design.titleStyle === 'proof' ? accent : '#fff',
          fontFamily: 'Arial, sans-serif',
          fontWeight: 800,
          fontSize: portrait ? 46 : 48,
          lineHeight: 1.08,
          letterSpacing: '-0.025em',
          textShadow: '0 3px 22px rgba(0,0,0,.72)',
        }}>
          {shot.onScreenText.split(/\s+/).map((word, index) => {
            const wordReveal = spring({
              fps,
              frame: Math.max(0, frame - index * 3),
              config: {damping: 17, stiffness: 150, mass: .72},
            });
            return (
              <span key={`${index}-${word}`} style={{
                display: 'inline-block',
                marginRight: '.24em',
                opacity: wordReveal,
                transform: `translateY(${(1 - wordReveal) * 26}px) scale(${.92 + wordReveal * .08})`,
              }}>{word}</span>
            );
          })}
        </div>
      ) : null}
      <CinematicFinish shot={shot}/>
      <TransitionOverlay design={design}/>
    </AbsoluteFill>
  );
};

const Caption = ({cue}) => {
  const {height, width} = useVideoConfig();
  if (!cue?.text) return null;
  const portrait = height > width;
  return (
    <div style={{
      position: 'absolute',
      left: portrait ? 76 : 150,
      right: portrait ? 76 : 150,
      bottom: portrait ? 205 : 78,
      textAlign: 'center',
      fontFamily: 'Arial, sans-serif',
      fontSize: portrait ? 43 : 38,
      lineHeight: 1.22,
      fontWeight: 800,
      color: '#fff',
      textShadow: '0 3px 3px #000, 0 0 14px rgba(0,0,0,.9)',
      padding: portrait ? '14px 20px 16px' : '10px 18px 12px',
      borderRadius: 18,
      background: 'rgba(0,0,0,.46)',
      boxShadow: '0 8px 28px rgba(0,0,0,.24)',
      opacity: 1,
      transform: 'translate3d(0,0,0)',
    }}>
      {cue.text}
    </div>
  );
};

const Story = ({shots = [], captionCues = [], watermark = '@ryuundy', captionsEnabled = true}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const activeCaption = captionCues.find((cue) => (
    frame >= Number(cue.startFrame || 0) && frame < Number(cue.endFrame || 0)
  ));
  return (
    <AbsoluteFill style={{backgroundColor: '#05070b'}}>
      {shots.map((shot) => (
        <Sequence
          key={shot.id}
          from={Number.isFinite(shot.startFrame) ? shot.startFrame : Math.round(shot.start * fps)}
          durationInFrames={Number.isFinite(shot.durationInFrames) ? shot.durationInFrames : Math.max(1, Math.round(shot.duration * fps))}
          premountFor={Math.round(fps * .5)}
        >
          <Shot shot={shot}/>
        </Sequence>
      ))}
      {captionsEnabled ? <Caption cue={activeCaption}/> : null}
      <div style={{
        position: 'absolute',
        left: 0,
        right: 0,
        bottom: 28,
        textAlign: 'center',
        color: 'rgba(255,255,255,.38)',
        fontFamily: 'Arial, sans-serif',
        fontSize: 23,
        fontStyle: 'italic',
        textShadow: '0 2px 8px rgba(0,0,0,.7)',
      }}>{watermark}</div>
    </AbsoluteFill>
  );
};

const RankingBackdrop = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const time = frame / fps;
  const drift = (frame % 240) / 240;
  return (
    <AbsoluteFill style={{
      background: [
        `radial-gradient(circle at ${18 + Math.sin(time * .22) * 5}% ${4 + Math.cos(time * .18) * 3}%, rgba(68,245,218,.2), transparent 31%)`,
        `radial-gradient(circle at ${92 + Math.sin(time * .16) * 4}% ${72 + Math.cos(time * .2) * 4}%, rgba(182,255,74,.13), transparent 35%)`,
        'linear-gradient(155deg, #051612 0%, #061018 48%, #09091a 100%)',
      ].join(','),
      overflow: 'hidden',
    }}>
      <div style={{
        position: 'absolute',
        inset: '-10%',
        opacity: .11,
        transform: `translateY(${drift * 48}px)`,
        backgroundImage: [
          'linear-gradient(rgba(126,255,231,.18) 1px, transparent 1px)',
          'linear-gradient(90deg, rgba(126,255,231,.18) 1px, transparent 1px)',
        ].join(','),
        backgroundSize: '72px 72px',
        maskImage: 'linear-gradient(to bottom, black, transparent 80%)',
      }}/>
      <div style={{
        position: 'absolute',
        width: 640,
        height: 640,
        right: -260,
        top: 420,
        borderRadius: '50%',
        border: '2px solid rgba(182,255,74,.12)',
        boxShadow: '0 0 120px rgba(182,255,74,.08)',
      }}/>
      <div style={{
        position: 'absolute',
        width: 510,
        height: 510,
        left: -310,
        top: 80,
        borderRadius: '50%',
        border: '1px solid rgba(111,255,229,.13)',
        boxShadow: '0 0 100px rgba(111,255,229,.07)',
        transform: `scale(${1 + Math.sin(time * .35) * .035})`,
      }}/>
      {[0, 1, 2, 3, 4, 5].map((index) => (
        <div key={index} style={{
          position: 'absolute',
          width: 5 + (index % 3) * 3,
          height: 5 + (index % 3) * 3,
          borderRadius: '50%',
          left: `${12 + ((index * 19) % 78)}%`,
          top: `${18 + ((index * 23) % 68)}%`,
          background: index % 2 ? '#B6FF4A' : '#6FFFE5',
          boxShadow: index % 2 ? '0 0 18px #B6FF4A' : '0 0 18px #6FFFE5',
          opacity: .16 + .12 * Math.sin(time * .8 + index),
          transform: `translate3d(${Math.sin(time * .42 + index) * 18}px, ${Math.cos(time * .35 + index) * 24}px, 0)`,
        }}/>
      ))}
    </AbsoluteFill>
  );
};

const KineticHeadline = ({text, accent = '#B6FF4A', progress = 1}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const words = String(text || '').split(/\s+/).filter(Boolean);
  return (
    <div style={{display: 'flex', flexWrap: 'wrap', gap: '0 .22em'}}>
      {words.map((word, index) => {
        const reveal = spring({
          fps,
          frame: Math.max(0, frame - index * 2),
          config: {damping: 19, stiffness: 185, mass: .62},
        }) * progress;
        const highlighted = index >= words.length - 2;
        return (
          <span key={`${word}-${index}`} style={{
            display: 'inline-block',
            color: highlighted ? accent : '#F7FFFC',
            opacity: reveal,
            transform: `translate3d(0, ${(1 - reveal) * 46}px, 0) scale(${.88 + reveal * .12})`,
            filter: `blur(${(1 - reveal) * 8}px)`,
            textShadow: highlighted ? `0 0 42px ${accent}33` : '0 12px 45px rgba(0,0,0,.35)',
          }}>{word}</span>
        );
      })}
    </div>
  );
};

const RankingDialogue = ({dialogue = []}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const second = frame / fps;
  const active = dialogue.find((cue) => (
    second >= Number(cue.start || 0)
    && second < Number(cue.start || 0) + Number(cue.duration || 0)
  ));
  if (!active) return null;
  const words = String(active.text || '').split(/\s+/).filter(Boolean);
  const host = active.speaker === 'HOST';
  const accent = host ? '#6FFFE5' : '#B6FF4A';
  return (
    <div style={{
      position: 'absolute',
      zIndex: 20,
      left: 62,
      right: 62,
      bottom: 248,
      display: 'flex',
      alignItems: 'flex-start',
      gap: 17,
      padding: '22px 25px 24px',
      borderRadius: 27,
      color: '#F7FFFC',
      background: 'linear-gradient(120deg, rgba(3,13,17,.94), rgba(8,10,22,.91))',
      border: `1px solid ${accent}66`,
      boxShadow: `0 20px 65px rgba(0,0,0,.46), 0 0 38px ${accent}18`,
      backdropFilter: 'blur(18px)',
      opacity: 1,
      transform: 'translate3d(0,0,0)',
    }}>
      <span style={{
        flex: '0 0 auto',
        marginTop: 2,
        padding: '8px 11px',
        borderRadius: 11,
        color: '#06110E',
        background: accent,
        fontSize: 15,
        lineHeight: 1,
        fontWeight: 950,
        letterSpacing: '.08em',
        boxShadow: `0 0 24px ${accent}55`,
      }}>{host ? 'HOST' : 'CO-HOST'}</span>
      <div style={{fontSize: 34, lineHeight: 1.17, fontWeight: 850, letterSpacing: '-.025em'}}>
        {words.map((word, index) => (
          <span key={`${word}-${index}`} style={{
            display: 'inline-block',
            marginRight: '.24em',
            color: /^(s|a|b|c|f)$/i.test(word.replace(/[^a-z]/gi, '')) ? accent : '#F7FFFC',
            textShadow: 'none',
            transform: 'none',
          }}>{word}</span>
        ))}
      </div>
    </div>
  );
};

const RankingVideo = ({
  title = 'AI VIDEO TOOL TIER LIST',
  kicker = 'RANKING',
  hook = 'WHAT BELONGS IN S TIER?',
  payoff = 'LOCKED IN.',
  footer = '',
  sourceNote = '',
  dialogue = [],
  items = [],
  watermark = '@ryuundy · HYPIT',
}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const second = frame / fps;
  const intro = spring({fps, frame, config: {damping: 18, stiffness: 155, mass: .72}});
  const boardIn = spring({fps, frame: frame - Math.round(2.25 * fps), config: {damping: 20, stiffness: 125, mass: .78}});
  const finalCue = dialogue.length ? dialogue[dialogue.length - 1] : null;
  const finalStartSecond = finalCue
    ? Number(finalCue.start || 0)
    : durationInFrames / fps - 5.5;
  const finalStart = Math.max(0, Math.round(finalStartSecond * fps));
  const finalReveal = spring({fps, frame: frame - finalStart, config: {damping: 17, stiffness: 145, mass: .72}});
  const tiers = ['S', 'A', 'B', 'C', 'D', 'F'];
  const rowHeight = 152;
  const finalActive = frame >= finalStart;
  const introExit = interpolate(second, [1.85, 2.75], [1, 0], {...clamp, easing: Easing.inOut(Easing.cubic)});
  const titleIn = interpolate(second, [2.05, 2.85], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
  const revealImpacts = items.map((item) => interpolate(
    second,
    [item.revealAt - .08, item.revealAt + .08, item.revealAt + .7],
    [0, 1, 0],
    clamp,
  ));
  const impact = revealImpacts.length ? Math.max(...revealImpacts) : 0;
  const activeItemIndex = items.reduce(
    (latest, item, index) => second >= item.revealAt ? index : latest,
    -1,
  );
  const revealedCount = Math.max(0, activeItemIndex + 1);
  const cameraFloat = Math.sin(second * .72) * 3;
  const progress = items.length ? revealedCount / items.length : 0;

  return (
    <AbsoluteFill style={{fontFamily: 'Arial, Helvetica, sans-serif', color: '#F7FFFC', overflow: 'hidden'}}>
      <RankingBackdrop/>
      <div style={{
        position: 'absolute', inset: '58px 58px auto 58px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        opacity: finalActive ? 1 - finalReveal * .72 : 1,
        transform: `translateY(${cameraFloat * .35}px)`,
      }}>
        <div style={{display: 'flex', alignItems: 'center', gap: 13}}>
          <div style={{width: 17, height: 17, borderRadius: 5, background: '#6FFFE5', boxShadow: '0 0 26px #6FFFE5', transform: `rotate(${second * 22}deg)`}}/>
          <span style={{fontSize: 22, letterSpacing: '.16em', fontWeight: 900, color: '#9EEBDD'}}>HYPIT / DIRECTOR</span>
        </div>
        <span style={{fontSize: 17, letterSpacing: '.11em', color: 'rgba(255,255,255,.55)'}}>REC ● 9:16</span>
      </div>

      <div style={{position: 'absolute', left: 64, right: 64, top: 132, opacity: finalActive ? 1 - finalReveal : 1}}>
        <div style={{
          display: 'inline-flex',
          padding: '10px 18px',
          borderRadius: 999,
          background: 'rgba(111,255,229,.1)',
          border: '1px solid rgba(111,255,229,.34)',
          color: '#8FF7E4',
          fontSize: 20,
          fontWeight: 800,
          letterSpacing: '.1em',
          opacity: intro * (second < 2.2 ? 1 : titleIn),
          transform: `translateY(${(1 - intro) * 20}px)`,
        }}>{kicker}</div>
        <div style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 78,
          maxWidth: 950,
          fontSize: 72,
          lineHeight: .96,
          letterSpacing: '-.058em',
          fontWeight: 950,
          textTransform: 'uppercase',
          opacity: introExit,
          transform: `translateY(${interpolate(introExit, [0, 1], [-30, 0], clamp)}px) scale(${.97 + introExit * .03})`,
        }}><KineticHeadline text={hook} progress={introExit}/></div>
        <h1 style={{
          margin: '26px 0 0',
          maxWidth: 950,
          fontSize: 69,
          lineHeight: .98,
          letterSpacing: '-.055em',
          textTransform: 'uppercase',
          opacity: titleIn,
          transform: `translateY(${(1 - titleIn) * 34}px) scale(${.97 + titleIn * .03})`,
          textShadow: '0 12px 45px rgba(0,0,0,.35)',
        }}>{title}</h1>
        <div style={{
          width: 250,
          height: 5,
          marginTop: 22,
          borderRadius: 99,
          background: 'rgba(255,255,255,.1)',
          overflow: 'hidden',
          opacity: titleIn,
        }}><div style={{height: '100%', width: `${Math.max(8, progress * 100)}%`, borderRadius: 99, background: 'linear-gradient(90deg,#6FFFE5,#B6FF4A)', boxShadow: '0 0 24px rgba(182,255,74,.45)'}}/></div>
      </div>

      <div style={{
        position: 'absolute',
        left: 58,
        right: 58,
        top: 402,
        padding: 18,
        borderRadius: 34,
        border: '1px solid rgba(142,238,218,.18)',
        background: 'linear-gradient(145deg, rgba(3,15,18,.84), rgba(5,8,19,.74))',
        backdropFilter: 'blur(18px)',
        boxShadow: `0 38px 110px rgba(0,0,0,.42), 0 0 ${24 + impact * 42}px rgba(111,255,229,${.04 + impact * .12})`,
        opacity: boardIn,
        transformOrigin: '50% 55%',
        transform: `perspective(1400px) translate3d(0, ${(1 - boardIn) * 54 + cameraFloat}px, 0) scale(${.955 + boardIn * .045 + impact * .018}) rotateX(${(1 - boardIn) * 4 - impact * .7}deg)`,
      }}>
        <div style={{position: 'absolute', left: 18, right: 18, top: -1, height: 2, overflow: 'hidden'}}>
          <div style={{height: '100%', width: '36%', background: 'linear-gradient(90deg,transparent,#B6FF4A,transparent)', transform: `translateX(${((second * 52) % 370) - 110}%)`, opacity: .75}}/>
        </div>
        {tiers.map((tier, rowIndex) => {
          const item = items.find((candidate) => candidate.tier === tier);
          const revealAt = item?.revealAt ?? 999;
          const itemReveal = spring({
            fps,
            frame: frame - Math.round(revealAt * fps),
            config: {damping: 15, stiffness: 150, mass: .72},
          });
          const accent = item?.accent || 'rgba(255,255,255,.22)';
          const isLatest = item && second >= revealAt && second < revealAt + 2.5;
          const settled = Boolean(item && second >= revealAt);
          const rowPulse = item ? interpolate(second, [revealAt, revealAt + .12, revealAt + .65], [0, 1, 0], clamp) : 0;
          return (
            <div key={tier} style={{
              height: rowHeight,
              display: 'grid',
              gridTemplateColumns: '132px 1fr',
              gap: 14,
              padding: '7px 0',
              opacity: item && !settled ? .42 : isLatest ? 1 : item ? .78 : .28,
              transform: `translateX(${item && !settled ? (rowIndex % 2 ? -10 : 10) : 0}px) scale(${1 + rowPulse * .012})`,
            }}>
              <div style={{
                borderRadius: 22,
                display: 'grid',
                placeItems: 'center',
                color: settled ? '#06110E' : 'rgba(255,255,255,.42)',
                background: settled ? accent : 'rgba(255,255,255,.055)',
                border: settled ? `1px solid ${accent}` : '1px solid rgba(255,255,255,.08)',
                fontSize: 61,
                fontWeight: 950,
                boxShadow: item && isLatest ? `0 0 ${48 + rowPulse * 40}px ${accent}66` : 'none',
                transform: `scale(${.94 + itemReveal * .06 + rowPulse * .04}) rotate(${(1 - itemReveal) * -4}deg)`,
              }}>{tier}</div>
              <div style={{
                position: 'relative',
                borderRadius: 22,
                border: item ? `1px solid ${accent}55` : '1px dashed rgba(255,255,255,.08)',
                background: settled ? 'linear-gradient(115deg, rgba(255,255,255,.12), rgba(255,255,255,.035))' : 'rgba(255,255,255,.018)',
                overflow: 'hidden',
                boxShadow: isLatest ? `inset 0 0 45px ${accent}12, 0 12px 34px rgba(0,0,0,.22)` : 'none',
              }}>
                {item ? <div style={{
                  position: 'absolute',
                  inset: 0,
                  padding: '22px 25px',
                  opacity: itemReveal,
                  transformOrigin: rowIndex % 2 ? '0% 50%' : '100% 50%',
                  transform: `translate3d(${(1 - itemReveal) * (rowIndex % 2 ? -440 : 440)}px, ${(1 - itemReveal) * 18}px, 0) rotateY(${(1 - itemReveal) * (rowIndex % 2 ? -18 : 18)}deg) scale(${.92 + itemReveal * .08})`,
                  filter: `blur(${(1 - itemReveal) * 7}px)`,
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'center',
                }}>
                  <span style={{position: 'absolute', right: 23, top: 18, fontSize: 14, fontWeight: 900, letterSpacing: '.12em', color: `${accent}`, opacity: .82}}>0{items.findIndex((candidate) => candidate.tier === tier) + 1}</span>
                  <strong style={{fontSize: 31, lineHeight: 1.05, letterSpacing: '-.025em'}}>{item.label}</strong>
                  <span style={{marginTop: 9, fontSize: 20, lineHeight: 1.18, color: 'rgba(235,255,249,.68)'}}>{item.detail}</span>
                </div> : null}
              </div>
            </div>
          );
        })}
      </div>

      <div style={{position: 'absolute', left: 66, right: 66, bottom: 128, display: 'flex', justifyContent: 'space-between', alignItems: 'end', gap: 28}}>
        <div style={{maxWidth: 780}}>
          <strong style={{display: 'block', fontSize: 28, lineHeight: 1.08, color: '#D9FFF6'}}>{footer}</strong>
          <span style={{display: 'block', marginTop: 10, fontSize: 17, color: 'rgba(255,255,255,.48)'}}>{sourceNote}</span>
        </div>
        <span style={{fontSize: 19, color: 'rgba(255,255,255,.38)', whiteSpace: 'nowrap'}}>{watermark}</span>
      </div>

      <div style={{position: 'absolute', right: 24, top: 620, display: 'flex', flexDirection: 'column', gap: 12, opacity: finalActive ? 0 : .8}}>
        {items.map((item, index) => {
          const active = index === activeItemIndex;
          const done = index <= activeItemIndex;
          return <div key={`${item.tier}-${index}`} style={{width: active ? 7 : 5, height: active ? 46 : 24, borderRadius: 99, background: done ? item.accent : 'rgba(255,255,255,.16)', boxShadow: active ? `0 0 18px ${item.accent}` : 'none', transition: 'none'}}/>;
        })}
      </div>

      {finalActive ? <AbsoluteFill style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 68,
        background: `rgba(4,12,13,${interpolate(finalReveal, [0, 1], [0, .91], clamp)})`,
        backdropFilter: `blur(${finalReveal * 9}px)`,
      }}>
        <div style={{
          position: 'absolute',
          width: 860,
          height: 860,
          borderRadius: '50%',
          border: '2px solid rgba(182,255,74,.34)',
          boxShadow: '0 0 120px rgba(182,255,74,.16)',
          opacity: finalReveal,
          transform: `scale(${.3 + finalReveal * .9}) rotate(${second * 5}deg)`,
        }}/>
        <div style={{
          width: '100%',
          padding: '70px 54px',
          borderRadius: 42,
          textAlign: 'center',
          background: 'linear-gradient(145deg, rgba(182,255,74,.98), rgba(100,245,206,.93))',
          color: '#07110E',
          boxShadow: `0 ${30 - finalReveal * 12}px 120px rgba(182,255,74,.3)`,
          transform: `translateY(${(1 - finalReveal) * 90}px) scale(${.78 + finalReveal * .22}) rotate(${(1 - finalReveal) * -3.5}deg)`,
          opacity: finalReveal,
        }}>
          <span style={{fontSize: 25, fontWeight: 900, letterSpacing: '.14em'}}>FINAL VERDICT</span>
          <div style={{marginTop: 20, fontSize: 78, fontWeight: 950, lineHeight: .96, letterSpacing: '-.055em'}}>
            {String(payoff).split(/\s+/).map((word, index) => {
              const wordIn = spring({fps, frame: Math.max(0, frame - finalStart - 4 - index * 2), config: {damping: 18, stiffness: 180, mass: .62}});
              return <span key={`${word}-${index}`} style={{display: 'inline-block', marginRight: '.2em', opacity: wordIn, transform: `translateY(${(1 - wordIn) * 28}px)`}}>{word}</span>;
            })}
          </div>
        </div>
        <AbsoluteFill style={{
          pointerEvents: 'none',
          background: '#fff',
          opacity: interpolate(frame - finalStart, [0, 2, 9], [.48, .18, 0], clamp),
          mixBlendMode: 'screen',
        }}/>
      </AbsoluteFill> : null}
      <RankingDialogue dialogue={dialogue}/>
    </AbsoluteFill>
  );
};

const InfographicBackdrop = ({accent = '#55C7F3'}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const second = frame / fps;
  return <AbsoluteFill style={{
    background: [
      `radial-gradient(circle at ${18 + Math.sin(second * .25) * 5}% 13%, ${accent}2F 0%, transparent 34%)`,
      `radial-gradient(circle at 82% ${72 + Math.cos(second * .2) * 5}%, #6E4BD42E 0%, transparent 38%)`,
      'linear-gradient(155deg, #0B5670 0%, #164E7A 42%, #27346F 72%, #34285E 100%)',
    ].join(','),
    overflow: 'hidden',
  }}>
    <div style={{position: 'absolute', width: 720, height: 720, borderRadius: '50%', left: -300, top: 520, background: `${accent}14`, transform: `scale(${1 + Math.sin(second * .35) * .035})`}}/>
    <div style={{position: 'absolute', width: 560, height: 560, borderRadius: '50%', right: -260, top: 160, border: '2px solid rgba(255,255,255,.055)'}}/>
    <AbsoluteFill style={{opacity: .035, backgroundImage: 'radial-gradient(rgba(255,255,255,.9) .8px, transparent .8px)', backgroundSize: '22px 22px'}}/>
  </AbsoluteFill>;
};

const WinningReelBackdrop = ({accent = '#F44B9B'}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const second = frame / fps;
  const laneOffset = (frame * 18) % 260;
  const cars = [
    {lane: 0, color: '#FFD447', delay: 0},
    {lane: 1, color: '#55D9FF', delay: 105},
    {lane: 2, color: '#F44B9B', delay: 210},
    {lane: 0, color: '#FFFFFF', delay: 330},
    {lane: 2, color: '#7CFF7A', delay: 440},
  ];
  return <AbsoluteFill style={{overflow: 'hidden', background: 'linear-gradient(180deg,#142C3D 0%,#305F55 38%,#17202E 100%)'}}>
    <div style={{position: 'absolute', inset: '0 0 56%', background: 'radial-gradient(circle at 50% 100%,rgba(255,212,71,.28),transparent 55%)'}}/>
    <div style={{position: 'absolute', left: -100, right: -100, top: 410, bottom: -180, background: 'linear-gradient(90deg,#24343A 0 12%,#151A22 12% 88%,#24343A 88%)', clipPath: 'polygon(34% 0,66% 0,100% 100%,0 100%)', boxShadow: `0 0 90px ${accent}22`}}>
      {[0, 1].map((lane) => <div key={lane} style={{position: 'absolute', left: `${44 + lane * 12}%`, top: -260 + laneOffset, width: 13, height: '150%', background: 'repeating-linear-gradient(180deg,rgba(255,255,255,.9) 0 90px,transparent 90px 210px)', opacity: .55, transform: 'perspective(500px) rotateX(14deg)'}}/>)}
      {cars.map((car, index) => {
        const travel = ((frame * (7.8 + index * .35) + car.delay) % 1480) - 170;
        const scale = .35 + Math.max(0, travel) / 1320 * .9;
        return <div key={index} style={{position: 'absolute', left: `${39 + car.lane * 11.5}%`, top: travel, width: 105, height: 175, borderRadius: 24, background: `linear-gradient(150deg,${car.color},#202636)`, border: '5px solid rgba(0,0,0,.65)', boxShadow: `0 18px 34px rgba(0,0,0,.45),0 0 24px ${car.color}55`, transform: `translateX(-50%) scale(${scale})`, transformOrigin: '50% 0'}}>
          <i style={{position: 'absolute', left: 19, right: 19, top: 24, height: 54, borderRadius: 12, background: '#9CEBFF99'}}/>
          <i style={{position: 'absolute', left: 11, bottom: 18, width: 24, height: 30, borderRadius: 8, background: '#FF315F'}}/>
          <i style={{position: 'absolute', right: 11, bottom: 18, width: 24, height: 30, borderRadius: 8, background: '#FF315F'}}/>
        </div>;
      })}
    </div>
    <AbsoluteFill style={{background: `radial-gradient(circle at ${50 + Math.sin(second * .7) * 8}% 48%,transparent 0 28%,rgba(3,8,18,.42) 76%)`}}/>
    <AbsoluteFill style={{opacity: .055, backgroundImage: 'radial-gradient(#fff 1px,transparent 1px)', backgroundSize: '20px 20px'}}/>
  </AbsoluteFill>;
};

const PhoneGraphic = ({accent, progress}) => <div style={{
  width: 430, height: 690, borderRadius: 66, padding: 18, background: '#1B2035',
  border: '5px solid rgba(0,0,0,.55)', boxShadow: '0 36px 70px rgba(2,8,28,.42)',
  transform: `translateY(${(1 - progress) * 55}px) rotate(${(1 - progress) * -4}deg) scale(${.88 + progress * .12})`,
}}>
  <div style={{height: '100%', borderRadius: 49, background: 'linear-gradient(160deg,#F7F1DF,#E7E6EB)', display: 'grid', placeItems: 'center', position: 'relative'}}>
    <div style={{position: 'absolute', top: 15, left: '36%', right: '36%', height: 20, borderRadius: 99, background: '#141827'}}/>
    <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 25}}>
      <div style={{width: 205, height: 100, border: '10px solid #202437', borderRadius: 20, padding: 9, position: 'relative'}}>
        <div style={{position: 'absolute', right: -23, top: 29, width: 15, height: 38, borderRadius: '0 8px 8px 0', background: '#202437'}}/>
        <div style={{width: `${22 + progress * 32}%`, height: '100%', borderRadius: 7, background: accent, boxShadow: `0 0 28px ${accent}77`}}/>
      </div>
      <strong style={{fontSize: 88, color: accent, WebkitTextStroke: '3px #202437', paintOrder: 'stroke fill', letterSpacing: '-.06em'}}>{Math.round(5 + progress * 15)}%</strong>
    </div>
  </div>
</div>;

const ChipGraphic = ({accent, progress}) => {
  const pins = Array.from({length: 7});
  return <div style={{position: 'relative', width: 690, height: 610, display: 'grid', placeItems: 'center'}}>
    <div style={{position: 'absolute', width: 520, height: 520, borderRadius: '50%', background: `${accent}28`, transform: `scale(${.72 + progress * .28})`}}/>
    <svg width="690" height="610" viewBox="0 0 690 610" style={{position: 'absolute'}}>
      <path d="M80 520 C180 500 150 380 285 350" fill="none" stroke={accent} strokeWidth="8" strokeDasharray="15 13" strokeDashoffset={-(progress * 85)}/>
      <path d="M610 520 C500 500 540 380 405 350" fill="none" stroke="#FFD447" strokeWidth="8" strokeDasharray="15 13" strokeDashoffset={progress * 95}/>
    </svg>
    <div style={{position: 'relative', width: 310, height: 310, borderRadius: 38, color: '#fff', background: 'linear-gradient(145deg,#232847,#171A31)', border: '8px solid #0E1122', boxShadow: `0 25px 70px rgba(0,0,0,.35), 0 0 55px ${accent}25`, display: 'grid', placeItems: 'center', transform: `scale(${.78 + progress * .22}) rotate(${(1 - progress) * 7}deg)`}}>
      {pins.map((_, index) => <React.Fragment key={index}>
        <i style={{position: 'absolute', left: -30, top: 32 + index * 38, width: 31, height: 13, borderRadius: 5, background: '#D7DCE9'}}/>
        <i style={{position: 'absolute', right: -30, top: 32 + index * 38, width: 31, height: 13, borderRadius: 5, background: '#D7DCE9'}}/>
      </React.Fragment>)}
      <strong style={{fontSize: 46, lineHeight: 1.02, textAlign: 'center'}}>SMART<br/>CHIP</strong>
    </div>
    <span style={{position: 'absolute', left: 35, bottom: 10, fontSize: 25, fontWeight: 900}}>masuk</span>
    <span style={{position: 'absolute', right: 25, bottom: 10, fontSize: 25, fontWeight: 900}}>keluar</span>
  </div>;
};

const ChartGraphic = ({accent, progress}) => <div style={{width: 850, height: 650, padding: '46px 48px 60px 76px', borderRadius: 34, background: '#F7F3E8', border: '7px solid #17203A', boxShadow: '0 35px 75px rgba(0,0,0,.3)', transform: `translateY(${(1 - progress) * 50}px) scale(${.9 + progress * .1})`}}>
  <svg width="100%" height="100%" viewBox="0 0 720 520">
    <path d="M32 16 V470 H696" fill="none" stroke="#202841" strokeWidth="6"/>
    <rect x="190" y="165" width="350" height="120" rx="18" fill={`${accent}45`} opacity={progress}/>
    <rect x="535" y="130" width="145" height="340" rx="16" fill="#FF626E35" opacity={progress}/>
    <path d="M48 42 C105 165 150 205 220 220 C320 240 425 220 515 250 C590 274 598 410 672 456" fill="none" stroke="#2586E7" strokeWidth="14" strokeLinecap="round" strokeDasharray="920" strokeDashoffset={(1 - progress) * 920}/>
    <text x="280" y="210" fontSize="34" fontWeight="900" fill="#1A2440">AREA KUNCI</text>
    <text x="10" y="505" fontSize="24" fontWeight="800" fill="#27304A">waktu →</text>
  </svg>
</div>;

const TemperatureGraphic = ({accent, progress}) => <div style={{width: 780, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 75, transform: `scale(${.84 + progress * .16})`}}>
  <div style={{width: 285, height: 430, borderRadius: 44, background: '#AAB2C5', border: '7px solid #242A43', display: 'grid', placeItems: 'center', position: 'relative'}}>
    <span style={{fontSize: 95, opacity: .75}}>⚡</span>
    <small style={{position: 'absolute', bottom: 25, fontSize: 27, fontWeight: 900}}>DAYA</small>
  </div>
  <div style={{position: 'relative', width: 150, height: 480}}>
    <div style={{position: 'absolute', left: 52, top: 10, width: 55, height: 370, borderRadius: 40, background: '#fff', border: '6px solid #22283E', overflow: 'hidden'}}>
      <div style={{position: 'absolute', left: 10, right: 10, bottom: 0, height: `${24 + progress * 48}%`, borderRadius: 30, background: accent}}/>
    </div>
    <div style={{position: 'absolute', left: 24, bottom: 0, width: 112, height: 112, borderRadius: '50%', border: '6px solid #22283E', background: accent, boxShadow: `0 0 36px ${accent}66`}}/>
    <span style={{position: 'absolute', left: 130, top: 80, fontSize: 52}}>❄</span>
    <span style={{position: 'absolute', left: -10, top: 190, fontSize: 44}}>❄</span>
  </div>
</div>;

const ProcessGraphic = ({accent, progress}) => <div style={{width: 850, display: 'flex', alignItems: 'center', justifyContent: 'space-between'}}>
  {['INPUT', 'PROSES', 'HASIL'].map((label, index) => {
    const local = Math.max(0, Math.min(1, progress * 1.5 - index * .22));
    return <React.Fragment key={label}>
      <div style={{width: 210, height: 210, borderRadius: 38, background: index === 1 ? '#1E2746' : '#F5F1E5', border: `7px solid ${index === 1 ? accent : '#202841'}`, color: index === 1 ? '#fff' : '#202841', boxShadow: index === 1 ? `0 0 48px ${accent}44` : '0 24px 45px rgba(0,0,0,.22)', display: 'grid', placeItems: 'center', fontSize: 31, fontWeight: 950, transform: `translateY(${(1 - local) * 45}px) scale(${.85 + local * .15})`, opacity: local}}>{label}</div>
      {index < 2 ? <div style={{fontSize: 62, color: accent, transform: `scaleX(${progress})`}}>→</div> : null}
    </React.Fragment>;
  })}
</div>;

const QuizGraphic = ({accent, progress, detail, options = []}) => <div style={{width: 900, padding: '52px 44px 40px', borderRadius: 34, color: '#242941', background: '#FAF8F0', border: '6px solid #1C2239', boxShadow: '0 34px 75px rgba(0,0,0,.32)', transform: `translateY(${(1 - progress) * 55}px) scale(${.88 + progress * .12})`}}>
  <div style={{fontSize: 37, lineHeight: 1.14, fontWeight: 900, textAlign: 'center', color: '#E84B5B'}}>{detail}</div>
  <div style={{display: 'grid', gridTemplateColumns: `repeat(${Math.max(1, Math.min(3, options.length))}, 1fr)`, gap: 20, marginTop: 42}}>
    {options.map((option, index) => <div key={`${option}-${index}`} style={{padding: '24px 16px', borderRadius: 17, border: '4px solid #252B43', background: index === 1 ? `${accent}33` : '#fff', textAlign: 'center', fontSize: 29, fontWeight: 950}}>{option}</div>)}
  </div>
</div>;

const ConceptGraphic = ({accent, progress, detail}) => <div style={{width: 760, height: 610, borderRadius: '50%', background: `${accent}26`, display: 'grid', placeItems: 'center', transform: `scale(${.72 + progress * .28})`}}>
  <div style={{width: 540, padding: '68px 46px', borderRadius: 44, background: '#F8F5EA', border: '7px solid #202741', color: '#202741', textAlign: 'center', boxShadow: '0 32px 70px rgba(0,0,0,.3)'}}>
    <div style={{fontSize: 85, marginBottom: 25}}>✦</div>
    <strong style={{fontSize: 40, lineHeight: 1.1}}>{detail}</strong>
  </div>
</div>;

const InfographicGraphic = ({beat, progress}) => {
  if (!beat) return null;
  const props = {accent: beat.accent || '#55C7F3', progress, detail: beat.detail || '', options: beat.quizOptions || []};
  if (beat.visual === 'phone') return <PhoneGraphic {...props}/>;
  if (beat.visual === 'chip') return <ChipGraphic {...props}/>;
  if (beat.visual === 'chart') return <ChartGraphic {...props}/>;
  if (beat.visual === 'temperature') return <TemperatureGraphic {...props}/>;
  if (beat.visual === 'process') return <ProcessGraphic {...props}/>;
  if (beat.visual === 'quiz') return <QuizGraphic {...props}/>;
  return <ConceptGraphic {...props}/>;
};

const InfographicVideo = ({
  title = 'INFOGRAPHIC EXPLAINER', hook = 'SATU HAL YANG PERLU KAMU TAHU', payoff = 'SUDAH MASUK AKAL?',
  footer = '', sourceNote = '', beats = [], watermark = '@ryuundy · HYPIT', styleVersion = '',
}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const second = frame / fps;
  const activeIndex = beats.reduce((latest, beat, index) => second >= Number(beat.revealAt || 0) ? index : latest, -1);
  const beat = activeIndex >= 0 ? beats[activeIndex] : null;
  const accent = beat?.accent || '#FFD447';
  const revealFrame = beat ? frame - Math.round(Number(beat.revealAt || 0) * fps) : frame;
  const reveal = spring({fps, frame: Math.max(0, revealFrame), config: {damping: 17, stiffness: 145, mass: .72}});
  const hookIn = spring({fps, frame, config: {damping: 18, stiffness: 165, mass: .68}});
  const finalStart = Math.max(0, durationInFrames - Math.round(5.5 * fps));
  const final = spring({fps, frame: frame - finalStart, config: {damping: 17, stiffness: 140, mass: .76}});
  const finalActive = frame >= finalStart;
  const progress = beats.length ? Math.max(0, activeIndex + 1) / beats.length : 0;
  const winningStyle = styleVersion === 'winning-reel-39-v1';
  return <AbsoluteFill style={{fontFamily: 'Arial, Helvetica, sans-serif', color: '#fff', overflow: 'hidden'}}>
    {winningStyle ? <WinningReelBackdrop accent={accent}/> : <InfographicBackdrop accent={accent}/>}
    <div style={{position: 'absolute', left: 42, top: 45, zIndex: 8, fontSize: 17, fontWeight: 900, letterSpacing: '.06em', textShadow: '0 2px 8px rgba(0,0,0,.45)'}}>{watermark}</div>
    <div style={{position: 'absolute', right: 42, top: 45, zIndex: 8, fontSize: 15, fontWeight: 800, opacity: .72}}>{winningStyle ? 'PATTERN TEST · 39S' : 'INFO · 9:16'}</div>
    <div style={{position: 'absolute', left: 60, right: 60, top: winningStyle ? 92 : 108, zIndex: 5, textAlign: 'center', opacity: finalActive ? 1 - final : 1}}>
      <div style={{fontSize: 31, lineHeight: 1, fontWeight: 950, letterSpacing: '.02em', color: '#fff', textShadow: '0 4px 12px rgba(0,0,0,.4)', transform: `translateY(${(1 - (beat ? reveal : hookIn)) * -22}px)`}}>{beat?.kicker || 'WAJIB TAHU'}</div>
      <div style={{display: 'inline-block', maxWidth: '100%', boxSizing: 'border-box', overflowWrap: 'anywhere', marginTop: 12, padding: winningStyle ? '16px 22px 20px' : 0, borderRadius: winningStyle ? 18 : 0, background: winningStyle ? 'rgba(5,8,15,.88)' : 'transparent', fontSize: beat ? 72 : winningStyle ? 54 : 66, lineHeight: .98, fontWeight: 950, letterSpacing: '-.045em', color: beat ? accent : '#FFD447', WebkitTextStroke: '4px rgba(18,25,55,.9)', paintOrder: 'stroke fill', textTransform: 'uppercase', boxShadow: winningStyle ? `0 12px 0 ${accent}` : 'none', transform: `scale(${.93 + (beat ? reveal : hookIn) * .07})`}}>{beat?.title || hook}</div>
      <div style={{width: 310, height: 8, margin: '25px auto 0', borderRadius: 99, background: 'rgba(255,255,255,.14)', overflow: 'hidden'}}><div style={{height: '100%', width: `${Math.max(7, progress * 100)}%`, borderRadius: 99, background: accent, boxShadow: `0 0 20px ${accent}`}}/></div>
    </div>
    <div style={{position: 'absolute', left: 45, right: 45, top: winningStyle ? 460 : 440, height: winningStyle ? 840 : 920, display: 'grid', placeItems: 'center', opacity: finalActive ? 1 - final : beat ? (winningStyle ? .93 : 1) : .35, transform: winningStyle ? 'scale(.82)' : 'none'}}>
      {beat ? <InfographicGraphic key={beat.id || activeIndex} beat={beat} progress={reveal}/> : <ConceptGraphic accent="#FFD447" progress={hookIn} detail={title}/>}
    </div>
    <div style={{position: 'absolute', left: 66, right: 66, bottom: 155, minHeight: 140, zIndex: 7, display: 'grid', placeItems: 'center', textAlign: 'center', opacity: finalActive ? 1 - final : 1}}>
      <div style={{maxWidth: '100%', boxSizing: 'border-box', overflowWrap: 'anywhere', padding: winningStyle ? '22px 30px' : '20px 25px', borderRadius: winningStyle ? 14 : 24, background: winningStyle ? '#EF3F91' : 'rgba(13,23,56,.52)', backdropFilter: 'blur(12px)', border: winningStyle ? '5px solid #fff' : '1px solid rgba(255,255,255,.1)', boxShadow: winningStyle ? '0 12px 0 rgba(7,10,18,.8)' : 'none', fontSize: winningStyle ? 36 : 32, lineHeight: 1.16, fontWeight: 900, textShadow: '0 3px 9px rgba(0,0,0,.6)'}}>{beat?.detail || hook}</div>
      <small style={{marginTop: 14, fontSize: 17, opacity: .7}}>{sourceNote}</small>
    </div>
    {finalActive ? <AbsoluteFill style={{zIndex: 20, display: 'grid', placeItems: 'center', padding: 70, background: `rgba(22,30,72,${.35 + final * .58})`, backdropFilter: `blur(${final * 10}px)`}}>
      <div style={{width: '100%', padding: '75px 45px 58px', borderRadius: 46, background: 'linear-gradient(150deg,#FFD447,#FFB62E)', color: '#1D2542', border: '7px solid #1B213B', boxShadow: '0 38px 95px rgba(0,0,0,.36)', textAlign: 'center', opacity: final, transform: `translateY(${(1 - final) * 90}px) scale(${.8 + final * .2}) rotate(${(1 - final) * -3}deg)`}}>
        <div style={{fontSize: 25, fontWeight: 950, letterSpacing: '.08em'}}>SEBELUM SELESAI</div>
        <div style={{marginTop: 18, fontSize: 78, lineHeight: .96, fontWeight: 950, letterSpacing: '-.055em'}}>{payoff}</div>
        <div style={{display: 'inline-block', marginTop: 38, padding: '18px 30px', borderRadius: 18, color: '#fff', background: '#1D2542', fontSize: 26, fontWeight: 950}}>{footer}</div>
      </div>
    </AbsoluteFill> : null}
  </AbsoluteFill>;
};

const ClipForgeComposition = (props) => props.template === 'ranking'
  ? <RankingVideo {...props}/>
  : props.template === 'infographic'
    ? <InfographicVideo {...props}/>
    : <Story {...props}/>;

const defaultProps = {
  width: 1080,
  height: 1920,
  fps: 30,
  durationSeconds: 10,
  shots: [],
  scenes: [],
  captionCues: [],
  watermark: '@ryuundy',
  captionsEnabled: true,
};

const Root = () => (
  <Composition
    id="ClipForgeStory"
    component={ClipForgeComposition}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={300}
    defaultProps={defaultProps}
    calculateMetadata={({props}) => ({
      width: props.width,
      height: props.height,
      fps: props.fps,
      durationInFrames: Math.max(1, Math.round(props.durationSeconds * props.fps)),
    })}
  />
);

registerRoot(Root);
