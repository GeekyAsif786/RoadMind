BEGIN;

DELETE FROM predictions
WHERE intersection_id IN (
    SELECT id FROM intersections
    WHERE name IN ('Central Avenue Junction', 'North Gate Signal', 'Metro Station Crossing')
)
OR intersection_id IN (
    '11111111-1111-1111-1111-111111111111',
    '22222222-2222-2222-2222-222222222222',
    '33333333-3333-3333-3333-333333333333'
);

DELETE FROM signal_plans
WHERE intersection_id IN (
    SELECT id FROM intersections
    WHERE name IN ('Central Avenue Junction', 'North Gate Signal', 'Metro Station Crossing')
)
OR intersection_id IN (
    '11111111-1111-1111-1111-111111111111',
    '22222222-2222-2222-2222-222222222222',
    '33333333-3333-3333-3333-333333333333'
);

WHERE intersection_id IN (
    SELECT id FROM intersections
    WHERE name IN ('Central Avenue Junction', 'North Gate Signal', 'Metro Station Crossing')
)
OR intersection_id IN (
    '11111111-1111-1111-1111-111111111111',
    '22222222-2222-2222-2222-222222222222',
    '33333333-3333-3333-3333-333333333333'
);

DELETE FROM detection_events
WHERE intersection_id IN (
    SELECT id FROM intersections
    WHERE name IN ('Central Avenue Junction', 'North Gate Signal', 'Metro Station Crossing')
)
OR intersection_id IN (
    '11111111-1111-1111-1111-111111111111',
    '22222222-2222-2222-2222-222222222222',
    '33333333-3333-3333-3333-333333333333'
);

DELETE FROM traffic_observations
WHERE intersection_id IN (
    SELECT id FROM intersections
    WHERE name IN ('Central Avenue Junction', 'North Gate Signal', 'Metro Station Crossing')
)
OR intersection_id IN (
    '11111111-1111-1111-1111-111111111111',
    '22222222-2222-2222-2222-222222222222',
    '33333333-3333-3333-3333-333333333333'
);

DELETE FROM intersections
WHERE name IN ('Central Avenue Junction', 'North Gate Signal', 'Metro Station Crossing')
OR id IN (
    '11111111-1111-1111-1111-111111111111',
    '22222222-2222-2222-2222-222222222222',
    '33333333-3333-3333-3333-333333333333'
);

INSERT INTO intersections (id, name, latitude, longitude, lanes, status)
VALUES
    ('11111111-1111-1111-1111-111111111111', 'Central Avenue Junction', 28.6139, 77.2090, 4, 'active'),
    ('22222222-2222-2222-2222-222222222222', 'North Gate Signal', 28.6201, 77.2155, 3, 'active'),
    ('33333333-3333-3333-3333-333333333333', 'Metro Station Crossing', 28.6075, 77.1988, 5, 'active')
ON CONFLICT (id) DO NOTHING;

INSERT INTO traffic_observations (
    id,
    intersection_id,
    vehicle_count,
    density,
    avg_speed,
    occupancy,
    source,
    captured_at
)
VALUES
    ('10000000-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 18, 0.25, 42.0, 0.32, 'demo', NOW() - INTERVAL '75 minutes'),
    ('10000000-0000-0000-0000-000000000002', '11111111-1111-1111-1111-111111111111', 28, 0.39, 34.0, 0.48, 'demo', NOW() - INTERVAL '60 minutes'),
    ('10000000-0000-0000-0000-000000000003', '11111111-1111-1111-1111-111111111111', 41, 0.57, 24.0, 0.67, 'demo', NOW() - INTERVAL '45 minutes'),
    ('10000000-0000-0000-0000-000000000004', '11111111-1111-1111-1111-111111111111', 55, 0.76, 16.0, 0.82, 'demo', NOW() - INTERVAL '30 minutes'),
    ('10000000-0000-0000-0000-000000000005', '11111111-1111-1111-1111-111111111111', 62, 0.86, 12.0, 0.90, 'demo', NOW() - INTERVAL '15 minutes'),
    ('10000000-0000-0000-0000-000000000006', '22222222-2222-2222-2222-222222222222', 12, 0.22, 46.0, 0.25, 'demo', NOW() - INTERVAL '70 minutes'),
    ('10000000-0000-0000-0000-000000000007', '22222222-2222-2222-2222-222222222222', 19, 0.35, 38.0, 0.41, 'demo', NOW() - INTERVAL '55 minutes'),
    ('10000000-0000-0000-0000-000000000008', '22222222-2222-2222-2222-222222222222', 27, 0.50, 29.0, 0.59, 'demo', NOW() - INTERVAL '40 minutes'),
    ('10000000-0000-0000-0000-000000000009', '22222222-2222-2222-2222-222222222222', 35, 0.65, 21.0, 0.73, 'demo', NOW() - INTERVAL '25 minutes'),
    ('10000000-0000-0000-0000-000000000010', '33333333-3333-3333-3333-333333333333', 22, 0.24, 44.0, 0.30, 'demo', NOW() - INTERVAL '80 minutes'),
    ('10000000-0000-0000-0000-000000000011', '33333333-3333-3333-3333-333333333333', 38, 0.42, 33.0, 0.52, 'demo', NOW() - INTERVAL '50 minutes'),
    ('10000000-0000-0000-0000-000000000012', '33333333-3333-3333-3333-333333333333', 71, 0.79, 14.0, 0.88, 'demo', NOW() - INTERVAL '20 minutes')
ON CONFLICT (id) DO NOTHING;

INSERT INTO emergency_events (
    id,
    intersection_id,
    vehicle_type,
    direction,
    severity,
    status,
    detected_at
)
VALUES
    ('20000000-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 'ambulance', 'northbound', 9, 'active', NOW() - INTERVAL '3 minutes'),
    ('20000000-0000-0000-0000-000000000002', '33333333-3333-3333-3333-333333333333', 'fire truck', 'eastbound', 8, 'cleared', NOW() - INTERVAL '35 minutes')
ON CONFLICT (id) DO NOTHING;

INSERT INTO signal_plans (
    id,
    intersection_id,
    green_seconds,
    yellow_seconds,
    red_seconds,
    priority,
    reason,
    expires_at
)
VALUES
    ('30000000-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 82, 4, 3, 'emergency', 'Demo emergency priority for ambulance approaching from northbound; severity 9/10.', NOW() + INTERVAL '5 minutes'),
    ('30000000-0000-0000-0000-000000000002', '22222222-2222-2222-2222-222222222222', 63, 4, 3, 'high', 'Demo adaptive timing based on moderate-to-high density.', NOW() + INTERVAL '12 minutes'),
    ('30000000-0000-0000-0000-000000000003', '33333333-3333-3333-3333-333333333333', 74, 4, 3, 'high', 'Demo timing for metro crossing rush-hour density.', NOW() + INTERVAL '10 minutes')
ON CONFLICT (id) DO NOTHING;

INSERT INTO predictions (
    id,
    intersection_id,
    horizon_minutes,
    predicted_density,
    predicted_vehicle_count,
    model_version
)
VALUES
    ('40000000-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 30, 0.82, 59, 'demo-rf'),
    ('40000000-0000-0000-0000-000000000002', '22222222-2222-2222-2222-222222222222', 30, 0.61, 33, 'demo-rf'),
    ('40000000-0000-0000-0000-000000000003', '33333333-3333-3333-3333-333333333333', 30, 0.73, 66, 'demo-rf')
ON CONFLICT (id) DO NOTHING;

COMMIT;