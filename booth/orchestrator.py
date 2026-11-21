"""Furhat Photo Booth orchestrator.

One process on the MacBook that ties everything together:
  - serves the kiosk page at http://localhost:8000 and talks to it over a WebSocket
  - drives Furhat through the Realtime API (robot.py, scripted by conditions.json)
  - saves each photo locally and uploads it to the Cloudflare Worker (uploader.py)
  - takes operator commands from the terminal (switch condition, simulate a person)

Run:   python orchestrator.py                # normal operation
       python orchestrator.py --check        # pre-flight check before deployment
See README.md for setup and the deployment-day checklist.
"""
import argparse
import asyncio
import csv
import json
import math
import os
import secrets
import string
import sys
import threading
from datetime import datetime, timezone

import aiohttp
import segno
from aiohttp import web

from robot import Robot, load_conditions
from uploader import Uploader

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
ID_ALPHABET = string.ascii_letters + string.digits


def load_env(path):
    """Read KEY=VALUE lines from booth/.env into os.environ (without overriding)."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def log(message):
    print(f"{datetime.now():%H:%M:%S}  {message}", flush=True)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_session_id():
    # Matches the Worker's ID check: 10 base62 characters, unguessable enough for a photo link.
    return "".join(secrets.choice(ID_ALPHABET) for _ in range(10))


def append_csv(name, row):
    """Local backup logs in data/: every photo and every condition switch, with timestamps."""
    path = os.path.join(DATA_DIR, name)
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row))
        if new:
            writer.writeheader()
        writer.writerow(row)


class Booth:
    def __init__(self, args, conditions):
        self.args = args
        self.condition_names = list(conditions["conditions"])
        self.countdown_s = conditions.get("countdown_s", 10)
        self.robot = Robot(args.furhat_host, conditions, log)
        self.uploader = Uploader(os.path.join(DATA_DIR, "photos"), args.worker_url, args.secret, log)
        self.kiosks = set()
        self.busy = False  # a photo is in progress or its QR code is on screen

    # ---- kiosk WebSocket ------------------------------------------------------------

    async def ws_handler(self, request):
        ws = web.WebSocketResponse(heartbeat=10)
        await ws.prepare(request)
        self.kiosks.add(ws)
        log("kiosk connected")
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self.on_kiosk_message(json.loads(msg.data))
        finally:
            self.kiosks.discard(ws)
            log("kiosk disconnected")
        return ws

    async def on_kiosk_message(self, event):
        kind = event.get("type")
        if kind == "photo_requested" and not self.busy:
            self.busy = True
            log("photo requested")
            await self.broadcast({"type": "countdown", "seconds": self.countdown_s})
            await self.robot.photo_started(self.countdown_s)
        elif kind == "reset":
            self.busy = False
            self.robot.kiosk_reset()

    async def broadcast(self, event):
        for ws in list(self.kiosks):
            await ws.send_json(event)

    # ---- HTTP ---------------------------------------------------------------------------

    async def capture_handler(self, request):
        """The kiosk posts the captured JPEG here; we answer with the QR code for its survey."""
        jpeg = await request.read()
        session_id = new_session_id()
        captured_at = now_iso()
        condition = self.robot.condition
        self.uploader.save(session_id, jpeg, condition, captured_at)
        append_csv("photos.csv", {"id": session_id, "condition": condition, "captured_at": captured_at})

        url = f"{self.args.worker_url.rstrip('/')}/s/{session_id}"
        # omitsize keeps the viewBox, so the kiosk's CSS can scale the code without shifting it
        qr_svg = segno.make(url, error="m").svg_inline(border=2, omitsize=True)
        log(f"photo {session_id} taken ({condition})  survey: {url}")
        await self.robot.photo_taken()
        return web.json_response({"id": session_id, "url": url, "qr_svg": qr_svg})

    async def index_handler(self, _request):
        # no-store: a plain reload always picks up edits to the kiosk page
        return web.FileResponse(os.path.join(HERE, "kiosk", "index.html"),
                                headers={"Cache-Control": "no-store"})

    # ---- operator terminal ----------------------------------------------------------

    def print_help(self):
        names = "  ".join(f"{i}={n}" for i, n in enumerate(self.condition_names, 1))
        print(f"\nCommands:  {names}\n"
              "           a=approach now (say the approach line immediately, interrupting)\n"
              "           i=idle now (say the idle line immediately, interrupting)\n"
              "           n=simulate person near  f=simulate nobody  r=real tracking\n"
              "           p=preview the photo face of the current condition\n"
              "           s=status  h=help  q=quit\n", flush=True)

    async def on_command(self, cmd):
        if cmd.isdigit() and 1 <= int(cmd) <= len(self.condition_names):
            name = self.condition_names[int(cmd) - 1]
            await self.robot.set_condition(name)
            append_csv("conditions.csv", {"switched_at": now_iso(), "condition": name})
        elif cmd == "a":
            if not self.robot.connected:
                log("robot not connected")
            else:
                await self.robot.approach_now()
        elif cmd == "i":
            if not self.robot.connected:
                log("robot not connected")
            else:
                await self.robot.idle_now()
        elif cmd == "n":
            self.robot.simulate(1.0)
            log("simulating a person arriving at 1.0 m")
        elif cmd == "f":
            self.robot.simulate(math.inf)
            log("simulating nobody")
        elif cmd == "r":
            self.robot.simulate(None)
            log("using real user tracking")
        elif cmd == "p":
            if (self.robot.behaviour.get("pose") or {}).get("face"):
                log(f"previewing the {self.robot.condition} photo face")
                self.robot.preview_pose()
            else:
                log(f"{self.robot.condition} has no photo face")
        elif cmd == "s":
            log(f"condition={self.robot.condition}  robot={'connected' if self.robot.connected else 'DISCONNECTED'}"
                f"  near={self.robot.near}  closest={self.robot.closest}  kiosks={len(self.kiosks)}"
                f"  pending_uploads={len(self.uploader.pending())}")
        elif cmd == "q":
            return False
        elif cmd:
            self.print_help()

    async def read_terminal(self):
        # A daemon thread reads stdin so a blocked readline never stops Ctrl+C from exiting.
        loop = asyncio.get_running_loop()
        lines = asyncio.Queue()

        def reader():
            for line in sys.stdin:
                loop.call_soon_threadsafe(lines.put_nowait, line)

        threading.Thread(target=reader, daemon=True).start()
        while await self.on_command((await lines.get()).strip().lower()) is not False:
            pass

    # ---- main ------------------------------------------------------------------------------

    async def run(self):
        app = web.Application(client_max_size=20 * 1024 * 1024)
        app.router.add_get("/", self.index_handler)
        app.router.add_get("/ws", self.ws_handler)
        app.router.add_post("/capture", self.capture_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "localhost", self.args.port).start()

        await self.robot.set_condition(self.args.condition or self.condition_names[0])
        append_csv("conditions.csv", {"switched_at": now_iso(), "condition": self.robot.condition})
        log(f"kiosk at http://localhost:{self.args.port}  worker {self.args.worker_url}")
        self.print_help()
        # Runs until the operator types q; the robot and uploader loops never end on their own.
        tasks = [asyncio.create_task(t) for t in (self.robot.run(), self.uploader.run(), self.read_terminal())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in tasks:
                t.cancel()
            await runner.cleanup()


# ---- pre-flight check --------------------------------------------------------------------------

async def check(args, conditions):
    """Exercise every link once: robot, webcam, Worker upload -> survey -> photo -> delete."""
    ok = True

    def result(name, passed, detail=""):
        nonlocal ok
        ok &= passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}  {detail}", flush=True)

    print(f"Checking robot at {args.furhat_host} ...")
    from furhat_realtime_api import AsyncFurhatClient
    try:
        client = AsyncFurhatClient(args.furhat_host)
        client.set_logging_level(40)
        await asyncio.wait_for(client.connect(), 10)
        result("robot connects", True)
        voice = conditions.get("voice")
        status = await client.request_voice_config(voice_id=voice) if voice else await client.request_voice_status()
        result("voice", status.get("voice_id") == voice or not voice, status.get("voice_id", ""))
        await client.request_speak_text("Photo booth check. Can you hear me?", wait=True)
        result("robot speaks (did you hear it?)", True)
        users = await client.request_users_once()
        people = users.get("users") or []
        result("user tracking responds", True, f"{len(people)} user(s) visible")
        if people:
            print(f"         first user payload: {json.dumps(people[0])[:300]}")
        await client.disconnect()
    except Exception as e:
        result("robot", False, repr(e))

    # Only a warning: the kiosk uses the browser's camera permission, not the terminal's,
    # so the real test is seeing the live preview on the kiosk page.
    print("Checking webcam ...")
    jpeg = None
    try:
        import cv2
        cam = cv2.VideoCapture(0)
        grabbed, frame = cam.read()
        cam.release()
        if grabbed:
            jpeg = cv2.imencode(".jpg", frame)[1].tobytes()
            print(f"  [PASS] webcam gives a frame  {frame.shape[1]}x{frame.shape[0]}")
    except Exception:
        pass
    if jpeg is None:
        print("  [WARN] terminal cannot read the webcam; confirm the live preview on the kiosk page instead")
        # still test the Worker, with a 1x1 image
        import base64
        jpeg = base64.b64decode(
            "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////"
            "////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA=")

    base = args.worker_url.rstrip("/")
    print(f"Checking Worker at {base} ...")
    session_id = new_session_id()
    with open(os.path.join(HERE, "..", "web", "src", "survey.json")) as f:
        survey = json.load(f)
    answers = {}
    for section in survey["sections"]:
        for item in section["items"]:
            if item["type"] == "scale":
                answers[item["id"]] = item["min"]
            elif item["type"] == "choice":
                answers[item["id"]] = item["options"][0]["value"]
    secret = {"x-booth-secret": args.secret}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as http:
            async with http.put(f"{base}/api/sessions/{session_id}", data=jpeg, headers={
                    **secret, "x-condition": "check", "x-captured-at": now_iso(),
                    "content-type": "image/jpeg"}) as r:
                result("upload with secret", r.status == 200, f"HTTP {r.status}")
            async with http.get(f"{base}/api/sessions/{session_id}/photo") as r:
                result("photo locked before survey", r.status == 403, f"HTTP {r.status}")
            async with http.post(f"{base}/api/sessions/{session_id}/survey", json={"answers": answers}) as r:
                result("survey submits", r.status == 200, f"HTTP {r.status}")
            async with http.get(f"{base}/api/sessions/{session_id}/photo") as r:
                result("photo downloads after survey", r.status == 200, f"HTTP {r.status}")
            async with http.delete(f"{base}/api/sessions/{session_id}", headers=secret) as r:
                result("test session deleted", r.status == 200, f"HTTP {r.status}")
    except Exception as e:
        result("worker reachable", False, repr(e))

    print("\nALL CHECKS PASSED" if ok else "\nSOME CHECKS FAILED: fix them before opening the booth")
    return 0 if ok else 1


def main():
    load_env(os.path.join(HERE, ".env"))
    conditions = load_conditions(os.path.join(HERE, "conditions.json"))
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="run the pre-flight check and exit")
    parser.add_argument("--condition", choices=list(conditions["conditions"]), help="condition to start in")
    parser.add_argument("--port", type=int, default=8000, help="kiosk port (default 8000)")
    parser.add_argument("--furhat-host", default=os.environ.get("FURHAT_HOST", "127.0.0.1"))
    parser.add_argument("--worker-url", default=os.environ.get("WORKER_URL", "http://localhost:3000"))
    parser.add_argument("--secret", default=os.environ.get("BOOTH_SECRET", ""))
    args = parser.parse_args()
    if not args.secret:
        parser.error("BOOTH_SECRET is not set (put it in booth/.env)")

    os.makedirs(DATA_DIR, exist_ok=True)
    if args.check:
        sys.exit(asyncio.run(check(args, conditions)))
    try:
        asyncio.run(Booth(args, conditions).run())
    except (KeyboardInterrupt, SystemExit):
        log("booth stopped")


if __name__ == "__main__":
    main()
