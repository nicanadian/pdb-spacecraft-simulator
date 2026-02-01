"""GraphQL query strings for Aerie API."""
from __future__ import annotations

# =============================================================================
# Mission Model Queries
# =============================================================================

GET_MISSION_MODELS = """
query GetMissionModels {
    mission_model {
        id
        name
        version
        created_at
    }
}
"""

GET_MISSION_MODEL_BY_ID = """
query GetMissionModel($id: Int!) {
    mission_model_by_pk(id: $id) {
        id
        name
        version
        created_at
        activity_types {
            name
            parameters
        }
    }
}
"""

UPLOAD_MISSION_MODEL = """
mutation UploadMissionModel($name: String!, $version: String!, $jarId: Int!) {
    insert_mission_model_one(object: {
        name: $name,
        version: $version,
        jar_id: $jarId
    }) {
        id
        name
        version
    }
}
"""

# =============================================================================
# Plan Queries
# =============================================================================

GET_PLANS = """
query GetPlans {
    plan {
        id
        name
        model_id
        start_time
        duration
        created_at
    }
}
"""

GET_PLAN_BY_NAME = """
query GetPlanByName($name: String!) {
    plan(where: {name: {_eq: $name}}) {
        id
        name
        model_id
        start_time
        duration
        created_at
    }
}
"""

GET_PLAN_BY_ID = """
query GetPlan($id: Int!) {
    plan_by_pk(id: $id) {
        id
        name
        model_id
        start_time
        duration
        created_at
        activity_directives {
            id
            type
            start_offset
            arguments
            anchor_id
            anchored_to_start
        }
    }
}
"""

CREATE_PLAN = """
mutation CreatePlan($name: String!, $modelId: Int!, $startTime: timestamptz!, $duration: interval!) {
    insert_plan_one(object: {
        name: $name,
        model_id: $modelId,
        start_time: $startTime,
        duration: $duration
    }) {
        id
        name
        start_time
        duration
    }
}
"""

DELETE_PLAN = """
mutation DeletePlan($id: Int!) {
    delete_plan_by_pk(id: $id) {
        id
        name
    }
}
"""

# =============================================================================
# Activity Queries
# =============================================================================

INSERT_ACTIVITY = """
mutation InsertActivity(
    $planId: Int!,
    $type: String!,
    $startOffset: interval!,
    $arguments: jsonb!
) {
    insert_activity_directive_one(object: {
        plan_id: $planId,
        type: $type,
        start_offset: $startOffset,
        arguments: $arguments
    }) {
        id
        type
        start_offset
    }
}
"""

INSERT_ACTIVITIES_BATCH = """
mutation InsertActivities($objects: [activity_directive_insert_input!]!) {
    insert_activity_directive(objects: $objects) {
        returning {
            id
            type
            start_offset
        }
    }
}
"""

DELETE_ACTIVITY = """
mutation DeleteActivity($id: Int!, $planId: Int!) {
    delete_activity_directive_by_pk(id: $id, plan_id: $planId) {
        id
        type
    }
}
"""

UPDATE_ACTIVITY = """
mutation UpdateActivity(
    $id: Int!,
    $planId: Int!,
    $startOffset: interval,
    $arguments: jsonb
) {
    update_activity_directive_by_pk(
        pk_columns: {id: $id, plan_id: $planId},
        _set: {start_offset: $startOffset, arguments: $arguments}
    ) {
        id
        type
        start_offset
        arguments
    }
}
"""

# =============================================================================
# Scheduler Queries
# =============================================================================

GET_SCHEDULING_GOALS = """
query GetSchedulingGoals($modelId: Int!) {
    scheduling_goal(where: {model_id: {_eq: $modelId}}) {
        id
        name
        definition
        enabled
    }
}
"""

CREATE_SCHEDULING_REQUEST = """
mutation CreateSchedulingRequest($specificationId: Int!) {
    schedule(specification_id: $specificationId) {
        reason
        analysisId: analysis_id
    }
}
"""

GET_SCHEDULING_STATUS = """
query GetSchedulingStatus($analysisId: Int!) {
    scheduling_request_by_pk(analysis_id: $analysisId) {
        analysis_id
        specification_id
        status
        reason
        canceled
    }
}
"""

GET_SCHEDULING_SPECIFICATION = """
query GetSchedulingSpecification($planId: Int!) {
    scheduling_specification(where: {plan_id: {_eq: $planId}}) {
        id
        plan_id
        plan_revision
        horizon_start
        horizon_end
        analysis_only
    }
}
"""

CREATE_SCHEDULING_SPECIFICATION = """
mutation CreateSchedulingSpecification(
    $planId: Int!,
    $planRevision: Int!,
    $horizonStart: timestamptz!,
    $horizonEnd: timestamptz!
) {
    insert_scheduling_specification_one(object: {
        plan_id: $planId,
        plan_revision: $planRevision,
        horizon_start: $horizonStart,
        horizon_end: $horizonEnd,
        simulation_arguments: {},
        analysis_only: false
    }) {
        id
        plan_id
    }
}
"""

# =============================================================================
# Simulation Queries
# =============================================================================

GET_SIMULATION_DATASET = """
query GetSimulationDataset($datasetId: Int!) {
    simulation_dataset_by_pk(id: $datasetId) {
        id
        plan_id
        status
        reason
        canceled
        simulation_start_time
        simulation_end_time
    }
}
"""

GET_RESOURCE_PROFILES = """
query GetResourceProfiles($datasetId: Int!) {
    profile(where: {dataset_id: {_eq: $datasetId}}) {
        id
        name
        type
        dataset_id
        profile_segments {
            start_offset
            dynamics
        }
    }
}
"""

GET_SIMULATED_ACTIVITIES = """
query GetSimulatedActivities($datasetId: Int!) {
    simulated_activity(where: {simulation_dataset_id: {_eq: $datasetId}}) {
        id
        activity_directive_id
        activity_type_name
        start_offset
        duration
        attributes
    }
}
"""

# =============================================================================
# Constraint Queries
# =============================================================================

GET_CONSTRAINT_RUNS = """
query GetConstraintRuns($planId: Int!) {
    constraint_run(where: {plan_id: {_eq: $planId}}, order_by: {id: desc}, limit: 1) {
        id
        plan_id
        results
    }
}
"""

# =============================================================================
# Export Queries
# =============================================================================

EXPORT_PLAN_ACTIVITIES = """
query ExportPlanActivities($planId: Int!) {
    plan_by_pk(id: $planId) {
        id
        name
        start_time
        duration
        model_id
        mission_model {
            name
            version
        }
        activity_directives {
            id
            type
            start_offset
            arguments
            anchor_id
            anchored_to_start
            metadata
            tags {
                tag {
                    name
                    color
                }
            }
        }
    }
}
"""

EXPORT_SIMULATED_PLAN = """
query ExportSimulatedPlan($planId: Int!, $datasetId: Int!) {
    plan_by_pk(id: $planId) {
        id
        name
        start_time
        duration
    }
    simulated_activity(where: {simulation_dataset_id: {_eq: $datasetId}}) {
        id
        activity_directive_id
        activity_type_name
        start_offset
        duration
        attributes
        parent_id
        child_ids
    }
    profile(where: {dataset_id: {_eq: $datasetId}}) {
        name
        type
        profile_segments {
            start_offset
            dynamics
        }
    }
}
"""
