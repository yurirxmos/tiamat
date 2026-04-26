from Rengar import LeagueClientNotFoundError, get_shared_rengar


class Chat:
    def __init__(self, rengar=None):
        self.rengar = rengar or get_shared_rengar()
        self.chat_state = False

    def refresh_state(self):
        response = self.rengar.riot_request("GET", "/chat/v1/session", "")
        if response.status_code == 200:
            self.chat_state = response.json().get("state") == "disconnected"
        return self.chat_state

    def safe_refresh_state(self):
        try:
            return self.refresh_state()
        except Exception:
            return self.chat_state

    def disconnect(self):
        response = self.rengar.riot_request(
            "POST", "/chat/v1/suspend", {"config": "disable"}
        )
        if response.status_code not in (200, 204):
            raise RuntimeError(
                f"Could not disconnect chat. [{response.status_code}] {response.text}"
            )
        self.chat_state = True
        return self.chat_state

    def reconnect(self):
        response = self.rengar.riot_request("POST", "/chat/v1/resume", "")
        if response.status_code not in (200, 204):
            raise RuntimeError(
                f"Could not reconnect chat. [{response.status_code}] {response.text}"
            )
        self.chat_state = False
        return self.chat_state

    def set_disconnected(self, disconnected):
        if disconnected:
            return self.disconnect()
        return self.reconnect()

    def toggle_chat(self):
        try:
            current_state = self.refresh_state()
        except LeagueClientNotFoundError:
            current_state = self.chat_state

        return self.set_disconnected(not current_state)
