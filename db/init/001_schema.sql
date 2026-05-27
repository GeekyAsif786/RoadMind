CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS intersections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(120) NOT NULL UNIQUE,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    lanes INTEGER NOT NULL DEFAULT 4,
    status VARCHAR(40) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS traffic_observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intersection_id UUID NOT NULL REFERENCES intersections(id) ON DELETE CASCADE,
    vehicle_count INTEGER NOT NULL,
    density DOUBLE PRECISION NOT NULL,
    avg_speed DOUBLE PRECISION,
    occupancy DOUBLE PRECISION,
    source VARCHAR(40) NOT NULL DEFAULT 'manual',
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_traffic_intersection_time
    ON traffic_observations(intersection_id, captured_at DESC);

CREATE TABLE IF NOT EXISTS detection_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intersection_id UUID REFERENCES intersections(id) ON DELETE SET NULL,
    vehicle_count INTEGER NOT NULL,
    density DOUBLE PRECISION NOT NULL,
    frame_width INTEGER NOT NULL,
    frame_height INTEGER NOT NULL,
    image_path TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS signal_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intersection_id UUID NOT NULL REFERENCES intersections(id) ON DELETE CASCADE,
    green_seconds INTEGER NOT NULL,
    yellow_seconds INTEGER NOT NULL,
    red_seconds INTEGER NOT NULL,
    priority VARCHAR(40) NOT NULL DEFAULT 'normal',
    reason TEXT NOT NULL,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_signal_plans_intersection_created
    ON signal_plans(intersection_id, created_at DESC);

CREATE TABLE IF NOT EXISTS emergency_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intersection_id UUID NOT NULL REFERENCES intersections(id) ON DELETE CASCADE,
    vehicle_type VARCHAR(60) NOT NULL,
    direction VARCHAR(40) NOT NULL,
    severity INTEGER NOT NULL DEFAULT 5,
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cleared_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_emergency_events_active
    ON emergency_events(intersection_id, status, severity DESC);

CREATE TABLE IF NOT EXISTS predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intersection_id UUID NOT NULL REFERENCES intersections(id) ON DELETE CASCADE,
    horizon_minutes INTEGER NOT NULL,
    predicted_density DOUBLE PRECISION NOT NULL,
    predicted_vehicle_count DOUBLE PRECISION NOT NULL,
    model_version VARCHAR(80) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO intersections (name, latitude, longitude, lanes)
VALUES ('Central Avenue Junction', 28.6139, 77.2090, 4)
ON CONFLICT (name) DO NOTHING;
