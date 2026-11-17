-- One row per photo. The booth creates it on upload; the survey fills in answers.
-- Either side may arrive first, so both use upserts on id.
CREATE TABLE sessions (
  id TEXT PRIMARY KEY,
  condition TEXT,
  captured_at TEXT,
  uploaded_at TEXT,
  photo_key TEXT,
  submitted_at TEXT,
  survey_version INTEGER,
  answers TEXT
);
