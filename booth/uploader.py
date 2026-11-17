"""Local-first photo storage with background upload to the Cloudflare Worker.

Every photo is written to data/photos/ before anything touches the network.
A sidecar <id>.json records its condition and whether it has been uploaded,
so pending uploads survive a crash or restart of the orchestrator.
"""
import asyncio
import json
import os

import aiohttp

RETRY_S = 5.0
WARN_AFTER_FAILURES = 2


class Uploader:
    def __init__(self, photo_dir, worker_url, secret, log):
        self.photo_dir = photo_dir
        self.worker_url = worker_url.rstrip("/")
        self.secret = secret
        self.log = log
        self.failures = 0
        self.wake = asyncio.Event()
        os.makedirs(photo_dir, exist_ok=True)

    def save(self, session_id, jpeg, condition, captured_at):
        with open(self._path(session_id, "jpg"), "wb") as f:
            f.write(jpeg)
        self._write_meta(session_id, {
            "id": session_id,
            "condition": condition,
            "captured_at": captured_at,
            "uploaded": False,
        })
        self.wake.set()

    def pending(self):
        return [m for m in self._all_meta() if not m["uploaded"]]

    async def run(self):
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as http:
            while True:
                for meta in self.pending():
                    if await self._upload(http, meta):
                        meta["uploaded"] = True
                        self._write_meta(meta["id"], meta)
                        self.log(f"uploaded {meta['id']}")
                        if self.failures >= WARN_AFTER_FAILURES:
                            self.log("uploads working again")
                        self.failures = 0
                    else:
                        self.failures += 1
                        if self.failures == WARN_AFTER_FAILURES:
                            self.log("!!! UPLOADS FAILING: check Wi-Fi or switch the Mac to the phone hotspot."
                                     " Photos are safe in data/photos and will upload when back online.")
                        break  # the network is likely down; wait before trying the rest
                self.wake.clear()
                try:
                    await asyncio.wait_for(self.wake.wait(), RETRY_S)
                except asyncio.TimeoutError:
                    pass

    async def _upload(self, http, meta):
        with open(self._path(meta["id"], "jpg"), "rb") as f:
            jpeg = f.read()
        try:
            async with http.put(
                f"{self.worker_url}/api/sessions/{meta['id']}",
                data=jpeg,
                headers={
                    "x-booth-secret": self.secret,
                    "x-condition": meta["condition"],
                    "x-captured-at": meta["captured_at"],
                    "content-type": "image/jpeg",
                },
            ) as resp:
                if resp.status == 200:
                    return True
                self.log(f"upload {meta['id']} failed: HTTP {resp.status} {await resp.text()}")
        except Exception as e:
            self.log(f"upload {meta['id']} failed: {e!r}")
        return False

    def _path(self, session_id, ext):
        return os.path.join(self.photo_dir, f"{session_id}.{ext}")

    def _write_meta(self, session_id, meta):
        tmp = self._path(session_id, "json.tmp")
        with open(tmp, "w") as f:
            json.dump(meta, f)
        os.replace(tmp, self._path(session_id, "json"))

    def _all_meta(self):
        metas = []
        for name in sorted(os.listdir(self.photo_dir)):
            if name.endswith(".json"):
                with open(os.path.join(self.photo_dir, name)) as f:
                    metas.append(json.load(f))
        return metas
