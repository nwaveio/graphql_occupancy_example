from typing import Dict, Tuple


def get_zone_occupancy_subscription() -> str:
    zone_occupancy_subscription = """
    subscription ZoneOccupancySubscription($sub_area_id: ID!) {
      onSubscriptionAreaUpdates(id: $sub_area_id) {
        expiresOn
        floorNumber
        granularity
        groupId
        id
        labels
        levelId
        location {
          lat
          lon
        }
        radius
        updateTime
        updates {
          ... on ZoneOccupancy {
            id
            name
            projectId
            summary {
              available
              occupied
              total
              undefined
            }
          }
        }
        zoneId
      }
    }
    """
    return zone_occupancy_subscription


def get_level_occupancy_subscription() -> str:
    level_occupancy_subscription = """
    subscription LevelOccupancySubscription($sub_area_id: ID!) {
      onSubscriptionAreaUpdates(id: $sub_area_id) {
        expiresOn
        floorNumber
        granularity
        groupId
        id
        labels
        levelId
        location {
          lat
          lon
        }
        radius
        updateTime
        updates {
          ... on LevelOccupancy {
            id
            name
            floorNumber
            summary {
              available
              occupied
              total
              undefined
            }
            zoneId
          }
        }
        zoneId
      }
    }
    """
    return level_occupancy_subscription


def get_group_occupancy_subscription() -> str:
    group_occupancy_subscription = """
    subscription GroupOccupancySubscription($sub_area_id: ID!) {
      onSubscriptionAreaUpdates(id: $sub_area_id) {
        id
        location {
          lat
          lon
        }
        radius
        groupId
        zoneId
        levelId
        floorNumber
        labels
        expiresOn
        granularity
        updateTime
        updates {
          ... on GroupOccupancy {
            id
            name
            customId
            groupType
            levelId
            location {
              lat
              lon
            }
            positionsOccupancy {
              customId
              groupId
              id
              location {
                lat
                lon
              }
              occupancyStatus
              statusChangeTime
            }
            zoneId
            summary {
              available
              occupied
              total
              undefined
            }
          }
        }
      }
    }
    """
    return group_occupancy_subscription


def get_position_occupancy_subscription() -> str:
    position_occupancy_subscription = """
    subscription LevelOccupancySubscription {
      onSubscriptionAreaUpdates(id: %(sub_area_id)s) {
        expiresOn
        floorNumber
        granularity
        groupId
        id
        labels
        levelId
        location {
          lat
          lon
        }
        radius
        updateTime
        zoneId
        updates {
          ... on PositionOccupancy {
            id
            customId
            groupId
            location {
              lat
              lon
            }
            occupancyStatus
            statusChangeTime
          }
        }
      }
    }
    """
    return position_occupancy_subscription


def _build_outer_inner_params(mutation_params: Dict) -> Tuple[str, str]:
    outer_inner_params = {
        "zone_id": ("$zone_id: [Int]", "zoneId: $zone_id"),
        "group_id": ("$group_id: [Int]", "groupId: $group_id"),
        "level_id": ("$level_id: [Int]", "levelId: $level_id"),
        "floor_number": ("$floor_number: [Int]", "floorNumber: $floor_number"),
        "labels": ("$labels: [String]", "labels: $labels"),
        "lat": ("$lat: Float", "lat: $lat"),
        "lon": ("$lon: Float", "lon: $lon"),
        "radius": ("$radius: Int", "radius: $radius"),
        "granularity": (
            "$granularity: SubscriptionGranularity",
            "granularity: $granularity",
        ),
    }
    if len(mutation_params) > 0:
        outer_inner_params = {
            k: v for k, v in outer_inner_params.items() if k in mutation_params
        }
    outer_param_list = [str(i[0]) for i in outer_inner_params.values()]
    inner_param_list = [str(i[1]) for i in outer_inner_params.values()]
    outer_params = ",\n".join(outer_param_list)
    inner_params = ",\n".join(inner_param_list)
    return outer_params, inner_params


def get_create_sub_area_query(mutation_params: Dict) -> str:
    outer_params, inner_params = _build_outer_inner_params(
        mutation_params=mutation_params
    )
    create_subscription_area_mutation = """
    mutation CreateSubscriptionAreaMutation(
      %(outer_params)s
    ) {
      createSubscriptionArea(
        %(inner_params)s
      ) {
        id
        location {
          lat
          lon
        }
        radius
        granularity
        expiresOn
        groupId
        levelId
        floorNumber
        zoneId
        labels
      }
    }
    """ % {
        "outer_params": outer_params,
        "inner_params": inner_params,
    }
    return create_subscription_area_mutation


def get_update_sub_area_query(mutation_params: Dict) -> str:
    outer_params, inner_params = _build_outer_inner_params(
        mutation_params=mutation_params
    )
    update_subscription_area_mutation = """
    mutation UpdateSubscriptionAreaMutation(
      $id: ID!,
      %(outer_params)s
    ) {
      updateSubscriptionArea(
        id: $id,
        %(inner_params)s
      ) {
        id
        location {
          lat
          lon
        }
        radius
        granularity
        expiresOn
        groupId
        levelId
        floorNumber
        zoneId
        labels
      }
    }
    """ % {
        "outer_params": outer_params,
        "inner_params": inner_params,
    }
    return update_subscription_area_mutation


def get_group_occupancies_query() -> str:
    find_group_occupancies_query = """
    query FindGroupOccupancies(
      $ids: [Int],
      $project_id: Int,
      $radius: Int,
      $lon: Float,
      $lat: Float,
      $level_id: [Int!],
      $limit: Int,
      $offset: Int,
      $zone_id: [Int!],
      $group_custom_id: String,
      $floor_number: [Int!]
    ) {
      findGroupOccupancies(
        floorNumber: $floor_number, 
        groupCustomId: $group_custom_id, 
        ids: $ids, 
        lat: $lat, 
        levelId: $level_id, 
        limit: $limit, 
        lon: $lon, 
        offset: $offset, 
        projectId: $project_id, 
        radius: $radius, 
        zoneId: $zone_id
      ) {
        levelId
        zoneId
        summary {
          available
          occupied
          total
          undefined
        }
      }
    }
    """
    return find_group_occupancies_query
