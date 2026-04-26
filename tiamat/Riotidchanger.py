from Rengar import get_shared_rengar


def change_riotid(name, tag):
    name = name.strip()
    tag = tag.strip()

    if not name or not tag:
        raise ValueError("Insert a valid name and tag.")
    if len(name) > 16:
        raise ValueError("Name length is bigger than 16.")
    if len(tag) > 5:
        raise ValueError("Tag length is bigger than 5.")

    response = get_shared_rengar().lcu_request(
        "POST", "/lol-summoner/v1/save-alias", {"gameName": name, "tagLine": tag}
    )
    if response.status_code not in (200, 201, 204):
        raise RuntimeError(
            f"Could not change Riot ID. [{response.status_code}] {response.text}"
        )

    return f"{name}#{tag}"
