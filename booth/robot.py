"""Furhat behaviour for the photo booth.

The robot never converses. It speaks scripted lines from conditions.json at four
moments (idle, approach, photo, after) and optionally looks at the closest person.
All the content lives in conditions.json; this file only decides *when* to speak.
"""
import asyncio
import json
import math
import random
import time

from furhat_realtime_api import AsyncFurhatClient

TICK_S = 0.25  # how often the behaviour loop re-evaluates the situation
SPEAK_TIMEOUT_S = 30.0  # treat a line as finished if speak.end never arrives
RECONNECT_S = 5.0


def load_conditions(path):
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg


def user_distance(user):
    """Distance in metres from the robot to one tracked user, or None if unknown.

    Furhat reports positions in metres with z pointing forward from the robot.
    The exact field names are read defensively so a firmware difference only
    disables proximity instead of crashing the booth.
    """
    loc = user.get("location") or user.get("position") or user.get("head") or {}
    if isinstance(loc, dict) and "z" in loc:
        return math.hypot(float(loc.get("x", 0.0)), float(loc["z"]))
    return None


class Robot:
    def __init__(self, host, conditions, log):
        self.host = host
        self.cfg = conditions
        self.log = log
        self.client = None
        self.connected = False
        self.condition = next(iter(conditions["conditions"]))

        # Proximity state
        self.near = False
        self.closest = None          # metres to the closest tracked user, None if nobody
        self.last_seen_close = 0.0   # last time someone was within leave_distance_m
        self.simulated = None        # operator override from the terminal: metres or None
        self.first_users_payload_logged = False

        # Speech state
        self.speaking = False
        self.speak_started = 0.0
        self.pending = None          # a moment waiting for the current line to finish
        self.last_idle = 0.0
        self.in_photo = False        # between photo_started and kiosk reset
        self.pose_task = None        # scheduled photo pose during the countdown
        self.pose_until = 0.0        # the after-photo moment waits until the pose has been held

    # ---- public API used by the orchestrator ------------------------------------

    @property
    def behaviour(self):
        return self.cfg["conditions"][self.condition]

    async def set_condition(self, name):
        self.condition = name
        self.pending = None
        self.last_idle = 0.0
        self.near = False  # anyone already standing there counts as a new arrival in the new condition
        self._cancel_pose()
        if self.connected:
            await self._safe(self.client.request_speak_stop())
            await self._apply_face()
            await self._look_ahead()
        self.log(f"condition -> {name}")

    async def photo_started(self, countdown_s):
        """The participant pressed the button: a countdown of countdown_s seconds starts now.

        The photo line plays immediately. The pose (the face for the picture) starts
        lead_s seconds before the shutter and is held for hold_s seconds, so it is
        on Furhat's face when the frame is captured even if the kiosk lags a little.
        """
        self.in_photo = True
        self.pending = None
        await self._say("photo", interrupt=True)
        pose = self.behaviour.get("pose") or {}
        if pose:
            self._cancel_pose()
            delay = max(0.0, countdown_s - pose.get("lead_s", 3.0))
            self.pose_task = asyncio.create_task(self._pose_after(delay))

    async def photo_taken(self):
        """The photo is captured and the QR code is on screen."""
        self.pending = "after"

    def kiosk_reset(self):
        """The QR screen was cleared; go back to the idle/approach behaviour."""
        self.in_photo = False
        self.last_idle = time.monotonic()
        self.pose_until = 0.0
        self._cancel_pose()

    async def approach_now(self):
        """Operator command (teleoperation): react to a person right now.

        Unlike automatic detection, this cuts off any line in progress, so the
        robot turns to the person immediately. The person then counts as near,
        so detection does not repeat the approach line while they stay.
        """
        if self.in_photo:
            self.log("photo in progress, approach skipped")
            return
        self.near = True
        self.last_seen_close = time.monotonic()
        self.pending = None
        if self.behaviour.get("gaze"):
            await self._safe(self.client.request_attend_user("closest"))
        await self._say("approach", interrupt=True)

    def simulate(self, distance):
        """Operator override for testing without a real person.

        A distance in metres, math.inf for "nobody there", or None to use real tracking.
        """
        self.simulated = distance
        if distance not in (None, math.inf):
            self.near = False  # pressing `n` again simulates a new person arriving

    # ---- connection ---------------------------------------------------------------

    async def run(self):
        """Connect and keep the behaviour loop running, reconnecting if the robot drops."""
        while True:
            try:
                self.client = AsyncFurhatClient(self.host)
                self.client.set_logging_level(40)  # errors only; the booth prints its own log
                await self.client.connect()
                self.connected = True
                self.log(f"robot connected at {self.host}")
                await self._setup()
                while self.client.is_connected:
                    await self._tick()
                    await asyncio.sleep(TICK_S)
                self.log("robot connection lost")
            except asyncio.CancelledError:
                raise
            except Exception as e:  # keep the kiosk alive whatever the robot does
                self.log(f"robot error: {e!r}")
            self.connected = False
            self.speaking = False
            await asyncio.sleep(RECONNECT_S)

    async def _setup(self):
        c = self.client
        c.add_handler("response.speak.start", self._on_speak_start)
        c.add_handler("response.speak.end", self._on_speak_end)
        c.add_handler("response.users.data", self._on_users)
        voice = self.cfg.get("voice")
        if voice:
            await self._safe(c.request_voice_config(voice_id=voice))
        await self._apply_face()
        await self._look_ahead()
        await c.request_users_start()

    # ---- event handlers -----------------------------------------------------------

    async def _on_speak_start(self, _event):
        self.speaking = True

    async def _on_speak_end(self, _event):
        self.speaking = False

    async def _on_users(self, event):
        users = event.get("users") or []
        if users and not self.first_users_payload_logged:
            # Printed once so the real robot's payload format can be checked on the day.
            self.log(f"first user payload: {json.dumps(users[0])[:300]}")
            self.first_users_payload_logged = True
        distances = [d for d in (user_distance(u) for u in users) if d is not None]
        self.closest = min(distances) if distances else None

    # ---- behaviour loop -------------------------------------------------------------

    async def _tick(self):
        now = time.monotonic()
        prox = self.cfg["proximity"]
        closest = self.simulated if self.simulated is not None else self.closest
        if closest == math.inf:  # simulated "nobody there"
            closest = None

        if closest is not None and closest <= prox["leave_distance_m"]:
            self.last_seen_close = now

        if not self.near and closest is not None and closest <= prox["approach_distance_m"]:
            self.near = True
            self.log(f"person close ({closest:.1f} m)")
            if self.behaviour.get("gaze"):
                await self._safe(self.client.request_attend_user("closest"))
            if not self.in_photo:
                self.pending = "approach"
        elif self.near and now - self.last_seen_close >= prox["leave_after_s"]:
            self.near = False
            self.log("person left")
            await self._look_ahead()
            if self.pending == "approach":
                self.pending = None
            self.last_idle = now  # start a fresh idle interval instead of speaking immediately

        if self.speaking and now - self.speak_started < SPEAK_TIMEOUT_S:
            return
        self.speaking = False
        if self.pending == "after" and now < self.pose_until:
            return  # keep the photo face on until the hold time is over
        if self.pending:
            moment, self.pending = self.pending, None
            await self._say(moment)
            return
        idle = self.behaviour.get("idle") or {}
        every = idle.get("every_s")
        if not self.near and not self.in_photo and every and now - self.last_idle >= every:
            self.last_idle = now
            await self._say("idle")

    # ---- helpers ----------------------------------------------------------------------

    async def _say(self, moment, interrupt=False):
        spec = self.behaviour.get(moment) or {}
        lines = spec.get("lines") or []
        gesture = spec.get("gesture")
        if not self.connected or (not lines and not gesture):
            return
        if lines:
            line = random.choice(lines)
            self.speaking = True  # set now; speak.start arrives a moment later
            self.speak_started = time.monotonic()
            await self._safe(self.client.request_speak_text(line, abort=interrupt))
            self.log(f"[{moment}] {line}")
        if gesture:
            await self._safe(self.client.request_gesture_start(gesture))

    async def _pose_after(self, delay, speak=True):
        """Put on the photo face and hold it for hold_s seconds, then release it.

        Gestures animate in and straight back out, so the held face is built from
        face parameters instead: once set, they stay until they are set back to 0.
        """
        await asyncio.sleep(delay)
        pose = self.behaviour.get("pose") or {}
        lines = pose.get("lines") or []
        face = pose.get("face") or {}
        hold_s = pose.get("hold_s", 6.0)
        if not self.connected:
            return
        if lines and speak:
            line = random.choice(lines)
            self.speaking = True
            self.speak_started = time.monotonic()
            await self._safe(self.client.request_speak_text(line, abort=True))
            self.log(f"[pose] {line}")
        if pose.get("gesture"):
            await self._safe(self.client.request_gesture_start(pose["gesture"]))
        if not face:
            return
        self.pose_until = time.monotonic() + hold_s
        await self._safe(self.client.request_face_params(face))
        self.log(f"[pose] holding face for {hold_s} s: {face}")
        try:
            await asyncio.sleep(hold_s)
        finally:
            # Also runs when the pose is cancelled (condition switch), so the face never stays stuck.
            await self._safe(self.client.request_face_params({name: 0.0 for name in face}))

    def preview_pose(self):
        """Operator command: show the current condition's photo face now, without a photo."""
        self._cancel_pose()
        self.pose_task = asyncio.create_task(self._pose_after(0.0, speak=False))

    def _cancel_pose(self):
        if self.pose_task and not self.pose_task.done():
            self.pose_task.cancel()
        self.pose_task = None

    async def _apply_face(self):
        micro = self.behaviour.get("microexpressions", True)
        await self._safe(self.client.request_face_reset())
        await self._safe(self.client.request_face_config(microexpressions=micro))

    async def _look_ahead(self):
        # Look straight out at about head height, 2 m away.
        await self._safe(self.client.request_attend_location(0.0, 0.0, 2.0))

    async def _safe(self, coro):
        try:
            return await coro
        except Exception as e:
            self.log(f"robot command failed: {e!r}")
