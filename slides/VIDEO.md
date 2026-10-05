# Recording the video pitch

The organizers require a video pitch **no longer than 3:00**, demo footage included, that demonstrates the working solution and explains the core architectural decisions. The cut targets 2:50: four slides of the deck (1, 3, 5, 6) carry the argument, four live segments of the app prove it works, and the four members of La Brasil del 70 share the narration.

| What | Where |
|---|---|
| The timed shot list: every segment's start and end, what is on screen, the exact clicks and commands, who speaks | [docs/demo/video-plan.md](../docs/demo/video-plan.md), the single source of truth for the cut |
| The spoken words, by speaker, with word counts and a rehearsal checklist | [docs/demo/video-monologue.md](../docs/demo/video-monologue.md), identical to [script.md](script.md) |
| The three cases to rehearse, with the exact messages and what to point at | [docs/demo/practice-cases.md](../docs/demo/practice-cases.md) |

`pnpm check:content` fails when the narration passes 3:00 at 150 words per minute or when the two narration files drift apart. This page covers how to record: the deck, the voices, the edit, and the export.

## Recording the deck

1. `pnpm dev`, then open `http://localhost:3131` in Chrome on a 1920 x 1080 display (or a window sized to exactly 1920 x 1080). Browser zoom at 100%.
2. Press `f` for fullscreen and move the pointer off the screen: Slidev shows its navigation bar when the mouse moves.
3. Advance with the right arrow or space only. Never press left while recording: it rewinds the scene quickly and that motion ends up in the take.
4. Wait for each scene to come to rest (1.5 to 4 seconds per click) before the next click. The scene plays at real speed only on the live slide, so record the slide window, not the presenter view.
5. Record one slide per take (the seams between slides are 0.4 s, easy to cut on). OBS Studio at 1920 x 1080, 60 fps, or QuickTime screen recording, both work. Slide 6 is recorded whole and cut in the edit (the video plan says which beats stay).

Presenter mode (`/#/presenter`) on a second screen shows the slide notes and the next click. The simplest workflow: record the voices first, per segment, then click the deck and drive the app to the voice track.

## Recording the app

The live segments come from the web app at 1440 px wide with the glass box open beside the chat, the agent console, the evaluator console, Jaeger, and Grafana. Which stack to record on (the deployed demo, which runs the current `main` with Azure OpenAI, or one local stack on the same commit), the setup commands, and the session-language and risk-tier notes are in the [video plan](../docs/demo/video-plan.md). Writes persist: record right after a fresh seed, and play the card block once per seed.

## Before the final recording

- [ ] `pnpm check:content --strict` passes (every metric filled, no placeholder).
- [ ] `pnpm check:fit` passes and `pnpm shots` looks right (`.shots/deck/`).
- [ ] Every live case of [practice-cases.md](../docs/demo/practice-cases.md) played once on the recording stack, and the Grafana panels the plan names show non-zero values.
- [ ] The team reviewed the limits and the next steps on slide 6 against the final state of the repository, and the names and roles on the team frame (they match the README team table).
- [ ] The PDF is exported with `pnpm export:final`: `la-brasil-del-70-pitch.pdf` has exactly six pages, one per main slide (the 32-page build-up version and the appendix are separate files).

## Audio

- A quiet, soft-furnished room. A USB or lavalier microphone, or a phone held 20 cm from the mouth, beats a laptop microphone. All four speakers use the same setup, so the voices match.
- Record at 48 kHz, 24-bit if possible. Leave 2 seconds of silence at the start of every take for noise reduction.
- Speak at about 150 words per minute, the pace the script is timed for. Pause at each click.
- Clean-up: noise reduction, a gentle compressor, then normalize the loudness to -14 LUFS integrated with peaks under -1 dBTP, per speaker first so the hand-offs do not jump in level. If you use a music bed, keep it at least 20 dB under the voice, or leave it out.

## Editing and export

- Timeline 1920 x 1080 at the recording frame rate (60 or 30 fps). Cut on the seams between slides, and cut the waiting time in the live segments (typing, model replies), never the words.
- The final cut must measure 3:00 or less; aim for 2:50.
- Label the live segments with a thin title in the deck's mono type ("live, es-MX", "live, pt-BR", "live, deployed demo", or "live, local stack" when recorded locally).
- Add captions from the monologue (a subtitle file, or burned in). Many judges watch muted.
- Export H.264, High profile, 1920 x 1080, 12 to 16 Mbit/s, AAC 48 kHz at 192 kbit/s, MP4. Check the file plays in a browser before sending it.
- Name it `la-brasil-del-70-pitch.mp4`, and send it with the repository link, the deployment link, and the six-page pitch PDF.
