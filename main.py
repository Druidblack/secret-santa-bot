import asyncio
import random
from typing import Dict, List, Set, Optional

import json
import os

from aiogram import Bot, Dispatcher, F, types

# --------- ВСТАВЬ СВОЙ ТОКЕН ---------
TOKEN = os.getenv("TOKEN", "")

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


def make_gift_keyboard(chat_active: bool = False) -> types.ReplyKeyboardMarkup:
    """Клавиатура участника. Выход из чата виден только во время переписки."""
    rows = [
        [
            types.KeyboardButton(text="🎁 Получить имя"),
            types.KeyboardButton(text="📝 Пожелание к подарку"),
        ],
        [types.KeyboardButton(text="💬 Анонимная переписка")],
    ]
    if chat_active:
        rows.append([types.KeyboardButton(text="⛔ Завершить чат")])
    return types.ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def make_chat_choice_keyboard(game_id: str, revision: int) -> types.InlineKeyboardMarkup:
    """У каждого участника две роли: даритель и получатель."""
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(
            text="🎁 Написать тому, кому дарю",
            callback_data=f"chat_start:{game_id}:{revision}:to_recipient",
        )],
        [types.InlineKeyboardButton(
            text="🎅 Написать моему Санте",
            callback_data=f"chat_start:{game_id}:{revision}:to_santa",
        )],
    ])


def make_chat_reply_keyboard(game_id: str, revision: int, direction: str) -> types.InlineKeyboardMarkup:
    """Кнопка ответа ведёт обратно в эту пару и эту игру."""
    reverse = "to_santa" if direction == "to_recipient" else "to_recipient"
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(
            text="↩️ Ответить анонимно",
            callback_data=f"chat_reply:{game_id}:{revision}:{reverse}",
        )],
    ])


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
        self.chat_revision: int = 0                           # защита от старых кнопок ответов

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
            "chat_revision": self.chat_revision,
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
        obj.chat_revision = int(data.get("chat_revision", 0))
        obj.handle_to_name = dict(data.get("handle_to_name", {}))
        return obj


# ---------- ГЛОБАЛЬНОЕ СОСТОЯНИЕ БОТА ----------

bot = Bot(token=TOKEN)
dp = Dispatcher()

# все активные игры: game_id -> Game
games: Dict[str, Game] = {}

# организатор -> код игры, от которого сейчас ждём список участников (после /newgame)
pending_game_codes: Dict[int, str] = {}

# организатор -> "последняя активная" игра (для /addplayer, /delplayer)
organizer_games: Dict[int, str] = {}

# пользователь -> КОД ТЕКУЩЕЙ игры (в которой он сейчас "находится" в боте)
user_games: Dict[int, str] = {}

# пользователи, от которых мы ждём текст пожелания после /wish или кнопки
waiting_wish_users: Set[int] = set()

# user_id -> {"game_id": ..., "direction": "to_santa" | "to_recipient"}
# Сохраняем между перезапусками, но при переключении игры / изменении пар сбрасываем.
chat_modes: Dict[int, Dict[str, str]] = {}

STATE_FILE = "secret_santa_state.json"


# ---------- СЕРИАЛИЗАЦИЯ СОСТОЯНИЯ ----------

def save_state() -> None:
    data = {
        "games": {gid: game.to_dict() for gid, game in games.items()},
        "user_games": {str(uid): gid for uid, gid in user_games.items()},
        "organizer_games": {str(uid): gid for uid, gid in organizer_games.items()},
        "chat_modes": {str(uid): mode for uid, mode in chat_modes.items()},
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

    chat_modes.clear()
    for uid_str, mode in data.get("chat_modes", {}).items():
        try:
            uid = int(uid_str)
            gid = mode["game_id"]
            direction = mode["direction"]
            if (direction in ("to_santa", "to_recipient") and gid in games
                    and user_games.get(uid) == gid
                    and uid in games[gid].user_names):
                chat_modes[uid] = {"game_id": gid, "direction": direction}
        except (ValueError, KeyError, TypeError):
            continue


load_state()


# ---------- АНОНИМНАЯ ПЕРЕПИСКА ----------


def claim_participant(game: Game, user_id: int, name: str, username: Optional[str]) -> Optional[str]:
    """Привязываем имя к одному Telegram ID, не позволяя занять чужое имя.

    Если организатор указал @username, ручной ввод имени не обходит его проверку.
    Для имён без @username по-прежнему требуется доверие к коду приглашения:
    невозможно проверить реальную личность только по введённому имени.
    """
    existing = game.user_names.get(user_id)
    if existing is not None and existing != name:
        return "Твой Telegram-аккаунт уже привязан к другому имени в этой игре. Обратись к организатору."

    expected_handles = [handle for handle, nm in game.handle_to_name.items() if nm == name]
    if expected_handles and (not username or username.lower() not in expected_handles):
        return "Для этого имени организатор указал другой @username. Войди с нужного Telegram-аккаунта."

    if any(uid != user_id and nm == name for uid, nm in game.user_names.items()):
        return "Это имя уже занято другим Telegram-аккаунтом. Если это ошибка, обратись к организатору."

    game.user_names[user_id] = name
    return None


def auto_identify_participant(game: Game, user_id: int, username: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Сначала доверяем ранее привязанному Telegram ID, затем @username."""
    existing = game.user_names.get(user_id)
    if existing in game.names:
        return existing, None
    if existing is not None:
        return None, "Прежняя запись о тебе больше не существует. Обратись к организатору."
    if not username:
        return None, None
    pretty = game.handle_to_name.get(username.lower())
    if not pretty:
        return None, None
    error = claim_participant(game, user_id, pretty, username)
    return (None, error) if error else (pretty, None)


def clear_chats_for_game(game_id: str) -> None:
    """Изменённое распределение не должно незаметно менять собеседника активного чата."""
    for uid, mode in list(chat_modes.items()):
        if mode["game_id"] == game_id:
            chat_modes.pop(uid, None)


def chat_other_participant(game: Game, name: str, direction: str) -> Optional[str]:
    if direction == "to_recipient":
        return game.assignment_by_name.get(name)
    if direction == "to_santa":
        return next((giver for giver, receiver in game.assignment_by_name.items()
                     if receiver == name), None)
    return None


def chat_other_user_id(game: Game, name: str) -> tuple[Optional[int], Optional[str]]:
    matches = [uid for uid, participant in game.user_names.items() if participant == name]
    if not matches:
        return None, "Собеседник ещё не присоединился к игре. Сообщение не отправлено; попробуй позже."
    if len(matches) > 1:
        return None, "В игре обнаружено несколько аккаунтов с одним именем. Обратись к организатору."
    return matches[0], None


def chat_direction_label(direction: str) -> str:
    if direction == "to_recipient":
        return "человеку, которому ты даришь подарок"
    return "твоему Тайному Санте"


async def send_anonymous_message(message: types.Message, game_id: str, direction: str) -> None:
    """Передаёт содержимое через бота без Telegram forwarding/sender attribution."""
    user_id = message.from_user.id
    game = games.get(game_id)
    if (not game or user_games.get(user_id) != game_id
            or user_id not in game.user_names):
        chat_modes.pop(user_id, None)
        save_state()
        await message.answer("Сначала войди в игру и выбери переписку заново.")
        return

    my_name = game.user_names[user_id]
    other_name = chat_other_participant(game, my_name, direction)
    if not other_name:
        chat_modes.pop(user_id, None)
        save_state()
        await message.answer("Не удалось найти собеседника. Выбери чат снова или обратись к организатору.")
        return

    recipient_id, error = chat_other_user_id(game, other_name)
    if error:
        await message.answer(error)
        return

    # Не сообщаем адресату Telegram ID, username или имя отправителя.
    # В сообщении только роль, код игры и написанный пользователем текст/медиа.
    role = "🎅 Сообщение от твоего Тайного Санты" if direction == "to_recipient" else "🎁 Сообщение от получателя твоего подарка"
    header = f"{role} (игра {game_id})"
    reply_markup = make_chat_reply_keyboard(game_id, game.chat_revision, direction)
    content_type = message.content_type
    allowed_caption_media = {"photo", "video", "animation", "voice"}
    allowed_other_media = {"sticker", "video_note"}

    if content_type != "text" and content_type not in allowed_caption_media | allowed_other_media:
        await message.answer(
            "В анонимном чате поддерживаются текст, фото, видео, GIF, голосовые сообщения и стикеры. "
            "Контакты, документы и другие типы вложений не пересылаются, чтобы не раскрыть личные данные."
        )
        return
    try:
        if content_type == "text":
            # Безопасный размер блока даже для Unicode / emoji (Telegram: 4096 символов).
            chunks = [message.text[i:i + 1800] for i in range(0, len(message.text), 1800)]
            for i, chunk in enumerate(chunks):
                prefix = f"{header}\n\n" if i == 0 else "(продолжение)\n"
                await bot.send_message(
                    recipient_id, prefix + chunk,
                    reply_markup=reply_markup if i == 0 else None,
                )
        elif content_type in allowed_caption_media:
            caption = message.caption or ""
            combined = header + ("\n\n" + caption if caption else "")
            # Telegram ограничивает длину caption; не теряем длинный текст.
            if len(combined.encode("utf-16-le")) // 2 <= 1024:
                await bot.copy_message(
                    chat_id=recipient_id, from_chat_id=message.chat.id,
                    message_id=message.message_id, caption=combined,
                    reply_markup=reply_markup,
                )
            else:
                await bot.copy_message(
                    chat_id=recipient_id, from_chat_id=message.chat.id,
                    message_id=message.message_id, caption=header,
                    reply_markup=reply_markup,
                )
                await bot.send_message(recipient_id, f"Текст к вложению:\n{caption}")
        else:
            # Стикеры и видеосообщения не имеют подписи: добавляем пояснение отдельно.
            await bot.copy_message(
                chat_id=recipient_id, from_chat_id=message.chat.id,
                message_id=message.message_id, reply_markup=reply_markup,
            )
            await bot.send_message(recipient_id, header)
    except Exception as exc:
        print(f"Не удалось доставить анонимное сообщение в игре {game_id}: {exc}")
        await message.answer("Не удалось доставить сообщение через Telegram. Возможно, собеседник заблокировал бота. Попробуй позже.")
        return

    await message.answer(f"✅ Анонимное сообщение отправлено {chat_direction_label(direction)}.")


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
        "     `/delplayer Имя Фамилия` — удалить\n"
        "6. Команда `/reset` — сбрасывает *все* созданные вами игры.\n\n"
        "*Для участника:*\n"
        "1. Напиши /start.\n"
        "2. Введи *код игры* от организатора (например: `A7F9`).\n"
        "   Можно участвовать в нескольких играх: каждый новый код переключает тебя в другую комнату.\n"
        "3. Если твой @username уже указан в списке, я узнаю тебя автоматически.\n"
        "4. Если не узнал — введи свои имя и фамилию.\n"
        "5. Нажми кнопку «🎁 Получить имя».\n"
        "6. Нажми кнопку «📝 Пожелание к подарку», чтобы задать или изменить пожелание.\n"
        "7. Нажми «💬 Анонимная переписка» (/chat) и выбери: написать получателю или своему Санте.\n"
        "   Ответить на входящее можно кнопкой под сообщением. Выход из чата: /cancel.\n\n"
        "*Бот:*\n"
        "- никому не даёт самого себя\n"
        "- один и тот же человек выдаётся только одному участнику в каждой игре\n"
        "- ты можешь нажимать кнопку сколько угодно — твой человек не поменяется."
    )
    await message.answer(text, parse_mode="Markdown")


@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    if chat_modes.pop(message.from_user.id, None) is not None:
        save_state()
    waiting_wish_users.discard(message.from_user.id)
    await message.answer(
        "Привет! 🎄\n\n"
        "Если ты *организатор* — напиши \n/newgame и создай список участников.\n"
        "А затем используй /orgmenu, чтобы смотреть свои игры и пары.\n\n"
        "Если ты *участник* — отправь мне *код игры*, который тебе дал организатор.\n"
        "Например: `A7F9`.\n\n"
        "Можно участвовать сразу в нескольких играх — каждый новый код переключает тебя в другую комнату.\n"
        "Если организатор прописал тебя как `Имя Фамилия @твой_ник`, "
        "я узнаю тебя по @username автоматически.\n\n"
        "Внутри игры доступен анонимный чат с твоим Сантой и получателем подарка.",
        parse_mode="Markdown",
    )


@dp.message(F.text.in_({"💬 Анонимная переписка", "/chat"}))
async def cmd_chat(message: types.Message):
    user_id = message.from_user.id
    game_id = user_games.get(user_id)
    game = games.get(game_id) if game_id else None
    if game is None or user_id not in game.user_names:
        await message.answer("Сначала присоединись к игре по коду и укажи своё имя.")
        return

    chat_modes.pop(user_id, None)
    waiting_wish_users.discard(user_id)
    save_state()
    await message.answer(
        f"💬 Анонимная переписка в игре {game_id}.\n\n"
        "Кому хочешь написать? Бот не покажет собеседнику твой Telegram-аккаунт.\n"
        "Важно: текст и медиа могут сами раскрыть, кто ты.",
        reply_markup=make_chat_choice_keyboard(game_id, game.chat_revision),
    )


@dp.callback_query(F.data.startswith("chat_start:") | F.data.startswith("chat_reply:"))
async def cb_chat_select(callback: types.CallbackQuery):
    data = (callback.data or "").split(":")
    if len(data) != 4 or data[3] not in ("to_recipient", "to_santa"):
        await callback.answer("Неверная команда чата", show_alert=True)
        return
    _, game_id, revision, direction = data
    user_id = callback.from_user.id
    game = games.get(game_id)
    if game is None or user_id not in game.user_names:
        await callback.answer("Ты не участвуешь в этой игре. Сначала войди по её коду.", show_alert=True)
        return
    if str(game.chat_revision) != revision:
        await callback.answer("Распределение изменилось. Открой новое меню через /chat.", show_alert=True)
        return
    # Проверяем направление по актуальному распределению.
    if not chat_other_participant(game, game.user_names[user_id], direction):
        await callback.answer("Собеседник не найден", show_alert=True)
        return

    user_games[user_id] = game_id
    waiting_wish_users.discard(user_id)
    chat_modes[user_id] = {"game_id": game_id, "direction": direction}
    save_state()
    await callback.answer("Анонимный чат выбран")
    await callback.message.answer(
        f"💬 Игра {game_id}. Теперь ты пишешь {chat_direction_label(direction)}.\n"
        "Отправь сообщение — я передам его анонимно. Можно отправлять несколько сообщений подряд.\n"
        "Чтобы закончить, нажми «⛔ Завершить чат» или напиши /cancel.",
        reply_markup=make_gift_keyboard(chat_active=True),
    )


@dp.message(F.text.in_({"⛔ Завершить чат", "/cancel"}))
async def cmd_cancel(message: types.Message):
    user_id = message.from_user.id
    was_chat = chat_modes.pop(user_id, None) is not None
    was_wish = user_id in waiting_wish_users
    waiting_wish_users.discard(user_id)
    if was_chat:
        save_state()
    await message.answer(
        "Переписка завершена. Чтобы начать снова, нажми «💬 Анонимная переписка»."
        if was_chat else "Ожидание сообщения отменено." if was_wish else "Сейчас нечего отменять.",
        reply_markup=make_gift_keyboard(),
    )


@dp.message(F.text == "/newgame")
async def cmd_newgame(message: types.Message):
    """
    Создание новой игры. Вызывается организатором.
    После этого бот ждёт список участников в следующем сообщении.
    """
    organizer_id = message.from_user.id
    if chat_modes.pop(organizer_id, None) is not None:
        save_state()
    waiting_wish_users.discard(organizer_id)

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
    Полный сброс *всех* игр, созданных этим организатором.
    """
    organizer_id = message.from_user.id

    # Список всех игр, созданных этим организатором
    owned_games = [gid for gid, g in games.items() if g.organizer_id == organizer_id]

    if not owned_games and organizer_id not in pending_game_codes:
        await message.answer("У вас сейчас нет активных игр, сбрасывать нечего 🙂")
        return

    # Удаляем незавершённую (ожидающую список) игру, если есть
    pending_game_codes.pop(organizer_id, None)

    # Для каждой игры чистим участников и удаляем игру
    for game_id in owned_games:
        game = games.get(game_id)
        if not game:
            continue

        # убираем всех участников этой игры из user_games
        for uid in list(game.user_names.keys()):
            if user_games.get(uid) == game_id:
                user_games.pop(uid, None)

        # удаляем игру и связанные с ней режимы переписки
        clear_chats_for_game(game_id)
        games.pop(game_id, None)

    # убираем ссылку на "последнюю активную" игру для этого организатора
    organizer_games.pop(organizer_id, None)

    save_state()

    if owned_games:
        codes = ", ".join(sorted(owned_games))
        await message.answer(
            "Все ваши игры сброшены.\n"
            f"Удалены игры с кодами: {codes}.\n"
            "Можно создать новую через /newgame."
        )
    else:
        # Были только pending, без завершённых игр
        await message.answer(
            "Незавершённая игра (ожидающая список участников) была сброшена.\n"
            "Можно создать новую через /newgame."
        )


@dp.message(F.text == "🎁 Получить имя")
async def handle_get_recipient(message: types.Message):
    """
    Участник просит своего получателя.
    """
    user_id = message.from_user.id
    if chat_modes.pop(user_id, None) is not None:
        save_state()

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

    await message.answer(text, parse_mode="Markdown", reply_markup=make_gift_keyboard())


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

    if chat_modes.pop(user_id, None) is not None:
        save_state()
    waiting_wish_users.add(user_id)

    if current_wish:
        await message.answer(
            f"Сейчас твоё пожелание к подарку в игре {game_id}:\n«{current_wish}»\n\n"
            "Отправь *одним следующим сообщением* новый текст, если хочешь изменить пожелание.",
            parse_mode="Markdown",
            reply_markup=make_gift_keyboard(),
        )
    else:
        await message.answer(
            f"Игра {game_id}.\n"
            "Отправь *одним следующим сообщением* своё пожелание к подарку.\n\n"
            "Например:\n"
            "«Что-то сладкое и тёплые носки» 🙂",
            parse_mode="Markdown",
            reply_markup=make_gift_keyboard(),
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

    if chat_modes.pop(user_id, None) is not None:
        save_state()
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

    game.chat_revision += 1
    clear_chats_for_game(game_id)
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

    game.chat_revision += 1
    clear_chats_for_game(game_id)
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


async def switch_to_game(message: types.Message, game_id: str, was_in_game: bool) -> None:
    """Переключение комнаты: сбрасываем предыдущий чат и проверяем уникальность имени."""
    user_id = message.from_user.id
    game = games[game_id]
    chat_modes.pop(user_id, None)
    waiting_wish_users.discard(user_id)
    user_games[user_id] = game_id
    pretty, error = auto_identify_participant(game, user_id, message.from_user.username)
    save_state()

    prefix = f"Ты переключился в игру *{game_id}* 🎄" if was_in_game else f"Игра с кодом *{game_id}* найдена! 🎄"
    if error:
        await message.answer(f"{prefix}\n\n{error}", parse_mode="Markdown")
    elif pretty:
        await message.answer(
            f"{prefix}\n"
            f"Я нашёл тебя в списке как *{pretty}*.\n\n"
            "Нажми «🎁 Получить имя», «📝 Пожелание к подарку» "
            "или «💬 Анонимная переписка».",
            parse_mode="Markdown",
            reply_markup=make_gift_keyboard(),
        )
    else:
        await message.answer(
            f"{prefix}\nТеперь напиши свои *имя и фамилию* "
            "точно как в списке организатора.",
            parse_mode="Markdown",
        )


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
    if user_id in waiting_wish_users and text.upper() not in games:
        if not text:
            await message.answer("Пожелание должно быть текстом. Отправь текст или /cancel.")
            return
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
            "6) нажимают «📝 Пожелание к подарку» и указывают пожелание\n"
            "7) для личных вопросов используют «💬 Анонимная переписка»",
            parse_mode="Markdown",
        )
        return

    # --- 3A/3B) Ввод кода игры или переключение между играми ---
    if user_id not in user_games:
        game_id = text.upper()
        if game_id not in games:
            await message.answer(
                "Я не нашёл игру с таким кодом 😔\n"
                "Проверь, правильно ли ты ввёл код (например: `A7F9`).",
                parse_mode="Markdown",
            )
            return
        await switch_to_game(message, game_id, was_in_game=False)
        return

    maybe_code = text.upper()
    if maybe_code in games:
        await switch_to_game(message, maybe_code, was_in_game=True)
        return

    # --- Если выбран анонимный чат, любой обычный текст/медиа идёт собеседнику ---
    mode = chat_modes.get(user_id)
    if mode:
        await send_anonymous_message(message, mode["game_id"], mode["direction"])
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
            "«📝 Пожелание к подарку» или «💬 Анонимная переписка».",
            reply_markup=kb,
        )
        return

    # Если ещё не знаем — сперва пробуем @username (для старых игр / состояний).
    pretty, error = auto_identify_participant(game, user_id, message.from_user.username)
    if error:
        await message.answer(error)
        return
    if pretty:
        save_state()
        await message.answer(
            f"Я нашёл тебя в списке игры {game_id} как *{pretty}* по @username.\n\n"
            "Теперь доступны получение имени, пожелание и анонимная переписка.",
            parse_mode="Markdown",
            reply_markup=make_gift_keyboard(),
        )
        return

    if not text:
        await message.answer("Для входа напиши своё имя и фамилию текстом.")
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
    error = claim_participant(game, user_id, pretty_name, message.from_user.username)
    if error:
        await message.answer(error)
        return
    save_state()

    kb = make_gift_keyboard()

    await message.answer(
        f"Отлично, {pretty_name}! 🎄\n"
        f"Твоё имя записано в игре {game_id}.\nТеперь нажми \n"
        f"«🎁 Получить имя», чтобы узнать, кому ты даришь подарок,\n"
        f"«📝 Пожелание к подарку» или «💬 Анонимная переписка».",
        reply_markup=kb,
    )


# ---------------------- ЗАПУСК БОТА ----------------------


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
