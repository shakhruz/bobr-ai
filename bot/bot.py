"""Точка входа: python bot.py"""
import asyncio
import logging

from aiogram import Bot, Dispatcher

import handlers
from config import get_config
from db import DB
from engine import Engine
from llm import LLM


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    cfg = get_config()
    engine = Engine(DB(cfg.db_path), LLM(cfg.api_key, cfg.model, cfg.effort))
    handlers.setup(engine)
    dp = Dispatcher()
    dp.include_router(handlers.router)
    bot = Bot(cfg.bot_token)
    logging.info("Bobr AI started, model=%s", cfg.model)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
