#!/usr/bin/env python3
"""
Spotify Live Lyrics Viewer
A beautiful, real-time synced lyrics display for Spotify with Kanagawa theme

Author: Jocce (with Claude)
License: MIT
Repository: https://github.com/YOUR_USERNAME/spotify-live-lyrics
"""

import subprocess
import time
import sys
import re
import threading
import shutil
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from typing import Callable, List, Tuple, Optional

# ============================================================================
# DEPENDENCIES CHECK & AUTO-INSTALL
# ============================================================================

def check_dependencies():
    """Check required Python modules."""
    missing = []

    try:
        from rich.console import Console
        from rich.text import Text
        from rich.live import Live
        from rich.align import Align
    except ImportError:
        missing.append('rich')

    if missing:
        print(f"Missing Python dependencies: {', '.join(missing)}")
        print("Install them in your project virtual environment, or on Arch with:")
        print("paru -S " + ' '.join([f'python-{p}' for p in missing]))
        sys.exit(1)

check_dependencies()

from rich.console import Console
from rich.text import Text
from rich.live import Live
from rich.align import Align
from rich.panel import Panel

# ============================================================================
# CONFIGURATION
# ============================================================================

# Timing offset in seconds - adjustable with Q (earlier) and A (later)
# Negative = show lyrics earlier, Positive = show lyrics later
TIMING_OFFSET_DEFAULT = 0.0

# Lyrics lookup timeout in seconds. Keep individual lookups short so changing
# songs does not leave the app stuck chasing lyrics for the previous track.
LYRICS_LOOKUP_TIMEOUT = 8

# Provider order for the syncedlyrics CLI fallback. LRCLIB is also queried
# directly before this list so we can use structured Spotify metadata.
# Musixmatch is intentionally excluded by default: it commonly returns noisy
# 401 errors without credentials, and LRCLIB/Netease/Megalobiz/Genius are more
# useful for obscure Swedish catalog tracks.
LYRICS_PROVIDERS = ["lrclib", "netease", "megalobiz", "genius"]

# Kanagawa Wave color palette
KANAGAWA_FUJI_WHITE = "#DCD7BA"
KANAGAWA_CRYSTAL_BLUE = "#7E9CD8"
KANAGAWA_SPRING_BLUE = "#7AA89F"
KANAGAWA_CARP_YELLOW = "#E6C384"
KANAGAWA_WAVE_BLUE_1 = "#223249"

# Global variable for live offset adjustment
current_offset = TIMING_OFFSET_DEFAULT

console = Console()

# ============================================================================
# DATA STRUCTURES
# ============================================================================

class LyricsLine:
    """A single line of lyrics with timestamp"""
    def __init__(self, timestamp: float, text: str):
        self.timestamp = timestamp
        self.text = text


# ============================================================================
# SPOTIFY INTEGRATION
# ============================================================================

def check_playerctl():
    """Check if playerctl is installed"""
    try:
        subprocess.run(['playerctl', '--version'],
                      capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_syncedlyrics():
    """Check if the syncedlyrics CLI is installed and available in PATH."""
    return shutil.which("syncedlyrics") is not None


def get_spotify_info() -> Optional[Tuple[str, str, float, Optional[float]]]:
    """Get artist, title, playback position and duration from Spotify via playerctl."""
    try:
        artist = subprocess.check_output(
            ["playerctl", "-p", "spotify", "metadata", "artist"],
            stderr=subprocess.DEVNULL,
            timeout=2
        ).decode().strip()

        title = subprocess.check_output(
            ["playerctl", "-p", "spotify", "metadata", "title"],
            stderr=subprocess.DEVNULL,
            timeout=2
        ).decode().strip()

        # Position in seconds
        position_str = subprocess.check_output(
            ["playerctl", "-p", "spotify", "position"],
            stderr=subprocess.DEVNULL,
            timeout=2
        ).decode().strip()

        position = float(position_str)

        duration = None
        try:
            # MPRIS reports length in microseconds. Some players omit it.
            duration_str = subprocess.check_output(
                ["playerctl", "-p", "spotify", "metadata", "mpris:length"],
                stderr=subprocess.DEVNULL,
                timeout=2
            ).decode().strip()
            if duration_str:
                duration = int(duration_str) / 1_000_000
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
            duration = None

        return artist, title, position, duration
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
        return None


def same_song(left_artist: str, left_title: str, right_artist: str, right_title: str) -> bool:
    """Compare Spotify song identity robustly enough for cancellation checks."""
    return (left_artist.casefold(), left_title.casefold()) == (
        right_artist.casefold(),
        right_title.casefold(),
    )


def make_song_cancel_checker(artist: str, title: str) -> Callable[[], bool]:
    """Return True when Spotify has moved away from the song being fetched."""
    def is_cancelled() -> bool:
        info = get_spotify_info()
        if not info:
            return False
        current_artist, current_title, _, _ = info
        return not same_song(current_artist, current_title, artist, title)

    return is_cancelled


# ============================================================================
# LYRICS FETCHING & PARSING
# ============================================================================

def format_lrc_timestamp(seconds: float) -> str:
    """Format seconds as an LRC timestamp."""
    seconds = max(0.0, seconds)
    minutes = int(seconds // 60)
    remainder = seconds - minutes * 60
    whole_seconds = int(remainder)
    centiseconds = int(round((remainder - whole_seconds) * 100))
    if centiseconds == 100:
        whole_seconds += 1
        centiseconds = 0
    return f"[{minutes:02d}:{whole_seconds:02d}.{centiseconds:02d}]"


def plain_lyrics_to_lrc(plain_lyrics: str, duration: Optional[float]) -> Optional[str]:
    """Convert plain lyrics to coarse timestamped LRC so the UI can display them."""
    lines = [line.strip() for line in plain_lyrics.splitlines() if line.strip()]
    lines = [line for line in lines if not re.match(r"^\d*Embed$", line, re.IGNORECASE)]
    if not lines:
        return None

    # Leave some room before the first lyric. If duration is missing, use a rough
    # reading pace. This is explicitly a fallback, not real synchronization.
    if duration and duration > 20:
        start_at = min(8.0, duration * 0.08)
        usable_duration = max(1.0, duration - start_at - 5.0)
        step = max(1.5, usable_duration / max(1, len(lines) - 1))
    else:
        start_at = 3.0
        step = 3.0

    return "\n".join(
        f"{format_lrc_timestamp(start_at + i * step)} {line}"
        for i, line in enumerate(lines)
    )


def normalize_title(title: str) -> str:
    """Remove common streaming metadata noise from track titles."""
    normalized = title.strip()
    normalized = re.sub(r"\s*[-–—]\s*(remaster(?:ed)?|\d{4} remaster(?:ed)?|radio edit|single version|album version|live).*$", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s*[\[(](feat\.?|featuring|with|remaster(?:ed)?|live|radio edit|single version|album version).*?[\])]", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized).strip(" -–—")
    return normalized or title.strip()


def build_search_terms(artist: str, title: str) -> List[str]:
    """Build increasingly loose search terms for obscure tracks."""
    clean_title = normalize_title(title)
    terms = [
        f"{artist} {title}",
        f"{artist} {clean_title}",
        f"{clean_title} {artist}",
        f"{title} {artist}",
        clean_title,
        title,
    ]

    deduped = []
    seen = set()
    for term in terms:
        term = re.sub(r"\s+", " ", term).strip()
        key = term.casefold()
        if term and key not in seen:
            deduped.append(term)
            seen.add(key)
    return deduped


def request_json(url: str, params: dict) -> Optional[object]:
    """Fetch JSON using only the standard library."""
    full_url = f"{url}?{urlencode(params)}"
    request = Request(
        full_url,
        headers={"User-Agent": "spotify-live-lyrics/1.0 (https://github.com/Joccem/spotify-live-lyrics)"},
    )
    try:
        with urlopen(request, timeout=LYRICS_LOOKUP_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return None


def fetch_lrclib_direct(
    artist: str,
    title: str,
    duration: Optional[float],
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> Optional[str]:
    """Query LRCLIB directly with structured metadata before fuzzy CLI search."""
    clean_title = normalize_title(title)

    if is_cancelled and is_cancelled():
        return None

    exact_params = {"artist_name": artist, "track_name": clean_title}
    if duration:
        exact_params["duration"] = str(round(duration))

    exact = request_json("https://lrclib.net/api/get", exact_params)
    if isinstance(exact, dict):
        synced = (exact.get("syncedLyrics") or "").strip()
        if synced:
            console.print("[green]✓ Found synced lyrics via LRCLIB exact metadata[/green]")
            return synced
        plain = (exact.get("plainLyrics") or "").strip()
        pseudo = plain_lyrics_to_lrc(plain, duration)
        if pseudo:
            console.print("[yellow]Found plain lyrics via LRCLIB exact metadata; using estimated timing[/yellow]")
            return pseudo

    for term in build_search_terms(artist, title):
        if is_cancelled and is_cancelled():
            return None
        results = request_json("https://lrclib.net/api/search", {"q": term})
        if not isinstance(results, list):
            continue

        # Prefer synced lyrics. LRCLIB search can return several nearby matches;
        # obscure Swedish tracks often need the looser query variants above.
        for track in results:
            synced = (track.get("syncedLyrics") or "").strip()
            if synced:
                console.print(f"[green]✓ Found synced lyrics via LRCLIB search:[/green] [dim]{term}[/dim]")
                return synced

        for track in results:
            plain = (track.get("plainLyrics") or "").strip()
            pseudo = plain_lyrics_to_lrc(plain, duration)
            if pseudo:
                console.print(f"[yellow]Found plain lyrics via LRCLIB search; using estimated timing:[/yellow] [dim]{term}[/dim]")
                return pseudo

    return None


def run_syncedlyrics_cli(
    search_term: str,
    providers: List[str],
    *,
    enhanced: bool = False,
    synced_only: bool = True,
    plain_only: bool = False,
    log_errors: bool = False,
) -> Optional[str]:
    """Run syncedlyrics CLI for one search term/provider set."""
    command = ["syncedlyrics", search_term, "-p", *providers]
    if enhanced:
        command.append("--enhanced")
    if synced_only:
        command.append("--synced-only")
    if plain_only:
        command.append("--plain-only")

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=LYRICS_LOOKUP_TIMEOUT
    )

    if result.returncode == 0 and result.stdout.strip():
        return result.stdout

    if log_errors and result.stderr.strip():
        console.print(f"[dim]syncedlyrics lookup failed for '{search_term}': {result.stderr.strip()}[/dim]")

    return None


def fetch_synced_lyrics(
    artist: str,
    title: str,
    duration: Optional[float] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> Optional[str]:
    """Fetch lyrics from LRCLIB and syncedlyrics providers with fallback search terms."""
    if not check_syncedlyrics():
        console.print("[red]Error: syncedlyrics command is not installed or not in PATH[/red]")
        console.print("Install it with: [cyan]uv tool install syncedlyrics[/cyan]")
        console.print("Then make sure uv's tool bin directory is in PATH: [cyan]uv tool update-shell[/cyan]")
        return None

    lrclib_result = fetch_lrclib_direct(artist, title, duration, is_cancelled)
    if lrclib_result:
        return lrclib_result

    search_terms = build_search_terms(artist, title)

    try:
        # Use quiet provider fallbacks. Failed providers are expected for obscure
        # tracks; dumping every 401/404 just turns normal misses into terminal soup.
        for term in search_terms:
            if is_cancelled and is_cancelled():
                console.print("[dim]Song changed while fetching lyrics; aborting stale lookup[/dim]")
                return None
            result = run_syncedlyrics_cli(term, LYRICS_PROVIDERS, synced_only=True)
            if result:
                console.print(f"[green]✓ Found synced lyrics via provider fallback:[/green] [dim]{term}[/dim]")
                return result

        # Final fallback: plain lyrics. The UI needs timestamps, so estimate them.
        # This is intentionally last because it is not true synchronization.
        for term in search_terms:
            if is_cancelled and is_cancelled():
                console.print("[dim]Song changed while fetching lyrics; aborting stale lookup[/dim]")
                return None
            result = run_syncedlyrics_cli(term, LYRICS_PROVIDERS, synced_only=False, plain_only=True)
            pseudo = plain_lyrics_to_lrc(result or "", duration)
            if pseudo:
                console.print(f"[yellow]Found plain lyrics via provider fallback; using estimated timing:[/yellow] [dim]{term}[/dim]")
                return pseudo

        return None
    except subprocess.TimeoutExpired:
        console.print("[red]Timed out while fetching lyrics[/red]")
        return None


def parse_lrc(lrc_content: str) -> List[LyricsLine]:
    """Parse .lrc format to timestamp + text, removing inline timestamps"""
    lines = []
    pattern = r'\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)'

    for line in lrc_content.split('\n'):
        match = re.match(pattern, line)
        if match:
            minutes = int(match.group(1))
            seconds = int(match.group(2))
            centiseconds = int(match.group(3)[:2])
            text = match.group(4).strip()

            # Remove inline timestamps (word-level sync)
            text = re.sub(r'<\d{1,2}:\d{2}\.\d{2}>', '', text)
            text = re.sub(r'\s+', ' ', text).strip()

            if text:  # Skip empty lines
                timestamp = minutes * 60 + seconds + centiseconds / 100
                lines.append(LyricsLine(timestamp, text))

    return sorted(lines, key=lambda x: x.timestamp)


def find_current_line(lyrics: List[LyricsLine], position: float) -> int:
    """Find which line should be displayed based on position"""
    global current_offset
    adjusted_position = position + current_offset

    for i in range(len(lyrics) - 1, -1, -1):
        if adjusted_position >= lyrics[i].timestamp:
            return i
    return 0


# ============================================================================
# KEYBOARD CONTROLS
# ============================================================================

def keyboard_listener():
    """Listen for keyboard input to adjust offset (Q=earlier, A=later, Z=reset)"""
    global current_offset
    import tty
    import termios

    old_settings = termios.tcgetattr(sys.stdin)

    try:
        tty.setcbreak(sys.stdin.fileno())

        while True:
            char = sys.stdin.read(1)

            if char == 'q':  # Show lyrics earlier - INCREASE offset (more positive)
                current_offset += 0.1
            elif char == 'a':  # Show lyrics later - DECREASE offset (more negative)
                current_offset -= 0.1
            elif char == 'z':  # Reset to default
                current_offset = TIMING_OFFSET_DEFAULT
            elif char == 'x':  # Exit (Ctrl+C also works)
                break

    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


# ============================================================================
# RENDERING
# ============================================================================

def render_lyrics(lyrics: List[LyricsLine], current_index: int,
                 artist: str, title: str, console_height: int,
                 console_width: int) -> Text:
    """Render lyrics with current line always centered in the window"""

    global current_offset

    # Header takes 3 lines: title + controls + blank line
    header_lines = 3
    available_height = max(5, console_height - header_lines)

    # Split available space evenly around the current line
    lines_above = (available_height - 1) // 2
    lines_below = available_height - lines_above - 1

    text = Text()

    # Title
    title_line = f"🎵 {artist} - {title}"
    text.append(title_line.center(console_width) + "\n",
               style=f"bold {KANAGAWA_SPRING_BLUE}")

    # Controls hint
    controls = f"[Offset: {current_offset:+.1f}s | Q=earlier A=later Z=reset X=exit]"
    text.append(controls.center(console_width) + "\n\n",
               style=f"dim {KANAGAWA_CRYSTAL_BLUE}")

    for i in range(current_index - lines_above, current_index + lines_below + 1):
        # Pad with blank lines when outside lyrics range
        if i < 0 or i >= len(lyrics):
            text.append("\n")
            continue

        line = lyrics[i]

        if i < current_index - 1:
            # Past lines - faded
            text.append(line.text.center(console_width) + "\n",
                       style=f"dim {KANAGAWA_CRYSTAL_BLUE}")

        elif i == current_index - 1:
            # Previous line - wave blue background
            text.append(line.text.center(console_width) + "\n",
                       style=f"{KANAGAWA_FUJI_WHITE} on {KANAGAWA_WAVE_BLUE_1}")

        elif i == current_index:
            # CURRENT line - yellow background, bold, centered
            line_content = f"♪♪  {line.text}  ♪♪"
            text.append(line_content.center(console_width) + "\n",
                       style=f"bold black on {KANAGAWA_CARP_YELLOW}")

        elif i == current_index + 1:
            # Next line - wave blue background
            text.append(line.text.center(console_width) + "\n",
                       style=f"{KANAGAWA_FUJI_WHITE} on {KANAGAWA_WAVE_BLUE_1}")

        else:
            # Future lines - normal
            text.append(line.text.center(console_width) + "\n",
                       style=KANAGAWA_FUJI_WHITE)

    return text


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    """Main application loop"""
    global current_offset

    # Check prerequisites
    if not check_playerctl():
        console.print("[red]Error: playerctl is not installed[/red]")
        console.print("Install it with: [cyan]paru -S playerctl[/cyan]")
        sys.exit(1)

    if not check_syncedlyrics():
        console.print("[red]Error: syncedlyrics command is not installed or not in PATH[/red]")
        console.print("Install it with: [cyan]uv tool install syncedlyrics[/cyan]")
        console.print("Then make sure uv's tool bin directory is in PATH: [cyan]uv tool update-shell[/cyan]")
        sys.exit(1)

    console.clear()

    # Outer loop for song changes
    while True:
        # Get current song
        info = get_spotify_info()
        if not info:
            console.print("[yellow]Waiting for Spotify...[/yellow]")
            console.print("Make sure Spotify is running and playing a song")
            time.sleep(2)
            console.clear()
            continue

        artist, title, _, duration = info

        console.print(f"[cyan]Fetching lyrics for:[/cyan] [bold]{artist} - {title}[/bold]")

        # Fetch lyrics. Abort stale lookups if Spotify changes song mid-search.
        is_cancelled = make_song_cancel_checker(artist, title)
        lrc_content = fetch_synced_lyrics(artist, title, duration, is_cancelled)

        if is_cancelled():
            console.clear()
            continue

        if not lrc_content:
            console.print("[red]No lyrics found for this song[/red]")
            console.print("[dim]Trying next song in 5 seconds...[/dim]")
            time.sleep(5)
            console.clear()
            continue

        # Parse lyrics
        lyrics = parse_lrc(lrc_content)

        if not lyrics:
            console.print("[red]Could not parse lyrics[/red]")
            time.sleep(2)
            console.clear()
            continue

        console.print(f"[green]✓ Found {len(lyrics)} synced lines[/green]")
        time.sleep(1)
        console.clear()

        # Reset offset for new song
        current_offset = TIMING_OFFSET_DEFAULT
        current_song = (artist, title)

        # Start keyboard listener thread
        listener_thread = threading.Thread(target=keyboard_listener, daemon=True)
        listener_thread.start()

        # Live update loop
        with Live(console=console, refresh_per_second=10, screen=True) as live:
            try:
                while True:
                    # Check for song change or pause
                    current_info = get_spotify_info()
                    if not current_info:
                        live.update(
                            Panel(
                                Align.center("[red]Spotify paused or closed[/red]"),
                                border_style="red"
                            )
                        )
                        time.sleep(1)
                        continue

                    new_artist, new_title, position, _ = current_info

                    # Handle song change
                    if (new_artist, new_title) != current_song:
                        console.clear()
                        console.print(f"[yellow]🎵 New song: {new_artist} - {new_title}[/yellow]")
                        time.sleep(1)
                        console.clear()
                        break  # Restart outer loop for new song

                    # Find and render current line
                    current_index = find_current_line(lyrics, position)
                    console_height = console.height
                    console_width = console.width

                    content = render_lyrics(lyrics, current_index, artist, title,
                                          console_height, console_width)
                    centered = Align.center(content, vertical="middle")
                    live.update(centered)

                    time.sleep(0.1)  # 10 FPS for smooth updates

            except KeyboardInterrupt:
                console.clear()
                console.print("[cyan]Thanks for singing along! 🎵[/cyan]")
                sys.exit(0)


if __name__ == "__main__":
    main()
