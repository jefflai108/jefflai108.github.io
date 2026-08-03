export interface ArchivePost {
  title: string;
  url: string;
  date: string;
  blurb: string;
}

/**
 * Earlier writing, all on Medium and all from the JHU / pre-MIT years.
 * Kept separate from the `blog` content collection so a 2017 post never
 * surfaces as the "latest" on the homepage.
 */
export const mediumArchive: ArchivePost[] = [
  {
    title: 'My Top Research Papers (2016–2019)',
    url: 'https://medium.com/@jefflai108/my-top-research-papers-2016-2019-279b7c89d9e8',
    date: '2019-02-18',
    blurb:
      'Eight papers that shaped my early thinking — Attention Is All You Need, CPC, GMM-UBM speaker verification, ResNet, GANs, and more.',
  },
  {
    title: "Some thoughts on Google's Outrageously Large Network",
    url: 'https://medium.com/@jefflai108/some-thoughts-on-googles-outrageously-large-network-9dc186afb614',
    date: '2017-10-02',
    blurb:
      "A read-through of Google's sparsely-gated Mixture-of-Experts paper — conditional computation, and routing each input to a few specialists.",
  },
  {
    title: 'Visualizing Deep Learning with Plotly',
    url: 'https://medium.com/@jefflai108/visualizing-deep-learning-with-plotly-8f2500e24b27',
    date: '2017-06-29',
    blurb: 'Swapping matplotlib for Plotly to get interactive training curves out of Keras runs.',
  },
  {
    title: 'Channel compensation for SVM speaker recognition',
    url: 'https://medium.com/@jefflai108/channel-compensation-for-svm-speaker-recognition-3588f777ca78',
    date: '2017-05-31',
    blurb:
      'Using projection matrices to strip channel and microphone variability out of SVM-based speaker recognition features.',
  },
  {
    title: 'A Study of Feature Selection of Whale Vocalization',
    url: 'https://medium.com/@jefflai108/a-study-of-feature-selection-of-whale-vocalization-4d06bad23677',
    date: '2017-05-28',
    blurb:
      'Reviewing two approaches to classifying whale calls — the Weyl Transform, and a comparison of PCA, MDS, Laplacian Eigenmaps and ISOMAP.',
  },
];
