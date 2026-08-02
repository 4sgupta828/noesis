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
    tone: 'a precise, analytical clinical evidence briefing delivered peer-to-peer to a physician '
      + 'or researcher — measured, authoritative, and evidence-focused (not patient-facing)',
    voice: 'onyx',
    voiceInstructions:
      'Speak as a knowledgeable clinical colleague briefing a physician or researcher: measured, '
      + 'precise, confident and analytical. Professional and peer-to-peer — no bedside reassurance, '
      + 'no talking down. Convey the evidence and its limitations crisply.',
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
