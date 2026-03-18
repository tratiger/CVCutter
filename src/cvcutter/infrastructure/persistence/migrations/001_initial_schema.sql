CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    role TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    stage_name TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(job_id, stage_name, attempt)
);

CREATE TABLE IF NOT EXISTS config_change_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    changed_key TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS publish_keys (
    job_id TEXT NOT NULL,
    segment_id TEXT NOT NULL,
    destination TEXT NOT NULL,
    PRIMARY KEY(job_id, segment_id, destination)
);

CREATE TABLE IF NOT EXISTS locks (
    lock_name TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    state TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    job_id TEXT,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS segments (
    segment_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    confidence_score INTEGER NOT NULL,
    review_status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audio_source_profiles (
    audio_profile_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    offset_ms INTEGER NOT NULL,
    quality_status TEXT NOT NULL,
    correction_resolution_status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metadata_mapping (
    mapping_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    segment_id TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    publish_visibility TEXT NOT NULL,
    validation_status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS role_policy (
    policy_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    executable_role TEXT NOT NULL,
    context_labels TEXT NOT NULL,
    recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS classification_strategies (
    job_id TEXT PRIMARY KEY,
    strategy TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
