import vlc
import curses
import time
import threading
import re


LINE_SIZE = 80
MAX_PROGRESS_LEN = 22
LOADING_LEN = 5000


class Subtitles:
    def __init__(self, filename):
        self.filename = filename

    def read_subtitles(self):
        # Read the file
        content = ""
        with open(self.filename, "r", encoding="utf-8") as file:
            content = file.read()
        return content

    def get_entries(self):
        content = self.read_subtitles()
        entries = content.strip().split("\n\n")
        return entries

    def safe_entries(self, entries):
        # Write back to the file
        with open(self.filename, "w", encoding="utf-8") as file:
            file.write("\n\n".join(entries))

    def add(self, position, text, duration=200):
        # Parse position and duration strings to get start and end time
        start_time = self.format_time(position)
        end_time = self.format_time(position + duration)

        entries = self.get_entries()

        # Insert the new subtitle
        new_entry = f"{len(entries) + 1}\n{start_time} --> {end_time}\n{text}"
        position_found = False
        for i, entry in enumerate(entries):
            entry_time = re.search(r"(\d{2}:\d{2}:\d{2},\d{3})", entry).group(1)
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

        self.safe_entries(entries)

    @staticmethod
    def parse_time(s):
        # Convert time string to milliseconds
        hours, minutes, seconds = s.split(":")
        seconds, millis = seconds.split(",")
        return (
            int(hours) * 3600000
            + int(minutes) * 60000
            + int(seconds) * 1000
            + int(millis)
        )

    @staticmethod
    def format_time(ms):
        # Convert milliseconds to time string
        hours = ms // 3600000
        minutes = (ms % 3600000) // 60000
        seconds = (ms % 60000) // 1000
        millis = ms % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


class NcursesApp:
    def __init__(self, key_handler=None, SIZE=5):
        self.SIZE = SIZE
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
        self.stdscr.addstr(line, 0, " " * LINE_SIZE)
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
            if self.key_handler is not None:
                self.key_handler(key)
            time.sleep(0.02)  # Small delay to prevent too rapid updates

    def run(self):
        self.thread = threading.Thread(target=self._run)
        self.thread.start()

    def close(self):
        self.running = False
        curses.endwin()


class Multiplayer:
    def __init__(self, name, N=1) -> None:
        instance = vlc.Instance("--file-caching=5000")
        self.players = [instance.media_player_new(x) for x in [name] * N]

        self.play()
        self.start_time = time.time()
        time.sleep(0.1)

    def play(self):
        for player in self.players:
            player.play()

    def set_time(self, time):
        for player in self.players:
            player.set_time(time)

    def get_time(self):
        return self.players[0].get_time()

    def pause(self):
        for player in self.players:
            player.pause()

    def is_playing(self):
        return self.players[0].is_playing()

    def toggle_fullscreen(self):
        self.players[0].toggle_fullscreen()

    def seek(self, dt):
        # update start time
        self.start_time = time.time() - player.get_time() / 1000

        self.start_time -= dt
        player.set_time(int((time.time() - self.start_time) * 1000))

    def play_pause(self):
        self.pause()

        # update start time
        self.start_time = time.time() - player.get_time() / 1000

    def get_ts(self):
        if player.is_playing():
            return time.time() - self.start_time
        else:
            return player.get_time() / 1000

    def get_ts_str(self):
        return Subtitles.format_time(int(self.get_ts() * 1000))


class ProgressSubtitles:
    def __init__(self, entries, count=3, ui=None):
        self.TIME = 0
        self.TEXT = 1
        self.list_entries = self.make_entries_list(entries)
        self.count = count
        self.ui = ui
        self.progress_len = min(LINE_SIZE, MAX_PROGRESS_LEN)
        self.position = 0
        self.next_start = self.list_entries[self.position][self.TIME]

    def make_entries_list(self, entries):
        list_entries = []
        for entry in entries:
            _, times_string, text = entry.split("\n")
            start_time = re.search(r"(\d{2}:\d{2}:\d{2},\d{3})", times_string).group(0)
            subtitle = (Subtitles.parse_time(start_time), text)
            list_entries.append(subtitle)
        return list_entries

    def print_progress(self, offset):
        bar_len = self.progress_len-2
        if offset < LOADING_LEN:
            left_part = offset / LOADING_LEN
            left = int(bar_len * left_part)
        else:
            left = bar_len

        right = bar_len - left
        bar = f"[{'|'*left}{' '*right}]"
        self.ui.set(1, bar)

    def print_text(self):
        line = 2
        for i in range(self.position, self.position + self.count):
            if i < len(self.list_entries):
                ui.set(line, self.list_entries[i][self.TEXT])
                line += 1

    def step(self, local_time):
        local_time *= 1000
        if self.next_start > local_time:
            # работаем с этим субтитром
            pass
        else:
            # переключаем субтитр
            if self.position < len(self.list_entries)-1 :
                self.position += 1
                self.next_start = self.list_entries[self.position][self.TIME]

        self.print_progress(self.next_start - local_time)
        self.print_text()


if __name__ == "__main__":
    ui = NcursesApp(SIZE=20)

    subtitles = Subtitles("sub/vl80_1part.srt")
    player = Multiplayer("vl80_1part.mp4", 2)
    time.sleep(0.1)
    player.pause()

    prog_subtitles = ProgressSubtitles(subtitles.get_entries(), ui=ui)

    def key_handler(key):
        key = chr(key)
        ui.set(8, f"Key ({key}) was pressed.")

        if key == "f":
            player.toggle_fullscreen()
            ui.set(9, "toggle fullscreen")
        elif key == "p":
            player.play_pause()
            ui.set(9, "play/pause")

        elif key == ".":
            ui.set(9, f"seek > to {player.get_ts_str()}")
            player.seek(0.1)
        elif key == ",":
            ui.set(9, f"seek < to {player.get_ts_str()}")
            player.seek(-0.1)

        elif key == "/":
            ui.set(9, f"seek >> to {player.get_ts_str()}")
            player.seek(5)
        elif key == "m":
            ui.set(9, f"seek << to {player.get_ts_str()}")
            player.seek(-5)

        elif key == "z":
            name = ui.input(1, "name:")
            ui.set(9, f"save {name} at {player.get_time()}")
            subtitles.add(player.get_time(), name)

        elif key == "q":
            ui.close()

        return True

    ui.set_key_handler(key_handler)

    try:
        ui.run()
        while ui.running:
            ui.set(10, f"pos: {player.get_ts_str()}")
            prog_subtitles.step(player.get_ts())
            # ui.set(9, f"pos: {player.get_ts()}")
            time.sleep(0.05)

    except KeyboardInterrupt:
        pass
    finally:
        ui.close()
