// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// User site (jefflai108.github.io) — served from the domain root, so no `base`.
export default defineConfig({
  site: 'https://jefflai108.github.io',
  integrations: [sitemap()],
  markdown: {
    shikiConfig: { theme: 'github-light', wrap: true },
  },
  build: {
    inlineStylesheets: 'auto',
  },
});
