# Bale Support Bot — Belmo / Python

این نسخه برای **BELMO → API → Python/Flask** آماده شده است.

در این Repository فقط یک سرویس وجود دارد و همان سرویس همه چیز را اجرا می‌کند:

- وب‌سایت و پنل مدیریت
- ربات بله با Webhook
- تیکت و پشتیبانی انسانی
- FAQ
- Gemini AI و چرخش کلیدها
- مدیریت ادمین‌های بله
- پیام همگانی
- دریافت Backup دیتابیس از سایت یا خود ربات
- بازیابی Backup دیتابیس از سایت یا خود ربات
- ساخت خودکار جدول‌های دیتابیس در اولین اجرا
- Health Check برای Belmo

## ساختار

```text
.
├── app.py
├── wsgi.py
├── requirements.txt
├── runtime.txt
├── Procfile
├── .env.example
├── app/
│   └── __init__.py
├── templates/
└── static/
```

## دیتابیس

بدون هیچ تنظیم اضافی، برنامه دیتابیس SQLite را در این مسیر می‌سازد:

```text
data/support_bot.db
```

و در هر اجرای برنامه `create_all()` اجرا می‌شود؛ بنابراین جدول‌ها خودکار ساخته می‌شوند و نیازی به اجرای migration برای شروع ندارید.

برای PostgreSQL هم پشتیبانی وجود دارد. اگر `DATABASE_URL` تعریف شود، برنامه به جای SQLite از آن استفاده می‌کند و جدول‌ها را باز هم خودش می‌سازد.

## Environment Variables

### ضروری

```text
BALE_BOT_TOKEN=
ADMIN_IDS=
ADMIN_PANEL_USERNAME=admin
ADMIN_PANEL_PASSWORD=
SECRET_KEY=
WEBHOOK_SECRET=
```

### اختیاری / پیشنهادشده

```text
PUBLIC_BASE_URL=
AUTO_REGISTER_WEBHOOK=true
DATABASE_URL=
GEMINI_MODEL=gemini-3.6-flash
GEMINI_API_KEY=
GROUP_CHAT_ID=
BOT_NAME=ربات پشتیبانی
ORGANIZATION_NAME=تیم پشتیبانی
AI_ENABLED=true
WELCOME_MESSAGE=
```

### توضیح متغیرها

| Variable | توضیح |
|---|---|
| `BALE_BOT_TOKEN` | Token ربات بله از BotFather/مدیریت بله |
| `ADMIN_IDS` | شناسه‌های عددی ادمین‌های اصلی، با کاما جدا شوند؛ مثال `123,456` |
| `ADMIN_PANEL_USERNAME` | نام کاربری ورود پنل وب |
| `ADMIN_PANEL_PASSWORD` | رمز ورود پنل وب |
| `SECRET_KEY` | Secret طولانی و تصادفی برای Session وب |
| `WEBHOOK_SECRET` | Secret طولانی و غیرقابل حدس برای URL وبهوک |
| `PUBLIC_BASE_URL` | آدرس عمومی سرویس Belmo؛ در صورت خالی بودن، اولین ورود به پنل آن را از Host درخواست تشخیص می‌دهد |
| `AUTO_REGISTER_WEBHOOK` | اگر `true` باشد، در اولین ورود پنل وبهوک ربات به‌صورت خودکار ثبت/به‌روزرسانی می‌شود |
| `DATABASE_URL` | اختیاری؛ خالی = SQLite خودکار، پر = PostgreSQL |
| `GEMINI_MODEL` | مدل AI؛ پیش‌فرض فعلی `gemini-3.6-flash` |
| `GEMINI_API_KEY` | اختیاری؛ یک کلید Gemini پیش‌فرض. کلیدهای بیشتر را می‌توان داخل پنل ذخیره کرد |
| `GROUP_CHAT_ID` | گروه پشتیبانی برای دریافت اعلان تیکت |
| `BOT_NAME` | نام نمایشی ربات |
| `ORGANIZATION_NAME` | نام مجموعه |
| `AI_ENABLED` | `true` یا `false` |
| `WELCOME_MESSAGE` | متن خوش‌آمد ربات |

## Deploy روی BELMO

1. کل Repository را روی GitHub Push کن.
2. در Belmo یک **API service** بساز و همان Repository را انتخاب کن.
3. Root Directory را روی ریشه Repository بگذار.
4. Belmo از روی `requirements.txt` و `wsgi.py` پروژه Flask را تشخیص می‌دهد.
5. Build را بدون تغییرات خاص اجرا کن.
6. Start را اگر Belmo از `Procfile` استفاده نکرد، این بگذار:

```text
gunicorn -w 2 -k gthread --threads 4 --timeout 120 wsgi:app
```

7. Environment Variables را وارد کن.
8. Deploy را بزن.
9. وقتی URL سرویس ساخته شد، وارد `/admin/login` شو.
10. اگر `PUBLIC_BASE_URL` خالی باشد، برنامه URL عمومی را تشخیص می‌دهد و در صورت فعال بودن `AUTO_REGISTER_WEBHOOK` وبهوک را خودش ثبت می‌کند.

## ورود به پنل

```text
https://YOUR-DOMAIN/admin/login
```

Username/Password همان `ADMIN_PANEL_USERNAME` و `ADMIN_PANEL_PASSWORD` هستند.

## تست سلامت

```text
https://YOUR-DOMAIN/health
```

پاسخ موفق:

```json
{
  "ok": true,
  "database": "ok"
}
```

## Backup / Restore در ربات بله

ادمین در ربات:

```text
🛠 پنل مدیریت
```

سپس:

```text
📦 دریافت دیتابیس
```

ربات یک فایل JSON کامل از اطلاعات دیتابیس می‌فرستد.

برای بازیابی:

```text
📥 ارسال دیتابیس
```

بعد همان فایل JSON را به‌صورت Document برای ربات ارسال کن.

در صورت موفقیت، اطلاعات فعلی دیتابیس با Backup جایگزین می‌شود.

همین Backup از پنل وب نیز از مسیر زیر قابل دانلود است:

```text
/admin/backup
```

## نکات امنیتی

- هیچ Token یا Password را داخل GitHub Commit نکن.
- `BALE_BOT_TOKEN`, `GEMINI_API_KEY`, `DATABASE_URL`, `SECRET_KEY` و Password پنل باید فقط در Environment Variables باشند.
- فایل `data/support_bot.db` داخل `.gitignore` است و نباید Commit شود.
- قبل از Restore، یک Backup جدید بگیر.

## نکته درباره SQLite روی سرویس ابری

SQLite بدون نیاز به دیتابیس خارجی کار می‌کند و خودش ساخته می‌شود، اما اگر سرویس میزبان دیسک دائمی نداشته باشد، برای نگهداری بلندمدت داده‌ها بهتر است `DATABASE_URL` را به یک PostgreSQL مدیریت‌شده وصل کنی. خود برنامه در این حالت جدول‌ها را باز هم خودکار می‌سازد.
