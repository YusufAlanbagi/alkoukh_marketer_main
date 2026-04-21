-- ============================================================
-- Vet_Auto_Marketer — Supabase schema
-- Run this in the Supabase SQL Editor (once).
-- ============================================================

-- ------------------------------------------------------------
-- content_queue
-- ------------------------------------------------------------
create table if not exists public.content_queue (
    id                  bigserial primary key,
    type                text not null check (type in ('post','story','reel')),
    status              text not null default 'ready_for_manual_post'
                         check (status in ('pending','ready_for_manual_post','marked_as_posted','failed','skipped')),
    content_type        text not null check (content_type in ('owner','nano_banana','trend','generated')),
    media_url           text,
    media_path          text,
    image_local_path    text,
    image_public_url    text,
    caption             text,
    hashtags            text,
    scheduled_at        timestamptz,
    published_at        timestamptz,
    content_posted_at   timestamptz,
    instagram_post_id   text,
    permalink           text,
    error_message       text,
    metadata            jsonb default '{}'::jsonb,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);

create index if not exists idx_cq_status_sched on public.content_queue (status, scheduled_at);
create index if not exists idx_cq_content_type on public.content_queue (content_type);

-- ------------------------------------------------------------
-- trends_log
-- ------------------------------------------------------------
create table if not exists public.trends_log (
    id                bigserial primary key,
    trend_topic       text not null,
    trend_volume      bigint,
    trend_type        text,
    relevance_score   int,
    relevant          boolean,
    content_created   boolean not null default false,
    queue_id          bigint references public.content_queue(id) on delete set null,
    reason            text,
    detected_at       timestamptz not null default now()
);

-- ------------------------------------------------------------
-- analytics
-- ------------------------------------------------------------
create table if not exists public.analytics (
    id              bigserial primary key,
    date            date not null,
    instagram_post_id text,
    queue_id        bigint references public.content_queue(id) on delete set null,
    likes           int default 0,
    comments        int default 0,
    shares          int default 0,
    saves           int default 0,
    reach           int default 0,
    impressions     int default 0,
    dm_responses    int default 0,
    response_rate   numeric(5,2),
    captured_at     timestamptz not null default now()
);

create index if not exists idx_analytics_date on public.analytics (date);

-- ------------------------------------------------------------
-- Trigger: updated_at
-- ------------------------------------------------------------
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end $$;

drop trigger if exists trg_touch_cq on public.content_queue;
create trigger trg_touch_cq before update on public.content_queue
    for each row execute function public.touch_updated_at();
