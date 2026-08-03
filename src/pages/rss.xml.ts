import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';
import { site } from '../data/site';
import type { APIContext } from 'astro';

export async function GET(context: APIContext) {
  const posts = (await getCollection('blog')).filter((p) => !p.data.draft);

  return rss({
    title: site.name,
    description: `Writing by ${site.name} on speech, audio LLMs, and real-time voice systems.`,
    site: context.site ?? site.url,
    items: posts
      .sort((a, b) => b.data.date.valueOf() - a.data.date.valueOf())
      .map((post) => ({
        title: post.data.title,
        description: post.data.description,
        pubDate: post.data.date,
        link: post.data.external ?? `/blog/${post.id}/`,
      })),
  });
}
