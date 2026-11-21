# Booth interface

How the pieces talk to each other, and which file each team member owns.

## Architecture

```
 Physical Furhat ──Ethernet──► MacBook (Internet Sharing: Wi-Fi → Ethernet)
   Realtime API :9000            │
                                 │  booth/orchestrator.py  (conda env `hri`)
                                 │   ├─ robot.py      ← reads booth/conditions.json
                                 │   ├─ uploader.py   → data/photos/ then PUT to Worker
                                 │   └─ kiosk page    http://localhost:8000  (+ WebSocket /ws)
                                 │
                                 └──Wi-Fi (or phone hotspot)──► Cloudflare Worker  booth.sagyzdop.com
                                                                 ├─ D1  sessions table
                                                                 └─ R2  photos/<id>.jpg
 Participant's phone ── scans QR ──► booth.sagyzdop.com/s/<id>  (survey → photo download)
 Second laptop ── Furhat Studio http://<robot-ip> ──► Furhat says the invite phrases by hand
```

The booth MacBook sets gaze, the photo phrase and the photo face, and records the condition. The
invite phrases are said from Furhat Studio on the second laptop. The Worker never talks to the robot.

## Who edits what

| File | Owner | What it controls |
| --- | --- | --- |
| `booth/conditions.json` | robot behaviour | Gaze per main condition, phrase and face per photo action, voice, countdown, proximity thresholds |
| `web/src/survey.json` | survey | Survey questions, scales, answer options |
| everything else | connection | Orchestrator, kiosk, Worker, export |

Neither JSON file needs code changes. Restart the orchestrator after editing `conditions.json`.
Redeploy the Worker (`npm run deploy` in `web/`) after editing `survey.json`, and raise its
`version` if questions change after data collection has started.

## conditions.json

The study is 3 × 2: a **main condition** (`conditions`: passive, inviting, complimenting) and a
**photo action** (`actions`: smile, silly). Both are switched from the booth terminal, and every
photo is stored with `condition = "<condition>/<action>"`, e.g. `inviting/silly`.

**Main conditions** only set `gaze` (look at the closest detected person while they are near) and
`microexpressions` (Furhat's small idle face movements; off for passive). Their invite phrases are
not in this file: they are said by hand from Furhat Studio.

**Actions** run when someone presses the photo button:

| Field | Meaning |
| --- | --- |
| `lines` | Said the moment the button is pressed, as the countdown (`countdown_s`, 10 s) starts. One is picked at random |
| `gesture` | Optional Furhat built-in played with the line (`Smile`, `BigSmile`, `Wink`, ...) |
| `face` | The face for the photo, started `lead_s` seconds before the shutter and held for `hold_s` seconds. Keep `hold_s` longer than `lead_s` so it is still on when the photo is taken |

**The photo face (`face`).** Gestures always animate in and straight back out, so they cannot
hold an expression. The action instead sets Furhat's face parameters directly, e.g.
`{"SMILE_OPEN": 1.0, "BROW_UP_LEFT": 0.5}` (values 0 to 1), holds them for `hold_s` seconds, then
sets them back to 0. Names are Furhat's basic and ARKit-style face parameters (`SMILE_OPEN`,
`SMILE_CLOSED`, `SURPRISE`, `BROW_UP_LEFT`, `BROW_DOWN_RIGHT`, `EYE_SQUINT_LEFT`, `JAW_OPEN`,
`MOUTH_LEFT`, `TONGUE_OUT`, ...). Furhat silently ignores names it does not know, so check every
change by eye: run the orchestrator, switch to the action and type `p` to preview its face.

Person detection only moves the gaze; it never makes the robot speak. Furhat detects **faces**
with its camera, so it only sees people who face it. A person counts as **near** within
`approach_distance_m` (1.5 m) and as **gone** once nobody has been within `leave_distance_m` (2.0 m)
for `leave_after_s` (3 s). The gap stops the gaze flickering when someone stands at the edge.

## Kiosk ⇄ orchestrator (WebSocket `/ws`, JSON)

| Direction | Message | Meaning |
| --- | --- | --- |
| kiosk → orchestrator | `{"type": "photo_requested"}` | Button (or Space) pressed on the live screen |
| orchestrator → kiosk | `{"type": "countdown", "seconds": 10}` | Start the on-screen countdown (the robot's action phrase starts now) |
| kiosk → orchestrator | `POST /capture` (JPEG body) | Returns `{id, url, qr_svg}` |
| kiosk → orchestrator | `{"type": "reset"}` | The QR screen was cleared; ready for the next person |

## Orchestrator → Worker (HTTPS)

| Route | Auth | Purpose |
| --- | --- | --- |
| `PUT /api/sessions/<id>` | `x-booth-secret` | Upload the JPEG with `x-condition` (`condition/action`) and `x-captured-at`. Idempotent |
| `DELETE /api/sessions/<id>` | `x-booth-secret` | Used only by `--check` to remove its test row |
| `GET /api/sessions/<id>` | public | `{submitted, hasPhoto}` for the survey page; never exposes the condition |
| `POST /api/sessions/<id>/survey` | public | `{answers}`; validated against `survey.json`; only once per id |
| `GET /api/sessions/<id>/photo` | public | The JPEG, only after the survey is submitted. `?download=1` forces a download |

Session IDs are 10 random base62 characters, generated on the MacBook, so the QR code is shown
immediately even while offline. The survey and the upload can arrive in either order.
