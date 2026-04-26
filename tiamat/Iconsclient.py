from Rengar import get_shared_rengar


def icon_client(icon_id):
    try:
        icon_id = int(icon_id)
    except (TypeError, ValueError):
        raise ValueError("Please enter a valid client icon ID.")

    if icon_id <= 0:
        raise ValueError("Please enter a valid client icon ID.")

    response = get_shared_rengar().lcu_request(
        "PUT", "/lol-chat/v1/me", {"icon": icon_id}
    )
    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"Could not change the client icon. [{response.status_code}] {response.text}"
        )

    return icon_id
