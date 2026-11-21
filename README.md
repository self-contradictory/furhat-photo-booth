# Furhat Photo Booth

A field study for ROBT 414. A Furhat robot stands in a busy university space next to a photo
booth. Its behaviour follows one of four conditions (see [EXPERIMENT.md](EXPERIMENT.md)). People
who take a photo scan a QR code, answer a short survey on their phone, and then download the photo.

How the parts connect, and which files each team member edits: [docs/INTERFACE.md](docs/INTERFACE.md).

## Quick start for teammates

You can run the whole booth on your own laptop with Virtual Furhat. No Cloudflare account is needed:
the web part runs locally with a local database.

1. Do sections 1, 2 (*Local development* only) and 3 below.
2. Edit your part:
   - **Robot behaviour** → `booth/conditions.json` (lines, gestures, photo face, countdown). Restart the
     orchestrator to load changes. Use `p` to preview a condition's photo face and `n` to make the robot
     react as if someone walked up. See [docs/INTERFACE.md](docs/INTERFACE.md) for every field.
   - **Survey** → `web/src/survey.json`. The local dev server reloads it by itself; open the link from a
     test photo's QR code (or http://localhost:3000/s/AAAAAAAAAA) to see it.
3. Commit and push. Publishing survey changes to the live site needs the Cloudflare account, so tell
   the account owner after you push; they run `npm run deploy`.

Things that are different locally:
- Virtual Furhat does not use your webcam to find people. Use `n`/`f`, or add a virtual person in the
  Furhat web interface (http://localhost:8080): double-click the area in front of the robot on the
  dashboard and drag the person closer or further away (type `r` first if you used `n`/`f`).
- Your `booth/.env` uses `BOOTH_SECRET=dev-secret`. The production secret is only needed on the
  deployment laptop and is shared privately, never committed.

| Folder | What it is |
| --- | --- |
| `booth/` | Python orchestrator on the MacBook: drives Furhat, serves the kiosk page, uploads photos |
| `web/` | Cloudflare Worker (TanStack Start): survey, photo download, D1 database, R2 photo storage |
| `scripts/export_spss.py` | Exports the results to SPSS (`analysis/data/sessions.sav`) |
| `docs/` | Interface contract and the observer tally sheet |

## Requirements

- macOS with [Miniforge/conda](https://github.com/conda-forge/miniforge), Python 3.12
- [Node.js](https://nodejs.org) 22+ and npm
- A [Cloudflare](https://dash.cloudflare.com) account (Workers, D1, R2) for the web part
- [Furhat SDK](https://furhat.io/downloads) with Virtual Furhat for testing; a physical Furhat for the study
- Python libraries: [furhat-realtime-api](https://pypi.org/project/furhat-realtime-api/),
  [aiohttp](https://docs.aiohttp.org), [segno](https://segno.readthedocs.io) (QR codes),
  [opencv-python](https://pypi.org/project/opencv-python/) (webcam check only),
  [pandas](https://pandas.pydata.org) and [pyreadstat](https://github.com/Roche/pyreadstat) (export only)

## 1. Python setup

```bash
conda create -n hri python=3.12         # once; skip if you already have a Python 3.12 env
conda activate hri
pip install -r booth/requirements.txt pandas pyreadstat
cp booth/.env.example booth/.env
```

For local testing, set these in `booth/.env`:

```
WORKER_URL=http://localhost:3000
BOOTH_SECRET=dev-secret
FURHAT_HOST=127.0.0.1
```

On deployment day, switch to `WORKER_URL=https://booth.sagyzdop.com` and the production `BOOTH_SECRET`.

## 2. Web part (Cloudflare Worker)

Local development:

```bash
cd web
npm install
echo "BOOTH_SECRET=dev-secret" > .dev.vars
npx wrangler d1 migrations apply DB --local   # re-run if database_id in wrangler.jsonc ever changes
npm run dev                             # http://localhost:3000
```

First deployment (once, already done for booth.sagyzdop.com, needs the Cloudflare account):

```bash
npx wrangler d1 create furhat-photo-booth        # put the printed database_id into wrangler.jsonc
npx wrangler r2 bucket create furhat-photo-booth
npx wrangler d1 migrations apply DB --remote
npx wrangler secret put BOOTH_SECRET              # a long random string; also goes in booth/.env
npm run deploy
```

Then add the custom domain `booth.sagyzdop.com` under the Worker's *Settings → Domains & Routes*
in the Cloudflare dashboard. After editing `src/survey.json`, run `npm run deploy` again.

## 3. Run the booth against Virtual Furhat

1. Start Virtual Furhat from the Furhat Launcher, open its web interface (http://localhost:8080),
   go to **Realtime API** and set *Access Level* to **Enabled without authentication**.
2. With `booth/.env` pointing at `WORKER_URL=http://localhost:3000` and the dev server running:

```bash
cd booth
python orchestrator.py --check          # every line should say PASS
python orchestrator.py --condition inviting
```

3. Open http://localhost:8000 in Chrome and allow camera access. Click **Take a photo** (or press **Space**).
   The preview and the saved photo are mirrored like a selfie camera. After the 10-second countdown a
   QR code appears; scanning it opens the survey (with the local dev server, open the printed URL on the
   same laptop instead, since your phone cannot reach `localhost`).

Terminal commands while it runs (type and press Enter):

| Key | Action |
| --- | --- |
| `1`–`4` | Switch condition: passive, inviting, complimenting, playful |
| `a` | Teleoperation: say the approach line right now, cutting off any line in progress (use it when someone walks up) |
| `i` | Teleoperation: say the current condition's idle (inviting) line right now, cutting off any line in progress, and restart the 20 s idle timer |
| `n` / `f` / `r` | Simulate a person arriving (press again for a new person) / nobody / back to real user tracking |
| `p` | Preview the current condition's photo face (held for `hold_s` seconds, no photo taken) |
| `s` | Status: condition, robot connection, closest person, pending uploads |
| `q` | Quit |

Every photo is saved in `booth/data/photos/` before it is uploaded. `booth/data/photos.csv` and
`booth/data/conditions.csv` are local backup logs with timestamps.

## 4. Deployment-day checklist

**Before you leave**
- [ ] Laptop and robot charged; Ethernet cable and USB-C Ethernet adapter packed; phone hotspot works
- [ ] `booth/.env` has `WORKER_URL=https://booth.sagyzdop.com` and the production `BOOTH_SECRET`
- [ ] Printed banner "Take a photo with Furhat! 📸", observer tally sheets ([docs/observer_sheet.md](docs/observer_sheet.md)), pen

**Network (about 8:20)**
1. Connect the robot to the MacBook with the Ethernet cable.
2. On the Mac: *System Settings → General → Sharing → Internet Sharing*: share from **Wi-Fi** to the
   **USB/Thunderbolt Ethernet** adapter, then turn it on. The robot gets an address such as `192.168.2.x`
   and internet access for its cloud voice.
3. Find the robot's IP on its own screen/web interface (or with `arp -a`) and put it in `booth/.env` as `FURHAT_HOST`.
4. Open `http://<robot-ip>:8080` and enable the **Realtime API** (*Enabled without authentication*), as in step 3.1.

**Pre-flight (about 8:30)**
```bash
conda activate hri && cd booth
python orchestrator.py --check
```
Fix anything marked FAIL. The first user payload printed shows that the robot's tracking works.

**Start (before 8:50)**
```bash
caffeinate -dis &                       # stop the Mac from sleeping
python orchestrator.py --condition <first condition>
```
- [ ] Chrome: open http://localhost:8000, allow the camera, enter full screen (Ctrl+Cmd+F), check the framing shows the person *and* Furhat
- [ ] Charger plugged in; Do Not Disturb on; auto-updates paused
- [ ] Walk up to the robot once: it should notice you (`person close` in the terminal) and speak

**During the day**
- At the start of each break window, type the condition number and note it on the observer sheet.
- If the terminal shows `UPLOADS FAILING`, switch the Mac's Wi-Fi to the phone hotspot. Photos are
  kept locally and upload by themselves when the connection returns.
- If the robot disconnects, the orchestrator reconnects every 5 s; the kiosk keeps working.

## 5. Export the data

```bash
python scripts/export_spss.py           # writes analysis/data/sessions.sav and sessions.csv
```

Look through the photos in R2 (or `booth/data/photos/`) and list the IDs of group photos in
`analysis/group_photos.csv` (a single `id` column) before the final export. They are flagged with
`group_photo = 1` and excluded from the analysis.

## Acknowledgements and AI use

The code and documentation in this repository were written with the help of Claude
(Anthropic's AI assistant, via Claude Code), then run and tested by the team. The Worker was
scaffolded with `create-cloudflare` (TanStack Start template). The survey uses the Godspeed
questionnaire (Bartneck et al., 2009) for likeability and perceived intelligence.
