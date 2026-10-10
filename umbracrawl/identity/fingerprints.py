"""Fingerprint profiles. One OS choice drives every field."""
from __future__ import annotations

import random

PROFILES = [
    {"os": "windows", "os_ver": "10.0.0", "arch": "x86",
     "ua": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
     "sec_ch_ua": ('"Chromium";v="124", "Google Chrome";v="124",'
                   ' "Not-A.Brand";v="99"'),
     "sec_ch_ua_platform": '"Windows"',
     "viewport": "1920x1080", "locale": "en-US", "tz": "America/New_York",
     "webgl": "ANGLE (Google, Vulkan 1.3.0, SwiftShader)"},
    {"os": "macos", "os_ver": "14.4.1", "arch": "arm",
     "ua": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
     "sec_ch_ua": ('"Chromium";v="124", "Google Chrome";v="124",'
                   ' "Not-A.Brand";v="99"'),
     "sec_ch_ua_platform": '"macOS"',
     "viewport": "1512x982", "locale": "en-US", "tz": "America/Chicago",
     "webgl": "ANGLE (Apple, ANGLE Metal Renderer)"},
]

try:
    import browserforge  # type: ignore
    HAVE_BFORGE = True
except ImportError:
    HAVE_BFORGE = False


def pick_profile(rng: random.Random | None = None) -> dict:
    rng = rng or random.Random()
    if HAVE_BFORGE:
        try:
            fp = browserforge.FingerprintGenerator().generate()
            return {"os": "browserforge", "ua": fp.navigator.userAgent,
                    "sec_ch_ua": ('"Chromium";v="124", "Google Chrome";v="124",'
                                  ' "Not-A.Brand";v="99"'),
                    "sec_ch_ua_platform": '"Windows"',
                    "viewport": f"{fp.screen.width}x{fp.screen.height}",
                    "locale": "en-US", "tz": "America/New_York",
                    "webgl": fp.webGl.renderer}
        except Exception:
            pass
    return dict(rng.choice(PROFILES))


def headers_for(profile: dict) -> dict:
    return {
        "User-Agent": profile["ua"],
        "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                   "image/avif,image/webp,*/*;q=0.8"),
        "Accept-Language": f"{profile['locale']},{profile['locale'].split('-')[0]};q=0.9",
        "Sec-CH-UA": profile["sec_ch_ua"],
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": profile["sec_ch_ua_platform"],
        "Upgrade-Insecure-Requests": "1",
    }
