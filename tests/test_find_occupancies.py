import pprint


def test_find_zone_occupancies(occupancy_client):
    result = occupancy_client.find_zone_occupancies(limit=100)
    print()
    pprint.pprint(result)


def test_find_level_occupancies(occupancy_client):
    result = occupancy_client.find_level_occupancies(limit=100)
    print()
    pprint.pprint(result)
