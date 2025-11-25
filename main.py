import asyncio
import random
import string
from typing import Dict, List, Optional, Set

from aiogram import Bot, Dispatcher, F, types

# --------- ВСТАВЬ СВОЙ ТОКЕН ---------
TOKEN = "YOUR_BOT_TOKEN_HERE"
# -------------------------------------


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


def generate_game_id(length: int = 4) -> str:
    """
    Генерирует короткий код игры, например: A7F9.
    """
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # без похожих символов типа 0/O/1/I
    while True:
        code = "".join(random.choice(alphabet) for _ in range(length))
        if code not in games:
            return code


# ---------- СТРУКТУРА ИГРЫ ----------

class Game:
    def __init__(self, organizer_id: int, names_pretty: List[str]):
        """
        names_pretty — список имён, как прислал организатор (красивый вид).
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
                # дубликаты пропускаем — лучше различать вручную
                continue
            name_index[norm] = pretty
            unique_pretty.append(pretty)

        if len(unique_pretty) < 2:
            raise ValueError("После удаления дубликатов осталось меньше 2 участников.")

        self.names: List[str] = unique_pretty                  # красивый список
        self.name_index: Dict[str, str] = name_index           # norm -> pretty
        self.assignment_by_name: Dict[str, str] = {}           # pretty -> pretty_получатель
        self.user_names: Dict[int, str] = {}                   # user_id -> pretty_name
        self.gift_wishes: Dict[str, str] = {}                  # pretty_name -> пожелание

        # генерируем распределение Санты
        receivers = make_derangement(self.names)
        self.assignment_by_name = {
            giver: receiver for giver, receiver in zip(self.names, receivers)
        }


# ---------- ГЛОБАЛЬНОЕ СОСТОЯНИЕ БОТА ----------

bot = Bot(token=TOKEN)
dp = Dispatcher()

# все активные игры: game_id -> Game
games: Dict[str, Game] = {}

# организатор -> код игры, от которого сейчас ждём список участников
pending_game_codes: Dict[int, str] = {}

# организатор -> код активной игры (после того как список принят)
organizer_games: Dict[int, str] = {}

# пользователь -> код игры, в которой он участвует
user_games: Dict[int, str] = {}

# пользователи, от которых ждём текст пожелания после /wish
waiting_wish_users: Set[int] = set()


# ------------------ ОБРАБОТЧИКИ КОМАНД ------------------


@dp.message(F.text == "/help")
async def cmd_help(message: types.Message):
    text = (
        "🎄 *Тайный Санта — бот*\n\n"  
        "*Для организатора:*\n"  
        "1. Напиши /newgame — я создам *код игры*.\n"  
        "2. В ответ пришли список участников: по одному `Имя Фамилия` в каждой строке.\n"  
        "3. Отправь участникам код игры и ссылку на бота.\n"  
        "4. В любой момент используй /orgmenu, чтобы открыть меню организатора и посмотреть свои игры.\n\n"  
        "*Для участника:*\n"  
        "1. Напиши /start.\n"  
        "2. Введи *код игры* от организатора (например: `A7F9`).\n"  
        "3. Потом введи свои имя и фамилию.\n"  
        "4. Нажми кнопку «🎁 Получить имя».\n"  
        "5. Если хочешь, укажи своё пожелание к подарку через /wish.\n\n"  
        "*Бот:*\n"  
        "- никому не даёт самого себя\n"  
        "- один и тот же человек выдаётся только одному участнику\n"  
        "- ты можешь нажимать кнопку сколько угодно — твой человек не поменяется."
    )
    await message.answer(text, parse_mode="Markdown")


@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! 🎄\n\n"  
        "Если ты *организатор* — напиши \n/newgame и создай список участников.\n"  
        "А затем используй /orgmenu, чтобы смотреть свои игры и пары.\n\n"  
        "Если ты *участник* — отправь мне *код игры*, который тебе дал организатор.\n"  
        "Например: `A7F9`.\n\n"  
        "После того как введёшь своё имя, можешь задать пожелание к подарку через /wish.",
        parse_mode="Markdown",
    )


@dp.message(F.text == "/newgame")
async def cmd_newgame(message: types.Message):
    """
    Создание новой игры. Вызывается организатором.
    После этого бот ждёт список участников в следующем сообщении.
    """
    organizer_id = message.from_user.id

    game_id = generate_game_id()
    pending_game_codes[organizer_id] = game_id

    await message.answer(
        "Окей! 🎄\n"  
        f"Код вашей игры: *{game_id}*.\n\n"  
        "1️⃣ Сначала пришлите список участников *одним сообщением*.\n"  
        "Каждый участник — в отдельной строке, формат: `Имя Фамилия`.\n"  
        "Минимум 2 человека.\n\n"  
        "2️⃣ Потом отправьте участникам *код игры* и ссылку на бота.\n",
        parse_mode="Markdown",
    )


@dp.message(F.text == "/reset")
async def cmd_reset(message: types.Message):
    """
    Полный сброс игры организатора (последней активной).
    """
    organizer_id = message.from_user.id

    if organizer_id not in organizer_games:
        await message.answer("У вас сейчас нет активной игры, сбрасывать нечего 🙂")
        return

    game_id = organizer_games[organizer_id]
    game = games.get(game_id)
    if game:
        # убираем всех участников этой игры
        for uid in list(game.user_names.keys()):
            user_games.pop(uid, None)

    games.pop(game_id, None)
    pending_game_codes.pop(organizer_id, None)
    organizer_games.pop(organizer_id, None)

    await message.answer(
        f"Игра с кодом *{game_id}* полностью сброшена. "  
        "Можно запустить новую через /newgame.",
        parse_mode="Markdown",
    )


@dp.message(F.text == "🎁 Получить имя")
async def handle_get_recipient(message: types.Message):
    """
    Участник просит своего получателя.
    """
    user_id = message.from_user.id

    if user_id not in user_games:
        await message.answer(
            "Сначала присоединись к игре:\n"  
            "1) /start\n"  
            "2) введи код игры от организатора\n"  
            "3) введи свои имя и фамилию 🙂"
        )
        return

    game_id = user_games[user_id]
    game = games.get(game_id)

    if game is None:
        await message.answer(
            "Похоже, игра уже была сброшена организатором 😔\n"  
            "Спросите у него, не создавал ли он новую игру."
        )
        return

    if user_id not in game.user_names:
        await message.answer(
            "Сначала напиши своё *имя и фамилию* как в списках у организатора, чтобы я понял, кто ты 🙂",
            parse_mode="Markdown",
        )
        return

    my_name = game.user_names[user_id]
    recipient = game.assignment_by_name.get(my_name)

    if not recipient:
        await message.answer(
            "Произошла внутренняя ошибка при поиске получателя 😔\n"  
            "Попроси организатора сбросить игру командой /reset и создать её заново."
        )
        return

    wish = game.gift_wishes.get(recipient)
    if wish:
        text = (
            f"Твой человек: **{recipient}** 🎁\n"  
            f"Его/её пожелание к подарку:\n«{wish}»\n\n"  
            "Никому не рассказывай 😉"
        )
    else:
        text = (
            f"Твой человек: **{recipient}** 🎁\n"  
            "Этот участник пока не указал пожелание к подарку.\n\n"  
            "Никому не рассказывай 😉"
        )

    await message.answer(text, parse_mode="Markdown")


# ---------- Пожелания по подарку (участники) ----------


@dp.message(F.text.startswith("/wish"))
async def cmd_wish(message: types.Message):
    """
    Команда /wish — участник задаёт пожелание к своему подарку.

    Варианты:
      - `/wish текст` — пожелание в той же строке
      - `/wish` — бот попросит отправить пожелание следующим сообщением
    """
    user_id = message.from_user.id
    text = (message.text or "").strip()

    if user_id not in user_games:
        await message.answer(
            "Сначала нужно присоединиться к игре:\n"  
            "1) /start\n"  
            "2) ввести код игры\n"  
            "3) ввести своё имя и фамилию 🙂"
        )
        return

    game_id = user_games[user_id]
    game = games.get(game_id)
    if game is None:
        await message.answer(
            "Похоже, игра уже была сброшена организатором 😔\n"  
            "Спросите у организатора, не создал ли он новую игру."
        )
        return

    if user_id not in game.user_names:
        await message.answer(
            "Сначала напиши своё *имя и фамилию*, как в списке у организатора,\n"  
            "а потом уже можно будет указать пожелание через /wish 🙂",
            parse_mode="Markdown",
        )
        return

    pretty_name = game.user_names[user_id]

    parts = text.split(maxsplit=1)
    if len(parts) == 2 and parts[1].strip():
        # вариант `/wish текст`
        wish_text = parts[1].strip()
        game.gift_wishes[pretty_name] = wish_text
        waiting_wish_users.discard(user_id)
        await message.answer(
            f"Пожелание сохранено! 🎁\n"  
            f"{pretty_name}, ты указал(а):\n«{wish_text}»"
        )
        return

    # просто `/wish` — ждём текст следующим сообщением
    waiting_wish_users.add(user_id)
    await message.answer(
        "Отправь одним следующим сообщением своё пожелание к подарку.\n\n"  
        "Например:\n"  
        "«Что-то сладкое и тёплые носки» 🙂"
    )


# ---------- Меню организатора ----------


@dp.message(F.text == "/orgmenu")
async def cmd_orgmenu(message: types.Message):
    """
    Главное меню организатора: список всех его игр.
    """
    organizer_id = message.from_user.id

    # выбираем все игры, где этот пользователь — организатор
    organizer_game_list = [
        (game_id, g) for game_id, g in games.items() if g.organizer_id == organizer_id
    ]

    if not organizer_game_list:
        await message.answer(
            "У вас пока нет ни одной созданной игры (или все были сброшены).\n"  
            "Создайте новую через /newgame."
        )
        return

    # сортируем по коду игры, чтобы порядок был стабильным
    organizer_game_list.sort(key=lambda x: x[0])

    buttons: List[List[types.InlineKeyboardButton]] = []
    for game_id, g in organizer_game_list:
        btn_text = f"Игра {game_id} ({len(g.names)} чел.)"
        buttons.append(
            [
                types.InlineKeyboardButton(
                    text=btn_text,
                    callback_data=f"org_game:{game_id}",
                )
            ]
        )

    kb = types.InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(
        "Выберите игру, которую хотите посмотреть:",
        reply_markup=kb,
    )


@dp.callback_query(F.data == "org_list_games")
async def cb_org_list_games(callback: types.CallbackQuery):
    """
    Возврат к списку игр из меню конкретной игры.
    """
    organizer_id = callback.from_user.id

    organizer_game_list = [
        (game_id, g) for game_id, g in games.items() if g.organizer_id == organizer_id
    ]

    if not organizer_game_list:
        await callback.message.edit_text(
            "У вас пока нет ни одной созданной игры (или все были сброшены).\n"  
            "Создайте новую через /newgame."
        )
        await callback.answer()
        return

    organizer_game_list.sort(key=lambda x: x[0])

    buttons: List[List[types.InlineKeyboardButton]] = []
    for game_id, g in organizer_game_list:
        btn_text = f"Игра {game_id} ({len(g.names)} чел.)"
        buttons.append(
            [
                types.InlineKeyboardButton(
                    text=btn_text,
                    callback_data=f"org_game:{game_id}",
                )
            ]
        )

    kb = types.InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        "Выберите игру, которую хотите посмотреть:",
        reply_markup=kb,
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("org_game:"))
async def cb_org_game(callback: types.CallbackQuery):
    """
    Выбор конкретной игры из списка организатора.
    """
    organizer_id = callback.from_user.id
    data = callback.data or ""
    _, game_id = data.split(":", 1)

    game = games.get(game_id)
    if game is None or game.organizer_id != organizer_id:
        await callback.answer(
            "Игра не найдена или вы не являетесь её организатором.",
            show_alert=True,
        )
        return

    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="👥 Участники и пожелания",
                    callback_data=f"org_members:{game_id}",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="🔐 Кто кому дарит",
                    callback_data=f"org_pairs:{game_id}",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="⬅️ К списку игр",
                    callback_data="org_list_games",
                )
            ],
        ]
    )

    await callback.message.edit_text(
        f"Игра *{game_id}*.\n"  
        f"Участников: {len(game.names)}.\n\n"  
        "Выберите, что показать:",
        reply_markup=kb,
        parse_mode="Markdown",
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("org_members:"))
async def cb_org_members(callback: types.CallbackQuery):
    """
    Показать список участников и их пожеланий для выбранной игры.
    """
    organizer_id = callback.from_user.id
    data = callback.data or ""
    _, game_id = data.split(":", 1)

    game = games.get(game_id)
    if game is None or game.organizer_id != organizer_id:
        await callback.answer(
            "Игра не найдена или вы не являетесь её организатором.",
            show_alert=True,
        )
        return

    lines = ["👥 Список участников и их пожеланий:\n"]
    for i, name in enumerate(game.names, start=1):
        wish = game.gift_wishes.get(name)
        if wish:
            line = f"{i}. {name} — пожелание: {wish}"
        else:
            line = f"{i}. {name} — (пожелание не указано)"
        lines.append(line)

    text = "\n".join(lines)
    await callback.message.answer(text)
    await callback.answer()


@dp.callback_query(F.data.startswith("org_pairs:"))
async def cb_org_pairs(callback: types.CallbackQuery):
    """
    Показать список «кто кому дарит» для выбранной игры.
    """
    organizer_id = callback.from_user.id
    data = callback.data or ""
    _, game_id = data.split(":", 1)

    game = games.get(game_id)
    if game is None or game.organizer_id != organizer_id:
        await callback.answer(
            "Игра не найдена или вы не являетесь её организатором.",
            show_alert=True,
        )
        return

    lines = ["🔐 Распределение подарков (кто кому дарит):\n"]
    for i, giver in enumerate(game.names, start=1):
        receiver = game.assignment_by_name.get(giver, "— неизвестно —")
        lines.append(f"{i}. {giver} → {receiver}")

    text = "\n".join(lines)
    await callback.message.answer(text)
    await callback.answer()


# ------------------ ОБРАБОТЧИК ВСЕГО ОСТАЛЬНОГО ТЕКСТА ------------------


@dp.message()
async def handle_text(message: types.Message):
    """
    Здесь несколько ситуаций:
    1) Пользователь после /wish присылает текст пожелания
    2) Ждём список участников от организатора после /newgame
    3) Пользователь вводит код игры, чтобы присоединиться
    4) Пользователь (уже в игре) вводит своё имя и фамилию
    """
    text = (message.text or "").strip()
    user_id = message.from_user.id

    # --- 1) Пользователь присылает текст пожелания после /wish ---
    if user_id in waiting_wish_users:
        waiting_wish_users.discard(user_id)

        if user_id not in user_games:
            await message.answer(
                "Похоже, ты ещё не присоединился к игре. "  
                "Сначала введи код игры и своё имя 🙂"
            )
            return

        game_id_for_wish = user_games[user_id]
        game_for_wish = games.get(game_id_for_wish)
        if game_for_wish is None:
            await message.answer(
                "Игра была сброшена организатором 😔\n"  
                "Спросите у него новый код игры."
            )
            return

        if user_id not in game_for_wish.user_names:
            await message.answer(
                "Сначала напиши своё имя и фамилию, как в списке у организатора 🙂"
            )
            return

        pretty_name = game_for_wish.user_names[user_id]
        if not text:
            await message.answer("Пожелание пустое, напиши хотя бы пару слов 🙂")
            return

        game_for_wish.gift_wishes[pretty_name] = text
        await message.answer(
            f"Пожелание сохранено! 🎁\n"  
            f"{pretty_name}, ты указал(а):\n«{text}»"
        )
        return

    # Игнорируем неизвестные команды
    if text.startswith("/"):
        await message.answer("Неизвестная команда. Попробуй /help 🙂")
        return

    # --- 2) Организатор присылает список участников ---
    if user_id in pending_game_codes:
        game_id = pending_game_codes[user_id]

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) < 2:
            await message.answer(
                "В списке должно быть минимум *два* участника.\n"  
                "Пришлите, пожалуйста, список ещё раз.",
                parse_mode="Markdown",
            )
            return

        try:
            game = Game(organizer_id=user_id, names_pretty=lines)
        except ValueError as e:
            await message.answer(f"Ошибка в списке участников: {e}")
            return

        games[game_id] = game
        organizer_games[user_id] = game_id
        pending_game_codes.pop(user_id, None)

        await message.answer(
            f"Новая игра создана! 🎄\n"  
            f"Код игры: *{game_id}*\n"  
            f"Участников: *{len(game.names)}*.\n\n"  
            "Теперь отправь участникам:\n"  
            f"— ссылку на бота\n"  
            f"— код игры: `{game_id}`\n\n"  
            "Участники:\n"  
            "1) заходят к боту\n"  
            "2) пишут /start\n"  
            "3) вводят код игры\n"  
            "4) вводят свои имя и фамилию\n"  
            "5) нажимают «🎁 Получить имя»\n"  
            "6) по желанию пишут /wish и указывают пожелание к подарку",
            parse_mode="Markdown",
        )
        return

    # --- 3) Пользователь вводит код игры, чтобы присоединиться ---
    if user_id not in user_games:
        game_id = text.upper()
        game = games.get(game_id)

        if game is None:
            await message.answer(
                "Я не нашёл игру с таким кодом 😔\n"  
                "Проверь, правильно ли ты ввёл код (например: `A7F9`).",
                parse_mode="Markdown",
            )
            return

        user_games[user_id] = game_id
        await message.answer(
            f"Игра с кодом *{game_id}* найдена! 🎄\n"  
            "Теперь напиши свои *имя и фамилию* так, как они есть в списке у организатора.\n",
            parse_mode="Markdown",
        )
        return

    # --- 4) Пользователь уже в игре — вводит своё имя и фамилию ---
    game_id = user_games[user_id]
    game = games.get(game_id)

    if game is None:
        await message.answer(
            "Похоже, игра уже была сброшена организатором 😔\n"  
            "Спросите у него, не создавал ли он новую игру."
        )
        return

    norm = normalize_name(text)
    if norm not in game.name_index:
        await message.answer(
            "Я не нашёл тебя в списке участников 😔\n\n"  
            "Напиши *имя и фамилию* так, как они есть в списке у организатора,\n"  
            "в одну строку.\n\n"  
            "Например:\n"  
            "`Евгения Дмитриева`\n"  
            "`Юлия Павликова`",
            parse_mode="Markdown",
        )
        return

    pretty_name = game.name_index[norm]
    game.user_names[user_id] = pretty_name

    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="🎁 Получить имя")]],
        resize_keyboard=True,
    )

    await message.answer(
        f"Отлично, {pretty_name}! 🎄\n"  
        f"Твоё имя записано.\nТеперь нажми кнопку \n«🎁 Получить имя», чтобы узнать, кому ты даришь подарок.\n\n"  
        f"Если хочешь, можешь указать пожелание к подарку командой /wish.",
        reply_markup=kb,
    )


# ---------------------- ЗАПУСК БОТА ----------------------


async def main():
    await dp.start_polling(bot)


asyncio.run(main())
