import pytest
from clients import HttpClient, WebSocketClient, OccupancyClient

API_URL = (
    "https://igy5fxeslncwlfuqeadhllrotq.appsync-api.eu-west-2.amazonaws.com/graphql"
)
API_KEY = "da2-ua26upkwpve2zf45i5cpyflbuq"
HTTP_CLIENT = HttpClient(api_url=API_URL, api_key=API_KEY)
WS_CLIENT = WebSocketClient(api_url=API_URL, api_key=API_KEY)
OCCUPANCY_CLIENT = OccupancyClient(http_client=HTTP_CLIENT, ws_client=WS_CLIENT)


@pytest.fixture()
def http_client():
    return HTTP_CLIENT


@pytest.fixture()
def ws_client():
    return WS_CLIENT


@pytest.fixture()
def occupancy_client():
    return OCCUPANCY_CLIENT
