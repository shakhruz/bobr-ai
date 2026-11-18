import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import router as R  # noqa: E402
from db import DB  # noqa: E402
from engine import Engine, check_answer  # noqa: E402
from llm import LLMError  # noqa: E402
from topics import FRACTIONS  # noqa: E402
from fractions import Fraction  # noqa: E402


def test_rules():
    assert R.route_by_rules("/report") == R.COMMAND
    assert R.route_by_rules("bilmayman") == R.HUMO
    assert R.route_by_rules("Menga yordam bering") == R.HUMO
    assert R.route_by_rules("я не знаю") == R.HUMO
    assert R.route_by_rules("помогите") == R.HUMO
    assert R.route_by_rules("tushunmadim") == R.HUMO
    assert R.route_by_rules("kasrlarni qoʻshamiz") is None
    assert R.route_by_rules("kasrlarni qoʻshamiz", wrong_streak=2) == R.HUMO
    assert R.route_by_verdict("wrong", "none", 1) == R.BOBR
    assert R.route_by_verdict("wrong", "none", 2) == R.HUMO
    assert R.route_by_verdict("dont_know", "none", 1) == R.HUMO
    assert R.route_by_verdict("correct", "distress", 0) == R.HUMO
    assert R.detect_lang("не знаю как") == "ru" and R.detect_lang("bilmayman") == "uz"


def test_check_answer():
    e = Fraction(5, 6)
    assert check_answer("JAVOB: 5/6", e) == (True, "ok")
    assert check_answer("JAVOB: 2/5", e)[0] is False
    assert check_answer("JAVOB: 10/12", e) == (False, "no_reduce")
    assert check_answer("nothing", e) == (False, "no_answer")


class FakeLLM:
    """Классификатор возвращает заготовленный JSON; Бобр решает по belief из system-промпта."""

    def __init__(self, classify):
        self.classify = list(classify)
        self.systems = []

    async def complete_json(self, system, messages, max_tokens=400):
        return self.classify.pop(0)

    async def complete(self, system, messages, max_tokens=400):
        self.systems.append(system)
        if "Режим: ты приносишь" in system:
            return "Ustoz, meni oʻrgat! 1/2 + 1/3 = ?"
        if "Режим: ребёнок объяснил" in system or "Режим: контрольная. Реши" in system:
            # «понимает» ровно то, что записано в belief
            import re
            task = re.search(r"(\d+)/(\d+) \+ (\d+)/(\d+)", system.split("=== СЕЙЧАС ===")[1])
            a, b, c, d = map(int, task.groups())
            if "maxrajlarni ham qoʻshamiz" in system:  # неверная выжимка
                return f"Qoʻshaman: {a}+{c}, {b}+{d}.\nJAVOB: {a + c}/{b + d}"
            from math import lcm
            L = lcm(b, d)
            n, den = a * (L // b) + c * (L // d), L
            from math import gcd
            g = gcd(n, den)
            return f"Keltiraman.\nJAVOB: {n // g}/{den // g}"
        if "Режим: твой прошлый" in system:
            return "Ustoz, qayerda xato qildim?"
        if "контрольная закончена" in system:
            return "Hammasini toʻgʻri yechdim, rahmat ustoz!"
        if "HUMO" in system:
            return "Keling, birga oʻylaymiz: nima uchun 1/2 va 1/3 ni bevosita qoʻshib boʻlmaydi?"
        return "..."


def run(c):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(c)


def mk(classify):
    db = DB(":memory:")
    llm = FakeLLM(classify)
    return Engine(db, llm), llm, db


def onboard(e):
    run(e.start(1))
    run(e.handle_text(1, "Aziza"))
    return run(e.handle_text(1, "kasrlarni tushunmoqchiman"))


def test_bobr_applies_wrong_belief_then_humo_after_two_wrong():
    wrong = {"verdict": "wrong", "mistake_kind": "add_both", "flag": "none",
             "belief": "Ustoz dedi: maxrajlarni ham qoʻshamiz va suratlarni ham."}
    e, llm, db = mk([wrong, wrong])
    out = onboard(e)
    assert out[0].persona == "bobr"
    r1 = run(e.handle_text(1, "suratlarni qoʻshamiz, maxrajlarni ham"))
    assert [x.persona for x in r1] == ["bobr", "bobr"]
    # выжимка ребёнка подставлена в промпт Бобра, и Бобр решил по ней неверно
    apply_sys = [s for s in llm.systems if "Режим: ребёнок объяснил" in s][-1]
    assert "maxrajlarni ham qoʻshamiz" in apply_sys
    assert "JAVOB" not in r1[0].text and "2/6" not in db.get_progress(1, "fractions_add")["stage"]
    assert db.get_progress(1, "fractions_add")["wrong_explanations"] == 1
    # второй неверный подряд -> Хумо
    r2 = run(e.handle_text(1, "yana shunday"))
    assert [x.persona for x in r2] == ["humo"]
    assert "🕊 Humo:" in r2[0].render()
    p = db.get_progress(1, "fractions_add")
    assert p["wrong_explanations"] == 2 and p["hint_level"] == 1 and not p["passed"]


def test_correct_explanation_passes_topic():
    ok = {"verdict": "correct", "mistake_kind": "none", "flag": "none",
          "belief": "Ustoz dedi: umumiy maxraj topamiz, suratlarni qoʻshamiz, qisqartiramiz."}
    e, llm, db = mk([ok])
    onboard(e)
    r = run(e.handle_text(1, "umumiy maxrajga keltiramiz, suratlarni qoʻshamiz, qisqartiramiz"))
    assert any("Nazorat" in x.text for x in r)
    p = db.get_progress(1, "fractions_add")
    assert p["passed"] == 1 and p["last_score"] == "3/3"
    assert "umumiy maxraj" in p["bobr_belief"]
    assert "Bobr nimani tushundi" in e.report(1)


def test_help_word_goes_to_humo_without_classifier():
    e, llm, db = mk([])
    onboard(e)
    r = run(e.handle_text(1, "bilmayman"))
    assert [x.persona for x in r] == ["humo"]


def test_llm_error_is_friendly():
    class Boom(FakeLLM):
        async def complete(self, *a, **k):
            raise LLMError("x")
    db = DB(":memory:")
    e = Engine(db, Boom([]))
    run(e.start(1))
    r = run(e.handle_text(1, "Aziza"))
    assert "Bobr" in r[0].text or r[0].persona in ("bobr", "system")
