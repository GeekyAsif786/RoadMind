# Emergency Logic

RoadMind keeps the existing emergency override behavior and adds explicit priority metadata.

Priority order:

1. Ambulance
2. Fire
3. Disaster response
4. Police
5. VIP

Corridor timing uses estimated travel time between intersections:

- Default spacing: 400 meters
- Input speed: `avg_speed_kmh`
- Offset: `sequence_order * spacing / speed`

If a corridor leg overlaps a higher-priority active emergency, the leg is marked `conflict`. Existing API behavior is preserved: RoadMind still creates the corridor records and signal plans instead of rejecting the request.
