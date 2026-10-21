# Client squads — Command 1A

Screenshots of the actual `ClientSquads` component within the Control page, rendered with offline service fixtures in the saved cloud environment. No production client data or credentials are used. Captured at viewport widths 375px and 1440px; images crop to the new tile.

`node tests/command-squads-ui.cjs` checks founder authorization, tenant mapping, the real server-side Tank helper, mutation/read-back, error states and tile rendering. It writes `/tmp/command1a-ui/client-squads.html`. Chromium verified seven labelled switches and no horizontal overflow at either viewport. The expanded audit history uses a fixture event.

- [375px](client-squads-375.png)
- [1440px](client-squads-1440.png)
