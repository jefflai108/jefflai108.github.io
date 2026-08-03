---
title: 'Hello — a template post'
description: 'Delete this file, or flip draft to false and start writing. It is here as a formatting reference.'
date: 2026-08-03
tags: ['speech', 'notes']
draft: true
---

This file is a template. While `draft: true` it is invisible everywhere — the homepage,
the blog index, and the RSS feed all skip it. Flip it to `false` (or delete the line) to
publish.

To add a post, drop a new `.md` file in `src/content/blog/`. The filename becomes the URL:
`my-post.md` → `/blog/my-post/`. The frontmatter fields above are the whole schema —
`title`, `description`, and `date` are required, `tags` and `draft` are optional.

## Formatting

Regular paragraphs, **bold**, *italic*, and [links](https://example.com) all work.

- Bullet lists
- Work fine

Code blocks are syntax-highlighted:

```python
import torch

def sparsity(model: torch.nn.Module) -> float:
    """Fraction of zeroed weights — the metric PARP optimizes against."""
    total = sum(p.numel() for p in model.parameters())
    zeros = sum((p == 0).sum().item() for p in model.parameters())
    return zeros / total
```

> Block quotes look like this.

## Linking out instead

To list a post that lives somewhere else (Medium, a lab blog), add an `external` URL to
the frontmatter. The blog index will link straight out to it and no local page is built.
