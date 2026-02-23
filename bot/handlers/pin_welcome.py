from aiogram import Bot, Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.core.config import settings
from bot.filters.admin import AdminFilter

router = Router(name="pin_welcome")


@router.message(Command(commands="pin_welcome"), AdminFilter())
async def pin_welcome_handler(message: types.Message, bot: Bot) -> None:
    """Send and pin a welcome message with bot link to the channel."""
    text = (
        "🎓 <b>Добро пожаловать в 3D Teacher!</b>\n"
        "\n"
        "Здесь вы найдёте уроки по 3D моделированию и визуализации.\n"
        "\n"
        "Чтобы получить полный доступ к материалам курса "
        "и AI-консультанту, перейдите в наш бот 👇"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Получить доступ к курсам", url="https://t.me/clubteacher_bot?start=channel")],
    ])

    sent = await bot.send_message(
        chat_id=settings.CHANNEL_ID,
        text=text,
        reply_markup=keyboard,
    )

    await bot.pin_chat_message(chat_id=settings.CHANNEL_ID, message_id=sent.message_id)

    await message.answer("✅ Сообщение отправлено и закреплено в канале.")
