"""TidalPlayCommand: "play <something> on Tidal" through this node's speaker (mpv)."""

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

for _candidate in ("tidal_shared", "lib"):
    _lib_dir: str = str(Path.home() / ".jarvis" / "packages" / "tidal_play" / _candidate)
    if _lib_dir not in sys.path:
        sys.path.insert(0, _lib_dir)

try:
    from jarvis_log_client import JarvisLogger
except ImportError:
    import logging

    class JarvisLogger:  # noqa: E303
        def __init__(self, **kw: str) -> None:
            self._log = logging.getLogger(kw.get("service", __name__))

        def error(self, msg: str, **kw: object) -> None: self._log.error(msg)

from jarvis_command_sdk import (
    CommandExample,
    CommandResponse,
    FastPathPattern,
    IJarvisCommand,
    IJarvisSecret,
    JarvisPackage,
    JarvisParameter,
    JarvisSecret,
    JarvisStorage,
    RequestInformation,
)
from jarvis_command_sdk.command import PreRouteResult

from tidal_shared.music_common import AUTO, KINDS, PLAYER, ServiceError, fast_arguments, fast_regexes
from tidal_shared.tidal_service import TidalService, open_session

logger = JarvisLogger(service="tidal-play")
_PLAY_ON, _NAME_FIRST = fast_regexes(r"tidal")


class TidalPlayCommand(IJarvisCommand):
    """Voice search and play on Tidal."""

    def __init__(self) -> None:
        self._storage = JarvisStorage("tidal_play")

    @property
    def command_name(self) -> str:
        return "tidal_play"

    @property
    def description(self) -> str:
        return (
            "Play a song, album, artist or playlist from Tidal. query is what to play, kind says what it is "
            "(leave empty unless the user says song, album, artist or playlist), artist narrows a song or album. "
            "Use when the user names Tidal: 'play ... on Tidal'."
        )

    @property
    def associated_service(self) -> Optional[str]:
        return "Tidal"

    @property
    def keywords(self) -> List[str]:
        return ["tidal", "play on tidal", "play from tidal", "song", "album", "playlist"]

    @property
    def parameters(self) -> List[JarvisParameter]:
        return [
            JarvisParameter("query", "string", required=True,
                            description="What to play: a song, album, artist or playlist name, without the service"),
            JarvisParameter("kind", "string", required=False, enum_values=KINDS,
                            description="track, album, artist or playlist. Leave empty when unsure."),
            JarvisParameter("artist", "string", required=False,
                            description="The artist, when the user named one for a song or album"),
        ]

    @property
    def fast_path_patterns(self) -> List[FastPathPattern]:
        return [
            FastPathPattern(id="tidal.play_on", description="Play something when you say 'on Tidal'",
                            example="Play Hysteria by Muse on Tidal", regex=_PLAY_ON, handler="_fast_play"),
            FastPathPattern(id="tidal.tidal_play", description="Play something when the phrase starts with 'Tidal'",
                            example="Tidal, play Discover Weekly", regex=_NAME_FIRST, handler="_fast_play"),
        ]

    def _fast_play(self, match: "re.Match[str]", voice_command: str) -> Optional[PreRouteResult]:
        args = fast_arguments(match.group("what"))
        return PreRouteResult(arguments=args) if args else None

    @property
    def required_secrets(self) -> List[IJarvisSecret]:
        return [
            JarvisSecret("TIDAL_TOKEN_TYPE", "Token type from get_session.py (Bearer)", "integration", "string", is_sensitive=False, friendly_name="Token type"),
            JarvisSecret("TIDAL_ACCESS_TOKEN", "Access token from get_session.py", "integration", "string", friendly_name="Access token"),
            JarvisSecret("TIDAL_REFRESH_TOKEN", "Refresh token from get_session.py", "integration", "string", friendly_name="Refresh token"),
            JarvisSecret("TIDAL_EXPIRY", "Access token expiry from get_session.py (ISO date and time)", "integration", "string", is_sensitive=False, friendly_name="Expiry"),
        ]

    @property
    def required_packages(self) -> List[JarvisPackage]:
        return [JarvisPackage("tidalapi", ">=0.8.0"), JarvisPackage("requests", ">=2.31.0")]

    @property
    def setup_guide(self) -> Optional[str]:
        return (
            '## Connect TIDAL (experimental)\n'
            '\n'
            "TIDAL has no public playback API. This uses the unofficial `tidalapi` library with your own paid TIDAL account, and TIDAL's terms may not allow it.\n"
            '\n'
            '1. On a machine with a browser run `python tidal_tools/get_session.py` and approve the link it prints.\n'
            "2. Copy the four values it prints into this command's settings.\n"
            '3. The node needs `mpv` installed. Long playlists are capped at 10 tracks, because each track needs its own request.\n'
        )

    def generate_prompt_examples(self) -> List[CommandExample]:
        return [
            CommandExample("Play Hysteria by Muse on Tidal",
                           {"query": "Hysteria", "kind": "track", "artist": "Muse"}, is_primary=True),
            CommandExample("Play the album Black Holes and Revelations on Tidal",
                           {"query": "Black Holes and Revelations", "kind": "album"}),
            CommandExample("Play some Muse from Tidal", {"query": "Muse", "kind": "artist"}),
        ]

    def generate_adapter_examples(self) -> List[CommandExample]:
        rows = [
            ("Play Bohemian Rhapsody on Tidal", "Bohemian Rhapsody", "track", None),
            ("Play Thunderstruck by AC/DC from Tidal", "Thunderstruck", "track", "AC/DC"),
            ("Play the album Rumours on Tidal", "Rumours", "album", None),
            ("Play Abbey Road by The Beatles on Tidal", "Abbey Road", "album", "The Beatles"),
            ("Play Taylor Swift on Tidal", "Taylor Swift", "artist", None),
            ("Play my Chill Hits playlist on Tidal", "Chill Hits", "playlist", None),
            ("Tidal, play Running Up That Hill", "Running Up That Hill", "track", None),
        ]
        out = []
        for text, query, kind, artist in rows:
            params = {"query": query, "kind": kind}
            if artist:
                params["artist"] = artist
            out.append(CommandExample(text, params))
        return out

    def _service(self) -> TidalService:
        import tidalapi

        s = self._storage
        token, access, refresh, expiry = (s.get_secret(k) for k in ("TIDAL_TOKEN_TYPE", "TIDAL_ACCESS_TOKEN", "TIDAL_REFRESH_TOKEN", "TIDAL_EXPIRY"))
        if not (token and access):
            raise ServiceError("TIDAL isn't set up yet. Run get_session.py and enter the tokens in the app.")
        session = open_session(tidalapi, token, access, refresh or "", expiry or "")
        models = [tidalapi.Track, tidalapi.Artist, tidalapi.Album, tidalapi.Playlist]

        def keep(sess) -> None:  # the library refreshes the login itself; remember the new tokens
            if sess.access_token != access:
                s.set_secret("TIDAL_ACCESS_TOKEN", sess.access_token)
                s.set_secret("TIDAL_REFRESH_TOKEN", sess.refresh_token or refresh or "")
                if sess.expiry_time:
                    s.set_secret("TIDAL_EXPIRY", sess.expiry_time.isoformat())

        return TidalService(session, models, keep)

    def run(self, request_info: RequestInformation, **kwargs: Any) -> CommandResponse:
        query = str(kwargs.get("query") or "").strip()
        if not query:
            return CommandResponse.error_response(error_details="What would you like me to play?",
                                                  context_data={"error": "missing_query"})
        kind = str(kwargs.get("kind") or AUTO).lower()
        try:
            item = self._service().find(query, kind, kwargs.get("artist"))
            PLAYER.play(item)
        except ServiceError as exc:
            return CommandResponse.error_response(error_details=str(exc), context_data={"error": "service_error"})
        except Exception as exc:  # noqa: BLE001 - never raise into the voice pipeline
            logger.error("Tidal play failed", error=str(exc))
            return CommandResponse.error_response(error_details="Tidal didn't respond. Try again in a moment.",
                                                  context_data={"error": "unexpected", "detail": str(exc)})
        return CommandResponse.success_response(
            context_data={"message": f"Playing {item.spoken()}.", "kind": item.kind}, wait_for_input=False)
