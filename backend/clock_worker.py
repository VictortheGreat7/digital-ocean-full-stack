import logging
import time
from threading import Thread

import cache
from config import MAJOR_CITIES, CACHE_TTL_WORLD_CLOCKS
from helpers import format_time_response
from telemetry import tracer

logger = logging.getLogger(__name__)

# Global reference to prevent duplicate threads in the same process
_updater_thread: Thread | None = None

def _clock_updater_loop():
    # Wait briefly on startup to allow the Redis connection to establish
    time.sleep(2)
    
    while True:
        try:
            if cache.is_cache_ready():
                lock_key = cache.build_cache_key("world-clocks-lock")
                
                # Try to acquire a 2-second distributed lock.
                # nx=True ensures only ONE worker across the cluster gets the lock.
                if cache._client.set(lock_key, "locked", nx=True, ex=2):
                    with tracer.start_as_current_span("world_clocks_background_update"):
                        cities_data: list[dict] = []
                    
                    for city, tz_name in MAJOR_CITIES.items():
                        data = format_time_response(tz_name, city=city)
                        cities_data.append(data)
                            
                    payload = {"cities": cities_data, "count": len(cities_data)}
                    
                    # Store the actual response payload with a TTL slightly longer than the tick
                    data_key = cache.build_cache_key("world-clocks", "latest")
                    cache.set_json(data_key, payload, CACHE_TTL_WORLD_CLOCKS + 5)

        except Exception as exc:
            logger.error("Background clock updater failed: %s", exc)
            
        # Yield the thread for 1 second before the next update tick
        time.sleep(1)

def init_clock_updater(app=None) -> None:
    """Start the background daemon thread if it isn't already running."""
    global _updater_thread

    if _updater_thread is None or not _updater_thread.is_alive():
        _updater_thread = Thread(
            target=_clock_updater_loop,
            daemon=True,
            name="clock-updater"
        )
        _updater_thread.start()
        logger.info("Clock updater background thread started")
    else:
        logger.debug("Clock updater background thread already running")