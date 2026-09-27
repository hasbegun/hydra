"""
Celery application and task infrastructure for Hydra.

Defines the Celery app, queue routing, and shared configuration.
Tasks are defined in submodules (e.g., ``tasks.scan_task``).

Queue layout:
    * ``express``    — CI/CD gate scans, small probe sets (<5 probes)
    * ``default``    — Normal interactive scans
    * ``background`` — Full/OWASP preset scans, scheduled campaigns
"""
import logging

from celery import Celery
from kombu import Exchange, Queue

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Queue definitions
# ---------------------------------------------------------------------------

# All queues use a single direct exchange for simplicity
_exchange = Exchange("hydra", type="direct")

QUEUE_EXPRESS = "express"
QUEUE_DEFAULT = "default"
QUEUE_BACKGROUND = "background"

TASK_QUEUES = (
    Queue(QUEUE_EXPRESS, _exchange, routing_key=QUEUE_EXPRESS),
    Queue(QUEUE_DEFAULT, _exchange, routing_key=QUEUE_DEFAULT),
    Queue(QUEUE_BACKGROUND, _exchange, routing_key=QUEUE_BACKGROUND),
)

# ---------------------------------------------------------------------------
# Celery app factory
# ---------------------------------------------------------------------------


def create_celery_app(
    broker_url: str = "redis://redis:6379/0",
    result_backend: str = "redis://redis:6379/1",
) -> Celery:
    """Create and configure the Celery application.

    Args:
        broker_url: Redis URL for the message broker.
        result_backend: Redis URL for storing task results.

    Returns:
        Configured Celery app instance.
    """
    app = Celery("hydra")

    app.conf.update(
        # Broker + result backend
        broker_url=broker_url,
        result_backend=result_backend,

        # Serialization: JSON only (no pickle — security)
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],

        # Queue config
        task_queues=TASK_QUEUES,
        task_default_queue=QUEUE_DEFAULT,
        task_default_exchange="hydra",
        task_default_routing_key=QUEUE_DEFAULT,

        # Worker behavior
        worker_prefetch_multiplier=1,  # Fair dispatch: one task at a time per worker
        task_acks_late=True,           # Ack after completion (not before)

        # Time limits
        task_soft_time_limit=3600,     # 1 hour soft limit (raises SoftTimeLimitExceeded)
        task_time_limit=3660,          # 1 hour + 1 min hard kill

        # Result expiry
        result_expires=86400,          # 24 hours

        # Timezone
        timezone="UTC",
        enable_utc=True,
    )

    # Auto-discover tasks in the tasks package
    app.autodiscover_tasks(["tasks"])

    return app


# Module-level app instance — import this from route handlers / services.
# Use config settings if available; fall back to defaults for standalone
# worker processes that import this module before FastAPI startup.
def _get_celery_app() -> Celery:
    try:
        from config import settings
        return create_celery_app(
            broker_url=settings.redis_url,
            result_backend=settings.redis_result_url,
        )
    except Exception:
        return create_celery_app()


celery_app = _get_celery_app()


def route_to_queue(probe_count: int = 0, preset: str = "") -> str:
    """Determine which queue a scan should be routed to.

    Args:
        probe_count: Number of probes in the scan.
        preset: Scan preset name (e.g., "fast", "owasp", "full").

    Returns:
        Queue name string.
    """
    # Full/OWASP presets and large scans go to background
    if preset in ("full", "owasp") or probe_count > 50:
        return QUEUE_BACKGROUND

    # Small scans (CI gates) go to express
    if probe_count > 0 and probe_count <= 5:
        return QUEUE_EXPRESS

    return QUEUE_DEFAULT
