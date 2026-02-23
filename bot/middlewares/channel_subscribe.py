from __future__ import annotations
from typing import TYPE_CHECKING, Any

from aiogram import BaseMiddleware, Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramNotFound
from aiogram.methods import GetChatMember
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from aiogram.utils.i18n import gettext as _

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from aiogram.types import TelegramObject, User


class ChannelSubscribeMiddleware(BaseMiddleware):
    """The middleware is only guaranteed to work for other users if the bot is an administrator in the chat."""

    def __init__(self, chat_ids: list[int | str] | int | str, channel_url: str) -> None:
        self.chat_ids = chat_ids
        self.channel_url = channel_url
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = getattr(event, "from_user", None)
        if not user:
            return await handler(event, data)

        user_id = user.id
        bot: Bot = data["bot"]

        if await self._is_subscribed(bot=bot, user_id=user_id):
            return await handler(event, data)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=_("subscribe button"), url=self.channel_url)],
            [InlineKeyboardButton(text=_("check subscribe button"), callback_data="check_subscribe")],
        ])

        if isinstance(event, Message):
            await event.answer(_("subscribe first"), reply_markup=keyboard)
        elif isinstance(event, CallbackQuery) and event.message:
            await event.message.answer(_("subscribe first"), reply_markup=keyboard)
            await event.answer()

        return None

    async def _is_subscribed(self, bot: Bot, user_id: int) -> bool:
        if isinstance(self.chat_ids, list):
            for chat_id in self.chat_ids:
                try:
                    member = await bot(GetChatMember(chat_id=chat_id, user_id=user_id))
                except TelegramNotFound:
                    return False

                if member.status in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED, ChatMemberStatus.RESTRICTED}:
                    return False

        elif isinstance(self.chat_ids, str | int):
            try:
                member = await bot(GetChatMember(chat_id=self.chat_ids, user_id=user_id))
            except TelegramNotFound:
                return False

            if member.status in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}:
                return False

        return True
