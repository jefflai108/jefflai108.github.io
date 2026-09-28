import mandarin from './tts-benchmark.json';
import english from './tts-benchmark-en-us.json';
import emotion from './tts-benchmark-zh-emotion.json';
import vocal from './tts-benchmark-zh-vocal.json';
import v4Mandarin from './tts-benchmark-v4.json';
import v4English from './tts-benchmark-v4-en-us.json';
import v4Emotion from './tts-benchmark-v4-zh-emotion.json';
import v4Vocal from './tts-benchmark-v4-zh-vocal.json';

export type Stats = {
  count: number; p50TtfbMs: number; p95TtfbMs: number;
  p50TotalMs: number; p95TotalMs: number; medianAudioSeconds: number;
};
type Passage = {
  id: string; title: string; category: string; sentences: number; text: string;
  spokenText?: string; audioTags?: string[]; tagReason?: string;
};
export type Benchmark = Omit<typeof mandarin, 'byModel' | 'byVoice' | 'paragraphs' | 'settings'> & {
  byModel: Record<string, Stats>;
  byVoice: Record<string, Record<string, Stats>>;
  paragraphs: Passage[];
  settings: Record<string, number>;
  method: {
    audioTags?: string[]; tagPlacement?: string; audioTagCategory?: string | null;
    tagsVaryByPassage?: boolean; warmupAudioTags?: string[];
  };
};
export const styles = [
  { id: 'plain', label: 'Plain text' },
  { id: 'emotion', label: 'Emotion' },
  { id: 'vocal', label: 'Vocal reaction' },
] as const;
export type StyleId = typeof styles[number]['id'];
export const variants = [
  { id: 'eleven_v3', modelId: 'eleven_v3', modelLabel: 'Eleven v3', label: 'Eleven v3', style: 'plain' },
  { id: 'eleven_v3_conversational', modelId: 'eleven_v3_conversational', modelLabel: 'v3 Conversational', label: 'v3 Conversational', style: 'plain' },
  { id: 'eleven_v4', modelId: 'eleven_v4', modelLabel: 'Eleven v4', label: 'Eleven v4', style: 'plain' },
  { id: 'eleven_v4_turbo', modelId: 'eleven_v4_turbo', modelLabel: 'Eleven v4 Turbo', label: 'Eleven v4 Turbo', style: 'plain' },
  { id: 'emotion', modelId: 'eleven_v3', modelLabel: 'Eleven v3', label: 'Eleven v3 · emotion', style: 'emotion' },
  { id: 'eleven_v4_emotion', modelId: 'eleven_v4', modelLabel: 'Eleven v4', label: 'Eleven v4 · emotion', style: 'emotion' },
  { id: 'eleven_v4_turbo_emotion', modelId: 'eleven_v4_turbo', modelLabel: 'Eleven v4 Turbo', label: 'Eleven v4 Turbo · emotion', style: 'emotion' },
  { id: 'vocal', modelId: 'eleven_v3', modelLabel: 'Eleven v3', label: 'Eleven v3 · vocal reaction', style: 'vocal' },
  { id: 'eleven_v4_vocal', modelId: 'eleven_v4', modelLabel: 'Eleven v4', label: 'Eleven v4 · vocal reaction', style: 'vocal' },
  { id: 'eleven_v4_turbo_vocal', modelId: 'eleven_v4_turbo', modelLabel: 'Eleven v4 Turbo', label: 'Eleven v4 Turbo · vocal reaction', style: 'vocal' },
];
type Variant = typeof variants[number];
type Run = { label: string; benchmark: Benchmark; downloadName: string; variantIds: string[] };
export type Cohort = {
  language: string; label: string; benchmark: Benchmark; runs: Run[];
  versions: (Variant & { benchmark: Benchmark })[];
};
function cohort(language: string, label: string, runs: Run[]): Cohort {
  const versions = variants.flatMap(variant => {
    const run = runs.find(r => r.variantIds.includes(variant.id));
    if (!run) return [];
    if (!run.benchmark.models.some(m => m.id === variant.modelId)) throw new Error(`Missing model for ${variant.id}`);
    return [{ ...variant, benchmark: run.benchmark }];
  });
  return { language, label, benchmark: runs[0].benchmark, runs, versions };
}
export const cohorts = [
  cohort('zh-Hant-TW', 'Taiwanese Mandarin', [
    { label: 'v3 · plain', benchmark: mandarin, downloadName: 'v3-benchmark', variantIds: ['eleven_v3', 'eleven_v3_conversational'] },
    { label: 'v3 · emotion', benchmark: emotion, downloadName: 'v3-benchmark-zh-emotion', variantIds: ['emotion'] },
    { label: 'v3 · vocal reaction', benchmark: vocal, downloadName: 'v3-benchmark-zh-vocal', variantIds: ['vocal'] },
    { label: 'v4 + Turbo · plain', benchmark: v4Mandarin, downloadName: 'v4-benchmark', variantIds: ['eleven_v4', 'eleven_v4_turbo'] },
    { label: 'v4 + Turbo · emotion', benchmark: v4Emotion, downloadName: 'v4-benchmark-zh-emotion', variantIds: ['eleven_v4_emotion', 'eleven_v4_turbo_emotion'] },
    { label: 'v4 + Turbo · vocal reaction', benchmark: v4Vocal, downloadName: 'v4-benchmark-zh-vocal', variantIds: ['eleven_v4_vocal', 'eleven_v4_turbo_vocal'] },
  ]),
  cohort('en-US', 'English', [
    { label: 'v3 · American accent', benchmark: english, downloadName: 'v3-benchmark-en-us', variantIds: ['eleven_v3', 'eleven_v3_conversational'] },
    { label: 'v4 + Turbo · American accent', benchmark: v4English, downloadName: 'v4-benchmark-en-us', variantIds: ['eleven_v4', 'eleven_v4_turbo'] },
  ]),
];

export const comparison = {
  generatedOn: cohorts.flatMap(c => c.runs.map(r => r.benchmark.generatedOn)).sort().at(-1)!,
  defaultModelId: mandarin.defaultModelId,
  variants,
  styles,
  voices: mandarin.voices,
  paragraphs: cohorts.flatMap(group => group.benchmark.paragraphs.map(paragraph => ({
    ...paragraph,
    language: group.language,
    languageLabel: group.label,
    versions: group.versions.map(version => {
      const input = version.benchmark.paragraphs.find(p => p.id === paragraph.id);
      if (!input) throw new Error(`Missing input: ${version.id}/${paragraph.id}`);
      if ((input.spokenText ?? input.text) !== (paragraph.spokenText ?? paragraph.text)) {
        throw new Error(`Spoken text differs: ${version.id}/${paragraph.id}`);
      }
      return {
        variantId: version.id, style: version.style, text: input.text,
        audioTags: input.audioTags ?? version.benchmark.method.audioTags ?? [],
        tagReason: input.tagReason ?? '',
        generatedOn: version.benchmark.generatedOn,
      };
    }),
  }))),
  records: cohorts.flatMap(group => group.versions.flatMap(version => version.benchmark.records
    .filter(record => record.modelId === version.modelId)
    .map(record => ({ ...record, variantId: version.id })))),
};

// Validate every voice/passage/style cell and the exact shared model inputs.
const recordKeys = new Set(comparison.records.map(r => `${r.variantId}/${r.paragraphId}/${r.voiceId}`));
if (recordKeys.size !== comparison.records.length) throw new Error('Duplicate comparison recordings');
for (const paragraph of comparison.paragraphs) {
  for (const style of styles) {
    const inputs = paragraph.versions.filter(v => v.style === style.id);
    if (new Set(inputs.map(v => v.text)).size > 1) throw new Error(`Model inputs differ: ${style.id}/${paragraph.id}`);
    if (new Set(inputs.map(v => JSON.stringify(v.audioTags))).size > 1) throw new Error(`Model tags differ: ${style.id}/${paragraph.id}`);
  }
  for (const version of paragraph.versions) {
    for (const voice of comparison.voices) {
      if (!recordKeys.has(`${version.variantId}/${paragraph.id}/${voice.id}`)) {
        throw new Error(`Missing recording: ${version.variantId}/${paragraph.id}/${voice.id}`);
      }
    }
  }
}
