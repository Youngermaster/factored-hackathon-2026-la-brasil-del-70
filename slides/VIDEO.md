# Recording the video pitch

The organizers require a short video that demonstrates the working solution and explains the core architectural decisions. The plan: a screen recording of this deck carries the argument, two short live clips of the app prove it works, and one narrator reads [script.md](script.md). Target length 3:30 to 4:00 (the narration measures 3:31 at 150 words per minute; animation and demo pauses add the rest).

## Shot list

Timestamps assume the narration is spoken over each animation, starting as the click lands. The click numbers match the `[click N]` cues in the script and the slide notes in presenter mode.

| Time | Segment | Source | What to click, what happens |
|---|---|---|---|
| 0:00 to 0:35 | Slide 1, hook | deck | Arrive: the row counter. Click 1 contact share, click 2 first-contact resolution (dispute in red), click 3 transcripts collapse, click 4 the four workflows |
| 0:35 to 1:22 | Slide 2, thesis | deck | Arrive: the customer message types in. Clicks 1 to 6: understand, decide, act and verify, injection bounces, escalate, thesis line. Let click 4 play fully before speaking |
| 1:22 to 1:42 | Demo A, dispute | app | See "Demo segments" |
| 1:42 to 2:16 | Slide 3, architecture | deck | Clicks 1 to 5: kernel, gateway, verifier, data platform, inward arrows |
| 2:16 to 2:52 | Slide 4, workflows | deck | Clicks 1 to 5: one workflow per click, then the depth bar |
| 2:52 to 3:07 | Demo B, card block and credit | app | See "Demo segments" |
| 3:07 to 3:33 | Slide 5, evidence | deck | Clicks 1 to 4. Record this slide only after phase 14 fills `data/metrics.yml` |
| 3:33 to 3:55 | Slide 6, close | deck | Clicks 1 to 3: route to operation, team, thesis and links. Hold the last frame 3 seconds |

If the cut runs long, trim in this order: the transcript beat of slide 1 (click 3), the depth bar of slide 4 (click 5), demo B's credit half. Never cut the thesis, the injection beat, or the limits.

## Recording the deck

1. `pnpm dev`, then open `http://localhost:3131` in Chrome on a 1920 x 1080 display (or a window sized to exactly 1920 x 1080). Browser zoom at 100%.
2. Press `f` for fullscreen and move the pointer off the screen: Slidev shows its navigation bar when the mouse moves.
3. Advance with the right arrow or space only. Never press left while recording: it rewinds the scene quickly and that motion ends up in the take.
4. Wait for each scene to come to rest (1.5 to 4 seconds per click) before the next click. The scene plays at real speed only on the live slide, so record the slide window, not the presenter view.
5. Record one slide per take (the seams between slides are 0.4 s, easy to cut on). OBS Studio at 1920 x 1080, 60 fps, or QuickTime screen recording, both work.

Presenter mode (`/#/presenter`) on a second screen shows the slide notes and the next click, useful when narrating live over the recording. Alternatively record the voice first, per section, then click the deck to the voice track.

## Demo segments

The demo clips come from the web app (`apps/web`) once it exists: the customer chat and the agent inbox with the glass box that renders the execution record (the glass box is planned for phase 13). Until then there is nothing to record; the slides say "illustrative turn" where they stand in for it.

| Clip | Length | Record | Must be visible |
|---|---|---|---|
| A, dispute (es-AR) | about 20 s | A customer disputes a charge written with slang ("15 lucas"), confirms, gets a case number; then one injection attempt in the same chat, refused | The chat and, side by side, the glass box: state, rule ids, the `create_dispute_case` call with its verification, the `injection_detected` intervention |
| B, card block (pt-BR) and credit | about 15 s | A protective card block in Portuguese with the step-up code and the verified read-back; then a credit eligibility question answered as indicative | The step-up prompt, the verified status, the eligibility reasons, the review path and the "indicative, not an offer" disclaimer; no risk estimate in the customer view |

Record the clips against the seeded demo data (`make seed`) with the provider the team chooses; if the model is not configured, the clip shows the deterministic fallback, and the narration must not claim otherwise. The demo data is synthetic, but keep document numbers and other identifiers off screen anyway. If the deployment exists by then, record against the deployed URL so the clip also proves the deployment.

## Before the final recording

- [ ] `pnpm check:content --strict` passes: every metric in `data/metrics.yml` is filled, including `deploy.url`.
- [ ] The `evidence` section of `script.md` says the measured numbers with their denominators.
- [ ] `pnpm check:fit` passes and `pnpm shots` looks right (`.shots/deck/`).
- [ ] The team reviewed the limits on slide 6 against the final state of the repository.
- [ ] The PDF is exported with `pnpm export:final`.

## Audio

- A quiet, soft-furnished room. A USB or lavalier microphone, or a phone held 20 cm from the mouth, beats a laptop microphone.
- Record at 48 kHz, 24-bit if possible. Leave 2 seconds of silence at the start of every take for noise reduction.
- One narrator for the whole video keeps it coherent; the team slide can name everyone.
- Speak at about 150 words per minute, the pace the script is timed for. Pause at each click.
- Clean-up: noise reduction, a gentle compressor, then normalize the loudness to -14 LUFS integrated with peaks under -1 dBTP. If you use a music bed, keep it at least 20 dB under the voice, or leave it out.

## Editing and export

- Timeline 1920 x 1080 at the recording frame rate (60 or 30 fps). Cut on the seams between slides.
- Put the demo clips at the timestamps above, full frame; a thin title in the deck's mono type ("live, es-AR") is enough labeling.
- Add captions from `script.md` (a subtitle file, or burned in). Many judges watch muted.
- Export H.264, High profile, 1920 x 1080, 12 to 16 Mbit/s, AAC 48 kHz at 192 kbit/s, MP4. Check the file plays in a browser before sending it.
- Name it `la-brasil-del-70-pitch.mp4`, and send it with the repository link, the deployment link and the PDF.
