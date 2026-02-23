from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING, Optional
import re

import google.generativeai as genai
from loguru import logger
from sqlalchemy import text, bindparam
from sentence_transformers import SentenceTransformer

from pgvector.sqlalchemy import Vector
from bot.core.config import settings
# from bot.database.database import course_db_sessionmaker

_embedding_model: Optional[SentenceTransformer] = None
_embedding_init_lock = asyncio.Lock()

async def get_embedding_model() -> SentenceTransformer:
    """Лениво инициализируем и возвращаем глобальную модель эмбеддингов."""
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model

    async with _embedding_init_lock:
        if _embedding_model is not None:
            return _embedding_model

        # Инициализация heavy sync-операции в thread-pool, чтобы не блокировать loop
        def _init():
            return SentenceTransformer('intfloat/multilingual-e5-base', device="cpu")

        _embedding_model = await asyncio.to_thread(_init)
        return _embedding_model

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# Конфигурируем Gemini API
genai.configure(api_key=settings.GEMINI_API_KEY)

# Настройки для векторного поиска
SIMILARITY_THRESHOLD = 0.75  # Порог схожести (косинусное расстояние)
MATCH_COUNT = 10  # Количество фрагментов для контекста


class AIConsultantService:
    """
    Сервис для получения ответов от AI-консультанта на основе
    данных из базы курсов.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.generation_model = genai.GenerativeModel(model_name="models/gemini-pro-latest")
        self.embedding_model = None

        # for m in genai.list_models():
        #     caps = []
        #     if "generateContent" in m.supported_generation_methods:
        #         caps.append("generateContent")
        #     if getattr(m, "input_token_limit", None):
        #         caps.append(f"input_tokens={m.input_token_limit}")
        #     if getattr(m, "output_token_limit", None):
        #         caps.append(f"output_tokens={m.output_token_limit}")
        #     logger.info(f"{m.name} | {', '.join(caps)}")

    async def _get_text_embedding(self, content: str) -> Optional[list[float]]:
        """Получает векторное представление контента с помощью модели SentenceTransformer.

        Args:
            content (str ): Текстовый контент
            model (SentenceTransformer): Предобученная модель для получения эмбеддингов.

        Returns:
            list[float]: Векторное представление контента.
        """
        if not content:
            logger.warning("Пустой контент для получения эмбеддинга.")
            return []
        
        try:
            self.embedding_model = await get_embedding_model()
        except Exception as e:
            logger.error(f"Ошибка инициализации общей модели эмбеддингов: {e}")
            return []

        normalized = self.normalize_for_embedding(content)
        if not normalized:
            logger.warning("Контент после нормализации пустой для получения эмбеддинга.")
            return []
        texts_for_embedding = f"passage: {normalized[:50000]}"
        emb = self.embedding_model.encode(
            texts_for_embedding,
            normalize_embeddings=True,
            convert_to_numpy=True
        )
        content_embedding = emb.astype('float32').tolist()
        return content_embedding

    def normalize_for_embedding(self, s: str) -> str:
        """Убрать ведущие таймкоды, переводы строк и лишние пробелы."""
        if not s:
            return ""
        # убрать ведущие таймкоды вида 00:01.71 :  или 1:02:03,123 - 
        s = re.sub(r'^\s*\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d+)?\s*[:\-]\s*', '', s)
        # заменить переводы строк на пробелы и нормализовать пробелы
        s = s.replace('\n', ' ').replace('\r', ' ')
        s = re.sub(r'\s+', ' ', s).strip()
        return s

    async def _find_relevant_context(self, embedding: list[float]) -> str:
        """
        Ищет наиболее релевантные фрагменты текста в базе данных курсов
        с использованием векторного поиска (косинусное расстояние).
        """
        if not embedding:
            return ""

        # Ищем в уроках (content_embedding — ваш столбец)
        lessons_query = text(
            """
            SELECT id, lesson_name, content_markdown
            FROM lessons
            WHERE 1 - (content_embedding <=> :embedding) > :threshold
            ORDER BY content_embedding <=> :embedding
            LIMIT :limit
            """
        ).bindparams(
            bindparam("embedding", type_=Vector(dim=len(embedding))),
            bindparam("threshold"),
            bindparam("limit"),
        )

        # Ищем в транскрипциях видео (проверьте имя столбца эмбеддинга!)
        fragments_query = text(
            """
            SELECT f.video_id, f.text, f.timestamp
            FROM video_transcript_fragment f
            WHERE 1 - (f.embedding <=> :embedding) > :threshold
            ORDER BY f.embedding <=> :embedding
            LIMIT :limit
            """
        ).bindparams(
            bindparam("embedding", type_=Vector(dim=len(embedding))),
            bindparam("threshold"),
            bindparam("limit"),
        )

        try:
            lessons_result = await self.session.execute(
                lessons_query,
                {"embedding": embedding, "threshold": SIMILARITY_THRESHOLD, "limit": MATCH_COUNT // 2},
            )
            fragments_result = await self.session.execute(
                fragments_query,
                {"embedding": embedding, "threshold": SIMILARITY_THRESHOLD, "limit": MATCH_COUNT // 2},
            )

            lessons = lessons_result.fetchall()
            fragments = fragments_result.fetchall()

            lessons_context = [row[2] for row in lessons]
            lessons_ids = [row[0] for row in lessons]
            fragments_context = [row[1] for row in fragments]
            fragments_video_ids = [row[0] for row in fragments]
            logger.info (f"Found {len(lessons_context)} lesson fragments and {len(fragments_context)} video fragments for context.")
            logger.info (f"Lessons IDs: {lessons_ids}, texts: {lessons_context}")
            logger.info (f"Video IDs: {fragments_video_ids}, texts: {fragments_context}")
            full_context = "\n---\n".join(lessons_context + fragments_context)
            logger.info(f"Found context length: {len(full_context)} chars")
            return full_context
        except Exception as e:
            # pgvector может быть не установлен или настроен неверно
            logger.error(f"Vector search failed: {e}. Is pgvector extension enabled in course_db?")
            return ""

    async def get_answer(self, question: str) -> str:
        """Основной метод: получает вопрос и возвращает сгенерированный ответ."""
        logger.info(f"New question for AI consultant: '{question}'")

        # 1. Получаем эмбеддинг вопроса
        question_embedding = await self._get_text_embedding(question)
        if not question_embedding:
            return "Не удалось обработать ваш вопрос. Попробуйте позже."

        # 2. Находим релевантный контекст в базе
        context = await self._find_relevant_context(question_embedding)
        if not context:
            return "К сожалению, я не нашел информации по вашему вопросу в материалах курса."

        # 3. Формируем промпт и генерируем ответ
        prompt = f"""
            Ты — персонализированный AI-консультант по учебному курсу 3d моделирования, визуализации.
            Твоя задача — отвечать на вопросы пользователя, основываясь ИСКЛЮЧИТЕЛЬНО на предоставленном контексте из материалов курса.
            Не придумывай ничего от себя. Если в контексте нет ответа, сообщи об этом.
            В конце ответа вежливо порекомендуй, какие еще материалы могут быть полезны, упомянув их названия, если они есть в контексте.

            КОНТЕКСТ:
            ---
            {context}
            ---

            ВОПРОС ПОЛЬЗОВАТЕЛЯ:
            {question}

            ТВОЙ ОТВЕТ:
            """

        try:
            response = await self.generation_model.generate_content_async(prompt)
            logger.success("Successfully generated answer from Gemini")
            return response.text
        except Exception as e:
            logger.error(f"Failed to generate content with Gemini: {e}")
            return "Произошла ошибка при генерации ответа. Пожалуйста, попробуйте еще раз."