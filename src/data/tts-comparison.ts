import mandarin from './tts-benchmark.json';
import english from './tts-benchmark-en-us.json';

type Benchmark = typeof mandarin & { method: { audioTags?: string[]; tagPlacement?: string } };

export const cohorts: { language: string; label: string; benchmark: Benchmark; downloadSuffix: string }[] = [
  { language: 'zh-Hant-TW', label: 'Taiwanese Mandarin', benchmark: mandarin, downloadSuffix: '' },
  { language: 'en-US', label: 'English', benchmark: english, downloadSuffix: '-en-us' },
];

export const comparison = {
  generatedOn: mandarin.generatedOn,
  defaultModelId: mandarin.defaultModelId,
  models: mandarin.models,
  voices: mandarin.voices,
  paragraphs: cohorts.flatMap(cohort => cohort.benchmark.paragraphs.map(paragraph => ({
    ...paragraph,
    language: cohort.language,
    languageLabel: cohort.label,
    audioTags: cohort.benchmark.method.audioTags ?? [],
  }))),
  records: cohorts.flatMap(cohort => cohort.benchmark.records),
};
