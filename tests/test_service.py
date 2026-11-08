import datetime as dt
import sys
import types

import pytest

from commands.tidal_play import command as mod
from tidal_shared.music_common import ServiceError
from tidal_shared.tidal_service import MAX_TRACKS, TidalService, open_session


class Obj:
    def __init__(self, name, **kw):
        self.name = name
        self.__dict__.update(kw)


class Track(Obj):
    def get_url(self):
        if self.__dict__.get("blocked"):
            raise RuntimeError("not available")
        return f"https://tidal/{self.name}.flac"


def artist(name, tracks=()):
    return Obj(name, get_top_tracks=lambda limit=None: list(tracks)[:limit])


class Session:
    def __init__(self, results, access="A"):
        self.results, self.access_token, self.refresh_token, self.expiry_time = results, access, "R", None
        self.queries = []

    def search(self, query, models=None, limit=50, offset=0):
        self.queries.append(query)
        return self.results


def svc(results, **kw):
    s = Session(results)
    return TidalService(s, ["models"], **kw), s


def test_track_includes_the_artist_in_the_query_and_returns_a_stream_url():
    t = Track("Hysteria", artist=Obj("Muse"))
    service, session = svc({"tracks": [t], "artists": [], "albums": [], "playlists": []})
    r = service.find("Hysteria", "track", "Muse")
    assert session.queries == ["Hysteria Muse"] and r.urls == ["https://tidal/Hysteria.flac"] and r.spoken() == "Hysteria by Muse"


def test_exact_artist_plays_their_top_tracks_shuffled_and_capped():
    tracks = [Track(f"t{i}") for i in range(MAX_TRACKS + 5)]
    r = svc({"artists": [artist("Muse", tracks)], "tracks": [Track("Muse")]})[0].find("muse")
    assert r.kind == "artist" and r.shuffle and len(r.urls) == MAX_TRACKS and r.by == ""


def test_albums_and_playlists_use_their_tracks_and_skip_ones_tidal_will_not_stream():
    album = Obj("Absolution", artist=Obj("Muse"), tracks=lambda limit=None: [Track("a", blocked=True), Track("b")])
    r = svc({"albums": [album]})[0].find("Absolution", "album")
    assert r.urls == ["https://tidal/b.flac"] and r.spoken() == "Absolution by Muse"
    playlist = Obj("Mix", tracks=lambda limit=None: [Track("c")])
    assert svc({"playlists": [playlist]})[0].find("Mix", "playlist").urls == ["https://tidal/c.flac"]


def test_a_none_entry_in_results_is_skipped():
    assert svc({"tracks": [None, Track("x", artist=Obj("A"))]})[0].find("x", "track").urls


def test_nothing_found_nothing_streamable_and_library_errors_are_spoken():
    with pytest.raises(ServiceError, match="couldn't find Nope on TIDAL"):
        svc({"tracks": []})[0].find("Nope")
    with pytest.raises(ServiceError, match="wouldn't stream"):
        svc({"tracks": [Track("x", blocked=True)]})[0].find("x", "track")

    class Broken:
        def search(self, *a, **k):
            raise RuntimeError("boom")

    with pytest.raises(ServiceError, match="didn't answer"):
        TidalService(Broken(), []).find("x")


def test_refreshed_tokens_are_handed_back_after_a_search():
    seen = []
    service, session = svc({"tracks": [Track("x")]}, on_tokens=seen.append)
    service.find("x", "track")
    assert seen == [session]


def test_open_session_passes_the_stored_tokens_and_reports_a_signed_out_login():
    calls = []

    class S:
        def load_oauth_session(self, *a):
            calls.append(a)
            return len(calls) == 1

    api = types.SimpleNamespace(Session=S)
    open_session(api, "Bearer", "acc", "ref", "2026-11-08T10:00:00")
    assert calls[0] == ("Bearer", "acc", "ref", dt.datetime(2026, 11, 8, 10))
    with pytest.raises(ServiceError, match="signed this node out"):
        open_session(api, "Bearer", "acc", "", "")
    assert calls[1] == ("Bearer", "acc", None, None)


def test_the_command_saves_refreshed_tokens(monkeypatch):
    saved = {}

    class Sess:
        access_token, refresh_token, expiry_time = "NEW", "NEWR", dt.datetime(2026, 11, 9, 1)

        def load_oauth_session(self, *a):
            return True

    api = types.SimpleNamespace(Session=Sess, Track=1, Artist=2, Album=3, Playlist=4)
    monkeypatch.setitem(sys.modules, "tidalapi", api)
    cmd = mod.TidalPlayCommand()
    stored = {"TIDAL_TOKEN_TYPE": "Bearer", "TIDAL_ACCESS_TOKEN": "OLD", "TIDAL_REFRESH_TOKEN": "R", "TIDAL_EXPIRY": ""}
    monkeypatch.setattr(cmd._storage, "get_secret", lambda k, scope=None: stored.get(k), raising=False)
    monkeypatch.setattr(cmd._storage, "set_secret", lambda k, v, scope=None, value_type="string": saved.update({k: v}), raising=False)
    service = cmd._service()
    service._on_tokens(service._s)
    assert saved == {"TIDAL_ACCESS_TOKEN": "NEW", "TIDAL_REFRESH_TOKEN": "NEWR", "TIDAL_EXPIRY": "2026-11-09T01:00:00"}
    stored.clear()
    with pytest.raises(ServiceError, match="isn't set up"):
        cmd._service()
