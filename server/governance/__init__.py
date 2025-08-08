"""
Neural Forge Governance Module

This module provides autonomous pre-action governance activation
for AI planning and coding activities.
"""

from .pre_action_engine import (
    PreActionGovernanceEngine,
    GovernanceContext,
    GovernanceRecommendation,
    ActivityType,
    activate_pre_action_governance,
    governance_engine
)

__all__ = [
    'PreActionGovernanceEngine',
    'GovernanceContext', 
    'GovernanceRecommendation',
    'ActivityType',
    'activate_pre_action_governance',
    'governance_engine'
]
