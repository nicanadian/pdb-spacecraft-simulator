"""Tests for Aerie GraphQL client."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from sim.io.aerie_client import (
    ActivityInput,
    AerieClient,
    AerieClientError,
    AerieConfig,
    AerieConnectionError,
    AerieQueryError,
)


class TestAerieConfig:
    """Test AerieConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AerieConfig()

        assert config.host == "localhost"
        assert config.port == 9000
        assert config.use_ssl is False
        assert config.auth_token is None

    def test_graphql_url_http(self):
        """Test GraphQL URL generation (HTTP)."""
        config = AerieConfig(host="localhost", port=9000, use_ssl=False)

        assert config.graphql_url == "http://localhost:9000/v1/graphql"

    def test_graphql_url_https(self):
        """Test GraphQL URL generation (HTTPS)."""
        config = AerieConfig(host="aerie.example.com", port=443, use_ssl=True)

        assert config.graphql_url == "https://aerie.example.com:443/v1/graphql"

    def test_from_env_defaults(self):
        """Test config from environment with defaults."""
        with patch.dict("os.environ", {}, clear=True):
            config = AerieConfig.from_env()

        assert config.host == "localhost"
        assert config.port == 9000

    def test_from_env_with_values(self):
        """Test config from environment variables."""
        env = {
            "AERIE_HOST": "aerie.example.com",
            "AERIE_GATEWAY_PORT": "8080",
            "AERIE_USE_SSL": "true",
            "AERIE_AUTH_TOKEN": "test-token-123",
        }

        with patch.dict("os.environ", env, clear=True):
            config = AerieConfig.from_env()

        assert config.host == "aerie.example.com"
        assert config.port == 8080
        assert config.use_ssl is True
        assert config.auth_token == "test-token-123"

    def test_from_env_file(self, tmp_path):
        """Test config from .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("""
AERIE_HOST=test-host
AERIE_GATEWAY_PORT=9999
""")

        with patch.dict("os.environ", {}, clear=True):
            config = AerieConfig.from_env(env_path=env_file)

        assert config.host == "test-host"
        assert config.port == 9999


class TestActivityInput:
    """Test ActivityInput."""

    def test_format_interval_hours(self):
        """Test interval formatting with hours."""
        td = timedelta(hours=2, minutes=30, seconds=45)
        result = ActivityInput._format_interval(td)

        assert result == "2:30:45"

    def test_format_interval_with_microseconds(self):
        """Test interval formatting with microseconds."""
        td = timedelta(hours=1, minutes=15, seconds=30, microseconds=500000)
        result = ActivityInput._format_interval(td)

        assert result == "1:15:30.500000"

    def test_to_insert_input(self):
        """Test conversion to GraphQL insert input."""
        activity = ActivityInput(
            activity_type="eo_collect",
            start_offset=timedelta(hours=1),
            arguments={"target_id": "target_001"},
        )

        input_dict = activity.to_insert_input(plan_id=42)

        assert input_dict["plan_id"] == 42
        assert input_dict["type"] == "eo_collect"
        assert input_dict["start_offset"] == "1:00:00"
        assert input_dict["arguments"] == {"target_id": "target_001"}

    def test_to_insert_input_with_anchor(self):
        """Test conversion with anchor ID."""
        activity = ActivityInput(
            activity_type="downlink",
            start_offset=timedelta(minutes=10),
            anchor_id=5,
            anchored_to_start=False,
        )

        input_dict = activity.to_insert_input(plan_id=42)

        assert input_dict["anchor_id"] == 5
        assert input_dict["anchored_to_start"] is False


class TestAerieClientErrors:
    """Test Aerie client error classes."""

    def test_aerie_client_error(self):
        """Test base error class."""
        error = AerieClientError("Test error")
        assert str(error) == "Test error"

    def test_aerie_connection_error(self):
        """Test connection error."""
        error = AerieConnectionError("Connection refused")
        assert isinstance(error, AerieClientError)
        assert "Connection refused" in str(error)

    def test_aerie_query_error(self):
        """Test query error with errors list."""
        errors = [{"message": "Field not found"}, {"message": "Invalid type"}]
        error = AerieQueryError("Query failed", errors)

        assert isinstance(error, AerieClientError)
        assert error.errors == errors
        assert len(error.errors) == 2


class TestAerieClientExecution:
    """Test AerieClient._execute method."""

    @pytest.fixture
    def client(self):
        """Create client for testing."""
        return AerieClient(AerieConfig())

    def test_execute_success(self, client):
        """Test successful query execution."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "data": {"plan": [{"id": 1, "name": "test"}]}
        }).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("sim.io.aerie_client.urlopen", return_value=mock_response):
            result = client._execute("query { plan { id name } }")

        assert result == {"plan": [{"id": 1, "name": "test"}]}

    def test_execute_with_variables(self, client):
        """Test query execution with variables."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "data": {"plan_by_pk": {"id": 1}}
        }).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("sim.io.aerie_client.urlopen", return_value=mock_response):
            result = client._execute(
                "query getPlan($id: Int!) { plan_by_pk(id: $id) { id } }",
                {"id": 1},
            )

        assert result == {"plan_by_pk": {"id": 1}}

    def test_execute_graphql_errors(self, client):
        """Test handling of GraphQL errors in response."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "errors": [{"message": "Field 'foo' not found"}]
        }).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("sim.io.aerie_client.urlopen", return_value=mock_response):
            with pytest.raises(AerieQueryError) as exc_info:
                client._execute("query { foo }")

        assert "Field 'foo' not found" in str(exc_info.value)
        assert len(exc_info.value.errors) == 1

    def test_execute_http_error(self, client):
        """Test handling of HTTP errors."""
        mock_error = HTTPError(
            url="http://localhost:9000/v1/graphql",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=MagicMock(read=MagicMock(return_value=b"Unauthorized")),
        )

        with patch("sim.io.aerie_client.urlopen", side_effect=mock_error):
            with pytest.raises(AerieQueryError) as exc_info:
                client._execute("query { plan { id } }")

        assert "HTTP 401" in str(exc_info.value)

    def test_execute_connection_error(self, client):
        """Test handling of connection errors."""
        with patch("sim.io.aerie_client.urlopen", side_effect=URLError("Connection refused")):
            with pytest.raises(AerieConnectionError) as exc_info:
                client._execute("query { plan { id } }")

        assert "Connection refused" in str(exc_info.value)

    def test_execute_with_auth_token(self):
        """Test that auth token is included in headers."""
        config = AerieConfig(auth_token="test-token")
        client = AerieClient(config)

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"data": {}}).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("sim.io.aerie_client.urlopen", return_value=mock_response) as mock_urlopen:
            with patch("sim.io.aerie_client.Request") as mock_request:
                mock_request.return_value = MagicMock()
                client._execute("query { plan { id } }")

                # Check that Request was called with auth header
                call_kwargs = mock_request.call_args
                headers = call_kwargs[1]["headers"]
                assert "Authorization" in headers
                assert headers["Authorization"] == "Bearer test-token"


class TestAerieClientMissionModels:
    """Test mission model methods."""

    @pytest.fixture
    def client(self):
        """Create client with mocked execute."""
        client = AerieClient(AerieConfig())
        client._execute = MagicMock()
        return client

    def test_list_mission_models(self, client):
        """Test listing mission models."""
        client._execute.return_value = {
            "mission_model": [
                {"id": 1, "name": "Model A"},
                {"id": 2, "name": "Model B"},
            ]
        }

        models = client.list_mission_models()

        assert len(models) == 2
        assert models[0]["name"] == "Model A"

    def test_get_mission_model(self, client):
        """Test getting mission model by ID."""
        client._execute.return_value = {
            "mission_model_by_pk": {"id": 1, "name": "Model A"}
        }

        model = client.get_mission_model(1)

        assert model["id"] == 1
        assert model["name"] == "Model A"

    def test_get_mission_model_not_found(self, client):
        """Test getting non-existent mission model."""
        client._execute.return_value = {"mission_model_by_pk": None}

        model = client.get_mission_model(999)

        assert model is None


class TestAerieClientPlans:
    """Test plan methods."""

    @pytest.fixture
    def client(self):
        """Create client with mocked execute."""
        client = AerieClient(AerieConfig())
        client._execute = MagicMock()
        return client

    def test_list_plans(self, client):
        """Test listing plans."""
        client._execute.return_value = {
            "plan": [
                {"id": 1, "name": "Plan A"},
                {"id": 2, "name": "Plan B"},
            ]
        }

        plans = client.list_plans()

        assert len(plans) == 2

    def test_find_plan_by_name_found(self, client):
        """Test finding plan by name."""
        client._execute.return_value = {
            "plan": [{"id": 1, "name": "Test Plan"}]
        }

        plan = client.find_plan_by_name("Test Plan")

        assert plan is not None
        assert plan["id"] == 1

    def test_find_plan_by_name_not_found(self, client):
        """Test finding non-existent plan by name."""
        client._execute.return_value = {"plan": []}

        plan = client.find_plan_by_name("Nonexistent")

        assert plan is None

    def test_get_plan(self, client):
        """Test getting plan by ID."""
        client._execute.return_value = {
            "plan_by_pk": {
                "id": 1,
                "name": "Test Plan",
                "activity_directives": [],
            }
        }

        plan = client.get_plan(1)

        assert plan["id"] == 1

    def test_create_plan(self, client):
        """Test creating a plan."""
        client._execute.return_value = {
            "insert_plan_one": {"id": 42}
        }

        start_time = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        duration = timedelta(hours=24)

        plan_id = client.create_plan(
            name="New Plan",
            model_id=1,
            start_time=start_time,
            duration=duration,
        )

        assert plan_id == 42

    def test_create_plan_no_id_returned(self, client):
        """Test create_plan error when no ID returned."""
        client._execute.return_value = {"insert_plan_one": {}}

        with pytest.raises(AerieClientError, match="no ID returned"):
            client.create_plan(
                name="New Plan",
                model_id=1,
                start_time=datetime.now(timezone.utc),
                duration=timedelta(hours=24),
            )

    def test_delete_plan_success(self, client):
        """Test deleting a plan."""
        client._execute.return_value = {
            "delete_plan_by_pk": {"id": 1}
        }

        result = client.delete_plan(1)

        assert result is True

    def test_delete_plan_not_found(self, client):
        """Test deleting non-existent plan."""
        client._execute.return_value = {"delete_plan_by_pk": None}

        result = client.delete_plan(999)

        assert result is False


class TestAerieClientActivities:
    """Test activity methods."""

    @pytest.fixture
    def client(self):
        """Create client with mocked execute."""
        client = AerieClient(AerieConfig())
        client._execute = MagicMock()
        return client

    def test_insert_activity(self, client):
        """Test inserting single activity."""
        client._execute.return_value = {
            "insert_activity_directive_one": {"id": 100}
        }

        activity_id = client.insert_activity(
            plan_id=1,
            activity_type="eo_collect",
            start_offset=timedelta(hours=1),
            arguments={"target_id": "T001"},
        )

        assert activity_id == 100

    def test_insert_activities_batch(self, client):
        """Test batch activity insertion."""
        client._execute.return_value = {
            "insert_activity_directive": {
                "returning": [
                    {"id": 100},
                    {"id": 101},
                    {"id": 102},
                ]
            }
        }

        activities = [
            ActivityInput("eo_collect", timedelta(hours=1)),
            ActivityInput("downlink", timedelta(hours=2)),
            ActivityInput("idle", timedelta(hours=3)),
        ]

        ids = client.insert_activities_batch(1, activities)

        assert ids == [100, 101, 102]

    def test_insert_activities_batch_empty(self, client):
        """Test batch insertion with empty list."""
        ids = client.insert_activities_batch(1, [])

        assert ids == []
        client._execute.assert_not_called()

    def test_delete_activity(self, client):
        """Test deleting activity."""
        client._execute.return_value = {
            "delete_activity_directive_by_pk": {"id": 100}
        }

        result = client.delete_activity(100, 1)

        assert result is True


class TestAerieClientScheduling:
    """Test scheduling methods."""

    @pytest.fixture
    def client(self):
        """Create client with mocked execute."""
        client = AerieClient(AerieConfig())
        client._execute = MagicMock()
        return client

    def test_get_scheduling_specification(self, client):
        """Test getting scheduling specification."""
        client._execute.return_value = {
            "scheduling_specification": [
                {"id": 1, "plan_id": 42}
            ]
        }

        spec = client.get_scheduling_specification(42)

        assert spec["id"] == 1

    def test_get_scheduling_specification_not_found(self, client):
        """Test getting non-existent scheduling specification."""
        client._execute.return_value = {"scheduling_specification": []}

        spec = client.get_scheduling_specification(999)

        assert spec is None

    def test_create_scheduling_specification(self, client):
        """Test creating scheduling specification."""
        client._execute.return_value = {
            "insert_scheduling_specification_one": {"id": 10}
        }

        spec_id = client.create_scheduling_specification(
            plan_id=42,
            plan_revision=1,
            horizon_start=datetime(2025, 1, 15, tzinfo=timezone.utc),
            horizon_end=datetime(2025, 1, 16, tzinfo=timezone.utc),
        )

        assert spec_id == 10

    def test_run_scheduler(self, client):
        """Test triggering scheduler."""
        client._execute.return_value = {
            "schedule": {
                "analysisId": 5,
                "reason": "Scheduling started",
            }
        }

        analysis_id, reason = client.run_scheduler(10)

        assert analysis_id == 5
        assert reason == "Scheduling started"

    def test_get_scheduling_status(self, client):
        """Test getting scheduler status."""
        client._execute.return_value = {
            "scheduling_request_by_pk": {
                "status": "complete",
                "reason": "Success",
            }
        }

        status = client.get_scheduling_status(5)

        assert status["status"] == "complete"


class TestAerieClientExport:
    """Test export methods."""

    @pytest.fixture
    def client(self):
        """Create client with mocked execute."""
        client = AerieClient(AerieConfig())
        client._execute = MagicMock()
        return client

    def test_export_plan(self, client):
        """Test exporting plan with activities."""
        client._execute.return_value = {
            "plan_by_pk": {
                "id": 42,
                "name": "Test Plan",
                "activity_directives": [
                    {"id": 1, "type": "eo_collect"},
                    {"id": 2, "type": "downlink"},
                ],
            }
        }

        plan = client.export_plan(42)

        assert plan["id"] == 42
        assert len(plan["activity_directives"]) == 2

    def test_export_simulated_plan(self, client):
        """Test exporting simulated plan."""
        client._execute.return_value = {
            "plan_by_pk": {"id": 42},
            "simulated_activity": [{"id": 1}],
        }

        result = client.export_simulated_plan(42, 1)

        assert "plan_by_pk" in result
        assert "simulated_activity" in result


class TestAerieClientResources:
    """Test resource query methods."""

    @pytest.fixture
    def client(self):
        """Create client with mocked execute."""
        client = AerieClient(AerieConfig())
        client._execute = MagicMock()
        return client

    def test_get_resource_profiles(self, client):
        """Test getting resource profiles."""
        client._execute.return_value = {
            "profile": [
                {"name": "battery_soc", "type": "real"},
                {"name": "storage_gb", "type": "real"},
            ]
        }

        profiles = client.get_resource_profiles(1)

        assert len(profiles) == 2
        assert profiles[0]["name"] == "battery_soc"

    def test_get_simulated_activities(self, client):
        """Test getting simulated activities."""
        client._execute.return_value = {
            "simulated_activity": [
                {"id": 1, "type": "eo_collect"},
            ]
        }

        activities = client.get_simulated_activities(1)

        assert len(activities) == 1


class TestAerieClientConstraints:
    """Test constraint query methods."""

    @pytest.fixture
    def client(self):
        """Create client with mocked execute."""
        client = AerieClient(AerieConfig())
        client._execute = MagicMock()
        return client

    def test_get_constraint_violations(self, client):
        """Test getting constraint violations."""
        client._execute.return_value = {
            "constraint_run": [
                {
                    "results": [
                        {"name": "SOC constraint", "violations": 2},
                    ]
                }
            ]
        }

        results = client.get_constraint_violations(42)

        assert len(results) == 1
        assert results[0]["name"] == "SOC constraint"

    def test_get_constraint_violations_no_runs(self, client):
        """Test getting violations with no constraint runs."""
        client._execute.return_value = {"constraint_run": []}

        results = client.get_constraint_violations(42)

        assert results == []
