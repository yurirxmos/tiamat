import requests

from Rengar import get_shared_rengar

SKINS_URL = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/skins.json"
SKINS_TIMEOUT = 10
_CHAMPIONS_CACHE = None


class Champ:
    def __init__(self, name="", key=0):
        self.name = name
        self.key = key
        self.skins = []


def fetch_all_champion_skins(force_refresh=False):
    global _CHAMPIONS_CACHE

    if _CHAMPIONS_CACHE is not None and not force_refresh:
        return _CHAMPIONS_CACHE

    response = requests.get(SKINS_URL, timeout=SKINS_TIMEOUT)
    if response.status_code != 200:
        raise RuntimeError("Error while searching skins.")

    skins_data = response.json()
    champs = {}

    for skin_id, current_skin in skins_data.items():
        load_screen_path = current_skin.get("loadScreenPath", "")
        name_start = load_screen_path.find("ASSETS/Characters/") + len(
            "ASSETS/Characters/"
        )
        champ_name = load_screen_path[name_start : load_screen_path.find("/", name_start)]
        if not champ_name:
            continue

        if champ_name not in champs:
            champs[champ_name] = Champ(name=champ_name)

        skin = {"champion": champ_name}
        name = current_skin.get("name", "")

        if current_skin.get("isBase", False):
            champ_key = skin_id[:-3] if skin_id.endswith("000") else skin_id
            champs[champ_name].key = int(champ_key)
            skin["id"] = skin_id
            skin["name"] = "default"
            champs[champ_name].skins.insert(0, skin)
        elif current_skin.get("questSkinInfo"):
            for skin_tier in current_skin["questSkinInfo"].get("tiers", []):
                tier_skin = skin.copy()
                tier_skin["id"] = skin_tier.get("id", "")
                tier_skin["name"] = skin_tier.get("name", "")
                champs[champ_name].skins.append(tier_skin)
        else:
            skin["id"] = skin_id
            skin["name"] = name
            champs[champ_name].skins.append(skin)

    _CHAMPIONS_CACHE = champs
    return _CHAMPIONS_CACHE


def search_skins_by_name(champions, search_query):
    search_query = search_query.lower().strip()
    found_skins = []

    for champ_name, champ_data in champions.items():
        if search_query in champ_name.lower():
            found_skins.extend(champ_data.skins)
            continue

        for skin in champ_data.skins:
            if search_query in skin["name"].lower():
                found_skins.append(skin)

    return found_skins


def format_skin_label(skin):
    return f"{skin['champion']} - {skin['name']} (ID: {skin['id']})"


def change_profile_background(skin_id):
    try:
        skin_id = int(skin_id)
    except (TypeError, ValueError):
        raise ValueError("Please enter a valid skin ID.")

    response = get_shared_rengar().lcu_request(
        "POST",
        "/lol-summoner/v1/current-summoner/summoner-profile",
        {"key": "backgroundSkinId", "value": skin_id},
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Error changing the background. [{response.status_code}] {response.text}"
        )

    return skin_id
