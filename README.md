🎄 **Secret Santa Telegram Bot** (The English description is located below this one)

Ссылка на бот в самом Telegram: https://t.me/santasecretpresentsbot



***Универсальный Telegram-бот для проведения игры «Тайный Санта» в любых компаниях, командах, университетах или семейных чатах.***



Бот позволяет провести честный и автоматический розыгрыш подарков:

&nbsp;• никто не получает сам себя

&nbsp;• каждый человек получает ровно одного получателя

&nbsp;• организатор задаёт список участников

&nbsp;• участники сами вводят свои имена

&nbsp;• бот учитывает разные варианты написания (ё/е, регистр, пробелы)

&nbsp;• результат стабилен: один участник → один человек



Бот написан на Python + aiogram 3 и готов к использованию на Replit, VDS или любом Python-сервере.





✨ **Возможности**



👑 *Для организатора:*



&nbsp;• команда /newgame создаёт новую игру

&nbsp;• бот ожидает список участников

&nbsp;• имена принимаются построчно:



Юлия Павликова

Евгения Дмитриева

Елена Мещерякова





&nbsp;• бот очищает список, удаляет дубликаты

&nbsp;• автоматически создаёт честное распределение «кто кому дарит»



🎁 *Для участника:*



&nbsp;• пишет /start

&nbsp;• вводит своё имя и фамилию

&nbsp;• получает кнопку «🎁 Получить имя»

&nbsp;• бот сообщает, кому он дарит подарок

&nbsp;• нажимать кнопку можно сколько угодно — результат фиксированный





🧠 **Умная обработка имён**



*Бот нормализует текст:*



&nbsp;• ё = е

&nbsp;• регистр не важен (анГЕлина киСЕЛЕва)

&nbsp;• лишние пробелы не мешают

&nbsp;• принимает русские имена в любом виде



*Пример вводов, которые считаются одним и тем же человеком:*



Ангелина Киселева

ангелина киселЕва

АНГЕЛИНА    КИСЕЛЁВА



🏗 **Архитектура (в двух словах)**



&nbsp;• Game — объект текущей игры (список участников, раздача пар, сессии игроков)

&nbsp;• make\_derangement() — создание перестановки без самопар

&nbsp;• normalize\_name() — умная нормализация имени

&nbsp;• aiogram Router — обработка команд

&nbsp;• один запуск бота = одна игра (как обычный Secret Santa)



🎮 **Команды**



Команда Описание

/start Начать участие

/help Инструкция

/newgame Создать новую игру (только организатор)

/reset Полный сброс игры





🚀 **Как запустить локально**



*1. Установите зависимости*



pip install aiogram==3.4.1 python-dotenv aiohttp aiofiles



*2. Создайте файл .env:*



BOT\_TOKEN=ВАШ\_ТОКЕН



*3. Запустите бота:*



python main.py





📦 **Список файлов репозитория**



main.py

pyproject.toml

.env.example

.gitignore

README.md



.env НЕ публикуется — токен хранится локально.





❤️ **Автор**



Бот разработан для массового использования: корпоративы, школьные группы, университеты, семейные чаты и любые события, где нужен честный и красивый Secret Santa.

Ссылка на бот: https://t.me/santasecretpresentsbot

*Для связи с создателем: @angel\_eugeniya (TELEGRAM)*





❄ Приятного использования!



**ENGLISH:**

🎄 **Secret Santa Telegram Bot**

Telegram bot link: https://t.me/santasecretpresentsbot

**A universal Telegram bot for running the Secret Santa game in companies, teams, university groups, or family chats.
The bot ensures a fair and fully automated gift assignment:**
 • nobody receives themselves
 • each participant gets exactly one recipient
 • the organizer provides the list of participants
 • users enter their own names
 • the bot handles different name spellings (ё/e, case, extra spaces)
 • results are stable: one participant → one fixed recipient

The bot is built with Python + aiogram 3 and can run on Replit, VDS, or any standard Python server.


✨ **Features**

👑 **For organizers**
 • /newgame creates a new Secret Santa game
 • the bot waits for the full participant list
 • names must be sent line-by-line:

Yulia Pavlikova  
Evgeniya Dmitrieva  
Elena Meshcheryakova

 • the bot cleans the list and removes duplicates
 • automatically generates a fair derangement (“who gives to whom”)


🎁 **For participants**
 • send /start
 • enter your first and last name
 • receive the button 🎁 Get recipient
 • the bot tells you who you will give a gift to
 • you may press the button as many times as you want — the result is fixed and does not change


🧠 **Smart name processing**

The bot normalizes text:
 • ё ≡ е
 • letter case does not matter (анГЕлина киСЕЛЕва)
 • extra spaces are ignored
 • Russian names are accepted in any form

Examples that count as the same person:

Ангелина Киселева
ангелина киселЕва
АНГЕЛИНА КИСЕЛЁВА


🏗 **Architecture (in short)**

 • Game — the object that stores participants, assignments, and user sessions
 • make_derangement() — generates a permutation where no one gets themselves
 • normalize_name() — smart name normalization
 • aiogram Router — handles all bot commands
 • one bot run = one Secret Santa game (just like in real life)

⸻

🎮 **Commands**

*Command Description*
/start Join the game
/help Show instructions
/newgame Create a new game (organizer only)
/reset Reset the current game completely


🚀 **How to run locally**

*1. Install dependencies*

pip install aiogram==3.4.1 python-dotenv aiohttp aiofiles

*2. Create .env:*

BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN

*3. Run the bot:*

python main.py


📦 **Repository structure**

main.py  
pyproject.toml  
.env.example  
.gitignore  
README.md

*Important: .env is NOT published — it contains your bot token and must be stored locally.*


❤️ **Author**

This bot was created for wide public use: corporate events, school groups, university teams, family chats, and any gatherings where you need a fair and fun Secret Santa experience.

Bot link: https://t.me/santasecretpresentsbot

*Contact the creator: @angel_eugeniya (Telegram)*


❄ Enjoy your Secret Santa!


