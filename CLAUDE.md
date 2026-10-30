# Trip Monitoring: rules for Claude Code

Trip Monitoring is a trip register on Google Sheets and Apps Script: requestors or drivers create and submit trips, supervisors validate them, Accounting completes them, Admin manages users and lookups. Plan: `trip-monitoring/docs/plan-m1-trips.md`; status: `trip-monitoring/docs/STATUS.md`.

## Stack and layout

- Stack: Google Sheets + Apps Script, plain HTML
- Work only inside the project folder the request names. Leave other folders and `.github/` alone.
- Keep the layers the plan names, and do not add a dependency the plan does not list.

## Design

- Design tokens (set in `trip-monitoring/src/web/app.css`; every screen reuses them, do not invent new ones):
  - Colors: text `#1f2933`, background `#f7f8fa`, surface `#ffffff`, accent `#1f6feb`, danger `#b42318`, success `#157347`, border `#d0d5dd`.
  - Fonts: system UI stack for body, system monospace for IDs and readings; scale 14/16/20/28 px.
  - Spacing 4, 8, 16, 24 px; corner radius 6 px; touch targets at least 44 px.
- Plain HTML and CSS for an Apps Script app; React only when the plan says so.

## Loop rules

Follow `.claude/skills/github-loop/SKILL.md`. The repository owner is `lheiiyy`. Never push to `main`; use `claude/` branches and open a pull request. Stop and use `needs-leo` only for: deleting files, changing the data model, touching anything outside the project folder, or editing `.github/`. Everything else, decide and continue.

## Tests

- Test command: `node --test 'tests/*.test.js'` in `trip-monitoring/` (or `npm test` there). Run it before every hand-off.
- A screen change is checked at 1280, 768 and 375 pixels, with screenshots saved as the frontend note says.
- An Apps Script app is tested on its mock transport (`tests/fixtures/`); its deploy is a manual step for the owner.
- The repository may be public: never commit secrets, tokens, real personal data or internal IDs.

Keep runs short: read only the files the issue names, and keep issue replies to the 150-word format.
