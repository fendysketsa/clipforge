# Optional images: existing assets and current-agent image generation

Image integration has two stages: the agent observes the current tools and calls them under the user's authorization; the script resolves the selection, checks the artifact, and saves it into the project. Scripts do not impersonate host tools, do not borrow another agent's login state, and do not switch image APIs automatically.

## Look at the task first, then at config

Import existing images directly with `use-image`. Code animation that needs no images skips this page. For new generation, first read the explicit preferences in the rules loaded for this run, then read this tool's config; when the user has already asked for generation, execute with the actual tool and the existing authorization, and do not ask again just to fill in config.

```sh
# S is the skill directory actually loaded for this run
python "$S/scripts/art-motion/capabilities.py" image-status
python "$S/scripts/art-motion/capabilities.py" use-image --file original.png --out <project>/images/asset.png
```

`preferences.image.mode` accepts `unconfigured/off/existing/generate`; provider is the accurate ID of the current tool or auto. `off` is the preference not to generate by default, and an explicit request in this run may override it; `policy.image_generation=deny` is a prohibition that temporary authorization flags cannot override. Save an explicit user "no" as policy, not only as mode.

When config is missing for the first time, ask only: existing assets / allow the current tool to generate / skip. `skip --capability image --scope task` writes nothing to disk; `--scope user` means enabling it manually for the long term. If the user picks it only for this run, do not store it as a long-term default. Existing voice config stays valid after upgrading; the newly added image capability remains unselected and is not granted automatically.

## Current tool snapshot

The agent reads names and schemas from the tool list already exposed in this session (or the host's official tool search), confirms the supported operations, then writes a task-scoped snapshot. It must not be inferred by scanning keys, installed skills, or agent names. If there are no tools, write `tools: []`.

```json
{
  "host": "codex",
  "session_id": "unique identifier for this task",
  "observed_at": 0,
  "tools": [{
    "id": "actual current tool ID",
    "kind": "host",
    "operations": ["generate", "edit"],
    "reference_images": true,
    "transparent_background": true,
    "cost": "subscription",
    "network": "cloud"
  }]
}
```

The example is not a capability declaration: `observed_at` must be filled with this run's Unix time, and tool features and IDs must come from this run's actual schema; the snapshot is valid for 15 minutes. host may be codex, claude-code, kimi, other; kind may be host or mcp. Billing type is subscription/paid_api/unknown/none; network is cloud/local. A subscription does not mean unlimited quota; when billing is unclear use unknown, never none.

All three hosts follow this common contract. One Codex session having image_gen does not mean every Codex product surface has it; Claude Code/Kimi may also be used if they expose a suitable MCP image tool, otherwise import existing images or deliver a note on assets still to be made. Do not invent built-in tools of the same name for these two.

## Plan → host execution → acceptance

Request JSON:

```json
{
  "prompt": "image description confirmed by the user",
  "operation": "generate",
  "references": [],
  "transparent_background": true,
  "min_width": 512,
  "min_height": 512
}
```

For image editing use edit and supply reference files; relative paths are relative to the request JSON. The script verifies that reference images decode and stores their hash; later changes invalidate the old plan.

```sh
python "$S/scripts/art-motion/capabilities.py" image-plan --request request.json \
  --host-tools host-tools.json --session this-run-id --mode generate \
  --allow-image-generation --allow-cloud --out execution-plan.json
```

Authorization flags express only the authorization the user has already given for this run. Uploading cloud reference images additionally needs `--allow-reference-upload`; an explicitly paid API needs `--allow-paid-api`; unknown billing needs `--allow-unknown-image-cost`. Long-term allowances can be stored in the corresponding policy fields. Projects can only set deny, never grant these rights. Prohibitions are handled first; when several tools are allowed and no choice can be made unambiguously it returns needs_selection — do not guess a platform.

On `host_action_required`, the agent calls the tool according to that tool's real schema; the plan is a semantic requirement, not a cross-platform parameter body. Write the receipt only after generation succeeds:

```json
{
  "status": "success",
  "plan_id": "ID from the execution plan",
  "session_id": "this run's identifier",
  "tool_id": "actual tool ID invoked",
  "output_sha256": "SHA256 of the actual output file"
}
```

Keep the actual tool-call record as evidence. The receipt is a call record supplied by the agent, not a platform signature attestation; PNG metadata alone cannot prove which model generated a file.

```sh
python "$S/scripts/art-motion/capabilities.py" accept-image --plan execution-plan.json --receipt receipt.json \
  --host-tools host-tools.json --session this-run-id --file host-output.png \
  --out <project>/images/final-asset.png --allow-image-generation --allow-cloud
```

Acceptance re-checks the current authorization, image-related config, tools, session, reference images, file hash, actual dimensions, and transparent pixels. A plan is valid for 1 hour; refresh the capability snapshot when it expires, and do not edit an old plan to pretend it is still valid. Do not overwrite when the original or a sidecar exists; static PNG/JPEG/WebP supported; Pillow required, and the tool will not install it automatically. Image content and reference identity still need visual checking; hash and dimensions cannot replace looking at the image.

After it passes, copy it into the project and write an adjacent JSON containing dimensions, transparency, SHA, tool ID, plan linkage, and `provenance: agent_reported_tool_call`. Do not cite the agent cache as the project's final asset, and do not claim a model name the server did not return as verified.

## Extension and feedback loop

When adding an image API adapter, first choose a real vendor, then implement its auth, request, output, and error protocols, and write success/failure contract tests. A URL that calls itself OpenAI-compatible does not automatically become a usable backend; this version has no generic API executor or self-installer. Existing MCP tools belong to the current agent's tool channel — execute them per their schema.

2026-10-08: P2 established the interface of selection → host action → asset acceptance. Before reusing it, read this page and the vendor's current tool docs; add tests and fix the underlying logic on repeatable failures, and write personal preferences only into private config. Voice and images are enabled separately; upgrading never widens existing authorization. Record deterministic acceptance and visual quality conclusions separately.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
