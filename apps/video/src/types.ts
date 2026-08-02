// Self-contained storyboard/scene types for the answer-video generator.
// Vendored (no cross-repo dependency) from the shape a canvas storyboard needs.

export type ClipFormat = '16:9' | '9:16' | '1:1';
export type FusionTheme = 'midnight' | 'aurora' | 'editorial' | 'noir' | 'sunrise';

export type SceneVisual =
  | 'title' | 'bullets' | 'stat' | 'quote' | 'chart'
  | 'comparison' | 'timeline' | 'bignumbers' | 'donut' | 'pictograph';

export interface StoryboardScene {
  narration: string; // voiceover text (spoken)
  visual: SceneVisual;
  title: string;     // on-screen headline
  subtitle?: string;
  bullets?: string[];
  stat?: { value: string; label: string };
  quote?: { text: string; attribution?: string };
  chart?: { unit?: string; bars: { label: string; value: number }[] };
  comparison?: { left: { heading: string; items: string[] }; right: { heading: string; items: string[] } };
  timeline?: { steps: { label: string; detail?: string }[] };
  bignumbers?: { items: { value: string; label: string }[] };
  donut?: { value: number; label: string; unit?: string };
  pictograph?: { filled: number; total: number; label: string }; // unit chart: `filled` of `total` icons
}

export interface AnswerVideo {
  title: string;
  filename: string;
  filePath: string;   // relative to the video app dir
  durationSec: number;
  size: number;
  mime: string;
}
