# Answer-video add-on

Turns a delivered `{question, answer}` into a ~60-second **narrated explainer mp4**, spoken
as an experienced physician giving calm, grounded guidance. It is a **completely separate,
flag-gated add-on** with **no cross-repo dependency** — the whole generator lives in-repo at
`apps/video/`. It never touches the kernel research core, retrieval, or providers; the research
path produces answers identically whether the add-on is present or not.

## Shape (all in-repo)

```
apps/web/index.html            "▶ Generate guidance video" button (only when video_enabled)
      │  POST /video/generate {question, answer, title?}
      ▼
apps/api/video.py              separate APIRouter, mounted ONLY when NOESIS_VIDEO_ENABLED=true
      │  async subprocess (asyncio.create_subprocess_exec), stdin=JSON, env passed through
      ▼
apps/video/bin/answer-video.ts self-contained Node/TS generator (run via the app's own tsx)
      │   src/render.ts   material text → LLM storyboard → per-scene canvas frames + OpenAI TTS
      │   src/visuals.ts  @napi-rs/canvas infographics (9 scene types, animated)
      │   src/llm.ts      Anthropic structured-output storyboard (env: NOESIS_VIDEO_MODEL)
      │   src/tts.ts      OpenAI text-to-speech voiceover
      │   → ffmpeg assembles per-scene clips into an mp4
      ▼
apps/video/out/<hex>.mp4       → served back via GET /video/file/<name>
```

No database, no external repo, no shared state. The physician **persona** lives entirely in
`bin/answer-video.ts` (tone + TTS voice instructions + material framing); the content conveyed
is strictly the delivered answer — the generator is told not to invent drugs, doses,
statistics, or outcomes beyond the answer text.

## One-time setup

The generator is a small Node package with its own deps (installed once, gitignored):

```bash
cd apps/video && npm install     # @napi-rs/canvas, openai, @anthropic-ai/sdk, zod, tsx
```

Also needs `ffmpeg`/`ffprobe` on PATH.

## Enabling it

Default **OFF** (Rule 20). It spends OpenAI/Anthropic credits per video (storyboard LLM + TTS),
so it is opt-in and never on the answer path.

```bash
export NOESIS_VIDEO_ENABLED=true          # mount the /video router + show the UI button
# optional overrides:
# NOESIS_VIDEO_DIR    (default <repo>/apps/video)
# NOESIS_VIDEO_TSX    (default <video_dir>/node_modules/.bin/tsx)
# NOESIS_VIDEO_MODEL  (storyboard model, default claude-opus-4-8)

# generation credentials (already in .env.medical, passed through to the subprocess):
OPENAI_API_KEY=...      # TTS voiceover
ANTHROPIC_API_KEY=...   # storyboard LLM
```

`scripts/serve.sh` sources `.env.medical`, which now sets `NOESIS_VIDEO_ENABLED=true`.

With the flag OFF: `/config` reports `video_enabled: false`, the UI shows no button, and
`/video/*` routes are absent (404) — a true no-op.

## API

| Route | Behaviour |
|-------|-----------|
| `POST /video/generate` | `{question, answer, title?}` → `{job_id, status:"running"}`; runs the generator in the background (~2 min). |
| `GET /video/status/{job_id}` | `{status: running\|done\|error, filename, title, duration_sec, error}`. |
| `GET /video/file/{filename}` | streams the mp4 from `apps/video/out/` (basename-only + fixed dir + `.mp4` guard → no path traversal). |

Jobs are tracked in-process (node-local); a multi-node deployment would back them with a table.

## Generator CLI (standalone)

```bash
cd apps/video
echo '{"question":"...","answer":"...","title":"..."}' | node_modules/.bin/tsx bin/answer-video.ts
# → last stdout line: {"filePath","filename","durationSec","title"}
```

## Verified

- Self-contained generator → real 68s h264+aac mp4 (`apps/video`, live credits), zero
  novelfusion involvement.
- `apps/video` typechecks (`tsc --noEmit`).
- API mounts only when flag ON; OFF is a no-op (config false, routes 404); path-traversal guarded.
- Full HTTP flow (generate → poll → serve): `POST /video/generate` → `done` →
  `GET /video/file/…` returns `200 video/mp4`, a valid mp4.
