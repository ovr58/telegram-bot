from aiogram import F, Router, types
from aiogram.utils.i18n import gettext as _

from bot.database.database import course_db_sessionmaker
from bot.services.ai_consultant import AIConsultantService

router = Router(name="ai_consultant")


@router.message(F.text & ~F.text.startswith("/"))
async def ai_consultant_handler(message: types.Message) -> None:
    """
    Обрабатывает текстовые сообщения, не являющиеся командами,
    и передает их AI-консультанту.
    """
    # Показываем, что бот "думает"
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    async with course_db_sessionmaker() as session:
        consultant = AIConsultantService(session)
        answer = await consultant.get_answer(message.text)
        await message.answer(answer)
