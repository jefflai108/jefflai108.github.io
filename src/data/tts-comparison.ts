import mandarin from './tts-benchmark.json';
import english from './tts-benchmark-en-us.json';
import emotion from './tts-benchmark-zh-emotion.json';
import vocal from './tts-benchmark-zh-vocal.json';

export type Stats = {
  count: number; p50TtfbMs: number; p95TtfbMs: number;
  p50TotalMs: number; p95TotalMs: number; medianAudioSeconds: number;
};
type Passage = {
  id: string; title: string; category: string; sentences: number; text: string;
  spokenText?: string; audioTags?: string[]; tagReason?: string;
};
export type Benchmark = Omit<typeof mandarin, 'byModel' | 'byVoice' | 'paragraphs'> & {
  byModel: Record<string, Stats>;
  byVoice: Record<string, Record<string, Stats>>;
  paragraphs: Passage[];
  method: {
    audioTags?: string[]; tagPlacement?: string; audioTagCategory?: string | null;
    tagsVaryByPassage?: boolean; warmupAudioTags?: string[];
  };
};
export const variants = [
  { id: 'eleven_v3', modelId: 'eleven_v3', label: 'Eleven v3', style: 'Original' },
  { id: 'eleven_v3_conversational', modelId: 'eleven_v3_conversational', label: 'v3 Conversational', style: 'Original' },
  { id: 'emotion', modelId: 'eleven_v3', label: 'Eleven v3 · emotion', style: 'Emotion' },
  { id: 'vocal', modelId: 'eleven_v3', label: 'Eleven v3 · vocal reaction', style: 'Vocal reaction' },
];
type Variant = typeof variants[number];
type Run = { label: string; benchmark: Benchmark; downloadSuffix: string; variantIds: string[] };
export type Cohort = {
  language: string; label: string; benchmark: Benchmark; runs: Run[];
  versions: (Variant & { benchmark: Benchmark })[];
};
function cohort(language: string, label: string, runs: Run[]): Cohort {
  const versions = runs.flatMap(run => run.variantIds.map(id => {
    const variant = variants.find(v => v.id === id)!;
    if (!run.benchmark.models.some(m => m.id === variant.modelId)) throw new Error(`Missing model for ${id}`);
    return { ...variant, benchmark: run.benchmark };
  }));
  return { language, label, benchmark: runs[0].benchmark, runs, versions };
}
export const cohorts = [
  cohort('zh-Hant-TW', 'Taiwanese Mandarin', [
    { label: 'Original models', benchmark: mandarin, downloadSuffix: '', variantIds: ['eleven_v3', 'eleven_v3_conversational'] },
    { label: 'Emotion', benchmark: emotion, downloadSuffix: '-zh-emotion', variantIds: ['emotion'] },
    { label: 'Vocal reaction', benchmark: vocal, downloadSuffix: '-zh-vocal', variantIds: ['vocal'] },
  ]),
  cohort('en-US', 'English', [
    { label: 'American accent', benchmark: english, downloadSuffix: '-en-us', variantIds: ['eleven_v3', 'eleven_v3_conversational'] },
  ]),
];

export const comparison = {
  generatedOn: mandarin.generatedOn,
  defaultModelId: mandarin.defaultModelId,
  variants,
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
        variantId: version.id, text: input.text,
        audioTags: input.audioTags ?? version.benchmark.method.audioTags ?? [],
        tagReason: input.tagReason ?? '',
      };
    }),
  }))),
  records: cohorts.flatMap(group => group.versions.flatMap(version => version.benchmark.records
    .filter(record => record.modelId === version.modelId)
    .map(record => ({ ...record, variantId: version.id })))),
};

// Fail the build if a comparison cell is missing or a style overwrites a baseline.
const recordKeys = new Set(comparison.records.map(r => `${r.variantId}/${r.paragraphId}/${r.voiceId}`));
if (recordKeys.size !== comparison.records.length) throw new Error('Duplicate comparison recordings');
for (const paragraph of comparison.paragraphs) {
  for (const version of paragraph.versions) {
    for (const voice of comparison.voices) {
      if (!recordKeys.has(`${version.variantId}/${paragraph.id}/${voice.id}`)) {
        throw new Error(`Missing recording: ${version.variantId}/${paragraph.id}/${voice.id}`);
      }
    }
  }
}
