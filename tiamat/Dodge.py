from Rengar import get_shared_rengar


def dodge():
    response = get_shared_rengar().lcu_request(
        "POST",
        '/lol-login/v1/session/invoke?destination=lcdsServiceProxy&method=call&args=["","teambuilder-draft","quitV2",""]',
        "",
    )
    if response.status_code not in (200, 204):
        raise RuntimeError(
            f"Could not dodge queue. [{response.status_code}] {response.text}"
        )

    return True
