#!/usr/bin/env python3
"""
Spotify Live Lyrics Viewer
A beautiful, real-time synced lyrics display for Spotify with Nord theme

Author: Jocce (with Claude)
License: MIT
Repository: https://github.com/YOUR_USERNAME/spotify-live-lyrics
"""

import subprocess
import time
import sys
import re
import threading
from typing import List, Tuple, Optional

# ============================================================================
# DEPENDENCIES CHECK & AUTO-INSTALL
# ============================================================================

def check_dependencies():
    """Check and install required dependencies"""
    missing = []

    try:
        from rich.console import Console
        from rich.text import Text
        from rich.live import Live
        from rich.align import Align
    except ImportError:
        missing.append('rich')

    if missing:
        print(f"Installing missing dependencies: {', '.join(missing)}")
        print("Please run: pip install --user " + ' '.join(missing))
        print("Or on Arch: paru -S " + ' '.join([f'python-{p}' for p in missing]))
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

# Nord color palette
NORD_SNOW_STORM = "#D8DEE9"
NORD_FROST_CYAN = "#88C0D0"
NORD_FROST_BLUE = "#81A1C1"
NORD_AURORA_YELLOW = "#EBCB8B"
NORD3 = "#4C566A"  # Dark grey for context lines

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


def get_spotify_info() -> Optional[Tuple[str, str, float]]:
    """Get artist, title and playback position from Spotify via playerctl"""
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

        return artist, title, position
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
        return None


# ============================================================================
# LYRICS FETCHING & PARSING
# ============================================================================

def fetch_synced_lyrics(artist: str, title: str) -> Optional[str]:
    """Fetch synced lyrics using syncedlyrics"""
    try:
        # Try with enhanced format first
        result = subprocess.run(
            ["syncedlyrics", f"{artist} {title}", "--enhanced"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0 and result.stdout:
            return result.stdout

        # Fallback to standard format
        result = subprocess.run(
            ["syncedlyrics", f"{artist} {title}"],
            capture_output=True,
            text=True,
            timeout=10
        )

        return result.stdout if result.returncode == 0 else None
    except (subprocess.TimeoutExpired, FileNotFoundError):
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
    """Render lyrics with highlighting - responsive to terminal size"""

    global current_offset

    # Calculate dynamic context based on terminal height
    available_lines = max(5, console_height - 6)
    context_before = (available_lines - 3) // 2
    context_after = available_lines - context_before - 3

    text = Text()

    # Title
    title_line = f"🎵 {artist} - {title}"
    text.append(title_line.center(console_width) + "\n",
               style=f"bold {NORD_FROST_CYAN}")

    # Controls hint
    controls = f"[Offset: {current_offset:+.1f}s | Q=earlier A=later Z=reset X=exit]"
    text.append(controls.center(console_width) + "\n\n",
               style=f"dim {NORD_FROST_BLUE}")

    start_idx = max(0, current_index - context_before)
    end_idx = min(len(lyrics), current_index + context_after + 3)

    for i in range(start_idx, end_idx):
        if i >= len(lyrics):
            break

        line = lyrics[i]

        if i < current_index - 1:
            # Past lines - faded
            text.append(line.text.center(console_width) + "\n",
                       style=f"dim {NORD_FROST_BLUE}")

        elif i == current_index - 1:
            # Previous line - grey background
            text.append("\n")
            text.append(line.text.center(console_width) + "\n",
                       style=f"{NORD_SNOW_STORM} on {NORD3}")

        elif i == current_index:
            # CURRENT line - yellow background, bold
            line_content = f"♪♪  {line.text}  ♪♪"
            text.append(line_content.center(console_width) + "\n",
                       style=f"bold black on {NORD_AURORA_YELLOW}")

        elif i == current_index + 1:
            # Next line - grey background
            text.append(line.text.center(console_width) + "\n",
                       style=f"{NORD_SNOW_STORM} on {NORD3}")
            text.append("\n")

        else:
            # Future lines - normal
            text.append(line.text.center(console_width) + "\n",
                       style=NORD_SNOW_STORM)

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

        artist, title, _ = info

        console.print(f"[cyan]Fetching lyrics for:[/cyan] [bold]{artist} - {title}[/bold]")

        # Fetch lyrics
        lrc_content = fetch_synced_lyrics(artist, title)

        if not lrc_content:
            console.print("[red]No synced lyrics found for this song[/red]")
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

                    new_artist, new_title, position = current_info

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
