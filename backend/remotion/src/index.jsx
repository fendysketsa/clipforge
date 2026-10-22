import React from 'react';
import {
  AbsoluteFill,
  Composition,
  Img,
  OffthreadVideo,
  Sequence,
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
    component={Story}
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
