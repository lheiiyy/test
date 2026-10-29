# Expert: frontend

Selected when screens, styles or client code change.

- It must work on desktop, tablet and phone: check 1280, 768 and 375 px (Playwright is preinstalled in scheduled runs).
- Every input has a label, every action a visible result, every error a message the user can act on.
- No console errors and no failed requests on the changed screens.
- The UI calls only the service or API layer, never the data store.
- Loading and empty states exist for every list.
- Touch targets are large enough to tap; nothing important needs hover.
- Review: look at the screenshots, not only the code.
