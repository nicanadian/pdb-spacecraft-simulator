"""Page object model for Aerie UI.

Provides methods for interacting with the Aerie web interface.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

try:
    from playwright.sync_api import Page, expect
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Page = None


class AeriePage:
    """
    Page object for Aerie UI.

    Provides methods for navigating and interacting with Aerie's
    web interface for plan management and scheduling.
    """

    def __init__(self, page: Page, base_url: str = "http://localhost:8080"):
        self.page = page
        self.base_url = base_url

    def goto_home(self) -> None:
        """Navigate to Aerie home page."""
        self.page.goto(self.base_url)
        self.page.wait_for_load_state("networkidle")

    def goto_plans(self) -> None:
        """Navigate to plans page."""
        self.page.goto(f"{self.base_url}/plans")
        self.page.wait_for_load_state("networkidle")

    def goto_mission_models(self) -> None:
        """Navigate to mission models page."""
        self.page.goto(f"{self.base_url}/models")
        self.page.wait_for_load_state("networkidle")

    def goto_plan(self, plan_id: int) -> None:
        """Navigate to specific plan page."""
        self.page.goto(f"{self.base_url}/plans/{plan_id}")
        self.page.wait_for_load_state("networkidle")

    def get_plan_list(self) -> List[dict]:
        """Get list of plans displayed on the plans page."""
        plans = []

        # Wait for plan list to load
        self.page.wait_for_selector("[data-testid='plan-row'], .plan-row, tr[data-plan-id]", timeout=5000)

        # Find plan rows
        rows = self.page.query_selector_all("[data-testid='plan-row'], .plan-row, tr[data-plan-id]")

        for row in rows:
            plan_id = row.get_attribute("data-plan-id")
            name_el = row.query_selector("[data-testid='plan-name'], .plan-name, td:first-child")
            name = name_el.inner_text() if name_el else None

            plans.append({
                "id": int(plan_id) if plan_id else None,
                "name": name,
            })

        return plans

    def get_mission_model_list(self) -> List[dict]:
        """Get list of mission models displayed."""
        models = []

        # Try to wait for model list to load, but don't fail if none exist
        try:
            self.page.wait_for_selector(
                "[data-testid='model-row'], .model-row, tr[data-model-id]",
                timeout=3000,
            )
        except Exception:
            # No models found - return empty list
            return models

        rows = self.page.query_selector_all("[data-testid='model-row'], .model-row, tr[data-model-id]")

        for row in rows:
            model_id = row.get_attribute("data-model-id")
            name_el = row.query_selector("[data-testid='model-name'], .model-name, td:first-child")
            name = name_el.inner_text() if name_el else None

            models.append({
                "id": int(model_id) if model_id else None,
                "name": name,
            })

        return models

    def create_plan(
        self,
        name: str,
        model_id: int,
        start_time: datetime,
        duration_hours: int = 24,
    ) -> int:
        """
        Create a new plan via the UI.

        Args:
            name: Plan name
            model_id: Mission model ID
            start_time: Plan start time
            duration_hours: Plan duration in hours

        Returns:
            Created plan ID
        """
        self.goto_plans()

        # Click create button
        self.page.click("[data-testid='create-plan-btn'], button:has-text('Create Plan'), button:has-text('New Plan')")

        # Fill form
        self.page.wait_for_selector("[data-testid='plan-name-input'], input[name='name'], #plan-name")
        self.page.fill("[data-testid='plan-name-input'], input[name='name'], #plan-name", name)

        # Select model
        self.page.click("[data-testid='model-select'], select[name='model'], #model-select")
        self.page.select_option(
            "[data-testid='model-select'], select[name='model'], #model-select",
            str(model_id),
        )

        # Set start time
        start_str = start_time.strftime("%Y-%m-%dT%H:%M")
        self.page.fill("[data-testid='start-time-input'], input[name='startTime'], #start-time", start_str)

        # Set duration
        self.page.fill(
            "[data-testid='duration-input'], input[name='duration'], #duration",
            f"{duration_hours}:00:00",
        )

        # Submit
        self.page.click("[data-testid='submit-plan-btn'], button[type='submit'], button:has-text('Create')")

        # Wait for navigation to new plan
        self.page.wait_for_url(f"{self.base_url}/plans/*", timeout=10000)

        # Extract plan ID from URL
        url = self.page.url
        plan_id = int(url.split("/plans/")[-1].split("/")[0])

        return plan_id

    def delete_plan(self, plan_id: int) -> None:
        """
        Delete a plan via the UI.

        Args:
            plan_id: Plan ID to delete
        """
        self.goto_plan(plan_id)

        # Click delete button
        self.page.click("[data-testid='delete-plan-btn'], button:has-text('Delete')")

        # Confirm deletion
        self.page.click("[data-testid='confirm-delete-btn'], button:has-text('Confirm'), .modal button:has-text('Delete')")

        # Wait for navigation back to plans list
        self.page.wait_for_url(f"{self.base_url}/plans", timeout=10000)

    def add_activity(
        self,
        plan_id: int,
        activity_type: str,
        start_offset_hours: float = 0,
    ) -> int:
        """
        Add an activity to a plan via the UI.

        Args:
            plan_id: Plan ID
            activity_type: Activity type name
            start_offset_hours: Start offset from plan start

        Returns:
            Created activity ID
        """
        self.goto_plan(plan_id)

        # Click add activity button
        self.page.click("[data-testid='add-activity-btn'], button:has-text('Add Activity')")

        # Wait for dialog
        self.page.wait_for_selector("[data-testid='activity-dialog'], .activity-dialog, .modal")

        # Select activity type
        self.page.click("[data-testid='activity-type-select'], select[name='type']")
        self.page.select_option("[data-testid='activity-type-select'], select[name='type']", activity_type)

        # Set start offset
        offset_str = f"{int(start_offset_hours)}:{int((start_offset_hours % 1) * 60):02d}:00"
        self.page.fill("[data-testid='start-offset-input'], input[name='startOffset']", offset_str)

        # Submit
        self.page.click("[data-testid='submit-activity-btn'], button:has-text('Add'), button[type='submit']")

        # Wait for activity to appear
        self.page.wait_for_selector(f"[data-activity-type='{activity_type}']", timeout=5000)

        # Get activity ID from the newly created activity
        activities = self.page.query_selector_all("[data-activity-id]")
        if activities:
            last_activity = activities[-1]
            return int(last_activity.get_attribute("data-activity-id"))

        return -1

    def delete_activity(self, plan_id: int, activity_id: int) -> None:
        """
        Delete an activity from a plan.

        Args:
            plan_id: Plan ID
            activity_id: Activity ID to delete
        """
        self.goto_plan(plan_id)

        # Find and click on activity
        activity = self.page.query_selector(f"[data-activity-id='{activity_id}']")
        if activity:
            activity.click()

            # Click delete button
            self.page.click("[data-testid='delete-activity-btn'], button:has-text('Delete Activity')")

            # Confirm
            self.page.click("[data-testid='confirm-delete-btn'], button:has-text('Confirm')")

    def run_scheduler(self, plan_id: int) -> None:
        """
        Trigger scheduler for a plan.

        Args:
            plan_id: Plan ID to schedule
        """
        self.goto_plan(plan_id)

        # Click schedule button
        self.page.click("[data-testid='run-scheduler-btn'], button:has-text('Schedule'), button:has-text('Run Scheduler')")

        # Wait for scheduler dialog or status update
        self.page.wait_for_selector(
            "[data-testid='scheduler-status'], .scheduler-status",
            timeout=5000,
        )

    def get_scheduler_status(self, plan_id: int) -> str:
        """
        Get current scheduler status for a plan.

        Args:
            plan_id: Plan ID

        Returns:
            Status string (e.g., "pending", "running", "complete", "failed")
        """
        self.goto_plan(plan_id)

        status_el = self.page.query_selector("[data-testid='scheduler-status'], .scheduler-status")
        if status_el:
            return status_el.inner_text().strip().lower()

        return "unknown"

    def wait_for_scheduler_complete(self, plan_id: int, timeout_ms: int = 60000) -> bool:
        """
        Wait for scheduler to complete.

        Args:
            plan_id: Plan ID
            timeout_ms: Timeout in milliseconds

        Returns:
            True if completed successfully, False otherwise
        """
        self.goto_plan(plan_id)

        try:
            self.page.wait_for_selector(
                "[data-testid='scheduler-status']:has-text('complete'), .scheduler-status:has-text('complete')",
                timeout=timeout_ms,
            )
            return True
        except:
            return False

    def is_loaded(self) -> bool:
        """Check if Aerie UI has loaded."""
        try:
            self.page.wait_for_selector("body", timeout=5000)
            return True
        except:
            return False

    def get_page_title(self) -> str:
        """Get current page title."""
        return self.page.title()
