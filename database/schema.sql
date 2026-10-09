-- RuffNeck Prospector - Expanded Schema (Free-tier friendly)
-- Run this in Supabase SQL Editor

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- for text search

-- Prospects (multi-platform)
CREATE TABLE IF NOT EXISTS prospects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    platform TEXT NOT NULL CHECK (platform IN ('instagram', 'twitter', 'reddit', 'youtube', 'tiktok', 'linkedin', 'other')),
    username TEXT NOT NULL,
    display_name TEXT,
    profile_url TEXT,
    comment_text TEXT,
    comment_url TEXT,
    post_url TEXT,
    post_caption TEXT,
    follower_count INT DEFAULT 0,
    following_count INT DEFAULT 0,
    post_count INT DEFAULT 0,
    bio_text TEXT,
    location TEXT,
    is_verified BOOLEAN DEFAULT FALSE,
    engagement_score FLOAT DEFAULT 0,          -- likes + replies + etc normalized
    intent_score INT DEFAULT 0 CHECK (intent_score >= 0 AND intent_score <= 100),
    score_reason TEXT,
    tags TEXT[] DEFAULT '{}',
    email TEXT,
    email_verified BOOLEAN DEFAULT FALSE,
    email_confidence INT DEFAULT 0,
    phone TEXT,
    website TEXT,
    lawful_basis TEXT DEFAULT 'legitimate_interest',
    data_source TEXT DEFAULT 'public_comment',
    last_contacted_at TIMESTAMPTZ,
    unsubscribed BOOLEAN DEFAULT FALSE,
    status TEXT DEFAULT 'new' CHECK (status IN ('new', 'scored', 'enriched', 'contacted', 'replied', 'converted', 'archived')),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_prospects_platform ON prospects(platform);
CREATE INDEX idx_prospects_intent ON prospects(intent_score DESC);
CREATE INDEX idx_prospects_username ON prospects(username);
CREATE INDEX idx_prospects_created ON prospects(created_at DESC);
CREATE INDEX idx_prospects_status ON prospects(status);
CREATE INDEX idx_prospects_tags ON prospects USING GIN(tags);

-- Campaigns
CREATE TABLE IF NOT EXISTS campaigns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    niche TEXT,
    platform_filter TEXT[],
    min_intent_score INT DEFAULT 50,
    template_id UUID,
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'paused', 'completed')),
    sent_count INT DEFAULT 0,
    open_count INT DEFAULT 0,
    reply_count INT DEFAULT 0,
    open_rate FLOAT DEFAULT 0,
    reply_rate FLOAT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Assets (ebooks, slides, etc.)
CREATE TABLE IF NOT EXISTS assets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    prospect_id UUID REFERENCES prospects(id) ON DELETE SET NULL,
    campaign_id UUID REFERENCES campaigns(id) ON DELETE SET NULL,
    asset_type TEXT NOT NULL CHECK (asset_type IN ('ebook', 'slides', 'one_pager', 'checklist', 'email_sequence')),
    topic TEXT NOT NULL,
    title TEXT,
    file_url TEXT,
    file_size_bytes INT,
    branding JSONB DEFAULT '{}',
    generated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Outreach logs
CREATE TABLE IF NOT EXISTS outreach_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    prospect_id UUID REFERENCES prospects(id) ON DELETE CASCADE,
    campaign_id UUID REFERENCES campaigns(id) ON DELETE SET NULL,
    channel TEXT NOT NULL CHECK (channel IN ('email', 'dm', 'comment_reply', 'other')),
    message_text TEXT,
    subject_line TEXT,
    status TEXT DEFAULT 'queued' CHECK (status IN ('queued', 'sent', 'delivered', 'opened', 'replied', 'bounced', 'failed', 'unsubscribed')),
    provider_message_id TEXT,
    error_message TEXT,
    sent_at TIMESTAMPTZ,
    opened_at TIMESTAMPTZ,
    replied_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Outreach templates
CREATE TABLE IF NOT EXISTS outreach_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    channel TEXT NOT NULL,
    subject_line TEXT,
    body_template TEXT NOT NULL,
    variables TEXT[] DEFAULT '{}', -- e.g. ['username', 'comment_snippet', 'topic']
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Audit / compliance logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID,
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id UUID,
    details JSONB DEFAULT '{}',
    ip_address INET,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Scraping jobs (for async tracking)
CREATE TABLE IF NOT EXISTS scrape_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    platform TEXT NOT NULL,
    target_url TEXT NOT NULL,
    keywords TEXT[],
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    celery_task_id TEXT,
    results_count INT DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Auto-purge old non-contacted prospects (GDPR / data minimization - 90 days)
CREATE OR REPLACE FUNCTION purge_old_prospects()
RETURNS trigger AS $$
BEGIN
    DELETE FROM prospects
    WHERE created_at < NOW() - INTERVAL '90 days'
      AND last_contacted_at IS NULL
      AND status IN ('new', 'scored', 'archived');
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS purge_prospects_trigger ON prospects;
CREATE TRIGGER purge_prospects_trigger
AFTER INSERT ON prospects
EXECUTE FUNCTION purge_old_prospects();

-- Updated_at trigger helper
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER prospects_updated_at
BEFORE UPDATE ON prospects
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER campaigns_updated_at
BEFORE UPDATE ON campaigns
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Seed a couple of default templates
INSERT INTO outreach_templates (name, channel, subject_line, body_template, variables) VALUES
(
    'Free Mini-Guide Offer',
    'email',
    'Quick resource based on your comment about {{topic}}',
    'Hi {{username}},

I saw your comment on {{platform}}: "{{comment_snippet}}"

I put together a short free mini-guide on {{topic}} that a lot of people in your position find useful.

Would you like me to send it over? Just reply "yes" and I''ll share the link.

No strings attached.

Best,
{{sender_name}}

---
Reply STOP to unsubscribe.',
    ARRAY['username', 'platform', 'comment_snippet', 'topic', 'sender_name']
),
(
    'Soft DM Opener',
    'dm',
    NULL,
    'Hey {{username}} — loved your take: "{{comment_snippet}}". 

I made a free 1-pager on {{topic}} if you want it. Happy to drop it here.',
    ARRAY['username', 'comment_snippet', 'topic']
);

COMMENT ON TABLE prospects IS 'Multi-platform social prospects extracted from public comments/posts';
COMMENT ON COLUMN prospects.lawful_basis IS 'GDPR/NDPR lawful basis for processing';
COMMENT ON COLUMN prospects.intent_score IS 'AI-generated intent score 0-100';

-- Pipeline stages (also stored on prospects.status for simplicity)
-- new → contacted → replied → meeting → won → lost

-- Replies / conversation log
CREATE TABLE IF NOT EXISTS replies (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  prospect_id UUID REFERENCES prospects(id) ON DELETE CASCADE,
  channel TEXT DEFAULT 'email',          -- email, linkedin, whatsapp, call
  direction TEXT DEFAULT 'inbound',      -- inbound / outbound
  subject TEXT,
  body TEXT,
  received_at TIMESTAMPTZ DEFAULT NOW(),
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_replies_prospect ON replies(prospect_id);

-- Sequences (multi-step)
CREATE TABLE IF NOT EXISTS sequences (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL,
  description TEXT,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sequence_steps (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  sequence_id UUID REFERENCES sequences(id) ON DELETE CASCADE,
  step_order INT NOT NULL,
  channel TEXT DEFAULT 'email',
  delay_days INT DEFAULT 0,
  subject_template TEXT,
  body_template TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sequence_enrollments (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  sequence_id UUID REFERENCES sequences(id) ON DELETE CASCADE,
  prospect_id UUID REFERENCES prospects(id) ON DELETE CASCADE,
  current_step INT DEFAULT 0,
  status TEXT DEFAULT 'active',  -- active, paused, completed, replied
  last_sent_at TIMESTAMPTZ,
  next_send_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(sequence_id, prospect_id)
);

-- Simple analytics helper view
CREATE OR REPLACE VIEW prospect_stats AS
SELECT
  COUNT(*) AS total_prospects,
  COUNT(*) FILTER (WHERE email IS NOT NULL) AS with_email,
  COUNT(*) FILTER (WHERE intent_score >= 70) AS high_intent,
  COUNT(*) FILTER (WHERE status = 'replied') AS replied,
  COUNT(*) FILTER (WHERE status = 'won') AS won,
  COUNT(*) FILTER (WHERE platform = 'maps') AS from_maps,
  COUNT(*) FILTER (WHERE platform = 'linkedin') AS from_linkedin,
  COUNT(*) FILTER (WHERE platform = 'jobs') AS from_jobs
FROM prospects;

-- ========== Team / Shared Workspace Support ==========
CREATE TABLE IF NOT EXISTS workspaces (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL,
  slug TEXT UNIQUE,
  owner_id UUID,  -- references auth.users when using Supabase Auth
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workspace_members (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id UUID,           -- Supabase auth.users id
  email TEXT,             -- for invite-by-email before auth
  role TEXT DEFAULT 'member',  -- owner, admin, member
  status TEXT DEFAULT 'active', -- active, invited, removed
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(workspace_id, email)
);

-- Add workspace_id to core tables (nullable for backward compatibility)
ALTER TABLE prospects ADD COLUMN IF NOT EXISTS workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL;
ALTER TABLE sequences ADD COLUMN IF NOT EXISTS workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL;
ALTER TABLE replies ADD COLUMN IF NOT EXISTS workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_prospects_workspace ON prospects(workspace_id);
CREATE INDEX IF NOT EXISTS idx_sequences_workspace ON sequences(workspace_id);

-- Simple helper: default personal workspace can be created per user on first login

-- ========== Row Level Security (RLS) ==========
-- Enable RLS on core tables
ALTER TABLE prospects ENABLE ROW LEVEL SECURITY;
ALTER TABLE sequences ENABLE ROW LEVEL SECURITY;
ALTER TABLE sequence_steps ENABLE ROW LEVEL SECURITY;
ALTER TABLE sequence_enrollments ENABLE ROW LEVEL SECURITY;
ALTER TABLE replies ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspace_members ENABLE ROW LEVEL SECURITY;

-- Helper: check if current user is member of a workspace
CREATE OR REPLACE FUNCTION is_workspace_member(ws_id UUID)
RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM workspace_members
    WHERE workspace_id = ws_id
      AND (
        user_id = auth.uid()
        OR email = (SELECT email FROM auth.users WHERE id = auth.uid())
      )
      AND status = 'active'
  );
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- Workspaces: members can see their workspaces
CREATE POLICY "workspaces_select_member"
  ON workspaces FOR SELECT
  USING (
    id IN (
      SELECT workspace_id FROM workspace_members
      WHERE (user_id = auth.uid() OR email = (SELECT email FROM auth.users WHERE id = auth.uid()))
        AND status = 'active'
    )
  );

CREATE POLICY "workspaces_insert_authenticated"
  ON workspaces FOR INSERT
  WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "workspaces_update_owner"
  ON workspaces FOR UPDATE
  USING (
    id IN (
      SELECT workspace_id FROM workspace_members
      WHERE (user_id = auth.uid() OR email = (SELECT email FROM auth.users WHERE id = auth.uid()))
        AND role IN ('owner', 'admin')
        AND status = 'active'
    )
  );

-- Workspace members
CREATE POLICY "workspace_members_select"
  ON workspace_members FOR SELECT
  USING (is_workspace_member(workspace_id) OR auth.uid() IS NOT NULL);

CREATE POLICY "workspace_members_insert"
  ON workspace_members FOR INSERT
  WITH CHECK (auth.uid() IS NOT NULL);

-- Prospects: visible if in a workspace the user belongs to, OR workspace_id is null (legacy/personal)
CREATE POLICY "prospects_select"
  ON prospects FOR SELECT
  USING (
    workspace_id IS NULL
    OR is_workspace_member(workspace_id)
  );

CREATE POLICY "prospects_insert"
  ON prospects FOR INSERT
  WITH CHECK (
    workspace_id IS NULL
    OR is_workspace_member(workspace_id)
  );

CREATE POLICY "prospects_update"
  ON prospects FOR UPDATE
  USING (
    workspace_id IS NULL
    OR is_workspace_member(workspace_id)
  );

CREATE POLICY "prospects_delete"
  ON prospects FOR DELETE
  USING (
    workspace_id IS NULL
    OR is_workspace_member(workspace_id)
  );

-- Sequences
CREATE POLICY "sequences_select"
  ON sequences FOR SELECT
  USING (
    workspace_id IS NULL
    OR is_workspace_member(workspace_id)
  );

CREATE POLICY "sequences_insert"
  ON sequences FOR INSERT
  WITH CHECK (
    workspace_id IS NULL
    OR is_workspace_member(workspace_id)
  );

CREATE POLICY "sequences_update"
  ON sequences FOR UPDATE
  USING (
    workspace_id IS NULL
    OR is_workspace_member(workspace_id)
  );

-- Sequence steps (inherit via sequence)
CREATE POLICY "sequence_steps_all"
  ON sequence_steps FOR ALL
  USING (
    sequence_id IN (
      SELECT id FROM sequences
      WHERE workspace_id IS NULL OR is_workspace_member(workspace_id)
    )
  );

-- Enrollments
CREATE POLICY "enrollments_all"
  ON sequence_enrollments FOR ALL
  USING (
    sequence_id IN (
      SELECT id FROM sequences
      WHERE workspace_id IS NULL OR is_workspace_member(workspace_id)
    )
  );

-- Replies
CREATE POLICY "replies_all"
  ON replies FOR ALL
  USING (
    workspace_id IS NULL
    OR is_workspace_member(workspace_id)
    OR prospect_id IN (
      SELECT id FROM prospects
      WHERE workspace_id IS NULL OR is_workspace_member(workspace_id)
    )
  );

-- NOTE:
-- 1. Service-role key (used by backend Celery/FastAPI) bypasses RLS.
-- 2. For frontend direct Supabase access, use the anon key + user JWT.
-- 3. Legacy rows with workspace_id IS NULL remain visible (personal/default).
-- 4. After running this SQL, test with a non-service-role client.

-- ========== Activity Timeline ==========
CREATE TABLE IF NOT EXISTS prospect_activities (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  prospect_id UUID REFERENCES prospects(id) ON DELETE CASCADE,
  workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL,
  activity_type TEXT NOT NULL,  -- discovered, enriched, emailed, replied, stage_changed, note, verified, enrolled
  title TEXT,
  body TEXT,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_activities_prospect ON prospect_activities(prospect_id);
CREATE INDEX IF NOT EXISTS idx_activities_created ON prospect_activities(created_at DESC);

-- Suppression / unsubscribe list
CREATE TABLE IF NOT EXISTS suppressions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  email TEXT UNIQUE NOT NULL,
  reason TEXT DEFAULT 'unsubscribe',
  source TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Lead assignment (team member email or user id)
ALTER TABLE prospects ADD COLUMN IF NOT EXISTS assigned_to TEXT;
CREATE INDEX IF NOT EXISTS idx_prospects_assigned ON prospects(assigned_to);

-- ========== Notifications ==========
CREATE TABLE IF NOT EXISTS notifications (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
  user_email TEXT,  -- optional target; null = workspace-wide
  type TEXT NOT NULL,  -- high_score_lead, positive_reply, sequence_sent, system
  title TEXT NOT NULL,
  body TEXT,
  prospect_id UUID REFERENCES prospects(id) ON DELETE SET NULL,
  read BOOLEAN DEFAULT false,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(read);

-- Assets library (ebooks, implementation guides)
CREATE TABLE IF NOT EXISTS assets (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  prospect_id UUID REFERENCES prospects(id) ON DELETE SET NULL,
  workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL,
  asset_type TEXT NOT NULL,  -- ebook, implementation_guide, slides
  title TEXT,
  file_path TEXT,
  file_name TEXT,
  branding JSONB DEFAULT '{}',
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_assets_created ON assets(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_assets_prospect ON assets(prospect_id);
