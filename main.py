import asyncio
import random
from typing import Dict, List, Set, Optional

import json
import os

from aiogram import Bot, Dispatcher, F, types

# --------- ВСТАВЬ СВОЙ ТОКЕН ---------
TOKEN = "8419911595:AAGEXB-tdEsvll2iYqc-sWT-ujKFfFn3-sk"
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


def parse_participant_line(line: str) -> (str, Optional[str]):
    """
    Разбирает строку вида:
      - 'Иван Иванов'
      - 'Иван Иванов @druidblack'

    Возвращает (display_name, handle_без_@ или None)
    """
    line = line.strip()
    if not line:
        return "", None

    parts = line.split()
    handle = None

    if parts[-1].startswith("@") and len(parts[-1]) > 1:
        handle = parts[-1][1:]  # без @
        parts = parts[:-1]

    display_name = " ".join(parts).strip()
    return display_name, handle


def make_gift_keyboard() -> types.ReplyKeyboardMarkup:
    """Клавиатура с кнопками '🎁 Получить имя' и '📝 Пожелание к подарку' в одном ряду."""
    return types.ReplyKeyboardMarkup(
        keyboard=[[
            types.KeyboardButton(text="🎁 Получить имя"),
            types.KeyboardButton(text="📝 Пожелание к подарку"),
        ]],
        resize_keyboard=True,
    )


# ---------- СТРУКТУРА ИГРЫ ----------

class Game:
    def __init__(self, organizer_id: int, rows: List[str]):
        """
        rows — список строк от организатора, каждая строка:
        'Имя Фамилия' или 'Имя Фамилия @username'.
        """
        self.organizer_id: int = organizer_id

        # norm -> pretty
        name_index: Dict[str, str] = {}
        unique_pretty: List[str] = []

        # username (без @, lower) -> pretty
        self.handle_to_name: Dict[str, str] = {}

        for row in rows:
            row = row.strip()
            if not row:
                continue
            pretty, handle = parse_participant_line(row)
            if not pretty:
                continue

            norm = normalize_name(pretty)
            if norm in name_index:
                # дубликаты по имени игнорируем
                continue

            name_index[norm] = pretty
            unique_pretty.append(pretty)

            if handle:
                h = handle.strip().lstrip("@").lower()
                if h:
                    self.handle_to_name[h] = pretty

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

    def to_dict(self) -> dict:
        return {
            "organizer_id": self.organizer_id,
            "names": self.names,
            "name_index": self.name_index,
            "assignment_by_name": self.assignment_by_name,
            "user_names": {str(uid): name for uid, name in self.user_names.items()},
            "gift_wishes": self.gift_wishes,
            "handle_to_name": self.handle_to_name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Game":
        obj = object.__new__(cls)
        obj.organizer_id = int(data["organizer_id"])
        obj.names = list(data.get("names", []))
        obj.name_index = dict(data.get("name_index", {}))
        obj.assignment_by_name = dict(data.get("assignment_by_name", {}))
        obj.user_names = {int(uid): name for uid, name in data.get("user_names", {}).items()}
        obj.gift_wishes = dict(data.get("gift_wishes", {}))
        obj.handle_to_name = dict(data.get("handle_to_name", {}))
        return obj


# ---------- ГЛОБАЛЬНОЕ СОСТОЯНИЕ БОТА ----------

bot = Bot(token=TOKEN)
dp = Dispatcher()

# все активные игры: game_id -> Game
games: Dict[str, Game] = {}

# организатор -> код игры, от которого сейчас ждём список участников (после /newgame)
pending_game_codes: Dict[int, str] = {}

# организатор -> "последняя активная" игра (для /reset, /addplayer, /delplayer)
organizer_games: Dict[int, str] = {}

# пользователь -> КОД ТЕКУЩЕЙ игры (в которой он сейчас "находится" в боте)
user_games: Dict[int, str] = {}

# пользователи, от которых мы ждём текст пожелания после /wish или кнопки
waiting_wish_users: Set[int] = set()

STATE_FILE = "secret_santa_state.json"


# ---------- СЕРИАЛИЗАЦИЯ СОСТОЯНИЯ ----------

def save_state() -> None:
    data = {
        "games": {gid: game.to_dict() for gid, game in games.items()},
        "user_games": {str(uid): gid for uid, gid in user_games.items()},
        "organizer_games": {str(uid): gid for uid, gid in organizer_games.items()},
    }
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка при сохранении состояния: {e}")


def load_state() -> None:
    if not os.path.exists(STATE_FILE):
        return
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Ошибка при загрузке состояния: {e}")
        return

    games.clear()
    for gid, gdata in data.get("games", {}).items():
        try:
            games[gid] = Game.from_dict(gdata)
        except Exception as e:
            print(f"Не удалось восстановить игру {gid}: {e}")

    user_games.clear()
    for uid_str, gid in data.get("user_games", {}).items():
        try:
            user_games[int(uid_str)] = gid
        except Exception:
            pass

    organizer_games.clear()
    for uid_str, gid in data.get("organizer_games", {}).items():
        try:
            organizer_games[int(uid_str)] = gid
        except Exception:
            pass


load_state()


# ---------- УВЕДОМЛЕНИЕ ДАРИТЕЛЕЙ О ПОЖЕЛАНИИ ----------

async def notify_givers_about_wish(
    game_id: str,
    game: Game,
    wisher_name: str,
    wish_text: str,
    is_update: bool,
) -> None:
    """
    Находит всех дарителей, которые дарят wisher_name, и отправляет им уведомление.
    """
    action = "обновил(а) своё пожелание" if is_update else "указал(а) своё пожелание"

    # кто дарит этому человеку?
    givers = [giver for giver, receiver in game.assignment_by_name.items() if receiver == wisher_name]
    if not givers:
        return

    for giver_name in givers:
        # ищем Telegram-пользователя, соответствующего этому имени
        for uid, uname in game.user_names.items():
            if uname == giver_name:
                text = (
                    f"🎄 Обновление по игре {game_id}.\n\n"
                    f"Твой человек *{wisher_name}* {action} к подарку:\n"
                    f"«{wish_text}»"
                )
                try:
                    await bot.send_message(uid, text, parse_mode="Markdown")
                except Exception as e:
                    print(f"Не удалось отправить уведомление пользователю {uid}: {e}")


# ---------- ПОМОЩНИКИ ДЛЯ РЕДАКТИРОВАНИЯ УЧАСТНИКОВ ----------

def add_participant_to_game(game: Game, line: str) -> None:
    """
    Добавить нового участника с минимальной правкой распределения.
    Строка может быть:
      - 'Имя Фамилия'
      - 'Имя Фамилия @username'
    """
    pretty, handle = parse_participant_line(line)
    pretty = pretty.strip()
    if not pretty:
        raise ValueError("Имя участника не может быть пустым.")

    norm = normalize_name(pretty)
    if norm in game.name_index:
        raise ValueError("Участник с таким именем уже есть в этой игре.")

    old_names = list(game.names)
    if len(old_names) < 2:
        raise ValueError("Нельзя добавлять участника в игру с менее чем 2 участниками.")

    game.names.append(pretty)
    game.name_index[norm] = pretty

    if handle:
        h = handle.strip().lstrip("@").lower()
        if h:
            game.handle_to_name[h] = pretty

    # минимальная правка дерранжмента:
    g = random.choice(old_names)
    r = game.assignment_by_name[g]
    game.assignment_by_name[g] = pretty
    game.assignment_by_name[pretty] = r


def remove_participant_from_game(game_id: str, game: Game, name_to_remove: str) -> str:
    """
    Удалить участника с минимальной правкой распределения:
    - в общем случае: A -> name_to_remove -> B заменяем на A -> B;
    - если получается самоназначение или что-то странное — пересчитаем всё целиком.
    Возвращает "patched" или "recomputed" для информации.
    """
    if name_to_remove not in game.names:
        raise ValueError("Такого участника нет в игре.")

    if len(game.names) <= 2:
        raise ValueError("Нельзя удалить участника: останется меньше 2 участников.")

    # кто дарил удаляемому?
    giver_pre = None
    for giver, receiver in game.assignment_by_name.items():
        if receiver == name_to_remove:
            giver_pre = giver
            break

    receiver_y = game.assignment_by_name.get(name_to_remove)

    # убираем из списков имён
    game.names.remove(name_to_remove)
    # из словаря нормализованных имён
    norm = normalize_name(name_to_remove)
    game.name_index.pop(norm, None)
    # из распределения
    if name_to_remove in game.assignment_by_name:
        del game.assignment_by_name[name_to_remove]
    # из пожеланий
    game.gift_wishes.pop(name_to_remove, None)
    # из handle_to_name
    handles_to_drop = [h for h, nm in game.handle_to_name.items() if nm == name_to_remove]
    for h in handles_to_drop:
        del game.handle_to_name[h]
    # из user_names и глобальной карты user_games
    to_drop_ids = [uid for uid, nm in game.user_names.items() if nm == name_to_remove]
    for uid in to_drop_ids:
        del game.user_names[uid]
        if user_games.get(uid) == game_id:
            del user_games[uid]

    # если не получилось аккуратно "выкусить" из цикла — пересчитываем полностью
    if giver_pre is None or receiver_y is None or receiver_y == giver_pre:
        receivers = make_derangement(game.names)
        game.assignment_by_name = {giver: rec for giver, rec in zip(game.names, receivers)}
        return "recomputed"

    # нормальный случай: просто замыкаем A -> B
    game.assignment_by_name[giver_pre] = receiver_y
    return "patched"


# ------------------ ОБРАБОТЧИКИ КОМАНД ------------------


@dp.message(F.text == "/help")
async def cmd_help(message: types.Message):
    text = (
        "🎄 *Тайный Санта — бот*\n\n"
        "*Для организатора:*\n"
        "1. Напиши /newgame — я создам *код игры*.\n"
        "2. В ответ пришли список участников: по одному `Имя Фамилия` в каждой строке.\n"
        "   Можно добавить хэндл: `Иван Иванов @username`.\n"
        "3. Отправь участникам код игры и ссылку на бота.\n"
        "4. Используй /orgmenu, чтобы открыть меню организатора и выбрать игру.\n"
        "5. После выбора игры можно:\n"
        "   • смотреть списки через кнопки меню\n"
        "   • редактировать участников командами:\n"
        "     `/addplayer Имя Фамилия[@username]` — добавить\n"
        "     `/delplayer Имя Фамилия` — удалить\n\n"
        "*Для участника:*\n"
        "1. Напиши /start.\n"
        "2. Введи *код игры* от организатора (например: `A7F9`).\n"
        "   Можно участвовать в нескольких играх: каждый новый код переключает тебя в другую комнату.\n"
        "3. Если твой @username уже указан в списке, я узнаю тебя автоматически.\n"
        "4. Если не узнал — введи свои имя и фамилию.\n"
        "5. Нажми кнопку «🎁 Получить имя».\n"
        "6. Нажми кнопку «📝 Пожелание к подарку», чтобы задать или изменить пожелание.\n\n"
        "*Бот:*\n"
        "- никому не даёт самого себя\n"
        "- один и тот же человек выдаётся только одному участнику в каждой игре\n"
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
        "Можно участвовать сразу в нескольких играх — каждый новый код переключает тебя в другую комнату.\n"
        "Если организатор прописал тебя как `Имя Фамилия @твой_ник`, "
        "я узнаю тебя по @username автоматически.",
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
        "Каждый участник — в отдельной строке, формат:\n"
        "`Имя Фамилия` или `Имя Фамилия @username`.\n"
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
            if user_games.get(uid) == game_id:
                user_games.pop(uid, None)

    games.pop(game_id, None)
    pending_game_codes.pop(organizer_id, None)
    organizer_games.pop(organizer_id, None)
    save_state()

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
            "Похоже, эта игра уже была сброшена организатором 😔\n"
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
            f"Твой человек в игре {game_id}: **{recipient}** 🎁\n"
            f"Его/её пожелание к подарку:\n«{wish}»\n\n"
            "Никому не рассказывай 😉"
        )
    else:
        text = (
            f"Твой человек в игре {game_id}: **{recipient}** 🎁\n"
            "Этот участник пока не указал пожелание к подарку.\n\n"
            "Никому не рассказывай 😉"
        )

    await message.answer(text, parse_mode="Markdown")


@dp.message(F.text == "📝 Пожелание к подарку")
async def handle_wish_button(message: types.Message):
    """
    Кнопка для ввода/изменения пожелания к подарку.
    Работает в два шага:
      1) пользователь жмёт кнопку
      2) следующим сообщением присылает текст пожелания
    """
    user_id = message.from_user.id

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
            "Похоже, эта игра уже была сброшена организатором 😔\n"
            "Спросите у организатора, не создал ли он новую игру."
        )
        return

    if user_id not in game.user_names:
        await message.answer(
            "Сначала напиши своё *имя и фамилию*, как в списке у организатора,\n"
            "чтобы я понял, кто ты 🙂",
            parse_mode="Markdown",
        )
        return

    pretty_name = game.user_names[user_id]
    current_wish = game.gift_wishes.get(pretty_name)

    waiting_wish_users.add(user_id)

    if current_wish:
        await message.answer(
            f"Сейчас твоё пожелание к подарку в игре {game_id}:\n«{current_wish}»\n\n"
            "Отправь *одним следующим сообщением* новый текст, если хочешь изменить пожелание.",
            parse_mode="Markdown",
        )
    else:
        await message.answer(
            f"Игра {game_id}.\n"
            "Отправь *одним следующим сообщением* своё пожелание к подарку.\n\n"
            "Например:\n"
            "«Что-то сладкое и тёплые носки» 🙂",
            parse_mode="Markdown",
        )


# ---------- Пожелания по подарку (команда /wish — для совместимости) ----------


@dp.message(F.text.startswith("/wish"))
async def cmd_wish(message: types.Message):
    """
    Команда /wish — оставлена для совместимости.
    Основной способ теперь — кнопка «📝 Пожелание к подарку».
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
            "Похоже, эта игра уже была сброшена организатором 😔\n"
            "Спросите у организатора, не создал ли он новую игру."
        )
        return

    if user_id not in game.user_names:
        await message.answer(
            "Сначала напиши своё *имя и фамилию*, как в списке у организатора,\n"
            "а потом уже можно будет указать пожелание (кнопкой или командой) 🙂",
            parse_mode="Markdown",
        )
        return

    pretty_name = game.user_names[user_id]

    parts = text.split(maxsplit=1)
    if len(parts) == 2 and parts[1].strip():
        # вариант `/wish текст` — обрабатываем сразу
        wish_text = parts[1].strip()
        had_prev = pretty_name in game.gift_wishes
        game.gift_wishes[pretty_name] = wish_text
        waiting_wish_users.discard(user_id)
        save_state()
        await message.answer(
            f"Пожелание сохранено! 🎁\n"
            f"{pretty_name}, ты указал(а):\n«{wish_text}»"
        )
        await notify_givers_about_wish(game_id, game, pretty_name, wish_text, had_prev)
        return

    # `/wish` без текста — ведём себя как наша кнопка: просим прислать следующим сообщением
    waiting_wish_users.add(user_id)
    await message.answer(
        "Отправь *одним следующим сообщением* своё пожелание к подарку.\n\n"
        "Например:\n"
        "«Что-то сладкое и тёплые носки» 🙂",
        parse_mode="Markdown",
    )


# ---------- КОМАНДЫ РЕДАКТИРОВАНИЯ УЧАСТНИКОВ ----------


@dp.message(F.text.startswith("/addplayer"))
async def cmd_addplayer(message: types.Message):
    """
    /addplayer Имя Фамилия[@username] — добавить участника в ТЕКУЩУЮ игру организатора.
    Текущая игра выбирается через /orgmenu (последняя выбранная).
    """
    organizer_id = message.from_user.id
    if organizer_id not in organizer_games:
        await message.answer(
            "Сначала выберите нужную игру в меню /orgmenu,\n"
            "а потом используйте команду /addplayer."
        )
        return

    game_id = organizer_games[organizer_id]
    game = games.get(game_id)
    if game is None or game.organizer_id != organizer_id:
        await message.answer("Игра не найдена или вы не являетесь её организатором.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "Использование:\n`/addplayer Имя Фамилия[@username]`",
            parse_mode="Markdown",
        )
        return

    new_line = parts[1].strip()
    try:
        add_participant_to_game(game, new_line)
    except ValueError as e:
        await message.answer(str(e))
        return

    save_state()
    await message.answer(
        f"Участник «{new_line}» добавлен в игру {game_id}.\n"
        "Распределение подарков изменено минимально (затронуты только пары с этим участником)."
    )


@dp.message(F.text.startswith("/delplayer"))
async def cmd_delplayer(message: types.Message):
    """
    /delplayer Имя Фамилия — удалить участника из ТЕКУЩЕЙ выбранной игры организатора.
    Можно написать и с @никнеймом в конце — он будет проигнорирован.
    """
    organizer_id = message.from_user.id
    if organizer_id not in organizer_games:
        await message.answer(
            "Сначала выберите нужную игру в меню /orgmenu,\n"
            "а потом используйте команду /delplayer."
        )
        return

    game_id = organizer_games[organizer_id]
    game = games.get(game_id)
    if game is None or game.organizer_id != organizer_id:
        await message.answer("Игра не найдена или вы не являетесь её организатором.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "Использование:\n`/delplayer Имя Фамилия`",
            parse_mode="Markdown",
        )
        return

    raw_line = parts[1].strip()
    name_only, _ = parse_participant_line(raw_line)
    norm = normalize_name(name_only)
    pretty = game.name_index.get(norm)
    if not pretty:
        await message.answer(
            "Участник с таким именем не найден в этой игре.\n"
            "Проверьте написание (как в изначальном списке)."
        )
        return

    try:
        mode = remove_participant_from_game(game_id, game, pretty)
    except ValueError as e:
        await message.answer(str(e))
        return

    save_state()
    text = f"Участник «{pretty}» удалён из игры {game_id}."
    if mode == "recomputed":
        text += (
            "\nПри удалении пришлось полностью перераспределить пары, "
            "чтобы никому не достался он сам."
        )
    else:
        text += "\nПары скорректированы минимально."
    await message.answer(text)


# ---------- Меню организатора ----------


@dp.message(F.text == "/orgmenu")
async def cmd_orgmenu(message: types.Message):
    """
    Главное меню организатора: список всех его игр.
    """
    organizer_id = message.from_user.id

    organizer_game_list = [
        (game_id, g) for game_id, g in games.items() if g.organizer_id == organizer_id
    ]

    if not organizer_game_list:
        await message.answer(
            "У вас пока нет ни одной созданной игры (или все были сброшены).\n"
            "Создайте новую через /newgame."
        )
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

    organizer_games[organizer_id] = game_id
    save_state()

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
        "Выберите, что показать, или используйте команды:\n"
        "`/addplayer Имя Фамилия[@username]` — добавить участника\n"
        "`/delplayer Имя Фамилия` — удалить участника\n"
        "(из этой игры).",
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

    name_to_handle: Dict[str, str] = {}
    for handle, name in game.handle_to_name.items():
        name_to_handle[name] = handle

    lines = [f"👥 Список участников и их пожеланий (игра {game_id}):\n"]
    for i, name in enumerate(game.names, start=1):
        handle = name_to_handle.get(name)
        display = f"{name} (@{handle})" if handle else name
        wish = game.gift_wishes.get(name)
        if wish:
            line = f"{i}. {display} — пожелание: {wish}"
        else:
            line = f"{i}. {display} — (пожелание не указано)"
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

    lines = [f"🔐 Распределение подарков (игра {game_id}):\n"]
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
    1) Пользователь после /wish или кнопки присылает текст пожелания
    2) Ждём список участников от организатора после /newgame
    3) Пользователь вводит код игры (всегда можно ввести новый, чтобы переключиться в другую комнату)
    4) Пользователь (уже в игре) что-то пишет:
       - если ещё не опознан — пытаемся по @username или по Имя Фамилия
       - если уже опознан — просто напоминаем про кнопки
    """
    text = (message.text or "").strip()
    user_id = message.from_user.id

    # --- 1) Пользователь присылает текст пожелания после кнопки или /wish ---
    if user_id in waiting_wish_users:
        waiting_wish_users.discard(user_id)

        if user_id not in user_games:
            await message.answer(
                "Похоже, ты ещё не присоединился ни к одной игре. "
                "Сначала введи код игры и своё имя 🙂"
            )
            return

        game_id_for_wish = user_games[user_id]
        game_for_wish = games.get(game_id_for_wish)
        if game_for_wish is None:
            await message.answer(
                "Эта игра была сброшена организатором 😔\n"
                "Спросите у него новый код игры или переключитесь в другую комнату, "
                "просто отправив её код."
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

        had_prev = pretty_name in game_for_wish.gift_wishes
        game_for_wish.gift_wishes[pretty_name] = text
        save_state()
        await message.answer(
            f"Пожелание сохранено! 🎁\n"
            f"{pretty_name}, ты указал(а):\n«{text}»"
        )
        # уведомляем дарителя
        await notify_givers_about_wish(game_id_for_wish, game_for_wish, pretty_name, text, had_prev)
        return

    # Игнорируем неизвестные команды
    if text.startswith("/"):
        await message.answer("Неизвестная команда. Попробуй /help 🙂")
        return

    # --- 2) Организатор присылает список участников для только что созданной игры ---
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
            game = Game(organizer_id=user_id, rows=lines)
        except ValueError as e:
            await message.answer(f"Ошибка в списке участников: {e}")
            return

        games[game_id] = game
        organizer_games[user_id] = game_id
        pending_game_codes.pop(user_id, None)
        save_state()

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
            "4) (если я их не узнал по @username) — вводят имя и фамилию\n"
            "5) нажимают «🎁 Получить имя»\n"
            "6) нажимают «📝 Пожелание к подарку» и указывают пожелание",
            parse_mode="Markdown",
        )
        return

    # --- 3A) Пользователь ещё не в игре — трактуем ввод как код игры ---
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

        # пробуем определить по @username
        tg_username = message.from_user.username
        auto_bound = False
        pretty = None
        if tg_username:
            h = tg_username.lower()
            pretty = game.handle_to_name.get(h)
            if pretty:
                game.user_names[user_id] = pretty
                auto_bound = True

        save_state()

        if auto_bound:
            kb = make_gift_keyboard()
            await message.answer(
                f"Игра с кодом *{game_id}* найдена! 🎄\n"
                f"Я нашёл тебя в списке как *{pretty}* по твоему @username.\n\n"
                "Теперь нажми кнопку «🎁 Получить имя», чтобы узнать, кому ты даришь подарок.\n\n"
                "Если хочешь, нажми «📝 Пожелание к подарку», чтобы задать пожелание.",
                parse_mode="Markdown",
                reply_markup=kb,
            )
        else:
            await message.answer(
                f"Игра с кодом *{game_id}* найдена! 🎄\n"
                "Теперь напиши свои *имя и фамилию* так, как они есть в списке у организатора.\n",
                parse_mode="Markdown",
            )
        return

    # --- 3B) Пользователь уже в какой-то игре — проверяем, не ввёл ли он НОВЫЙ код игры ---
    maybe_code = text.upper()
    if maybe_code in games:
        game = games[maybe_code]
        user_games[user_id] = maybe_code

        # пробуем автоопознать по username в НОВОЙ игре
        tg_username = message.from_user.username
        auto_bound = False
        pretty = None
        if tg_username:
            h = tg_username.lower()
            pretty = game.handle_to_name.get(h)
            if pretty:
                game.user_names[user_id] = pretty
                auto_bound = True

        save_state()

        if auto_bound:
            kb = make_gift_keyboard()
            await message.answer(
                f"Ты переключился в игру *{maybe_code}* 🎄\n"
                f"Я нашёл тебя в её списке как *{pretty}* по твоему @username.\n\n"
                "Теперь нажми «🎁 Получить имя», чтобы узнать, кому ты даришь подарок в этой игре,\n"
                "или «📝 Пожелание к подарку», чтобы указать пожелание.",
                parse_mode="Markdown",
                reply_markup=kb,
            )
        else:
            await message.answer(
                f"Ты переключился в игру *{maybe_code}* 🎄\n"
                "Теперь напиши свои *имя и фамилию* так, как они есть в списке у организатора этой игры.\n",
                parse_mode="Markdown",
            )
        return

    # --- 4) Пользователь уже в игре, это не код — работаем в контексте ТЕКУЩЕЙ игры ---
    game_id = user_games[user_id]
    game = games.get(game_id)

    if game is None:
        await message.answer(
            "Похоже, эта игра уже была сброшена организатором 😔\n"
            "Если ты участвуешь ещё в другой игре, просто отправь её код, чтобы переключиться."
        )
        return

    # Если мы УЖЕ знаем его имя — не просим вводить его снова
    if user_id in game.user_names:
        kb = make_gift_keyboard()
        await message.answer(
            f"Сейчас ты в игре {game_id} 🙂\n"
            "Нажми «🎁 Получить имя», чтобы узнать, кому ты даришь подарок,\n"
            "или «📝 Пожелание к подарку», чтобы задать или изменить пожелание.",
            reply_markup=kb,
        )
        return

    # Если ещё не знаем — сперва пробуем по @username (на случай старых игр / старого состояния)
    tg_username = message.from_user.username
    if tg_username:
        h = tg_username.lower()
        pretty = game.handle_to_name.get(h)
        if pretty:
            game.user_names[user_id] = pretty
            save_state()
            kb = make_gift_keyboard()
            await message.answer(
                f"Я нашёл тебя в списке игры {game_id} как *{pretty}* по твоему @username.\n\n"
                "Теперь нажми «🎁 Получить имя», чтобы узнать, кому ты даришь подарок,\n"
                "или «📝 Пожелание к подарку», чтобы задать пожелание.",
                parse_mode="Markdown",
                reply_markup=kb,
            )
            return

    # ВАЖНО: убираем возможный хвост '@nickname', чтобы не ломать поиск по имени
    name_only, _ = parse_participant_line(text)
    norm = normalize_name(name_only)

    if norm not in game.name_index:
        await message.answer(
            f"Я не нашёл тебя в списке участников игры {game_id} 😔\n\n"
            "Напиши *имя и фамилию* так, как они есть в списке у организатора,\n"
            "в одну строку (без лишних символов).\n\n"
            "Например:\n"
            "`Евгения Дмитриева`\n"
            "`Юлия Павликова`",
            parse_mode="Markdown",
        )
        return

    pretty_name = game.name_index[norm]
    game.user_names[user_id] = pretty_name
    save_state()

    kb = make_gift_keyboard()

    await message.answer(
        f"Отлично, {pretty_name}! 🎄\n"
        f"Твоё имя записано в игре {game_id}.\nТеперь нажми \n"
        f"«🎁 Получить имя», чтобы узнать, кому ты даришь подарок,\n"
        f"и при желании «📝 Пожелание к подарку», чтобы указать своё пожелание.",
        reply_markup=kb,
    )


# ---------------------- ЗАПУСК БОТА ----------------------


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
