# CLAUDE.md — Vet_Auto_Marketer

Instagram automation system for **عيادة الكوخ البيطرية (ALKOUKH Veterinary Clinic)** in Iraq.

## Project Purpose
Full-stack AI automation for the clinic's Instagram presence:
- Auto-publishing Posts, Stories, Reels (owner uploads + Nano-Banana designs + trend-based content)
- Auto-replying to DMs and comments in natural Iraqi Arabic
- Tracking Iraqi trends and producing relevant clinic content
- Analytics logging and reporting

## Stack
- Python 3.11+
- Anthropic Claude (claude-opus-4-7) for caption/reply generation
- Supabase (Postgres) for content queue, conversations, analytics
- Instagram Graph API for publishing + messaging
- APScheduler for timed jobs
- FastAPI for the webhook receiver

## Entry Point
`python main.py` — starts scheduler + webhook server together.

## Brand Voice Rules (CRITICAL)
- **Language:** Iraqi Arabic (عامية عراقية طبيعية), not MSA.
- **Tone:** warm, professional, friendly — never robotic, never reveal AI.
- **Colors (brand):** purple + white + purple→pink gradient. Refer to tone/feeling, not literal hex codes in captions.
- **Fixed hashtags:** `#الكوخ #عيادة_الكوخ #بيطري_العراق #ALKOUKH`
- **Medical safety:** never give specific medical advice; always recommend a clinic visit. Emergencies → clinic phone immediately.

## Directory Map
```
config/      — settings, prompts, posting schedule
agents/      — high-level orchestrators (publisher, reply, trend, content)
modules/     — IG API, AI, media, trend-tracking, scheduler
database/    — Supabase client + domain tables
content/     — uploads/, nano_banana/, generated/
main.py      — boot
```

## Content Types
1. **Owner Content** — uploaded media, AI writes caption.
2. **Nano-Banana Content** — branded templates, AI writes caption.
3. **Trend Content** — AI checks Iraqi trends, generates if relevant.

## DM/Comment Rules
- Reply must sound human (never admit to being AI).
- Pricing → ask to contact directly.
- Emergency keywords → respond with clinic phone immediately.
- Vet questions → general answer + suggest clinic visit.

## Before Editing
- Check `.env` (never commit it).
- Test with `DRY_RUN=true` before hitting real IG APIs.
- All new features MUST have try/except + loguru logging.
