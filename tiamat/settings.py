from dataclasses import asdict, dataclass
from json import JSONDecodeError, dump, load
from pathlib import Path
import os


@dataclass
class AppSettings:
    auto_accept_enabled: bool = False
    instalock_enabled: bool = False
    instalock_champion: str = "Random"
    auto_ban_enabled: bool = False
    auto_ban_champion: str = "None"
    last_profile_icon: str = ""
    last_client_icon: str = ""
    last_background_query: str = ""
    last_riot_name: str = ""
    last_riot_tag: str = ""
    last_status: str = ""

    @classmethod
    def settings_dir(cls):
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "Tiamat"
        return Path.home() / "AppData" / "Roaming" / "Tiamat"

    @classmethod
    def settings_path(cls):
        return cls.settings_dir() / "settings.json"

    @classmethod
    def load(cls):
        settings_path = cls.settings_path()
        if not settings_path.exists():
            settings = cls()
            settings.save()
            return settings

        try:
            with settings_path.open("r", encoding="utf-8") as file:
                data = load(file)
        except (OSError, JSONDecodeError):
            settings = cls()
            settings.save()
            return settings

        fields = {}
        for field_name, field in cls.__dataclass_fields__.items():
            fields[field_name] = data.get(field_name, field.default)
        return cls(**fields)

    def save(self):
        settings_dir = self.settings_dir()
        settings_dir.mkdir(parents=True, exist_ok=True)

        with self.settings_path().open("w", encoding="utf-8") as file:
            dump(asdict(self), file, indent=2)
