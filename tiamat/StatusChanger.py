from Rengar import get_shared_rengar


def change_status(status_text):
    response = get_shared_rengar().lcu_request(
        "PUT", "/lol-chat/v1/me", {"statusMessage": status_text.rstrip()}
    )
    if response.status_code not in (200, 201, 204):
        raise RuntimeError(
            f"Could not change status. [{response.status_code}] {response.text}"
        )

    return status_text.rstrip()
