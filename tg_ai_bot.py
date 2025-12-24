import asyncio
import logging
import re
import base64
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    BufferedInputFile
)
from aiogram.filters import CommandStart
import aiohttp
import json
import os
from datetime import datetime
from io import BytesIO


# Настройки
TELEGRAM_TOKEN = "7963460845:AAFoa_MPJW_jKVAZ3wTs-wa7wYOqYy6FEIM"
API_URL = "http://api.onlysq.ru/ai/v2"
DB_FILE = "chat_history.json"
MAX_MESSAGE_LENGTH = 4000

# Доступные модели
MODELS = {
    "gemini-3-pro": "🔷 Gemini 3 Pro",
    "gpt-4o": "🟢 GPT-4o",
    "claude-3.5-sonnet": "🟣 Claude 3.5 Sonnet",
    "gpt-4-turbo": "🔵 GPT-4 Turbo",
    "gemini-2-flash": "⚡ Gemini 2 Flash"
}

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()


# === РАБОТА С ФАЙЛАМИ И ИЗОБРАЖЕНИЯМИ ===

async def download_file(bot: Bot, file_id: str) -> bytes:
    """Скачать файл из Telegram"""
    try:
        file = await bot.get_file(file_id)
        file_bytes = await bot.download_file(file.file_path)
        return file_bytes.read()
    except Exception as e:
        logging.error(f"Ошибка скачивания файла: {e}")
        return None


async def read_code_file(file_bytes: bytes, filename: str) -> str:
    """Прочитать содержимое файла кода"""
    try:
        # Пробуем разные кодировки
        encodings = ['utf-8', 'cp1251', 'latin-1']
        
        for encoding in encodings:
            try:
                content = file_bytes.decode(encoding)
                return f"Файл: {filename}\n\n```\n{content}\n```"
            except UnicodeDecodeError:
                continue
        
        return f"❌ Не удалось прочитать файл {filename}"
    except Exception as e:
        logging.error(f"Ошибка чтения файла: {e}")
        return f"❌ Ошибка при чтении файла"


def image_to_base64(image_bytes: bytes) -> str:
    """Конвертировать изображение в base64"""
    return base64.b64encode(image_bytes).decode('utf-8')


# === РАБОТА С JSON БАЗОЙ ===

def load_db():
    """Загрузить JSON базу"""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_db(data):
    """Сохранить в JSON"""
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_user_model(user_id: int) -> str:
    """Получить выбранную модель пользователя"""
    db = load_db()
    user_id_str = str(user_id)
    
    if user_id_str not in db:
        db[user_id_str] = {
            "model": "gemini-3-pro",
            "history": [],
            "web_search": True
        }
        save_db(db)
        return "gemini-3-pro"
    
    if "model" not in db[user_id_str]:
        db[user_id_str]["model"] = "gemini-3-pro"
    
    if "web_search" not in db[user_id_str]:
        db[user_id_str]["web_search"] = True
        save_db(db)
    
    return db[user_id_str]["model"]


def get_web_search_status(user_id: int) -> bool:
    """Получить статус веб-поиска"""
    db = load_db()
    user_id_str = str(user_id)
    
    if user_id_str not in db or "web_search" not in db[user_id_str]:
        return True
    
    return db[user_id_str]["web_search"]


def toggle_web_search(user_id: int) -> bool:
    """Переключить веб-поиск"""
    db = load_db()
    user_id_str = str(user_id)
    
    if user_id_str not in db:
        db[user_id_str] = {
            "model": "gemini-3-pro",
            "history": [],
            "web_search": False
        }
    else:
        current = db[user_id_str].get("web_search", True)
        db[user_id_str]["web_search"] = not current
    
    save_db(db)
    return db[user_id_str]["web_search"]


def set_user_model(user_id: int, model: str):
    """Установить модель для пользователя"""
    db = load_db()
    user_id_str = str(user_id)
    
    if user_id_str not in db:
        db[user_id_str] = {
            "model": model,
            "history": [],
            "web_search": True
        }
    else:
        db[user_id_str]["model"] = model
        # Сохраняем существующие настройки
        if "web_search" not in db[user_id_str]:
            db[user_id_str]["web_search"] = True
    
    save_db(db)


def save_message(user_id: int, role: str, content: str):
    """Сохранить сообщение"""
    db = load_db()
    user_id_str = str(user_id)

    if user_id_str not in db:
        db[user_id_str] = {
            "model": "gemini-3-pro",
            "history": [],
            "web_search": True
        }

    if "history" not in db[user_id_str]:
        db[user_id_str]["history"] = []

    db[user_id_str]["history"].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    })

    save_db(db)


def get_history(user_id: int, limit: int = 20) -> list:
    """Получить историю"""
    db = load_db()
    user_id_str = str(user_id)

    if user_id_str not in db or "history" not in db[user_id_str]:
        return []

    messages = db[user_id_str]["history"][-limit:]
    return [
        {"role": msg["role"], "content": msg["content"]}
        for msg in messages
    ]


def clear_history(user_id: int):
    """Очистить историю"""
    db = load_db()
    user_id_str = str(user_id)

    if user_id_str in db:
        model = db[user_id_str].get("model", "gemini-3-pro")
        web_search = db[user_id_str].get("web_search", True)
        db[user_id_str] = {
            "model": model,
            "history": [],
            "web_search": web_search
        }
        save_db(db)


# === ФОРМАТИРОВАНИЕ КОДА ===

def extract_code_blocks(text: str) -> list:
    """Извлечь блоки кода из текста"""
    # Паттерн для блоков кода с языком: ```язык\nкод\n```
    pattern = r'```(\w+)?\n(.*?)```'
    matches = re.finditer(pattern, text, re.DOTALL)
    
    code_blocks = []
    for match in matches:
        lang = match.group(1) or 'text'
        code = match.group(2).strip()
        code_blocks.append({
            'language': lang,
            'code': code,
            'full_match': match.group(0)
        })
    
    return code_blocks


def format_message_with_code(text: str) -> str:
    """Форматировать сообщение с красивым выделением кода"""
    # Конвертируем markdown форматирование в HTML
    # **жирный** -> <b>жирный</b>
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    # *курсив* -> <i>курсив</i>
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    # `код` -> <code>код</code>
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    
    # Заменяем блоки кода на красиво оформленные
    code_blocks = extract_code_blocks(text)
    
    for block in code_blocks:
        lang = block['language']
        code = block['code']
        
        # Экранируем HTML символы в коде
        code = code.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Создаем красиво оформленный блок
        formatted = f"<b>📝 Код ({lang}):</b>\n<pre>{code}</pre>"
        text = text.replace(block['full_match'], formatted)
    
    return text


# === РАЗБИВКА ДЛИННЫХ СООБЩЕНИЙ ===

def split_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list:
    """Разбить длинное сообщение на части"""
    if len(text) <= max_length:
        return [text]

    parts = []
    while text:
        if len(text) <= max_length:
            parts.append(text)
            break

        split_pos = text.rfind('\n', 0, max_length)
        if split_pos == -1:
            split_pos = text.rfind(' ', 0, max_length)
        if split_pos == -1:
            split_pos = max_length

        parts.append(text[:split_pos])
        text = text[split_pos:].lstrip()

    return parts


async def send_long_message(message: Message, text: str):
    """Отправить длинное сообщение"""
    formatted_text = format_message_with_code(text)
    parts = split_message(formatted_text)

    for i, part in enumerate(parts):
        if i > 0:
            await asyncio.sleep(0.5)
        try:
            await message.answer(part, parse_mode="HTML")
        except Exception:
            # Если HTML не работает, отправляем как есть
            await message.answer(part)


# === КЛАВИАТУРЫ ===

def get_models_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора моделей"""
    buttons = []
    for model_id, model_name in MODELS.items():
        buttons.append([
            InlineKeyboardButton(
                text=model_name,
                callback_data=f"model_{model_id}"
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_code_actions_keyboard(code_index: int) -> InlineKeyboardMarkup:
    """Клавиатура для действий с кодом"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📥 Скачать файл",
            callback_data=f"download_{code_index}"
        )]
    ])


# === РАБОТА С AI ===

async def get_ai_response(
    user_id: int,
    user_message: str,
    image_base64: str = None
) -> str:
    """Получить ответ от AI с историей и опциональным изображением"""
    headers = {
        "Authorization": "Bearer openai"
    }

    model = get_user_model(user_id)
    web_search = get_web_search_status(user_id)
    history = get_history(user_id, limit=20)
    
    # Формируем сообщение с учетом изображения
    if image_base64:
        message_content = [
            {"type": "text", "text": user_message},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64}"
                }
            }
        ]
    else:
        message_content = user_message
    
    history.append({
        "role": "user",
        "content": message_content
    })

    send = {
        "model": model,
        "request": {
            "messages": history
        }
    }
    
    # Добавляем веб-поиск если включен
    if web_search:
        send["tools"] = [{"type": "web_search"}]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                API_URL,
                json=send,
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    ai_reply = data['choices'][0]['message']['content']

                    # Сохраняем текстовую версию для истории
                    user_msg = user_message if not image_base64 else f"{user_message} [изображение]"
                    save_message(user_id, "user", user_msg)
                    save_message(user_id, "assistant", ai_reply)

                    return ai_reply
                else:
                    error_text = await response.text()
                    logging.error(f"API Error: {response.status} - {error_text}")
                    return "❌ Ошибка API"
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        return "❌ Ошибка соединения"


# === КОМАНДЫ БОТА ===

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Команда /start"""
    current_model = get_user_model(message.from_user.id)
    model_name = MODELS.get(current_model, current_model)
    web_status = "🌐 Вкл" if get_web_search_status(message.from_user.id) else "🔌 Выкл"
    
    await message.answer(
        f"🤖 <b>Привет! Я AI-ассистент с памятью.</b>\n\n"
        f"📊 Модель: {model_name}\n"
        f"🌐 Интернет: {web_status}\n\n"
        f"<b>Команды:</b>\n"
        f"🔄 /model - выбрать модель\n"
        f"🌐 /web - переключить интернет\n"
        f"🗑️ /clear - очистить историю\n"
        f"📚 /history - показать историю\n"
        f"❓ /help - помощь\n\n"
        f"<b>Что я умею:</b>\n"
        f"💬 Отвечать на вопросы\n"
        f"🌐 Искать в интернете\n"
        f"📸 Анализировать изображения\n"
        f"📄 Читать файлы кода\n"
        f"💾 Помнить контекст беседы\n\n"
        f"<i>Напиши мне, отправь фото или файл!</i>",
        parse_mode="HTML"
    )


@dp.message(F.text == "/web")
async def cmd_web(message: Message):
    """Команда переключения интернет-поиска"""
    new_status = toggle_web_search(message.from_user.id)
    status_text = "🌐 <b>Включен</b>" if new_status else "🔌 <b>Выключен</b>"
    
    await message.answer(
        f"🌐 <b>Поиск в интернете</b>\n\n"
        f"Статус: {status_text}\n\n"
        f"<i>{'Теперь я могу искать актуальную информацию в интернете!' if new_status else 'Отвечаю только на основе своих знаний.'}</i>",
        parse_mode="HTML"
    )


@dp.message(F.text == "/model")
async def cmd_model(message: Message):
    """Команда выбора модели"""
    current_model = get_user_model(message.from_user.id)
    model_name = MODELS.get(current_model, current_model)
    
    await message.answer(
        f"🎯 <b>Выбор модели</b>\n\n"
        f"Текущая: {model_name}\n\n"
        f"Выбери новую модель:",
        reply_markup=get_models_keyboard(),
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("model_"))
async def process_model_selection(callback: CallbackQuery):
    """Обработка выбора модели"""
    model_id = callback.data.replace("model_", "")
    
    if model_id in MODELS:
        set_user_model(callback.from_user.id, model_id)
        model_name = MODELS[model_id]
        
        await callback.message.edit_text(
            f"✅ <b>Модель изменена!</b>\n\n"
            f"Выбрана: {model_name}",
            parse_mode="HTML"
        )
    
    await callback.answer()


@dp.message(F.text == "/clear")
async def cmd_clear(message: Message):
    """Команда очистки истории"""
    clear_history(message.from_user.id)
    await message.answer("🗑️ <b>История очищена!</b>", parse_mode="HTML")


@dp.message(F.text == "/history")
async def cmd_history(message: Message):
    """Команда показа истории"""
    history = get_history(message.from_user.id, limit=10)

    if not history:
        await message.answer("📭 <b>История пуста</b>", parse_mode="HTML")
        return

    text = "📚 <b>Последние 10 сообщений:</b>\n\n"
    for msg in history:
        role = "👤 Вы" if msg["role"] == "user" else "🤖 AI"
        content = msg["content"][:80] + "..." if len(msg["content"]) > 80 else msg["content"]
        text += f"<b>{role}:</b>\n{content}\n\n"

    await message.answer(text, parse_mode="HTML")


@dp.message(F.text == "/help")
async def cmd_help(message: Message):
    """Команда помощи"""
    web_status = "🌐 Включен" if get_web_search_status(message.from_user.id) else "🔌 Выключен"
    
    await message.answer(
        f"❓ <b>Помощь</b>\n\n"
        f"Я AI-ассистент с памятью и доступом в интернет.\n\n"
        f"<b>Возможности:</b>\n"
        f"• 🌐 Поиск информации в интернете ({web_status})\n"
        f"• 🤖 Несколько AI моделей на выбор\n"
        f"• 💾 Память о предыдущих сообщениях\n"
        f"• 💻 Красивое форматирование кода\n"
        f"• 📥 Скачивание кода в файлы\n"
        f"• 📸 Анализ изображений\n"
        f"• 📄 Чтение файлов кода\n\n"
        f"<b>Команды:</b>\n"
        f"/model - выбрать AI модель\n"
        f"/web - вкл/выкл интернет-поиск\n"
        f"/clear - очистить историю\n"
        f"/history - просмотр истории\n"
        f"/help - эта справка\n\n"
        f"<b>Как использовать:</b>\n"
        f"💬 Текст - просто задай вопрос\n"
        f"📸 Фото - отправь изображение\n"
        f"📄 Файл - прикрепи код (до 20 МБ)\n\n"
        f"<i>Я понимаю контекст и помню разговор!</i>",
        parse_mode="HTML"
    )


# Хранилище кода для скачивания
user_code_storage = {}


@dp.callback_query(F.data.startswith("download_"))
async def process_code_download(callback: CallbackQuery):
    """Обработка скачивания кода"""
    user_id = callback.from_user.id
    
    if user_id not in user_code_storage:
        await callback.answer("❌ Код не найден", show_alert=True)
        return
    
    try:
        code_index = int(callback.data.replace("download_", ""))
        
        if code_index >= len(user_code_storage[user_id]):
            await callback.answer("❌ Код не найден", show_alert=True)
            return
        
        code_data = user_code_storage[user_id][code_index]
        language = code_data['language']
        code = code_data['code']
        
        # Определяем расширение файла
        extensions = {
            'python': 'py',
            'javascript': 'js',
            'java': 'java',
            'cpp': 'cpp',
            'c': 'c',
            'csharp': 'cs',
            'html': 'html',
            'css': 'css',
            'sql': 'sql',
            'bash': 'sh',
            'php': 'php',
            'ruby': 'rb',
            'go': 'go',
            'rust': 'rs',
            'typescript': 'ts'
        }
        
        ext = extensions.get(language.lower(), 'txt')
        filename = f"code_{code_index + 1}.{ext}"
        
        # Создаем файл
        file = BufferedInputFile(
            code.encode('utf-8'),
            filename=filename
        )
        
        await callback.message.answer_document(
            file,
            caption=f"📄 <b>Файл с кодом ({language})</b>",
            parse_mode="HTML"
        )
        
        await callback.answer("✅ Файл отправлен!")
        
    except Exception as e:
        logging.error(f"Ошибка при скачивании кода: {e}")
        await callback.answer("❌ Ошибка при создании файла", show_alert=True)


@dp.message(F.document)
async def handle_document(message: Message):
    """Обработка документов/файлов"""
    document = message.document
    
    # Проверка размера файла (максимум 20 МБ)
    if document.file_size > 20 * 1024 * 1024:
        await message.answer("❌ Файл слишком большой! Максимум 20 МБ.")
        return
    
    thinking_msg = await message.answer(
        "📄 <i>Читаю файл...</i>",
        parse_mode="HTML"
    )
    
    try:
        # Скачиваем файл
        file_bytes = await download_file(bot, document.file_id)
        
        if file_bytes is None:
            await thinking_msg.edit_text("❌ Ошибка при скачивании файла")
            return
        
        # Читаем содержимое файла
        file_content = await read_code_file(file_bytes, document.file_name)
        
        # Формируем запрос
        caption = message.caption if message.caption else "Что находится в этом файле?"
        full_message = f"{caption}\n\n{file_content}"
        
        await thinking_msg.edit_text("💭 <i>Анализирую...</i>", parse_mode="HTML")
        await bot.send_chat_action(message.chat.id, "typing")
        
        # Получаем ответ от AI
        ai_response = await get_ai_response(message.from_user.id, full_message)
        
        await thinking_msg.delete()
        
        # Проверяем наличие кода
        code_blocks = extract_code_blocks(ai_response)
        
        if code_blocks:
            user_code_storage[message.from_user.id] = code_blocks
        
        # Отправляем ответ
        await send_long_message(message, ai_response)
        
        # Если есть код, добавляем кнопки
        if code_blocks:
            for i, block in enumerate(code_blocks):
                await message.answer(
                    f"📥 <b>Код #{i + 1} ({block['language']})</b>\n"
                    f"<i>Нажми кнопку чтобы скачать файл</i>",
                    reply_markup=get_code_actions_keyboard(i),
                    parse_mode="HTML"
                )
    
    except Exception as e:
        logging.error(f"Ошибка обработки документа: {e}")
        await thinking_msg.edit_text("❌ Ошибка при обработке файла")


@dp.message(F.photo)
async def handle_photo(message: Message):
    """Обработка фотографий"""
    thinking_msg = await message.answer(
        "🖼️ <i>Анализирую изображение...</i>",
        parse_mode="HTML"
    )
    
    try:
        # Берем фото наилучшего качества (последнее в массиве)
        photo = message.photo[-1]
        
        # Скачиваем фото
        photo_bytes = await download_file(bot, photo.file_id)
        
        if photo_bytes is None:
            await thinking_msg.edit_text("❌ Ошибка при скачивании изображения")
            return
        
        # Конвертируем в base64
        image_base64 = image_to_base64(photo_bytes)
        
        # Формируем запрос
        caption = message.caption if message.caption else "Что изображено на этой фотографии?"
        
        await thinking_msg.edit_text("💭 <i>Думаю...</i>", parse_mode="HTML")
        await bot.send_chat_action(message.chat.id, "typing")
        
        # Получаем ответ от AI с изображением
        ai_response = await get_ai_response(
            message.from_user.id,
            caption,
            image_base64
        )
        
        await thinking_msg.delete()
        
        # Проверяем наличие кода
        code_blocks = extract_code_blocks(ai_response)
        
        if code_blocks:
            user_code_storage[message.from_user.id] = code_blocks
        
        # Отправляем ответ
        await send_long_message(message, ai_response)
        
        # Если есть код, добавляем кнопки
        if code_blocks:
            for i, block in enumerate(code_blocks):
                await message.answer(
                    f"📥 <b>Код #{i + 1} ({block['language']})</b>\n"
                    f"<i>Нажми кнопку чтобы скачать файл</i>",
                    reply_markup=get_code_actions_keyboard(i),
                    parse_mode="HTML"
                )
    
    except Exception as e:
        logging.error(f"Ошибка обработки фото: {e}")
        await thinking_msg.edit_text("❌ Ошибка при обработке изображения")


@dp.message(F.text)
async def handle_message(message: Message):
    """Обработка текстовых сообщений"""
    if message.text.startswith('/'):
        return

    thinking_msg = await message.answer("💭 <i>Думаю...</i>", parse_mode="HTML")
    await bot.send_chat_action(message.chat.id, "typing")

    ai_response = await get_ai_response(message.from_user.id, message.text)

    await thinking_msg.delete()

    # Проверяем наличие кода
    code_blocks = extract_code_blocks(ai_response)
    
    if code_blocks:
        # Сохраняем код для возможности скачивания
        user_code_storage[message.from_user.id] = code_blocks
    
    # Отправляем сообщение с форматированием
    await send_long_message(message, ai_response)
    
    # Если есть код, добавляем кнопки для скачивания
    if code_blocks:
        for i, block in enumerate(code_blocks):
            await message.answer(
                f"📥 <b>Код #{i + 1} ({block['language']})</b>\n"
                f"<i>Нажми кнопку чтобы скачать файл</i>",
                reply_markup=get_code_actions_keyboard(i),
                parse_mode="HTML"
            )


async def main():
    """Запуск бота"""
    logging.info("🚀 Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
