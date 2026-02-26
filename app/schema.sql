CREATE TABLE IF NOT EXISTS articles (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    content TEXT,
    published_at TIMESTAMPTZ,
    fetched_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_profiles (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    interests TEXT NOT NULL
);

-- Seed a default profile if table is empty
INSERT INTO user_profiles (name, interests)
SELECT 'Default', 'software engineering, cloud computing, AI and machine learning, open source, DevOps, distributed systems'
WHERE NOT EXISTS (SELECT 1 FROM user_profiles LIMIT 1);

CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY,
    user_profile_id INT REFERENCES user_profiles(id) DEFAULT 1,
    timeframe_hours INT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    progress TEXT,
    article_count INT,
    interests TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error TEXT
);

CREATE TABLE IF NOT EXISTS digests (
    id SERIAL PRIMARY KEY,
    job_id UUID REFERENCES jobs(id),
    briefing TEXT NOT NULL,
    article_ids INT[] NOT NULL,
    scores JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS article_scores (
    article_id INT REFERENCES articles(id),
    user_profile_id INT REFERENCES user_profiles(id),
    score INT NOT NULL CHECK (score BETWEEN 1 AND 10),
    scored_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (article_id, user_profile_id)
);

CREATE INDEX IF NOT EXISTS idx_articles_fetched_at ON articles(fetched_at);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_article_scores_score ON article_scores(score);

-- Idempotent migration: add interests column to existing jobs table
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
    WHERE table_name='jobs' AND column_name='interests')
  THEN ALTER TABLE jobs ADD COLUMN interests TEXT;
  END IF;
END$$;
