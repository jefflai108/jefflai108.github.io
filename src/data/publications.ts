export interface Publication {
  key: string;
  title: string;
  /** Author list. Wrap Jeff's own name in {} so it can be emphasised. */
  authors: string;
  venue: string;
  year: number;
  honor?: string;
  citations?: number;
  arxiv?: string;
  code?: string;
  page?: string;
  /** show on the homepage's selected list */
  selected?: boolean;
}

/**
 * Ordered newest-first. `citations` are a Google Scholar snapshot — see
 * site.scholarStats.asOf. Every arXiv / code / page URL below was fetched and
 * confirmed to resolve to this exact paper; where no verified link exists the
 * field is simply omitted rather than guessed.
 */
export const publications: Publication[] = [
  {
    key: 'instruct-asr',
    title: 'Instruction-Following Speech Recognition',
    authors: '{Cheng-I Jeff Lai}*, Zhiyun Lu, Liangliang Cao, Ruoming Pang',
    venue: 'NeurIPS Workshop',
    year: 2024,
    arxiv: 'https://arxiv.org/abs/2309.09843',
    code: 'https://github.com/jefflai108/speeech-instruction-following',
    selected: true,
  },
  {
    key: 'superb-eval',
    title: 'A Large-Scale Evaluation of Speech Foundation Models',
    authors:
      'Shu-wen Yang, Heng-Jui Chang, Zili Huang, Andy T. Liu, {Cheng-I Jeff Lai}, Haibin Wu, Jiatong Shi, Xuankai Chang, et al.',
    venue: 'IEEE/ACM TASLP',
    year: 2024,
    citations: 89,
    arxiv: 'https://arxiv.org/abs/2404.09385',
    code: 'https://github.com/s3prl/s3prl',
    page: 'https://superbbenchmark.github.io/',
    selected: true,
  },
  {
    key: 'av-nsl',
    // Published at ASRU under this title. An earlier submission circulated as
    // "Textless Phrase Structure Induction from Visually-Grounded Speech".
    title: 'Audio-Visual Neural Syntax Acquisition',
    authors:
      '{Cheng-I Jeff Lai}*, Freda Shi*, Puyuan Peng*, Yoon Kim, Kevin Gimpel, Shiyu Chang, Yung-Sung Chuang, Saurabhchand Bhati, David Cox, David Harwath, Yang Zhang, Karen Livescu, James Glass',
    venue: 'ASRU',
    year: 2023,
    // The arXiv preprint carries the earlier title "Audio-Visual Neural Syntax Acquisition".
    arxiv: 'https://arxiv.org/abs/2310.07654',
    code: 'https://github.com/jefflai108/AV-NSL',
    selected: true,
  },
  {
    key: 's3-router',
    title:
      'Losses Can Be Blessings: Routing Self-Supervised Speech Representations Towards Efficient Multilingual and Multitask Speech Processing',
    authors:
      'Yonggan Fu, Yang Zhang, Kaizhi Qian, Zhifan Ye, Zhongzhi Yu, {Cheng-I Jeff Lai}, Yingyan Lin',
    venue: 'NeurIPS',
    year: 2022,
    citations: 11,
    arxiv: 'https://arxiv.org/abs/2211.01522',
    code: 'https://github.com/GATECH-EIC/S3-Router',
  },
  {
    key: 'unsup-tts',
    title: 'Simple and Effective Unsupervised Speech Synthesis',
    authors:
      'Alexander H. Liu*, {Cheng-I Jeff Lai}*, Wei-Ning Hsu, Michael Auli, Alexei Baevski, James Glass',
    venue: 'Interspeech',
    year: 2022,
    citations: 22,
    arxiv: 'https://arxiv.org/abs/2204.02524',
    code: 'https://github.com/jefflai108/Unsupervised-TTS',
    selected: true,
  },
  {
    key: 'contentvec',
    title:
      'ContentVec: An Improved Self-Supervised Speech Representation by Disentangling Speakers',
    authors:
      'Kaizhi Qian, Yang Zhang, Heting Gao, Junrui Ni, {Cheng-I Jeff Lai}, David Cox, Mark Hasegawa-Johnson, Shiyu Chang',
    venue: 'ICML',
    year: 2022,
    citations: 207,
    arxiv: 'https://arxiv.org/abs/2204.09224',
    code: 'https://github.com/auspicious3000/contentvec',
    selected: true,
  },
  {
    key: 'cm-discrete',
    title: 'Cross-Modal Discrete Representation Learning',
    authors:
      'Alexander H. Liu, SouYoung Jin, {Cheng-I Jeff Lai}, Andrew Rouditchenko, Aude Oliva, James Glass',
    venue: 'ACL',
    year: 2022,
    honor: 'Oral',
    citations: 79,
    arxiv: 'https://arxiv.org/abs/2106.05438',
    page: 'https://aclanthology.org/2022.acl-long.215/',
  },
  {
    key: 'superb-sg',
    title:
      'SUPERB-SG: Enhanced Speech Processing Universal PERformance Benchmark for Semantic and Generative Capabilities',
    authors:
      'Hsiang-Sheng Tsai, Heng-Jui Chang, Wen-Chin Huang, Zili Huang, Kushal Lakhotia, Shu-wen Yang, Shuyan Dong, Andy T. Liu, {Cheng-I Jeff Lai}, et al.',
    venue: 'ACL',
    year: 2022,
    citations: 141,
    arxiv: 'https://arxiv.org/abs/2203.06849',
    code: 'https://github.com/s3prl/s3prl',
    page: 'https://superbbenchmark.github.io/',
  },
  {
    key: 'ssast',
    title: 'SSAST: Self-Supervised Audio Spectrogram Transformer',
    authors: 'Yuan Gong, {Cheng-I Jeff Lai}, Yu-An Chung, James Glass',
    venue: 'AAAI',
    year: 2022,
    citations: 564,
    arxiv: 'https://arxiv.org/abs/2110.09784',
    code: 'https://github.com/YuanGongND/ssast',
    selected: true,
  },
  {
    key: 'tts-pruning',
    title:
      'On the Interplay Between Sparsity, Naturalness, Intelligibility, and Prosody in Speech Synthesis',
    authors:
      '{Cheng-I Jeff Lai}, Erica Cooper, Yang Zhang, Shiyu Chang, Kaizhi Qian, Yi-Lun Liao, Yung-Sung Chuang, Alexander H. Liu, Junichi Yamagishi, David Cox, James Glass',
    venue: 'ICASSP',
    year: 2022,
    arxiv: 'https://arxiv.org/abs/2110.01147',
    code: 'https://github.com/jefflai108/TTS-Pruning-Pytorch',
  },
  {
    key: 'parp',
    title: 'PARP: Prune, Adjust and Re-Prune for Self-Supervised Speech Recognition',
    authors:
      '{Cheng-I Jeff Lai}, Yang Zhang*, Alexander H. Liu*, Shiyu Chang*, Yi-Lun Liao, Yung-Sung Chuang, Kaizhi Qian, Sameer Khurana, David Cox, James Glass',
    venue: 'NeurIPS',
    year: 2021,
    honor: 'Spotlight',
    citations: 100,
    arxiv: 'https://arxiv.org/abs/2106.05933',
    code: 'https://github.com/jefflai108/PARP-wav2vec-PyTorch',
    selected: true,
  },
  {
    key: 'superb',
    title: 'SUPERB: Speech Processing Universal PERformance Benchmark',
    authors:
      'Shu-wen Yang, Po-Han Chi*, Yung-Sung Chuang*, {Cheng-I Jeff Lai}*, Kushal Lakhotia*, Yist Y. Lin*, Andy T. Liu*, Jiatong Shi*, Xuankai Chang, et al.',
    venue: 'Interspeech',
    year: 2021,
    citations: 1429,
    arxiv: 'https://arxiv.org/abs/2105.01051',
    code: 'https://github.com/s3prl/s3prl',
    page: 'https://superbbenchmark.github.io/',
    selected: true,
  },
  {
    key: 'semi-slu',
    title:
      'Semi-Supervised Spoken Language Understanding via Self-Supervised Speech and Language Model Pretraining',
    authors: '{Cheng-I Jeff Lai}, Yung-Sung Chuang, Hung-Yi Lee, Shang-Wen Li, James Glass',
    venue: 'ICASSP',
    year: 2021,
    citations: 77,
    arxiv: 'https://arxiv.org/abs/2010.13826',
    code: 'https://github.com/jefflai108/Semi-Supervsied-Spoken-Language-Understanding-PyTorch',
  },
  {
    key: 'semi-semantics',
    title: 'Towards Semi-Supervised Semantics Understanding from Speech',
    authors: '{Cheng-I Jeff Lai}, Jin Cao, Sravan Bodapati, Shang-Wen Li',
    venue: 'NeurIPS Workshop',
    year: 2020,
    arxiv: 'https://arxiv.org/abs/2011.06195',
  },
  {
    key: 'conditioned-nlg',
    title:
      'Conditioned Natural Language Generation Using Only Unconditioned Language Model: An Exploration',
    authors: 'Fan-Keng Sun, {Cheng-I Jeff Lai}',
    venue: 'arXiv',
    year: 2020,
    citations: 16,
    arxiv: 'https://arxiv.org/abs/2011.07347',
  },
  {
    key: 'f0-codebook',
    title:
      'Improved Prosody from Learned F0 Codebook Representations for VQ-VAE Speech Waveform Reconstruction',
    authors:
      'Yi Zhao, Haoyu Li, {Cheng-I Jeff Lai}, Jennifer Williams, Erica Cooper, Junichi Yamagishi',
    venue: 'Interspeech',
    year: 2020,
    citations: 24,
    arxiv: 'https://arxiv.org/abs/2005.07884',
    page: 'https://www.isca-archive.org/interspeech_2020/zhao20g_interspeech.html',
  },
  {
    key: 'speaker-aug-tts',
    title: 'Can Speaker Augmentation Improve Multi-Speaker End-to-End TTS?',
    authors: 'Erica Cooper, {Cheng-I Jeff Lai}, Yusuke Yasuda, Junichi Yamagishi',
    venue: 'Interspeech',
    year: 2020,
    citations: 33,
    arxiv: 'https://arxiv.org/abs/2005.01245',
  },
  {
    key: 'zero-shot-tts',
    title:
      'Zero-Shot Multi-Speaker Text-to-Speech with State-of-the-Art Neural Speaker Embeddings',
    authors:
      'Erica Cooper, {Cheng-I Jeff Lai}, Yusuke Yasuda, Fuming Fang, Xin Wang, Nanxin Chen, Junichi Yamagishi',
    venue: 'ICASSP',
    year: 2020,
    honor: 'Oral',
    citations: 277,
    arxiv: 'https://arxiv.org/abs/1910.10838',
    code: 'https://github.com/nii-yamagishilab/multi-speaker-tacotron',
    page: 'https://nii-yamagishilab.github.io/samples-multi-speaker-tacotron/',
  },
  {
    key: 'assert',
    title: 'ASSERT: Anti-Spoofing with Squeeze-Excitation and Residual Networks',
    authors: '{Cheng-I Jeff Lai}, Nanxin Chen, Jesús Villalba, Najim Dehak',
    venue: 'Interspeech',
    year: 2019,
    citations: 258,
    arxiv: 'https://arxiv.org/abs/1904.01120',
    code: 'https://github.com/jefflai108/ASSERT',
    selected: true,
  },
  {
    key: 'attentive-filtering',
    title: 'Attentive Filtering Networks for Audio Replay Attack Detection',
    authors:
      '{Cheng-I Jeff Lai}, Alberto Abad, Korin Richmond, Junichi Yamagishi, Najim Dehak, Simon King',
    venue: 'ICASSP',
    year: 2019,
    citations: 109,
    arxiv: 'https://arxiv.org/abs/1810.13048',
    code: 'https://github.com/jefflai108/Attentive-Filtering-Network',
  },
  {
    key: 'cpc-asv',
    title: 'Contrastive Predictive Coding Based Feature for Automatic Speaker Verification',
    authors: '{Cheng-I Jeff Lai}',
    venue: 'B.S. thesis, JHU',
    year: 2019,
    citations: 52,
    arxiv: 'https://arxiv.org/abs/1904.01575',
    code: 'https://github.com/jefflai108/Contrastive-Predictive-Coding-PyTorch',
  },
  {
    key: 'reading-level',
    title: 'Controlling the Reading Level of Machine Translation Output',
    authors: 'Kelly Marchisio, Jialiang Guo, {Cheng-I Jeff Lai}, Philipp Koehn',
    venue: 'MT Summit',
    year: 2019,
    citations: 41,
    page: 'https://aclanthology.org/W19-6619/',
  },
  {
    key: 'bandwidth-ext',
    title: 'Investigation on Bandwidth Extension for Speaker Recognition',
    authors: 'Phani Sankar Nidadavolu, {Cheng-I Jeff Lai}, Jesús Villalba, Najim Dehak',
    venue: 'Interspeech',
    year: 2018,
    citations: 27,
    page: 'https://www.isca-archive.org/interspeech_2018/nidadavolu18_interspeech.html',
  },
];

export const selectedPublications = publications.filter((p) => p.selected);
