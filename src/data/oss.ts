export interface OssProject {
  name: string;
  url: string;
  /** precise: "Author" only where he wrote the code */
  role: string;
  hot?: boolean;
  year: string;
  stars?: number;
  blurb: string;
}

/** Star counts are a snapshot taken at build time — see README for how to refresh. */
export const openSource: OssProject[] = [
  {
    name: 's3prl / SUPERB',
    url: 'https://github.com/s3prl/s3prl',
    role: 'SUPERB benchmark co-author',
    year: '2021',
    stars: 2559,
    blurb:
      'Self-supervised speech toolkit hosting the SUPERB benchmark — the evaluation suite that became a community standard for speech representations.',
  },
  {
    name: 'ContentVec',
    url: 'https://github.com/auspicious3000/contentvec',
    role: 'Paper co-author',
    year: '2022',
    stars: 520,
    blurb: 'Speaker-disentangled self-supervised speech representations (ICML 2022).',
  },
  {
    name: 'Contrastive-Predictive-Coding-PyTorch',
    url: 'https://github.com/jefflai108/Contrastive-Predictive-Coding-PyTorch',
    role: 'Author',
    hot: true,
    year: '2019',
    stars: 506,
    blurb:
      'Reference PyTorch implementation of CPC representations for speaker verification, from my undergraduate thesis.',
  },
  {
    name: 'SSAST',
    url: 'https://github.com/YuanGongND/ssast',
    role: 'Paper co-author',
    year: '2022',
    stars: 430,
    blurb: 'Self-Supervised Audio Spectrogram Transformer (AAAI 2022).',
  },
  {
    name: 'pytorch-kaldi-neural-speaker-embeddings',
    url: 'https://github.com/jefflai108/pytorch-kaldi-neural-speaker-embeddings',
    role: 'Author',
    hot: true,
    year: '2019',
    stars: 136,
    blurb:
      'Lightweight Kaldi + PyTorch pipeline for extracting neural speaker embeddings and reproducing speaker-recognition results.',
  },
  {
    name: 'ASSERT',
    url: 'https://github.com/jefflai108/ASSERT',
    role: 'Author',
    hot: true,
    year: '2019',
    stars: 57,
    blurb:
      "JHU's ASVspoof 2019 anti-spoofing system — squeeze-excitation and residual networks (Interspeech 2019).",
  },
  {
    name: 'Attentive-Filtering-Network',
    url: 'https://github.com/jefflai108/Attentive-Filtering-Network',
    role: 'Author',
    hot: true,
    year: '2018',
    stars: 50,
    blurb:
      'Edinburgh–JHU audio replay attack detection system for ASVspoof 2017 v2.0 (ICASSP 2019).',
  },
];
