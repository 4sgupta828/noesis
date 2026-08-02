// Self-contained bridge CLI: {question, answer} JSON → a narrated explainer mp4 — a concise
// CLINICAL EVIDENCE BRIEFING for a physician / researcher audience. No cross-repo dependency, no DB.
//
//   echo '{"question":"...","answer":"...","title":"..."}' | tsx bin/answer-video.ts
//   tsx bin/answer-video.ts --file /tmp/qa.json
//
// Result JSON on the LAST stdout line. Requires OPENAI_API_KEY (TTS) + ANTHROPIC_API_KEY
// (storyboard). Env is loaded from the caller's process (the noesis API passes it through).

import 'dotenv/config';
import fs from 'node:fs';
import { renderAnswerVideo } from '../src/render.js';

function readInput(): { question: string; answer: string; title?: string } {
  const fileArg = process.argv.indexOf('--file');
  const raw = fileArg >= 0 && process.argv[fileArg + 1]
    ? fs.readFileSync(process.argv[fileArg + 1]!, 'utf8')
    : fs.readFileSync(0, 'utf8');
  const obj = JSON.parse(raw);
  if (!obj || typeof obj.question !== 'string' || typeof obj.answer !== 'string') {
    throw new Error('input must be JSON with string "question" and "answer"');
  }
  return obj;
}

/** Frame the Q&A as material for a CLINICAL EVIDENCE BRIEFING aimed at a physician /
 *  researcher audience (not a patient). The peer-to-peer persona lives in the tone + voice
 *  instructions; the material is the grounded content. */
function briefingMaterial(question: string, answer: string): string {
  return [
    `RESEARCH QUESTION: ${question}`,
    ``,
    `EVIDENCE-BASED ANSWER (the ONLY facts to convey — do not add claims beyond these):`,
    answer,
    ``,
    `Turn this into a concise CLINICAL EVIDENCE BRIEFING for a PHYSICIAN or RESEARCHER audience`,
    `(doctors doing research and analysis — NOT patients). Frame it analytically: what the`,
    `studies show, the STRENGTH and LIMITATIONS of the evidence (study design, phase, whether`,
    `outcomes are reported vs. only intended), and the implications for clinical practice or`,
    `further research. Peer-to-peer, precise and evidence-focused. Do NOT address a patient, do`,
    `NOT give individualized medical advice or bedside reassurance, and do NOT invent`,
    `statistics, drugs, doses, or outcomes beyond the answer above.`,
  ].join('\n');
}

async function main() {
  const { question, answer, title } = readInput();
  const video = await renderAnswerVideo({
    material: briefingMaterial(question, answer),
    title: title || question.slice(0, 80),
    tone: 'a warm, engaging clinical evidence briefing delivered peer-to-peer to a physician or '
      + 'researcher — knowledgeable and precise, but human and approachable (not patient-facing)',
    voice: 'sage',                    // warm, natural voice
    voiceModel: 'gpt-4o-mini-tts',    // the ONLY model that honors `voiceInstructions`
    voiceInstructions:
      'Speak as a warm, engaging senior clinical colleague briefing a peer: friendly and human, '
      + 'with genuine warmth and an even, unhurried pace — never robotic, clipped, or cold. Precise '
      + 'and credible, but relaxed and conversational, like explaining findings to a respected '
      + 'colleague over coffee. Let sentences breathe; connect ideas smoothly.',
    speed: 0.98,
    captions: false,
    format: '16:9',
    theme: 'midnight',
  });
  process.stdout.write('\n' + JSON.stringify({
    filePath: video.filePath, filename: video.filename,
    durationSec: video.durationSec, title: video.title,
  }) + '\n');
}

main().catch((e) => {
  process.stderr.write(`answer-video failed: ${e?.message || e}\n`);
  process.exit(1);
});
