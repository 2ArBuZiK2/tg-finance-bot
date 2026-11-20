"""Минимальная замена Telegram API для интеграционных тестов.

Харнесс прогоняет настоящие хендлеры и FSM, но вместо сети складывает
отправленные сообщения и нажатия кнопок в списки, которые проверяет тест.
"""

from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.methods import (
    AnswerCallbackQuery,
    EditMessageReplyMarkup,
    EditMessageText,
    SendMessage,
    SetMyCommands,
)
from aiogram.types import (
    CallbackQuery,
    Chat,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
    Update,
    User,
)

BOT_TOKEN = "42:TEST"
CHAT_ID = 900000001
CALLBACK_MESSAGE_ID = 50


def normalize(text: str | None) -> str:
    """Убирает узкие и неразрывные пробелы, чтобы сравнивать суммы."""
    return (text or "").replace("\u2009", " ").replace("\u00a0", " ")


class FakeSession(BaseSession):
    """Заглушка сессии aiogram: запоминает вызовы вместо HTTP-запросов."""

    def __init__(self) -> None:
        super().__init__()
        self.log: list[dict] = []
        self.callbacks: list[dict] = []
        self._message_id = 100

    async def close(self) -> None:
        return None

    async def stream_content(self, *args, **kwargs):
        yield b""

    def _message(self, method, text=None, markup=None) -> Message:
        return Message(
            message_id=getattr(method, "message_id", None) or self._message_id,
            date=datetime.now(),
            chat=Chat(id=CHAT_ID, type="private"),
            text=text,
            # ReplyKeyboardMarkup в ответ на edit_text Telegram не принимает.
            reply_markup=markup if isinstance(markup, InlineKeyboardMarkup) else None,
        )

    async def make_request(self, bot, method, timeout=None):
        if isinstance(method, SendMessage):
            self._message_id += 1
            self.log.append(
                {"kind": "send", "text": method.text, "markup": method.reply_markup}
            )
            return self._message(method, method.text, method.reply_markup)
        if isinstance(method, EditMessageText):
            self.log.append(
                {"kind": "edit", "text": method.text, "markup": method.reply_markup}
            )
            return self._message(method, method.text, method.reply_markup)
        if isinstance(method, EditMessageReplyMarkup):
            return self._message(method)
        if isinstance(method, AnswerCallbackQuery):
            self.callbacks.append(
                {"text": method.text, "alert": bool(method.show_alert)}
            )
            return True
        if isinstance(method, SetMyCommands):
            return True
        raise AssertionError(f"Неожиданный метод Telegram API: {type(method).__name__}")


class BotHarness:
    """Кормит обновления диспетчеру и отдаёт последний экран бота.

    Диспетчер создаётся один раз на тестовую сессию: aiogram запрещает
    подключать один и тот же Router к разным Dispatcher'ам. Изоляцию между
    тестами даёт уникальный tg_id.
    """

    def __init__(self, dispatcher: Dispatcher, tg_id: int | None = None) -> None:
        self.tg_id = tg_id or CHAT_ID
        self.session = FakeSession()
        self.bot = Bot(token=BOT_TOKEN, session=self.session)
        self.dispatcher = dispatcher
        self.user = User(id=self.tg_id, is_bot=False, first_name="Тест")
        self._update_id = 0

    async def close(self) -> None:
        await self.bot.session.close()

    def _chat(self) -> Chat:
        return Chat(id=self.tg_id, type="private")

    def _next_update_id(self) -> int:
        self._update_id += 1
        return self._update_id

    async def send(self, text: str) -> None:
        update = Update(
            update_id=self._next_update_id(),
            message=Message(
                message_id=self._next_update_id(),
                date=datetime.now(),
                chat=self._chat(),
                from_user=self.user,
                text=text,
            ),
        )
        await self.dispatcher.feed_update(self.bot, update)

    async def press(self, callback_data: str) -> None:
        update = Update(
            update_id=self._next_update_id(),
            callback_query=CallbackQuery(
                id=str(self._update_id),
                from_user=self.user,
                chat_instance="test",
                data=callback_data,
                message=Message(
                    message_id=CALLBACK_MESSAGE_ID,
                    date=datetime.now(),
                    chat=self._chat(),
                    text="экран",
                ),
            ),
        )
        await self.dispatcher.feed_update(self.bot, update)

    @property
    def last(self) -> dict:
        assert self.session.log, "бот ещё ничего не отправил"
        return self.session.log[-1]

    @property
    def text(self) -> str:
        return normalize(self.last["text"])

    @property
    def buttons(self) -> list[str]:
        """callback_data кнопок на последнем inline-экране."""
        markup = self.last["markup"]
        if not isinstance(markup, InlineKeyboardMarkup):
            return []
        return [
            button.callback_data
            for row in markup.inline_keyboard
            for button in row
        ]

    @property
    def reply_keyboard(self) -> list[str]:
        """Тексты кнопок нижней (reply) клавиатуры."""
        markup = self.last["markup"]
        if not isinstance(markup, ReplyKeyboardMarkup):
            return []
        return [button.text for row in markup.keyboard for button in row]

    @property
    def callback(self) -> dict:
        assert self.session.callbacks, "бот ещё не отвечал на callback"
        return self.session.callbacks[-1]
