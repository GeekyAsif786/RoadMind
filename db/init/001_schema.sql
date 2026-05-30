CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS intersections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(120) NOT NULL UNIQUE,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    lanes INTEGER NOT NULL DEFAULT 4,
    road_type VARCHAR(20) NOT NULL DEFAULT 'urban' CHECK (road_type IN ('urban','highway','service')),
    status VARCHAR(40) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS traffic_observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intersection_id UUID NOT NULL REFERENCES intersections(id) ON DELETE CASCADE,
    direction VARCHAR(10) DEFAULT 'ALL' CHECK (direction IN ('N','S','E','W','NE','NW','SE','SW','ALL')),
    vehicle_count INTEGER NOT NULL,
    density DOUBLE PRECISION NOT NULL,
    avg_speed DOUBLE PRECISION,
    occupancy DOUBLE PRECISION,
    weather_condition VARCHAR(20) NOT NULL DEFAULT 'clear',
    pcu_total DOUBLE PRECISION,
    source VARCHAR(40) NOT NULL DEFAULT 'manual',
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_traffic_intersection_time
    ON traffic_observations(intersection_id, captured_at DESC);

CREATE INDEX IF NOT EXISTS ix_traffic_observations_captured_at
    ON traffic_observations(captured_at DESC);

CREATE INDEX IF NOT EXISTS ix_traffic_observations_intersection_direction_time
    ON traffic_observations(intersection_id, direction, captured_at DESC);

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

CREATE INDEX IF NOT EXISTS ix_detection_events_intersection_created
    ON detection_events(intersection_id, created_at DESC);

CREATE TABLE IF NOT EXISTS signal_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intersection_id UUID NOT NULL REFERENCES intersections(id) ON DELETE CASCADE,
    green_seconds INTEGER NOT NULL,
    yellow_seconds INTEGER NOT NULL,
    red_seconds INTEGER NOT NULL,
    priority VARCHAR(40) NOT NULL DEFAULT 'normal',
    reason TEXT NOT NULL,
    decision_source VARCHAR(40) NOT NULL DEFAULT 'historical_observation',
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_signal_plans_intersection_created
    ON signal_plans(intersection_id, created_at DESC);

CREATE TABLE IF NOT EXISTS signal_phases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES signal_plans(id) ON DELETE CASCADE,
    phase_number INTEGER NOT NULL CHECK (phase_number >= 1),
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('N','S','E','W','NE','NW','SE','SW','PED','ALL')),
    green_seconds INTEGER NOT NULL CHECK (green_seconds > 0),
    yellow_seconds INTEGER NOT NULL DEFAULT 4,
    phase_order INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_signal_phases_plan
    ON signal_phases(plan_id, phase_order);

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

CREATE INDEX IF NOT EXISTS ix_emergency_events_intersection_detected
    ON emergency_events(intersection_id, detected_at DESC);

CREATE TABLE IF NOT EXISTS emergency_corridors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    emergency_id UUID NOT NULL REFERENCES emergency_events(id) ON DELETE CASCADE,
    intersection_id UUID NOT NULL REFERENCES intersections(id) ON DELETE CASCADE,
    sequence_order INTEGER NOT NULL,
    green_offset_seconds INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_corridors_emergency
    ON emergency_corridors(emergency_id, sequence_order);

CREATE INDEX IF NOT EXISTS ix_emergency_corridors_intersection_status
    ON emergency_corridors(intersection_id, status);

CREATE TABLE IF NOT EXISTS predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intersection_id UUID NOT NULL REFERENCES intersections(id) ON DELETE CASCADE,
    horizon_minutes INTEGER NOT NULL,
    predicted_density DOUBLE PRECISION NOT NULL,
    predicted_vehicle_count DOUBLE PRECISION NOT NULL,
    model_version VARCHAR(80) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_predictions_intersection_created
    ON predictions(intersection_id, created_at DESC);

CREATE TABLE IF NOT EXISTS intersection_signal_states (
    intersection_id UUID PRIMARY KEY REFERENCES intersections(id) ON DELETE CASCADE,
    last_density DOUBLE PRECISION NOT NULL DEFAULT 0,
    last_vehicle_count INTEGER NOT NULL DEFAULT 0,
    last_signal_plan_id UUID REFERENCES signal_plans(id) ON DELETE SET NULL,
    last_detection_timestamp TIMESTAMPTZ,
    decision_source VARCHAR(40) NOT NULL DEFAULT 'safe_fallback_plan',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_intersection_signal_states_updated_at
    ON intersection_signal_states(updated_at);

CREATE TABLE IF NOT EXISTS model_evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_version VARCHAR(80) NOT NULL UNIQUE,
    model_type VARCHAR(40) NOT NULL,
    samples INTEGER NOT NULL,
    mae DOUBLE PRECISION,
    rmse DOUBLE PRECISION,
    r2 DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_model_evaluations_created_at
    ON model_evaluations(created_at);

INSERT INTO intersections (name, latitude, longitude, lanes)
VALUES ('Central Avenue Junction', 28.6139, 77.2090, 4)
ON CONFLICT (name) DO NOTHING;
