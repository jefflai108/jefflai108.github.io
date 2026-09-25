// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// User site (jefflai108.github.io) — served from the domain root, so no `base`.
export default defineConfig({
  site: 'https://jefflai108.github.io',
  // Keep whitespace around inline links when upgrading from Astro 5.
  compressHTML: true,
  integrations: [sitemap({
    filter: (page) => !/^\/tts(?:\/|$)/.test(new URL(page).pathname),
  })],
  markdown: {
    shikiConfig: { theme: 'github-light', wrap: true },
  },
  build: {
    inlineStylesheets: 'auto',
  },
});
