import webbrowser

from Rengar import get_shared_rengar

_REGION_CACHE = None


class ChampionSelectNotFoundError(RuntimeError):
    pass


def _get_region(rengar):
    global _REGION_CACHE

    if _REGION_CACHE:
        return _REGION_CACHE

    response = rengar.lcu_request("GET", "/riotclient/region-locale", "")
    if response.status_code != 200:
        return ""

    _REGION_CACHE = response.json().get("webRegion", "")
    return _REGION_CACHE


def get_reveal_url():
    rengar = get_shared_rengar()
    champ_select = rengar.lcu_request("GET", "/lol-champ-select/v1/session", "")

    if champ_select.status_code != 200 or "RPC_ERROR" in champ_select.text:
        raise ChampionSelectNotFoundError("Not in champion select.")

    champ_select_data = champ_select.json()
    summ_names = []
    is_ranked = False

    for player in champ_select_data.get("myTeam", []):
        if player.get("nameVisibilityType") == "HIDDEN":
            is_ranked = True
            break

        summoner_id = player.get("summonerId")
        if summoner_id == "0":
            continue

        summoner = rengar.lcu_request("GET", f"/lol-summoner/v1/summoners/{summoner_id}", "")
        if summoner.status_code == 200:
            summoner_data = summoner.json()
            summ_names.append(
                f"{summoner_data['gameName']}%23{summoner_data['tagLine']}"
            )

    if is_ranked:
        summ_names = []
        participants = rengar.riot_request("GET", "/chat/v5/participants", "")
        participants_data = participants.json()

        for participant in participants_data.get("participants", []):
            if "champ-select" not in participant.get("cid", ""):
                continue
            summ_names.append(
                f"{participant['game_name']}%23{participant['game_tag']}"
            )

    region = _get_region(rengar)
    if not region or not summ_names:
        raise RuntimeError("Failed to get region or summoner names.")

    return f"https://porofessor.gg/pregame/{region}/{','.join(summ_names)}/soloqueue/season"


def reveal():
    url = get_reveal_url()
    webbrowser.open(url)
    return url
