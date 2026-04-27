# TechMill

Website for [TechMill](https://techmill.co), a technology community organization based in Denton, Texas.

Built with [Jekyll](https://jekyllrb.com), managed via [Pages CMS](https://pagescms.org), and deployed to GitHub Pages.

## Development

```bash
bundle install
bundle exec jekyll serve
```

Visit `http://localhost:4000`.

## Content Management

Content is managed through [Pages CMS](https://app.pagescms.org). Connect the repo there to edit posts and pages through a web UI.

- Posts → `_posts/` (format: `YYYY-MM-DD-slug.md`)
- Pages → `_pages/`
- Media → `media/`

## Rebuilding from Archive

To repopulate content from the Wayback Machine:

```bash
pip install -r requirements.txt
python3 scripts/archive_fetch.py --download-media
```

Run with `--dry-run` to preview what would be fetched without writing files.

## Deployment

Pushes to `master` deploy automatically via GitHub Actions → GitHub Pages.
