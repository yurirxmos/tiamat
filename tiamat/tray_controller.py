import logging
from pathlib import Path
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import winreg

import pystray
from PIL import Image, ImageDraw

from AutoAccept import AutoAccept
from Backgrounds import (
    change_profile_background,
    fetch_all_champion_skins,
    format_skin_label,
    search_skins_by_name,
)
from Badges import BADGE_MODE_GLITCHED, BADGE_OPTIONS, change_profile_badges
from disconnect_reconnect_chat import Chat
from Dodge import dodge
from Icons import change_profile_icon
from Iconsclient import icon_client
from InstalockAutoban import InstalockAutoban
from RemoveFriends import remove_all_friends
from RestartUX import restart
from Rengar import LeagueClientNotFoundError, check_league_client, get_shared_rengar
from Reveal import reveal
from Riotidchanger import change_riotid
from StatusChanger import change_status
from settings import AppSettings

logger = logging.getLogger("tiamat")

WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
WINDOWS_RUN_VALUE_NAME = "Tiamat"
ACCOUNT_NOT_DETECTED_LABEL = "Account: not detected"
ACCOUNT_LP_UNRANKED_LABEL = "LP: unranked"
ACCOUNT_LP_UNAVAILABLE_LABEL = "LP: unavailable"
ACCOUNT_WIN_RATE_UNRANKED_LABEL = "Win rate: unranked"
ACCOUNT_WIN_RATE_UNAVAILABLE_LABEL = "Win rate: unavailable"
ACCOUNT_DETAILS_REFRESH_INTERVAL_SECONDS = 15.0
ACCOUNT_DETAILS_RETRY_INTERVAL_SECONDS = 2.0
SOLO_QUEUE_TYPE = "RANKED_SOLO_5x5"


class FormDialog(simpledialog.Dialog):
    def __init__(self, parent, title, fields):
        self.fields = fields
        self.entries = {}
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        for index, field in enumerate(self.fields):
            ttk.Label(master, text=field["label"]).grid(
                row=index, column=0, sticky="w", padx=(0, 12), pady=4
            )
            entry = ttk.Entry(master, width=36)
            entry.grid(row=index, column=1, sticky="ew", pady=4)
            entry.insert(0, field.get("value", ""))
            self.entries[field["key"]] = entry

        master.columnconfigure(1, weight=1)
        first_field = self.fields[0]["key"]
        return self.entries[first_field]

    def apply(self):
        self.result = {key: entry.get() for key, entry in self.entries.items()}


class MultilineDialog(simpledialog.Dialog):
    def __init__(self, parent, title, prompt, initial_value=""):
        self.prompt = prompt
        self.initial_value = initial_value
        self.text_widget = None
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text=self.prompt, justify="left", wraplength=420).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        self.text_widget = tk.Text(master, width=56, height=10, wrap="word")
        self.text_widget.grid(row=1, column=0, sticky="nsew")
        self.text_widget.insert("1.0", self.initial_value)

        master.columnconfigure(0, weight=1)
        master.rowconfigure(1, weight=1)
        return self.text_widget

    def apply(self):
        self.result = self.text_widget.get("1.0", "end").rstrip()


class ListSelectionDialog(simpledialog.Dialog):
    def __init__(self, parent, title, prompt, items, initial_index=0):
        self.prompt = prompt
        self.items = items
        self.initial_index = initial_index
        self.listbox = None
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        self.after_idle(self._raise_window)

        ttk.Label(master, text=self.prompt, justify="left", wraplength=460).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        frame = ttk.Frame(master)
        frame.grid(row=1, column=0, sticky="nsew")

        self.listbox = tk.Listbox(
            frame,
            width=72,
            height=min(14, max(len(self.items), 6)),
            selectmode=tk.SINGLE,
            exportselection=False,
        )
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)

        self.listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        for item in self.items:
            self.listbox.insert(tk.END, item)

        if self.items:
            index = min(max(self.initial_index, 0), len(self.items) - 1)
            self.listbox.selection_set(index)
            self.listbox.activate(index)
            self.listbox.see(index)

        self.listbox.bind("<Double-Button-1>", lambda _event: self.ok())
        self.listbox.bind("<Return>", lambda _event: self.ok())

        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        master.columnconfigure(0, weight=1)
        master.rowconfigure(1, weight=1)
        return self.listbox

    def _raise_window(self):
        self.lift()
        self.attributes("-topmost", True)
        self.after(150, lambda: self.attributes("-topmost", False))
        self.focus_force()
        if self.listbox is not None:
            self.listbox.focus_set()

    def validate(self):
        selection = self.listbox.curselection()
        if selection:
            return True

        active_index = self.listbox.index(tk.ACTIVE)
        if 0 <= active_index < len(self.items):
            self.listbox.selection_set(active_index)
            self.listbox.activate(active_index)
            return True

        self.bell()
        return False

    def apply(self):
        selection = self.listbox.curselection()
        self.result = selection[0] if selection else None


class TrayController:
    def __init__(self, on_ready=None):
        self._on_ready = on_ready
        self.settings = AppSettings.load()
        self.auto_accept = AutoAccept()
        self.instalock_autoban = InstalockAutoban()
        self.chat = Chat()
        self._restore_services()
        self._stop_event = threading.Event()
        self._status_thread = None
        self._blink_on = False
        self._current_icon_frame = None
        self._current_account_name_label = ACCOUNT_NOT_DETECTED_LABEL
        self._current_account_lp_label = ACCOUNT_LP_UNRANKED_LABEL
        self._current_account_win_rate_label = ACCOUNT_WIN_RATE_UNRANKED_LABEL
        self._show_account_ranked_details = False
        self._next_account_refresh_at = 0.0
        self._last_client_available = None
        self._icon_images = {
            "waiting": self._create_status_icon((238, 196, 55, 255), (255, 255, 255, 220)),
            "active_on": self._create_status_icon((46, 204, 113, 255), (255, 255, 255, 220)),
            "active_off": self._create_status_icon((20, 120, 66, 255), (180, 255, 206, 200)),
        }

        self.icon = pystray.Icon(
            "tiamat",
            self._icon_images["waiting"],
            "Tiamat - Waiting for LoL",
            menu=self._build_menu(),
        )
        logger.info("Tray controller initialized.")

    def _restore_services(self):
        self.auto_accept.set_enabled(self.settings.auto_accept_enabled)
        self.instalock_autoban.restore_state(
            self.settings.instalock_enabled,
            self.settings.instalock_champion,
            self.settings.auto_ban_enabled,
            self.settings.auto_ban_champion,
        )

    def _create_status_icon(self, fill_color, outline_color):
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((7, 7, 57, 57), fill=(255, 255, 255, 32))
        draw.ellipse((11, 11, 53, 53), fill=fill_color, outline=outline_color, width=3)
        draw.ellipse((20, 17, 31, 28), fill=(255, 255, 255, 110))
        return image

    def _on_icon_ready(self, icon):
        icon.visible = True
        self._set_icon_frame("waiting", "Tiamat - Waiting for LoL")

        if self._on_ready is not None:
            try:
                self._on_ready()
            except Exception:
                logger.exception("Startup ready callback failed.")

        self._notify("Tiamat has started!", "Tiamat")
        logger.info("Tray icon is visible.")
        self._status_thread = threading.Thread(target=self._monitor_icon_status, daemon=True)
        self._status_thread.start()

    def _is_league_client_available(self):
        port, token = check_league_client(wait=False)
        return bool(port and token)

    def _set_icon_frame(self, frame_name, title):
        if self._current_icon_frame == frame_name and self.icon.title == title:
            return

        self.icon.icon = self._icon_images[frame_name]
        self.icon.title = title
        self._current_icon_frame = frame_name

    def _monitor_icon_status(self):
        logger.info("Tray status monitor started.")
        while not self._stop_event.is_set():
            client_available = self._is_league_client_available()
            current_time = time.monotonic()
            availability_changed = (
                self._last_client_available is None
                or self._last_client_available != client_available
            )
            menu_changed = False

            if availability_changed:
                logger.info(
                    "League client availability changed: %s",
                    "connected" if client_available else "waiting",
                )
                self._last_client_available = client_available

                if not client_available:
                    menu_changed = self._set_account_menu_labels(ACCOUNT_NOT_DETECTED_LABEL)
                    self._next_account_refresh_at = 0.0

            if client_available and (
                availability_changed or current_time >= self._next_account_refresh_at
            ):
                menu_changed = self._refresh_detected_account_details() or menu_changed
                refresh_interval = (
                    ACCOUNT_DETAILS_REFRESH_INTERVAL_SECONDS
                    if self._show_account_ranked_details
                    else ACCOUNT_DETAILS_RETRY_INTERVAL_SECONDS
                )
                self._next_account_refresh_at = current_time + refresh_interval

            if client_available:
                self._blink_on = not self._blink_on
                frame_name = "active_on" if self._blink_on else "active_off"
                title = "Tiamat - LoL connected"
                delay = 0.55
            else:
                self._blink_on = False
                frame_name = "waiting"
                title = "Tiamat - Waiting for LoL"
                delay = 0.8

            try:
                self._set_icon_frame(frame_name, title)
                if menu_changed:
                    self._refresh_menu()
            except Exception:
                logger.exception("Tray status monitor stopped after icon update failure.")
                return

            self._stop_event.wait(delay)

        logger.info("Tray status monitor stopped.")

    def _build_menu(self):
        return pystray.Menu(self._menu_items)

    def _menu_items(self):
        item = pystray.MenuItem
        configs_menu = pystray.Menu(
            item("Icon Changer", self._handle_profile_icon),
            item("Client-Only Icon Changer", self._handle_client_icon),
            item("Background Changer", self._handle_background_change),
            item("Lobby Reveal", self._handle_reveal),
            item(
                "Toggle Auto Accept",
                self._toggle_auto_accept,
                checked=self._auto_accept_checked,
            ),
            item("Dodge", self._handle_dodge),
            item("Riot ID Changer", self._handle_riot_id_change),
            item("Restart Client UX", self._handle_restart_ux),
            item(
                "Toggle Instalock",
                self._toggle_instalock,
                checked=self._instalock_checked,
            ),
            item(
                "Toggle AutoBan",
                self._toggle_autoban,
                checked=self._autoban_checked,
            ),
            item(
                "Disconnect Chat",
                self._toggle_chat,
                checked=self._chat_checked,
            ),
            item("Remove All Friends", self._handle_remove_friends),
            item("Change Profile Badges", self._handle_badges_change),
            item("Change Status", self._handle_status_change),
        )
        menu_items = [item(self._current_account_name_label, self._noop, enabled=False)]

        if self._show_account_ranked_details:
            menu_items.extend(
                [
                    item(self._current_account_lp_label, self._noop, enabled=False),
                    item(self._current_account_win_rate_label, self._noop, enabled=False),
                    pystray.Menu.SEPARATOR,
                ]
            )

        menu_items.extend(
            [
                item("Configs", configs_menu),
                item(
                    "Start with Windows",
                    self._toggle_start_with_windows,
                    checked=self._start_with_windows_checked,
                ),
                item("Exit", self._quit),
            ]
        )
        return tuple(menu_items)

    def run(self):
        logger.info("Starting tray icon event loop.")
        self.icon.run(setup=self._on_icon_ready)
        logger.info("Tray icon event loop stopped.")

    def _with_dialog_root(self, callback):
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.update_idletasks()

        try:
            return callback(root)
        finally:
            root.destroy()

    def _ask_string(self, title, prompt, initial_value=""):
        return self._with_dialog_root(
            lambda root: simpledialog.askstring(
                title,
                prompt,
                initialvalue=initial_value,
                parent=root,
            )
        )

    def _ask_integer(self, title, prompt, initial_value=None, minimum=None, maximum=None):
        return self._with_dialog_root(
            lambda root: simpledialog.askinteger(
                title,
                prompt,
                initialvalue=initial_value,
                minvalue=minimum,
                maxvalue=maximum,
                parent=root,
            )
        )

    def _ask_form(self, title, fields):
        return self._with_dialog_root(lambda root: FormDialog(root, title, fields).result)

    def _ask_multiline(self, title, prompt, initial_value=""):
        return self._with_dialog_root(
            lambda root: MultilineDialog(root, title, prompt, initial_value).result
        )

    def _choose_from_list(self, title, prompt, items, initial_index=0):
        return self._with_dialog_root(
            lambda root: ListSelectionDialog(root, title, prompt, items, initial_index).result
        )

    def _confirm(self, title, prompt):
        return self._with_dialog_root(
            lambda root: messagebox.askyesno(title, prompt, parent=root)
        )

    def _run_menu_callback(self, callback):
        try:
            return callback()
        except Exception as exc:
            logger.exception("Tray menu callback failed.")
            self._show_error(str(exc))
            return None

    def _noop(self, _icon, _item):
        return None

    def _show_error(self, message):
        logger.error("User-facing error: %s", message)
        self._with_dialog_root(
            lambda root: messagebox.showerror("Tiamat", message, parent=root)
        )

    def _select_champion(self, title, initial_value="", include_random=False):
        champion_names = self.instalock_autoban.get_champion_names()
        items = ["Random"] + champion_names if include_random else champion_names

        if not items:
            raise RuntimeError("Champion list is empty.")

        initial_index = 0
        if initial_value:
            normalized_initial = initial_value.lower()
            for index, item in enumerate(items):
                if item.lower() == normalized_initial:
                    initial_index = index
                    break

        selection = self._choose_from_list(
            title,
            "Choose a champion:",
            items,
            initial_index,
        )
        if selection is None:
            return None

        return items[selection]

    def _notify(self, message, title=None):
        if not message:
            return

        try:
            self.icon.notify(message, title)
        except Exception:
            pass

    def _refresh_menu(self):
        try:
            self.icon.update_menu()
        except Exception:
            pass

    def _run_action(self, callback, success_message=None, refresh_menu=True):
        try:
            result = callback()
        except Exception as exc:
            logger.exception("Tray action failed.")
            self._show_error(str(exc))
            return None

        if callable(success_message):
            message = success_message(result)
        else:
            message = success_message

        if message:
            self._notify(message)
        if refresh_menu:
            self._refresh_menu()
        return result

    def _set_account_menu_labels(
        self,
        name_label,
        lp_label=ACCOUNT_LP_UNRANKED_LABEL,
        win_rate_label=ACCOUNT_WIN_RATE_UNRANKED_LABEL,
        show_ranked_details=False,
    ):
        current_state = (
            self._current_account_name_label,
            self._current_account_lp_label,
            self._current_account_win_rate_label,
            self._show_account_ranked_details,
        )
        new_state = (name_label, lp_label, win_rate_label, show_ranked_details)

        if current_state == new_state:
            return False

        self._current_account_name_label = name_label
        self._current_account_lp_label = lp_label
        self._current_account_win_rate_label = win_rate_label
        self._show_account_ranked_details = show_ranked_details
        return True

    def _format_detected_account_name_label(self, account_data):
        game_name = str(account_data.get("gameName") or "").strip()
        tag_line = str(account_data.get("tagLine") or "").strip()
        display_name = str(account_data.get("displayName") or "").strip()
        internal_name = str(account_data.get("internalName") or "").strip()

        if game_name and tag_line:
            return f"Account: {game_name}#{tag_line}"
        if game_name:
            return f"Account: {game_name}"
        if display_name:
            return f"Account: {display_name}"
        if internal_name:
            return f"Account: {internal_name}"
        return ACCOUNT_NOT_DETECTED_LABEL

    def _extract_solo_queue_stats(self, ranked_stats_data):
        queue_map = ranked_stats_data.get("queueMap")
        if isinstance(queue_map, dict):
            queue_stats = queue_map.get(SOLO_QUEUE_TYPE)
            if isinstance(queue_stats, dict):
                return queue_stats

        queues = ranked_stats_data.get("queues")
        if isinstance(queues, list):
            for queue_stats in queues:
                if not isinstance(queue_stats, dict):
                    continue
                if str(queue_stats.get("queueType") or "").strip() == SOLO_QUEUE_TYPE:
                    return queue_stats

        return None

    def _format_solo_queue_labels(self, ranked_stats_data):
        queue_stats = self._extract_solo_queue_stats(ranked_stats_data)
        if not queue_stats:
            return ACCOUNT_LP_UNRANKED_LABEL, ACCOUNT_WIN_RATE_UNRANKED_LABEL

        league_points = queue_stats.get("leaguePoints")
        wins = queue_stats.get("wins")
        losses = queue_stats.get("losses")

        lp_label = (
            f"LP: {league_points}"
            if isinstance(league_points, int)
            else ACCOUNT_LP_UNAVAILABLE_LABEL
        )

        if isinstance(wins, int) and isinstance(losses, int):
            total_games = wins + losses
            if total_games > 0:
                win_rate = (wins / total_games) * 100
                return lp_label, f"Win rate: {win_rate:.1f}%"
            return lp_label, ACCOUNT_WIN_RATE_UNRANKED_LABEL

        return lp_label, ACCOUNT_WIN_RATE_UNAVAILABLE_LABEL

    def _refresh_detected_account_details(self):
        try:
            rengar = get_shared_rengar()
            response = rengar.lcu_request(
                "GET", "/lol-summoner/v1/current-summoner", ""
            )
            if response.status_code != 200:
                return self._set_account_menu_labels(ACCOUNT_NOT_DETECTED_LABEL)

            name_label = self._format_detected_account_name_label(response.json())
            if name_label == ACCOUNT_NOT_DETECTED_LABEL:
                return self._set_account_menu_labels(ACCOUNT_NOT_DETECTED_LABEL)

            lp_label = ACCOUNT_LP_UNAVAILABLE_LABEL
            win_rate_label = ACCOUNT_WIN_RATE_UNAVAILABLE_LABEL

            try:
                ranked_response = rengar.lcu_request(
                    "GET", "/lol-ranked/v1/current-ranked-stats", ""
                )
                if ranked_response.status_code == 200:
                    lp_label, win_rate_label = self._format_solo_queue_labels(
                        ranked_response.json()
                    )
                elif ranked_response.status_code in (204, 404):
                    lp_label = ACCOUNT_LP_UNRANKED_LABEL
                    win_rate_label = ACCOUNT_WIN_RATE_UNRANKED_LABEL
            except (LeagueClientNotFoundError, RuntimeError, ValueError):
                pass

            return self._set_account_menu_labels(
                name_label,
                lp_label,
                win_rate_label,
                show_ranked_details=True,
            )
        except (LeagueClientNotFoundError, RuntimeError, ValueError):
            return self._set_account_menu_labels(ACCOUNT_NOT_DETECTED_LABEL)

    def _auto_accept_checked(self, _item):
        return self.auto_accept.auto_accept_enabled

    def _instalock_checked(self, _item):
        return self.instalock_autoban.instalock_enabled

    def _autoban_checked(self, _item):
        return self.instalock_autoban.auto_ban_enabled

    def _chat_checked(self, _item):
        return self.chat.safe_refresh_state()

    def _start_with_windows_checked(self, _item):
        return self._get_start_with_windows_value() is not None

    def _get_start_with_windows_value(self):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, winreg.KEY_READ) as key:
                value, _value_type = winreg.QueryValueEx(key, WINDOWS_RUN_VALUE_NAME)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise RuntimeError(f"Could not read Windows startup setting: {exc}") from exc

        return value or None

    def _get_start_with_windows_command(self):
        if getattr(sys, "frozen", False):
            return subprocess.list2cmdline([sys.executable])

        executable_path = Path(sys.executable)
        executable_name = executable_path.name.lower()
        if executable_name == "python.exe":
            pythonw_path = executable_path.with_name("pythonw.exe")
            if pythonw_path.exists():
                executable_path = pythonw_path

        script_path = Path(__file__).with_name("tray_app.pyw").resolve()
        return subprocess.list2cmdline([str(executable_path), str(script_path)])

    def _set_start_with_windows_enabled(self, enabled):
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY) as key:
                if enabled:
                    winreg.SetValueEx(
                        key,
                        WINDOWS_RUN_VALUE_NAME,
                        0,
                        winreg.REG_SZ,
                        self._get_start_with_windows_command(),
                    )
                else:
                    try:
                        winreg.DeleteValue(key, WINDOWS_RUN_VALUE_NAME)
                    except FileNotFoundError:
                        pass
        except OSError as exc:
            raise RuntimeError(f"Could not update Windows startup setting: {exc}") from exc

    def _handle_profile_icon(self, _icon, _item):
        icon_id = self._ask_string(
            "Icon Changer",
            "Type the icon ID:",
            self.settings.last_profile_icon,
        )
        if icon_id is None:
            return

        def action():
            changed_icon = change_profile_icon(icon_id)
            self.settings.last_profile_icon = str(changed_icon)
            self.settings.save()
            return changed_icon

        self._run_action(action, lambda icon_value: f"Profile icon changed to {icon_value}.")

    def _handle_client_icon(self, _icon, _item):
        icon_id = self._ask_string(
            "Client-Only Icon Changer",
            "Type the icon ID:",
            self.settings.last_client_icon,
        )
        if icon_id is None:
            return

        def action():
            changed_icon = icon_client(icon_id)
            self.settings.last_client_icon = str(changed_icon)
            self.settings.save()
            return changed_icon

        self._run_action(action, lambda icon_value: f"Client icon changed to {icon_value}.")

    def _handle_background_change(self, _icon, _item):
        search_query = self._ask_string(
            "Background Changer",
            "Type the champion or skin name:",
            self.settings.last_background_query,
        )
        if search_query is None:
            return

        def action():
            if not search_query.strip():
                raise ValueError("Type a champion or skin name.")

            champions = fetch_all_champion_skins()
            skins = search_skins_by_name(champions, search_query)
            if not skins:
                raise RuntimeError("Skin not found.")

            visible_skins = skins[:40]
            selection = self._choose_from_list(
                "Background Changer",
                "Choose a skin:",
                [format_skin_label(skin) for skin in visible_skins],
            )
            if selection is None:
                return None

            selected_skin = visible_skins[selection]
            change_profile_background(selected_skin["id"])
            self.settings.last_background_query = search_query
            self.settings.save()
            return selected_skin

        self._run_action(
            action,
            lambda selected_skin: None
            if selected_skin is None
            else f"Background changed to {selected_skin['champion']} - {selected_skin['name']}.",
        )

    def _handle_reveal(self, _icon, _item):
        self._run_action(reveal, "Opened Porofessor in your browser.")

    def _toggle_auto_accept(self, _icon, _item):
        def action():
            enabled = self.auto_accept.toggle_auto_accept()
            self.settings.auto_accept_enabled = enabled
            self.settings.save()
            return enabled

        self._run_action(
            action,
            lambda enabled: "Auto Accept enabled." if enabled else "Auto Accept disabled.",
        )

    def _handle_dodge(self, _icon, _item):
        self._run_action(dodge, "Queue dodge sent.")

    def _handle_riot_id_change(self, _icon, _item):
        form_result = self._ask_form(
            "Riot ID Changer",
            [
                {"key": "name", "label": "New name", "value": self.settings.last_riot_name},
                {"key": "tag", "label": "New tag", "value": self.settings.last_riot_tag},
            ],
        )
        if form_result is None:
            return

        def action():
            riot_id = change_riotid(form_result["name"], form_result["tag"])
            self.settings.last_riot_name = form_result["name"]
            self.settings.last_riot_tag = form_result["tag"]
            self.settings.save()
            self._refresh_detected_account_details()
            return riot_id

        self._run_action(action, lambda riot_id: f"Riot ID changed to {riot_id}.")

    def _handle_restart_ux(self, _icon, _item):
        self._run_action(restart, "Client UX restart requested.")

    def _toggle_instalock(self, _icon, _item):
        def callback():
            if self.instalock_autoban.instalock_enabled:
                def disable_action():
                    self.instalock_autoban.instalock_enabled = False
                    self.settings.instalock_enabled = False
                    self.settings.instalock_champion = self.instalock_autoban.instalock_champion
                    self.settings.save()
                    return False

                self._run_action(disable_action, "Instalock disabled.")
                return

            initial_value = self.settings.instalock_champion
            if initial_value in ("", "None"):
                initial_value = "Random"

            champion_name = self._select_champion(
                "Toggle Instalock",
                initial_value,
                include_random=True,
            )
            if champion_name is None:
                return

            def enable_action():
                champion = self.instalock_autoban.set_instalock_champion(champion_name)
                self.settings.instalock_enabled = True
                self.settings.instalock_champion = champion
                self.settings.save()
                return champion

            self._run_action(
                enable_action,
                lambda champion: f"Instalock enabled for {champion}.",
            )

        self._run_menu_callback(callback)

    def _toggle_autoban(self, _icon, _item):
        def callback():
            if self.instalock_autoban.auto_ban_enabled:
                def disable_action():
                    self.instalock_autoban.auto_ban_enabled = False
                    self.settings.auto_ban_enabled = False
                    self.settings.auto_ban_champion = self.instalock_autoban.auto_ban_champion
                    self.settings.save()
                    return False

                self._run_action(disable_action, "AutoBan disabled.")
                return

            initial_value = self.settings.auto_ban_champion
            if initial_value == "None":
                initial_value = ""

            champion_name = self._select_champion(
                "Toggle AutoBan",
                initial_value,
                include_random=False,
            )
            if champion_name is None:
                return

            def enable_action():
                champion = self.instalock_autoban.set_auto_ban_champion(champion_name)
                self.settings.auto_ban_enabled = True
                self.settings.auto_ban_champion = champion
                self.settings.save()
                return champion

            self._run_action(
                enable_action,
                lambda champion: f"AutoBan enabled for {champion}.",
            )

        self._run_menu_callback(callback)

    def _toggle_chat(self, _icon, _item):
        self._run_action(
            self.chat.toggle_chat,
            lambda disconnected: "Chat disconnected."
            if disconnected
            else "Chat reconnected.",
        )

    def _handle_remove_friends(self, _icon, _item):
        if not self._confirm(
            "Remove All Friends",
            "This will remove every friend from your League account. Continue?",
        ):
            return

        self._run_action(
            remove_all_friends,
            lambda result: "No friends to remove."
            if result["total"] == 0
            else (
                f"Removed {result['removed']} friend(s)."
                if result["failed"] == 0
                else f"Removed {result['removed']} friend(s) and failed to remove {result['failed']}."
            ),
        )

    def _handle_badges_change(self, _icon, _item):
        badge_choice = self._choose_from_list(
            "Change Profile Badges",
            "Choose a badge option:",
            [label for _mode, label in BADGE_OPTIONS],
        )
        if badge_choice is None:
            return

        mode = BADGE_OPTIONS[badge_choice][0]
        glitched_id = None
        if mode == BADGE_MODE_GLITCHED:
            glitched_id = self._ask_integer(
                "Change Profile Badges",
                "Enter the glitched badge ID (0-5):",
                initial_value=0,
                minimum=0,
                maximum=5,
            )
            if glitched_id is None:
                return

        self._run_action(
            lambda: change_profile_badges(mode, glitched_id),
            "Profile badges updated.",
        )

    def _handle_status_change(self, _icon, _item):
        status_text = self._ask_multiline(
            "Change Status",
            "Type the status text below:",
            self.settings.last_status,
        )
        if status_text is None:
            return

        def action():
            changed_status = change_status(status_text)
            self.settings.last_status = changed_status
            self.settings.save()
            return changed_status

        self._run_action(action, "Status updated.")

    def _toggle_start_with_windows(self, _icon, _item):
        def action():
            enabled = not self._start_with_windows_checked(None)
            self._set_start_with_windows_enabled(enabled)
            return enabled

        self._run_action(
            action,
            lambda enabled: "Tiamat will start with Windows."
            if enabled
            else "Tiamat will no longer start with Windows.",
        )

    def _quit(self, _icon, _item):
        logger.info("Exit requested from tray menu.")
        self._stop_event.set()
        self.icon.stop()
