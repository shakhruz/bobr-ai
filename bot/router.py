"""Роутер: правила сначала, потом решение по вердикту LLM-классификатора."""
import re

HELP_WORDS = [
    "bilmayman", "bilmadim", "yordam", "tushunmadim", "tushunmayapman", "qiyin", "bilmiman",
    "не знаю", "незнаю", "помогите", "помоги", "не понимаю", "не понял", "не поняла", "помощь", "сложно",
    "humo", "xumo", "хумо",
]
COMMANDS = {"/start", "/help", "/report", "/topic", "/reset", "/humo"}

BOBR, HUMO, COMMAND = "bobr", "humo", "command"


def is_help_request(text: str) -> bool:
    t = text.lower().replace("ʻ", "'").replace("ʼ", "'").replace("’", "'")
    return any(w in t for w in HELP_WORDS)


def detect_lang(text: str) -> str:
    cyr = len(re.findall(r"[А-Яа-яЁё]", text))
    lat = len(re.findall(r"[A-Za-z]", text))
    if cyr > lat and cyr >= 3:
        return "ru"
    return "uz"


def route_by_rules(text: str, wrong_streak: int = 0, humo_active: bool = False) -> str | None:
    """Возвращает 'command' / 'humo' или None (решит классификатор)."""
    t = text.strip()
    if t.startswith("/") and t.split()[0].split("@")[0].lower() in COMMANDS:
        return COMMAND
    if is_help_request(t):
        return HUMO
    if wrong_streak >= 2:
        return HUMO
    return None


def route_by_verdict(verdict: str, flag: str, wrong_streak: int) -> str:
    """wrong_streak — уже с учётом текущего ответа."""
    if flag == "distress":
        return HUMO
    if verdict == "dont_know":
        return HUMO
    if verdict == "wrong" and wrong_streak >= 2:
        return HUMO
    return BOBR
