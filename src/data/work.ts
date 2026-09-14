export interface WorkItem {
  /** short display name */
  name: string;
  /** one-line framing — what it is */
  tagline: string;
  /** 1-2 sentences */
  blurb: string;
  date: string;
  /** e.g. "Preprint", "Google DeepMind", "Side project" */
  tags?: string[];
  links?: { label: string; href: string }[];
  /** highlight the newest / most significant entry */
  featured?: boolean;
}

/**
 * Newest first. This is the front-of-house section — projects worth clicking
 * into, not a changelog. More speech side-projects land here as they ship.
 */
export const recentWork: WorkItem[] = [
  {
    name: '台灣語林',
    tagline: 'A topic map of Taiwan’s everyday conversations',
    blurb:
      'An interactive map of collected PTT, Dcard and Threads posts. Follow topic branches, compare coverage, and trace each title back to its original conversation.',
    date: '2026',
    tags: ['TaiwanCorpus', 'Interactive collection'],
    links: [{ label: 'explore the tree', href: '/taiwan-corpus/' }],
  },
  {
    name: 'AV-Gemma',
    tagline: 'Audio-visual foundation models that speak about what they see',
    blurb:
      'A family of 3B/10B audio–visual models that generate audio tokens directly from images and short video — a SigLIP encoder for visual understanding, audio-token generation inside a Gemma backbone, pretrained on 285k hours of web-scale spoken captions. Transfers to Spoken Visual QA, video-to-speech generation, and audio-visual sound understanding.',
    date: '2025',
    tags: ['Google DeepMind'],
    featured: true,
    links: [
      { label: 'project page', href: 'https://people.csail.mit.edu/clai24/avgemma/' },
      { label: 'paper', href: '/data/av-gemma.pdf' },
    ],
  },
];
