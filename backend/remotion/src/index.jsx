import React from 'react';
import {PresenterSceneGraphic} from './presenter';
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

const StableDialogueCaption = ({dialogue = [], palette = 'ranking', bottom = 248}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const second = frame / fps;
  const activeIndex = dialogue.reduce(
    (latest, cue, index) => second >= Number(cue.start || 0) ? index : latest,
    -1,
  );
  const active = activeIndex >= 0 ? dialogue[activeIndex] : null;
  if (!active) return null;
  const infographic = palette === 'infographic';
  if (infographic) {
    const words = String(active?.text || '').split(/\s+/).filter(Boolean);
    const emphasisIndex = words.reduce((picked, word, index) => {
      const clean = word.replace(/[^A-Za-zÀ-ÖØ-öø-ÿ0-9-]/g, '');
      return clean.length >= 6 ? index : picked;
    }, Math.max(0, words.length - 1));
    return <div style={{
      position: 'absolute', zIndex: 60, left: 72, right: 72, bottom,
      minHeight: 78, display: 'flex', alignItems: 'center', justifyContent: 'center',
      textAlign: 'center', color: '#FFFFFF', fontFamily: 'Arial Black, Arial, Helvetica, sans-serif',
      fontSize: words.length > 20 ? 28 : words.length > 14 ? 31 : 34,
      lineHeight: 1.24, fontWeight: 900, letterSpacing: '-.02em',
      textShadow: '0 4px 0 #17204C, 0 8px 20px rgba(0,0,0,.55)',
      opacity: 1,
    }}>
      <span>{words.map((word, index) => <React.Fragment key={`${word}-${index}`}>
        {index ? ' ' : ''}<span style={{color: index === emphasisIndex ? '#FFD447' : '#FFFFFF'}}>{word}</span>
      </React.Fragment>)}</span>
    </div>;
  }
  const renderCue = (cue) => {
    const host = cue?.speaker === 'HOST';
    const accent = infographic ? '#55D9FF' : '#6FFFE5';
    const text = String(cue?.text || '');
    const fontSize = text.length > 150 ? 29 : text.length > 105 ? 32 : 35;
    return <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', gap: 17}}>
      <span style={{
        flex: '0 0 auto', marginTop: 2, padding: '8px 11px', borderRadius: 11,
        color: '#06110E', background: accent, fontSize: 15, lineHeight: 1,
        fontWeight: 950, letterSpacing: '.08em', boxShadow: `0 0 24px ${accent}55`,
      }}>{host ? 'HOST' : 'CO-HOST'}</span>
      <div style={{fontSize, lineHeight: 1.18, fontWeight: 850, letterSpacing: '-.025em'}}>{text}</div>
    </div>;
  };
  return (
    <div style={{
      position: 'absolute',
      zIndex: 60,
      left: 62,
      right: 62,
      bottom,
      minHeight: 132,
      padding: '20px 25px 22px',
      borderRadius: 27,
      color: '#F7FFFC',
      background: infographic ? '#11172D' : '#071014',
      border: `1px solid ${infographic ? '#55D9FF55' : '#6FFFE555'}`,
      boxShadow: `0 20px 65px rgba(0,0,0,.46), 0 0 38px ${infographic ? '#55D9FF16' : '#6FFFE516'}`,
      opacity: 1,
    }}>
      <div style={{position: 'relative', width: '100%', minHeight: 88}}>
        {renderCue(active)}
      </div>
    </div>
  );
};

const MidVideoEngagement = ({config = {}}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (config.enabled !== true) return null;
  const start = Number(config.start || 0);
  const duration = Number(config.duration || 2.8);
  const local = frame - Math.round(start * fps);
  const total = Math.max(1, Math.round(duration * fps));
  if (local < 0 || local > total) return null;
  const enter = spring({fps, frame: local, config: {damping: 15, stiffness: 190, mass: .68}});
  const exit = interpolate(local, [Math.max(0, total - Math.round(.32 * fps)), total], [1, 0], clamp);
  const visible = enter * exit;
  const pulse = 1 + Math.sin(local * .18) * .025;
  return <AbsoluteFill style={{zIndex: 32, display: 'grid', placeItems: 'center', padding: 70, pointerEvents: 'none', background: `rgba(4,8,20,${visible * .72})`}}>
    <div style={{width: '100%', padding: '54px 42px 48px', borderRadius: 40, textAlign: 'center', color: '#17213B', background: 'linear-gradient(145deg,#FFD447,#FFB936)', border: '7px solid #17213B', boxShadow: '0 34px 100px rgba(0,0,0,.42)', opacity: visible, transform: `translateY(${(1-visible)*90}px) scale(${(.78 + visible*.22)*pulse})`}}>
      <div style={{fontSize: 25, fontWeight: 950, letterSpacing: '.12em'}}>{config.eyebrow || 'SEBELUM LANJUT'}</div>
      <div style={{display: 'flex', justifyContent: 'center', gap: 24, margin: '28px 0 20px'}}>
        <span style={{width: 112, height: 112, borderRadius: 32, display: 'grid', placeItems: 'center', color: '#fff', background: '#FF5265', border: '6px solid #17213B', fontSize: 60}}>♥</span>
        <span style={{width: 112, height: 112, borderRadius: 32, display: 'grid', placeItems: 'center', color: '#17213B', background: '#F8F5EA', border: '6px solid #17213B', fontSize: 47}}>●●</span>
      </div>
      <div style={{fontSize: 67, lineHeight: .96, fontWeight: 950, letterSpacing: '-.05em'}}>{config.title || 'LIKE + KOMEN DULU'}</div>
      <div style={{marginTop: 18, fontSize: 28, lineHeight: 1.15, fontWeight: 800}}>{config.body || 'Tulis pendapatmu, lalu kita lanjut.'}</div>
    </div>
  </AbsoluteFill>;
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
  midCta = {},
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
      <MidVideoEngagement config={midCta}/>
      <StableDialogueCaption dialogue={dialogue}/>
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

const EditorialExplainerBackdrop = ({accent = '#55C7F3'}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const second = frame / fps;
  const specks = [
    [9, 18, 3, .4], [18, 43, 2, .8], [83, 17, 2, 1.1], [91, 39, 3, 1.5],
    [12, 72, 2, 2.0], [76, 64, 2, 2.4], [88, 82, 3, 2.9], [32, 86, 2, 3.4],
  ];
  return <AbsoluteFill style={{overflow: 'hidden', background: 'linear-gradient(180deg,#202D66 0%,#1B285D 52%,#172250 100%)'}}>
    <div style={{position: 'absolute', width: 720, height: 720, left: -400, top: 340, borderRadius: '50%', background: `${accent}0D`, filter: 'blur(12px)'}}/>
    <div style={{position: 'absolute', width: 620, height: 620, right: -420, top: 780, borderRadius: '50%', background: '#6C56D70C', filter: 'blur(14px)'}}/>
    {specks.map(([left, top, size, delay], index) => <i key={index} style={{
      position: 'absolute', left: `${left}%`, top: `${top}%`, width: size, height: size,
      borderRadius: '50%', background: index % 3 ? '#FFFFFF' : accent,
      opacity: .24 + (Math.sin(second * .85 + delay) + 1) * .13,
      transform: `translateY(${Math.sin(second * .42 + delay) * 10}px)`,
    }}/>) }
    <AbsoluteFill style={{opacity: .028, backgroundImage: 'linear-gradient(rgba(255,255,255,.4) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.4) 1px,transparent 1px)', backgroundSize: '72px 72px'}}/>
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

const QuizOptionIcon = ({option, accent}) => {
  if (/v[ -]?belt/i.test(option)) return <svg width="124" height="96" viewBox="0 0 124 96"><ellipse cx="62" cy="48" rx="50" ry="31" fill="none" stroke="#202741" strokeWidth="18"/><ellipse cx="62" cy="48" rx="50" ry="31" fill="none" stroke={accent} strokeWidth="7" strokeDasharray="12 8"/></svg>;
  if (/busi|spark[ -]?plug/i.test(option)) return <svg width="88" height="118" viewBox="0 0 88 118"><rect x="34" y="5" width="20" height="22" rx="5" fill="#9EA9BA" stroke="#202741" strokeWidth="5"/><rect x="22" y="23" width="44" height="42" rx="13" fill="#F8F5EA" stroke="#202741" strokeWidth="6"/><path d="M14 63 H74 L64 82 H24 Z" fill={accent} stroke="#202741" strokeWidth="6"/><rect x="29" y="80" width="30" height="30" fill="#AAB4C2" stroke="#202741" strokeWidth="6"/><path d="M44 108 V116 M65 105 V114 H51" fill="none" stroke="#202741" strokeWidth="6" strokeLinecap="round"/></svg>;
  if (/ping|lag|packet/i.test(option)) return <svg width="126" height="105" viewBox="0 0 126 105"><path d="M15 88 A49 49 0 0 1 111 88" fill={accent} stroke="#202741" strokeWidth="10"/><path d="M63 82 L94 38" stroke="#202741" strokeWidth="10" strokeLinecap="round"/><circle cx="63" cy="82" r="13" fill="#F8F5EA" stroke="#202741" strokeWidth="7"/></svg>;
  if (/layar|terang|brightness/i.test(option)) return <svg width="112" height="112" viewBox="0 0 112 112"><circle cx="56" cy="56" r="28" fill="#FFD447" stroke="#202741" strokeWidth="8"/>{[0,45,90,135].map((angle) => <line key={angle} x1="56" y1="5" x2="56" y2="20" stroke="#202741" strokeWidth="8" strokeLinecap="round" transform={`rotate(${angle} 56 56)`}/>)}</svg>;
  if (/awet|stabil|aman/i.test(option)) return <svg width="112" height="112" viewBox="0 0 112 112"><path d="M56 7 L98 22 V55 C98 80 82 98 56 106 C30 98 14 80 14 55 V22Z" fill="#66E39B" stroke="#202741" strokeWidth="8"/><path d="M34 56 L49 71 L79 40" fill="none" stroke="#202741" strokeWidth="10" strokeLinecap="round" strokeLinejoin="round"/></svg>;
  if (/aus|komponen|mesin|oli|pelumas/i.test(option)) return <svg width="118" height="112" viewBox="0 0 118 112"><path d="M59 5 C78 31 90 47 90 68 A31 31 0 1 1 28 68 C28 47 40 31 59 5Z" fill="#FFD447" stroke="#202741" strokeWidth="8"/><path d="M47 73 L57 83 L76 57" fill="none" stroke={accent} strokeWidth="9" strokeLinecap="round" strokeLinejoin="round"/></svg>;
  return <div style={{height: 96, display: 'grid', placeItems: 'center', fontSize: 58, color: accent}}>?</div>;
};

const QuizGraphic = ({accent, progress, detail, options = []}) => <div style={{width: 900, padding: '45px 44px 36px', borderRadius: 34, color: '#242941', background: '#FAF8F0', border: '6px solid #1C2239', boxShadow: '0 34px 75px rgba(0,0,0,.32)', transform: `translateY(${(1 - progress) * 55}px) scale(${.88 + progress * .12})`}}>
  <div style={{fontSize: 37, lineHeight: 1.14, fontWeight: 900, textAlign: 'center', color: '#E84B5B'}}>{detail}</div>
  <div style={{display: 'grid', gridTemplateColumns: `repeat(${Math.max(1, Math.min(3, options.length))}, 1fr)`, gap: 20, marginTop: 32}}>
    {options.map((option, index) => <div key={`${option}-${index}`} style={{minHeight: 190, padding: '18px 16px', borderRadius: 20, border: '4px solid #252B43', background: index === 1 ? `${accent}24` : '#fff', textAlign: 'center', fontSize: 29, fontWeight: 950, display: 'grid', placeItems: 'center'}}><QuizOptionIcon option={option} accent={accent}/><span>{option}</span></div>)}
  </div>
</div>;

const SubjectPlate = ({subject, accent, dark = false}) => <div style={{
  maxWidth: 520, padding: '17px 26px 19px', borderRadius: 18, textAlign: 'center',
  color: dark ? '#202741' : '#fff', background: dark ? '#F8F5EA' : '#202741',
  border: `5px solid ${dark ? '#202741' : accent}`, boxShadow: `0 14px 0 ${accent}55`,
  fontSize: 32, lineHeight: 1.05, fontWeight: 950, textTransform: 'uppercase',
}}>{subject || 'IDE UTAMA'}</div>;

const stagedProgress = (second, start, duration = .34) => interpolate(second, [start, start + duration], [0, 1], clamp);

const CalloutPill = ({children, color = '#FFD447', progress = 1, style = {}}) => <div style={{
  padding: '12px 20px 13px', borderRadius: 999, color: '#202741', background: color,
  border: '5px solid #202741', boxShadow: '0 9px 0 rgba(15,20,48,.28)',
  fontSize: 24, lineHeight: 1, fontWeight: 950, textTransform: 'uppercase',
  opacity: progress, transform: `translateY(${(1-progress)*24}px) scale(${.82+progress*.18})`,
  ...style,
}}>{children}</div>;

const EngineOilGraphic = ({accent, progress, subject, detail, localSeconds = 0}) => {
  const frame = useCurrentFrame();
  const pistonY = 44 + Math.sin(frame * .17) * 37;
  const crank = frame * 5.4;
  const oilIn = stagedProgress(localSeconds, .45);
  const frictionIn = stagedProgress(localSeconds, 1.35);
  const heatIn = stagedProgress(localSeconds, 2.15);
  const warning = /jarang|turun|buruk|gesekan|aus|keausan|risiko/i.test(`${subject} ${detail}`);
  return <div style={{position: 'relative', width: 900, height: 720, transform: `translateY(${(1-progress)*54}px) scale(${.82+progress*.18})`}}>
    <svg width="900" height="720" viewBox="0 0 900 720" style={{filter: 'drop-shadow(0 26px 30px rgba(0,0,0,.28))'}}>
      <path d="M225 118 H680 Q735 118 735 175 V548 Q735 602 680 602 H225 Q170 602 170 548 V175 Q170 118 225 118Z" fill="#F7F4E9" stroke="#202741" strokeWidth="14"/>
      <path d="M272 176 H622 V470 Q622 526 565 526 H329 Q272 526 272 470Z" fill="#D9E2EA" stroke="#202741" strokeWidth="12"/>
      <rect x="338" y="186" width="220" height="220" rx="28" fill="#263554" stroke="#202741" strokeWidth="12"/>
      <g transform={`translate(448 ${pistonY})`}>
        <rect x="-82" y="178" width="164" height="80" rx="18" fill={warning ? '#FFCE49' : accent} stroke="#202741" strokeWidth="11"/>
        <rect x="-70" y="195" width="140" height="13" rx="7" fill="#F7F4E9" opacity=".72"/>
        <path d="M0 258 L0 346" stroke="#202741" strokeWidth="22" strokeLinecap="round"/>
      </g>
      <g transform={`translate(448 492) rotate(${crank})`}>
        <circle r="88" fill={accent} stroke="#202741" strokeWidth="13"/>
        <circle r="25" fill="#F7F4E9" stroke="#202741" strokeWidth="10"/>
        <line x1="0" y1="0" x2="62" y2="0" stroke="#202741" strokeWidth="18" strokeLinecap="round"/>
        <circle cx="62" cy="0" r="18" fill="#FFD447" stroke="#202741" strokeWidth="8"/>
      </g>
      <path d="M228 530 C210 425 218 255 310 234 M587 234 C683 255 695 420 666 532" fill="none" stroke="#D89A18" strokeWidth="34" strokeLinecap="round" opacity=".22"/>
      <path d="M228 530 C210 425 218 255 310 234 M587 234 C683 255 695 420 666 532" fill="none" stroke="#FFD447" strokeWidth="12" strokeLinecap="round" strokeDasharray="25 20" strokeDashoffset={-frame*5} opacity={oilIn}/>
      {[0,1,2].map((drop) => <path key={drop} d="M0 -24 C18 2 28 19 28 35 A28 28 0 1 1 -28 35 C-28 19 -18 2 0 -24Z" transform={`translate(${236 + drop*210} ${232 + ((frame*5 + drop*110)%270)}) scale(.55)`} fill="#FFD447" stroke="#202741" strokeWidth="8" opacity={oilIn}/>) }
      {warning ? <g opacity={heatIn}>
        <path d="M705 244 C761 207 754 159 724 127 C785 144 811 213 778 272Z" fill="#FF5D64" stroke="#202741" strokeWidth="10"/>
        <path d="M727 239 C754 218 753 193 741 173 C770 188 775 220 758 248Z" fill="#FFD447"/>
      </g> : null}
      <g transform="translate(76 444) rotate(-7)" opacity={oilIn}>
        <path d="M8 70 H112 L127 111 V220 Q127 247 98 247 H23 Q-7 247 -7 219 V111Z" fill="#FFD447" stroke="#202741" strokeWidth="11"/>
        <path d="M19 68 V28 H98 V69" fill="#55D9FF" stroke="#202741" strokeWidth="11"/>
        <text x="60" y="170" textAnchor="middle" fontSize="39" fontWeight="950" fill="#202741">OLI</text>
      </g>
      <g opacity={frictionIn} transform="translate(650 430)">
        {[0,1,2].map((spark) => <path key={spark} d={`M${spark*34} 0 l12 24 l22 -10 l-8 28`} fill="none" stroke="#FF5D64" strokeWidth="9" strokeLinecap="round"/>) }
      </g>
    </svg>
    <CalloutPill color="#FFD447" progress={oilIn} style={{position: 'absolute', left: 34, top: 140}}>oli mengalir</CalloutPill>
    <CalloutPill color="#FF777F" progress={frictionIn} style={{position: 'absolute', right: 8, top: 355}}>{warning ? 'gesekan naik' : 'gesekan turun'}</CalloutPill>
    <CalloutPill color={accent} progress={heatIn} style={{position: 'absolute', left: 305, bottom: 3}}>{warning ? 'komponen cepat aus' : 'mesin terlindungi'}</CalloutPill>
  </div>;
};

const GamingNetworkGraphic = ({accent, progress, subject, detail, localSeconds = 0}) => {
  const frame = useCurrentFrame();
  const routerIn = stagedProgress(localSeconds, .35);
  const serverIn = stagedProgress(localSeconds, 1.05);
  const metricIn = stagedProgress(localSeconds, 1.75);
  const problem = /lemah|loss|padat|tinggi|lag|putus|terputus/i.test(`${subject} ${detail}`);
  const wired = /kabel lan|ethernet/i.test(`${subject} ${detail}`);
  const packetTravel = (frame * 7.5) % 590;
  return <div style={{position: 'relative', width: 900, height: 700, transform: `scale(${.82+progress*.18})`}}>
    <svg width="900" height="700" viewBox="0 0 900 700" style={{filter: 'drop-shadow(0 24px 28px rgba(0,0,0,.25))'}}>
      <path d="M178 345 H744" fill="none" stroke="rgba(255,255,255,.32)" strokeWidth="12" strokeDasharray="22 17"/>
      <path d="M178 345 H744" fill="none" stroke={wired ? '#66E39B' : accent} strokeWidth={wired ? 12 : 7} strokeDasharray={wired ? undefined : '22 17'} strokeDashoffset={wired ? 0 : -frame*4} opacity={serverIn}/>
      {[0,1,2].map((packet) => {
        const x = 178 + ((packetTravel + packet*190) % 566);
        const lost = problem && packet === 1 && x > 420 && x < 545;
        return <g key={packet} opacity={serverIn} transform={`translate(${x} 345)`}>
          <rect x="-18" y="-18" width="36" height="36" rx="9" fill={lost ? '#FF626E' : '#FFD447'} stroke="#202741" strokeWidth="7"/>
          {lost ? <path d="M-12 -12 L12 12 M12 -12 L-12 12" stroke="#fff" strokeWidth="6" strokeLinecap="round"/> : null}
        </g>;
      })}
      <g transform="translate(118 345)">
        <rect x="-83" y="-150" width="166" height="300" rx="34" fill="#F7F4E9" stroke="#202741" strokeWidth="12"/>
        <rect x="-57" y="-112" width="114" height="155" rx="18" fill="#97E58B" stroke="#202741" strokeWidth="8"/>
        <path d="M-42 -26 L-5 -56 L28 -32 L55 -66" fill="none" stroke="#fff" strokeWidth="12" strokeLinecap="round" strokeLinejoin="round"/>
        <circle cy="99" r="14" fill={accent}/>
      </g>
      <g transform={`translate(450 345) scale(${.72+routerIn*.28})`} opacity={routerIn}>
        <rect x="-112" y="-66" width="224" height="132" rx="34" fill="#55D9FF" stroke="#202741" strokeWidth="12"/>
        <line x1="-68" y1="-59" x2="-94" y2="-145" stroke="#202741" strokeWidth="13" strokeLinecap="round"/>
        <line x1="68" y1="-59" x2="94" y2="-145" stroke="#202741" strokeWidth="13" strokeLinecap="round"/>
        {[0,1,2].map((ring) => <path key={ring} d={`M${-58-ring*28} ${-92-ring*18} Q0 ${-145-ring*24} ${58+ring*28} ${-92-ring*18}`} fill="none" stroke={problem && ring===2 ? '#FF626E' : '#FFD447'} strokeWidth="11" strokeLinecap="round" opacity={.9-ring*.18}/>) }
        {[0,1,2].map((light) => <circle key={light} cx={-48+light*48} cy="16" r="10" fill={light===2&&problem ? '#FF626E' : '#202741'}/>) }
      </g>
      {wired ? <g transform="translate(274 345)" opacity={routerIn}>
        <rect x="-34" y="-25" width="68" height="50" rx="9" fill="#66E39B" stroke="#202741" strokeWidth="8"/>
        {[0,1,2,3].map((pin) => <line key={pin} x1={-17+pin*11} y1="-19" x2={-17+pin*11} y2="-7" stroke="#202741" strokeWidth="4"/>)}
      </g> : null}
      <g transform={`translate(790 345) scale(${.72+serverIn*.28})`} opacity={serverIn}>
        <rect x="-76" y="-178" width="152" height="356" rx="24" fill="#F7F4E9" stroke="#202741" strokeWidth="12"/>
        {[-112,-20,72].map((y,index) => <g key={y}><rect x="-49" y={y} width="98" height="61" rx="12" fill={index===1 ? accent : '#D9E2EA'} stroke="#202741" strokeWidth="7"/><circle cx="25" cy={y+30} r="8" fill={problem&&index===1 ? '#FF626E' : '#57D98A'}/></g>) }
      </g>
      <g transform="translate(40 535)">
        <path d="M0 32 Q78 -36 156 32" fill="none" stroke="#F7F4E9" strokeWidth="28" strokeLinecap="round"/>
        <rect x="50" y="8" width="56" height="22" rx="8" fill="#202741"/>
        <circle cx="38" cy="36" r="12" fill="#202741"/><circle cx="119" cy="36" r="12" fill="#202741"/>
        <circle cx="124" cy="13" r="8" fill="#FF626E"/><circle cx="143" cy="27" r="8" fill="#FFD447"/>
      </g>
    </svg>
    <CalloutPill color="#55D9FF" progress={routerIn} style={{position: 'absolute', left: 330, top: 65}}>router / wifi</CalloutPill>
    <CalloutPill color={problem ? '#FF777F' : '#66E39B'} progress={metricIn} style={{position: 'absolute', left: wired ? 292 : 320, bottom: 22}}>{problem ? 'ping naik · packet hilang' : wired ? 'kabel LAN · stabil' : 'koneksi stabil'}</CalloutPill>
    <CalloutPill color={accent} progress={serverIn} style={{position: 'absolute', right: 8, top: 80}}>server game</CalloutPill>
  </div>;
};

const NetworkGraphic = ({accent, progress, subject}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const nodes = [[110,310],[260,130],[430,300],[610,130],[770,315],[455,520]];
  return <div style={{position: 'relative', width: 880, height: 650, transform: `scale(${.82 + progress * .18})`}}>
    <svg width="880" height="650" viewBox="0 0 880 650" style={{position: 'absolute'}}>
      {[[0,1],[1,2],[2,3],[3,4],[2,5],[5,4]].map(([a,b], index) => <path key={index} d={`M${nodes[a][0]} ${nodes[a][1]} L${nodes[b][0]} ${nodes[b][1]}`} stroke="rgba(255,255,255,.42)" strokeWidth="10" strokeLinecap="round" strokeDasharray="18 18" strokeDashoffset={-(frame * (1.5 + index * .12))}/>) }
      {nodes.map(([x,y], index) => <g key={index} transform={`translate(${x} ${y}) scale(${.65 + progress * .35})`}>
        <circle r="64" fill={index === 2 ? accent : '#F8F5EA'} stroke="#202741" strokeWidth="8"/>
        <circle r={18 + Math.sin(frame / fps * 3 + index) * 4} fill={index === 2 ? '#202741' : accent}/>
      </g>)}
      <circle r="13" fill="#fff" cx={110 + ((frame * 8) % 660)} cy={310 - Math.sin((frame / 83) * Math.PI) * 180} style={{filter: `drop-shadow(0 0 12px ${accent})`}}/>
    </svg>
    <div style={{position: 'absolute', left: 180, right: 180, bottom: 0, display: 'grid', placeItems: 'center'}}><SubjectPlate subject={subject} accent={accent}/></div>
  </div>;
};

const SecurityGraphic = ({accent, progress, subject}) => {
  const frame = useCurrentFrame();
  const pulse = 1 + Math.sin(frame * .08) * .035;
  return <div style={{position: 'relative', width: 790, height: 650, display: 'grid', placeItems: 'center', transform: `scale(${(.8 + progress * .2) * pulse})`}}>
    {[0,1,2].map((ring) => <div key={ring} style={{position: 'absolute', width: 370 + ring * 120, height: 370 + ring * 120, borderRadius: '50%', border: `4px solid ${accent}${ring === 0 ? '88' : '30'}`, transform: `scale(${.84 + progress * .16}) rotate(${frame * (ring % 2 ? -.08 : .06)}deg)`}}/>)}
    <svg width="430" height="500" viewBox="0 0 430 500" style={{filter: 'drop-shadow(0 28px 35px rgba(0,0,0,.28))'}}>
      <path d="M215 20 L390 82 V225 C390 340 318 431 215 475 C112 431 40 340 40 225 V82 Z" fill={accent} stroke="#202741" strokeWidth="14"/>
      <path d="M125 245 L187 307 L315 166" fill="none" stroke="#202741" strokeWidth="28" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="300" strokeDashoffset={(1-progress)*300}/>
    </svg>
    {[0,1,2,3,4,5].map((dot) => <i key={dot} style={{position: 'absolute', width: 24, height: 24, borderRadius: 7, background: dot % 2 ? '#FF626E' : '#fff', left: `${7 + (dot * 17) % 88}%`, top: `${12 + (dot * 29) % 72}%`, transform: `translateY(${Math.sin(frame * .06 + dot) * 22}px) scale(${progress})`}}/>)}
    <div style={{position: 'absolute', bottom: -5}}><SubjectPlate subject={subject} accent={accent}/></div>
  </div>;
};

const JourneyGraphic = ({accent, progress, subject}) => {
  const frame = useCurrentFrame();
  const travel = Math.min(1, ((frame % 150) / 100)) * progress;
  return <div style={{position: 'relative', width: 900, height: 650}}>
    <svg width="900" height="650" viewBox="0 0 900 650">
      <path d="M70 525 C220 120 510 560 820 135" fill="none" stroke="rgba(255,255,255,.28)" strokeWidth="34" strokeLinecap="round"/>
      <path d="M70 525 C220 120 510 560 820 135" fill="none" stroke={accent} strokeWidth="13" strokeLinecap="round" strokeDasharray="20 18" strokeDashoffset={-frame * 2}/>
      <circle cx="70" cy="525" r="45" fill="#F8F5EA" stroke="#202741" strokeWidth="8"/>
      <path d="M780 110 L850 110 L850 215 L815 190 L780 215 Z" fill="#FF626E" stroke="#202741" strokeWidth="8"/>
      <g transform={`translate(${70 + travel * 745} ${525 - Math.sin(travel * Math.PI) * 245 - travel * 135}) rotate(${-20 + travel * 10})`}>
        <rect x="-58" y="-38" width="116" height="76" rx="22" fill="#FFD447" stroke="#202741" strokeWidth="8"/>
        <circle cx="-35" cy="42" r="18" fill="#202741"/><circle cx="35" cy="42" r="18" fill="#202741"/>
      </g>
    </svg>
    <div style={{position: 'absolute', left: 190, right: 190, bottom: 5, display: 'grid', placeItems: 'center'}}><SubjectPlate subject={subject} accent={accent}/></div>
  </div>;
};

const ComparisonGraphic = ({accent, progress, subject}) => <div style={{position: 'relative', width: 900, height: 650, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 35}}>
  {[0,1].map((side) => <div key={side} style={{width: 375, height: 470, borderRadius: 42, display: 'grid', placeItems: 'center', color: '#202741', background: side ? accent : '#F8F5EA', border: '8px solid #202741', boxShadow: '0 28px 60px rgba(0,0,0,.28)', transform: `translateX(${(1-progress)*(side ? 140 : -140)}px) rotate(${(1-progress)*(side ? 8 : -8)}deg)`}}>
    <div style={{width: 180, height: 180, borderRadius: side ? 48 : '50%', background: side ? '#202741' : accent, display: 'grid', placeItems: 'center', color: side ? '#fff' : '#202741', fontSize: 86, fontWeight: 950}}>{side ? 'B' : 'A'}</div>
  </div>)}
  <div style={{position: 'absolute', left: '50%', top: '42%', width: 110, height: 110, marginLeft: -55, borderRadius: '50%', display: 'grid', placeItems: 'center', background: '#FF626E', border: '7px solid #202741', fontSize: 36, fontWeight: 950, transform: `scale(${.65 + progress * .35})`}}>VS</div>
  <div style={{position: 'absolute', left: 185, right: 185, bottom: 0, display: 'grid', placeItems: 'center'}}><SubjectPlate subject={subject} accent={accent}/></div>
</div>;

const PeopleGraphic = ({accent, progress, subject}) => {
  const frame = useCurrentFrame();
  return <div style={{position: 'relative', width: 900, height: 650, display: 'flex', justifyContent: 'space-around', alignItems: 'center'}}>
    {[0,1,2].map((person) => <div key={person} style={{position: 'relative', width: 220, height: 430, transform: `translateY(${(1-progress)*(person%2 ? -80 : 80)}px)`}}>
      <div style={{position: 'absolute', left: 55, top: 20, width: 110, height: 110, borderRadius: '50%', background: person === 1 ? accent : '#F8F5EA', border: '7px solid #202741'}}/>
      <div style={{position: 'absolute', left: 25, top: 125, width: 170, height: 250, borderRadius: '70px 70px 38px 38px', background: person === 1 ? '#F8F5EA' : accent, border: '7px solid #202741'}}/>
    </div>)}
    <div style={{position: 'absolute', top: 155, left: 125 + ((frame * 5) % 590), width: 78, height: 78, borderRadius: 22, background: '#FFD447', border: '7px solid #202741', transform: `rotate(${frame * 1.2}deg) scale(${progress})`}}/>
    <div style={{position: 'absolute', left: 190, right: 190, bottom: 5, display: 'grid', placeItems: 'center'}}><SubjectPlate subject={subject} accent={accent}/></div>
  </div>;
};

const MoneyGraphic = ({accent, progress, subject}) => <div style={{position: 'relative', width: 850, height: 650, display: 'flex', alignItems: 'flex-end', justifyContent: 'center', gap: 28, paddingBottom: 115}}>
  {[.38,.58,.78,1].map((height, index) => <div key={index} style={{width: 145, height: 360 * height * progress, minHeight: 35, borderRadius: '20px 20px 10px 10px', background: index === 3 ? accent : '#FFD447', border: '7px solid #202741', boxShadow: '0 18px 35px rgba(0,0,0,.23)', position: 'relative'}}>{[0,1,2].map((line) => <i key={line} style={{position: 'absolute', left: 15, right: 15, top: 20 + line * 45, height: 9, borderRadius: 9, background: 'rgba(32,39,65,.28)'}}/>)}</div>)}
  <svg width="760" height="360" viewBox="0 0 760 360" style={{position: 'absolute', left: 45, top: 15}}><path d="M35 300 C190 280 260 205 360 210 C500 218 585 85 720 55" fill="none" stroke="#fff" strokeWidth="15" strokeLinecap="round" strokeDasharray="900" strokeDashoffset={(1-progress)*900}/><path d="M680 35 L730 52 L704 98" fill="none" stroke="#fff" strokeWidth="15" strokeLinecap="round" strokeLinejoin="round"/></svg>
  <div style={{position: 'absolute', left: 180, right: 180, bottom: 5, display: 'grid', placeItems: 'center'}}><SubjectPlate subject={subject} accent={accent}/></div>
</div>;

const TimelineGraphic = ({accent, progress, subject}) => <div style={{position: 'relative', width: 900, height: 650, display: 'grid', placeItems: 'center'}}>
  <div style={{position: 'absolute', left: 75, right: 75, top: 300, height: 18, borderRadius: 99, background: 'rgba(255,255,255,.25)', overflow: 'hidden'}}><div style={{height: '100%', width: `${progress*100}%`, background: accent}}/></div>
  {[0,1,2,3].map((event) => { const local = Math.max(0, Math.min(1, progress*1.5-event*.18)); return <div key={event} style={{position: 'absolute', left: 80+event*205, top: event%2 ? 320 : 120, width: 180, height: 155, borderRadius: 28, background: event===3 ? accent : '#F8F5EA', color: '#202741', border: '7px solid #202741', display: 'grid', placeItems: 'center', fontSize: 36, fontWeight: 950, opacity: local, transform: `translateY(${(1-local)*(event%2 ? 45 : -45)}px)`}}>{String(event+1).padStart(2,'0')}</div>; })}
  <div style={{position: 'absolute', left: 180, right: 180, bottom: 5, display: 'grid', placeItems: 'center'}}><SubjectPlate subject={subject} accent={accent}/></div>
</div>;

const MachineGraphic = ({accent, progress, subject}) => {
  const frame = useCurrentFrame();
  const gears = [{x:170,y:260,s:210,d:1},{x:365,y:135,s:270,d:-1},{x:590,y:310,s:230,d:1}];
  return <div style={{position: 'relative', width: 850, height: 650}}>
    {gears.map((gear,index) => <div key={index} style={{position: 'absolute', left: gear.x, top: gear.y, width: gear.s, height: gear.s, borderRadius: '50%', background: index===1 ? accent : '#F8F5EA', border: '18px dashed #202741', boxShadow: '0 24px 50px rgba(0,0,0,.25)', transform: `rotate(${frame*gear.d*.7}deg) scale(${.7+progress*.3})`, display: 'grid', placeItems: 'center'}}><i style={{width: gear.s*.28, height: gear.s*.28, borderRadius: '50%', background: '#202741'}}/></div>)}
    <div style={{position: 'absolute', left: 165, right: 165, bottom: 0, display: 'grid', placeItems: 'center'}}><SubjectPlate subject={subject} accent={accent}/></div>
  </div>;
};

const MotorcycleGraphic = ({accent, progress, subject, detail}) => {
  const frame = useCurrentFrame();
  const wheelTurn = frame * 5.2;
  const ride = Math.sin(frame * .095) * 5;
  const shake = /getar/i.test(`${subject} ${detail}`) ? Math.sin(frame * .9) * 7 : 0;
  return <div style={{position: 'relative', width: 900, height: 650, transform: `translateX(${(1-progress)*-170}px) scale(${.82+progress*.18})`}}>
    <svg width="900" height="650" viewBox="0 0 900 650" style={{overflow: 'visible', filter: 'drop-shadow(0 25px 28px rgba(0,0,0,.28))'}}>
      <path d="M45 515 H855" stroke="rgba(255,255,255,.32)" strokeWidth="14" strokeLinecap="round" strokeDasharray="70 34" strokeDashoffset={-frame*8}/>
      <g transform={`translate(${shake} ${ride})`}>
        {[[245,465],[672,465]].map(([x,y], index) => <g key={index} transform={`translate(${x} ${y}) rotate(${wheelTurn} ${0} ${0})`}>
          <circle r="104" fill="#15213B" stroke="#F8F5EA" strokeWidth="14"/>
          <circle r="63" fill="#293654" stroke={accent} strokeWidth="10"/>
          {[0,45,90,135].map((angle) => <line key={angle} x1="-54" y1="0" x2="54" y2="0" stroke="#F8F5EA" strokeWidth="9" strokeLinecap="round" transform={`rotate(${angle})`}/>) }
          <circle r="18" fill={accent}/>
        </g>)}
        <path d="M245 452 C280 318 363 278 492 282 L603 298 C640 305 670 344 677 422 L638 427 C622 368 585 352 530 355 L395 357 C340 358 309 389 294 452 Z" fill={accent} stroke="#202741" strokeWidth="14" strokeLinejoin="round"/>
        <path d="M405 292 C438 214 516 187 578 217 L615 302 L511 302 L475 255 L429 309 Z" fill="#F8F5EA" stroke="#202741" strokeWidth="13" strokeLinejoin="round"/>
        <path d="M578 214 L642 184" stroke="#202741" strokeWidth="16" strokeLinecap="round"/><path d="M624 178 H685" stroke="#202741" strokeWidth="14" strokeLinecap="round"/>
        <path d="M354 282 C380 242 436 228 500 244" stroke="#202741" strokeWidth="22" strokeLinecap="round"/>
        <rect x="332" y="343" width="167" height="72" rx="34" fill="#263453" stroke="#202741" strokeWidth="10"/>
        <circle cx="598" cy="286" r="23" fill="#FFD447" stroke="#202741" strokeWidth="8"/>
      </g>
      {[0,1,2].map((smoke) => <circle key={smoke} cx={110-((frame*3+smoke*45)%120)} cy={395-smoke*28-Math.sin(frame*.08+smoke)*12} r={13+smoke*7} fill="rgba(255,255,255,.28)"/>)}
    </svg>
    <div style={{position: 'absolute', left: 175, right: 175, bottom: 0, display: 'grid', placeItems: 'center'}}><SubjectPlate subject={subject || 'MOTOR MATIC'} accent={accent}/></div>
  </div>;
};

const CvtGraphic = ({accent, progress, subject, detail}) => {
  const frame = useCurrentFrame();
  const dirty = /kotor|debu|kampas/i.test(`${subject} ${detail}`);
  const rotation = frame * 4.8;
  return <div style={{position: 'relative', width: 900, height: 650, transform: `scale(${.8+progress*.2})`}}>
    <svg width="900" height="650" viewBox="0 0 900 650" style={{filter: 'drop-shadow(0 28px 34px rgba(0,0,0,.3))'}}>
      <path d="M105 155 Q115 80 215 72 H682 Q790 80 800 175 V440 Q790 530 690 542 H208 Q110 530 98 435 Z" fill="#F8F5EA" stroke="#202741" strokeWidth="14"/>
      <path d="M270 216 C370 135 530 135 640 215 C691 255 693 360 640 405 C530 485 370 485 270 404 C220 362 220 258 270 216 Z" fill="none" stroke="#202741" strokeWidth="46" strokeLinecap="round"/>
      <path d="M270 216 C370 135 530 135 640 215 C691 255 693 360 640 405 C530 485 370 485 270 404 C220 362 220 258 270 216 Z" fill="none" stroke={accent} strokeWidth="15" strokeDasharray="28 20" strokeDashoffset={-frame*5} strokeLinecap="round"/>
      {[[280,310,118],[650,310,92]].map(([x,y,r], index) => <g key={index} transform={`translate(${x} ${y}) rotate(${rotation*(index ? -1.25 : 1)})`}>
        <circle r={r} fill={index ? '#55D9FF' : '#FFD447'} stroke="#202741" strokeWidth="13"/>
        {[0,60,120].map((angle) => <rect key={angle} x="-13" y={-r+18} width="26" height={r-32} rx="13" fill="#202741" transform={`rotate(${angle})`}/>) }
        <circle r="31" fill="#F8F5EA" stroke="#202741" strokeWidth="10"/>
      </g>)}
      <rect x="360" y="102" width="180" height="53" rx="26" fill="#202741"/><text x="450" y="139" textAnchor="middle" fill="#fff" fontSize="30" fontWeight="900">V-BELT</text>
      <rect x="175" y="448" width="220" height="53" rx="26" fill="#202741"/><text x="285" y="485" textAnchor="middle" fill="#fff" fontSize="27" fontWeight="900">KAMPAS CVT</text>
      {dirty ? [0,1,2,3,4,5,6].map((dot) => <circle key={dot} cx={170+(dot*87)%560} cy={155+(dot*73)%290} r={8+(dot%3)*4} fill="#9A7657" opacity={.55+Math.sin(frame*.08+dot)*.2}/>) : null}
    </svg>
    <div style={{position: 'absolute', left: 175, right: 175, bottom: 0, display: 'grid', placeItems: 'center'}}><SubjectPlate subject={subject || 'TRANSMISI CVT'} accent={accent}/></div>
  </div>;
};

const SparkPlugGraphic = ({accent, progress, subject}) => {
  const frame = useCurrentFrame();
  const flash = Math.max(0, Math.sin(frame*.34));
  return <div style={{position: 'relative', width: 780, height: 650, display: 'grid', placeItems: 'center', transform: `translateY(${(1-progress)*90}px) scale(${.76+progress*.24})`}}>
    <svg width="610" height="590" viewBox="0 0 610 590" style={{filter: 'drop-shadow(0 28px 32px rgba(0,0,0,.3))'}}>
      <g transform="translate(305 40) rotate(10)">
        <rect x="-34" y="0" width="68" height="78" rx="18" fill="#C9D1DC" stroke="#202741" strokeWidth="11"/>
        <rect x="-72" y="68" width="144" height="218" rx="49" fill="#F8F5EA" stroke="#202741" strokeWidth="13"/>
        {[0,1,2,3].map((rib) => <rect key={rib} x="-82" y={98+rib*39} width="164" height="18" rx="9" fill="#D9E0E7" stroke="#202741" strokeWidth="6"/>)}
        <path d="M-101 276 L101 276 L77 352 L-77 352 Z" fill={accent} stroke="#202741" strokeWidth="13"/>
        <rect x="-67" y="344" width="134" height="132" rx="9" fill="#AEB8C6" stroke="#202741" strokeWidth="12"/>
        {[0,1,2,3,4].map((thread) => <line key={thread} x1="-58" y1={368+thread*21} x2="58" y2={368+thread*21} stroke="#657188" strokeWidth="8"/>)}
        <rect x="-19" y="470" width="38" height="70" rx="8" fill="#C9D1DC" stroke="#202741" strokeWidth="9"/>
        <path d="M62 468 V526 Q62 552 37 552 H17" fill="none" stroke="#202741" strokeWidth="18" strokeLinecap="round"/>
        <path d="M17 536 L-8 554 L22 564 L-3 582" fill="none" stroke="#FFF47A" strokeWidth={8+flash*8} strokeLinecap="round" strokeLinejoin="round" style={{filter: `drop-shadow(0 0 ${10+flash*25}px #55D9FF)`}}/>
      </g>
    </svg>
    <div style={{position: 'absolute', left: 120, right: 120, bottom: 0, display: 'grid', placeItems: 'center'}}><SubjectPlate subject={subject || 'BUSI'} accent={accent}/></div>
  </div>;
};

const PlantWorldGraphic = ({accent, progress, localSeconds = 0, mode = 'plant_life', subject, sceneTime = 'neutral', sceneWeather = 'clear'}) => {
  const sway = Math.sin(localSeconds * 1.7);
  const pulse = (Math.sin(localSeconds * 3.1) + 1) / 2;
  const night = sceneTime === 'night';
  const sceneScale = .86 + progress * .14;
  const gasParticles = [0, 1, 2, 3];
  const leaves = [
    [245, 280, -28], [330, 220, -8], [415, 255, 16], [510, 215, 25],
    [575, 300, 43], [370, 335, -15], [475, 355, 20], [295, 390, -35],
  ];

  if (mode === 'stomata') {
    const poreOpen = 20 + pulse * 15;
    return <div style={{position: 'relative', width: 820, height: 760, transform: `scale(${sceneScale})`, filter: 'drop-shadow(0 30px 40px rgba(0,0,0,.28))'}}>
      <svg width="820" height="700" viewBox="0 0 820 700">
        <defs>
          <linearGradient id="leafMacro" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#9BE55F"/><stop offset="1" stopColor="#2B9B58"/></linearGradient>
          <filter id="stomataGlow"><feGaussianBlur stdDeviation="9" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
        </defs>
        <rect x="25" y="25" width="770" height="630" rx="82" fill="url(#leafMacro)" stroke="#173D36" strokeWidth="12"/>
        <path d="M80 530 C260 430 450 290 745 120" fill="none" stroke="#D9FF9E" strokeWidth="22" opacity=".5"/>
        {[0,1,2,3].map((row) => [0,1,2,3,4].map((col) => <path key={`${row}-${col}`} d={`M${70+col*145+(row%2)*35} ${75+row*135} q58 -38 116 0 l18 75 q-55 50 -122 12 z`} fill="rgba(255,255,220,.13)" stroke="rgba(25,78,55,.36)" strokeWidth="6"/>))}
        <g transform={`translate(410 345) scale(${.82 + progress * .18})`} filter="url(#stomataGlow)">
          <ellipse cx="-92" cy="0" rx="98" ry="145" fill="#69C85A" stroke="#183F38" strokeWidth="12" transform="rotate(-18)"/>
          <ellipse cx="92" cy="0" rx="98" ry="145" fill="#69C85A" stroke="#183F38" strokeWidth="12" transform="rotate(18)"/>
          <ellipse cx="0" cy="0" rx={poreOpen} ry="104" fill="#13263B" stroke="#D7FFB2" strokeWidth="8"/>
          <circle cx="-95" cy="-12" r="18" fill="#D7FF72"/><circle cx="95" cy="12" r="18" fill="#D7FF72"/>
        </g>
        {gasParticles.map((item) => {
          const travel = ((localSeconds * .35 + item * .22) % 1);
          const entering = item % 2 === 0;
          const x = entering ? 90 + travel * 285 : 445 + travel * 285;
          const y = 300 + (item % 2 ? 1 : -1) * (1 - travel) * 95 + Math.sin(localSeconds * 2 + item) * 12;
          return <g key={item} transform={`translate(${x} ${y})`} opacity={.55 + progress * .45}>
            <circle r="34" fill={entering ? '#FFD447' : '#69E7FF'} stroke="#17304A" strokeWidth="7"/>
            <text y="9" textAnchor="middle" fontSize="24" fontWeight="900" fill="#17233D">{entering ? 'CO₂' : 'O₂'}</text>
          </g>;
        })}
        <text x="410" y="625" textAnchor="middle" fontSize="28" fontWeight="950" fill="#173D36">PERTUKARAN GAS MELALUI STOMATA</text>
      </svg>
      <div style={{position: 'absolute', left: 115, right: 115, bottom: 0}}><SubjectPlate subject="STOMATA · PORI DAUN" accent={accent}/></div>
    </div>;
  }

  const photosynthesis = mode === 'photosynthesis';
  const respiration = mode === 'plant_respiration';
  const dayNight = mode === 'plant_day_night';
  const skyTop = night ? '#18285C' : sceneWeather === 'rain' ? '#536D89' : photosynthesis ? '#48BEE8' : '#5AADE0';
  const skyBottom = night ? '#46356F' : sceneWeather === 'rain' ? '#ACBFC5' : '#D9F4C8';
  const antTravel = 300 + ((localSeconds * 48) % 190);

  return <div style={{position: 'relative', width: 840, height: 790, transform: `translateY(${(1-progress)*36}px) scale(${sceneScale})`, filter: 'drop-shadow(0 30px 42px rgba(0,0,0,.3))'}}>
    <svg width="840" height="735" viewBox="0 0 840 735">
      <defs>
        <linearGradient id="plantSky" x1="0" y1="0" x2="0" y2="1"><stop stopColor={skyTop}/><stop offset="1" stopColor={skyBottom}/></linearGradient>
        <linearGradient id="plantGround" x1="0" y1="0" x2="0" y2="1"><stop stopColor="#63B45B"/><stop offset="1" stopColor="#245B43"/></linearGradient>
        <filter id="energyGlow"><feGaussianBlur stdDeviation="12" result="g"/><feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      </defs>
      <rect x="18" y="18" width="804" height="675" rx="74" fill="url(#plantSky)" stroke="#182B46" strokeWidth="12"/>
      {dayNight ? <>
        <path d="M420 25 H750 Q815 25 815 90 V685 H420 Z" fill="#28345F"/>
        <path d="M420 25 H90 Q25 25 25 90 V685 H420 Z" fill="#98D9E7"/>
        <path d="M420 25 V690" stroke="rgba(255,255,255,.38)" strokeWidth="5" strokeDasharray="14 18"/>
        <circle cx="165" cy="125" r="62" fill="#FFD447" stroke="#F58C35" strokeWidth="10" style={{filter: 'drop-shadow(0 0 25px #FFD44799)'}}/>
        <path d="M690 72 a70 70 0 1 0 54 112 a62 62 0 1 1 -54 -112" fill="#F8F4CE" stroke="#B9C8EF" strokeWidth="9"/>
        {[0,1,2,3,4].map((star) => <circle key={star} cx={555+star*48} cy={205+(star%2)*55} r={5+(star%3)} fill="#FFF7C8" opacity={.75 + pulse*.25}/>) }
      </> : night ? <>
        <path d="M145 68 a62 62 0 1 0 48 100 a55 55 0 1 1 -48 -100" fill="#F8F4CE" stroke="#B9C8EF" strokeWidth="9"/>
        {[0,1,2,3,4].map((star) => <circle key={star} cx={300+star*98} cy={85+(star%2)*65} r={5+(star%3)} fill="#FFF7C8" opacity={.75+pulse*.25}/>)}
      </> : <>
        <circle cx="145" cy="130" r={58+pulse*5} fill="#FFD447" stroke="#F58C35" strokeWidth="10" style={{filter: 'drop-shadow(0 0 32px #FFD447AA)'}}/>
        {[0,1,2,3,4,5,6,7].map((ray) => <line key={ray} x1="145" y1="130" x2={145+Math.cos(ray*Math.PI/4)*(95+pulse*18)} y2={130+Math.sin(ray*Math.PI/4)*(95+pulse*18)} stroke="#FFF2A2" strokeWidth="9" strokeLinecap="round"/>) }
      </>}
      <path d="M25 555 Q160 485 295 550 T565 545 T815 525 V690 H25 Z" fill="url(#plantGround)"/>
      <path d="M390 535 C360 600 315 625 270 660 M410 540 C430 600 475 630 530 665 M400 548 V680" fill="none" stroke="#75482D" strokeWidth="22" strokeLinecap="round"/>
      <path d="M402 565 C380 680 350 692 323 700 M418 570 C445 665 490 684 550 700" fill="none" stroke="#D6A05E" strokeWidth="8" strokeLinecap="round" opacity=".8"/>
      <path d="M405 560 C410 455 403 330 420 245" fill="none" stroke="#75482D" strokeWidth="58" strokeLinecap="round"/>
      <path d="M405 395 C345 350 300 324 245 308 M412 350 C475 305 530 286 585 270 M407 455 C340 430 305 410 265 380 M412 420 C480 390 535 365 590 340" fill="none" stroke="#75482D" strokeWidth="30" strokeLinecap="round"/>
      {[[285,255,105],[380,205,125],[490,235,118],[575,300,105],[315,355,112],[455,335,130],[555,395,100]].map(([cx,cy,r], index) => <circle key={index} cx={cx} cy={cy} r={r} fill={index%2 ? '#2F9E58' : '#44B865'} stroke="#1B6948" strokeWidth="9" style={{transformOrigin: `${cx}px ${cy}px`, transform: `scale(${1 + Math.sin(localSeconds*1.2+index)*.018})`}}/>) }
      {leaves.map(([x,y,rotate], index) => <ellipse key={index} cx={x} cy={y} rx="42" ry="20" fill={index%2 ? '#91DF5A' : '#B8EE6B'} stroke="#245C40" strokeWidth="6" transform={`rotate(${rotate+sway*3} ${x} ${y})`}/>) }
      <g transform={`translate(${antTravel} 375)`}>
        <circle cx="-18" cy="0" r="8" fill="#291E26"/><circle cx="0" cy="0" r="10" fill="#291E26"/><circle cx="20" cy="0" r="12" fill="#291E26"/>
        {[[-7,-14],[5,-15],[15,-15],[-7,14],[5,15],[15,15]].map(([x,y], index) => <line key={index} x1={x} y1="0" x2={x+(index<3?-11:11)} y2={y} stroke="#291E26" strokeWidth="4" strokeLinecap="round"/>) }
      </g>
      {photosynthesis ? <>
        {[0,1,2].map((item) => { const t=(localSeconds*.28+item*.28)%1; return <g key={`co-${item}`} transform={`translate(${70+t*260} ${340+item*65-Math.sin(t*Math.PI)*65})`}><circle r="31" fill="#FFD447" stroke="#243653" strokeWidth="7"/><text y="9" textAnchor="middle" fontSize="23" fontWeight="900" fill="#243653">CO₂</text></g>; })}
        {[0,1,2].map((item) => { const t=(localSeconds*.3+item*.3)%1; return <g key={`ox-${item}`} transform={`translate(${545+t*210} ${250+item*72-Math.sin(t*Math.PI)*80})`}><circle r="31" fill="#6EE7FF" stroke="#243653" strokeWidth="7"/><text y="9" textAnchor="middle" fontSize="24" fontWeight="900" fill="#243653">O₂</text></g>; })}
        <path d="M190 190 Q285 240 355 285" fill="none" stroke="#FFF3A5" strokeWidth="14" strokeLinecap="round" strokeDasharray="22 15" strokeDashoffset={-localSeconds*35}/>
        <text x="170" y="255" fontSize="24" fontWeight="950" fill="#5B4520">CAHAYA</text>
      </> : null}
      {respiration ? <>
        {[0,1,2].map((item) => { const t=(localSeconds*.32+item*.31)%1; return <g key={item} transform={`translate(${735-t*285} ${280+item*88})`}><circle r="30" fill="#6EE7FF" stroke="#243653" strokeWidth="7"/><text y="9" textAnchor="middle" fontSize="24" fontWeight="900" fill="#243653">O₂</text></g>; })}
        <circle cx="410" cy="420" r={52+pulse*18} fill="#FFD447" opacity={.36+pulse*.4} filter="url(#energyGlow)"/>
        <path d="M405 500 L370 438 L410 452 L445 390 L438 445 L480 438 Z" fill="#FFF47A" stroke="#744B22" strokeWidth="8" filter="url(#energyGlow)"/>
        <text x="500" y="500" fontSize="25" fontWeight="950" fill="#243653">ENERGI</text>
      </> : null}
      {dayNight ? <>
        <path d="M105 390 C210 350 255 330 320 350" fill="none" stroke="#6EE7FF" strokeWidth="12" strokeDasharray="20 14" strokeDashoffset={-localSeconds*30}/>
        <path d="M735 405 C640 360 585 345 520 365" fill="none" stroke="#6EE7FF" strokeWidth="12" strokeDasharray="20 14" strokeDashoffset={-localSeconds*30}/>
        <text x="95" y="440" fontSize="25" fontWeight="950" fill="#183350">TETAP BERNAPAS</text>
        <text x="570" y="455" fontSize="25" fontWeight="950" fill="#F8F4CE">TETAP BERNAPAS</text>
      </> : null}
      {mode === 'plant_life' ? <>
        <path d="M110 485 Q220 430 300 455" fill="none" stroke="#E5FFF2" strokeWidth="9" strokeLinecap="round" strokeDasharray="18 16" strokeDashoffset={-localSeconds*24}/>
        <circle cx="110" cy="485" r="18" fill="#6EE7FF"/><circle cx="145" cy="465" r="13" fill="#6EE7FF"/>
      </> : null}
      {sceneWeather === 'rain' ? <g>
        {[0,1,2,3,4,5,6,7,8,9].map((drop) => <line key={drop} x1={65+drop*76} y1={65+((localSeconds*190+drop*51)%490)} x2={55+drop*76} y2={96+((localSeconds*190+drop*51)%490)} stroke="#DBF4FF" strokeWidth="6" strokeLinecap="round" opacity=".8"/>)}
        <path d="M65 95 Q35 52 85 46 Q110 12 148 43 Q197 27 215 70 Q244 98 212 115 H80 Z" fill="#C9D6E0" stroke="#53657A" strokeWidth="6"/>
      </g> : null}
      {sceneWeather === 'hot' ? [0,1,2].map((wave) => <path key={wave} d={`M${90+wave*300} 480 q-20 -45 0 -90 t0 -90`} fill="none" stroke="#FFB56B" strokeWidth="9" opacity={.4+pulse*.25} transform={`translate(0 ${sway*10})`}/>) : null}
      {sceneWeather === 'cold' ? [0,1,2,3].map((flake) => <text key={flake} x={95+flake*195} y={120+((localSeconds*35+flake*110)%340)} fontSize="34" fill="#F1FAFF">❄</text>) : null}
      {sceneWeather === 'haze' ? <path d="M40 230 H800 M40 290 H800 M40 350 H800" stroke="#DDE5DD" strokeWidth="32" opacity=".28"/> : null}
    </svg>
    <div style={{position: 'absolute', left: 110, right: 110, bottom: 0}}><SubjectPlate subject={photosynthesis ? 'CO₂ MASUK · O₂ KELUAR' : respiration ? 'OKSIGEN → ENERGI' : dayNight ? 'BERNAPAS SIANG & MALAM' : 'DUNIA TUMBUHAN'} accent={accent}/></div>
  </div>;
};

const ConceptGraphic = ({accent, progress, subject, metaphor}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const objects = [0,1,2,3,4];
  return <div style={{position: 'relative', width: 790, height: 650, display: 'grid', placeItems: 'center', transform: `scale(${.74 + progress * .26})`}}>
    <div style={{position: 'absolute', width: 540, height: 540, borderRadius: '50%', background: `${accent}24`, border: `4px solid ${accent}55`}}/>
    {objects.map((item) => { const angle = frame/fps*.45 + item*Math.PI*2/objects.length; return <div key={item} style={{position: 'absolute', left: 365+Math.cos(angle)*270, top: 280+Math.sin(angle)*210, width: 86, height: 86, borderRadius: item%2 ? 24 : '50%', background: item%2 ? accent : '#F8F5EA', border: '7px solid #202741', transform: `rotate(${angle*42}deg) scale(${progress})`}}/>; })}
    <div style={{position: 'relative', width: 430, height: 320, borderRadius: 48, background: '#F8F5EA', border: '8px solid #202741', display: 'grid', placeItems: 'center', color: '#202741', boxShadow: '0 32px 70px rgba(0,0,0,.3)', textAlign: 'center', padding: 35}}>
      <svg width="155" height="150" viewBox="0 0 155 150"><path d="M77 8 L96 57 L148 75 L97 94 L77 143 L58 94 L7 75 L58 56 Z" fill={accent} stroke="#202741" strokeWidth="8"/></svg>
      <strong style={{fontSize: 35, lineHeight: 1.05, textTransform: 'uppercase'}}>{subject || metaphor || 'IDE UTAMA'}</strong>
    </div>
  </div>;
};

const DirectedSceneContext = ({beat, progress, localSeconds}) => {
  const setting = beat.sceneSetting || 'abstract';
  const time = beat.sceneTime || 'neutral';
  const weather = beat.sceneWeather || 'clear';
  const mood = beat.sceneMood || 'curious';
  const situation = beat.situation || 'explanation';
  const details = Array.isArray(beat.environmentDetails) ? beat.environmentDetails : [];
  const pressure = mood === 'pressure';
  const outdoor = ['forest', 'road', 'public_space', 'market'].includes(setting);
  const desk = ['desk', 'office', 'gaming_desk', 'analysis_room', 'device_cutaway'].includes(setting);
  const night = time === 'night';
  const pulse = (Math.sin(localSeconds * 2.4) + 1) / 2;
  const accent = beat.accent || '#55C7F3';
  const topColor = night ? '#18234E' : pressure ? '#6C4052' : '#56A6C9';
  const bottomColor = night ? '#40325E' : pressure ? '#E49A68' : '#D8E9C1';

  return <AbsoluteFill style={{overflow: 'hidden', borderRadius: 62, border: `7px solid ${pressure ? '#FF8A6A' : '#172A45'}`, background: `linear-gradient(180deg,${topColor},${bottomColor})`, boxShadow: '0 30px 70px rgba(0,0,0,.28)'}}>
    {outdoor ? <>
      {night ? <div style={{position: 'absolute', right: 78, top: 56, width: 84, height: 84, borderRadius: '50%', background: '#FFF5C5', boxShadow: '0 0 34px #FFF5C577'}}/> : <div style={{position: 'absolute', right: 70, top: 54, width: 92, height: 92, borderRadius: '50%', background: '#FFD447', boxShadow: '0 0 38px #FFD44799', transform: `scale(${1+pulse*.05})`}}/>}
      <div style={{position: 'absolute', left: -80, right: -80, bottom: 0, height: 250, borderRadius: '50% 50% 0 0', background: setting === 'road' ? '#4A5660' : '#4F9C59', transform: 'translateY(80px)'}}/>
      {setting === 'road' ? <div style={{position: 'absolute', left: 300, top: 350, width: 260, height: 430, background: '#232C36', clipPath: 'polygon(39% 0,61% 0,100% 100%,0 100%)'}}><i style={{position: 'absolute', left: '49%', top: 30, width: 9, height: 380, background: 'repeating-linear-gradient(#FFF 0 32px,transparent 32px 68px)', opacity: .7}}/></div> : null}
      {setting === 'forest' ? [0,1,2,3].map((tree) => <div key={tree} style={{position: 'absolute', left: 35+tree*210, bottom: 80+(tree%2)*30, width: 44, height: 185, borderRadius: 20, background: '#79523A', opacity: .5}}><i style={{position: 'absolute', width: 150, height: 150, borderRadius: '50%', left: -53, top: -90, background: tree%2 ? '#267B52' : '#3B9360'}}/></div>) : null}
    </> : null}
    {desk ? <>
      <div style={{position: 'absolute', left: 52, right: 52, top: 44, height: 285, borderRadius: 34, background: night ? '#152544' : '#BDE4F0', border: '8px solid #273653', overflow: 'hidden'}}>
        {night ? [0,1,2,3,4].map((star) => <i key={star} style={{position: 'absolute', left: 55+star*125, top: 40+(star%2)*65, width: 8, height: 8, borderRadius: '50%', background: '#FFF2B0'}}/>) : <div style={{position: 'absolute', right: 58, top: 42, width: 72, height: 72, borderRadius: '50%', background: '#FFD447'}}/>}
      </div>
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 235, background: setting === 'gaming_desk' ? '#26304A' : '#8B6548', borderTop: '12px solid #342B31'}}/>
      <div style={{position: 'absolute', left: 76, bottom: 90, width: 135, height: 90, borderRadius: 18, background: '#F5E5BC', border: '7px solid #26304A'}}/>
      <div style={{position: 'absolute', right: 75, bottom: 100, width: 72, height: 125, borderRadius: '10px 10px 35px 35px', background: '#83C97B', border: '7px solid #26304A'}}/>
    </> : null}
    {setting === 'server_room' || setting === 'control_room' ? <>
      {[0,1,2].map((rack) => <div key={rack} style={{position: 'absolute', left: 55+rack*250, top: 85, width: 190, height: 545, borderRadius: 24, background: '#18243A', border: '8px solid #334764'}}>{[0,1,2,3,4,5].map((row) => <i key={row} style={{position: 'absolute', left: 20, right: 20, top: 30+row*82, height: 48, borderRadius: 10, background: '#283958', border: '3px solid #4E6486'}}><b style={{position: 'absolute', right: 13, top: 13, width: 15, height: 15, borderRadius: '50%', background: row%2 ? '#6FFFA1' : accent, boxShadow: `0 0 12px ${accent}`}}/></i>)}</div>)}
    </> : null}
    {setting === 'workshop' ? <>
      <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(180deg,#6C7883,#3E4852)'}}/>
      <div style={{position: 'absolute', left: 45, right: 45, top: 55, height: 185, borderRadius: 28, background: '#2B3744', border: '8px solid #202936'}}>{[0,1,2,3].map((tool) => <i key={tool} style={{position: 'absolute', left: 75+tool*170, top: 35, width: 25, height: 100, borderRadius: 12, background: tool%2 ? '#FFD447' : '#D6DEE8', transform: `rotate(${tool%2 ? 22 : -18}deg)`}}/>)}</div>
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 210, background: '#8B6548', borderTop: '12px solid #2A3038'}}/>
    </> : null}
    {setting === 'laboratory' ? <>
      <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(180deg,#C8EEF0,#76B9BF)'}}/>
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 190, background: '#ECF4F1', borderTop: '10px solid #254B5B'}}/>
      {[0,1,2].map((glass) => <div key={glass} style={{position: 'absolute', left: 90+glass*285, bottom: 72, width: 86, height: 120+glass*18, border: '8px solid #315A6A', borderTop: 0, borderRadius: '0 0 30px 30px', background: `${glass%2 ? '#F4A4C5' : '#6EE7FF'}99`}}/>)}
    </> : null}
    {!outdoor && !desk && !['server_room','control_room','workshop','laboratory'].includes(setting) ? <>
      <AbsoluteFill style={{background: `radial-gradient(circle at 50% 42%,${accent}35,transparent 45%),linear-gradient(160deg,#273467,#182451)`}}/>
      <AbsoluteFill style={{opacity: .08, backgroundImage: 'linear-gradient(#fff 1px,transparent 1px),linear-gradient(90deg,#fff 1px,transparent 1px)', backgroundSize: '58px 58px'}}/>
    </> : null}
    {situation === 'cause_effect' ? <svg width="100%" height="100%" viewBox="0 0 840 760" style={{position: 'absolute', opacity: .48}}><path d="M95 565 C240 470 560 470 735 565" fill="none" stroke={pressure ? '#FF7A68' : accent} strokeWidth="18" strokeLinecap="round" strokeDasharray="28 20" strokeDashoffset={-localSeconds*42}/><path d="M710 535 L760 565 L710 595" fill="none" stroke={pressure ? '#FF7A68' : accent} strokeWidth="18" strokeLinecap="round" strokeLinejoin="round"/></svg> : null}
    {situation === 'comparison' ? <div style={{position: 'absolute', left: '50%', top: 45, bottom: 45, width: 5, background: 'rgba(255,255,255,.65)', boxShadow: '0 0 22px #fff'}}/> : null}
    {situation === 'process' ? <div style={{position: 'absolute', left: 80, right: 80, bottom: 65, height: 12, background: `repeating-linear-gradient(90deg,${accent} 0 24px,transparent 24px 42px)`, transform: `translateX(${(localSeconds*20)%42-42}px)`, opacity: .75}}/> : null}
    {details.includes('notification_cards') ? [0,1,2].map((card) => <div key={card} style={{position: 'absolute', right: 42+card*20, top: 170+card*82, width: 180, height: 64, borderRadius: 18, background: card%2 ? '#F0F4FF' : '#FFD8E7', border: '5px solid #25314A', transform: `translateX(${Math.sin(localSeconds*1.7+card)*12}px) rotate(${card*2-2}deg)`, opacity: .82}}/>) : null}
    {details.includes('storage_blocks') ? [0,1,2,3,4].map((block) => <div key={block} style={{position: 'absolute', left: 38+block*58, bottom: 48, width: 48, height: 42+block*14, borderRadius: 9, background: block>2 ? '#FF756B' : '#FFD447', border: '4px solid #27314A'}}/>) : null}
    {details.includes('warning_badge') ? <div style={{position: 'absolute', right: 35, top: 35, width: 86, height: 86, borderRadius: '50%', display: 'grid', placeItems: 'center', background: '#FF655F', color: '#fff', border: '7px solid #2B3045', fontSize: 52, fontWeight: 950, transform: `scale(${.92+pulse*.12})`}}>!</div> : null}
    {details.includes('heat_waves') ? [0,1,2].map((wave) => <div key={wave} style={{position: 'absolute', left: 170+wave*235, top: 100+(wave%2)*80, width: 34, height: 150, borderRadius: '50%', borderLeft: '10px solid #FF8A5C', transform: `translateY(${Math.sin(localSeconds*2+wave)*18}px) rotate(12deg)`, opacity: .7}}/>) : null}
    {details.includes('data_particles') ? [0,1,2,3,4,5].map((dot) => <i key={dot} style={{position: 'absolute', left: `${12+((localSeconds*11+dot*17)%76)}%`, top: `${14+(dot%3)*25}%`, width: 13+dot%2*7, height: 13+dot%2*7, borderRadius: '50%', background: dot%2 ? accent : '#FFD447', boxShadow: `0 0 18px ${accent}`}}/>) : null}
    {weather === 'rain' ? [0,1,2,3,4,5,6,7].map((drop) => <i key={drop} style={{position: 'absolute', left: `${8+drop*12}%`, top: `${((localSeconds*170+drop*83)%700)-80}px`, width: 5, height: 44, borderRadius: 8, background: '#BDEBFF', transform: 'rotate(12deg)', opacity: .75}}/>) : null}
    {weather === 'hot' ? <AbsoluteFill style={{background: 'linear-gradient(180deg,rgba(255,97,52,.16),transparent 42%)'}}/> : null}
    {weather === 'haze' ? <AbsoluteFill style={{background: 'rgba(226,224,211,.25)', backdropFilter: 'blur(5px)'}}/> : null}
  </AbsoluteFill>;
};

const InfographicGraphic = ({beat, progress, localSeconds = 0, beatDuration = 4}) => {
  if (!beat) return null;
  if (beat.presentationScene?.objects?.length) return <PresenterSceneGraphic beat={beat} progress={progress} localSeconds={localSeconds}/>;
  const props = {accent: beat.accent || '#55C7F3', progress, localSeconds, beatDuration, detail: beat.detail || '', options: beat.quizOptions || [], subject: beat.visualSubject || beat.title || '', metaphor: beat.visualMetaphor || '', sceneTime: beat.sceneTime, sceneWeather: beat.sceneWeather};
  if (beat.visual === 'quiz') return <QuizGraphic {...props}/>;
  if (['plant_life', 'stomata', 'photosynthesis', 'plant_respiration', 'plant_day_night'].includes(beat.visual)) return <PlantWorldGraphic {...props} mode={beat.visual}/>;
  const visual = beat.visual === 'phone' ? <PhoneGraphic {...props}/>
    : beat.visual === 'chip' ? <ChipGraphic {...props}/>
    : beat.visual === 'chart' ? <ChartGraphic {...props}/>
    : beat.visual === 'temperature' ? <TemperatureGraphic {...props}/>
    : beat.visual === 'process' ? <ProcessGraphic {...props}/>
    : beat.visual === 'network' ? <NetworkGraphic {...props}/>
    : beat.visual === 'security' ? <SecurityGraphic {...props}/>
    : beat.visual === 'journey' ? <JourneyGraphic {...props}/>
    : beat.visual === 'comparison' ? <ComparisonGraphic {...props}/>
    : beat.visual === 'people' ? <PeopleGraphic {...props}/>
    : beat.visual === 'money' ? <MoneyGraphic {...props}/>
    : beat.visual === 'timeline' ? <TimelineGraphic {...props}/>
    : beat.visual === 'machine' ? <MachineGraphic {...props}/>
    : beat.visual === 'motorcycle' ? <MotorcycleGraphic {...props}/>
    : beat.visual === 'cvt' ? <CvtGraphic {...props}/>
    : beat.visual === 'sparkplug' ? <SparkPlugGraphic {...props}/>
    : beat.visual === 'engine_oil' ? <EngineOilGraphic {...props}/>
    : beat.visual === 'gaming_network' ? <GamingNetworkGraphic {...props}/>
    : <ConceptGraphic {...props}/>;
  const cameraScale = beat.camera === 'macro_cutaway' ? 1.04 : beat.camera === 'wide_environment' ? .88 : .94;
  return <div style={{position: 'relative', width: 840, height: 760, display: 'grid', placeItems: 'center'}}>
    <DirectedSceneContext beat={beat} progress={progress} localSeconds={localSeconds}/>
    <div style={{position: 'relative', zIndex: 2, transform: `scale(${cameraScale})`, transformOrigin: '50% 52%'}}>{visual}</div>
  </div>;
};

const InfographicVideo = ({
  title = 'INFOGRAPHIC EXPLAINER', hook = 'SATU HAL YANG PERLU KAMU TAHU', payoff = 'SUDAH MASUK AKAL?',
  footer = '', sourceNote = '', beats = [], dialogue = [], midCta = {}, watermark = '@ryuundy · HYPIT', styleVersion = '', finalStart: authoredFinalStart,
}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const second = frame / fps;
  const activeIndex = beats.reduce((latest, beat, index) => second >= Number(beat.revealAt || 0) ? index : latest, -1);
  const beat = activeIndex >= 0 ? beats[activeIndex] : null;
  const hookBeat = beats[0] || null;
  const accent = beat?.accent || '#FFD447';
  const revealFrame = beat ? frame - Math.round(Number(beat.revealAt || 0) * fps) : frame;
  const reveal = spring({fps, frame: Math.max(0, revealFrame), config: {damping: 17, stiffness: 145, mass: .72}});
  const nextRevealAt = activeIndex >= 0 && activeIndex + 1 < beats.length
    ? Number(beats[activeIndex + 1].revealAt || durationInFrames / fps)
    : Number(authoredFinalStart ?? dialogue[dialogue.length - 1]?.start ?? durationInFrames / fps - 5.5);
  const currentRevealAt = Number(beat?.revealAt || 0);
  const localSeconds = Math.max(0, second - currentRevealAt);
  const beatDuration = Math.max(.5, nextRevealAt - currentRevealAt);
  // Keep a composed picture visible until the next beat replaces it. Fading the
  // outgoing scene to empty frames made both the illustration and subtitle feel
  // like they were blinking at every narration boundary.
  const pictureProgress = reveal;
  const hookIn = spring({fps, frame, config: {damping: 18, stiffness: 165, mass: .68}});
  const finalStart = Math.max(0, Math.round(Number(authoredFinalStart ?? dialogue[dialogue.length - 1]?.start ?? durationInFrames / fps - 5.5) * fps));
  const final = spring({fps, frame: frame - finalStart, config: {damping: 17, stiffness: 140, mass: .76}});
  const finalActive = frame >= finalStart;
  const progress = beats.length ? Math.max(0, activeIndex + 1) / beats.length : 0;
  const legacyWinningStyle = styleVersion === 'winning-reel-39-v1' || styleVersion === 'illustrated-winning-reel-v2';
  const editorialStyle = styleVersion === 'editorial-explainer-v3' || styleVersion === 'presenter-explainer-v1';
  const headlineText = beat?.title || hook;
  const editorialHeadlineSize = String(headlineText).length > 52 ? 59 : String(headlineText).length > 39 ? 65 : 72;
  return <AbsoluteFill style={{fontFamily: 'Arial Black, Arial, Helvetica, sans-serif', color: '#fff', overflow: 'hidden'}}>
    {editorialStyle ? <EditorialExplainerBackdrop accent={accent}/> : legacyWinningStyle ? <WinningReelBackdrop accent={accent}/> : <InfographicBackdrop accent={accent}/>} 
    <div style={{position: 'absolute', left: 42, top: 45, zIndex: 8, fontSize: 17, fontWeight: 900, letterSpacing: '.06em', textShadow: '0 2px 8px rgba(0,0,0,.45)'}}>{watermark}</div>
    <div style={{position: 'absolute', right: 42, top: 45, zIndex: 8, fontSize: 15, fontWeight: 800, opacity: .72}}>{editorialStyle ? 'VISUAL EXPLAINER' : legacyWinningStyle ? 'PATTERN TEST · 39S' : 'INFO · 9:16'}</div>
    <div style={{position: 'absolute', left: 60, right: 60, top: editorialStyle ? 104 : legacyWinningStyle ? 92 : 108, zIndex: 5, textAlign: 'center', opacity: finalActive ? 1 - final : 1}}>
      <div style={{fontSize: 31, lineHeight: 1, fontWeight: 950, letterSpacing: '.02em', color: '#fff', textShadow: '0 4px 12px rgba(0,0,0,.4)', transform: `translateY(${(1 - (beat ? reveal : hookIn)) * -22}px)`}}>{beat?.kicker || 'WAJIB TAHU'}</div>
      <div style={{display: 'inline-block', maxWidth: '100%', boxSizing: 'border-box', overflowWrap: 'anywhere', marginTop: 12, padding: legacyWinningStyle ? '16px 22px 20px' : 0, borderRadius: legacyWinningStyle ? 18 : 0, background: legacyWinningStyle ? 'rgba(5,8,15,.88)' : 'transparent', fontSize: editorialStyle ? editorialHeadlineSize : beat ? 72 : legacyWinningStyle ? 54 : 66, lineHeight: .98, fontWeight: 950, letterSpacing: '-.045em', color: beat ? accent : '#FFD447', WebkitTextStroke: '4px rgba(18,25,55,.9)', paintOrder: 'stroke fill', textTransform: 'uppercase', boxShadow: legacyWinningStyle ? `0 12px 0 ${accent}` : 'none', transform: `scale(${.93 + (beat ? reveal : hookIn) * .07})`}}>{headlineText}</div>
      <div style={{width: 310, height: 8, margin: '25px auto 0', borderRadius: 99, background: 'rgba(255,255,255,.14)', overflow: 'hidden'}}><div style={{height: '100%', width: `${Math.max(7, progress * 100)}%`, borderRadius: 99, background: accent, boxShadow: `0 0 20px ${accent}`}}/></div>
    </div>
    <div style={{position: 'absolute', left: 45, right: 45, top: editorialStyle ? 365 : legacyWinningStyle ? 390 : 410, height: editorialStyle ? 990 : legacyWinningStyle ? 870 : 900, display: 'grid', placeItems: 'center', opacity: finalActive ? 1 - final : beat ? (legacyWinningStyle ? .96 : 1) : .35, transform: `${legacyWinningStyle ? 'scale(.88)' : 'scale(1)'} translateY(${(1-pictureProgress)*28}px)`, transformOrigin: '50% 48%'}}>
      {beat ? <InfographicGraphic key={beat.id || activeIndex} beat={beat} progress={pictureProgress} localSeconds={localSeconds} beatDuration={beatDuration}/> : hookBeat ? <InfographicGraphic beat={hookBeat} progress={hookIn} localSeconds={second} beatDuration={Number(hookBeat.revealAt || 4.4)}/> : <ConceptGraphic accent="#FFD447" progress={hookIn} subject={title}/>} 
    </div>
    <small style={{position: 'absolute', left: 65, right: 65, bottom: 68, zIndex: 7, textAlign: 'center', fontSize: 16, opacity: .66}}>{sourceNote}</small>
    {finalActive ? <AbsoluteFill style={{zIndex: 20, display: 'grid', placeItems: 'center', padding: 70, background: `rgba(22,30,72,${.35 + final * .58})`}}>
      <div style={{width: '100%', padding: '75px 45px 58px', borderRadius: 46, background: 'linear-gradient(150deg,#FFD447,#FFB62E)', color: '#1D2542', border: '7px solid #1B213B', boxShadow: '0 38px 95px rgba(0,0,0,.36)', textAlign: 'center', opacity: final, transform: `translateY(${(1 - final) * 90}px) scale(${.8 + final * .2}) rotate(${(1 - final) * -3}deg)`}}>
        <div style={{fontSize: 25, fontWeight: 950, letterSpacing: '.08em'}}>SEBELUM SELESAI</div>
        <div style={{marginTop: 18, fontSize: 78, lineHeight: .96, fontWeight: 950, letterSpacing: '-.055em'}}>{payoff}</div>
        <div style={{display: 'inline-block', marginTop: 38, padding: '18px 30px', borderRadius: 18, color: '#fff', background: '#1D2542', fontSize: 26, fontWeight: 950}}>{footer}</div>
      </div>
    </AbsoluteFill> : null}
    <MidVideoEngagement config={midCta}/>
    <StableDialogueCaption dialogue={dialogue} palette="infographic" bottom={218}/>
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
