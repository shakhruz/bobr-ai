"""aiogram-обвязка: команды и текстовые сообщения -> Engine."""
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from engine import Engine, Reply

router = Router()
engine: Engine | None = None  # задаётся в bot.py


def setup(e: Engine) -> None:
    global engine
    engine = e


async def send(message: Message, replies: list[Reply]) -> None:
    for r in replies:
        await message.answer(r.render())


@router.message(Command("start"))
async def cmd_start(message: Message):
    await send(message, await engine.start(message.from_user.id))


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "🦫 Bobr — oʻquvchi, sen — ustozsan: unga tushuntir!\n"
        "🕊 Humo — senga yordam beradi, qiyin boʻlsa yoz «yordam».\n\n"
        "/start — boshidan\n/humo — Humoni chaqirish\n/topic — mavzular\n/report — hisobot\n/reset — mavzuni qayta boshlash")


@router.message(Command("humo"))
async def cmd_humo(message: Message):
    await message.bot.send_chat_action(message.chat.id, "typing")
    await send(message, await engine.ask_humo(message.from_user.id))


@router.message(Command("topic"))
async def cmd_topic(message: Message, command: CommandObject):
    from topics import TOPICS
    if command.args:
        await message.answer(engine.set_topic(message.from_user.id, command.args.strip()))
    else:
        await message.answer("Mavzular:\n" + "\n".join(f"/topic {k} — {t.title}" for k, t in TOPICS.items()))


@router.message(Command("reset"))
async def cmd_reset(message: Message):
    st = engine.db.get_student(message.from_user.id)
    if st:
        engine.db.reset_progress(message.from_user.id, st["current_topic"])
    await message.answer("Mavzu boshidan boshlandi. Biror narsa yoz 🙂")


@router.message(Command("report"))
async def cmd_report(message: Message):
    await message.answer(engine.report(message.from_user.id))


@router.message()
async def on_text(message: Message):
    if not message.text:
        await message.answer("Men faqat matnni oʻqiy olaman, ustoz 🦫 Yozib yubor!")
        return
    await message.bot.send_chat_action(message.chat.id, "typing")
    await send(message, await engine.handle_text(message.from_user.id, message.text))
