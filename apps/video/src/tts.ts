// OpenAI text-to-speech chokepoint for scene voiceover. Self-contained (no config module).

import OpenAI from 'openai';

// gpt-4o-mini-tts adds warmer, steerable voices (ash/ballad/coral/sage/verse) and, unlike
// tts-1/tts-1-hd, actually HONORS `instructions` (tone/pacing/warmth).
export type TtsVoice =
  | 'alloy' | 'echo' | 'fable' | 'onyx' | 'nova' | 'shimmer'
  | 'ash' | 'ballad' | 'coral' | 'sage' | 'verse';
export type TtsModel = 'tts-1' | 'tts-1-hd' | 'gpt-4o-mini-tts';

let client: OpenAI | null = null;
function getOpenAI(): OpenAI {
  if (!client) {
    if (!process.env.OPENAI_API_KEY) throw new Error('No OPENAI_API_KEY — TTS voiceover needs it.');
    client = new OpenAI();
  }
  return client;
}

export interface SpeechOpts {
  voice?: TtsVoice;
  model?: TtsModel;
  /** Steerable delivery direction — ONLY honored by gpt-4o-mini-tts. */
  instructions?: string;
  /** Playback speed 0.25–4.0. */
  speed?: number;
}

/** Synthesize voiceover from text via OpenAI TTS. Returns mp3 bytes. Fails loudly. */
export async function synthesizeSpeech(text: string, opts: SpeechOpts = {}): Promise<Buffer> {
  const model: TtsModel = opts.model ?? 'tts-1';
  const voice: TtsVoice = opts.voice ?? 'alloy';
  const speed = Math.max(0.25, Math.min(4, opts.speed ?? 1));
  const req: Record<string, unknown> = { model, voice, input: text, response_format: 'mp3', speed };
  if (model === 'gpt-4o-mini-tts' && opts.instructions) req.instructions = opts.instructions;
  const res = await getOpenAI().audio.speech.create(req as unknown as Parameters<OpenAI['audio']['speech']['create']>[0]);
  return Buffer.from(await res.arrayBuffer());
}
