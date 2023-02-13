import logging
import signal
import sys

from models import SubscriptionArea
from tests.conftest import OCCUPANCY_CLIENT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

occupancy_client = OCCUPANCY_CLIENT


def signal_handler(signum, frame):
    signal.signal(signum, signal.SIG_IGN)  # ignore additional signals
    occupancy_client.unsubscribe_from_all()  # cleanup
    sys.exit(0)


if __name__ == "__main__":
    result: SubscriptionArea = occupancy_client.create_subscription_area(
        granularity="Zone",
        group_id=[3544],
    )

    signal.signal(signal.SIGINT, signal_handler)

    occupancy_client.subscribe_to_area(
        sub_area_id=result.id, granularity=result.granularity
    )
