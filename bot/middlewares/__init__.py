from aiogram import Dispatcher
from aiogram.utils.callback_answer import CallbackAnswerMiddleware

from .auth import AuthMiddleware
from .channel_subscribe import ChannelSubscribeMiddleware
from .database import DatabaseMiddleware
from .i18n import ACLMiddleware
from .logging import LoggingMiddleware
from .throttling import ThrottlingMiddleware
from bot.core.config import settings
from bot.core.loader import i18n as _i18n


def register_middlewares(dp: Dispatcher) -> None:
    dp.message.outer_middleware(ThrottlingMiddleware())

    dp.update.outer_middleware(LoggingMiddleware())

    dp.update.outer_middleware(DatabaseMiddleware())

    if settings.CHANNEL_ID:
        dp.message.middleware(ChannelSubscribeMiddleware(
            chat_ids=settings.CHANNEL_ID,
            channel_url=settings.CHANNEL_URL,
        ))
        dp.callback_query.middleware(ChannelSubscribeMiddleware(
            chat_ids=settings.CHANNEL_ID,
            channel_url=settings.CHANNEL_URL,
        ))

    dp.message.middleware(AuthMiddleware())

    ACLMiddleware(i18n=_i18n).setup(dp)

    dp.callback_query.middleware(CallbackAnswerMiddleware())
