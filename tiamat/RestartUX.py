from Rengar import get_shared_rengar


def restart():
    response = get_shared_rengar().lcu_request(
        "POST", "/riotclient/kill-and-restart-ux", ""
    )
    if response.status_code not in (200, 204):
        raise RuntimeError(
            f"Could not restart client UX. [{response.status_code}] {response.text}"
        )

    return True
