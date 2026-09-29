"""
Tests for Phase 2 Week 6: Credential storage in Prism.

Covers:
- TargetService: create, get, list, delete, rotate, fetch_credentials
- Credential separation: sensitive fields → Prism, metadata → Postgres
- No plaintext credentials in Postgres
- Credential injection into scan config at task start
- Credential cleanup after scan completion
- Migration script: existing config_json → Prism
- Fallback behavior when Prism is down
- Target model to_dict never includes credential values
"""
import json
import os
import sys
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mock settings
_mock_settings = MagicMock()
_mock_settings.prism_url = "http://prism-test:8080"
_mock_settings.prism_api_key = "test-key"
_mock_settings.prism_timeout = 5.0
_mock_settings.prism_enabled = True
_mock_settings.prism_fallback_to_minio = False
_mock_settings.prism_cache_ttl = 300
_mock_settings.redis_url = "redis://localhost:6379/0"
_mock_settings.garak_reports_path = "/tmp/test_reports"
_mock_settings.storage_backend = "local"
_mock_settings.database_url = "sqlite:///:memory:"

# ---------------------------------------------------------------------------
# DB fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    """Initialize an in-memory SQLite database with all tables."""
    from database.session import init_db
    engine = init_db(":memory:")
    yield engine
    # Cleanup
    import database.session as sess
    sess._engine = None
    sess._SessionFactory = None


@pytest.fixture
def db_session(db):
    """Provide a database session for test assertions."""
    from database.session import get_db
    with get_db() as session:
        yield session


# ---------------------------------------------------------------------------
# TargetService: credential separation
# ---------------------------------------------------------------------------

class TestTargetCreation:
    """Test that target creation separates credentials from metadata."""

    def test_create_target_stores_metadata_in_postgres(self, db_session):
        """Non-sensitive fields (name, endpoint, body_template) go to Postgres."""
        from services.target_service import TargetService
        from database.models import Target

        svc = TargetService()
        payload = {
            "name": "my-gpt4",
            "type": "rest",
            "endpoint": "https://api.openai.com/v1/chat/completions",
            "body_template": '{"model":"gpt-4o","messages":[{"role":"user","content":"$INPUT"}]}',
            "response_json_field": "$.choices[0].message.content",
        }

        with patch("services.prism_client.prism_available", return_value=False):
            result = svc.create_target("tenant-a", payload)

        assert result["name"] == "my-gpt4"
        assert result["type"] == "rest"
        assert result["endpoint"] == "https://api.openai.com/v1/chat/completions"

        # Verify in DB
        target = db_session.query(Target).filter_by(id=result["target_id"]).first()
        assert target is not None
        assert target.name == "my-gpt4"
        assert target.endpoint == "https://api.openai.com/v1/chat/completions"

    def test_create_target_stores_credentials_in_prism(self, db_session):
        """Sensitive fields go to Prism, not Postgres."""
        from services.target_service import TargetService
        from database.models import Target

        mock_prism = MagicMock()
        mock_prism.store_sync.return_value = "tenant-a/target:tgt_123:credentials"

        svc = TargetService()
        payload = {
            "name": "my-api",
            "type": "rest",
            "endpoint": "https://api.example.com",
            "credentials": {
                "headers": {"Authorization": "Bearer sk-secret-key"},
                "cookies": {"session": "abc123"},
            },
        }

        with patch("services.prism_client.prism_available", return_value=True):
            with patch("services.prism_client.get_prism_client", return_value=mock_prism):
                result = svc.create_target("tenant-a", payload)

        assert result["has_credentials"] is True
        # Verify Prism was called
        mock_prism.store_sync.assert_called_once()
        call_args = mock_prism.store_sync.call_args
        assert call_args[0][0] == "tenant-a"  # tenant_id
        stored_data = json.loads(call_args[0][2])  # data bytes
        assert "Authorization" in stored_data.get("headers", {})

    def test_postgres_has_no_plaintext_credentials(self, db_session):
        """config_json in Postgres must NOT contain credential values."""
        from services.target_service import TargetService
        from database.models import Target

        mock_prism = MagicMock()
        mock_prism.store_sync.return_value = "key"

        svc = TargetService()
        payload = {
            "name": "secret-api",
            "type": "rest",
            "endpoint": "https://api.example.com",
            "credentials": {
                "headers": {"Authorization": "Bearer sk-proj-abc123"},
                "query_params": {"api_key": "dangerous-key"},
            },
        }

        with patch("services.prism_client.prism_available", return_value=True):
            with patch("services.prism_client.get_prism_client", return_value=mock_prism):
                result = svc.create_target("tenant-a", payload)

        target = db_session.query(Target).filter_by(id=result["target_id"]).first()
        # Check that config_json has no credential values
        if target.config_json:
            config_text = target.config_json.lower()
            assert "bearer" not in config_text
            assert "sk-proj" not in config_text
            assert "api_key" not in config_text
            assert "dangerous-key" not in config_text

    def test_target_to_dict_never_includes_credentials(self, db_session):
        """Target.to_dict() response must not contain credential values."""
        from services.target_service import TargetService

        mock_prism = MagicMock()
        mock_prism.store_sync.return_value = "key"

        svc = TargetService()
        payload = {
            "name": "api-with-creds",
            "type": "rest",
            "endpoint": "https://api.example.com",
            "credentials": {
                "headers": {"Authorization": "Bearer secret-token"},
            },
        }

        with patch("services.prism_client.prism_available", return_value=True):
            with patch("services.prism_client.get_prism_client", return_value=mock_prism):
                result = svc.create_target("tenant-a", payload)

        # to_dict should not have credentials
        assert "credentials" not in result
        assert "secret-token" not in json.dumps(result)
        assert result["has_credentials"] is True


class TestTargetCRUD:
    """Test get, list, delete operations."""

    def _create_target(self, svc, tenant_id="t1", name="test-target"):
        payload = {
            "name": name,
            "type": "rest",
            "endpoint": "https://api.example.com",
        }
        with patch("services.prism_client.prism_available", return_value=False):
            return svc.create_target(tenant_id, payload)

    def test_get_target(self, db_session):
        from services.target_service import TargetService
        svc = TargetService()
        created = self._create_target(svc)

        result = svc.get_target("t1", created["target_id"])
        assert result is not None
        assert result["name"] == "test-target"

    def test_get_target_tenant_scoped(self, db_session):
        """Tenant A cannot see Tenant B's targets."""
        from services.target_service import TargetService
        svc = TargetService()
        created = self._create_target(svc, tenant_id="tenant-a")

        result = svc.get_target("tenant-b", created["target_id"])
        assert result is None

    def test_list_targets(self, db_session):
        from services.target_service import TargetService
        svc = TargetService()
        self._create_target(svc, name="target-1")
        self._create_target(svc, name="target-2")

        results = svc.list_targets("t1")
        assert len(results) == 2

    def test_list_targets_tenant_isolated(self, db_session):
        """list_targets only returns targets for the given tenant."""
        from services.target_service import TargetService
        svc = TargetService()
        self._create_target(svc, tenant_id="t1", name="t1-target")
        self._create_target(svc, tenant_id="t2", name="t2-target")

        t1_targets = svc.list_targets("t1")
        t2_targets = svc.list_targets("t2")
        assert len(t1_targets) == 1
        assert t1_targets[0]["name"] == "t1-target"
        assert len(t2_targets) == 1
        assert t2_targets[0]["name"] == "t2-target"

    def test_delete_target(self, db_session):
        from services.target_service import TargetService
        svc = TargetService()
        created = self._create_target(svc)

        with patch("services.prism_client.prism_available", return_value=False):
            result = svc.delete_target("t1", created["target_id"])
        assert result is True

        assert svc.get_target("t1", created["target_id"]) is None

    def test_delete_target_cleans_prism(self, db_session):
        """Deleting a target with credentials also deletes from Prism."""
        from services.target_service import TargetService

        mock_prism = MagicMock()
        mock_prism.store_sync.return_value = "key"
        mock_prism.delete_sync.return_value = True

        svc = TargetService()
        payload = {
            "name": "to-delete",
            "type": "rest",
            "endpoint": "https://api.example.com",
            "credentials": {"headers": {"X-Key": "secret"}},
        }

        with patch("services.prism_client.prism_available", return_value=True):
            with patch("services.prism_client.get_prism_client", return_value=mock_prism):
                created = svc.create_target("t1", payload)
                svc.delete_target("t1", created["target_id"])

        mock_prism.delete_sync.assert_called_once()

    def test_delete_nonexistent_returns_false(self, db_session):
        from services.target_service import TargetService
        svc = TargetService()
        result = svc.delete_target("t1", "nonexistent")
        assert result is False


class TestCredentialRotation:
    """Test credential rotation (atomic swap)."""

    def test_rotate_deletes_old_stores_new(self, db_session):
        """Rotation deletes old Prism credentials before storing new ones."""
        from services.target_service import TargetService

        mock_prism = MagicMock()
        mock_prism.store_sync.return_value = "key"
        mock_prism.delete_sync.return_value = True

        svc = TargetService()
        payload = {
            "name": "rotate-target",
            "type": "rest",
            "endpoint": "https://api.example.com",
            "credentials": {"headers": {"Authorization": "Bearer old-key"}},
        }

        with patch("services.prism_client.prism_available", return_value=True):
            with patch("services.prism_client.get_prism_client", return_value=mock_prism):
                created = svc.create_target("t1", payload)
                assert mock_prism.store_sync.call_count == 1

                result = svc.rotate_credentials(
                    "t1",
                    created["target_id"],
                    {"headers": {"Authorization": "Bearer new-key"}},
                )

        assert result is True
        # 1 delete (old) + 2 stores (create + rotate)
        mock_prism.delete_sync.assert_called_once()
        assert mock_prism.store_sync.call_count == 2

    def test_rotate_nonexistent_target(self, db_session):
        from services.target_service import TargetService
        svc = TargetService()
        result = svc.rotate_credentials("t1", "nonexistent", {"headers": {}})
        assert result is False


class TestCredentialFetch:
    """Test credential fetching for scan execution."""

    def test_fetch_credentials_from_prism(self, db_session):
        """fetch_credentials returns decrypted credentials from Prism."""
        from services.target_service import TargetService

        creds_data = {"headers": {"Authorization": "Bearer sk-test"}}
        mock_prism = MagicMock()
        mock_prism.store_sync.return_value = "key"
        mock_prism.fetch_sync.return_value = json.dumps(creds_data).encode()

        svc = TargetService()
        payload = {
            "name": "fetch-target",
            "type": "rest",
            "endpoint": "https://api.example.com",
            "credentials": creds_data,
        }

        with patch("services.prism_client.prism_available", return_value=True):
            with patch("services.prism_client.get_prism_client", return_value=mock_prism):
                created = svc.create_target("t1", payload)
                fetched = svc.fetch_credentials("t1", created["target_id"])

        assert fetched is not None
        assert fetched["headers"]["Authorization"] == "Bearer sk-test"

    def test_fetch_credentials_no_prism_returns_none(self, db_session):
        """When Prism is down, fetch_credentials returns None."""
        from services.target_service import TargetService

        svc = TargetService()
        with patch("services.prism_client.prism_available", return_value=False):
            result = svc.fetch_credentials("t1", "some-target")
        assert result is None

    def test_fetch_credentials_target_without_creds(self, db_session):
        """Target with no credentials returns None."""
        from services.target_service import TargetService
        svc = TargetService()
        payload = {
            "name": "no-creds",
            "type": "rest",
            "endpoint": "https://api.example.com",
        }
        with patch("services.prism_client.prism_available", return_value=False):
            created = svc.create_target("t1", payload)

        with patch("services.prism_client.prism_available", return_value=True):
            result = svc.fetch_credentials("t1", created["target_id"])
        assert result is None


# ---------------------------------------------------------------------------
# Scan task: credential injection
# ---------------------------------------------------------------------------

class TestScanTaskCredentialInjection:
    """Test that scan_task injects credentials and strips them from DB."""

    def test_credentials_injected_into_scan_config(self, db):
        """Credentials are fetched from Prism and injected before sending to garak."""
        from tasks.scan_task import execute_scan

        creds = {"headers": {"Authorization": "Bearer injected-key"}}
        mock_target_svc = MagicMock()
        mock_target_svc.fetch_credentials.return_value = creds

        # Mock the garak service call
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        config = {
            "target_id": "tgt_abc",
            "target_type": "rest",
            "target_name": "test",
            "probes": ["dan.Dan_11_0"],
        }

        # Track what was sent to garak (deep copy to capture at call time,
        # because injected_config.pop("credentials") mutates the dict later)
        import copy
        sent_configs = []

        def capture_post(path, json=None, **kwargs):
            if json:
                sent_configs.append(copy.deepcopy(json))
            return mock_response

        with patch("services.target_service.get_target_service", return_value=mock_target_svc):
            with patch("httpx.Client") as MockClient:
                ctx = MockClient.return_value.__enter__.return_value
                ctx.post.side_effect = capture_post
                # Make SSE stream return empty to end quickly
                mock_stream = MagicMock()
                mock_stream.__enter__ = MagicMock(return_value=mock_stream)
                mock_stream.__exit__ = MagicMock(return_value=False)
                mock_stream.status_code = 200
                mock_stream.iter_lines.return_value = []
                ctx.stream.return_value = mock_stream

                with patch("tasks.scan_task._sync_scan_to_db"):
                    with patch("tasks.scan_task._publish_progress"):
                        result = execute_scan(
                            "scan-1", config, tenant_id="t1",
                            garak_service_url="http://garak:9090",
                        )

                # Verify credentials were injected into the POST to garak
                assert len(sent_configs) == 1
                assert sent_configs[0]["config"]["credentials"] == creds

    def test_credentials_not_in_db_config(self, db):
        """config_json saved to DB must NOT contain credentials."""
        from tasks.scan_task import execute_scan

        db_configs_saved = []

        def capture_sync(scan_id, tenant_id, status, config_dict=None, **kwargs):
            if config_dict:
                db_configs_saved.append(config_dict)

        config = {
            "target_id": "tgt_abc",
            "target_type": "rest",
            "target_name": "test",
            "credentials": {"headers": {"Authorization": "Bearer should-not-persist"}},
            "probes": ["dan.Dan_11_0"],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.Client") as MockClient:
            ctx = MockClient.return_value.__enter__.return_value
            ctx.post.return_value = mock_response
            mock_stream = MagicMock()
            mock_stream.__enter__ = MagicMock(return_value=mock_stream)
            mock_stream.__exit__ = MagicMock(return_value=False)
            mock_stream.status_code = 200
            mock_stream.iter_lines.return_value = []
            ctx.stream.return_value = mock_stream

            with patch("tasks.scan_task._sync_scan_to_db", side_effect=capture_sync):
                with patch("tasks.scan_task._publish_progress"):
                    execute_scan(
                        "scan-2", config, tenant_id="t1",
                        garak_service_url="http://garak:9090",
                    )

        # None of the DB configs should contain credentials
        for cfg in db_configs_saved:
            assert "credentials" not in cfg
            cfg_text = json.dumps(cfg).lower()
            assert "bearer" not in cfg_text
            assert "should-not-persist" not in cfg_text


# ---------------------------------------------------------------------------
# Migration script tests
# ---------------------------------------------------------------------------

class TestCredentialMigration:
    """Test the credential migration script."""

    def test_migration_extracts_credentials(self, db_session):
        """Migration extracts sensitive fields from config_json and stores in Prism."""
        from database.models import Scan
        from database.migrate_credentials_to_prism import migrate

        # Create a scan with credentials in config_json
        scan = Scan(
            id="scan-migrate-1",
            tenant_id="t1",
            target_type="rest",
            target_name="test",
            status="completed",
            config_json=json.dumps({
                "target_type": "rest",
                "endpoint": "https://api.example.com",
                "headers": {"Authorization": "Bearer sk-old-key"},
                "api_key": "dangerous-plaintext",
            }),
        )
        db_session.add(scan)
        db_session.commit()

        mock_prism = MagicMock()

        with patch("services.prism_client.prism_available", return_value=True):
            with patch("services.prism_client.get_prism_client", return_value=mock_prism):
                summary = migrate(dry_run=False)

        assert summary["migrated"] == 1
        mock_prism.store_sync.assert_called_once()

        # Verify config_json was cleaned
        db_session.refresh(scan)
        clean_config = json.loads(scan.config_json)
        assert "headers" not in clean_config
        assert "api_key" not in clean_config
        assert "endpoint" in clean_config  # non-sensitive kept

    def test_migration_dry_run(self, db_session):
        """Dry run logs changes without making them."""
        from database.models import Scan
        from database.migrate_credentials_to_prism import migrate

        scan = Scan(
            id="scan-dry",
            tenant_id="t1",
            target_type="rest",
            target_name="test",
            status="completed",
            config_json=json.dumps({
                "headers": {"Authorization": "Bearer sk-key"},
            }),
        )
        db_session.add(scan)
        db_session.commit()

        summary = migrate(dry_run=True)
        assert summary["migrated"] == 1

        # Config should NOT be modified in dry run
        db_session.refresh(scan)
        config = json.loads(scan.config_json)
        assert "headers" in config  # Still there

    def test_migration_skips_clean_configs(self, db_session):
        """Scans without credentials are skipped."""
        from database.models import Scan
        from database.migrate_credentials_to_prism import migrate

        scan = Scan(
            id="scan-clean",
            tenant_id="t1",
            target_type="rest",
            target_name="test",
            status="completed",
            config_json=json.dumps({"target_type": "rest", "probes": ["dan"]}),
        )
        db_session.add(scan)
        db_session.commit()

        summary = migrate(dry_run=False)
        assert summary["skipped"] == 1
        assert summary["migrated"] == 0


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestHelperFunctions:
    """Test internal helper functions."""

    def test_extract_credentials_with_creds(self):
        from services.target_service import _extract_credentials
        payload = {
            "name": "test",
            "credentials": {
                "headers": {"Authorization": "Bearer sk-123"},
                "cookies": {"session": "abc"},
                "query_params": {},
            },
        }
        creds = _extract_credentials(payload)
        assert creds is not None
        assert "headers" in creds
        assert "cookies" in creds
        assert "query_params" not in creds  # empty, filtered out

    def test_extract_credentials_none(self):
        from services.target_service import _extract_credentials
        assert _extract_credentials({"name": "test"}) is None
        assert _extract_credentials({"credentials": {}}) is None

    def test_strip_credentials(self):
        from services.target_service import _strip_credentials
        payload = {
            "name": "test",
            "endpoint": "https://example.com",
            "credentials": {"headers": {"Authorization": "Bearer sk-123"}},
        }
        clean = _strip_credentials(payload)
        assert "credentials" not in clean
        assert clean["name"] == "test"
        # Original unchanged
        assert "credentials" in payload

    def test_prism_credential_key(self):
        from services.target_service import _prism_credential_key
        assert _prism_credential_key("tgt_abc123") == "target:tgt_abc123:credentials"


# ---------------------------------------------------------------------------
# Target model tests
# ---------------------------------------------------------------------------

class TestTargetModel:
    """Test the Target SQLAlchemy model."""

    def test_target_table_created(self, db_session):
        """Target table exists after init_db."""
        from database.models import Target
        # Should not raise
        db_session.query(Target).count()

    def test_target_to_dict_shape(self, db_session):
        from database.models import Target

        target = Target(
            id="tgt_test",
            tenant_id="t1",
            name="test-target",
            target_type="rest",
            endpoint="https://api.example.com",
            body_template='{"model":"gpt-4"}',
            response_json_field="$.choices[0]",
            credential_prism_key="t1/target:tgt_test:credentials",
            has_credentials=True,
            created_at="2025-01-01T00:00:00",
            updated_at="2025-01-01T00:00:00",
        )
        db_session.add(target)
        db_session.commit()

        d = target.to_dict()
        assert d["target_id"] == "tgt_test"
        assert d["type"] == "rest"
        assert d["has_credentials"] is True
        assert "credential_prism_key" not in d  # Never exposed
        assert "credentials" not in d


class TestSensitiveFieldExtraction:
    """Test the migration helper for extracting sensitive fields."""

    def test_extract_nested_credentials(self):
        from database.migrate_credentials_to_prism import _extract_sensitive
        config = {
            "target_type": "rest",
            "endpoint": "https://api.example.com",
            "credentials": {
                "headers": {"Authorization": "Bearer sk-123"},
                "cookies": {"session": "abc"},
            },
            "probes": ["dan"],
        }
        creds, clean = _extract_sensitive(config)
        assert "headers" in creds
        assert "cookies" in creds
        assert "endpoint" in clean
        assert "probes" in clean
        assert "credentials" not in clean  # parent key removed

    def test_extract_top_level_sensitive(self):
        from database.migrate_credentials_to_prism import _extract_sensitive
        config = {
            "target_type": "rest",
            "headers": {"Authorization": "Bearer sk-123"},
            "api_key": "plain-key",
        }
        creds, clean = _extract_sensitive(config)
        assert creds["headers"]["Authorization"] == "Bearer sk-123"
        assert creds["api_key"] == "plain-key"
        assert "headers" not in clean
        assert "api_key" not in clean
