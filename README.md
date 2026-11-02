# ایجنت انتشار خودکار اینستاگرام (اجرا روی GitHub Actions، بدون نصب هیچ برنامه‌ای)

همه‌چیز روی سرور رایگان GitHub اجرا می‌شود و تو فقط با مرورگر کنترلش می‌کنی.
مسیر کار: ایده و کپشن (Claude) ← تولید تصویر (OpenAI) ← کنترل کیفیت (Claude) ← تأیید تو ← زمان‌بندی ← انتشار با Graph API رسمی.

## چیزهایی که لازم داری

1. حساب GitHub (رایگان) — github.com
2. کلید API از Anthropic (console.anthropic.com) و از OpenAI (platform.openai.com). اشتراک ChatGPT شامل API نیست؛ API جداست و اعتبار پرداختی می‌خواهد.
3. اکانت اینستاگرام Professional (Business یا Creator) و یک اپ در developers.facebook.com با دسترسی انتشار:
   - لاگین اینستاگرام: `instagram_business_basic` و `instagram_business_content_publish` (در فایل agent.yml مقدار GRAPH_HOST را `https://graph.instagram.com` کن)
   - لاگین فیسبوک: `instagram_basic`، `instagram_content_publish` و `pages_read_engagement`
   - از اپ، `IG_USER_ID` و توکن دسترسی را بگیر. تاریخ انقضای توکن را یادداشت کن.

## راه‌اندازی (همه در مرورگر)

**۱. فایل‌ها را آماده کن:** فایل zip را در ویندوز راست‌کلیک ← Extract All کن.

**۲. مخزن بساز:** در GitHub روی New repository بزن، یک اسم بده (مثلاً `ig-agent`)، گزینه‌ی **Public** را انتخاب کن و Create بزن. (باید Public باشد تا اینستاگرام بتواند عکس‌ها را دانلود کند و Actions هم برایش رایگان باشد.)

**۳. فایل‌ها را آپلود کن:** در صفحه‌ی مخزن روی «uploading an existing file» بزن و همه‌ی فایل‌ها و پوشه‌های **داخل** پوشه‌ی بازشده را بکش و رها کن، بعد Commit changes.
بعد از آپلود چک کن فایل `.github/workflows/agent.yml` هست. اگر نیست: Add file ← Create new file، اسم را دقیقاً `.github/workflows/agent.yml` بنویس و محتوای فایل را داخلش paste کن.

**۴. کلیدها را بگذار:** Settings ← Secrets and variables ← Actions ← New repository secret، چهار تا با همین اسم‌ها:
`ANTHROPIC_API_KEY`، `OPENAI_API_KEY`، `IG_USER_ID`، `IG_ACCESS_TOKEN`

**۵. شخصیت پیج را تنظیم کن:** فایل `persona.json` را با آیکن مداد در GitHub ویرایش کن (نام، ظاهر، علایق، زبان کپشن، timezone، ساعت‌های فعال).

**۶. اولین اجرا (تست بدون انتشار):** در فایل `.github/workflows/agent.yml` مقدار `DRY_RUN` را موقتاً `"true"` کن. بعد تب Actions ← instagram-agent (اگر خواست Enable کن) ← Run workflow ← در کادر command بنویس `generate -n 3`.
بعد از چند دقیقه فایل `REVIEW.md` در مخزن عکس‌ها و کپشن‌ها را نشان می‌دهد.

**۷. تأیید و اولین انتشار واقعی:** Run workflow با `approve --all` (یا `approve 1 2` و `reject 3`). بعد `DRY_RUN` را به `"false"` برگردان و Run workflow با `publish-now`. اگر پست روی اینستاگرام آمد، کار تمام است.

از اینجا به بعد خودش هر ۳۰ دقیقه اجرا می‌شود: اگر وقت انتشار باشد پست می‌گذارد و بافر پست‌های جدید را پر نگه می‌دارد. هر چند وقت یک بار `REVIEW.md` را ببین و تأیید کن. اگر به کیفیت اعتماد کردی، `REQUIRE_APPROVAL` را در agent.yml روی `"false"` بگذار.

## دستورها (در کادر command)

| دستور | کار |
|---|---|
| `tick` | کار عادی (خودکار هر ۳۰ دقیقه) |
| `generate -n 3` | ساخت ۳ پست جدید |
| `approve --all` / `approve 3 4` | تأیید پست‌ها |
| `reject 5` | رد پست |
| `publish-now` | انتشار فوری یک پست تأییدشده |
| `status` | وضعیت صف و سهمیه (در لاگ اجرا) |

## مقیاس‌دهی

تعداد پست در روز در `persona.json ← schedule.ramp` است: ۱ در روز ← ۲ از روز ۷ ← ۳ از روز ۲۱ ← ۵ از روز ۴۵. فقط وقتی آمار (ریچ، ذخیره، فالوور) بعد از هر افزایش افت نکرد بالاتر برو. سقف انتشار اکانت را کد زنده از خود API می‌خواند.

## نکات مهم

- **عمومی بودن:** چون مخزن Public است، `persona.json`، کپشن‌ها و عکس‌ها برای همه قابل دیدن است (کلیدها در Secrets امن‌اند و دیده نمی‌شوند).
- **۶۰ روز:** GitHub در مخزن‌های عمومی اجرای زمان‌بندی‌شده را بعد از ۶۰ روز بدون هیچ فعالیتی خاموش می‌کند. کامیت‌های روزانه‌ی خود ایجنت معمولاً این را جلو می‌اندازد، ولی اگر یک‌وقت اجرا قطع شد، تب Actions ← Enable workflow.
- **تأخیر:** اجراهای زمان‌بندی‌شده‌ی GitHub گاهی چند دقیقه دیر می‌شوند؛ برای پست روزانه مشکلی نیست.
- **توکن اینستاگرام:** منقضی می‌شود. اگر انتشار ناگهان خطای توکن داد، توکن جدید بگیر و Secret را عوض کن.
- **برچسب AI** به‌صورت پیش‌فرض روی هر پست فعال است (`AI_DISCLOSURE`).
- **هاست جایگزین:** اگر اینستاگرام عکس را از آدرس GitHub قبول نکرد، به‌جایش `STORAGE: s3` و تنظیمات `S3_*` (مثلاً Cloudflare R2) را در agent.yml بگذار؛ توضیح متغیرها در `.env.example` است.
- **اجرای محلی** (اگر یک روز کامپیوتر بهتری داشتی): `pip install -r requirements.txt` و `python agent.py status`.
