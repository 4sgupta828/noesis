// Self-contained answer-video generator: material TEXT →
//   1. an LLM STORYBOARD (scenes: narration + on-screen visual),
//   2. per scene a canvas INFOGRAPHIC (visuals.ts) + an OpenAI TTS VOICEOVER,
//   3. ffmpeg assembly (per-scene fades, then concat) → a final mp4.
// No DB, no cross-repo dependency. Synthetic by design (generated visuals + AI voice).
//
// ffmpeg via execFile with argument ARRAYS (never a shell string); all files are
// process-generated random paths under our own dirs; TTS goes through the OpenAI chokepoint.

import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { randomBytes } from 'node:crypto';
import { z } from 'zod/v4';
import { structured } from './llm.js';
import { synthesizeSpeech, type TtsVoice, type TtsModel } from './tts.js';
import { renderSceneFrame, SCENE_ANIM_SEC } from './visuals.js';
import type { ClipFormat, StoryboardScene, FusionTheme, AnswerVideo } from './types.js';

const exec = promisify(execFile);
const DIMS: Record<ClipFormat, [number, number]> = { '16:9': [1280, 720], '9:16': [720, 1280], '1:1': [1080, 1080] };
// Output dir: default <app>/out, overridable so the API can point it wherever it serves from.
const OUT_DIR = process.env.NOESIS_VIDEO_OUT_DIR
  || path.join(path.dirname(path.dirname(new URL(import.meta.url).pathname)), 'out');
const FPS = 30;
const TAIL_SEC = 0.8;   // scene tail after narration; MUST exceed XFADE so narrations never overlap
const MIN_SCENE = 2.5;
const MAX_SCENE = 60;   // effectively no cap — never TRUNCATE narration (truncation → overlap → double voice)
const MAX_INPUT_CHARS = 14000;

export class VideoError extends Error {
  code: string;
  constructor(code: string, message: string) { super(message); this.code = code; }
}

const SceneSchema = z.object({
  narration: z.string().describe('what the VOICEOVER says for this scene — 1–3 natural spoken sentences. Heard, not shown.'),
  visual: z.enum(['title', 'bullets', 'stat', 'quote', 'chart', 'comparison', 'timeline', 'bignumbers', 'donut']).describe('what SHOWS on screen — pick the type that best fits the content'),
  title: z.string().describe('short on-screen headline (a few words)'),
  subtitle: z.string().optional().describe('title scenes only: one supporting line'),
  bullets: z.array(z.string()).optional().describe('bullets scenes: 2–5 SHORT phrases (not sentences)'),
  stat: z.object({ value: z.string(), label: z.string() }).optional().describe('stat scenes: ONE big number/value + its label'),
  quote: z.object({ text: z.string(), attribution: z.string().optional() }).optional().describe('quote scenes: a punchy line + who said it'),
  chart: z.object({ unit: z.string().optional(), bars: z.array(z.object({ label: z.string(), value: z.number() })) }).optional().describe('chart scenes: 2–6 labeled bars'),
  comparison: z.object({ left: z.object({ heading: z.string(), items: z.array(z.string()) }), right: z.object({ heading: z.string(), items: z.array(z.string()) }) }).optional().describe('comparison scenes: two sides; 1–4 items each'),
  timeline: z.object({ steps: z.array(z.object({ label: z.string(), detail: z.string().optional() })) }).optional().describe('timeline scenes: an ordered sequence of 2–5 steps'),
  bignumbers: z.object({ items: z.array(z.object({ value: z.string(), label: z.string() })) }).optional().describe('bignumbers scenes: 2–4 headline stats in a grid'),
  donut: z.object({ value: z.number(), label: z.string(), unit: z.string().optional() }).optional().describe('donut scenes: ONE percentage (0–100) as a ring + label'),
});
const StoryboardSchema = z.object({
  title: z.string().describe('the video title'),
  scenes: z.array(SceneSchema).describe('4–9 scenes'),
});

const SYSTEM = `You are a world-class video director turning source material into a punchy, narrated explainer STORYBOARD (a sharp 45–90s explainer). Output scenes; each has VOICEOVER narration (heard) and an on-screen VISUAL (seen) — they complement each other, they are not the same text.

The on-screen visual TYPES available — use a RICH VARIETY, pick each for its content:
- title: open/close hero — a headline + one supporting line.
- bullets: 2–5 SHORT key phrases (not sentences).
- stat: ONE big number that lands (e.g. "95%").
- bignumbers: 2–4 headline numbers side by side.
- chart: 2–6 comparable values as bars.
- donut: ONE percentage (0–100) as a ring.
- comparison: two sides — old vs new, before/after, benefits vs risks.
- timeline: an ordered sequence of 2–5 steps.
- quote: a punchy line + who said it.

Rules:
- STATE THE TOPIC UP FRONT. The opening 'title' scene must clearly say what this briefing is about — name the specific question/subject in the first sentence, so the viewer immediately knows the topic. Do not open with a vague hook.
- END WITH A CLEAR CONCLUSION. The FINAL scene must be a 'title' that delivers the bottom-line takeaway — what to conclude from the evidence and its limitations. Never end mid-topic or trail off.
- The narration is ONE CONTINUOUS briefing read start-to-finish: write it so each scene's narration flows naturally into the next with light connective phrasing (e.g. "First… ", "The evidence also… ", "Taken together… "). It must read as a single cohesive spoken piece, NOT disconnected fragments — this keeps the voiceover smooth across scene changes.
- Build the arc: topic → substance scenes → conclusion. VARY the visual types across the arc; don't repeat one type back-to-back.
- Narration is spoken: natural, warm, and clear — engaged but precise. On-screen text is terse: headlines and keywords, never paragraphs.
- KEEP ON-SCREEN TEXT SHORT so it fits the frame (the narration carries the detail, the slide carries the gist):
  · title: ≤ 8 words. · bullets: ≤ 5 items, each ≤ 9 words (a phrase, not a sentence).
  · comparison: heading ≤ 3 words; ≤ 3 items per side, each ≤ 7 words. · timeline: step label ≤ 5 words.
  · stat/donut label ≤ 12 words; bignumbers label ≤ 4 words. Put full explanation in the NARRATION, not the slide.
- Ground it in the source material — use its real claims, numbers, and language. Do NOT invent statistics; only use stat/chart/donut/bignumbers values the material actually supports. If there are no real numbers, prefer bullets/comparison/timeline/quote over inventing figures.
- 5–8 scenes. Every scene must have narration and a title, plus the field for its chosen visual type.`;

export interface RenderAnswerVideoOpts {
  material: string;
  title?: string;
  voice?: TtsVoice;
  voiceModel?: TtsModel;
  voiceInstructions?: string;
  speed?: number;
  theme?: FusionTheme;
  format?: ClipFormat;
  captions?: boolean;
  tone?: string;
}

const escFilter = (p: string) => p.replace(/\\/g, '\\\\').replace(/:/g, '\\:').replace(/'/g, "\\'");
const CAPTION_STYLE = "force_style='Alignment=2,FontSize=13,MarginV=44,MarginL=60,MarginR=60,PrimaryColour=&H00FFFFFF,OutlineColour=&HCC000000,BorderStyle=1,Outline=2,Shadow=1'";

const srtTime = (s: number) => {
  const hh = Math.floor(s / 3600), mm = Math.floor((s % 3600) / 60), ss = Math.floor(s % 60), ms = Math.round((s - Math.floor(s)) * 1000);
  const p = (n: number, l = 2) => String(n).padStart(l, '0');
  return `${p(hh)}:${p(mm)}:${p(ss)},${p(ms, 3)}`;
};

async function probeDuration(file: string): Promise<number> {
  const { stdout } = await exec('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', file]);
  return parseFloat(stdout.trim()) || 0;
}

/** Generate an answer video from raw material text. Throws VideoError on bad input;
 *  OpenAI/ffmpeg errors propagate (the caller reports a failed render). */
export async function renderAnswerVideo(opts: RenderAnswerVideoOpts): Promise<AnswerVideo> {
  const voice: TtsVoice = opts.voice ?? 'onyx';
  const theme: FusionTheme = opts.theme ?? 'midnight';
  const format: ClipFormat = opts.format ?? '16:9';
  const captions = opts.captions ?? true;
  const [w, h] = DIMS[format];
  const material = (opts.material || '').slice(0, MAX_INPUT_CHARS);
  const defaultTitle = (opts.title ?? 'Untitled').slice(0, 80);
  if (!material.trim()) throw new VideoError('no_material', 'No material to storyboard.');

  // 1. Storyboard.
  const toneLine = opts.tone ? `\n\nTONE: make the narration and framing feel ${opts.tone}.` : '';
  const board = await structured({
    stage: 'answer-video-storyboard',
    system: SYSTEM,
    user: `Create a storyboard from this material:\n\n${material}${toneLine}`,
    schema: StoryboardSchema,
    maxTokens: 7000,
  });
  const scenes: StoryboardScene[] = board.scenes;
  if (scenes.length === 0) throw new VideoError('empty_storyboard', 'The storyboard came back empty.');

  fs.mkdirSync(OUT_DIR, { recursive: true });
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'noesis-vid-'));
  try {
    // 2. Per scene: infographic frames + TTS voiceover → a VIDEO-ONLY scene clip. The
    // narration is assembled separately into one continuous track (below) so the voiceover
    // never fades/swells at scene changes.
    const sceneFiles: string[] = [];
    const mp3Files: string[] = [];
    const durations: number[] = [];
    const speechDurs: number[] = [];
    for (let i = 0; i < scenes.length; i++) {
      const scene = scenes[i]!;
      const isFirst = i === 0, isLast = i === scenes.length - 1;
      const mp3 = path.join(tmp, `s${i}.mp3`);
      fs.writeFileSync(mp3, await synthesizeSpeech(scene.narration, { voice, model: opts.voiceModel, instructions: opts.voiceInstructions, speed: opts.speed }));
      mp3Files.push(mp3);
      const speech = await probeDuration(mp3);
      speechDurs.push(speech);
      const dur = Math.min(MAX_SCENE, Math.max(MIN_SCENE, speech + TAIL_SEC));
      durations.push(dur);

      const frameDir = path.join(tmp, `s${i}`);
      fs.mkdirSync(frameDir, { recursive: true });
      const sceneCtx = { width: w, height: h, index: i, total: scenes.length, theme, brand: 'Noesis' } as const;
      const totalFrames = Math.round(dur * FPS);
      const animFrames = Math.min(totalFrames - 1, Math.round(SCENE_ANIM_SEC * FPS));
      for (let f = 0; f <= animFrames; f++) {
        fs.writeFileSync(path.join(frameDir, `f_${String(f).padStart(5, '0')}.png`), renderSceneFrame(scene, sceneCtx, f / FPS));
      }
      const holdSec = Math.max(0, dur - (animFrames + 1) / FPS);
      const fadeOut = Math.max(0, dur - 0.4);

      // NO per-scene dip-to-black between scenes — crossfades (xfade) join them smoothly.
      // Keep only a fade-IN on the first scene (intro) and fade-OUT on the last (outro).
      let vf = `[0:v]fps=${FPS},tpad=stop_mode=clone:stop_duration=${holdSec.toFixed(3)}`;
      if (isFirst) vf += `,fade=t=in:st=0:d=0.4`;
      if (isLast) vf += `,fade=t=out:st=${fadeOut}:d=0.4`;
      if (captions) {
        const srt = path.join(tmp, `s${i}.srt`);
        fs.writeFileSync(srt, `1\n${srtTime(0)} --> ${srtTime(dur)}\n${scene.narration.replace(/\r?\n/g, ' ').trim()}\n`);
        vf += `,subtitles='${escFilter(srt)}':${CAPTION_STYLE}`;
      }
      vf += `,format=yuv420p[v]`;

      const clip = path.join(tmp, `s${i}.mp4`);
      await exec('ffmpeg', [
        '-y', '-framerate', String(FPS), '-i', path.join(frameDir, 'f_%05d.png'),
        '-filter_complex', vf,
        '-map', '[v]', '-t', String(dur),
        '-r', String(FPS), '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', clip,
      ], { maxBuffer: 1 << 27 });
      sceneFiles.push(clip);
    }

    // 3. Assemble: smooth video CROSSFADES (xfade) + one CONTINUOUS narration track. Each
    // scene's narration is placed at that scene's start time (adelay) over a shared bed and
    // mixed — so the voiceover plays gapless at full volume across scene changes (no swell/cut).
    const outName = `${randomBytes(9).toString('hex')}.mp4`;
    const outFile = path.join(OUT_DIR, outName);
    const XFADE = 0.5;   // video crossfade overlap (seconds)

    // continuous audio: narration k starts where scene k begins on the video timeline.
    const audioFile = path.join(tmp, 'vo.m4a');
    const aInputs: string[] = [];
    for (const m of mp3Files) aInputs.push('-i', m);
    const aParts: string[] = [];
    const aLabels: string[] = [];
    let startMs = 0;
    for (let k = 0; k < mp3Files.length; k++) {
      const d = Math.round(startMs);
      aParts.push(`[${k}:a]adelay=${d}|${d}[ad${k}]`);
      aLabels.push(`[ad${k}]`);
      // advance to the next narration's start. GUARD: never start before this narration has
      // fully finished (+0.2s) — otherwise two voiceovers overlap (double-voice bug).
      startMs += Math.max(durations[k]! - XFADE, speechDurs[k]! + 0.2) * 1000;
    }
    const aFilter = mp3Files.length === 1
      ? '[0:a]anull[a]'
      : `${aParts.join(';')};${aLabels.join('')}amix=inputs=${mp3Files.length}:normalize=0:dropout_transition=0[a]`;
    await exec('ffmpeg', ['-y', ...aInputs, '-filter_complex', aFilter, '-map', '[a]',
      '-c:a', 'aac', '-ar', '44100', audioFile], { maxBuffer: 1 << 27 });

    // video track (xfade), then mux the continuous narration over it
    const videoOnly = sceneFiles.length === 1 ? sceneFiles[0]! : path.join(tmp, 'video.mp4');
    if (sceneFiles.length > 1) {
      const inputs: string[] = [];
      for (const f of sceneFiles) inputs.push('-i', f);
      const vparts: string[] = [];
      let vlabel = '[0:v]';
      let prevLen = durations[0]!;
      for (let k = 1; k < sceneFiles.length; k++) {
        const offset = Math.max(0, prevLen - XFADE);
        const vout = k === sceneFiles.length - 1 ? '[v]' : `[v${k}]`;
        vparts.push(`${vlabel}[${k}:v]xfade=transition=fade:duration=${XFADE}:offset=${offset.toFixed(3)}${vout}`);
        vlabel = vout;
        prevLen = prevLen + durations[k]! - XFADE;
      }
      await exec('ffmpeg', ['-y', ...inputs, '-filter_complex', vparts.join(';'), '-map', '[v]',
        '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', videoOnly], { maxBuffer: 1 << 27 });
    }
    await exec('ffmpeg', ['-y', '-i', videoOnly, '-i', audioFile, '-map', '0:v', '-map', '1:a',
      '-c:v', 'copy', '-c:a', 'aac', '-shortest', '-movflags', '+faststart', outFile], { maxBuffer: 1 << 27 });

    const durationSec = await probeDuration(outFile);
    const size = fs.statSync(outFile).size;
    return {
      title: board.title || defaultTitle, filename: outName,
      filePath: path.relative(process.cwd(), outFile), durationSec, size, mime: 'video/mp4',
    };
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
}
