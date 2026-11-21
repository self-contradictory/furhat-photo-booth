"""Furhat behaviour for the photo booth.

The design is 3 x 2:
  - the main condition (passive, inviting, complimenting) sets gaze and micro-expressions.
    Its invite phrase is said by hand from Furhat Studio on a second laptop, not from here;
    the booth only records which condition is running.
  - the action (smile, silly) is what the robot does when someone presses the photo button:
    it says the action's phrase and holds the action's face for the shutter.
Person detection only turns the robot's gaze; it never makes the robot speak.
All the content lives in conditions.json; this file only decides *when*.
"""
import asyncio
import json
import math
import random
import time

from furhat_realtime_api import AsyncFurhatClient

TICK_S = 0.25  # how often the gaze loop re-evaluates the situation
RECONNECT_S = 5.0


def load_conditions(path):
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg


def user_distance(user):
    """Distance in metres from the robot to one tracked user, or None if unknown.

    Furhat reports positions in metres with z pointing forward from the robot.
    The exact field names are read defensively so a firmware difference only
    disables gaze instead of crashing the booth.
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
        self.action = next(iter(conditions["actions"]))

        # Proximity state (drives gaze only)
        self.near = False
        self.closest = None          # metres to the closest tracked user, None if nobody
        self.last_seen_close = 0.0   # last time someone was within leave_distance_m
        self.simulated = None        # operator override from the terminal: metres or None
        self.first_users_payload_logged = False

        self.pose_task = None        # scheduled photo face during the countdown

    # ---- public API used by the orchestrator ------------------------------------

    @property
    def behaviour(self):
        return self.cfg["conditions"][self.condition]

    @property
    def action_spec(self):
        return self.cfg["actions"][self.action]

    async def set_condition(self, name):
        self.condition = name
        self.near = False  # re-evaluate gaze for anyone already standing there
        self._cancel_pose()
        if self.connected:
            await self._apply_face()
            await self._look_ahead()
        self.log(f"condition -> {name}")

    def set_action(self, name):
        self.action = name
        self.log(f"action -> {name}")

    async def photo_started(self, countdown_s):
        """The participant pressed the button: a countdown of countdown_s seconds starts now.

        The action's phrase plays immediately. Its face starts lead_s seconds before the
        shutter and is held for hold_s seconds, so it is on Furhat's face when the frame
        is captured even if the kiosk lags a little.
        """
        spec = self.action_spec
        await self._say(spec)
        self._cancel_pose()
        delay = max(0.0, countdown_s - spec.get("lead_s", 3.0))
        self.pose_task = asyncio.create_task(self._pose_after(delay))

    def kiosk_reset(self):
        """The QR screen was cleared; the booth is ready for the next person."""
        self._cancel_pose()

    def simulate(self, distance):
        """Operator override for testing without a real person.

        A distance in metres, math.inf for "nobody there", or None to use real tracking.
        """
        self.simulated = distance
        if distance not in (None, math.inf):
            self.near = False  # pressing `n` again makes the robot turn to the "new" person

    def preview_pose(self):
        """Operator command: show the current action's face now, without a photo."""
        self._cancel_pose()
        self.pose_task = asyncio.create_task(self._pose_after(0.0))

    # ---- connection ---------------------------------------------------------------

    async def run(self):
        """Connect and keep the gaze loop running, reconnecting if the robot drops."""
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
            await asyncio.sleep(RECONNECT_S)

    async def _setup(self):
        c = self.client
        c.add_handler("response.users.data", self._on_users)
        voice = self.cfg.get("voice")
        if voice:
            await self._safe(c.request_voice_config(voice_id=voice))
        await self._apply_face()
        await self._look_ahead()
        await c.request_users_start()

    # ---- event handlers -----------------------------------------------------------

    async def _on_users(self, event):
        users = event.get("users") or []
        if users and not self.first_users_payload_logged:
            # Printed once so the real robot's payload format can be checked on the day.
            self.log(f"first user payload: {json.dumps(users[0])[:300]}")
            self.first_users_payload_logged = True
        distances = [d for d in (user_distance(u) for u in users) if d is not None]
        self.closest = min(distances) if distances else None

    # ---- gaze loop ------------------------------------------------------------------

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
        elif self.near and now - self.last_seen_close >= prox["leave_after_s"]:
            self.near = False
            self.log("person left")
            await self._look_ahead()

    # ---- helpers ----------------------------------------------------------------------

    async def _say(self, spec):
        lines = spec.get("lines") or []
        if not self.connected:
            return
        if lines:
            line = random.choice(lines)
            await self._safe(self.client.request_speak_text(line, abort=True))
            self.log(f"[{self.action}] {line}")
        if spec.get("gesture"):
            await self._safe(self.client.request_gesture_start(spec["gesture"]))

    async def _pose_after(self, delay):
        """Put on the action's face and hold it for hold_s seconds, then release it.

        Gestures animate in and straight back out, so the held face is built from
        face parameters instead: once set, they stay until they are set back to 0.
        """
        await asyncio.sleep(delay)
        spec = self.action_spec
        face = spec.get("face") or {}
        hold_s = spec.get("hold_s", 6.0)
        if not self.connected or not face:
            return
        await self._safe(self.client.request_face_params(face))
        self.log(f"[{self.action}] holding face for {hold_s} s: {face}")
        try:
            await asyncio.sleep(hold_s)
        finally:
            # Also runs when the pose is cancelled (condition switch), so the face never stays stuck.
            await self._safe(self.client.request_face_params({name: 0.0 for name in face}))

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
