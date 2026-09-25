import mandarin from './tts-benchmark.json';
import english from './tts-benchmark-en.json';

export const cohorts = [
  { language: 'zh-Hant-TW', label: 'Taiwanese Mandarin', benchmark: mandarin, downloadSuffix: '' },
  { language: 'en', label: 'English', benchmark: english, downloadSuffix: '-en' },
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
  }))),
  records: cohorts.flatMap(cohort => cohort.benchmark.records),
};
