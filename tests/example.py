"""
To run example execute PYTHONPATH=src python tests/main.py in terminal from the project root
"""
import signal
import sys
import threading
from abc import ABC
from typing import Dict, List

from clients import HttpClient, WebSocketClient, OccupancyClient
from models import ZoneOccupancy, LevelOccupancy, OccupancySummary, SubscriptionArea

API_URL = (
    "https://6k53h4xplzfpxedhs56wonxf3q.appsync-api.eu-west-1.amazonaws.com/graphql"
)
AUTH_TOKEN = "1234567890AaBbCcDdEeFf0987654321" # Your token
ZONE_ID = 777 # Your Zone ID
FLOOR_NUMBER = None # Number of a floor inside your zone


class LedPanelWebSocketClient(WebSocketClient, ABC):
    def _on_message_data(self, ws, message_object: Dict):
        """Example implementation of data processing method"""
        self.logger.info(f"Sending Message to LED panel: {message_object}")


if __name__ == "__main__":
    # Set up
    http_client = HttpClient(api_url=API_URL, auth_token=AUTH_TOKEN)
    ws_client = LedPanelWebSocketClient(api_url=API_URL, auth_token=AUTH_TOKEN)
    occupancy_client = OccupancyClient(http_client=http_client, ws_client=ws_client, extension_interval=20)

    # Get Occupancy for Zone ZONE_ID
    zone_occupancy: List[ZoneOccupancy] = occupancy_client.find_zone_occupancies(zone_id=ZONE_ID)
    zone_occupancy_summary = zone_occupancy[0].summary

    # Get Occupancy for floor number 0 in zone ZONE_ID
    floor0: List[LevelOccupancy] = occupancy_client.find_level_occupancies(
        zone_id=ZONE_ID, floor_number=FLOOR_NUMBER
    )
    floor0_summary: OccupancySummary = floor0[0].summary

    # Create subscription area for zone ZONE_ID
    zone_occupancy_sub_area: SubscriptionArea = occupancy_client.create_subscription_area(
        granularity="Zone", zone_id=ZONE_ID
    )

    # Create subscription area for floor number 0 in zone ZONE_ID
    floor0_sub_area: SubscriptionArea = occupancy_client.create_subscription_area(
        granularity="Level", zone_id=ZONE_ID, floor_number=FLOOR_NUMBER
    )

    """
    # Create subscription area for floor number 0 & 1 in zone ZONE_ID
    floor0_1_sub_area: SubscriptionArea = occupancy_client.create_subscription_area(
        granularity="Level", zone_id=ZONE_ID, floor_number=[1, 2]
    )

    # subscribe to all areas
    """
    sub_areas = [zone_occupancy_sub_area, floor0_sub_area]

    def signal_handler(signum, frame):
        signal.signal(signum, signal.SIG_IGN)  # ignore additional signals
        occupancy_client.unsubscribe_from_all()  # cleanup
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    threads = [
        threading.Thread(
            target=occupancy_client.subscribe_to_area,
            args=(
                sa.id,
                sa.granularity,
            ),
        )
        for sa in sub_areas
    ]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
