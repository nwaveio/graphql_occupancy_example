import json
from datetime import datetime
from enum import Enum
from threading import Timer
from typing import Optional, List, Dict

from pydantic import BaseModel, root_validator, validator


def to_camel(string: str) -> str:
    words = []
    for i, word in enumerate(string.split("_")):
        if i == 0:
            words.append(word)
        else:
            words.append(word.capitalize())
    return "".join(words)


class SubscriptionGranularity(Enum):
    """Occupancy Grouping Granularity"""

    Position = "Position"
    Group = "Group"
    Level = "Level"
    Zone = "Zone"


class Location(BaseModel):
    """Geospatial coordinates"""

    lat: float
    lon: float


class OccupancySummary(BaseModel):
    """Summary of position occupancies"""

    total: int
    occupied: int
    available: int
    undefined: int


class HierarchyFilters(BaseModel):
    """Hierarchy Filters common to all Subscription Areas"""

    zone_id: Optional[List[int]] = None
    group_id: Optional[List[int]] = None
    level_id: Optional[List[int]] = None
    floor_number: Optional[List[int]] = None
    labels: Optional[List[str]] = None

    @validator("labels", "group_id", "level_id", "floor_number", "zone_id", pre=True, always=True)
    def to_list(cls, value):
        if isinstance(value, (int, str)):
            return [value]
        return value


class SubscriptionArea(HierarchyFilters):
    """Model for existing Subscription Areas"""

    id: int
    granularity: SubscriptionGranularity
    expires_on: Optional[datetime] = None

    location: Optional[Location] = None
    radius: Optional[int] = None

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True


class SubscriptionAreaCreate(HierarchyFilters):
    """Model for creating Subscription Area objects"""

    granularity: SubscriptionGranularity

    lat: Optional[float] = None
    lon: Optional[float] = None
    radius: Optional[int] = None

    @root_validator
    def at_least_one_filter(cls, values):
        """Checks that at least one filtering option is present"""
        geospatial_filters = [
            values.get("lat"),
            values.get("lon"),
            values.get("radius"),
        ]
        if any(geospatial_filters):
            assert all(
                geospatial_filters
            ), "Incomplete geospatial filter (lat, lon, radius)"
            return values
        else:
            hierarchical_filters = [
                values.get("zone_id"),
                values.get("group_id"),
                values.get("level_id"),
                values.get("floor_number"),
                values.get("labels"),
            ]
            assert any(
                hierarchical_filters
            ), "At least one filtering option has to be provided"
            return values

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True

    def mutation_params(self) -> Dict:
        """Returns mutation parameters"""
        return json.loads(self.json(exclude_unset=True))


class SubscriptionAreaUpdate(HierarchyFilters):
    """Model for updating Subscription Area objects"""

    id: int
    granularity: Optional[SubscriptionGranularity] = None

    lat: Optional[float] = None
    lon: Optional[float] = None
    radius: Optional[int] = None

    def mutation_params(self) -> Dict:
        """Returns mutation parameters"""
        return json.loads(self.json(exclude_unset=True))


class LevelOccupancy(BaseModel):
    """Level Occupancy"""

    id: Optional[int]
    zone_id: int
    summary: Optional[OccupancySummary] = None

    class Config:
        allow_population_by_field_name = True
        alias_generator = to_camel


class ZoneOccupancy(BaseModel):
    """Zone Occupancy"""

    id: Optional[int] = None
    summary: Optional[OccupancySummary] = None

    class Config:
        allow_population_by_field_name = True
        alias_generator = to_camel


class FindQueryFilter(BaseModel):
    """Find Query Filtering Model"""

    ids: Optional[List[int]] = None
    level_id: Optional[List[int]] = None
    floor_number: Optional[List[int]] = None
    zone_id: Optional[List[int]] = None
    project_id: Optional[int] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    radius: Optional[int] = None
    limit: Optional[int] = None
    offset: Optional[int] = None

    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True

    @root_validator
    def at_geo_filter_validator(cls, values):
        """Checks that at least one filtering option is present"""
        geospatial_filters = [
            values.get("lat"),
            values.get("lon"),
            values.get("radius"),
        ]
        if any(geospatial_filters):
            assert all(
                geospatial_filters
            ), "Incomplete geospatial filter (lat, lon, radius)"

        return values

    @validator("ids", "level_id", "floor_number", "zone_id", pre=True, always=True)
    def int_to_list(cls, value):
        if isinstance(value, (int, str)):
            return [value]
        return value


class SubscriptionDetails(BaseModel):
    query: str
    subscription_area_id: int
    websocket_subscription_id: str
    timeout_timer: Optional[Timer] = None
    timeout_interval_s: Optional[int] = 10

    class Config:
        arbitrary_types_allowed = True

