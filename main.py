import asyncio
import random
from typing import Dict, List, Optional

from aiogram import Bot, Dispatcher, F, types

# ------------------ ВСТАВЬ СВОЙ ТОКЕН ------------------
TOKEN = "YOUR_TOKEN"
# -------------------------------------------------------


# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----------

def normalize_name(s: str) -> str:
    """
    Нормализация имени:
    - обрезаем пробелы
    - приводим к нижнему регистру
    - ё -> е
    - сжимаем несколько пробелов в один
    """
    s = s.strip().lower()
    s = s.replace("ё", "е")
    s = " ".join(s.split())
    return s


def make_derangement(items: List[str]) -> List[str]:
    """
    Делает случайную перестановку без неподвижных точек:
    никто не получает сам себя.
    items: список имён (в фиксированном порядке).
    """
    if len(items) < 2:
        raise ValueError("Нужно минимум 2 участника для Тайного Санты")

    base = items[:]

    while True:
        shuffled = base[:]
        random.shuffle(shuffled)
        if all(a != b for a, b in zip(base, shuffled)):
            return shuffled


# ---------- СТРУКТУРА ИГРЫ ----------

class Game:
    def __init__(self, organizer_id: int, names_pretty: List[str]):
        """
        names_pretty — список имён как прислал организатор (красивый вариант).
        """
        self.organizer_id: int = organizer_id

        # оставляем только уникальные имена по нормализованной форме
        name_index: Dict[str, str] = {}
        unique_pretty: List[str] = []
        for pretty in names_pretty:
            pretty = pretty.strip()
            if not pretty:
                continue
            norm = normalize_name(pretty)
            if norm in name_index:
                # дубликаты тихо пропускаем
                continue
            name_index[norm] = pretty
            unique_pretty.append(pretty)

        if len(unique_pretty) < 2:
            raise ValueError("После удаления дубликатов осталось меньше 2 участников.")

        self.names: List[str] = unique_pretty                  # красивый список
        self.name_index: Dict[str, str] = name_index           # norm -> pretty
        self.assignment_by_name: Dict[str, str] = {}           # pretty_name -> pretty_recipient
        self.user_names: Dict[int, str] = {}                   # user_id -> pretty_name

        # генерируем распределение Санты
        receivers = make_derangement(self.names)
        self.assignment_by_name = {
            giver: receiver for giver, receiver in zip(self.names, receivers)
        }


# ---------- ГЛОБАЛЬНОЕ СОСТОЯНИЕ БОТА ----------

bot = Bot(token=TOKEN)
dp = Dispatcher()

current_game: Optional[Game] = None
pending_list_from: Optional[int] = None  # user_id, от которого ждём список участников


# ------------------ ОБРАБОТЧИКИ КОМАНД ------------------


@dp.message(F.text == "/help")
async def cmd_help(message: types.Message):
    text = (
        "🎄 *Тайный Санта — бот*\n\n"
        "*Для организатора:*\n"
        "1. Напиши /newgame\n"
        "2. В ответ отправь список участников: по одному -Имя Фамилия- в каждой строке.\n"
        "3. Скинь ссылку на бота участникам.\n\n"
        "*Для участника:*\n"
        "1. Напиши /start\n"
        "2. Введи своё имя и фамилию (как в списке у организатора).\n"
        "3. Нажми кнопку «🎁 Получить имя».\n\n"
        "*Бот:*\n"
        "- никому не даёт самого себя\n"
        "- один и тот же человек выдаётся только одному участнику\n"
        "- ты можешь нажимать кнопку несколько раз — твой человек не поменяется(пока идёт текущая сессия)."
    )
    await message.answer(text, parse_mode="Markdown")


@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    global current_game

    if current_game is None:
        await message.answer(
            "Привет! 🎄\n"
            "Пока нет активной игры.\n"
            "Попроси организатора запустить /newgame и задать список участников.\n\n"
            "Подробнее — /help"
        )
        return

    await message.answer(
        "Привет! 🎄\n"
        "Напиши, пожалуйста, *свои имя и фамилию* так, как они есть в списке у организатора. Если ты организатор - нажми /newgame и задай список участников.\n",
        parse_mode="Markdown",
    )


@dp.message(F.text == "/newgame")
async def cmd_newgame(message: types.Message):
    global current_game, pending_list_from

    organizer_id = message.from_user.id
    current_game = None
    pending_list_from = organizer_id

    await message.answer(
        "Окей! 🎄\n"
        "Пришли список участников *одним сообщением*.\n"
        "Каждый участник — в отдельной строке, формат: Имя Фамилия.\n"
        "Минимум 2 человека.\n\n"
        "Пример:\n"
        "`Юлия Павликова`\n"
        "`Евгения Дмитриева`\n",
        parse_mode="Markdown",
    )


@dp.message(F.text == "/reset")
async def cmd_reset(message: types.Message):
    global current_game, pending_list_from

    if current_game is None:
        await message.answer("Сейчас нет активной игры, сбрасывать нечего 🙂")
        return

    if message.from_user.id != current_game.organizer_id:
        await message.answer("Сбросить игру может только организатор, который её создал.")
        return

    current_game = None
    pending_list_from = None
    await message.answer("Игра полностью сброшена. Можно запустить новую через /newgame.")


@dp.message(F.text == "🎁 Получить имя")
async def handle_get_recipient(message: types.Message):
    global current_game

    if current_game is None:
        await message.answer(
            "Пока нет активной игры.\n"
            "Попроси организатора запустить /newgame.\n\n"
            "Подробнее — /help"
        )
        return

    user_id = message.from_user.id

    if user_id not in current_game.user_names:
        await message.answer("Сначала напиши своё *имя и фамилию*, чтобы я понял, кто ты 🙂")
        return

    my_name = current_game.user_names[user_id]
    recipient = current_game.assignment_by_name.get(my_name)

    if not recipient:
        await message.answer(
            "Произошла внутренняя ошибка при поиске получателя 😔\n"
            "Попроси организатора сбросить игру командой /reset и создать её заново."
        )
        return

    await message.answer(
        f"Твой человек: {recipient} 🎁\nНикому не рассказывай 😉",
        parse_mode="Markdown",
    )


# ------------------ ОБРАБОТЧИК ВСЕГО ОСТАЛЬНОГО ТЕКСТА ------------------


@dp.message()
async def handle_text(message: types.Message):
    """
    Здесь две ситуации:
    1) Ждём список участников от организатора после /newgame
    2) Пользователь вводит своё имя и фамилию, чтобы участвовать
    """
    global current_game, pending_list_from

    text = (message.text or "").strip()
    user_id = message.from_user.id

    # Игнорируем чистые команды, которые не поддерживаем
    if text.startswith("/"):
        await message.answer("Неизвестная команда. Попробуй /help 🙂")
        return

    # --- 1) Организатор присылает список участников ---
    if pending_list_from is not None and user_id == pending_list_from and current_game is None:
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        if len(lines) < 2:
            await message.answer(
                "В списке должно быть минимум *два* участника.\n"
                "Пришли, пожалуйста, список ещё раз.",
                parse_mode="Markdown",
            )
            return

        try:
            game = Game(organizer_id=user_id, names_pretty=lines)
        except ValueError as e:
            await message.answer(f"Ошибка в списке участников: {e}")
            return

        current_game = game
        pending_list_from = None

        await message.answer(
            f"Новая игра создана! 🎄\n"
            f"Участников: *{len(current_game.names)}*.\n\n"
            "Теперь скинь участникам ссылку на бота и скажи:\n"
            "— Зайдите к боту\n"
            "— Напишите /start\n"
            "— Введите свои имя и фамилию\n"
            "— Нажмите «🎁 Получить имя»",
            parse_mode="Markdown",
        )
        return

    # --- 2) Пользователь вводит своё имя и фамилию ---
    if current_game is None:
        await message.answer(
            "Пока нет активной игры.\n"
            "Попроси организатора запустить /newgame и задать список участников.\n\n"
            "Подробнее — /help"
        )
        return

    norm = normalize_name(text)
    if norm not in current_game.name_index:
        await message.answer(
            "Я не нашёл тебя в списке участников 😔\n\n"
            "Напиши *имя и фамилию* так, как они есть в списке у организатора,\n"
            "в одну строку.\n\n",
            parse_mode="Markdown",
        )
        return

    pretty_name = current_game.name_index[norm]
    current_game.user_names[user_id] = pretty_name

    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="🎁 Получить имя")]],
        resize_keyboard=True,
    )

    await message.answer(
        f"Отлично, {pretty_name}! 🎄\n"
        f"Твоё имя записано.\nТеперь нажми кнопку «🎁 Получить имя», чтобы узнать, кому ты даришь подарок.",
        reply_markup=kb,
    )


# ---------------------- ЗАПУСК БОТА ----------------------


async def main():
    await dp.start_polling(bot)


asyncio.run(main())