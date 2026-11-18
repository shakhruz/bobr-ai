"""Логика диалога без aiogram: тестируется с подменённым LLM."""
import asyncio
import re
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import router as R
from db import DB
from llm import LLMError
from topics import DEFAULT_TOPIC, TOPICS, Topic, fmt_fraction, get_topic

PROMPTS = Path(__file__).parent / "prompts"
HISTORY_N = 8
LABEL = {"bobr": "🦫 Bobr:", "humo": "🕊 Humo:", "system": ""}

SAFE_FAIL = "Voy, internet uzilib qoldi. Birozdan keyin yana yozib koʻr, ustoz!"


@dataclass
class Reply:
    persona: str
    text: str

    def render(self) -> str:
        label = LABEL.get(self.persona, "")
        return f"{label}\n{self.text}" if label else self.text


def render(template: str, **kw) -> str:
    for k, v in kw.items():
        template = template.replace("{" + k + "}", str(v))
    return template


def load_prompt(name: str) -> str:
    return (PROMPTS / name).read_text(encoding="utf-8")


def bobr_mode_block(mode: str) -> str:
    text = load_prompt("bobr_uz.md")
    m = re.search(rf"### MODE {mode}\n(.*?)(?=\n### MODE |\Z)", text, re.S)
    return m.group(1).strip()


def bobr_base() -> str:
    return load_prompt("bobr_uz.md").split("### MODE ask")[0]


def lang_hint(lang: str) -> str:
    return "Ребёнок пишет по-русски — отвечай по-русски (обращение «ты», ребёнка зови «устоз»)." if lang == "ru" else ""


def parse_answer(text: str) -> Fraction | None:
    m = re.search(r"JAVOB:\s*(\d+)\s*/\s*(\d+)", text, re.I)
    if not m or int(m.group(2)) == 0:
        return None
    return Fraction(int(m.group(1)), int(m.group(2)))  # Fraction сам сократит; проверяем "сырую" форму отдельно


def raw_answer(text: str) -> tuple[int, int] | None:
    m = re.search(r"JAVOB:\s*(\d+)\s*/\s*(\d+)", text, re.I)
    return (int(m.group(1)), int(m.group(2))) if m else None


def strip_answer_line(text: str) -> str:
    return re.sub(r"\n?\s*`?JAVOB:.*$", "", text, flags=re.I | re.S).strip()


def check_answer(text: str, expected: Fraction) -> tuple[bool, str]:
    """Верно только если ответ равен эталону И записан несокращаемой дробью."""
    raw = raw_answer(text)
    if raw is None:
        return False, "no_answer"
    n, d = raw
    if d == 0 or Fraction(n, d) != expected:
        return False, "wrong_value"
    if (n, d) != (expected.numerator, expected.denominator):
        return False, "no_reduce"
    return True, "ok"


def build_messages(history) -> list[dict]:
    """Склеивает историю в чередующиеся user/assistant, последняя — user."""
    msgs: list[dict] = []
    for h in history:
        role = "user" if h["role"] == "child" else "assistant"
        text = h["text"] if role == "user" or h["persona"] == "bobr" else f"[Humo]: {h['text']}"
        if msgs and msgs[-1]["role"] == role:
            msgs[-1]["content"] += "\n" + text
        else:
            msgs.append({"role": role, "content": text})
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    if not msgs or msgs[-1]["role"] != "user":
        msgs.append({"role": "user", "content": "(davom et)"})
    return msgs


class Engine:
    def __init__(self, db: DB, llm):
        self.db, self.llm = db, llm

    # ---------- публичное
    async def start(self, tg_id: int) -> list[Reply]:
        self.db.delete_student(tg_id)
        self.db.create_student(tg_id)
        text = ("Salom! Men Bobrman 🦫 Matematikani yaxshi koʻrishni oʻrganyapman, lekin hali juda kam bilaman. "
                "Seni oʻqituvchi — ustoz deb chaqirsam maylimi? Isming nima?")
        self.db.add_message(tg_id, "bot", "bobr", text)
        return [Reply("bobr", text)]

    async def handle_text(self, tg_id: int, text: str) -> list[Reply]:
        st = self.db.get_student(tg_id)
        if st is None:
            return await self.start(tg_id)
        text = text.strip()[:1500]
        lang = R.detect_lang(text)
        if lang != st["lang"]:
            self.db.update_student(tg_id, lang=lang)
        self.db.add_message(tg_id, "child", "child", text)
        try:
            if st["onboarding"] != "done":
                return await self._onboard(tg_id, st, text, lang)
            return await self._learn(tg_id, st, text, lang)
        except LLMError:
            return [Reply("system", SAFE_FAIL)]

    async def ask_humo(self, tg_id: int) -> list[Reply]:
        st = self.db.get_student(tg_id)
        if st is None or st["onboarding"] != "done":
            return [Reply("system", "Avval /start bosib, tanishib olaylik 🙂")]
        self.db.add_message(tg_id, "child", "child", "yordam")
        try:
            topic = get_topic(st["current_topic"])
            p = self.db.get_progress(tg_id, topic.key)
            return [await self._humo(tg_id, st, topic, p, "dont_know", "no_knowledge", "none", st["lang"])]
        except LLMError:
            return [Reply("system", SAFE_FAIL)]

    def set_topic(self, tg_id: int, key: str) -> str:
        if key not in TOPICS:
            return "Bunday mavzu yoʻq. Mavjud: " + ", ".join(TOPICS)
        if not TOPICS[key].ready:
            return "Bu mavzu tez orada tayyor boʻladi. Hozircha: fractions_add"
        self.db.update_student(tg_id, current_topic=key)
        return f"Mavzu tanlandi: {TOPICS[key].title}. Davom etish uchun biror narsa yoz."

    def report(self, tg_id: int) -> str:
        st = self.db.get_student(tg_id)
        if st is None:
            return "Maʼlumot yoʻq: avval /start."
        lines = [f"📋 Hisobot: {st['name'] or '—'}", f"Maqsad: {st['goal'] or '—'}"]
        for p in self.db.all_progress(tg_id):
            t = get_topic(p["topic"])
            lines.append(
                f"\nMavzu: {t.title}\n  bosqich: {p['stage']} · urinishlar: {p['attempts']} · "
                f"notoʻgʻri tushuntirishlar: {p['wrong_explanations']} · oʻzlashtirildi: {'ha' if p['passed'] else 'yoʻq'}"
                f"{' · nazorat: ' + p['last_score'] if p['last_score'] else ''}\n"
                f"  Bobr nimani tushundi: {p['bobr_belief'] or '—'}")
        ms = self.db.mistakes_summary(tg_id)
        if ms:
            lines.append("\nTez-tez uchraydigan xatolar:")
            lines += [f"  • {m['kind']}: {m['n']} marta" for m in ms]
        return "\n".join(lines)

    # ---------- знакомство
    async def _onboard(self, tg_id, st, text, lang) -> list[Reply]:
        if st["onboarding"] == "name":
            name = re.sub(r"[^\w\-ʻʼ' ]", "", text, flags=re.U).split()[:1]  # только имя, без фамилии
            name = name[0][:30] if name else "doʻstim"
            self.db.update_student(tg_id, name=name, onboarding="goal")
            reply = (f"{name}, juda yoqimli ism! 🦫 Ustoz deb chaqiraman. Ayt-chi, matematikadan nimani tushunishni xohlaysan? "
                     "Masalan: «kasrlarni tushunmoqchiman».")
            self.db.add_message(tg_id, "bot", "bobr", reply)
            return [Reply("bobr", reply)]
        # goal
        self.db.update_student(tg_id, goal=text[:200], onboarding="done")
        st = self.db.get_student(tg_id)
        topic = get_topic(st["current_topic"] or DEFAULT_TOPIC)
        p = self.db.get_progress(tg_id, topic.key)
        out = [await self._bobr_ask(tg_id, st, topic, p, lang)]
        return out

    # ---------- обучение
    async def _learn(self, tg_id, st, text, lang) -> list[Reply]:
        topic = get_topic(st["current_topic"])
        p = self.db.get_progress(tg_id, topic.key)
        if p["passed"]:  # тема засчитана: начать заново
            p = self.db.reset_progress(tg_id, topic.key)
            return [await self._bobr_ask(tg_id, st, topic, p, lang)]
        forced = R.route_by_rules(text, p["wrong_streak"], bool(p["humo_active"]))
        task = topic.tasks[topic.teach_idx]
        if R.is_help_request(text):
            verdict_d = {"verdict": "dont_know", "mistake_kind": "no_knowledge", "belief": p["bobr_belief"], "flag": "none"}
        else:
            verdict_d = await self._classify(topic, task, p["bobr_belief"], text)
        verdict = verdict_d["verdict"]
        kind = verdict_d["mistake_kind"]
        flag = verdict_d["flag"]
        belief = verdict_d["belief"] or p["bobr_belief"]

        bad = verdict in ("wrong", "dont_know")
        streak = p["wrong_streak"] + 1 if bad else 0
        upd = dict(wrong_streak=streak, attempts=p["attempts"] + 1)
        if bad:
            upd["wrong_explanations"] = p["wrong_explanations"] + 1
            self.db.add_mistake(tg_id, topic.key, kind if kind not in ("none", "") else "other")
        if verdict in ("correct", "partial", "wrong"):
            upd["bobr_belief"] = belief  # Бобр учится из слов ребёнка — даже неверных
        self.db.update_progress(tg_id, topic.key, **upd)
        p = self.db.get_progress(tg_id, topic.key)

        persona = R.HUMO if forced == R.HUMO else R.route_by_verdict(verdict, flag, streak)
        if p["humo_active"] and bad:  # Хумо уже ведёт ребёнка — не бросаем на середине лестницы
            persona = R.HUMO
        if flag == "offtopic" and persona == R.BOBR:
            return [await self._bobr(tg_id, st, topic, p, "chat", task=task.text, lang=lang)]
        if persona == R.HUMO:
            return [await self._humo(tg_id, st, topic, p, verdict, kind, flag, lang)]
        return await self._bobr_apply(tg_id, st, topic, p, verdict, kind, lang)

    async def _classify(self, topic: Topic, task, prev_belief: str, text: str) -> dict:
        system = render(
            load_prompt("router.md"),
            topic_title=topic.title, method=topic.method, task=task.text, prev_belief=prev_belief or "(hech narsa bilmaydi)",
            mistakes="\n".join(f"- {k}: {v}" for k, v in topic.mistakes.items()), child_text=text)
        try:
            d = await self.llm.complete_json(system, [{"role": "user", "content": text}], max_tokens=350)
        except LLMError:
            d = {}
        v = d.get("verdict") if d.get("verdict") in ("correct", "partial", "wrong", "dont_know") else "partial"
        flag = d.get("flag") if d.get("flag") in ("distress", "offtopic", "none") else "none"
        return {"verdict": v, "mistake_kind": str(d.get("mistake_kind") or "other"),
                "belief": str(d.get("belief") or "")[:600], "flag": flag}

    # ---------- Бобр
    async def _bobr(self, tg_id, st, topic, p, mode, task="", lang="uz", **extra) -> Reply:
        system = render(
            bobr_base() + "\n" + bobr_mode_block(mode),
            name=st["name"] or "doʻst", belief=p["bobr_belief"] or "(Bobr hech narsa bilmaydi — mavzu butunlay yangi)",
            lang_hint=lang_hint(lang), task=task, topic_title=topic.title,
            mistake_hint=extra.get("mistake_hint", ""), verdict=extra.get("verdict", ""),
            score=extra.get("score", ""), total=extra.get("total", ""), details=extra.get("details", ""))
        text = await self.llm.complete(system, build_messages(self.db.last_messages(tg_id, HISTORY_N)), max_tokens=400)
        return self._say(tg_id, "bobr", text)

    def _say(self, tg_id, persona, text) -> Reply:
        self.db.add_message(tg_id, "bot", persona, text)
        return Reply(persona, text)

    async def _bobr_ask(self, tg_id, st, topic, p, lang) -> Reply:
        self.db.update_progress(tg_id, topic.key, stage="explain")
        return await self._bobr(tg_id, st, topic, p, "ask", task=topic.tasks[topic.teach_idx].text, lang=lang)

    async def solve_by_belief(self, tg_id, st, topic, p, mode, task, verdict, kind, lang) -> tuple[str, bool, str]:
        hint = topic.mistakes.get(kind) or "ошибается так, как типично для 5-классника в этой теме"
        reply = await self._bobr(tg_id, st, topic, p, mode, task=task.text, lang=lang, mistake_hint=hint, verdict=verdict)
        ok, why = check_answer(reply.text, task.answer)
        return strip_answer_line(reply.text), ok, why

    async def _bobr_apply(self, tg_id, st, topic, p, verdict, kind, lang) -> list[Reply]:
        idx = topic.apply_idx[p["task_idx"] % len(topic.apply_idx)]
        task = topic.tasks[idx]
        # _bobr уже пишет сообщение в историю; перезапишем очищенным текстом ниже
        text, ok, why = await self.solve_by_belief(tg_id, st, topic, p, "apply", task, verdict, kind, lang)
        self._replace_last_bot(tg_id, text)
        self.db.update_progress(tg_id, topic.key, task_idx=p["task_idx"] + 1, hint_level=0, humo_active=0)
        out = [Reply("bobr", text)]
        if ok and verdict != "wrong":
            return out + await self._test(tg_id, st, topic, lang)
        if not ok and why != "no_answer":
            self.db.add_mistake(tg_id, topic.key, kind if kind in topic.mistakes else ("no_reduce" if why == "no_reduce" else "other"))
        p2 = self.db.get_progress(tg_id, topic.key)
        out.append(await self._bobr(tg_id, st, topic, p2, "fix", task=task.text, lang=lang))
        return out

    def _replace_last_bot(self, tg_id, text):
        self.db.c.execute("UPDATE messages SET text=? WHERE id=(SELECT MAX(id) FROM messages WHERE student_id=? AND role='bot')",
                          (text, tg_id))
        self.db.c.commit()

    async def _test(self, tg_id, st, topic, lang) -> list[Reply]:
        p = self.db.get_progress(tg_id, topic.key)
        tasks = [topic.tasks[i] for i in topic.test_idx]

        async def one(t):
            system = render(bobr_base() + "\n" + bobr_mode_block("test"), name=st["name"] or "doʻst",
                            belief=p["bobr_belief"] or "(hech narsa)", lang_hint=lang_hint(lang), task=t.text,
                            mistake_hint="ошибается так, как типично для 5-классника: пропускает неясный шаг",
                            topic_title=topic.title)
            return await self.llm.complete(system, [{"role": "user", "content": "(nazorat ishi)"}], max_tokens=300)

        raws = await asyncio.gather(*(one(t) for t in tasks))
        results = [check_answer(r, t.answer) for r, t in zip(raws, tasks)]
        score = sum(1 for ok, _ in results if ok)
        lines = []
        for t, r, (ok, why) in zip(tasks, raws, results):
            ans = raw_answer(r)
            got = f"{ans[0]}/{ans[1]}" if ans else "?"
            lines.append(f"{t.text} = {got} {'✓' if ok else '✗ (' + why + ')'}")
        for (ok, why), t in zip(results, tasks):
            if not ok:
                self.db.add_mistake(tg_id, topic.key, why if why != "wrong_value" else "other")
        passed = score >= 2
        self.db.update_progress(tg_id, topic.key, stage="done" if passed else "explain", passed=int(passed),
                                last_score=f"{score}/{len(tasks)}", wrong_streak=0)
        header = "📝 Nazorat ishi:\n" + "\n".join(lines)
        self.db.add_message(tg_id, "bot", "bobr", header)
        p = self.db.get_progress(tg_id, topic.key)
        res = await self._bobr(tg_id, st, topic, p, "result", lang=lang, score=score, total=len(tasks), details="; ".join(lines))
        return [Reply("bobr", header), res]

    # ---------- Хумо
    async def _humo(self, tg_id, st, topic, p, verdict, kind, flag, lang) -> Reply:
        level = min(p["hint_level"], 3)
        task = topic.tasks[topic.teach_idx]
        system = render(
            load_prompt("humo_uz.md"), name=st["name"] or "doʻst", hint_level=level, task=task.text, method=topic.method,
            topic_title=topic.title, verdict=verdict, mistake_kind=kind, lang_hint=lang_hint(lang),
            flag_block=load_prompt("humo_distress.txt") if flag == "distress" else "")
        text = await self.llm.complete(system, build_messages(self.db.last_messages(tg_id, HISTORY_N)), max_tokens=400)
        self.db.update_progress(tg_id, topic.key, hint_level=min(level + 1, 3), humo_active=1, wrong_streak=0)
        return self._say(tg_id, "humo", text)
