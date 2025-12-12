🎄 Secret Santa Telegram Bot
(The English description is located below this one)

Универсальный Telegram-бот для проведения игры «Тайный Санта» в любых компаниях, командах, университетах или семейных чатах.

Бот позволяет провести честный и автоматический розыгрыш подарков:

 • никто не получает сам себя
 
 • каждый человек в каждой игре получает ровно одного получателя
 
 • организатор задаёт список участников (при желании — с @никнеймами)
 
 • участники сами заходят в нужные игры по коду
 
 • бот учитывает разные варианты написания (ё/е, регистр, пробелы)
 
 • бот умеет автоматически узнавать участников по @username
 
 • каждый участник может указать и менять своё пожелание к подарку
 
 • при изменении пожелания бот уведомляет дарителя (“Твой человек указал своё пожелание…”)
 
 • результат в рамках игры стабилен: один участник → один человек

Бот поддерживает много игр одновременно через game code, а участник может участвовать сразу в нескольких играх и переключаться между ними, просто отправляя код нужной игры.

Бот написан на Python + aiogram 3 и готов к использованию на Replit, VDS или любом Python-сервере.

✨ Возможности

👑 Для организатора:

 • команда /newgame создаёт новую игру и выдаёт код игры (например, A7F9), который нужно отправить участникам.
 
 • бот ожидает список участников одним сообщением, построчно, формат:

Иван Иванов

Пётр Петров @petya

Анна Смирнова @anna_smirnova


 • в каждой строке можно указать только имя/фамилию, а можно добавить и Telegram-аккаунт:
Имя Фамилия @username — это позволит боту автоматически узнавать участника, когда он зайдёт в игру.

 Код игры используется участниками, чтобы присоединиться именно к вашей игре.

После получения списка участников, бот:

 • очищает список, удаляет дубликаты
 
 • автоматически создаёт честное распределение «кто кому дарит» (дерранжмент — никто не получает сам себя)

Далее у организатора доступны дополнительные функции:

 • /orgmenu — меню организатора со списком всех созданных им игр
 
 • выбор конкретной игры показывает inline-меню:
 
   • «👥 Участники и пожелания» — список всех участников игры + их пожелания к подаркам (если указаны)
   
   • «🔐 Кто кому дарит» — полный список пар «кто кому дарит»

 • организатор может редактировать список участников уже после создания игры:
 
   • /addplayer Имя Фамилия[@username] — добавить нового участника в выбранную игру
   
   • /delplayer Имя Фамилия — удалить участника из выбранной игры

При добавлении/удалении участника бот старается минимально менять существующее распределение, перелопачивая только пары вокруг нового/удалённого участника. Если это невозможно без конфликтов, распределение пересчитывается честно заново.

 • /reset — полный сброс всех игр этого организатора (включая незавершённые). Все созданные им комнаты удаляются.

🎁 Для участника:

 • пишет /start
 
 • вводит код игры от организатора (например, A7F9)
 
 • может участвовать в нескольких играх — каждый новый код переключает бота в другую «комнату»
 
 • если организатор указал в списке Имя Фамилия @username, бот автоматически узнаёт участника по его @никнейму
 
 • если авто-опознания нет, участник вводит своё имя и фамилию так, как в списке у организатора

После успешного входа в игру участник получает клавиатуру с кнопками:

 • 🎁 Получить имя — бот сообщает, кому именно этот участник дарит подарок в текущей игре.
 
 • 📝 Пожелание к подарку — участник может указать или изменить своё пожелание (желания к подарку).

Пожелание можно задавать и менять:

 • при первом вводе — бот сохраняет текст как пожелание к подарку
 
 • при повторном — обновляет пожелание

Когда участник впервые указывает или меняет своё пожелание, бот:

 • находит того, кто дарит ему подарок в этой игре
 
 • отправляет этому дарителю личное уведомление:
 
«Твой человек указал/обновил своё пожелание…» с текстом желания

Нажимать кнопку «🎁 Получить имя» можно сколько угодно раз — результат в рамках конкретной игры фиксированный и не меняется.

🧠 Умная обработка имён и пользователей

Бот нормализует текст:

 • ё = е
 
 • регистр не важен (анГЕлина киСЕЛЕва)
 
 • лишние пробелы не мешают
 
 • принимает русские имена в любом виде

Пример вводов, которые считаются одним и тем же человеком:

 Ангелина Киселева
 
 ангелина киселЕва
 
 АНГЕЛИНА КИСЕЛЁВА
 

Кроме этого, бот умеет:

 • сопоставлять участника с записью в списке по @username (если организатор указал @никнейм в строке участника)
 
 • автоматически определять участника при входе в игру по его Telegram-аккаунту
 
 • помнить участие одного пользователя сразу в нескольких играх и переключаться между ними по введённому коду игры.


Бот поддерживает неограниченное количество игр одновременно: каждая игра имеет свой game_id (короткий код), а участники привязаны к нужной игре по этому коду. Один пользователь может быть в нескольких играх сразу.

🎮 Команды

Команда	Описание

/start	Начать / присоединиться к игре, ввести код игры

/help	Подробная инструкция

/newgame	Создать новую игру (только организатор)

/orgmenu	Меню организатора: список игр, просмотр участников/пожеланий и пар

/addplayer Имя Фамилия[@username]	Добавить участника в выбранную игру организатора

/delplayer Имя Фамилия	Удалить участника из выбранной игры организатора

/reset	Полный сброс всех игр, созданных этим организатором

/wish ...	(Опционально) указать/изменить своё пожелание текстом; основной способ — кнопка «📝 Пожелание к подарку»

🚀 Как запустить локально

1. Установите зависимости

pip install aiogram==3.4.1 python-dotenv aiohttp aiofiles


2. Создайте файл .env:

BOT_TOKEN=ВАШ_ТОКЕН


3. Запустите бота:

python main.py


❤️ Автор

Бот разработан для массового использования: корпоративы, школьные группы, университеты, семейные чаты и любые события, где нужен честный и удобный Secret Santa с пожеланиями и уведомлениями для дарителей.

Ссылка на бот: https://t.me/santasecretpresentsbot

Для связи с создателем: @angel_eugeniya (TELEGRAM)

❄ Приятного использования!

ENGLISH:

🎄 Secret Santa Telegram Bot

Bot link: https://t.me/santasecretpresentsbot

A universal Telegram bot for running Secret Santa games for companies, teams, school groups, university classrooms, communities, and families.

The bot automates the entire process:

 ✔ nobody gets themselves
 
 ✔ each participant in each game receives exactly one recipient
 
 ✔ organizer defines the participants list (optionally with Telegram usernames)
 
 ✔ participants join via game code
 
 ✔ bot handles name normalization (ё/e, case, spaces)
 
 ✔ bot can auto-recognize users by their @username
 
 ✔ each participant can set and update a personal gift wish
 
 ✔ whenever a wish is set/changed, the Secret Santa is notified with the wish text
 
 ✔ each user always receives the same fixed recipient in a given game

The bot supports multiple games in parallel via game codes, and a single user can participate in multiple games at once by switching between them using their game codes.

Built with Python + aiogram 3, ready to run on Replit, VDS, Docker, or any Python server.

✨ Features

👑 For organizers

 • /newgame — create a new game and receive a game code (e.g. A7F9)
 
 • send a single message with the full participants list; one participant per line, for example:

Yulia Pavlikova

Evgenia Dmitrieva

Elena Meshcheryakova @elena_m


You may specify just name + surname, or name + surname + @username:

FirstName LastName @username — this allows the bot to automatically recognize a participant by their Telegram account.

The game code is what participants use to join exactly your game.

After receiving the list, the bot:

 • cleans the list
 
 • removes duplicates
 
 • ensures at least 2 participants
 
 • generates a fair derangement (nobody gets themselves)

Organizers also get:

 • /orgmenu — organizer menu with a list of all games they created
 
 • selecting a game opens an inline menu with:
 
   • “👥 Participants & wishes” — full list of participants and their gift wishes (if any)
   
   • “🔐 Who gives to whom” — full mapping of gift pairs

 • Editing participants after game creation:
 
   • /addplayer FirstName LastName[@username] — add a new participant to the currently selected game
   
   • /delplayer FirstName LastName — remove a participant from the currently selected game

When adding/removing participants, the bot tries to minimally modify the existing assignment, only adjusting pairs around the changed participant. If that’s impossible without conflicts, a new fair derangement is generated.

 • /reset — reset all games created by this organizer (including pending ones). All their rooms are deleted.

🎁 For participants

 • send /start
 
 • enter the game code from the organizer (e.g. A7F9)
 
 • you can participate in multiple games; sending another game code switches the bot to that “room”
 
 • if the organizer added your @username (FirstName LastName @your_handle), the bot will automatically match you to the participant record
 
 • otherwise, you enter your first and last name as the organizer wrote them

Once you are recognized in a game, you get a custom keyboard with:

 • 🎁 Get recipient — the bot tells you who you should give a present to in the current game
 
 • 📝 Gift wish — you can set or change your gift wish

Gift wishes:

 • first time you send a wish — it is stored as your preference
 
 • subsequent wishes overwrite the previous one

Whenever you set or update your wish, the bot:

 • finds your Secret Santa in this game
 
 • sends them a private notification:
 
“Your person has set/updated their gift wish…” with the text of your wish

You can press “🎁 Get recipient” as many times as you want — the result is always fixed for that game.

🧠 Smart name & user processing

The bot normalizes names:

 • treats ё as е
 
 • case-insensitive
 
 • collapses multiple spaces into one
 
 • accepts Russian names in any reasonable form

All of the following are treated as the same person:

 Ангелина Киселева
 
 ангелина киселева
 
 АНГЕЛИНА КИСЕЛЁВА

Additionally, the bot:

 • can match participants by their @username (if specified in the participants list)
 
 • automatically recognizes users when they join a game
 
 • allows a single Telegram user to be part of multiple games and switch between them just by sending another game code.

🎮 Commands

Command	Description
/start	Join a game; enter a game code

/help	Full instructions

/newgame	Create a new game (organizer only)

/orgmenu	Organizer menu: list games, view participants/wishes and pairs

/addplayer FirstName LastName[@username]	Add a participant to the selected game

/delplayer FirstName LastName	Remove a participant from the selected game

/reset	Reset all games created by this organizer

/wish ...	(Optional) Set/update your wish via text; main way is the “📝 Gift wish” button

🚀 How to run locally

1. Install dependencies

pip install aiogram==3.4.1 python-dotenv aiohttp aiofiles


2. Create a .env file

BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN


3. Run the bot

python main.py


❤️ Author

This bot was created for public, large-scale usage: companies, school groups, university teams, family chats, and any events where a fair, user-friendly Secret Santa with wishes and donor notifications is needed.

Bot link: https://t.me/santasecretpresentsbot

Contact: @angel_eugeniya (Telegram)

❄️ Enjoy your Secret Santa experience!
