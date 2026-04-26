from Rengar import get_shared_rengar

BADGE_MODE_EMPTY = "empty"
BADGE_MODE_COPY_FIRST = "copy_first"
BADGE_MODE_GLITCHED = "glitched"
BADGE_OPTIONS = (
    (BADGE_MODE_EMPTY, "Empty badges"),
    (BADGE_MODE_COPY_FIRST, "Copy first badge to all"),
    (BADGE_MODE_GLITCHED, "Set all to a glitched ID (0-5)"),
)


def _get_player_data():
    response = get_shared_rengar().lcu_request(
        "GET", "/lol-challenges/v1/summary-player-data/local-player", ""
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Error getting player data. [{response.status_code}] {response.text}"
        )
    return response.json()


def _update_player_preferences(payload):
    response = get_shared_rengar().lcu_request(
        "POST", "/lol-challenges/v1/update-player-preferences/", payload
    )
    if response.status_code not in (200, 201, 204):
        raise RuntimeError(
            f"Error updating badges. [{response.status_code}] {response.text}"
        )


def change_profile_badges(mode, glitched_id=None):
    data = _get_player_data()
    title_id = data.get("title", {}).get("itemId", -1)
    banner_id = data.get("bannerId", "")
    top_challenges = data.get("topChallenges", [])

    if mode == BADGE_MODE_EMPTY:
        new_ids = []
    elif mode == BADGE_MODE_COPY_FIRST:
        if not top_challenges:
            raise RuntimeError("No badges found to copy.")
        try:
            first_id = int(top_challenges[0].get("id"))
        except (TypeError, ValueError):
            raise RuntimeError("Could not read the ID of the first badge.")
        new_ids = [first_id] * 3
    elif mode == BADGE_MODE_GLITCHED:
        try:
            glitched_id = int(glitched_id)
        except (TypeError, ValueError):
            raise ValueError("Please enter a valid glitched badge ID.")

        if not 0 <= glitched_id <= 5:
            raise ValueError("Please enter a number between 0 and 5.")
        new_ids = [glitched_id] * 3
    else:
        raise ValueError("Invalid badge option.")

    payload = {"challengeIds": new_ids}
    if title_id != -1:
        payload["title"] = str(title_id)
    if banner_id:
        payload["bannerAccent"] = banner_id

    _update_player_preferences(payload)
    return mode
