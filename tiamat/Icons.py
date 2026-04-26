from Rengar import get_shared_rengar


def change_profile_icon(icon_id):
    try:
        icon_id = int(icon_id)
    except (TypeError, ValueError):
        raise ValueError("Please enter a valid profile icon ID.")

    if icon_id <= 0:
        raise ValueError("Please enter a valid profile icon ID.")

    response = get_shared_rengar().lcu_request(
        "PUT", "/lol-summoner/v1/current-summoner/icon", {"profileIconId": icon_id}
    )
    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"Could not change the profile icon. [{response.status_code}] {response.text}"
        )

    return icon_id
