
# ZhorikBase Anti-Scam Bot

Бұл бот LiarsRobot / LiarsBase логикасына ұқсайтын толық анти-скам база боты.

## Іске қосу

1. Python 3.10+ орнат
2. Виртуалка жаса:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```
3. Тәуелділіктерді орнат:
   ```bash
   pip install -r requirements.txt
   ```
4. `.env` файлын жаса немесе `.env.example` ішіндегі мәндерді көшіріп, келесілерді толтыр:
   ```env
   BOT_TOKEN=your-telegram-bot-token
   ADMIN_IDS=123456789,987654321
   ```
5. Фото file_id алу үшін, ботқа сурет жіберіп, Telegram API арқылы немесе логтан алып, `PHOTO_*` айнымалыларын толтыр.
6. Ботты іске қос:
   ```bash
   python main.py
   ```

## Админ / модератор командалары

- `/admin` — статистика және көмек
- `/addmod 123456789` — модератор қосу
- `/delmod 123456789` — модераторды өшіру
- `/listmods` — модератор тізімі
- `/setstatus @username статус [пруф/коммент]`

Статус мәндері:
- `team` / `команда`
- `guarantor` / `гарант`
- `verified` / `проверенный`
- `unknown` / `неизвестный`
- `doubt` / `сомнительный`
- `scam` / `scammer` / `мошенник`
