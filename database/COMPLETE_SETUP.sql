-- RuffNeck Prospector — COMPLETE database setup (one run)
-- Use this if prospects table does not exist yet.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ========== Prospects ==========
CREATE TABLE IF NOT EXISTS prospects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    platform TEXT NOT NULL,
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
    engagement_score FLOAT DEFAULT 0,
    intent_score INT DEFAULT 0,
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
    status TEXT DEFAULT 'new',
    metadata JSONB DEFAULT '{}',
    assigned_to TEXT,
    workspace_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prospects_platform ON prospects(platform);
CREATE INDEX IF NOT EXISTS idx_prospects_intent ON prospects(intent_score DESC);
CREATE INDEX IF NOT EXISTS idx_prospects_username ON prospects(username);
CREATE INDEX IF NOT EXISTS idx_prospects_created ON prospects(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_prospects_status ON prospects(status);

-- ========== Campaigns ==========
CREATE TABLE IF NOT EXISTS campaigns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    niche TEXT,
    platform_filter TEXT[],
    min_intent_score INT DEFAULT 50,
    status TEXT DEFAULT 'draft',
    sent_count INT DEFAULT 0,
    open_count INT DEFAULT 0,
    reply_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========== Workspaces ==========
CREATE TABLE IF NOT EXISTS workspaces (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL,
  slug TEXT UNIQUE,
  owner_id UUID,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workspace_members (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id UUID,
  email TEXT,
  role TEXT DEFAULT 'member',
  status TEXT DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(workspace_id, email)
);

ALTER TABLE prospects DROP CONSTRAINT IF EXISTS prospects_workspace_id_fkey;
ALTER TABLE prospects
  ADD CONSTRAINT prospects_workspace_id_fkey
  FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE SET NULL;

-- ========== Sequences ==========
CREATE TABLE IF NOT EXISTS sequences (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL,
  description TEXT,
  is_active BOOLEAN DEFAULT true,
  workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL,
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
  status TEXT DEFAULT 'active',
  last_sent_at TIMESTAMPTZ,
  next_send_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(sequence_id, prospect_id)
);

-- ========== Replies ==========
CREATE TABLE IF NOT EXISTS replies (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  prospect_id UUID REFERENCES prospects(id) ON DELETE CASCADE,
  channel TEXT DEFAULT 'email',
  direction TEXT DEFAULT 'inbound',
  subject TEXT,
  body TEXT,
  received_at TIMESTAMPTZ DEFAULT NOW(),
  metadata JSONB DEFAULT '{}',
  workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_replies_prospect ON replies(prospect_id);

-- ========== Activities ==========
CREATE TABLE IF NOT EXISTS prospect_activities (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  prospect_id UUID REFERENCES prospects(id) ON DELETE CASCADE,
  workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL,
  activity_type TEXT NOT NULL,
  title TEXT,
  body TEXT,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========== Suppressions ==========
CREATE TABLE IF NOT EXISTS suppressions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  email TEXT UNIQUE NOT NULL,
  reason TEXT DEFAULT 'unsubscribe',
  source TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========== Notifications ==========
CREATE TABLE IF NOT EXISTS notifications (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
  user_email TEXT,
  type TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT,
  prospect_id UUID REFERENCES prospects(id) ON DELETE SET NULL,
  read BOOLEAN DEFAULT false,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========== Assets ==========
CREATE TABLE IF NOT EXISTS assets (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  prospect_id UUID REFERENCES prospects(id) ON DELETE SET NULL,
  workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL,
  asset_type TEXT NOT NULL,
  title TEXT,
  file_path TEXT,
  file_name TEXT,
  branding JSONB DEFAULT '{}',
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========== Outreach logs (optional) ==========
CREATE TABLE IF NOT EXISTS outreach_logs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  prospect_id UUID REFERENCES prospects(id) ON DELETE CASCADE,
  channel TEXT,
  subject TEXT,
  body TEXT,
  status TEXT,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========== Helper ==========
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

-- ========== RLS ==========
ALTER TABLE prospects ENABLE ROW LEVEL SECURITY;
ALTER TABLE sequences ENABLE ROW LEVEL SECURITY;
ALTER TABLE sequence_steps ENABLE ROW LEVEL SECURITY;
ALTER TABLE sequence_enrollments ENABLE ROW LEVEL SECURITY;
ALTER TABLE replies ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspace_members ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "workspaces_select_member" ON workspaces;
DROP POLICY IF EXISTS "workspaces_insert_authenticated" ON workspaces;
DROP POLICY IF EXISTS "workspaces_update_owner" ON workspaces;
DROP POLICY IF EXISTS "workspace_members_select" ON workspace_members;
DROP POLICY IF EXISTS "workspace_members_insert" ON workspace_members;
DROP POLICY IF EXISTS "prospects_select" ON prospects;
DROP POLICY IF EXISTS "prospects_insert" ON prospects;
DROP POLICY IF EXISTS "prospects_update" ON prospects;
DROP POLICY IF EXISTS "prospects_delete" ON prospects;
DROP POLICY IF EXISTS "sequences_select" ON sequences;
DROP POLICY IF EXISTS "sequences_insert" ON sequences;
DROP POLICY IF EXISTS "sequences_update" ON sequences;
DROP POLICY IF EXISTS "sequence_steps_all" ON sequence_steps;
DROP POLICY IF EXISTS "enrollments_all" ON sequence_enrollments;
DROP POLICY IF EXISTS "replies_all" ON replies;

CREATE POLICY "workspaces_select_member" ON workspaces FOR SELECT
  USING (
    id IN (
      SELECT workspace_id FROM workspace_members
      WHERE (user_id = auth.uid() OR email = (SELECT email FROM auth.users WHERE id = auth.uid()))
        AND status = 'active'
    )
  );

CREATE POLICY "workspaces_insert_authenticated" ON workspaces FOR INSERT
  WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "workspaces_update_owner" ON workspaces FOR UPDATE
  USING (
    id IN (
      SELECT workspace_id FROM workspace_members
      WHERE (user_id = auth.uid() OR email = (SELECT email FROM auth.users WHERE id = auth.uid()))
        AND role IN ('owner', 'admin') AND status = 'active'
    )
  );

CREATE POLICY "workspace_members_select" ON workspace_members FOR SELECT
  USING (is_workspace_member(workspace_id) OR auth.uid() IS NOT NULL);

CREATE POLICY "workspace_members_insert" ON workspace_members FOR INSERT
  WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "prospects_select" ON prospects FOR SELECT
  USING (workspace_id IS NULL OR is_workspace_member(workspace_id));

CREATE POLICY "prospects_insert" ON prospects FOR INSERT
  WITH CHECK (workspace_id IS NULL OR is_workspace_member(workspace_id));

CREATE POLICY "prospects_update" ON prospects FOR UPDATE
  USING (workspace_id IS NULL OR is_workspace_member(workspace_id));

CREATE POLICY "prospects_delete" ON prospects FOR DELETE
  USING (workspace_id IS NULL OR is_workspace_member(workspace_id));

CREATE POLICY "sequences_select" ON sequences FOR SELECT
  USING (workspace_id IS NULL OR is_workspace_member(workspace_id));

CREATE POLICY "sequences_insert" ON sequences FOR INSERT
  WITH CHECK (workspace_id IS NULL OR is_workspace_member(workspace_id));

CREATE POLICY "sequences_update" ON sequences FOR UPDATE
  USING (workspace_id IS NULL OR is_workspace_member(workspace_id));

CREATE POLICY "sequence_steps_all" ON sequence_steps FOR ALL
  USING (
    sequence_id IN (
      SELECT id FROM sequences WHERE workspace_id IS NULL OR is_workspace_member(workspace_id)
    )
  );

CREATE POLICY "enrollments_all" ON sequence_enrollments FOR ALL
  USING (
    sequence_id IN (
      SELECT id FROM sequences WHERE workspace_id IS NULL OR is_workspace_member(workspace_id)
    )
  );

CREATE POLICY "replies_all" ON replies FOR ALL
  USING (workspace_id IS NULL OR is_workspace_member(workspace_id));

-- Done. Table Editor should show: prospects, workspaces, sequences, assets, notifications
