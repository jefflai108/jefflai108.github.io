import { orgs, people } from './site';

export interface TimelineItem {
  role: string;
  org: string;
  orgUrl?: string;
  loc?: string;
  period: string;
  current?: boolean;
  advisors?: { name: string; url?: string }[];
  advisorLabel?: string;
  desc?: string;
  points?: string[];
}

export const experience: TimelineItem[] = [
  {
    role: 'Research Scientist',
    org: 'Meta Superintelligence Labs',
    orgUrl: orgs.meta,
    period: '2025.08 — Present',
    current: true,
    points: [
      'Scaling real-time audio-text LLMs from research to production — long-term memory and user-specific personalization for voice AI companions.',
      'Leading <strong>user-memory post-training</strong> data curation and evaluation as part of the core real-time voice post-training recipe.',
      'Co-leading infra integration for real-time memory extraction and personalized response generation in streaming voice interactions.',
    ],
  },
  {
    role: 'Member of Technical Staff',
    org: 'WaveForms AI',
    period: '2025.05 — 2025.07',
    desc: `<a href="${orgs.waveformsNews}">Acquired by Meta</a> in August 2025.`,
    points: [
      'Architected the initial <strong>audio-text MoE</strong> architecture for real-time voice modeling, moving the stack from dense to sparse experts.',
      'Orchestrated large-scale mid-training across <strong>256 GPUs</strong> — expert load balancing, throughput, and training stability.',
      'Owned model-training tradeoffs across routing, checkpointing, and systems throughput.',
    ],
  },
  {
    role: 'Student Researcher',
    org: 'Google DeepMind, Speech',
    orgUrl: orgs.deepmind,
    period: '2024.06 — 2024.12',
    points: [
      'Built <strong>Audio-Visual Gemma</strong> (3B / 10B / 28B), a foundation-model family for natively visually-coherent speech generation.',
      'Led audio-visual data curation (<strong>285k hours</strong> of spoken captions) and orchestrated training on <strong>512 TPUs</strong>.',
      'SOTA on Spoken Visual QA, video-to-speech generation, and audio-visual sound understanding.',
    ],
  },
  {
    role: 'Research Scientist Intern',
    org: 'Apple, Foundation Models',
    orgUrl: orgs.apple,
    period: '2023.05 — 2023.08',
    desc: 'Instruction-following ASR — models that follow natural-language prompts for controllable transcription.',
  },
  {
    role: 'Research Scientist Intern',
    org: 'Meta FAIR',
    orgUrl: orgs.metaFair,
    period: '2022.05 — 2022.09',
    desc: 'Grounding sources for word discovery, applied to direct speech-to-speech translation.',
  },
  {
    role: 'Research Scientist Intern',
    org: 'MIT-IBM Watson AI Lab',
    orgUrl: orgs.mitIbm,
    period: '2021.06 — 2021.09',
    desc: 'Pruning-based self-supervised ASR (<strong>NeurIPS 2021 Spotlight</strong>) and disentanglement for self-supervised speech representations.',
  },
  {
    role: 'Applied Scientist Intern',
    org: 'Amazon AI',
    orgUrl: orgs.amazon,
    period: '2020.05 — 2020.08',
    desc: 'Self-supervised spoken language understanding under limited and noisy data regimes.',
  },
];

/** Older internships, rendered as a compact one-liner under the timeline. */
export const earlierRoles = {
  label: 'Earlier',
  html: `Research intern at the <a href="${orgs.nii}">National Institute of Informatics</a>, Tokyo (2019) and the <a href="${orgs.edinburgh}">Centre for Speech Technology Research</a>, University of Edinburgh (2018).`,
};

export const education: TimelineItem[] = [
  {
    role: 'Ph.D. + S.M., Electrical Engineering & Computer Science',
    org: 'MIT',
    orgUrl: orgs.mit,
    loc: 'CSAIL, Spoken Language Systems',
    period: '2019 — 2025',
    advisorLabel: 'Advisor:',
    advisors: [{ name: 'James Glass', url: people.glass }],
    points: [
      '<strong>Ph.D. thesis</strong>: Language Modeling from Visually Grounded Speech.',
      '<strong>S.M. thesis</strong>: Finding Sparse Subnetworks in Self-Supervised Speech Recognition and Speech Synthesis.',
      'Merrill Lynch Fellowship, MIT EECS.',
    ],
  },
  {
    role: 'B.S., Electrical Engineering',
    org: 'Johns Hopkins University',
    orgUrl: orgs.jhu,
    loc: 'CLSP',
    period: '2015 — 2018',
    advisorLabel: 'Advisors:',
    advisors: [
      { name: 'Najim Dehak', url: people.dehak },
      { name: 'Jesús Villalba', url: people.villalba },
    ],
    points: [
      '<strong>Thesis</strong>: Contrastive Predictive Coding Based Feature for Automatic Speaker Verification.',
      'Vredenburg Scholarship · Departmental and General Honors · Dean’s List (all semesters).',
    ],
  },
];

export interface Talk {
  date: string;
  title: string;
  venue: string;
  venueUrl?: string;
}

export const talks: Talk[] = [
  {
    date: '2022.04',
    title: 'The SUPERB Benchmark',
    venue: 'MIT 6.345 Automatic Speech Recognition — guest lecture',
  },
  {
    date: '2022.04',
    title: 'Making Machines Understand Uncommon Spoken Languages',
    venue: 'MIT ROCSA 5×5',
  },
  {
    date: '2021',
    title: 'Finding Sparse Subnetworks in Self-Supervised Speech Recognition and Speech Synthesis',
    venue: 'Georgia Tech · A*STAR Singapore · ASAPP · NII Japan',
  },
  {
    date: '2020—21',
    title: 'Semi-Supervised Training for Semantics Understanding from Speech',
    venue: 'NII Japan · NEC · JHU CLSP · MIT · AWS AI',
  },
];

export const service = {
  committees: 'AAAI 2022 SAS · ACL 2021 MetaNLP · NeurIPS 2020 SAS',
  reviewing:
    'ACL · NAACL · EMNLP · EACL · ICML · NeurIPS · SLT · IEEE/ACM TASLP · Computer Speech & Language',
};
