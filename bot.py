from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ChatPermissions
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.bot import DefaultBotProperties
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.methods import BanChatMember
import asyncio
import logging
from telegram.ext import CallbackContext, CallbackQueryHandler
import os

# Конфігурація
API_TOKEN = os.getenv("API_TOKEN")
CHANNEL_ID = -1002485164281  # ID вашого каналу
ADMIN_IDS = [521090103]  # ID адміністраторів
FORBIDDEN_WORDS = {"погано", "заборонено", "спам", "Спам"}

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ініціалізація бота
bot = Bot(token=API_TOKEN, session=AiohttpSession(), default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
router = Router()


# Функція для створення клавіатури
def get_admin_keyboard(username, user_id, message_id, original_text):
    try:
        # Використовуємо InlineKeyboardMarkup з правильним форматом даних
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    #InlineKeyboardButton(text="Дозволити", callback_data=f"allow:{message_id}"),
                    #InlineKeyboardButton(text="Редагувати", callback_data=f"edit:{message_id}:{user_id}"),
                    #InlineKeyboardButton(text="Видалити", callback_data=f"delete:{message_id}"),
                    InlineKeyboardButton(text="Повернути", url=f"https://t.me/{username}?text=Ваше повідомлення містить спам, тому ми його пересилаємо вам назад. Відредагуйте і прокоментуйте повторно. Дякуємо. \n{original_text}"),
                    InlineKeyboardButton(text="Забанити", callback_data=f"ban:{user_id}:{message_id}")
                ]
            ]
        )
        return keyboard
    except Exception as e:
        logger.error(f"Помилка створення клавіатури: {e}")
        return InlineKeyboardMarkup(inline_keyboard=[])

@router.callback_query(lambda c: c.data.startswith("ban:"))
async def handle_ban(callback_query: CallbackQuery):
    try:
        # Отримуємо user_id із callback_data
        user_id = int(callback_query.data.split(":")[1])
        chat_id = int(callback_query.data.split(":")[2])  # ID групи для коментарів, а не каналу

        # Виконуємо бан користувача у чаті коментарів
        #await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
        await bot(BanChatMember(chat_id=chat_id, user_id=user_id))

        # Повідомляємо адміністратора
        await callback_query.message.answer(f"Користувач з ID {user_id} був забанений у коментарях.")

        # Відповідаємо на callback
        await callback_query.answer("Користувача забанено.")
    except TelegramAPIError as e:
        # Логування помилок
        logger.error(f"Помилка бану користувача {user_id}: {e}")
        await callback_query.answer("Сталася помилка під час спроби забанити користувача.")


@router.message(F.content_type == 'text')
async def handle_edited_message(message: Message):
    logger.info("Test")
    if message.text and any(word in message.text.lower() for word in FORBIDDEN_WORDS):
        logger.info("Редаговане повідомлення містить заборонені слова. Надсилання на модерацію...")

        # Відправляємо повідомлення адміністраторам
        for admin_id in ADMIN_IDS:
            try:
                keyboard = get_admin_keyboard('message.text', message.from_user.id, message.message_id)
                await bot.send_message(
                    -1002485164281,
                    f"Редаговане повідомлення від користувача {message.from_user.username}: {message.text}",
                    parse_mode="HTML",
                    reply_markup=keyboard
                )

                # Можна також видалити або заблокувати редагування
                await message.delete()

                logger.info(f"Повідомлення надіслано адміністратору {admin_id}.")
            except Exception as e:
                logger.error(f"Помилка при відправленні повідомлення адміністратору: {e}")


@dp.message(F.chat.type.in_({"group", "supergroup", "channel"}))
async def moderate_comments(message: Message):
    logger.info(f"Отримано повідомлення: {message.text} від {message.from_user.username} {message.from_user.id}")

    # Перевірка на заборонені слова
    if any(word in message.text.lower() for word in FORBIDDEN_WORDS):
        logger.info("Повідомлення містить заборонені слова. Надсилання на модерацію...")

        try:
            await message.delete()
        except Exception as e:
            logger.error(f"Не вдалося видалити повідомлення: {e}")

        # Повідомлення адміністраторам
        for admin_id in ADMIN_IDS:
            try:
                keyboard = get_admin_keyboard(message.from_user.username, message.from_user.id, message.message_id, message.text)
                logger.info(f"Клавіатура створена: {keyboard}")

                await bot.send_message(
                    -1002485164281,
                    f"Користувач <a href='tg://user?id={message.from_user.id}'>@{message.from_user.username or 'анонім'}</a>, \n"
                    
                    f"залишив коментар у каналі <a href='https://t.me/{message.chat.username or 'анонімний канал'}'>{message.chat.title}</a> \n"
                    
                    f"<b>Текст коментаря:</b> «{message.text}»",

                    parse_mode="HTML",
                    reply_markup=keyboard
                )

                try:
                    await bot.send_message(
                        message.from_user.id,
                        "Ваш коментар було надіслано на модерацію. Дякуємо за ваш внесок!",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Не вдалося надіслати повідомлення автору: {e}")

                logger.info(f"Повідомлення надіслано адміністратору {admin_id}.")
            except Exception as e:
                logger.error(f"Помилка під час відправлення повідомлення адміністратору {admin_id}: {e}")


    else:
        logger.info("Повідомлення не містить заборонених слів.")

async def main():
    try:
        logger.info("Бот запускається...")
        dp.include_router(router)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("Бот завершив роботу.")


if __name__ == "__main__":
    asyncio.run(main())
