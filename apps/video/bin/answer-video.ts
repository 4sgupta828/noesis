// Self-contained bridge CLI: {question, answer} JSON → a narrated explainer mp4, spoken as an
// experienced physician giving calm, grounded guidance. No cross-repo dependency, no DB.
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

/** Frame the Q&A as material a physician-narrator turns into spoken guidance. The doctor
 *  PERSONA lives in the tone + voice instructions; the material is the grounded content. */
function physicianMaterial(question: string, answer: string): string {
  return [
    `PATIENT QUESTION: ${question}`,
    ``,
    `EVIDENCE-BASED ANSWER (the ONLY facts to convey — do not add medical claims beyond these):`,
    answer,
    ``,
    `Turn this into guidance an experienced physician would give a patient: explain what the`,
    `evidence says in plain, reassuring language, what it means for them, and sensible next`,
    `steps (including "discuss with your own doctor"). Do not invent statistics, drugs, doses,`,
    `or outcomes that are not in the answer above.`,
  ].join('\n');
}

async function main() {
  const { question, answer, title } = readInput();
  const video = await renderAnswerVideo({
    material: physicianMaterial(question, answer),
    title: title || question.slice(0, 80),
    tone: 'an experienced, warm physician giving calm, clear, reassuring guidance to a patient',
    voice: 'onyx',
    voiceInstructions:
      'Speak as a seasoned, empathetic doctor talking directly to a patient: measured, warm, '
      + 'clear and unhurried. Reassuring but honest; never alarmist, never salesy.',
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
