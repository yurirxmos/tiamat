import threading
import time

from Rengar import LeagueClientNotFoundError, get_shared_rengar


class AutoAccept:
    def __init__(self, rengar=None):
        self.auto_accept_enabled = False
        self.rengar = rengar or get_shared_rengar()
        self._monitor_started = False
        self._monitor_lock = threading.Lock()

    def ensure_monitor_started(self):
        with self._monitor_lock:
            if self._monitor_started:
                return

            threading.Thread(target=self.monitor_queue, daemon=True).start()
            self._monitor_started = True

    def set_enabled(self, enabled):
        self.ensure_monitor_started()
        self.auto_accept_enabled = bool(enabled)

    def toggle_auto_accept(self):
        self.set_enabled(not self.auto_accept_enabled)
        return self.auto_accept_enabled

    def accept_match(self):
        self.rengar.lcu_request("POST", "/lol-matchmaking/v1/ready-check/accept", "")

    def monitor_queue(self):
        while True:
            if not self.auto_accept_enabled:
                time.sleep(1)
                continue

            try:
                response = self.rengar.lcu_request(
                    "GET", "/lol-lobby/v2/lobby/matchmaking/search-state", ""
                )
                if response.status_code == 200:
                    match_data = response.json()
                    if match_data.get("searchState") == "Found":
                        self.accept_match()
            except LeagueClientNotFoundError:
                time.sleep(1)
                continue
            except Exception:
                time.sleep(1)
                continue

            time.sleep(0.5)


autoaccept = AutoAccept
