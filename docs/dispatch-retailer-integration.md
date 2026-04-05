# Dispatch: Retailer API Integration Point

The dispatch flow (diagnostics → parts → mechanic) currently uses **stub retailers** for part suggestions. Real store locations and inventory are not yet integrated.

## Current State

- **Location:** `core/dispatch/graph.py` → `MOCK_RETAILERS` in `suggest_parts_node`
- **Format:** `[{ "id", "name", "distance_mi", "store_id" }, ...]`
- **Usage:** Shown to user when selecting part + retailer before payment

## Integration Options (Future)

1. **Google Places API** – Search "AutoZone near [user location]" for real store names and distances. No inventory.
2. **Partner API** – PartsTech, Parts Authority, or similar B2B parts APIs (often paid).
3. **Retailer direct** – AutoZone, NAPA, O'Reilly, Advance do not offer public store-locator or inventory APIs.

## Where to Integrate

Replace `MOCK_RETAILERS` in `suggest_parts_node` with a call to a retailer service, e.g.:

```python
def suggest_parts_node(state: DispatchState) -> dict:
    suggested = state.get("suggested_parts", [])
    user_lat = state.get("user_latitude")
    user_lng = state.get("user_longitude")
    retailers = get_retailers_near(user_lat, user_lng) if (user_lat and user_lng) else MOCK_RETAILERS
    return {
        "part_retailers": retailers,
        ...
    }
```

Ensure each retailer dict has: `id`, `name`, `distance_mi`, `store_id`.
