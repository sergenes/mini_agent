---
name: web-architecture
description: >-
  Default web app architecture: TypeScript, feature folders, a view / state /
  client split in the same spirit as MVVM. Use when creating or changing web
  UI, TypeScript/JavaScript frontend, React or similar SPA/SSR pages, CSS, or
  browser API clients in an app that has not already chosen a different pattern.
---

# Web architecture

Load this skill before adding pages, API clients, or a new frontend package. This is a small-product default, not a framework war. If the repo already picked Next, Vite, Svelte, or something else, stay on that toolchain. Do not propose a rewrite to match this file.

## Pattern

Treat each screen the way mobile MVVM treats a screen:

- **View:** the component that renders. It receives state and callbacks. It does not fetch.
- **State:** a view-model / store / hook that owns that screen's data and user actions.
- **Client:** HTTP (or tRPC, or fetch wrappers) in one module. Views never call `fetch` inline once a client exists for that resource.

The exact library names change. The split does not. If every page invents its own loading flag and its own `useEffect(fetch)`, the agent will keep doing that.

## Folder layout

```
src/
  app/ or pages/     — routing only
  features/<name>/
    <Name>Page.tsx
    use<Name>State.ts
  lib/
    api.ts           — shared client, types, error mapping
    auth.ts
```

Group by feature, not by type. Do not grow a 40-file `components/` folder of unrelated widgets plus a 40-file `hooks/` folder that only those widgets use.

## Libraries (default)

| Job | Use | Do not add unless already in the repo |
|---|---|---|
| Language | TypeScript | new `.js` pages in a TS app |
| UI | whatever the repo already uses | a second component library "just for this screen" |
| HTTP | existing client, or `fetch` behind `lib/api.ts` | Axios *and* fetch *and* ky in one feature |
| Styling | existing CSS approach | a new CSS-in-JS runtime next to Tailwind (or the reverse) |

Greenfield and nothing is chosen yet: TypeScript, one UI library, one fetch wrapper, one CSS approach. Write those three names into the *project* `CLAUDE.md` so sessions do not renegotiate them.

## Front end is not the whole product

If this web UI shares a product with iOS and Android (same users, same billing), the data model and auth contract live in the product spec, not only in `src/lib`. Do not invent a web-only user shape.
