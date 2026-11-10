"""Local presentation proof from an existing render, never an upload job."""
from dataclasses import fields, replace
import hashlib
import json
import os
from pathlib import Path

for name in ('SHORTS_ADAPTIVE_COLOR_ENABLED','SHORTS_CINEMATIC_FINISH_ENABLED',
             'SHORTS_CINEMATIC_SMOKE_ENABLED','SHORTS_EVIDENCE_RESEARCH_ENABLED',
             'CTA_VOICEOVER_ENABLED','SHORTS_BACKGROUND_MUSIC_ENABLED',
             'SHORTS_PROCEDURAL_MUSIC_ENABLED','SHORTS_SCHEDULED_SOCIAL_CARD_ENABLED',
             'SHORTS_SCHEDULED_REACTION_AVATAR_ENABLED'):
    os.environ[name]='false'
os.environ.update(CLIPFORGE_CRON_DIRECTOR_EFFECTS='true',QURAN_OUTRO_ENABLED='true',
    SHORTS_RENDER_QC_ENABLED='true',SHORTS_SCHEDULED_SUBSCRIBE_PULSE_ENABLED='true',
    FENDY_CLIPPER_CPU_THREADS_PER_JOB='2')

import clipper
import cron_short_director

folder=Path('reports/cron-short-presentation-20261110')
work=folder/'roblox'
original=json.loads((work/'original-sidecar.json').read_text())
candidate=clipper.ClipCandidate(**{item.name:original[item.name] for item in fields(clipper.ClipCandidate) if item.name in original})
candidate=replace(candidate,start=0.,end=float(original['duration']))
rows=[clipper.TranscriptSegment(**row) for row in json.loads((work/'transcript.json').read_text())]
focus=cron_short_director.measure_focus(work/'source-context.mp4',0,candidate.end)
(folder/'focus-analysis.json').write_text(json.dumps(focus,indent=2)+'\n')
output=clipper.export_clip(work/'source-context.mp4',candidate,rows,folder/'preview',True,'person',
    caption=clipper.CaptionStyle(font_size=9),generate_assets=False,enforce_size=False,
    base_name_override='cron-gameplay-preview',source_transcript=rows,
    # The derived input already contains the original two source accents.
    # Production cron keeps its normal 1-2 accent budget.
    cron_effect_budget=0)
before=json.loads((folder/'source-before.json').read_text())
source=Path(before['path']);stat=source.stat()
assert (stat.st_size,stat.st_mtime_ns)==(before['size'],before['mtime_ns'])
assert hashlib.sha256(source.read_bytes()).hexdigest()==before['sha256']
sidecar=json.loads(output.with_suffix('.json').read_text())
sidecar.update(preview_only=True,manual_publication_review=True,
    source_provenance=original.get('source_provenance'),
    derived_from_existing_render={'path':before['path'],'sha256':before['sha256']})
output.with_suffix('.json').write_text(json.dumps(sidecar,ensure_ascii=False,indent=2)+'\n')
proof=dict(preview_only=True,upload_queued=False,publication_review_required=True,
    source_is_previously_rendered_derivative=True,source_rights=original.get('source_provenance'),
    original_unchanged=True,output=str(output),layout=sidecar['portrait_framing'],
    opening=sidecar['cron_short_presentation']['opening'],
    original_duration=float(original['output_duration_seconds']),new_duration=sidecar['output_duration_seconds'],
    retained_source_duration=float(original['duration']),quran_outro=sidecar['quran_outro'],
    render_quality_qc=sidecar['render_quality_qc'])
(folder/'preview-verification.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'output':str(output),'layout':sidecar['layout'],'opening':proof['opening'],'original_unchanged':True},ensure_ascii=False))
