import base64
import threading
from time import sleep

import psutil
import requests
import urllib3

REQUEST_TIMEOUT = 3
PROCESS_SCAN_SLEEP = 0.5
LEAGUE_CLIENT_PROCESS = "LeagueClientUx.exe"

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_shared_rengar = None
_shared_rengar_lock = threading.Lock()


class LeagueClientNotFoundError(RuntimeError):
    pass


def _iter_league_client_cmdlines():
    for proc in psutil.process_iter(["name", "cmdline"]):
        try:
            name = proc.info.get("name") or ""
            cmdline = proc.info.get("cmdline") or []
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

        if name != LEAGUE_CLIENT_PROCESS:
            continue

        yield cmdline


def _extract_argument(cmdline, prefix):
    for arg in cmdline:
        if arg.startswith(prefix):
            return arg.split("=", 1)[1]
    return None


def find_league_client_credentials():
    for cmdline in _iter_league_client_cmdlines():
        port = _extract_argument(cmdline, "--app-port=")
        token = _extract_argument(cmdline, "--remoting-auth-token=")
        if port and token:
            return port, token
    return None, None


def find_riot_client_credentials():
    for cmdline in _iter_league_client_cmdlines():
        port = _extract_argument(cmdline, "--riotclient-app-port=")
        token = _extract_argument(cmdline, "--riotclient-auth-token=")
        if port and token:
            return port, token
    return None, None


def check_league_client(wait=True):
    while True:
        port, token = find_league_client_credentials()
        if port and token:
            return port, token
        if not wait:
            return None, None
        sleep(PROCESS_SCAN_SLEEP)


def return_lcu_url(league_port):
    return f"https://127.0.0.1:{league_port}"


def return_riot_url(riot_port):
    return f"https://127.0.0.1:{riot_port}"


def return_riot_headers(riot_token):
    auth = base64.b64encode(f"riot:{riot_token}".encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}


def return_lcu_headers(league_token):
    auth = base64.b64encode(f"riot:{league_token}".encode("utf-8")).decode(
        "utf-8"
    )
    return {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}


def get_shared_rengar():
    global _shared_rengar

    with _shared_rengar_lock:
        if _shared_rengar is None:
            _shared_rengar = Rengar()
        return _shared_rengar


class Rengar:
    _credentials_lock = threading.Lock()

    def __init__(self):
        self.league_port = None
        self.league_token = None
        self.league_url = None
        self.league_headers = None
        self.riot_port = None
        self.riot_token = None
        self.riot_url = None
        self.riot_headers = None

    def update_league_credentials(self, force=False, wait=False):
        with self._credentials_lock:
            if not force and self.league_port and self.league_token:
                return

            port, token = find_league_client_credentials()
            if (port is None or token is None) and wait:
                port, token = check_league_client(wait=True)

            if port is None or token is None:
                self.league_port = None
                self.league_token = None
                self.league_url = None
                self.league_headers = None
                raise LeagueClientNotFoundError(
                    "League of Legends client is not running."
                )

            self.league_port = port
            self.league_token = token
            self.league_url = return_lcu_url(port)
            self.league_headers = return_lcu_headers(token)

    def update_riot_credentials(self, force=False, wait=False):
        with self._credentials_lock:
            if not force and self.riot_port and self.riot_token:
                return

            port, token = find_riot_client_credentials()
            if wait:
                while port is None or token is None:
                    check_league_client(wait=True)
                    port, token = find_riot_client_credentials()

            if port is None or token is None:
                self.riot_port = None
                self.riot_token = None
                self.riot_url = None
                self.riot_headers = None
                raise LeagueClientNotFoundError(
                    "Riot client connection is not available yet."
                )

            self.riot_port = port
            self.riot_token = token
            self.riot_url = return_riot_url(port)
            self.riot_headers = return_riot_headers(token)

    def _request(self, updater, url_attr, headers_attr, method, endpoint, body):
        payload = None if body in ("", None) else body
        last_error = None

        for attempt in range(2):
            updater(force=attempt > 0, wait=False)

            try:
                return requests.request(
                    method=method.upper(),
                    url=f"{getattr(self, url_attr)}{endpoint}",
                    headers=getattr(self, headers_attr),
                    json=payload,
                    verify=False,
                    timeout=REQUEST_TIMEOUT,
                )
            except requests.exceptions.RequestException as exc:
                last_error = exc

        raise RuntimeError("Request to the League client failed.") from last_error

    def lcu_request(self, method, endpoint, body=None):
        return self._request(
            updater=self.update_league_credentials,
            url_attr="league_url",
            headers_attr="league_headers",
            method=method,
            endpoint=endpoint,
            body=body,
        )

    def riot_request(self, method, endpoint, body=None):
        return self._request(
            updater=self.update_riot_credentials,
            url_attr="riot_url",
            headers_attr="riot_headers",
            method=method,
            endpoint=endpoint,
            body=body,
        )
