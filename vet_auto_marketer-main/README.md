# Vet_Auto_Marketer 🐾

نظام أتمتة كامل لإدارة حساب Instagram الخاص بـ **عيادة الكوخ البيطرية (ALKOUKH)** في العراق.

يتضمن: نشر تلقائي (Posts / Stories / Reels)، ردود AI طبيعية على DMs والتعليقات بالعربية العراقية، تتبّع ترندات عراقية، توليد صور Nano Banana، ولوحة تحكم ويب للموظفين.

---

## ✨ المميزات

- 🤖 **محتوى بـ AI** — كابشن وردود بالعربية العراقية عبر Claude Sonnet 4.5
- 📅 **نشر مجدول** — Posts + Stories + Reels بـ APScheduler
- 💬 **رد تلقائي** — DMs + التعليقات + DM متابعة للمعلقين
- 🚨 **Emergency detection** — كلمات طوارئ تحوّل الرسالة لرقم العيادة مباشرة
- 🎨 **Nano Banana** — توليد صور tip يومية بالهوية البصرية
- 📈 **تتبع الترندات** — Twitter + fallback لـ trends24.in + قائمة مواضيع بيطرية موسمية
- 🔒 **HMAC webhook verification** — تأمين endpoint استقبال events من Meta
- 🖥️ **Dashboard** — واجهة RTL لرفع/جدولة المحتوى وعرض المحادثات والإحصائيات
- 📊 **تقارير أسبوعية** — Likes, Reach, Impressions, response rates

---

## 🛠️ المتطلبات

| المتطلب | الإصدار |
|--------|---------|
| Python | 3.11+ |
| حساب Instagram Business | مربوط بـ Facebook Page |
| Facebook Developer App | مع صلاحيات `instagram_basic`, `instagram_content_publish`, `instagram_manage_messages`, `instagram_manage_comments`, `pages_messaging` |
| Supabase | مشروع جاهز |
| Anthropic API | مفتاح Claude |
| Nano Banana | مفتاح (اختياري) |
| Twitter Bearer Token | اختياري — يوجد fallback |

---

## 🚀 التثبيت المحلي

```bash
# 1) استنساخ المشروع
git clone <your-repo> Vet_Auto_Marketer
cd Vet_Auto_Marketer

# 2) بيئة افتراضية
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3) تثبيت المكتبات
pip install -r requirements.txt

# 4) إعدادات البيئة
cp .env.example .env
# عدّل .env باللي عندك من مفاتيح
# 👈 خلّي DRY_RUN=true أول مرة للاختبار

# 5) تجهيز قاعدة البيانات
#   افتح Supabase → SQL Editor → الصق محتوى database/schema.sql → Run
#   ثم من Storage → New bucket → اسمه "media" → Public

# 6) التشغيل
uvicorn main:app --reload
# أو:
python main.py
```

الواجهات ستشتغل على:
- `http://localhost:8000/` — root
- `http://localhost:8000/health` — uptime probe
- `http://localhost:8000/dashboard/` — لوحة التحكم
- `http://localhost:8000/docs` — Swagger UI

---

## ☁️ النشر على Railway

```bash
# 1) رفع على GitHub
git init && git add . && git commit -m "Initial"
git remote add origin <your-github-repo>
git push -u origin main

# 2) في Railway
#    - New Project → Deploy from GitHub repo
#    - اختار المشروع
#    - Railway يلاحظ Procfile + railway.json تلقائياً

# 3) إضافة المتغيرات البيئية
#    Variables → أضف كل المتغيرات من .env.example
#    ⚠️  لا تنسَ: DRY_RUN=false عند التشغيل الفعلي

# 4) احصل على URL
#    Settings → Networking → Generate domain
#    سجّل الرابط (مثال: https://vet-auto-marketer.up.railway.app)
#    ضعه في WEBHOOK_PUBLIC_URL
```

### بديل: Docker

```bash
docker build -t vet-auto-marketer .
docker run -p 8000:8000 --env-file .env vet-auto-marketer
```

---

## 🔗 ربط Webhook على Meta

1. افتح **Facebook Developer Console** → Your App → **Webhooks**.
2. اختر **Instagram** من القائمة.
3. **Callback URL**: `https://<your-domain>/webhooks/instagram`
4. **Verify Token**: نفس اللي حطيته في `INSTAGRAM_WEBHOOK_VERIFY_TOKEN`.
5. اضغط **Verify and Save** — لو ضبط، راح يرجع status 200.
6. اشترك على الحقول: `messages`, `comments`, `messaging_postbacks`.

⚠️ **ملاحظة أمنية**: متى ما حطيت `INSTAGRAM_APP_SECRET` في `.env`، النظام تلقائياً يتحقق من HMAC signature على كل webhook. الرسائل بدون signature صحيح → `403`.

---

## 📂 هيكل المشروع

```
Vet_Auto_Marketer/
├── main.py                   # FastAPI + scheduler bootstrap
├── CLAUDE.md                 # دليل المساعدة لـ Claude Code
├── requirements.txt          # dependencies
├── Procfile                  # Railway/Heroku
├── railway.json              # Railway config
├── Dockerfile                # Docker
├── .dockerignore / .gitignore
├── .env.example
│
├── config/
│   ├── settings.py           # Pydantic settings
│   ├── prompts.py            # AI prompts (عربي عراقي)
│   └── schedule.py           # جدولة النشر
│
├── agents/
│   ├── publisher_agent.py    # نشر المحتوى + analytics
│   ├── reply_agent.py        # DMs + تعليقات
│   ├── trend_agent.py        # استغلال الترندات
│   └── content_agent.py      # تحضير المحتوى
│
├── modules/
│   ├── instagram_api.py      # Graph API
│   ├── ai_generator.py       # Anthropic Claude
│   ├── media_processor.py    # Pillow + Supabase Storage
│   ├── trend_tracker.py      # Twitter + trends24 + seasonal
│   ├── nano_banana.py        # توليد صور AI
│   └── scheduler.py          # APScheduler
│
├── database/
│   ├── schema.sql            # جداول Supabase
│   ├── supabase_client.py
│   ├── content_queue.py      # DAO
│   └── analytics.py
│
├── dashboard/
│   ├── routes.py             # APIRouter
│   └── templates/            # HTML RTL + Tailwind-like
│
├── content/
│   ├── uploads/              # يرفع فيه الموظف
│   ├── nano_banana/          # صور مولّدة
│   └── generated/            # معالجة
└── logs/
```

---

## 🌐 Endpoints

### Public API
| Method | Path | الوصف |
|--------|------|-------|
| GET  | `/` | معلومات أساسية |
| GET  | `/health` | uptime probe |
| GET  | `/docs` | Swagger UI |

### Webhooks (تُستدعى من Meta)
| Method | Path | الوصف |
|--------|------|-------|
| GET  | `/webhooks/instagram` | verification challenge |
| POST | `/webhooks/instagram` | استقبال events (HMAC-verified) |

### Dashboard
| Method | Path | الوصف |
|--------|------|-------|
| GET  | `/dashboard/` | الرئيسية |
| GET  | `/dashboard/upload` | صفحة الرفع |
| POST | `/dashboard/upload` | رفع ملف + enqueue |
| GET  | `/dashboard/queue` | قائمة المجدول |
| DELETE | `/dashboard/queue/{id}` | إلغاء بوست |
| GET  | `/dashboard/conversations` | DMs الأخيرة |
| GET  | `/dashboard/analytics` | تقرير الأسبوع |
| GET  | `/dashboard/stats` | JSON counts |

---

## 🔐 تأمين الـ Dashboard

الـ dashboard **غير مؤمّن افتراضياً** — عرض مباشر بدون login. قبل ما تشاركه علنياً:
- ضعه خلف **Basic Auth** عبر middleware.
- قيّد الوصول عبر **IP allowlist** في Railway/Cloudflare.
- أو حطه على **VPN** داخلي.

مثال Basic Auth بسيط يمكن إضافته في `main.py` لاحقاً (TODO).

---

## 🧪 الاختبار السريع

```bash
# فحص الصحة
curl http://localhost:8000/health

# محاكاة webhook verification
curl "http://localhost:8000/webhooks/instagram?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=42"

# دخول Dashboard
open http://localhost:8000/dashboard/
```

### اختبار الوحدات

```bash
python -m modules.ai_generator        # caption demo
python -m database.supabase_client    # DB ping
python -m modules.nano_banana         # image gen
```

---

## ⚠️ ملاحظات مهمة

- `DRY_RUN=true` = النظام يشتغل كامل بدون نشر فعلي. ممتاز للتجربة.
- الـ Access Token طويل المدى ينتهي كل 60 يوم — **جدّده** من Graph API Explorer.
- أي DM من الحساب للحساب نفسه يُتجاهل تلقائياً (منع حلقة الرد).
- Meta تطلب استجابة `200 OK` خلال 20 ثانية — النظام يرد فوراً ويعالج في background.

---

## 📞 الدعم

- راجع [CLAUDE.md](CLAUDE.md) لقواعد العمل والهوية.
- المشاكل؟ افتح issue على GitHub.
