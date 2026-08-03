import { orgs, people } from './site';

export interface NewsItem {
  date: string;
  /** one line of HTML */
  html: string;
}

/** Reverse-chronological. Keep to one line each. */
export const news: NewsItem[] = [
  {
    date: '2025.08',
    html: `Joined <a href="${orgs.meta}">Meta Superintelligence Labs</a> as a Research Scientist — real-time voice AI, long-term memory, and personalization.`,
  },
  {
    date: '2025.08',
    html: `Finished my Ph.D. at <a href="${orgs.mit}">MIT</a>. Thesis: <strong>Language Modeling from Visually Grounded Speech</strong>, advised by <a href="${people.glass}">James Glass</a>.`,
  },
  {
    date: '2025.05',
    html: `Joined <strong>WaveForms AI</strong> to build audio-text MoE models for real-time voice — the team was <a href="${orgs.waveformsNews}">acquired by Meta</a> that August.`,
  },
  {
    date: '2024.06',
    html: `Started at <a href="${orgs.deepmind}">Google DeepMind</a> Speech as a Student Researcher, working on large-scale audio-visual foundation models for visually-coherent speech generation.`,
  },
  {
    date: '2024.04',
    html: `<a class="venue-badge" href="https://arxiv.org/abs/2404.09385">TASLP 2024</a> <strong>A Large-Scale Evaluation of Speech Foundation Models</strong> — the extended journal version of SUPERB and SUPERB-SG.`,
  },
  {
    date: '2023.10',
    html: `<a class="venue-badge" href="https://arxiv.org/abs/2310.07654">ASRU 2023</a> <strong>Audio-Visual Neural Syntax Acquisition</strong> accepted — grammar induction from speech and images, with no text or ASR in the loop.`,
  },
  {
    date: '2023.05',
    html: `Spent the summer at <a href="${orgs.apple}">Apple</a> Foundation Models on <a href="https://arxiv.org/abs/2309.09843">instruction-following ASR</a>.`,
  },
  {
    date: '2022.10',
    html: `<a class="venue-badge" href="https://arxiv.org/abs/2211.01522">NeurIPS 2022</a> <strong>S3-Router</strong> accepted — routing self-supervised speech representations for efficient multilingual and multitask processing.`,
  },
  {
    date: '2022.05',
    html: `Summer at <a href="${orgs.metaFair}">Meta FAIR</a> on multi-modal word discovery for textless direct speech-to-speech translation.`,
  },
  {
    date: '2022.05',
    html: `<a class="venue-badge" href="https://arxiv.org/abs/2204.09224">ICML 2022</a> <strong>ContentVec</strong>; <a class="venue-badge" href="https://arxiv.org/abs/2106.05438">ACL 2022</a> <strong>Cross-Modal Discrete Representation Learning</strong> (<span class="honor">Oral</span>) and <a href="https://arxiv.org/abs/2203.06849"><strong>SUPERB-SG</strong></a>.`,
  },
  {
    date: '2021.10',
    html: `<a class="venue-badge" href="https://arxiv.org/abs/2106.05933">NeurIPS 2021</a> <strong>PARP</strong> accepted as a <span class="honor">Spotlight</span> (top 3%).`,
  },
  {
    date: '2021.08',
    html: `<a class="venue-badge" href="https://arxiv.org/abs/2105.01051">Interspeech 2021</a> <strong>SUPERB</strong> — the Speech processing Universal PERformance Benchmark, since widely adopted for evaluating speech representations.`,
  },
];
