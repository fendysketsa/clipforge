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
      opacity: .28,
      mixBlendMode: 'screen',
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
  const length = Math.max(4, Math.round(fps * .38));
  if (frame > length) return null;
  const p = interpolate(frame, [0, length], [0, 1], clamp);
  const accent = design.accentColor || '#65B7FF';
  const type = design.transition || 'directional_wipe';
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
    filter: 'saturate(1.05) contrast(1.035)',
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
      <TransitionOverlay design={design}/>
    </AbsoluteFill>
  );
};

const Caption = ({scene}) => {
  const frame = useCurrentFrame();
  const {fps, height, width} = useVideoConfig();
  if (!scene?.narration) return null;
  const words = scene.narration.trim().split(/\s+/).filter(Boolean);
  const localFrame = Math.max(0, frame - Math.round(scene.start * fps));
  const sceneFrames = Math.max(1, Math.round(scene.duration * fps));
  const active = Math.min(words.length - 1, Math.floor((localFrame / sceneFrames) * words.length));
  const portrait = height > width;
  const phraseSize = portrait ? 7 : 10;
  const phraseStart = Math.floor(active / phraseSize) * phraseSize;
  const phrase = words.slice(phraseStart, phraseStart + phraseSize);
  const phraseStartFrame = Math.floor(sceneFrames * phraseStart / Math.max(1, words.length));
  const phraseReveal = spring({
    fps,
    frame: Math.max(0, localFrame - phraseStartFrame),
    config: {damping: 20, stiffness: 170, mass: .65},
  });
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
      opacity: phraseReveal,
      transform: `translateY(${(1 - phraseReveal) * 18}px)`,
    }}>
      {phrase.map((word, index) => {
        const absoluteIndex = phraseStart + index;
        return (
          <span key={`${absoluteIndex}-${word}`} style={{
            color: absoluteIndex === active ? '#FFD54A' : '#fff',
            display: 'inline-block',
            marginRight: '.26em',
            transform: absoluteIndex === active ? 'scale(1.045)' : 'scale(1)',
          }}>{word}</span>
        );
      })}
    </div>
  );
};

const Story = ({shots = [], scenes = [], watermark = '@ryuundy', captionsEnabled = true}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const activeScene = scenes.find((scene) => {
    const start = Math.round(scene.start * fps);
    const end = start + Math.round(scene.duration * fps);
    return frame >= start && frame < end;
  });
  return (
    <AbsoluteFill style={{backgroundColor: '#05070b'}}>
      {shots.map((shot) => (
        <Sequence
          key={shot.id}
          from={Math.round(shot.start * fps)}
          durationInFrames={Math.max(1, Math.round(shot.duration * fps))}
          premountFor={Math.round(fps * .5)}
        >
          <Shot shot={shot}/>
        </Sequence>
      ))}
      {captionsEnabled ? <Caption scene={activeScene}/> : null}
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
  const localFrame = Math.max(0, frame - Math.round(Number(active.start || 0) * fps));
  const durationFrames = Math.max(1, Math.round(Number(active.duration || 0) * fps));
  const reveal = spring({fps, frame: localFrame, config: {damping: 20, stiffness: 170, mass: .68}});
  const exit = interpolate(localFrame, [Math.max(0, durationFrames - 7), durationFrames], [1, 0], clamp);
  const words = String(active.text || '').split(/\s+/).filter(Boolean);
  const activeWord = Math.min(
    Math.max(0, words.length - 1),
    Math.floor((localFrame / durationFrames) * Math.max(1, words.length)),
  );
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
      opacity: reveal * exit,
      transform: `translateY(${(1 - reveal) * 34 + (1 - exit) * 12}px) scale(${.965 + reveal * .035})`,
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
            color: index === activeWord ? accent : '#F7FFFC',
            textShadow: index === activeWord ? `0 0 20px ${accent}55` : 'none',
            transform: index === activeWord ? 'translateY(-1px) scale(1.025)' : 'none',
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
  const finalStart = Math.max(0, durationInFrames - Math.round(4.3 * fps));
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

const ClipForgeComposition = (props) => props.template === 'ranking'
  ? <RankingVideo {...props}/>
  : <Story {...props}/>;

const defaultProps = {
  width: 1080,
  height: 1920,
  fps: 30,
  durationSeconds: 10,
  shots: [],
  scenes: [],
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
