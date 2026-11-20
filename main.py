import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, ErrorEvent

from app.config import BOT_TOKEN
from app.database.models import async_main, engine
from app.handlers import router

logger = logging.getLogger(__name__)

COMMANDS = [
    BotCommand(command="start", description="Главное меню"),
    BotCommand(command="cancel", description="Отменить текущее действие"),
]


async def on_error(event: ErrorEvent) -> None:
    """Не даёт боту молча падать: пишет трейсбек в лог и отвечает пользователю."""
    logger.error("Необработанная ошибка", exc_info=event.exception)

    update = event.update
    try:
        if update.callback_query:
            await update.callback_query.answer(
                "Произошла ошибка. Попробуйте ещё раз.", show_alert=True
            )
        elif update.message:
            await update.message.answer(
                "Произошла ошибка. Попробуйте ещё раз или отправьте /start."
            )
    except Exception:
        logger.exception("Не удалось сообщить пользователю об ошибке")


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN не задан. Скопируйте .env.example в .env "
            "и укажите токен, полученный у @BotFather."
        )

    await async_main()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    dp.errors.register(on_error)

    try:
        await bot.set_my_commands(COMMANDS)
        logger.info("Бот запущен")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await engine.dispose()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот выключен")
    except RuntimeError as error:
        logger.error("%s", error)
