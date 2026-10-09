from datetime import UTC, datetime


def now() -> str:
    return datetime.now(UTC).isoformat()


def freshness(observation: dict | None, photo: dict | None, created_at: str) -> str:
    if not observation or observation["location_state"] == "unknown":
        return "unknown_location"
    current = datetime.now(UTC)
    timestamps = [created_at, observation["confirmed_at"]]
    if photo and photo["captured_at"]:
        timestamps.append(photo["captured_at"])
    if any(datetime.fromisoformat(t) > current for t in timestamps):
        return "unknown_clock"
    if (
        observation["review_after"]
        and datetime.fromisoformat(observation["review_after"]) < current
    ):
        return "needs_recheck"
    if photo and photo["captured_at"] is None:
        return "unknown_photo_time"
    return "last_recorded"  # Never means present/live location verified.
