import json
import logging
import abc
import threading
from base64 import b64encode
from collections import defaultdict
from typing import Dict, List, Union
from uuid import uuid4
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
from graphql import DocumentNode, GraphQLError
from typing_extensions import Literal
from websocket import WebSocketApp

from models import (
    SubscriptionArea,
    SubscriptionAreaUpdate,
    ZoneOccupancy,
    LevelOccupancy,
    SubscriptionAreaCreate,
    SubscriptionGranularity,
    FindQueryFilter,
    SubscriptionDetails,
    OccupancySummary,
)
from queries import (
    get_update_sub_area_query,
    get_create_sub_area_query,
    get_zone_occupancy_subscription,
    get_level_occupancy_subscription,
    get_group_occupancy_subscription,
    get_position_occupancy_subscription,
    get_group_occupancies_query,
)

logging.basicConfig(level=logging.INFO)


class Empty:
    """Empty Parameter Type"""


class HttpClient:
    def __init__(self, api_url: str, auth_token: str):
        self.api_url = api_url
        self.auth_token = auth_token
        self.logger = logging.getLogger(self.__class__.__name__)
        self._init_client()

    def _init_client(self):
        """Initialize HTTP Client with credentials"""
        transport = AIOHTTPTransport(
            url=self.api_url, headers={"Authorization": self.auth_token}, timeout=60
        )
        self.client = Client(transport=transport)
        self.logger.info("Initialized HTTP Client")

    def execute(self, query: str, variables: Dict):
        """Executes GraphQL query/mutation and returns the result"""
        try:
            parsed_query: DocumentNode = gql(query)
            result = self.client.execute(parsed_query, variable_values=variables)
            return result
        except GraphQLError as exc:
            self.logger.error(f"Cannot validate query: {exc}")


class WebSocketClient:
    def __init__(self, api_url: str, auth_token: str):
        self.wss_url = self._get_wss_url(api_url)
        self.header = self._make_header(api_url, auth_token)
        self.connection_url = (
            self.wss_url
            + "?header="
            + self._header_encode(self.header)
            + "&payload=e30="
        )
        self.active_subscriptions: Dict[WebSocketApp, SubscriptionDetails] = {}
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("Initialized WebSocket Client")

    @staticmethod
    def _get_wss_url(api_url: str) -> str:
        """Makes Websocket URL from the https URL"""
        wss_url = api_url.replace("https", "wss").replace(
            "appsync-api", "appsync-realtime-api"
        )
        return wss_url

    @staticmethod
    def _get_host(api_url: str) -> str:
        """Retrieved Host name from the https URL"""
        host = api_url.replace("https://", "").replace("/graphql", "")
        return host

    @staticmethod
    def _header_encode(header: Dict):
        """Encodes header using base 64"""
        return b64encode(json.dumps(header).encode("utf-8")).decode("utf-8")

    def _initialize_connection(self, ws: WebSocketApp):
        """Sends connection initialization message"""
        init = {"type": "connection_init"}
        init_conn = json.dumps(init)
        ws.send(init_conn)
        details = self.active_subscriptions.get(ws)
        self.logger.info(f"SA {details.subscription_area_id}: Connection init")

    def _close_connection(self, ws: WebSocketApp):
        """Closes websocket connection"""
        ws.close()
        self._remove_subscription(ws)

    def _deregister(self, ws: WebSocketApp):
        """Deregisters websocket subscription"""
        details = self.active_subscriptions[ws]
        deregister = {"type": "stop", "id": details.websocket_subscription_id}
        end_sub = json.dumps(deregister)
        ws.send(end_sub)
        self.logger.info(f"SA {details.subscription_area_id}: Deregistered")

    def get_active_subscription_area_ids(self) -> List[int]:
        """Retrieves a list of active subscription area ids"""
        return [
            details.subscription_area_id
            for details in self.active_subscriptions.values()
        ]

    def _make_header(self, api_url: str, auth_token: str) -> Dict:
        """Creates AppSync request header"""
        host = self._get_host(api_url)
        header = {"host": host, "Authorization": auth_token}
        return header

    def _reset_timer(self, ws: WebSocketApp):
        """Resets connection timeout timer"""
        details: SubscriptionDetails = self.active_subscriptions.get(ws)
        if details.timeout_timer:
            details.timeout_timer.cancel()
            self.logger.debug(f"SA {details.subscription_area_id}: Canceled timer")
        details.timeout_timer = threading.Timer(
            details.timeout_interval_s, lambda: ws.close()
        )
        details.timeout_timer.daemon = True
        details.timeout_timer.start()
        self.logger.info(
            f"SA {details.subscription_area_id}: Reset timer"
        )

    def _on_message(self, ws: WebSocketApp, message: str):
        """This function is called when a new message is received from a websocket"""
        self.logger.debug(f"Message: {message}")

        message_object = json.loads(message)
        message_type = message_object["type"]

        if message_type == "ka":
            self._on_message_keep_alive(ws=ws)

        elif message_type == "connection_ack":
            self._on_message_connection_ack(ws=ws, message_object=message_object)

        elif message_type == "data":
            self._on_message_data(ws=ws, message_object=message_object)

        elif message_object["type"] == "error":
            self._on_message_error(ws=ws, message_object=message_object)

        elif message_object["type"] == "complete":
            self._close_connection(ws)

    def _on_message_keep_alive(self, ws: WebSocketApp):
        self._reset_timer(ws)

    def _on_message_connection_ack(self, ws: WebSocketApp, message_object: Dict):
        details = self.active_subscriptions[ws]
        payload_interval = (
            int(json.dumps(message_object["payload"]["connectionTimeoutMs"])) // 1000
        )
        details.timeout_interval_s = payload_interval
        register = {
            "id": details.websocket_subscription_id,
            "payload": {
                "data": details.query,
                "extensions": {"authorization": self.header},
            },
            "type": "start",
        }
        start_sub = json.dumps(register)
        ws.send(start_sub)
        self.logger.info(f"SA {details.subscription_area_id}: Connection ack sent, timeout {payload_interval}s")

    @abc.abstractmethod
    def _on_message_data(self, ws, message_object: Dict):
        """Implement this message processing method
        :param ws: WebSocketApp
        :param message_object: parsed message object
        """

    def _on_message_error(self, ws: WebSocketApp, message_object: Dict):
        details = self.active_subscriptions.get(ws)
        self.logger.error(f"SA {details.subscription_area_id}: Error from AppSync {message_object['payload']}")
        self._close_connection(ws=ws)

    def _on_error(self, ws: WebSocketApp, error):
        details = self.active_subscriptions.get(ws)
        self.logger.error(f"SA {details.subscription_area_id}: Error {error}")
        self._close_connection(ws=ws)

    def _on_close(self, ws: WebSocketApp, close_status_code: int, close_msg: str):
        details = self.active_subscriptions.get(ws)
        self.logger.info(
            f"SA {details.subscription_area_id}: Connection closed, status Code {close_status_code}, message {close_msg}"
        )

    def _on_open(self, ws: WebSocketApp):
        self._initialize_connection(ws=ws)

    def _remove_subscription(self, ws: WebSocketApp):
        removed = self.active_subscriptions.pop(ws, None)
        self.logger.info(f"SA {removed.subscription_area_id}: Removed active subscription")

    def subscribe(self, sub_area_id: int, subscription: str):
        ws = WebSocketApp(
            self.connection_url,
            subprotocols=["graphql-ws"],
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        query = json.dumps(
            {"query": subscription, "variables": {"sub_area_id": sub_area_id}}
        )

        details = SubscriptionDetails(
            query=query,
            subscription_area_id=sub_area_id,
            websocket_subscription_id=str(uuid4()),
        )
        self.active_subscriptions[ws] = details
        self.logger.info(f"SA {details.subscription_area_id}: Websocket created")
        ws.run_forever()

    def unsubscribe(self, sub_area_id) -> bool:
        for ws, details in self.active_subscriptions.items():
            if details.subscription_area_id == sub_area_id:
                self._deregister(ws=ws)
                return True
        return False


class OccupancyClient:
    def __init__(
        self,
        http_client: HttpClient,
        ws_client: WebSocketClient,
        extension_interval: int = 240,
    ):
        self.http_client = http_client
        self.ws_client = ws_client
        self.logger = logging.getLogger(self.__class__.__name__)
        self.extension_interval = extension_interval

    def _extend_active_subscriptions(self):
        active_sub_ids = self.ws_client.get_active_subscription_area_ids()
        if len(active_sub_ids) == 0:
            self.extender.cancel()
            self.logger.info(f"No active subscription, canceled extender")
        else:
            for sub_area_id in active_sub_ids:
                self.extend_subscription_area(sub_area_id=sub_area_id)
            self._start_subscription_extender()

    def _start_subscription_extender(self):
        extender = threading.Timer(
            self.extension_interval, lambda: self._extend_active_subscriptions()
        )
        extender.daemon = True
        extender.start()
        self.extender = extender
        self.logger.info("Subscription extender started")

    def unsubscribe_from_all(self):
        actives_subs = self.ws_client.get_active_subscription_area_ids()
        for id_ in actives_subs:
            self.unsubscribe_from_area(sub_area_id=id_)

    @staticmethod
    def sum_summaries(summaries: List[OccupancySummary]) -> OccupancySummary:
        """Calculates total summary from list of summaries"""
        total_summary = OccupancySummary(total=0, occupied=0, available=0, undefined=0)
        for s in summaries:
            total_summary.total += s.total
            total_summary.occupied += s.occupied
            total_summary.available += s.available
            total_summary.undefined += s.undefined
        return total_summary

    @staticmethod
    def _build_params(
        zone_id: Union[Empty, None, List[int]],
        group_id: Union[Empty, None, List[int]],
        level_id: Union[Empty, None, List[int]],
        floor_number: Union[Empty, None, List[int]],
        labels: Union[Empty, None, List[str]],
        granularity: Union[Empty, None, Literal["Zone", "Level", "Group", "Position"]],
        lat: Union[Empty, None, float],
        lon: Union[Empty, None, float],
        radius: Union[Empty, None, int],
    ) -> Dict:
        params = dict()
        if zone_id is not Empty:
            params["zone_id"] = zone_id
        if group_id is not Empty:
            params["group_id"] = group_id
        if level_id is not Empty:
            params["level_id"] = level_id
        if floor_number is not Empty:
            params["floor_number"] = floor_number
        if labels is not Empty:
            params["labels"] = labels
        if granularity is not Empty:
            params["granularity"] = (
                SubscriptionGranularity[granularity]
                if granularity is not None
                else None
            )
        if lat is not Empty:
            params["lat"] = lat
        if lon is not Empty:
            params["lon"] = lon
        if radius is not Empty:
            params["radius"] = radius

        return params

    def _group_by_zone(self, occupancies: List[Dict]) -> List[ZoneOccupancy]:
        """Groups occupancies by Zone"""
        grouped = defaultdict(list)
        zo: ZoneOccupancy
        for zo in [ZoneOccupancy.parse_obj(o) for o in occupancies]:
            summary = zo.summary
            if summary is not None:
                grouped[zo.id].append(summary)
        result = []
        for zone_id, summaries in grouped.items():
            total_summary = self.sum_summaries(summaries)
            zo = ZoneOccupancy(id=zone_id, summary=total_summary)
            result.append(zo)
        return result

    def _group_by_level(self, occupancies: List[Dict]) -> List[LevelOccupancy]:
        """Groups occupancies by Level"""
        grouped = defaultdict(list)
        lo: LevelOccupancy
        for lo in [LevelOccupancy.parse_obj(o) for o in occupancies]:
            summary = lo.summary
            if summary is not None:
                grouped[(lo.id, lo.zone_id)].append(summary)
        result = []
        for (level_id, zone_id), summaries in grouped.items():
            total_summary = self.sum_summaries(summaries)
            result.append(
                LevelOccupancy(id=level_id, zone_id=zone_id, summary=total_summary)
            )
        return result

    def find_zone_occupancies(
        self,
        group_id: Union[int, List[int]] = None,
        level_id: Union[int, List[int]] = None,
        floor_number: Union[int, List[int]] = None,
        zone_id: Union[int, List[int]] = None,
        project_id: int = None,
        lat: float = None,
        lon: float = None,
        radius: int = None,
        limit: int = None,
        offset: int = None,
    ) -> List[ZoneOccupancy]:
        """ Zone occupancy """
        filters = FindQueryFilter(
            ids=group_id,
            level_id=level_id,
            floor_number=floor_number,
            zone_id=zone_id,
            project_id=project_id,
            lat=lat,
            lon=lon,
            radius=radius,
            limit=limit,
            offset=offset,
        )
        query = get_group_occupancies_query()
        response = self.http_client.execute(query=query, variables=filters.dict())
        occupancies = response["findGroupOccupancies"]
        zone_occupancies = self._group_by_zone(occupancies=occupancies)
        return zone_occupancies

    def find_level_occupancies(
        self,
        group_id: Union[int, List[int]] = None,
        level_id: Union[int, List[int]] = None,
        floor_number: Union[int, List[int]] = None,
        zone_id: Union[int, List[int]] = None,
        project_id: int = None,
        lat: float = None,
        lon: float = None,
        radius: int = None,
        limit: int = None,
        offset: int = None,
    ) -> List[LevelOccupancy]:
        """ Level occupancy """
        filters = FindQueryFilter(
            ids=group_id,
            level_id=level_id,
            floor_number=floor_number,
            zone_id=zone_id,
            project_id=project_id,
            lat=lat,
            lon=lon,
            radius=radius,
            limit=limit,
            offset=offset,
        )
        query = get_group_occupancies_query()
        response = self.http_client.execute(query=query, variables=filters.dict())
        occupancies = response["findGroupOccupancies"]
        level_occupancies = self._group_by_level(occupancies=occupancies)
        return level_occupancies

    def create_subscription_area(
        self,
        granularity: Literal["Zone", "Level", "Group", "Position"],
        lat: float = Empty,
        lon: float = Empty,
        radius: int = Empty,
        zone_id: Union[int, List[int]] = Empty,
        group_id: Union[int, List[int]] = Empty,
        level_id: Union[int, List[int]] = Empty,
        floor_number: Union[int, List[int]] = Empty,
        labels: Union[str, List[str]] = Empty,
    ) -> SubscriptionArea:
        """Creates new subscription area"""
        params = self._build_params(
            zone_id=zone_id,
            group_id=group_id,
            level_id=level_id,
            floor_number=floor_number,
            labels=labels,
            granularity=granularity,
            lat=lat,
            lon=lon,
            radius=radius,
        )
        sub_area = SubscriptionAreaCreate.parse_obj(params)
        self.logger.debug("Creating subscription area...")
        mutation = get_create_sub_area_query(mutation_params=sub_area.mutation_params())
        result = self.http_client.execute(
            mutation, variables=sub_area.mutation_params()
        )
        created_dict = result.get("createSubscriptionArea")
        created_sa = SubscriptionArea.parse_obj(created_dict)
        self.logger.debug(f"Subscription area created {created_sa.dict()}")
        return created_sa

    def update_subscription_area(
        self,
        sub_area_id: int,
        granularity: Literal["Zone", "Level", "Group", "Position"] = Empty,
        lat: float = Empty,
        lon: float = Empty,
        radius: int = Empty,
        zone_id: Union[int, List[int]] = Empty,
        group_id: Union[int, List[int]] = Empty,
        level_id: Union[int, List[int]] = Empty,
        floor_number: Union[int, List[int]] = Empty,
        labels: Union[str, List[str]] = Empty,
    ) -> SubscriptionArea:
        """Updates an existing subscription area"""
        params = self._build_params(
            zone_id=zone_id,
            group_id=group_id,
            level_id=level_id,
            floor_number=floor_number,
            labels=labels,
            granularity=granularity,
            lat=lat,
            lon=lon,
            radius=radius,
        )
        params["id"] = sub_area_id
        sub_area = SubscriptionAreaUpdate.parse_obj(params)
        self.logger.debug(f"Updating subscription area {sub_area_id}...")
        mutation = get_update_sub_area_query(mutation_params=sub_area.mutation_params())
        result = self.http_client.execute(
            mutation, variables=sub_area.mutation_params()
        )
        updated_dict = result.get("updateSubscriptionArea")
        updated_sa = SubscriptionArea.parse_obj(updated_dict)
        self.logger.debug(f"Subscription area updated {updated_sa.json()}")
        return updated_sa

    def extend_subscription_area(self, sub_area_id: int) -> SubscriptionArea:
        """Extends subscription area expiration"""
        sub_area = SubscriptionAreaUpdate.parse_obj({"id": sub_area_id})
        self.logger.debug(f"Extending expiry for subscription area {sub_area_id}...")
        mutation = get_update_sub_area_query(mutation_params=sub_area.mutation_params())
        result = self.http_client.execute(
            mutation, variables=sub_area.mutation_params()
        )
        updated_dict = result.get("updateSubscriptionArea")
        updated_sa = SubscriptionArea.parse_obj(updated_dict)
        self.logger.debug(
            f"SA {updated_sa.id}: Extended expiry {updated_sa.expires_on.isoformat()}"
        )
        return updated_sa

    def subscribe_to_area(
        self, sub_area_id: int, granularity: SubscriptionGranularity
    ):
        """Subscribe to subscription area"""
        self.logger.debug(f"Subscribing to area {sub_area_id}...")
        if granularity == SubscriptionGranularity.Position:
            subscription = get_position_occupancy_subscription()
        elif granularity == SubscriptionGranularity.Group:
            subscription = get_group_occupancy_subscription()
        elif granularity == SubscriptionGranularity.Level:
            subscription = get_level_occupancy_subscription()
        elif granularity == SubscriptionGranularity.Zone:
            subscription = get_zone_occupancy_subscription()
        else:
            raise ValueError(f"Unsupported granularity: {granularity}")
        self._start_subscription_extender()
        self.ws_client.subscribe(sub_area_id=sub_area_id, subscription=subscription)

    def unsubscribe_from_area(self, sub_area_id: int) -> bool:
        """Unsubscribe from subscription"""
        return self.ws_client.unsubscribe(sub_area_id=sub_area_id)
