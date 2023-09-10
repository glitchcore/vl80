import vlc
import curses
import time
import threading
import re

class Subtitles:
    def __init__(self, filename):
        self.filename = filename
    
    def add(self, position, text, duration=200):
        # Parse position and duration strings to get start and end time
        start_time = self.format_time(position)
        end_time = self.format_time(position + duration)

        # Read the file
        with open(self.filename, 'r', encoding="utf-8") as file:
            content = file.read()
            entries = content.strip().split("\n\n")

        # Insert the new subtitle
        new_entry = f"{len(entries) + 1}\n{start_time} --> {end_time}\n{text}"
        position_found = False
        for i, entry in enumerate(entries):
            entry_time = re.search(r'(\d{2}:\d{2}:\d{2},\d{3})', entry).group(1)
            if self.parse_time(entry_time) > self.parse_time(start_time):
                entries.insert(i, new_entry)
                position_found = True
                break

        # If the subtitle is to be placed at the end
        if not position_found:
            entries.append(new_entry)

        # Update indices
        for i, entry in enumerate(entries):
            lines = entry.split("\n")
            lines[0] = str(i + 1)
            entries[i] = "\n".join(lines)

        # Write back to the file
        with open(self.filename, 'w', encoding="utf-8") as file:
            file.write("\n\n".join(entries))

    @staticmethod
    def parse_time(s):
        # Convert time string to milliseconds
        hours, minutes, seconds = s.split(":")
        seconds, millis = seconds.split(",")
        return int(hours) * 3600000 + int(minutes) * 60000 + int(seconds) * 1000 + int(millis)

    @staticmethod
    def format_time(ms):
        # Convert milliseconds to time string
        hours = ms // 3600000
        minutes = (ms % 3600000) // 60000
        seconds = (ms % 60000) // 1000
        millis = ms % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

class NcursesApp:
    def __init__(self, key_handler=None):
        self.SIZE = 5
        self.strings = [""] * self.SIZE

        self.key_handler = key_handler
        self.running = True
        self._lock = False

        self.stdscr = curses.initscr()
        curses.curs_set(0)  # Hide cursor
        self.stdscr.clear()
        self.refresh()

    def set_key_handler(self, key_handler=None):
        self.key_handler = key_handler

    def refresh(self):
        if not self._lock:
            self.stdscr.clear()
            for i, s in enumerate(self.strings):
                self.stdscr.addstr(i, 0, s)
            self.stdscr.refresh()

    def set(self, line, text):
        if 0 <= line < self.SIZE:
            self.strings[line] = text
            self.refresh()

    def input(self, line, prompt):
        self._lock = True
        self.stdscr.addstr(line, 0, " " * 80)
        self.stdscr.addstr(line, 0, prompt)
        self.stdscr.refresh()
        curses.echo()  # Enable user input
        user_input = self.stdscr.getstr(line, len(prompt) + 1, 80)  # Get user input
        curses.noecho()  # Disable user input
        self._lock = False
        self.refresh()
        return user_input.decode()

    def _run(self):
        while self.running:
            key = self.stdscr.getch()  # Get user input
            self.key_handler(key)
            time.sleep(0.02)  # Small delay to prevent too rapid updates

    def run(self):
        self.thread = threading.Thread(target=self._run)
        self.thread.start()

    def close(self):
        self.running = False
        curses.endwin()

if __name__ == "__main__":
    ui = NcursesApp()


    subtitles = Subtitles("vl80.srt")

    instance = vlc.Instance("--file-caching=5000")
    player = instance.media_player_new("vl80.mp4")

    player.play()
    start_time = time.time()
    time.sleep(0.1)

    def seek(dt):
        global start_time

        start_time -= dt
        player.set_time(int((time.time() - start_time) * 1000))

        # update start time
        start_time = time.time() - player.get_time() / 1000

    def play_pause():
        global start_time

        player.pause()

        # update start time
        start_time = time.time() - player.get_time() / 1000

    def get_ts():
        if player.is_playing():
            return Subtitles.format_time(int((time.time() - start_time) * 1000))
        else:
            return Subtitles.format_time(int(player.get_time()))

    def key_handler(key):
        key = chr(key)
        ui.set(0, f"Key ({key}) was pressed.")

        if key == "f":
            player.toggle_fullscreen()
            ui.set(1, "toggle fullscreen")
        elif key == "p":
            play_pause()
            ui.set(1, "play/pause")

        elif key == ".":
            ui.set(1, f"seek > to {get_ts()}")
            seek(0.1)
        elif key == ",":
            ui.set(1, f"seek < to {get_ts()}")
            seek(-0.1)
        
        elif key == "/":
            ui.set(1, f"seek >> to {get_ts()}")
            seek(5)
        elif key == "m":
            ui.set(1, f"seek << to {get_ts()}")
            seek(-5)

        elif key == "z":
            name = ui.input(1, "name:")
            ui.set(1, f"save {name} at {player.get_time()}")
            subtitles.add(player.get_time(), name)

        elif key == "q":
            ui.close()

        return True

    ui.set_key_handler(key_handler)

    try:
        ui.run()
        # t_start = time.time() * 1000 - player.get_time()

        while ui.running:
            ui.set(3, f"pos: {get_ts()}")
            # ui.set(4, f"paused: {player.is_playing()}")
            time.sleep(0.05)
            # player.set_time(int(time.time() * 1000 - t_start))
        
    except KeyboardInterrupt:
        pass
    finally:
        ui.close()
