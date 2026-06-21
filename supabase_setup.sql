-- 在 Supabase SQL Editor 中执行此文件
-- 故事档案系统：stories + chapters + story_bible

create table if not exists stories (
  id uuid default gen_random_uuid() primary key,
  name text not null,
  genre text default 'fantasy',   -- 'fantasy' 玄幻 | 'emotional' 情感
  style_notes text default '',    -- 作者风格备注
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists chapters (
  id uuid default gen_random_uuid() primary key,
  story_id uuid references stories(id) on delete cascade not null,
  chapter_number integer not null,
  title text not null default '',
  content_markdown text default '',   -- 公众号全文
  content_xhs text default '',        -- 小红书版本
  context_summary text default '',    -- AI 提炼的200字摘要，用于后续章节上下文
  created_at timestamptz default now(),
  unique(story_id, chapter_number)
);

create table if not exists story_bible (
  id uuid default gen_random_uuid() primary key,
  story_id uuid references stories(id) on delete cascade not null unique,
  characters jsonb default '[]',          -- [{name, role, status, traits}]
  world_notes text default '',            -- 世界观关键词
  ongoing_threads jsonb default '[]',     -- [{thread, status}]
  last_chapter_number integer default 0,
  updated_at timestamptz default now()
);

-- 关闭 RLS，允许 anon key 直接读写（内部系统，无需用户鉴权）
alter table stories disable row level security;
alter table chapters disable row level security;
alter table story_bible disable row level security;
