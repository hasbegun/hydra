"""
Tests for Phase 1: Celery application setup and queue configuration.

Covers:
- Celery app configuration (broker, serializer, result backend)
- Three queue definitions (express, default, background)
- Queue routing logic (probe count and preset-based routing)
- JSON serializer enforcement (no pickle)
- Worker behavior settings (prefetch, ack_late)
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Celery app configuration
# ---------------------------------------------------------------------------

class TestCeleryAppConfig:
    """Tests for the Celery application setup."""

    def test_celery_app_exists(self):
        from tasks import celery_app
        assert celery_app is not None
        assert celery_app.main == "hydra"

    def test_celery_json_serializer(self):
        from tasks import celery_app
        assert celery_app.conf.task_serializer == "json"
        assert celery_app.conf.result_serializer == "json"
        assert "json" in celery_app.conf.accept_content

    def test_celery_no_pickle(self):
        """Pickle must not be accepted — security risk."""
        from tasks import celery_app
        assert "pickle" not in celery_app.conf.accept_content

    def test_celery_acks_late(self):
        """Tasks should ack after completion, not before."""
        from tasks import celery_app
        assert celery_app.conf.task_acks_late is True

    def test_celery_prefetch_one(self):
        """Fair dispatch: one task at a time per worker."""
        from tasks import celery_app
        assert celery_app.conf.worker_prefetch_multiplier == 1

    def test_celery_time_limits(self):
        from tasks import celery_app
        assert celery_app.conf.task_soft_time_limit == 3600
        assert celery_app.conf.task_time_limit == 3660

    def test_celery_result_expiry(self):
        from tasks import celery_app
        assert celery_app.conf.result_expires == 86400

    def test_celery_utc_enabled(self):
        from tasks import celery_app
        assert celery_app.conf.enable_utc is True
        assert celery_app.conf.timezone == "UTC"


# ---------------------------------------------------------------------------
# Queue definitions
# ---------------------------------------------------------------------------

class TestQueueDefinitions:
    """Tests for the three-queue layout."""

    def test_three_queues_defined(self):
        from tasks import TASK_QUEUES
        assert len(TASK_QUEUES) == 3

    def test_queue_names(self):
        from tasks import TASK_QUEUES
        names = {q.name for q in TASK_QUEUES}
        assert names == {"express", "default", "background"}

    def test_default_queue_is_default(self):
        from tasks import celery_app, QUEUE_DEFAULT
        assert celery_app.conf.task_default_queue == QUEUE_DEFAULT

    def test_all_queues_use_hydra_exchange(self):
        from tasks import TASK_QUEUES
        for q in TASK_QUEUES:
            assert q.exchange.name == "hydra"

    def test_queue_routing_keys_match_names(self):
        from tasks import TASK_QUEUES
        for q in TASK_QUEUES:
            assert q.routing_key == q.name


# ---------------------------------------------------------------------------
# Queue routing logic
# ---------------------------------------------------------------------------

class TestQueueRouting:
    """Tests for route_to_queue() priority routing."""

    def test_express_for_small_probe_count(self):
        from tasks import route_to_queue, QUEUE_EXPRESS
        assert route_to_queue(probe_count=1) == QUEUE_EXPRESS
        assert route_to_queue(probe_count=3) == QUEUE_EXPRESS
        assert route_to_queue(probe_count=5) == QUEUE_EXPRESS

    def test_default_for_medium_probe_count(self):
        from tasks import route_to_queue, QUEUE_DEFAULT
        assert route_to_queue(probe_count=6) == QUEUE_DEFAULT
        assert route_to_queue(probe_count=20) == QUEUE_DEFAULT
        assert route_to_queue(probe_count=50) == QUEUE_DEFAULT

    def test_background_for_large_probe_count(self):
        from tasks import route_to_queue, QUEUE_BACKGROUND
        assert route_to_queue(probe_count=51) == QUEUE_BACKGROUND
        assert route_to_queue(probe_count=200) == QUEUE_BACKGROUND

    def test_background_for_owasp_preset(self):
        from tasks import route_to_queue, QUEUE_BACKGROUND
        assert route_to_queue(preset="owasp") == QUEUE_BACKGROUND

    def test_background_for_full_preset(self):
        from tasks import route_to_queue, QUEUE_BACKGROUND
        assert route_to_queue(preset="full") == QUEUE_BACKGROUND

    def test_default_for_fast_preset(self):
        from tasks import route_to_queue, QUEUE_DEFAULT
        assert route_to_queue(preset="fast") == QUEUE_DEFAULT

    def test_default_for_zero_probes(self):
        """Zero probes (e.g., 'all' shorthand) defaults to default queue."""
        from tasks import route_to_queue, QUEUE_DEFAULT
        assert route_to_queue(probe_count=0) == QUEUE_DEFAULT

    def test_preset_overrides_probe_count(self):
        """owasp preset goes to background even with few probes."""
        from tasks import route_to_queue, QUEUE_BACKGROUND
        assert route_to_queue(probe_count=2, preset="owasp") == QUEUE_BACKGROUND


# ---------------------------------------------------------------------------
# create_celery_app factory
# ---------------------------------------------------------------------------

class TestCeleryAppFactory:
    """Tests for create_celery_app() with custom URLs."""

    def test_custom_broker_url(self):
        from tasks import create_celery_app
        app = create_celery_app(broker_url="redis://custom:6380/5")
        assert app.conf.broker_url == "redis://custom:6380/5"

    def test_custom_result_backend(self):
        from tasks import create_celery_app
        app = create_celery_app(result_backend="redis://custom:6380/6")
        assert app.conf.result_backend == "redis://custom:6380/6"
