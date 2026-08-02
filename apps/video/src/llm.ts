// Anthropic structured-output chokepoint for the storyboard step. Self-contained:
// model from env (NOESIS_VIDEO_MODEL, default claude-opus-4-8), no trace file, no config module.

import Anthropic from '@anthropic-ai/sdk';
import { zodOutputFormat } from '@anthropic-ai/sdk/helpers/zod';
import type { z } from 'zod/v4';

const MODEL = process.env.NOESIS_VIDEO_MODEL || 'claude-opus-4-8';

let client: Anthropic | null = null;
function getClient(): Anthropic {
  if (!client) {
    if (!process.env.ANTHROPIC_API_KEY && !process.env.ANTHROPIC_AUTH_TOKEN) {
      throw new Error('No Anthropic credentials (ANTHROPIC_API_KEY) — the storyboard step needs it.');
    }
    client = new Anthropic();
  }
  return client;
}

export interface CallOpts {
  stage: string;
  system: string;
  user: string;
  maxTokens?: number;
}

export async function structured<T extends z.ZodTypeAny>(opts: CallOpts & { schema: T }): Promise<z.infer<T>> {
  const response = await getClient().messages.parse({
    model: MODEL,
    max_tokens: opts.maxTokens ?? 8000,
    thinking: { type: 'adaptive' },
    system: [{ type: 'text', text: opts.system, cache_control: { type: 'ephemeral' } }],
    messages: [{ role: 'user', content: opts.user }],
    output_config: { format: zodOutputFormat(opts.schema) },
  });
  if (response.stop_reason === 'refusal') {
    throw new Error(`Model refused at stage "${opts.stage}" — inspect input; do not retry blindly.`);
  }
  if (response.parsed_output == null) {
    throw new Error(`Structured output parse failed at stage "${opts.stage}" (stop_reason=${response.stop_reason}).`);
  }
  return response.parsed_output;
}
