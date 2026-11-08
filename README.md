# jarvis-cmd-tidal

A [Jarvis](https://github.com/alexberardi/jarvis-server) Pantry package that plays music from your own paid TIDAL account through the node's speaker.

## What you can say

| You say                                | Plays                                |
| -------------------------------------- | ------------------------------------ |
| "Play Hysteria by Muse on Tidal"       | The song                             |
| "Play the album Rumours from Tidal"    | The album                            |
| "Play Taylor Swift on Tidal"           | The artist (an exact name), shuffled |
| "Play my Chill Hits playlist on Tidal" | The playlist                         |
| "Tidal, play Discover Weekly"          | Best match                           |

The phrase must include "Tidal". These are fast paths, so the node runs them with no model, and each can be switched off
in the app's Inspect fast-paths screen. With [jarvis-cmd-music](https://github.com/opticon454/jarvis-cmd-music), "play
Korn" also works and uses your default music service.

## Requirements

- A paid TIDAL account.
- `mpv` on the node.
- Run `python tidal_tools/get_session.py` once, on a machine with a browser.

## Settings

Entered in the Jarvis app; nothing is stored in this repository.

| Setting               | Required | Meaning                                                                                   |
| --------------------- | -------- | ----------------------------------------------------------------------------------------- |
| `TIDAL_TOKEN_TYPE`    | Yes      | From `tidal_tools/get_session.py` (Bearer).                                               |
| `TIDAL_ACCESS_TOKEN`  | Yes      | From the same script.                                                                     |
| `TIDAL_REFRESH_TOKEN` | Yes      | From the same script.                                                                     |
| `TIDAL_EXPIRY`        | Yes      | From the same script. The package updates all three when the library refreshes the login. |

## How it plays

The command finds the music, then starts `mpv` on the node with the stream addresses. A new play replaces the old one,
pauses the Spotify Connect receiver if it is running, and ends any other `mpv`, so two streams never share the speaker.
Audio goes to a connected Bluetooth speaker, else PulseAudio (so the agent can lower it while you talk), else the Pi
image's ALSA `output` alias. Long queues are limited to 50 tracks.

## Status

**Experimental draft.** TIDAL has no public playback API, so this uses the unofficial `tidalapi` library (method names checked against 0.8.11) and TIDAL's terms may not allow it. Tested with fakes only; **never run against a TIDAL account.** A queue is capped at 10 tracks because each needs its own request.

## Tests

```bash
PYTHONPATH=/path/to/jarvis-command-sdk python3 -m pytest
```

The tests use fakes, so no node, account or network is needed.

## Licence

Apache-2.0. Not affiliated with Tidal. `mpv` is a separate program and is not included.
