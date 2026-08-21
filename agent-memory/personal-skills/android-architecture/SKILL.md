---
name: android-architecture
description: >-
  Default Android app architecture: MVVM, three Gradle modules, Jetpack Compose,
  Hilt, Coil, Ktor, Room, DataStore. Use when creating or changing Android,
  Kotlin, Jetpack Compose, Gradle modules, Activities, ViewModels, or Android
  libraries in an app that has not already chosen a different pattern.
---

# Android architecture

Load this skill before adding screens, data sources, or modules. Do not introduce a second pattern next to this one.

## Pattern

MVVM. Views (Compose) render state. ViewModels hold UI state and map user actions to domain calls. Models and use cases live in `:domain`. Repository implementations live in `:data`.

Do not put business rules in composables. Do not put fitness goals on an `AuthenticationManager`. One feature, one home.

Initial load: the ViewModel receives an explicit action (`ScreenStarted`, refresh). Do not treat `LaunchedEffect(Unit)` as the place business work begins. See [Where Should Initial Load Logic Live in Jetpack Compose?](https://medium.com/gitconnected/where-should-initial-load-logic-live-in-jetpack-compose).

Concurrency: Kotlin coroutines and Flow only. Do not add RxJava or a second event bus.

Threading: `viewModelScope.launch` stays on Main. Repositories are main-safe. Room, DataStore, and Ktor/OkHttp suspend calls already hop off Main; do not wrap them in extra `withContext(IO)` unless the API is blocking.

## Modules

```
:domain  — models, use case classes, repository interfaces. Zero Android imports.
:data    — repository implementations, Ktor, Room, DataStore
:app     — Compose UI, Hilt, navigation, ViewModels
```

Dependencies:

```
:app  → :domain
:app  → :data
:data → :domain
:domain → (nothing)
```

UI in `:app` never imports `:data` types. Only domain types cross that boundary.

Feature layout inside `:app`:

```
ui/<feature>/
  <Feature>Screen.kt
  <Feature>ViewModel.kt
  <Feature>UiState.kt
```

Keep a composable that only lays out UI separate from the screen that collects ViewModel state, when the layout is worth previewing or testing on its own.

## Libraries (default)

| Job | Use | Do not add unless already in the repo |
|---|---|---|
| UI | Jetpack Compose | View XML for new screens |
| DI | Hilt | A second DI framework |
| Images | Coil | Glide or Picasso on new Compose screens |
| HTTP | Ktor | The Google/Firebase SDK when the spec says talk HTTP |
| Local DB | Room | |
| Key-value | DataStore | SharedPreferences for new keys |
| Navigation | type-safe Compose Navigation | string routes for new graphs |

If the repo already uses Retrofit, stay on Retrofit. Do not mix Ktor and Retrofit in one feature.

## Demo and review

If the app will go to Play review, swap the data source behind a demo flag rather than depending on a live backend that ages. Bundled JSON fixtures, Hilt module swap or `BuildConfig`. Wire this before the first store submission.
