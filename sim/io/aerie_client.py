"""
Aerie GraphQL client for mission planning integration.

Provides methods to interact with NASA Aerie's GraphQL API for:
- Mission model management
- Plan creation and modification
- Activity scheduling
- Plan export
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sim.io import aerie_queries as queries


logger = logging.getLogger(__name__)


@dataclass
class AerieConfig:
    """Configuration for Aerie connection."""

    host: str = "localhost"
    port: int = 9000
    use_ssl: bool = False
    auth_token: Optional[str] = None

    @property
    def graphql_url(self) -> str:
        protocol = "https" if self.use_ssl else "http"
        return f"{protocol}://{self.host}:{self.port}/v1/graphql"

    @classmethod
    def from_env(cls, env_path: Optional[Path] = None) -> "AerieConfig":
        """Create config from environment variables or .env file."""
        env = dict(os.environ)

        # Load from .env file if present
        if env_path and env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        env.setdefault(key.strip(), value.strip())

        return cls(
            host=env.get("AERIE_HOST", "localhost"),
            port=int(env.get("AERIE_GATEWAY_PORT", "9000")),
            use_ssl=env.get("AERIE_USE_SSL", "false").lower() == "true",
            auth_token=env.get("AERIE_AUTH_TOKEN"),
        )


@dataclass
class ActivityInput:
    """Input for creating an activity directive."""

    activity_type: str
    start_offset: timedelta
    arguments: Dict[str, Any] = field(default_factory=dict)
    anchor_id: Optional[int] = None
    anchored_to_start: bool = True

    def to_insert_input(self, plan_id: int) -> Dict[str, Any]:
        """Convert to GraphQL insert input format."""
        offset_str = self._format_interval(self.start_offset)
        return {
            "plan_id": plan_id,
            "type": self.activity_type,
            "start_offset": offset_str,
            "arguments": self.arguments,
            **({"anchor_id": self.anchor_id} if self.anchor_id else {}),
            **({"anchored_to_start": self.anchored_to_start} if self.anchor_id else {}),
        }

    @staticmethod
    def _format_interval(td: timedelta) -> str:
        """Format timedelta as PostgreSQL interval string."""
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        micros = td.microseconds
        if micros:
            return f"{hours}:{minutes:02d}:{seconds:02d}.{micros:06d}"
        return f"{hours}:{minutes:02d}:{seconds:02d}"


class AerieClientError(Exception):
    """Base exception for Aerie client errors."""

    pass


class AerieConnectionError(AerieClientError):
    """Connection to Aerie failed."""

    pass


class AerieQueryError(AerieClientError):
    """GraphQL query returned an error."""

    def __init__(self, message: str, errors: List[Dict[str, Any]]):
        super().__init__(message)
        self.errors = errors


class AerieClient:
    """
    Client for Aerie GraphQL API.

    Example usage:
        client = AerieClient()
        plan_id = client.create_plan("my-plan", model_id=1, start_time=dt, duration=hours(24))
        client.insert_activities_batch(plan_id, activities)
    """

    def __init__(self, config: Optional[AerieConfig] = None):
        self.config = config or AerieConfig.from_env()
        self._session_headers: Dict[str, str] = {}

    def _execute(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a GraphQL query/mutation."""
        payload = json.dumps({
            "query": query,
            "variables": variables or {},
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            **self._session_headers,
        }
        if self.config.auth_token:
            headers["Authorization"] = f"Bearer {self.config.auth_token}"

        req = Request(
            self.config.graphql_url,
            data=payload,
            headers=headers,
            method="POST",
        )

        try:
            with urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())

                if "errors" in result:
                    error_messages = "; ".join(
                        e.get("message", str(e)) for e in result["errors"]
                    )
                    raise AerieQueryError(
                        f"GraphQL query failed: {error_messages}",
                        result["errors"],
                    )

                return result.get("data", {})

        except HTTPError as e:
            body = e.read().decode("utf-8") if e.fp else ""
            raise AerieQueryError(f"HTTP {e.code}: {body}", [{"message": body}])
        except URLError as e:
            raise AerieConnectionError(f"Connection failed: {e.reason}")

    # =========================================================================
    # Mission Model Methods
    # =========================================================================

    def list_mission_models(self) -> List[Dict[str, Any]]:
        """Get all mission models."""
        result = self._execute(queries.GET_MISSION_MODELS)
        return result.get("mission_model", [])

    def get_mission_model(self, model_id: int) -> Optional[Dict[str, Any]]:
        """Get mission model by ID."""
        result = self._execute(
            queries.GET_MISSION_MODEL_BY_ID,
            {"id": model_id},
        )
        return result.get("mission_model_by_pk")

    # =========================================================================
    # Plan Methods
    # =========================================================================

    def list_plans(self) -> List[Dict[str, Any]]:
        """Get all plans."""
        result = self._execute(queries.GET_PLANS)
        return result.get("plan", [])

    def find_plan_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Find a plan by name (for idempotency checks)."""
        result = self._execute(queries.GET_PLAN_BY_NAME, {"name": name})
        plans = result.get("plan", [])
        return plans[0] if plans else None

    def get_plan(self, plan_id: int) -> Optional[Dict[str, Any]]:
        """Get plan by ID with activity directives."""
        result = self._execute(queries.GET_PLAN_BY_ID, {"id": plan_id})
        return result.get("plan_by_pk")

    def create_plan(
        self,
        name: str,
        model_id: int,
        start_time: datetime,
        duration: timedelta,
    ) -> int:
        """
        Create a new plan.

        Args:
            name: Plan name (must be unique)
            model_id: Mission model ID
            start_time: Plan start time (UTC)
            duration: Plan duration

        Returns:
            Created plan ID
        """
        # Format duration as PostgreSQL interval
        total_seconds = int(duration.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        duration_str = f"{hours}:{minutes:02d}:{seconds:02d}"

        # Ensure UTC timezone
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)

        result = self._execute(
            queries.CREATE_PLAN,
            {
                "name": name,
                "modelId": model_id,
                "startTime": start_time.isoformat(),
                "duration": duration_str,
            },
        )

        plan = result.get("insert_plan_one", {})
        plan_id = plan.get("id")

        if plan_id is None:
            raise AerieClientError("Plan creation failed: no ID returned")

        logger.info(f"Created plan '{name}' with ID {plan_id}")
        return plan_id

    def delete_plan(self, plan_id: int) -> bool:
        """Delete a plan by ID."""
        result = self._execute(queries.DELETE_PLAN, {"id": plan_id})
        deleted = result.get("delete_plan_by_pk")
        return deleted is not None

    # =========================================================================
    # Activity Methods
    # =========================================================================

    def insert_activity(
        self,
        plan_id: int,
        activity_type: str,
        start_offset: timedelta,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Insert a single activity directive."""
        offset_str = ActivityInput._format_interval(start_offset)

        result = self._execute(
            queries.INSERT_ACTIVITY,
            {
                "planId": plan_id,
                "type": activity_type,
                "startOffset": offset_str,
                "arguments": arguments or {},
            },
        )

        activity = result.get("insert_activity_directive_one", {})
        return activity.get("id")

    def insert_activities_batch(
        self,
        plan_id: int,
        activities: List[ActivityInput],
    ) -> List[int]:
        """
        Insert multiple activities in a single request.

        Args:
            plan_id: Plan ID to add activities to
            activities: List of ActivityInput objects

        Returns:
            List of created activity IDs
        """
        if not activities:
            return []

        objects = [a.to_insert_input(plan_id) for a in activities]

        result = self._execute(
            queries.INSERT_ACTIVITIES_BATCH,
            {"objects": objects},
        )

        returning = result.get("insert_activity_directive", {}).get("returning", [])
        ids = [a.get("id") for a in returning]

        logger.info(f"Inserted {len(ids)} activities into plan {plan_id}")
        return ids

    def delete_activity(self, activity_id: int, plan_id: int) -> bool:
        """Delete an activity directive."""
        result = self._execute(
            queries.DELETE_ACTIVITY,
            {"id": activity_id, "planId": plan_id},
        )
        return result.get("delete_activity_directive_by_pk") is not None

    # =========================================================================
    # Scheduling Methods
    # =========================================================================

    def get_scheduling_specification(self, plan_id: int) -> Optional[Dict[str, Any]]:
        """Get scheduling specification for a plan."""
        result = self._execute(
            queries.GET_SCHEDULING_SPECIFICATION,
            {"planId": plan_id},
        )
        specs = result.get("scheduling_specification", [])
        return specs[0] if specs else None

    def create_scheduling_specification(
        self,
        plan_id: int,
        plan_revision: int,
        horizon_start: datetime,
        horizon_end: datetime,
    ) -> int:
        """Create a scheduling specification for a plan."""
        if horizon_start.tzinfo is None:
            horizon_start = horizon_start.replace(tzinfo=timezone.utc)
        if horizon_end.tzinfo is None:
            horizon_end = horizon_end.replace(tzinfo=timezone.utc)

        result = self._execute(
            queries.CREATE_SCHEDULING_SPECIFICATION,
            {
                "planId": plan_id,
                "planRevision": plan_revision,
                "horizonStart": horizon_start.isoformat(),
                "horizonEnd": horizon_end.isoformat(),
            },
        )
        return result.get("insert_scheduling_specification_one", {}).get("id")

    def run_scheduler(self, specification_id: int) -> Tuple[int, str]:
        """
        Trigger scheduler run.

        Returns:
            Tuple of (analysis_id, reason)
        """
        result = self._execute(
            queries.CREATE_SCHEDULING_REQUEST,
            {"specificationId": specification_id},
        )
        schedule_result = result.get("schedule", {})
        return (
            schedule_result.get("analysisId"),
            schedule_result.get("reason", ""),
        )

    def get_scheduling_status(self, analysis_id: int) -> Dict[str, Any]:
        """Get status of a scheduling run."""
        result = self._execute(
            queries.GET_SCHEDULING_STATUS,
            {"analysisId": analysis_id},
        )
        return result.get("scheduling_request_by_pk", {})

    # =========================================================================
    # Export Methods
    # =========================================================================

    def export_plan(self, plan_id: int) -> Dict[str, Any]:
        """Export plan with activity directives."""
        result = self._execute(
            queries.EXPORT_PLAN_ACTIVITIES,
            {"planId": plan_id},
        )
        return result.get("plan_by_pk", {})

    def export_simulated_plan(
        self,
        plan_id: int,
        dataset_id: int,
    ) -> Dict[str, Any]:
        """Export simulated plan with resolved activities and resources."""
        result = self._execute(
            queries.EXPORT_SIMULATED_PLAN,
            {"planId": plan_id, "datasetId": dataset_id},
        )
        return result

    # =========================================================================
    # Resource Queries
    # =========================================================================

    def get_resource_profiles(self, dataset_id: int) -> List[Dict[str, Any]]:
        """Get resource profiles from a simulation dataset."""
        result = self._execute(
            queries.GET_RESOURCE_PROFILES,
            {"datasetId": dataset_id},
        )
        return result.get("profile", [])

    def get_simulated_activities(self, dataset_id: int) -> List[Dict[str, Any]]:
        """Get simulated activities from a simulation dataset."""
        result = self._execute(
            queries.GET_SIMULATED_ACTIVITIES,
            {"datasetId": dataset_id},
        )
        return result.get("simulated_activity", [])

    # =========================================================================
    # Constraint Queries
    # =========================================================================

    def get_constraint_violations(self, plan_id: int) -> List[Dict[str, Any]]:
        """Get latest constraint run results for a plan."""
        result = self._execute(
            queries.GET_CONSTRAINT_RUNS,
            {"planId": plan_id},
        )
        runs = result.get("constraint_run", [])
        if runs:
            return runs[0].get("results", [])
        return []
