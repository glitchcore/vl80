import vlc
import curses
import time
import threading

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
            return time.time() - start_time
        else:
            return player.get_time() / 1000

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
