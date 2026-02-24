# Atlas Market Intelligence — Brand Usage

## Primary Assets

- `logo-mark.png` → Primary mark (default for header icon + favicon source)
- `logo-horizontal.png` → Full logo with wordmark (light background)
- `logo-banner-dark.png` → Full logo for dark hero/banner strips
- `logo-mark-large.png` → High-resolution mark variant

## Deployment Rules

1. If brand text "Atlas Market Intelligence" is already present nearby, use **logo-mark.png** only.
2. If no nearby text, use **logo-horizontal.png** (or `logo-banner-dark.png` on dark strips).
3. Favicon should be generated from **logo-mark.png**.

## Current Site Mapping

- Site header strips: `logo-mark.png` + text label
- Favicon: `assets/favicon.png` (generated from `logo-mark.png`)
- Optional dark hero/banner: `logo-banner-dark.png`
