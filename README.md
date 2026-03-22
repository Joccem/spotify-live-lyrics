# Spotify Live Lyrics 🎵

A beautiful, real-time synced lyrics display for Spotify with a sleek Nord color theme.

![Nord Theme](https://img.shields.io/badge/theme-Nord-88C0D0)
![Platform](https://img.shields.io/badge/platform-Linux-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)

## Features

✨ **Real-time sync** - Lyrics update smoothly as the song plays  
🎨 **Nord theme** - Beautiful color scheme that's easy on the eyes  
⌨️ **Live adjustment** - Fine-tune timing with Q/A keys  
🎯 **Smart highlighting** - Current line in yellow, context in grey  
🔄 **Auto song detection** - Switches lyrics when you change songs  
📱 **Responsive** - Adapts to any terminal size

## Preview

```
🎵 Artist Name - Song Title
[Offset: +0.0s | Q=earlier A=later Z=reset X=exit]

Previous lyric line here
♪♪  Current lyric line highlighted in yellow  ♪♪
Next lyric line here

Rest of the lyrics...
```

## Requirements

- **Linux** (tested on Arch/CachyOS, should work on Ubuntu/Debian/Fedora)
- **Python 3.8+**
- **Spotify** (desktop app or web player)
- **playerctl** - for Spotify integration
- **syncedlyrics** - for fetching lyrics

## Installation

### Arch Linux / CachyOS

```bash
# Install system dependencies
paru -S playerctl python-rich python-pyfiglet

# Install syncedlyrics
pipx install syncedlyrics

# Download the script
curl -o ~/.local/bin/lyrics-live https://raw.githubusercontent.com/Joccem/spotify-live-lyrics/main/spotify-live-lyrics.py
chmod +x ~/.local/bin/lyrics-live
```

### Ubuntu / Debian

```bash
# Install system dependencies
sudo apt install playerctl python3-pip

# Install Python packages
pip3 install --user rich pyfiglet syncedlyrics

# Download the script
curl -o ~/.local/bin/lyrics-live https://raw.githubusercontent.com/Joccem/spotify-live-lyrics/main/spotify-live-lyrics.py
chmod +x ~/.local/bin/lyrics-live
```

### Other Linux

```bash
# Install playerctl (check your package manager)
# Then install Python packages
pip3 install --user rich pyfiglet syncedlyrics

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
| `Q` | Show lyrics earlier (increase offset) |
| `A` | Show lyrics later (decrease offset) |
| `Z` | Reset offset to 0.0 |
| `X` | Exit viewer |
| `Ctrl+C` | Exit viewer |

The offset resets to 0.0 for each new song.

## Configuration

Edit the script to change default values:

```python
# Timing offset default (in seconds)
TIMING_OFFSET_DEFAULT = 0.0  # Start with no offset

# Color scheme (Nord palette)
NORD_AURORA_YELLOW = "#EBCB8B"  # Current line color
NORD3 = "#4C566A"  # Context lines background
```

## Troubleshooting

### "playerctl is not installed"
Install playerctl using your package manager (see Installation section)

### "No synced lyrics found"
Not all songs have synced lyrics available. The script will wait for the next song.

### Lyrics are off-sync
Use `Q` to make lyrics appear earlier, or `A` to make them appear later. Each press adjusts by 0.1 seconds.

### Spotify not detected
Make sure Spotify is running and actually playing a song (not paused).

## How It Works

1. **playerctl** monitors Spotify playback and provides current position
2. **syncedlyrics** fetches time-synced lyrics from online databases
3. The script parses `.lrc` format lyrics and matches them to playback position
4. **Rich** library renders the beautiful terminal UI with Nord colors
5. Live offset adjustment compensates for any timing differences

## Contributing

**Full transparency:** This was 100% vibe-coded with AI assistance (Claude). The code works great, but there's definitely room for improvement and optimization!

I hope you enjoy using it, and if you're a developer who wants to refactor, optimize, or add features - please do! Contributions are more than welcome:

- Report bugs
- Suggest features
- Submit pull requests
- Improve code quality
- Refactor for better performance
- Add cross-platform support (Windows/macOS)
- Improve documentation

Don't be shy - make it better! 🚀

## Credits

- Built by **Jocce** with assistance from **Claude (Anthropic)**
- Uses the [Nord color palette](https://www.nordtheme.com/)
- Lyrics fetched via [syncedlyrics](https://github.com/moehmeni/syncedlyrics)

## License

MIT License - feel free to use and modify!

---

**Enjoy singing along! 🎤✨**
