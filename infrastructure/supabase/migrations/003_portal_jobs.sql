-- ============================================================
-- CargoIQ Migration 003: Portal Jobs + Container Tracking
-- ============================================================

-- Portal execution jobs (SARS, Transnet, Shipping Lines)
CREATE TABLE portal_jobs (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  job_type        TEXT NOT NULL,    -- e.g. "portal:sars:rla_check"
  portal          TEXT NOT NULL,    -- "sars" | "transnet" | "shipping_msc" etc.
  status          TEXT NOT NULL DEFAULT 'queued'
                  CHECK (status IN ('queued','running','completed','failed','cancelled')),
  params          JSONB NOT NULL DEFAULT '{}',
  result_data     JSONB,
  screenshot      TEXT,             -- Storage path to screenshot
  error           TEXT,
  duration_ms     INTEGER,
  attempt_number  INTEGER NOT NULL DEFAULT 1,
  shipment_id     UUID REFERENCES shipments(id),
  scheduled_at    TIMESTAMPTZ,      -- For cron jobs
  started_at      TIMESTAMPTZ,
  completed_at    TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_portal_jobs_org  ON portal_jobs(org_id, status);
CREATE INDEX idx_portal_jobs_type ON portal_jobs(job_type);
CREATE INDEX idx_portal_jobs_scheduled ON portal_jobs(scheduled_at) WHERE status = 'queued';

-- Container tracking (updated by portal workers every 30 min)
CREATE TABLE container_tracking (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id            UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  container_number  TEXT NOT NULL,
  shipping_line     TEXT,
  status            TEXT,
  location          TEXT,
  vessel_name       TEXT,
  eta               TIMESTAMPTZ,
  is_released       BOOLEAN NOT NULL DEFAULT FALSE,
  released_at       TIMESTAMPTZ,
  demurrage_zar     NUMERIC(12,2) DEFAULT 0,
  days_over_free    INTEGER DEFAULT 0,
  free_days_allowed INTEGER DEFAULT 7,
  shipment_id       UUID REFERENCES shipments(id),
  last_checked_at   TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(org_id, container_number)
);

CREATE INDEX idx_container_tracking_org  ON container_tracking(org_id);
CREATE INDEX idx_container_tracking_released ON container_tracking(org_id, is_released);

ALTER TABLE container_tracking ENABLE ROW LEVEL SECURITY;
CREATE POLICY "org_isolation_container_tracking" ON container_tracking
  FOR ALL USING (org_id = auth_user_org_id());

-- Notification queue (portal workers post here, API sends them out)
CREATE TABLE notification_queue (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  type        TEXT NOT NULL,
  payload     JSONB NOT NULL DEFAULT '{}',
  status      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','sent','failed')),
  sent_at     TIMESTAMPTZ,
  error       TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notif_queue_pending ON notification_queue(org_id, status) WHERE status = 'pending';

ALTER TABLE notification_queue ENABLE ROW LEVEL SECURITY;
CREATE POLICY "org_isolation_notifications" ON notification_queue
  FOR ALL USING (org_id = auth_user_org_id());

-- RLS
ALTER TABLE portal_jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "org_isolation_portal_jobs" ON portal_jobs
  FOR ALL USING (org_id = auth_user_org_id());
