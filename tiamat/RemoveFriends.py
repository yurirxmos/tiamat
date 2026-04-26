from Rengar import get_shared_rengar


def remove_all_friends():
    response = get_shared_rengar().lcu_request("GET", "/lol-chat/v1/friends", "")
    if response.status_code != 200:
        raise RuntimeError(
            f"Error fetching friends. [{response.status_code}] {response.text}"
        )

    friends = response.json()
    if not friends:
        return {"removed": 0, "failed": 0, "total": 0}

    removed_count = 0
    failed_count = 0
    for friend in friends:
        friend_id = friend.get("pid")
        try:
            delete_response = get_shared_rengar().lcu_request(
                "DELETE", f"/lol-chat/v1/friends/{friend_id}", ""
            )
            if delete_response.status_code in (200, 204):
                removed_count += 1
            else:
                failed_count += 1
        except Exception:
            failed_count += 1

    return {
        "removed": removed_count,
        "failed": failed_count,
        "total": len(friends),
    }
