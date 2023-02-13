import json
import pprint
import pytest


def test_create_subscription_area(occupancy_client):
    result = occupancy_client.create_subscription_area(
        granularity="Zone",
        zone_id=[1],
        group_id=None,
        level_id=None,
        floor_number=None,
        labels=None,
        lat=None,
        lon=None,
        radius=None,
    )
    print()
    pprint.pprint(result.dict())


@pytest.mark.parametrize(
    "to_create, to_update, expected",
    [
        (
            {
                "granularity": "Zone",
                "zone_id": [1],
                "group_id": [1],
                "level_id": [1],
                "labels": ["EV"],
            },
            {
                "granularity": "Level",
                "zone_id": None,
                "group_id": None,
                "level_id": None,
                "labels": ["EV", "Disabled"],
            },
            {
                "granularity": "Level",
                "zone_id": None,
                "group_id": None,
                "level_id": None,
                "floor_number": None,
                "labels": ["EV", "Disabled"],
            },
        ),
    ],
)
def test_update_subscription_area(occupancy_client, to_create, to_update, expected):
    result = occupancy_client.create_subscription_area(**to_create)
    print()
    pprint.pprint(result.dict())

    result = occupancy_client.update_subscription_area(
        sub_area_id=result.id, **to_update
    )
    print()
    pprint.pprint(result.dict())

    result = json.loads(result.json())
    for k, v in expected.items():
        assert result[k] == v


@pytest.mark.parametrize(
    "to_create, to_update, expected",
    [
        (
            {
                "granularity": "Zone",
                "zone_id": [1],
                "group_id": [1],
                "level_id": [1],
                "labels": ["EV"],
            },
            {},
            {
                "granularity": "Zone",
                "zone_id": [1],
                "group_id": [1],
                "level_id": [1],
                "labels": ["EV"],
            },
        ),
    ],
)
def test_extend_subscription_area(occupancy_client, to_create, to_update, expected):
    result = occupancy_client.create_subscription_area(**to_create)
    print()
    pprint.pprint(result.dict())

    result = occupancy_client.update_subscription_area(sub_area_id=result.id)
    print()
    pprint.pprint(result.dict())
