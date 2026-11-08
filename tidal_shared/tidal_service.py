"""Find music on TIDAL with the user's own login and give mpv direct stream URLs.

EXPERIMENTAL. TIDAL has no public playback API; this uses the unofficial ``tidalapi`` library with a device-login
session the user creates once (tidal_tools/get_session.py). Each track needs its own stream-URL request, so a queue is
capped at MAX_TRACKS. TIDAL's terms may not allow this; use at your own risk.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Callable, Optional

from tidal_shared.music_common import AUTO, KINDS, Resolved, ServiceError, pick

MAX_TRACKS = 10


def open_session(tidalapi: Any, token_type: str, access: str, refresh: str, expiry: str) -> Any:
    """A logged-in tidalapi.Session from the stored tokens, or a spoken error."""
    session = tidalapi.Session()
    when = dt.datetime.fromisoformat(expiry) if expiry else None
    if not session.load_oauth_session(token_type, access, refresh or None, when):
        raise ServiceError("TIDAL has signed this node out. Run get_session.py again and update the tokens in the app.")
    return session


class TidalService:
    def __init__(self, session: Any, models: list, on_tokens: Optional[Callable[[Any], None]] = None) -> None:
        self._s, self._models, self._on_tokens = session, models, on_tokens

    def find(self, query: str, kind: str = AUTO, artist: Optional[str] = None) -> Resolved:
        kind = kind if kind in KINDS else AUTO
        try:
            res = self._s.search(f"{query} {artist}" if artist else query, models=self._models, limit=5)
            found = {"artist": _items(res, "artists"), "album": _items(res, "albums"), "track": _items(res, "tracks"),
                     "playlist": _items(res, "playlists")}
            hit = pick(found, query, kind)
            if hit is None:
                raise ServiceError(f"I couldn't find {query} on TIDAL.")
            k, item = hit
            tracks = self._tracks(k, item)
            urls = [u for u in (_url(t) for t in tracks[:MAX_TRACKS]) if u]
            if self._on_tokens:  # the library may have refreshed the login while searching
                self._on_tokens(self._s)
        except ServiceError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ServiceError("TIDAL didn't answer that. Try again in a moment.") from exc
        if not urls:
            raise ServiceError(f"TIDAL wouldn't stream {item.name}. Streaming needs a paid plan.")
        by = "" if k in ("artist", "playlist") else _by(item)
        return Resolved(k, item.name, by, urls, shuffle=k == "artist")

    @staticmethod
    def _tracks(kind: str, item: Any) -> list:
        if kind == "track":
            return [item]
        if kind == "artist":
            return list(item.get_top_tracks(limit=MAX_TRACKS))
        return list(item.tracks(limit=MAX_TRACKS))


def _items(res: Any, key: str) -> list:
    return [i for i in (res.get(key) or []) if i is not None]


def _by(item: Any) -> str:
    artist = getattr(item, "artist", None)
    return getattr(artist, "name", "") if artist else ""


def _url(track: Any) -> Optional[str]:
    try:
        return track.get_url()
    except Exception:  # noqa: BLE001 - unavailable in this region or plan; skip the track
        return None
