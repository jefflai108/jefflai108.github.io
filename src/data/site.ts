export const site = {
  name: 'Cheng-I Jeff Lai',
  short: 'Jeff Lai',
  role: 'Research Scientist',
  org: 'Meta Superintelligence Labs',
  orgUrl: 'https://ai.meta.com/',
  location: 'Mountain View, CA',
  email: 'jefflai108@gmail.com',
  url: 'https://jefflai108.github.io',
  avatar: '/images/jeff-avatar.jpg',
  cv: '/data/cheng-i-jeff-lai-cv.pdf',
  links: {
    scholar: 'https://scholar.google.com/citations?user=mV4mRm0AAAAJ&hl=en',
    github: 'https://github.com/jefflai108',
    linkedin: 'https://www.linkedin.com/in/jefflai108/',
    medium: 'https://medium.com/@jefflai108',
  },
  scholarStats: {
    citations: '3,600+',
    hIndex: 18,
    i10: 21,
    asOf: 'Aug 2026',
  },
} as const;

/**
 * Canonical outbound URLs, kept in one place so links stay consistent.
 * All checked to resolve as of Aug 2026.
 *
 * Note: waveforms.ai no longer resolves (NXDOMAIN) after the Meta acquisition,
 * so there is deliberately no `waveforms` homepage here — the acquisition
 * coverage is linked instead.
 */
export const orgs = {
  meta: 'https://ai.meta.com/',
  metaFair: 'https://ai.meta.com/research/',
  waveformsNews: 'https://techcrunch.com/2025/08/08/meta-acquires-ai-audio-startup-waveforms/',
  deepmind: 'https://deepmind.google/',
  apple: 'https://machinelearning.apple.com/',
  mitIbm: 'https://mitibm.mit.edu/',
  amazon: 'https://www.amazon.science/',
  mit: 'https://www.mit.edu/',
  csail: 'https://www.csail.mit.edu/',
  sls: 'https://sls.csail.mit.edu/',
  jhu: 'https://www.jhu.edu/',
  clsp: 'https://www.clsp.jhu.edu/',
  edinburgh: 'https://www.cstr.ed.ac.uk/',
  nii: 'https://www.nii.ac.jp/en/',
} as const;

export const people = {
  glass: 'https://people.csail.mit.edu/jrg/',
  dehak: 'https://engineering.jhu.edu/faculty/najim-dehak/',
  villalba: 'https://engineering.jhu.edu/faculty/jesus-villalba/',
} as const;
