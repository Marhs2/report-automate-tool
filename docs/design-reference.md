# Design reference — 일일보고 app chrome

Cited products (opened 2026-09-18):

- [Linear, “A calmer interface for a product in motion”](https://linear.app/now/behind-the-latest-design-refresh) (2026-03-12 UI refresh)
- [Linear changelog: UI refresh](https://linear.app/changelog/2026-03-12-ui-refresh)
- [Notion product](https://www.notion.com/product) — workspace sidebar + one work surface
- Existing `DESIGN.md` (Linear / Notion / Slite internal-tool chrome, sage-cream tokens)

These are chrome references only. Sage-cream tokens stay; do not copy Linear’s dark navy or Notion’s marketing hero.

## Rules taken from the references

1. **Receding sidebar.** Linear 2026: navigation that supports orientation should recede so the work surface stays in focus. Sidebar is a few notches dimmer than the canvas; inactive labels are muted; active item is a quiet pill, not a filled brand block.
2. **One header action row.** Linear: headers became consistent so actions sit in a predictable place. Topbar holds the page title on the left and **at most one** primary sage CTA on the right. Page bodies do not invent a second title row that duplicates the topbar.
3. **Grouped by intent, not org chart.** Notion-style workspace: a short primary rail (work the user does every day) plus one **설정** destination for people, teams, and names. Do not list every admin screen as a peer of 일일보고.
4. **Compact tabs, felt structure.** Linear: tabs are compact pills, not full-width underlines. Borders stay hairline and low-contrast so structure is felt, not drawn as a grid of boxes.

## What we will not copy

- Linear dark theme, colored team-icon backgrounds, icon-only tab bars as the only nav.
- Notion marketing landing density (hero, 80px type).
- Extra product surfaces (inbox, billing, dark mode).
