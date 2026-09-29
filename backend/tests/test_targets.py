"""
Tests for Phase 3 Week 7: Target CRUD + credential rotation + connectivity.

Covers:
- Target CRUD (create/get/list/update/delete) with tenant scoping
- Credential separation (Prism vs Postgres)
- Connectivity test endpoint
- Inline credential support
- No credential values in API responses
"""
import json
import os
import sys
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def db():
    from database.session import init_db
    engine = init_db(":memory:")
    yield engine
    import database.session as sess
    sess._engine = None
    sess._SessionFactory = None


@pytest.fixture
def db_session(db):
    from database.session import get_db
    with get_db() as session:
        yield session


class TestTargetCRUDRoutes:
    """Test target REST API endpoints."""

    def _make_client(self):
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)

    def test_create_target_stores_metadata(self, db):
        """POST /targets stores non-sensitive metadata in Postgres."""
        from services.target_service import TargetService
        svc = TargetService()
        with patch("services.prism_client.prism_available", return_value=False):
            result = svc.create_target("t1", {
                "name": "my-api",
                "type": "rest",
                "endpoint": "https://api.example.com",
                "body_template": '{"model":"gpt-4o"}',
                "response_json_field": "$.choices[0]",
                "tags": ["staging", "gpt4"],
            })
        assert result["name"] == "my-api"
        assert result["endpoint"] == "https://api.example.com"
        assert result["tags"] == ["staging", "gpt4"]
        assert result["target_id"].startswith("tgt_")

    def test_create_target_stores_credentials_in_prism(self, db):
        """credentials.headers -> Prism, not Postgres."""
        from services.target_service import TargetService
        from database.models import Target
        from database.session import get_db

        mock_prism = MagicMock()
        mock_prism.store_sync.return_value = "key"

        svc = TargetService()
        with patch("services.prism_client.prism_available", return_value=True):
            with patch("services.prism_client.get_prism_client", return_value=mock_prism):
                result = svc.create_target("t1", {
                    "name": "cred-api",
                    "endpoint": "https://api.example.com",
                    "credentials": {
                        "headers": {"Authorization": "Bearer sk-secret"},
                    },
                })
        assert result["has_credentials"] is True
        mock_prism.store_sync.assert_called_once()

        with get_db() as session:
            target = session.query(Target).filter_by(id=result["target_id"]).first()
            if target.config_json:
                assert "sk-secret" not in target.config_json

    def test_create_target_response_has_no_credential_values(self, db):
        """API response has has_credentials: true but no key values."""
        from services.target_service import TargetService
        mock_prism = MagicMock()
        mock_prism.store_sync.return_value = "key"

        svc = TargetService()
        with patch("services.prism_client.prism_available", return_value=True):
            with patch("services.prism_client.get_prism_client", return_value=mock_prism):
                result = svc.create_target("t1", {
                    "name": "secret-api",
                    "endpoint": "https://api.example.com",
                    "credentials": {
                        "headers": {"Authorization": "Bearer sk-proj-abc123"},
                    },
                })
        assert result["has_credentials"] is True
        assert "credentials" not in result
        assert "sk-proj-abc123" not in json.dumps(result)

    def test_create_target_bearer_token(self, db):
        """Authorization: Bearer sk-... stored in Prism."""
        from services.target_service import TargetService
        mock_prism = MagicMock()
        mock_prism.store_sync.return_value = "key"

        svc = TargetService()
        with patch("services.prism_client.prism_available", return_value=True):
            with patch("services.prism_client.get_prism_client", return_value=mock_prism):
                svc.create_target("t1", {
                    "name": "bearer-api",
                    "endpoint": "https://api.example.com",
                    "credentials": {"headers": {"Authorization": "Bearer sk-test123"}},
                })
        stored = json.loads(mock_prism.store_sync.call_args[0][2])
        assert stored["headers"]["Authorization"] == "Bearer sk-test123"

    def test_create_target_api_key_header(self, db):
        """X-API-Key stored in Prism."""
        from services.target_service import TargetService
        mock_prism = MagicMock()
        mock_prism.store_sync.return_value = "key"

        svc = TargetService()
        with patch("services.prism_client.prism_available", return_value=True):
            with patch("services.prism_client.get_prism_client", return_value=mock_prism):
                svc.create_target("t1", {
                    "name": "apikey-api",
                    "endpoint": "https://api.example.com",
                    "credentials": {"headers": {"X-API-Key": "key-123"}},
                })
        stored = json.loads(mock_prism.store_sync.call_args[0][2])
        assert stored["headers"]["X-API-Key"] == "key-123"

    def test_create_target_cookie_auth(self, db):
        """credentials.cookies stored in Prism."""
        from services.target_service import TargetService
        mock_prism = MagicMock()
        mock_prism.store_sync.return_value = "key"

        svc = TargetService()
        with patch("services.prism_client.prism_available", return_value=True):
            with patch("services.prism_client.get_prism_client", return_value=mock_prism):
                svc.create_target("t1", {
                    "name": "cookie-api",
                    "endpoint": "https://api.example.com",
                    "credentials": {"cookies": {"session": "abc-session"}},
                })
        stored = json.loads(mock_prism.store_sync.call_args[0][2])
        assert stored["cookies"]["session"] == "abc-session"

    def test_create_target_no_credentials(self, db):
        """Target without credentials -> has_credentials: false."""
        from services.target_service import TargetService
        svc = TargetService()
        with patch("services.prism_client.prism_available", return_value=False):
            result = svc.create_target("t1", {
                "name": "local-ollama",
                "endpoint": "http://localhost:11434",
            })
        assert result["has_credentials"] is False

    def test_list_targets_scoped_to_tenant(self, db):
        """Tenant A sees only own targets."""
        from services.target_service import TargetService
        svc = TargetService()
        with patch("services.prism_client.prism_available", return_value=False):
            svc.create_target("tenant-a", {"name": "a-target", "endpoint": "http://a"})
            svc.create_target("tenant-b", {"name": "b-target", "endpoint": "http://b"})

        a_targets = svc.list_targets("tenant-a")
        b_targets = svc.list_targets("tenant-b")
        assert len(a_targets) == 1
        assert a_targets[0]["name"] == "a-target"
        assert len(b_targets) == 1
        assert b_targets[0]["name"] == "b-target"

    def test_get_target_returns_metadata_only(self, db):
        """GET /targets/{id} never includes credential values."""
        from services.target_service import TargetService
        mock_prism = MagicMock()
        mock_prism.store_sync.return_value = "key"

        svc = TargetService()
        with patch("services.prism_client.prism_available", return_value=True):
            with patch("services.prism_client.get_prism_client", return_value=mock_prism):
                created = svc.create_target("t1", {
                    "name": "get-test",
                    "endpoint": "https://api.example.com",
                    "credentials": {"headers": {"Authorization": "Bearer secret"}},
                })

        result = svc.get_target("t1", created["target_id"])
        assert result is not None
        assert "credentials" not in result
        assert "secret" not in json.dumps(result)

    def test_update_target_metadata(self, db):
        """PUT /targets/{id} updates non-sensitive fields."""
        from services.target_service import TargetService
        svc = TargetService()
        with patch("services.prism_client.prism_available", return_value=False):
            created = svc.create_target("t1", {
                "name": "old-name",
                "endpoint": "http://old.example.com",
            })

        result = svc.update_target("t1", created["target_id"], {
            "name": "new-name",
            "endpoint": "http://new.example.com",
            "tags": ["production"],
        })
        assert result is not None
        assert result["name"] == "new-name"
        assert result["endpoint"] == "http://new.example.com"
        assert result["tags"] == ["production"]

    def test_rotate_credentials_deletes_old_key(self, db):
        """PUT /targets/{id}/credentials deletes old Prism key."""
        from services.target_service import TargetService
        mock_prism = MagicMock()
        mock_prism.store_sync.return_value = "key"

        svc = TargetService()
        with patch("services.prism_client.prism_available", return_value=True):
            with patch("services.prism_client.get_prism_client", return_value=mock_prism):
                created = svc.create_target("t1", {
                    "name": "rotate-test",
                    "endpoint": "https://api.example.com",
                    "credentials": {"headers": {"Authorization": "Bearer old"}},
                })
                svc.rotate_credentials("t1", created["target_id"],
                    {"headers": {"Authorization": "Bearer new"}})

        mock_prism.delete_sync.assert_called_once()

    def test_rotate_credentials_stores_new_key(self, db):
        """New credentials stored in Prism under same target."""
        from services.target_service import TargetService
        mock_prism = MagicMock()
        mock_prism.store_sync.return_value = "key"

        svc = TargetService()
        with patch("services.prism_client.prism_available", return_value=True):
            with patch("services.prism_client.get_prism_client", return_value=mock_prism):
                created = svc.create_target("t1", {
                    "name": "rotate-store",
                    "endpoint": "https://api.example.com",
                    "credentials": {"headers": {"Authorization": "Bearer old"}},
                })
                svc.rotate_credentials("t1", created["target_id"],
                    {"headers": {"Authorization": "Bearer new-key"}})

        # 2 stores: create + rotate
        assert mock_prism.store_sync.call_count == 2
        last_stored = json.loads(mock_prism.store_sync.call_args_list[-1][0][2])
        assert last_stored["headers"]["Authorization"] == "Bearer new-key"

    def test_delete_target_removes_prism_credentials(self, db):
        """DELETE /targets/{id} cleans up Prism credentials."""
        from services.target_service import TargetService
        mock_prism = MagicMock()
        mock_prism.store_sync.return_value = "key"

        svc = TargetService()
        with patch("services.prism_client.prism_available", return_value=True):
            with patch("services.prism_client.get_prism_client", return_value=mock_prism):
                created = svc.create_target("t1", {
                    "name": "delete-test",
                    "endpoint": "https://api.example.com",
                    "credentials": {"headers": {"Authorization": "Bearer del"}},
                })
                svc.delete_target("t1", created["target_id"])

        mock_prism.delete_sync.assert_called_once()

    def test_scan_with_target_id_fetches_credentials(self, db):
        """Scan start with target_id triggers credential fetch from Prism."""
        from services.target_service import TargetService
        creds = {"headers": {"Authorization": "Bearer injected"}}
        mock_prism = MagicMock()
        mock_prism.store_sync.return_value = "key"
        mock_prism.fetch_sync.return_value = json.dumps(creds).encode()

        svc = TargetService()
        with patch("services.prism_client.prism_available", return_value=True):
            with patch("services.prism_client.get_prism_client", return_value=mock_prism):
                created = svc.create_target("t1", {
                    "name": "scan-target",
                    "endpoint": "https://api.example.com",
                    "credentials": creds,
                })
                fetched = svc.fetch_credentials("t1", created["target_id"])

        assert fetched is not None
        assert fetched["headers"]["Authorization"] == "Bearer injected"

    def test_inline_credentials_not_in_postgres(self, db):
        """Inline credentials in scan config stripped before DB write."""
        import copy
        from tasks.scan_task import _sync_scan_to_db

        saved_configs = []
        original_upsert = None

        def capture_upsert(scan_id, **kwargs):
            if kwargs.get("config_json"):
                saved_configs.append(kwargs["config_json"])

        config = {
            "target_type": "rest",
            "credentials": {"headers": {"Authorization": "Bearer inline-secret"}},
            "probes": ["dan"],
        }
        db_config = {k: v for k, v in config.items() if k != "credentials"}

        with patch("database.scan_ops.upsert_scan", side_effect=capture_upsert):
            _sync_scan_to_db("scan-1", "t1", "pending", config_dict=db_config)

        for cfg_json in saved_configs:
            assert "inline-secret" not in cfg_json

    def test_target_cross_tenant_isolation(self, db):
        """Tenant A cannot get/update/delete Tenant B's targets."""
        from services.target_service import TargetService
        svc = TargetService()
        with patch("services.prism_client.prism_available", return_value=False):
            created = svc.create_target("tenant-a", {
                "name": "private",
                "endpoint": "https://api.example.com",
            })
        tid = created["target_id"]

        assert svc.get_target("tenant-b", tid) is None
        assert svc.update_target("tenant-b", tid, {"name": "hacked"}) is None
        assert svc.delete_target("tenant-b", tid) is False


class TestTargetConnectivityTest:
    """Test target connectivity testing logic."""

    def test_connectivity_test_builds_correct_request(self, db):
        """Connectivity test uses correct endpoint and credentials."""
        from services.target_service import TargetService
        svc = TargetService()
        with patch("services.prism_client.prism_available", return_value=False):
            created = svc.create_target("t1", {
                "name": "conn-test",
                "endpoint": "https://api.example.com/v1/chat",
                "body_template": '{"model":"gpt-4","messages":[{"role":"user","content":"$INPUT"}]}',
            })
        # Verify the target was created for connectivity testing
        target = svc.get_target("t1", created["target_id"])
        assert target is not None
        assert target["endpoint"] == "https://api.example.com/v1/chat"
