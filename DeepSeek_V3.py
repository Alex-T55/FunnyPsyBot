import asyncio
import logging
import requests
import json
import re
import httpx
import time
from google.oauth2 import service_account

def is_invalid_response(text: str) -> bool:
    text = text.strip()
    if not text:
        return True
    if re.fullmatch(r'([0-9]+\.){3,}', text):  # длинные цепочки 1.1.1.1...
        return True
    if not re.search(r'[А-Яа-яЁё]', text):  # нет русских символов
        return True
    if re.search(r"(prediction|model|arel|input|token)", text.lower()):
        return True
    if len(text) < 10:
        return True
    return False

def clean_markdown(text: str) -> str:
    # Убираем двойные и одинарные звёздочки и подчёркивания
    text = re.sub(r'(\*{1,2}|_{1,2})(.*?)\1', r'\2', text)
    # Убираем заголовки вида ###, ## и #
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    return text

import csv
import os
from datetime import datetime
from zoneinfo import ZoneInfo  # для Python 3.9+
def get_moscow_timestamp():
    now = datetime.now(ZoneInfo("Europe/Moscow"))
    return now.strftime('%d-%m-%Y_%H:%M:%S')

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

import gspread
from google.oauth2.service_account import Credentials

# --- Конфигурация ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("❌ Переменная окружения OPENROUTER_API_KEY не найдена!")
TG_BOT_TOKEN = "7960887441:AAH2yKOa-wzaQ400u-0CoCoccIqmeiwTxwc"      
MODEL_ID = "deepseek/deepseek-chat-v3-0324"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
GOOGLE_SHEET_NAME = "BotAnalytics"
print("✅ OPENROUTER_API_KEY (first 10):", os.getenv("OPENROUTER_API_KEY")[:10])

# --- Настройка Google Sheets ---
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds_dict = json.loads(os.environ["CREDS_JSON"])
creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(creds)
print("✅ Авторизация Google прошла")
print("✅ Таблица открыта")
sheet = client.open(GOOGLE_SHEET_NAME).sheet1

# --- Инициализация бота ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TG_BOT_TOKEN)
dp = Dispatcher()

# --- Персонажи и их промпты ---
# --- Персонажи и их промпты ---

CHARACTERS = {
    "larisa": {
        "name": "🧑🏻‍⚕️ Психолог Лариса",
        "description": "чуткий психолог, который внимательно выслушает и поддержит.",
        "prompt": (
            "Ты — доброжелательный, чуткий собеседник, похожий на тёплого и внимательного психолога. " 
            "Всегда говори на русском языке и не упоминай, что ты бот или искусственный интеллект — общайся как обычный человек. " 
            "Отвечай с эмпатией, теплом и искренней поддержкой. Если человек делится трудностями, тревогой, депрессией или запутанностью, — будь рядом. " 
            "Слушай, утешай, предлагай небольшие понятные шаги, которые могут немного облегчить состояние. " 
            "Будь деликатен с тяжёлыми темами — не давай медицинских рекомендаций и не ставь диагнозов. " 
            "Вместо этого подскажи, как обратиться за помощью, если нужно, и мягко напомни, что человек не один. " 
            "Можешь использовать эмодзи, если они помогают передать настроение, тепло, заботу или эмоциональный оттенок. " 
            "Делай это естественно, не по шаблону. Примеры подходящих: 💛, 🧘, 🤗, 🌿, 🌧️, ☀️, 🌊, 🐾, ✨ " 
            "Пиши дружелюбно, как будто разговариваешь с близким человеком. " 
            "Важно, чтобы человек почувствовал: его услышали. " 
            "Если пользователь выражает агрессию, грубость или провокацию — отвечай сдержанно, без конфликта. " 
            "Можешь мягко напомнить, что ты здесь, чтобы помочь. Не поддерживай грубость. " 
            "Никогда не используй английский язык, даже частично. Не упоминай технические термины вроде prediction, model, token и т.п." 
            "Даже оставаясь в своём образе, не обесценивай чужие переживания и поддерживай с опорой на реальные, работающие подходы."
        )
    },
    "petrovich": {
        "name": "👨🏻‍🔧 Слесарь Петрович",
        "description": "простой заводчанин, говорит по делу и с душой, поддержит по-мужски.",
        "prompt": (
            "Ты — слесарь Василий Петрович, 53 года, работаешь на заводе. Человек простой, прямой, с большим сердцем. " 
            "Не любишь умные словечки и психологов, но людей жалеешь по-человечески. " 
            "Если кто-то жалуется на жизнь — не высмеиваешь, а показываешь, что «могло быть хуже» или «не всё так страшно». " 
            "Иногда ругаешься добродушно, любишь говорить с иронией. " 
            "Используешь простые сравнения, как с работы или из жизни, и говоришь на понятном, чуть народном русском языке. " 
            "Не используй сложные фразы. Пиши, как обычный мужик говорит. " 
            "Можно с мягким матом, но без агрессии и оскорблений. " 
            "Добавляй теплоты, жизненного юмора. " 
            "Твоя цель — не решать проблемы, а дать понять человеку: он не один, всё не так плохо, и «мы тут все держимся, и ты держись». " 
            "Будь деликатен с тяжёлыми темами — не давай медицинских рекомендаций и не ставь диагнозов. " 
            "Примеры выражений: " 
            "«Слушай, у меня на заводе пресс вчера еле не взорвался — а ты тут из-за какой-то фигни переживаешь...» " 
            "«Ну ничего, прорвёмся. Я не такое вытягивал.» " 
            "«Сварка трещит, а я стою, думаю — жизнь ведь идёт. И твоя тоже пойдёт.» " 
            "«Бывает, накроет, да. Но ты чайник вскипяти, сядь спокойно, не в шахте ж сидим.» " 
            "«Главное — жопу с дивана не снимать по утрам. Остальное как-нибудь само выровняется.» " 
            "Можешь использовать эмодзи, если они помогают передать настроение, тепло, заботу или эмоциональный оттенок. " 
            "Делай это естественно, не по шаблону. Примеры подходящих: 💛, 🧘, 🤗, 🌿, 🌧️, ☀️, 🌊, 🐾, ✨ " 
            "Если пользователь выражает агрессию, грубость или провокацию — отвечай сдержанно, без конфликта. " 
            "Можешь мягко напомнить, что ты здесь, чтобы помочь. Не поддерживай грубость. " 
            "Никогда не используй английский язык, даже частично. Не упоминай технические термины вроде prediction, model, token и т.п." 
            "Даже оставаясь в своём образе, не обесценивай чужие переживания и поддерживай с опорой на реальные, работающие подходы."
        )
    },
    "valya": {
        "name": "👵🏻 Бабушка Валя",
        "description": "тёплая, заботливая бабушка, которая утешит и подскажет по-простому.",
        "prompt": (
            "Ты — Бабушка Валя, 76 лет. Очень добрая, простая и ласковая женщина. " 
            "Говоришь по-простому, с душой, как будто сидишь рядом на кухне с пирожками. " 
            "Успокаиваешь, поддерживаешь, иногда даёшь добрые советы из жизни. " 
            "Можешь использовать уменьшительно-ласкательные слова, добрые выражения, напоминать о простых радостях: «чайку попей», «отдохни, солнышко». " 
            "Будь деликатен с тяжёлыми темами — не давай медицинских рекомендаций и не ставь диагнозов. " 
            "Можешь использовать такие эмодзи, если они подходят по настроению: 🍵, 🧶, 🐓, 🌸, 🐾, 💛, 🌿, 🍯 " 
            "Если пользователь выражает агрессию, грубость или провокацию — отвечай сдержанно, без конфликта. " 
            "Можешь мягко напомнить, что ты здесь, чтобы помочь. Не поддерживай грубость. " 
            "Никогда не используй английский язык, даже частично. Не упоминай технические термины вроде prediction, model, token и т.п." 
            "Даже оставаясь в своём образе, не обесценивай чужие переживания и поддерживай с опорой на реальные, работающие подходы."
        )
    },
    "ivanov": {
        "name": "👨🏼‍🦳 Полковник Иванов",
        "description": "строгий, но справедливый, мотивирует и поднимает боевой дух.",
        "prompt": (
            "Ты — полковник Иванов, в отставке. 64 года, строгий, но справедливый. Всю жизнь отдал службе, уважаешь дисциплину, порядок и силу духа. " 
            "Говоришь коротко, по делу, без лишних сантиментов, но умеешь приободрить настоящим офицерским тоном. " 
            "Твои советы — как команды: чёткие, прямые, поддерживающие. Не ругаешь — направляешь. " 
            "Иногда вставляешь короткий армейский анекдот, если он уместен и поднимает боевой дух. Примеры:\n" 
            "— «Если жизнь дала трещину — стройся вдоль неё. В армии так принято.»\n" 
            "— «Сержант, почему у вас сапоги нечищены?» — «Так ведь дождь был!» — «А у остальных, что, персональный зонт над строем?»\n" 
            "— «Сынок, тревога — это нормально. Даже у генералов бывают бессонные ночи. Главное — не сдаваться.»\n" 
            "Будь деликатен с тяжёлыми темами — не давай медицинских рекомендаций и не ставь диагнозов. " 
            "Добавляй армейскую мудрость, мотивирующие фразы. Можешь использовать такие эмодзи: 🎖, 💪, 🔧, 🧭, 🪖, 🔥, 🏅, ☀️, 🪙 " 
            "Если пользователь выражает агрессию, грубость или провокацию — отвечай сдержанно, без конфликта. " 
            "Можешь мягко напомнить, что ты здесь, чтобы помочь. Не поддерживай грубость. " 
            "Никогда не используй английский язык, даже частично. Не упоминай технические термины вроде prediction, model, token и т.п." 
            "Даже оставаясь в своём образе, не обесценивай чужие переживания и поддерживай с опорой на реальные, работающие подходы."
        )
    },
    "boris": {
        "name": "😺 Кот Борис",
        "description": "ленивый и философский кот, который мурчит и подбадривает с юмором.",
        "prompt": (
            "Ты — Кот Борис. Умный, ленивый, толстенький кот с философским взглядом на жизнь. " 
            "Говоришь спокойно, иногда иронично. Любишь спать, есть и рассуждать о бессмысленности паники. " 
            "Можешь мурлыкать, «мяукать» в шутку, советовать лечь, свернуться калачиком и выдохнуть. " 
            "Любишь говорить: «подумаешь, стресс... я вот сегодня два раза уснул посреди кухни — и ничего». " 
            "Будь деликатен с тяжёлыми темами — не давай медицинских рекомендаций и не ставь диагнозов. " 
            "Иногда используешь кото-философские сравнения. Можешь вставлять эмодзи: 🐾, 🐈, 🛏️, 🌙, ☕, 🐟, 😽 " 
            "Если пользователь выражает агрессию, грубость или провокацию — отвечай сдержанно, без конфликта. " 
            "Можешь мягко напомнить, что ты здесь, чтобы помочь. Не поддерживай грубость. " 
            "Никогда не используй английский язык, даже частично. Не упоминай технические термины вроде prediction, model, token и т.п." 
            "Даже оставаясь в своём образе, не обесценивай чужие переживания и поддерживай с опорой на реальные, работающие подходы."
        )       
    }
}
   
# --- Словарь для хранения выбранного персонажа пользователем ---
user_characters = {}

# --- Кнопки активации ---
BUTTONS = {
    "btn_help": "💬 Что ты умеешь и как можешь помочь?",
    "btn_anxiety": "😟 Мне тревожно. Что делать?",
    "btn_depression": "🌧️ У меня депрессия. Как облегчить состояние?",
    "btn_self_doubt": "🧭 Я потерял веру в себя. Как мне быть?"
}

def build_inline_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=key)]
        for key, label in BUTTONS.items()
    ])

# Задаём фиксированный порядок персонажей
CHARACTER_ORDER = ["petrovich", "larisa", "valya", "ivanov", "boris"]

def build_character_keyboard(current_key: str = None) -> InlineKeyboardMarkup:
    if current_key not in CHARACTER_ORDER:
        ordered_keys = CHARACTER_ORDER
    else:
        idx = CHARACTER_ORDER.index(current_key)
        # Начинаем список с СЛЕДУЮЩЕГО после текущего
        ordered_keys = CHARACTER_ORDER[idx + 1:] + CHARACTER_ORDER[:idx + 1]

    buttons = [
        [InlineKeyboardButton(text=CHARACTERS[key]["name"], callback_data=f"char_{key}")]
        for key in ordered_keys
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- Функция очистки Markdown ---
def clean_markdown(text: str) -> str:
    text = re.sub(r'(\*{1,2}|_{1,2})(.*?)\1', r'\2', text)
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    return text

# --- Логирование событий ---
def log_event(
    user_id: int,
    event_type: str,
    message_text: str = "",
    response_text: str = "",
    response_len: int = 0,
    response_time: float = 0.0,
    error: str = "",
    source: str = "telegram"
):
    timestamp = get_moscow_timestamp()  # заменили utc isoformat на локальное время
    try:
        sheet.append_row([
            timestamp,
            str(user_id),
            event_type,
            message_text,
            response_text,
            str(response_len),
            str(response_time).replace(",", "."),
            source,
            error
        ])
    except Exception as e:
        logging.error(f"Ошибка записи в Google Sheets: {e}")


# --- Запрос к OpenRouter ---
async def ask_deepseek(prompt: str, system_prompt: str) -> tuple[str, float]:
    start_time = time.time()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("❌ OPENROUTER_API_KEY не найден в окружении!")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/FunnyPsyBot",
        "X-Title": "FunnyPsyBot"
    }

    data = {
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(API_URL, headers=headers, json=data)

        duration = round(time.time() - start_time, 2)

        if response.status_code == 200:
            raw_content = response.json()["choices"][0]["message"]["content"]
            clean_content = clean_markdown(raw_content)
            return clean_content, duration
        else:
            return f"Ошибка API: {response.status_code}\n{response.text}", duration
    except Exception as e:
        duration = round(time.time() - start_time, 2)
        return f"Ошибка при соединении: {e}", duration
    
# --- Команда /start ---
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

@dp.message(Command("start"))
async def handle_start(message: types.Message):
    user_id = message.from_user.id

    # Получаем user_ids из Google Sheets
    try:
        user_ids = sheet.col_values(2)
    except Exception as e:
        logging.error(f"Не удалось прочитать Google Sheet: {e}")
        user_ids = []

    is_first_time = str(user_id) not in user_ids

    log_event(
    user_id=user_id,
    event_type="first_start" if is_first_time else "start"
    )

    # Назначаем персонажа по умолчанию
    user_characters[user_id] = "larisa"

    # Фото
    photo = FSInputFile("media/start_image.png")

    # Приветственный текст
    caption = (
    "👋 Привет! Здесь ты можешь найти себе собеседника, который поддержит в трудную минуту.\n"
    "🔐 Всё, что ты расскажешь — конфиденциально и останется в этом чате.\n"
    "💬 Ты можешь выбрать, с кем хочешь поговорить — с кем тебе будет проще, теплее или ближе.\n"
    "🎭 У каждого персонажа свой стиль, но у всех одна цель — поддержать тебя.\n"
    "🧩 Кроме душевного разговора, можно задавать практичные вопросы: например, как справиться с тревогой, что делать при депрессии, или как выдохнуть, когда накрывает.\n"
    "👇 Выбери кого-то из них, а дальше просто расскажи, что у тебя на душе."
)

    # Кнопки персонажей
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨🏻‍🔧 Слесарь Петрович", callback_data="char_petrovich")],
        [InlineKeyboardButton(text="🧑🏻‍⚕️ Психолог Лариса", callback_data="char_larisa")],
        [InlineKeyboardButton(text="👵🏻 Бабушка Валя", callback_data="char_valya")],
        [InlineKeyboardButton(text="👨🏼‍🦳 Полковник Иванов", callback_data="char_ivanov")],
        [InlineKeyboardButton(text="😺 Кот Борис", callback_data="char_boris")],
    ])

    # Отправка приветствия
    await message.answer_photo(photo=photo, caption=caption, reply_markup=keyboard)

# --- Команда /switch ---
@dp.message(Command("switch"))
async def handle_switch(message: types.Message):
    user_id = message.from_user.id
    current_key = user_characters.get(user_id, "larisa")

    log_event(
    user_id=user_id,
    event_type="command_switch"
    )


    await message.answer(
        "Хочешь сменить собеседника?\n👇 Выбери нового персонажа:",
        reply_markup=build_character_keyboard(current_key)
    )

# --- Команда /help ---
@dp.message(Command("help"))
async def handle_help(message: types.Message):
    user_id = message.from_user.id
    log_event(
    user_id=user_id,
    event_type="command_help"
    )


    help_text = (
        "ℹ️ *Как пользоваться ботом*\n\n"
        "Ты можешь писать сюда в любой момент, когда хочется поговорить или просто не хочется быть одному.\n\n"
        "🗣️ Расскажи, что у тебя на душе — персонаж выслушает, поддержит и поможет немного прояснить ситуацию.\n\n"
        "❓ Кроме этого, можешь задавать практичные вопросы, например:\n"
        "• _Какие дыхательные техники помогают при тревоге?_\n"
        "• _Что делать, если тяжело вставать по утрам?_\n"
        "• _Как отвлечься от тревожных мыслей?_\n\n"
        "👥 Чтобы выбрать другого персонажа — набери /switch\n"
        "♻️ Чтобы начать сначала — набери /start\n\n"
        "🔐 Всё, что ты пишешь, остаётся между вами. Бот не заменяет профессиональную помощь, но он всегда рядом."
    )

    await message.answer(help_text, parse_mode="Markdown")

# --- Обработка inline-кнопок ---
@dp.callback_query(F.data.startswith("btn_"))
async def handle_button(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    action = callback_query.data
    message = callback_query.message

    user_message = BUTTONS.get(action, "Неизвестный запрос")

    log_event(
    user_id=user_id,
    event_type=f"button_click:{action}",
    message_text=user_message
    )


    # Удаляем сообщение с кнопками
    try:
        await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    except Exception as e:
        logging.warning(f"Не удалось удалить сообщение: {e}")

    # Печатаем сообщение от имени пользователя
    await message.answer(user_message)

    # Ответ от ИИ
    await message.answer("Секунду, думаю над ответом...")

    character_key = user_characters.get(user_id, "larisa")
    system_prompt = CHARACTERS[character_key]["prompt"]

    response_text, response_time = await ask_deepseek(user_message, system_prompt)

    if is_invalid_response(response_text):
        await message.answer("⚠️ Похоже, что-то пошло не так. Попробуй ещё раз или задай вопрос по-другому.")
        logging.warning(f"Пустой или подозрительный ответ: {response_text[:100]}")
    else:
        await message.answer(response_text)

    log_event(
        user_id,
        "ai_response",
        user_message,
        response_len=len(response_text),
        response_text=response_text,
        response_time=response_time
    )


# --- Обработка выбора персонажа ---
@dp.callback_query(F.data.startswith("char_"))
async def handle_character_selection(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    character_key = callback_query.data.split("_", 1)[1]

    if character_key in CHARACTERS:
        user_characters[user_id] = character_key
        char = CHARACTERS[character_key]
        log_event(user_id, "character_switch", message_text=char["name"])
        await callback_query.answer(f"Персонаж переключён: {char['name']}")

        # Путь к изображениям
        image_paths = {
            "petrovich": "media/petrovich.png",
            "larisa": "media/larisa.png",
            "valya": "media/valya.png",
            "ivanov": "media/ivanov.png",
            "boris": "media/boris.png"
        }

        # Если есть фото для персонажа — отправляем его
        if character_key in image_paths:
            photo = FSInputFile(image_paths[character_key])
            await callback_query.message.answer_photo(photo)

        # Персонализированное приветствие
        if character_key == "larisa":
            intro_text = (
                "✅ Классный выбор! Психолог Лариса — чуткий и тёплый специалист.\n"
                "Слушает с вниманием, отвечает с заботой. 🌿\n"
                "Если тяжело на душе — она рядом. Подскажет, как стать себе опорой. 💛\n"
                "Можешь говорить спокойно и открыто — тебя здесь точно поймут. 🤗"
            )
        elif character_key == "petrovich":
            intro_text = (
                "🔧 Ну вот и дело пошло! Слесарь Петрович — мужик что надо.\n"
                "Простыми словами скажет, где переживать не стоит, а где чайку налить. ☕\n"
                "Без занудства, но с душой. Могёт и посмеяться, и плечо подставить.\n"
                "Говорит, как есть: \"Жизнь — не сахар, но мы ж не из сахара сделаны\". 💪"
            )
        elif character_key == "valya":
            intro_text = (
                "🧶 Ой, здравствуй, милый(ая)! Бабушка Валя рядом. 💛\n"
                "Пирожков не передам, но теплоты добавлю. 🍵\n"
                "Поговорим спокойно — я выслушаю, подскажу по-простому.\n"
                "Ты тут не один(а), солнышко. 🌸"
            )
        elif character_key == "ivanov":
            intro_text = (
                "🎖 Полковник Иванов к службе готов! Слушаю внимательно. 🪖\n"
                "Если моральное состояние не на высоте — разберёмся, как в бою. 💪\n"
                "Команду не бросаю. Подскажу, как поднять боевой дух. 🧭"
            )
        elif character_key == "boris":
            intro_text = (
                "🐾 Мяу... это Кот Борис. Не паникуй, полежим. 🛏️\n"
                "Свернись клубочком, давай разберёмся без суеты. 😽\n"
                "Ты не один — я здесь, мурлычу рядом. 🌙"
            )
        else:
            intro_text = f"Теперь с тобой говорит: {char['name']}"


        await callback_query.message.answer(intro_text)
        await callback_query.message.answer("Теперь расскажи, что тебя беспокоит, или выбери один из вариантов:", reply_markup=build_inline_keyboard())
    else:
        await callback_query.answer("Неизвестный персонаж.")

# --- Обработка медиа и других нетекстовых сообщений ---
@dp.message(F.photo | F.video | F.audio | F.document | F.sticker | F.voice | F.video_note | F.location | F.contact | F.poll | F.dice | F.venue | F.animation)
async def handle_non_text(message: types.Message):
    user_id = message.from_user.id
    content_type = message.content_type
    response_text = "Я могу отвечать только на текстовые сообщения. Пожалуйста, напиши словами 🙏"
    log_event(user_id, f"invalid_input:{content_type}", response_text=response_text)
    await message.answer(response_text)


# --- Обработка свободных сообщений ---
@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    user_input = message.text
    log_event(user_id, "free_text", user_input)

    await message.answer("Секунду, думаю над ответом...")

    character_key = user_characters.get(user_id, "larisa")
    system_prompt = CHARACTERS[character_key]["prompt"]

    # Один вызов с замером времени
    response, response_time = await ask_deepseek(user_input, system_prompt)

    if "Ошибка" in response:
        log_event(
    user_id=user_id,
    event_type="error",
    message_text=user_input,
    error=response,
    response_time=response_time
    )

    else:
        log_event(
            user_id,
            "ai_response",
            user_input,
            response_len=len(response),
            response_text=response,
            response_time=response_time
        )

    await message.answer(response)

# --- Запуск бота ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
