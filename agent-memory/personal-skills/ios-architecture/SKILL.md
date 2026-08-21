---
name: ios-architecture
description: >-
  Default iOS and macOS app architecture: MVVM, SwiftUI, @Observable,
  async/await, URLSession. Use when creating or changing iOS, iPadOS, macOS,
  SwiftUI, ViewModels, Swift packages, or Xcode app targets that have not
  already chosen a different pattern.
---

# iOS architecture

Load this skill before adding screens, services, or Swift packages. Do not introduce a second pattern next to this one.

## Pattern

MVVM. SwiftUI views render state. An `@Observable` ViewModel holds UI state and talks to a data layer. Views do not call `URLSession` or SwiftData directly.

Do not put unrelated features on the auth object. One feature, one type.

New code: Swift concurrency (`async`/`await`, `Task`). Do not add Combine publishers for new flow. Apple's own agent prompt prefers async APIs over Combine; follow that for new work. Existing Combine can stay until you touch that file for another reason.

Use `@Observable` and `@State` for new ViewModels. Do not start new types as `ObservableObject` with `@Published` unless you are matching a surrounding module that is still on that API.

## Folder layout

```
App/                 — @main, App struct, root tabs
Features/<Feature>/
  <Feature>View.swift
  <Feature>ViewModel.swift
Data/
  API/               — URLSession clients, DTOs, mapping into domain types
  Persistence/       — SwiftData models or file stores
Domain/              — structs and protocols used by ViewModels (no SwiftUI)
```

Keep Views in the feature folder next to their ViewModel. Do not make a single `Views/` bucket that every screen dumps into.

## Libraries (default)

| Job | Use | Do not add unless already in the repo |
|---|---|---|
| UI | SwiftUI | UIKit for new full screens |
| State | `@Observable` | A third-party reactive framework for new screens |
| HTTP | `URLSession` | |
| Persistence | SwiftData when you need a store | Core Data stack from scratch for a small app |
| Images | AsyncImage, or one loader if the project already has it | A second image library |

No CocoaPods for new dependencies if Swift Package Manager already builds the app.

## Demo and review

If the app will go to TestFlight or App Review, load bundled JSON behind a demo flag (`--demo-mode` launch argument or an `AppEnvironment` value) so reviewers and visual checks see the same data. Wire this before the first upload.
