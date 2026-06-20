# Spotify Live Lyrics 🎵

A real-time synced lyrics display for Spotify with a Kanagawa Wave color theme.

![Kanagawa](https://img.shields.io/badge/theme-Kanagawa_Wave-E6C384)
![Platform](https://img.shields.io/badge/platform-Linux-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)

## Features

- **Real-time sync** - Lyrics update smoothly as the song plays
- **Kanagawa Wave theme** - warm yellow highlight, muted blue context lines
- **Live adjustment** - Fine-tune timing with Q/A keys (0.1s per press)
- **Centered display** - Current line is always highlighted in the middle of the window
- **Auto song detection** - Switches lyrics when you change songs
- **Multi-source search** - Uses LRCLIB metadata search plus Netease, Megalobiz and Genius fallbacks
- **Stale lookup cancellation** - Stops searching for the old track when you change songs mid-lookup
- **Plain lyrics fallback** - If synced lyrics are missing, plain lyrics can still be displayed with estimated timing
- **Responsive** - Adapts to any terminal size

## Preview

```
              🎵 Artist Name - Song Title
     [Offset: +0.0s | Q=earlier A=later Z=reset X=exit]

                  ...earlier lyrics...
                  a faded past line
                  the line before current        <- Fuji white on wave blue
♪♪              Current lyric line              ♪♪  <- carp yellow highlight
                  the line after current         <- Fuji white on wave blue
                  upcoming line
                  ...more upcoming lines...
```

The highlighted line always stays in the vertical center of the terminal. Past lines appear above (faded), future lines appear below.

## Requirements

- **Linux** (tested on Arch/CachyOS, should work on Ubuntu/Debian/Fedora)
- **Python 3.8+**
- **Spotify** (desktop app)
- **playerctl** - for Spotify integration
- **syncedlyrics** - CLI command for fetching lyrics from LRCLIB, Netease, Megalobiz and Genius
- **rich** - for terminal UI rendering

## Installation

### Arch Linux / CachyOS

```bash
# Install system dependencies
paru -S playerctl python-rich

# Install syncedlyrics as a standalone CLI tool
uv tool install syncedlyrics
uv tool update-shell

# Download the script
curl -o ~/.local/bin/lyrics-live https://raw.githubusercontent.com/Joccem/spotify-live-lyrics/main/spotify-live-lyrics.py
chmod +x ~/.local/bin/lyrics-live
```

Restart your shell after `uv tool update-shell`, or make sure uv's tool bin directory is in your `PATH`.

### Ubuntu / Debian

```bash
# Install system dependencies
sudo apt install playerctl python3-pip

# Install rich and syncedlyrics
python3 -m pip install --user rich
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install syncedlyrics

# Download the script
curl -o ~/.local/bin/lyrics-live https://raw.githubusercontent.com/Joccem/spotify-live-lyrics/main/spotify-live-lyrics.py
chmod +x ~/.local/bin/lyrics-live
```

### Other Linux

```bash
# Install playerctl (check your package manager)
# Then install rich and the syncedlyrics CLI
python3 -m pip install --user rich
pipx install syncedlyrics

# Download and install script
curl -o ~/.local/bin/lyrics-live https://raw.githubusercontent.com/Joccem/spotify-live-lyrics/main/spotify-live-lyrics.py
chmod +x ~/.local/bin/lyrics-live
```

## Usage

1. **Start Spotify** and play a song
2. **Run the viewer**:
   ```bash
   lyrics-live
   ```

### Controls

| Key | Action |
|-----|--------|
| `Q` | Show lyrics earlier (increase offset by 0.1s) |
| `A` | Show lyrics later (decrease offset by 0.1s) |
| `Z` | Reset offset to 0.0 |
| `X` | Exit viewer |
| `Ctrl+C` | Exit viewer |

The offset resets to 0.0 for each new song.

## Configuration

Edit the script to change default values:

```python
# Timing offset default (in seconds)
TIMING_OFFSET_DEFAULT = 0.0

# Lyrics lookup timeout default (in seconds)
LYRICS_LOOKUP_TIMEOUT = 8

# Provider fallback order
LYRICS_PROVIDERS = ["lrclib", "netease", "megalobiz", "genius"]

# Color scheme (Kanagawa Wave)
KANAGAWA_CARP_YELLOW = "#E6C384"   # Current line highlight
KANAGAWA_WAVE_BLUE_1 = "#223249"   # Previous/next line background
KANAGAWA_FUJI_WHITE = "#DCD7BA"    # Previous/next and future line text
```

## Troubleshooting

### "playerctl is not installed"
Install playerctl using your package manager (see Installation section).

### "syncedlyrics command is not installed or not in PATH"
Install the `syncedlyrics` CLI and make sure the installed command is visible in your shell:

```bash
uv tool install syncedlyrics
uv tool update-shell
command -v syncedlyrics
```

If `command -v syncedlyrics` prints nothing, restart the terminal or add uv's tool bin directory to `PATH`.

### "No lyrics found"
Not all songs have synced lyrics available. The app first tries synced lyrics, then falls back to plain lyrics with estimated timing when possible. If nothing is found, the track is probably missing from the configured providers.

### Lyrics are off-sync
Use `Q` to make lyrics appear earlier, or `A` to make them appear later. Each press adjusts by 0.1 seconds.

### Spotify not detected
Make sure Spotify is running and actually playing a song (not paused).

## How It Works

1. **playerctl** monitors Spotify playback and returns the current artist, title, position and duration
2. **LRCLIB** is queried directly with structured Spotify metadata for better exact matches
3. **syncedlyrics** then searches LRCLIB, Netease, Megalobiz and Genius with several normalized search terms
4. If only plain lyrics are found, the app converts them to coarse timestamped lines so they can still be displayed
5. The script parses the `.lrc` timestamps and finds the line matching the current position
6. **rich** renders the terminal UI: current line centered and highlighted in Kanagawa carp yellow, surrounding lines in Fuji white and wave blue
7. The display refreshes at 10 FPS; offset adjustment compensates for timing differences

## Contributing

**Full transparency:** This was vibe-coded with AI assistance (Claude). The code works great, but there's definitely room for improvement!

Contributions welcome:

- Bug reports
- Feature suggestions
- Pull requests
- Performance improvements
- Cross-platform support (Windows/macOS)

## Credits

- Built by **Jocce** with assistance from **Claude (Anthropic)**
- Uses the [Kanagawa](https://github.com/rebelot/kanagawa.nvim) Wave color palette
- Lyrics fetched via [syncedlyrics](https://github.com/moehmeni/syncedlyrics)

## License

MIT License - feel free to use and modify!

---

**Enjoy singing along!**
