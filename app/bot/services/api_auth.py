from app.core.config import get_settings

_cfg = get_settings()


def bot_headers(user_id: int | None = None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if _cfg.bot_api_token:
        headers["X-Bot-Token"] = _cfg.bot_api_token
    if user_id is not None:
        headers["X-Bot-User-Id"] = str(user_id)
    return headers
