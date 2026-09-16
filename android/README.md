# JalJeev — Android app

Native Android client for the JalJeev backend (SIH26176). Kotlin + Jetpack
Compose, Material 3, MapLibre Native. It talks to the same FastAPI server the
React frontend does — `POST /chat`, `/marine/state`, `/marine/quick-check`,
`/marine/safest-route`, `/marine/optimize-route`, `/marine/simulate/*` — and
adds the two things a browser tab cannot do: a background safety watch that
keeps running with the screen off, and OS-level warnings.

It computes nothing. Every number on every screen came from the deterministic
agents in `backend/app/agents/`; the app's job is to render them, including
the parts that say "we don't know".

## What's in it

| Tab | What it does | Endpoints |
|---|---|---|
| **Ask** | Conversational query with session continuity ("what about tomorrow?" resolves the earlier location server-side), optional attached GPS position, and an expandable **evidence receipt** under every answer — sources, factor lines, data gaps, rejected alternatives, confidence, decision id. | `POST /chat` |
| **Map** | OSM basemap, tap any point to run the full multi-source state for it, route overlay with risk-coloured waypoints, centre-on-me. | `GET /marine/state` |
| **Route** | Origin + radius, then either the fast 16-zone candidate scan (with the full "why not" list of vetoed alternatives) or the A* search over the H3 risk graph. | `GET /marine/safest-route`, `GET /marine/optimize-route` |
| **Watch** | Foreground-service safety monitor: takes your position on a fixed interval, re-runs the same hard-constraint checks, warns via notification the moment conditions where you actually are turn unsafe. | `GET /marine/quick-check` |
| **Settings** | Backend base URL (with a connection test), vessel profile, watch interval. | `GET /health` |

## Running it

1. **Start the backend** (from the repo root — see the root `CLAUDE.md`):
   ```bash
   docker compose up -d postgres redis
   ```
   then
   ```bash
   cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
   `--host 0.0.0.0` matters if you are running on a physical phone; `127.0.0.1`
   is only reachable from the laptop itself.

2. **Open `android/` in Android Studio** (Ladybug or newer) and let it sync.

3. **Point the app at your backend** — Settings tab:
   - Android emulator: `http://10.0.2.2:8000` (the default; `10.0.2.2` is the
     emulator's alias for the host's `127.0.0.1`).
   - Physical phone on the same Wi-Fi: `http://<laptop-LAN-IP>:8000`.
   - Tap **Save and test** — it calls `/health` and reports exactly what came
     back, including the failure text if it didn't.

4. Run. Grant location when asked (the Watch tab needs it; the Map and Ask
   tabs work without it).

**Demo tip** (from the root `CLAUDE.md`): run `python scripts/prewarm_demo.py`
about 10–15 minutes ahead so Redis is warm. Use offshore coordinates like
`17.65, 83.35` (Visakhapatnam, ~40–56 m depth) rather than a city name — a
geocoded city centre is on land and will correctly hard-veto.

## Build requirements

- **JDK 17** — `JAVA_HOME` must point at it. AGP 8.7 will not run on JDK 8.
- Android SDK: `platforms;android-35`, `build-tools;35.0.0`, `platform-tools`.
- `local.properties` with `sdk.dir=<path to SDK>` (gitignored, machine-local).

Building from the command line, without Android Studio:

```bash
./gradlew :app:assembleDebug :app:testDebugUnitTest
```

The debug APK lands in `app/build/outputs/apk/debug/app-debug.apk` (~59 MB —
unminified, and MapLibre ships native `.so` libraries for every ABI).

**Status: builds clean.** Verified on Windows with Microsoft OpenJDK 17.0.20.1,
Gradle 8.9, Android SDK platform 35 / build-tools 35.0.0 — zero errors, zero
warnings, 5/5 unit tests passing. All dependency versions in
`gradle/libs.versions.toml` resolve as pinned, MapLibre 11.5.0 included.

Not yet verified: **runtime**. Nothing has been installed on a device or
emulator, so this says the code compiles and its unit tests pass — not that
the map renders or that a screen survives first launch.

## Design decisions worth knowing

**Manual DI, not Hilt.** Six singletons in `AppContainer` (`JalJeevApplication.kt`).
Hilt would add a KSP round to every build and a Kotlin/AGP version matrix to
maintain, for a graph this size.

**Vetoes are rendered differently from scores.** `RiskLevel.Rejected` has its
own colour and no numeric badge, because the backend short-circuits before
scoring a vetoed candidate — its `factor_breakdown` is legitimately empty.
Showing it on the same 0–100 scale as a scored result would undo the exact
bug the two-stage pipeline was built to fix.

**Missing data is shown as missing.** `Reading()` renders `null` as
"not available", never `0`. A fabricated `0.0 m` wave height reads as a calm
sea. `missing[]`, `data_gaps[]` and the SST single-year-baseline caveat are
all surfaced verbatim rather than summarised away.

**Failures say what failed.** `MarineRepository` keeps the exception type and
message and puts them in the error card (root `CLAUDE.md` gotcha #4: a bare
`catch { null }` in this project once hid an instant HTTP 429 behind two
debugging sessions of "it's probably just slow").

**The watch does not read the cache.** `/marine/state` falls back to a
last-known-good cached answer when offline — labelled with its age. The safety
watch deliberately does not: a twenty-minute-old verdict presented as "you are
safe right now" is worse than saying the check failed.

**Two loops in the watch service, not one.** GPS updates write to a volatile
field; a separate timer reads it and calls the backend. Polling straight from
the location callback would tie request rate to GPS jitter and can exceed the
backend's 60-requests-per-minute limit.

**English only.** Navigation, actions and repeated labels are in
`res/values/strings.xml`, so a `values-hi/` copy translates the app's chrome.
The longer explanatory paragraphs inside Map, Route, Watch and Settings are
still inline in their composables — extract those into `strings.xml` first
when you add a language. Voice I/O (Android `SpeechRecognizer` /
`TextToSpeech`) is the natural next addition and needs no backend change.

## Tests

```bash
./gradlew :app:testDebugUnitTest
```

5 tests, all passing. `WireContractTest` checks the hand-mirrored wire models
against real backend response shapes — that absent measurements stay `null`
instead of defaulting to `0`, that a vetoed point parses as `REJECTED` with no
factor breakdown, and that an unknown risk level degrades instead of throwing.

## Not built

- Fishing / PFZ features — blocked on MOSDAC access, same as the backend.
- Voice input and output.
- Offline map tiles (MapLibre supports offline packs; the risk data itself
  still needs the backend).
- `/marine/simulate/*` has a typed client method but no screen yet — the
  "what if I leave 6 hours later?" panel is the obvious next screen.
