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
```

The robot is driven only from the MacBook. The Worker never talks to the robot.

## Who edits what

| File | Owner | What it controls |
| --- | --- | --- |
| `booth/conditions.json` | robot behaviour | Lines, gestures, gaze, voice, proximity thresholds for the 5 conditions |
| `web/src/survey.json` | survey | Survey questions, scales, answer options |
| everything else | connection | Orchestrator, kiosk, Worker, export |

Neither JSON file needs code changes. Restart the orchestrator after editing `conditions.json`.
Redeploy the Worker (`npm run deploy` in `web/`) after editing `survey.json`, and raise its
`version` if questions change after data collection has started.

## conditions.json

Each condition has four **moments**. Every moment is optional; an empty `{}` means silence.

| Moment | When | Notes |
| --- | --- | --- |
| `idle` | Nobody is close, repeated every `every_s` seconds | |
| `approach` | Once, when a person comes within `approach_distance_m` | Waits for the current line to finish |
| `photo` | The moment someone presses Space; the 3-second countdown starts at the same time | The only moment that interrupts a line in progress |
| `after` | The photo is taken and the QR code is shown | |

Each moment takes `lines` (one is picked at random) and an optional `gesture`
(Furhat built-ins such as `Smile`, `BigSmile`, `Nod`, `Wink`, `Surprise`, `Thoughtful`, `BrowRaise`).

Per condition: `gaze` (look at the closest person while they are near) and
`microexpressions` (Furhat's small idle face movements; off for the passive condition).

A person counts as **near** within `approach_distance_m` (1.5 m) and as **gone** once nobody
has been within `leave_distance_m` (2.0 m) for `leave_after_s` (3 s). The gap stops the robot
flickering between states when someone stands at the edge.

## Kiosk ⇄ orchestrator (WebSocket `/ws`, JSON)

| Direction | Message | Meaning |
| --- | --- | --- |
| kiosk → orchestrator | `{"type": "photo_requested"}` | Space pressed on the live screen |
| orchestrator → kiosk | `{"type": "countdown", "seconds": 3}` | Start the on-screen countdown (the robot's photo line starts now) |
| kiosk → orchestrator | `POST /capture` (JPEG body) | Returns `{id, url, qr_svg}`; the robot says its `after` line |
| kiosk → orchestrator | `{"type": "reset"}` | The QR screen was cleared; back to idle/approach |

## Orchestrator → Worker (HTTPS)

| Route | Auth | Purpose |
| --- | --- | --- |
| `PUT /api/sessions/<id>` | `x-booth-secret` | Upload the JPEG with `x-condition` and `x-captured-at`. Idempotent |
| `DELETE /api/sessions/<id>` | `x-booth-secret` | Used only by `--check` to remove its test row |
| `GET /api/sessions/<id>` | public | `{submitted, hasPhoto}` for the survey page; never exposes the condition |
| `POST /api/sessions/<id>/survey` | public | `{answers}`; validated against `survey.json`; only once per id |
| `GET /api/sessions/<id>/photo` | public | The JPEG, only after the survey is submitted. `?download=1` forces a download |

Session IDs are 10 random base62 characters, generated on the MacBook, so the QR code is shown
immediately even while offline. The survey and the upload can arrive in either order.
