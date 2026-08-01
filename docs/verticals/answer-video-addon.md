# Answer-video add-on

Turns a delivered `{question, answer}` into a ~60-second **narrated explainer mp4**, spoken
as an experienced physician giving calm, grounded guidance. It is a **completely separate,
flag-gated add-on** — it never touches the kernel research core, retrieval, or providers. The
research path produces answers identically whether the add-on is present or not.

## Shape

```
apps/web/index.html            "▶ Generate guidance video" button (only when video_enabled)
      │  POST /video/generate {question, answer, title?}
      ▼
apps/api/video.py              separate APIRouter, mounted ONLY when NOESIS_VIDEO_ENABLED=true
      │  async subprocess (asyncio.create_subprocess_exec), stdin=JSON
      ▼
~/novelfusion/bin/answer-video.ts   standalone bridge (tsx) — raw-text path into NovelFusion's
      │                              EXPERIMENTAL renderFusionVideo(): storyboard (LLM) → canvas
      │                              infographics + OpenAI TTS voiceover → ffmpeg mp4
      ▼
~/novelfusion/data/fusion/<hex>.mp4  → served back via GET /video/file/<name>
```

The physician **persona** lives entirely in the bridge (tone + TTS voice instructions +
material framing); the content conveyed is strictly the delivered answer — the bridge is told
not to invent drugs, doses, statistics, or outcomes beyond the answer text.

## Enabling it

Default **OFF** (Rule 20). It spends OpenAI/Anthropic credits per video (storyboard LLM + TTS),
so it is opt-in and never on the answer path.

```bash
# noesis API
export NOESIS_VIDEO_ENABLED=true          # mount the /video router + show the UI button
export NOESIS_VIDEO_NF_DIR=~/novelfusion  # default; the NovelFusion repo
# NOESIS_VIDEO_TSX defaults to <nf>/node_modules/.bin/tsx

# NovelFusion (already set in ~/novelfusion/.env)
NF_FLAG_FUSION_VIDEO=true
OPENAI_API_KEY=...      # TTS voiceover (and storyboard if NF_MODEL is OpenAI)
ANTHROPIC_API_KEY=...   # storyboard LLM (NF_MODEL defaults to claude-opus-4-8)
```

With the flag OFF: `/config` reports `video_enabled: false`, the UI shows no button, and
`/video/*` routes are absent (404) — a true no-op.

## API

| Route | Behaviour |
|-------|-----------|
| `POST /video/generate` | `{question, answer, title?}` → `{job_id, status:"running"}`; runs the bridge in the background (~2 min). |
| `GET /video/status/{job_id}` | `{status: running\|done\|error, filename, title, duration_sec, error}`. |
| `GET /video/file/{filename}` | streams the mp4 (basename-only + fixed dir + `.mp4` guard → no path traversal). |

Jobs are tracked in-process (node-local); a multi-node deployment would back them with a table.

## Bridge CLI (standalone)

```bash
cd ~/novelfusion
echo '{"question":"...","answer":"...","title":"..."}' | node_modules/.bin/tsx bin/answer-video.ts
# → last stdout line: {"filePath","filename","durationSec","title","id"}
```

The only NovelFusion source change is **additive**: `renderFusionVideo` gained an `opts.material`
raw-text path (`gatherMaterial` returns it directly, skipping the DB source lookup) plus
`material?/title?/origin?` on `RenderFusionOpts`. All existing talk/moment/source paths are
unchanged.

## Verified

- Bridge → real 60s h264+aac mp4 (`tsx bin/answer-video.ts`, live credits).
- API mounts only when flag ON; OFF is a no-op (config false, routes 404); path-traversal guarded.
- Full HTTP flow (generate → poll → serve): `POST /video/generate` → `done` →
  `GET /video/file/…` returns `200 video/mp4`, a valid 63s mp4.
