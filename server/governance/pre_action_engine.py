"""
Pre-Action Governance Engine

This module implements the autonomous pre-action governance activation system.
It detects when AI is about to plan/code, analyzes context, retrieves relevant
Neural Forge rules, and provides governance guidance automatically.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from server.db.engine import get_async_engine
from server.db.repo import (
    fetch_governance_token_metrics_pg,
    record_governance_token_metric_pg,
)

logger = logging.getLogger(__name__)


class ActivityType(Enum):
    """Types of AI activities that trigger governance"""
    PLANNING = "planning"
    CODING = "coding" 
    ARCHITECTURE = "architecture"
    REFACTORING = "refactoring"
    TESTING = "testing"
    SECURITY = "security"
    PERFORMANCE = "performance"
    DATABASE = "database"
    API_DESIGN = "api_design"
    DEPLOYMENT = "deployment"
    UNKNOWN = "unknown"


@dataclass
class GovernanceContext:
    """Context information for governance activation"""
    activity_type: ActivityType
    confidence: float
    detected_keywords: List[str]
    user_intent: str
    relevant_domains: List[str]
    project_id: Optional[str] = None


@dataclass
class GovernanceRecommendation:
    """Governance recommendation with rules and guidance"""
    activity_type: ActivityType
    relevant_rules: List[Dict[str, Any]]
    summary: str
    key_principles: List[str]
    warnings: List[str]
    confidence: float


class PreActionGovernanceEngine:
    """
    Core engine for autonomous pre-action governance activation.
    
    This engine monitors AI conversations, detects when planning/coding
    is about to occur, and automatically provides relevant governance
    guidance from Neural Forge's 63 engineering tokens.
    """
    
    def __init__(self):
        self.activity_patterns = self._initialize_activity_patterns()
        self.domain_mappings = self._initialize_domain_mappings()
        self.rule_cache = {}
        self.token_metrics_cache: Dict[str, Dict[str, Any]] = {}
        
    def _initialize_activity_patterns(self) -> Dict[ActivityType, List[str]]:
        """Initialize regex patterns for detecting different AI activities"""
        return {
            ActivityType.PLANNING: [
                r'\b(?:plan|planning|design|approach|strategy|outline)\b',
                r'\b(?:how to|let\'s|should we|going to)\b',
                r'\b(?:create|build|implement|develop)\b',
                r'\b(?:step by step|roadmap|timeline)\b'
            ],
            ActivityType.CODING: [
                r'\b(?:code|coding|program|script|function|class|method)\b',
                r'\b(?:write|implement|create|build).*(?:code|function|class|api)\b',
                r'\b(?:python|javascript|java|go|rust|typescript|html|css)\b',
                r'\b(?:algorithm|logic|implementation)\b'
            ],
            ActivityType.ARCHITECTURE: [
                r'\b(?:architecture|system design|microservices|monolith)\b',
                r'\b(?:database design|schema|data model)\b',
                r'\b(?:scalability|distributed|cloud)\b',
                r'\b(?:patterns|design patterns|architectural)\b'
            ],
            ActivityType.REFACTORING: [
                r'\b(?:refactor|refactoring|cleanup|optimize|improve)\b',
                r'\b(?:technical debt|code quality|maintainability)\b',
                r'\b(?:restructure|reorganize|simplify)\b'
            ],
            ActivityType.TESTING: [
                r'\b(?:test|testing|unit test|integration test|e2e)\b',
                r'\b(?:coverage|test cases|assertions)\b',
                r'\b(?:mock|stub|fixture)\b'
            ],
            ActivityType.SECURITY: [
                r'\b(?:security|authentication|authorization|encryption)\b',
                r'\b(?:vulnerability|threat|attack|exploit)\b',
                r'\b(?:oauth|jwt|ssl|tls|https)\b'
            ],
            ActivityType.PERFORMANCE: [
                r'\b(?:performance|optimization|speed|latency|throughput)\b',
                r'\b(?:caching|memory|cpu|database query)\b',
                r'\b(?:bottleneck|profiling|benchmark)\b'
            ],
            ActivityType.DATABASE: [
                r'\b(?:database|sql|nosql|query|schema|migration)\b',
                r'\b(?:postgres|mysql|mongodb|redis)\b',
                r'\b(?:index|transaction|orm)\b'
            ],
            ActivityType.API_DESIGN: [
                r'\b(?:api|endpoint|rest|graphql|grpc)\b',
                r'\b(?:route|handler|controller|service)\b',
                r'\b(?:request|response|payload|json)\b'
            ],
            ActivityType.DEPLOYMENT: [
                r'\b(?:deploy|deployment|docker|kubernetes|ci/cd)\b',
                r'\b(?:production|staging|environment|infrastructure)\b',
                r'\b(?:pipeline|build|release)\b'
            ]
        }
    
    def _initialize_domain_mappings(self) -> Dict[ActivityType, List[str]]:
        """Map activity types to Neural Forge rule domains"""
        return {
            ActivityType.PLANNING: ["architecture", "ai-learning"],
            ActivityType.CODING: ["code-quality", "security", "performance"],
            ActivityType.ARCHITECTURE: ["architecture", "performance", "reliability"],
            ActivityType.REFACTORING: ["code-quality", "performance", "reliability"],
            ActivityType.TESTING: ["testing", "reliability"],
            ActivityType.SECURITY: ["security", "reliability"],
            ActivityType.PERFORMANCE: ["performance", "architecture"],
            ActivityType.DATABASE: ["data", "performance", "security"],
            ActivityType.API_DESIGN: ["architecture", "security", "performance"],
            ActivityType.DEPLOYMENT: ["reliability", "security", "performance"]
        }
    
    async def analyze_context(
        self,
        user_message: str,
        conversation_history: Optional[List[str]] = None,
        project_id: Optional[str] = None,
    ) -> GovernanceContext:
        """
        Analyze user message and conversation to detect AI activity context
        
        Args:
            user_message: The current user message
            conversation_history: Previous messages for context (optional)
            
        Returns:
            GovernanceContext with detected activity and confidence
        """
        # Combine current message with recent history for better context
        full_context = user_message
        if conversation_history:
            # Use last 3 messages for context
            recent_history = conversation_history[-3:]
            full_context = " ".join(recent_history + [user_message])
        
        # Detect activity type and confidence
        activity_scores = {}
        detected_keywords = []
        
        for activity_type, patterns in self.activity_patterns.items():
            score = 0.0
            activity_keywords = []
            
            for pattern in patterns:
                matches = re.findall(pattern, full_context.lower(), re.IGNORECASE)
                if matches:
                    score += len(matches) * 0.2  # Each match adds 0.2 to confidence
                    activity_keywords.extend(matches)
            
            if score > 0:
                activity_scores[activity_type] = min(score, 1.0)  # Cap at 1.0
                detected_keywords.extend(activity_keywords)
        
        # Determine primary activity type
        if not activity_scores:
            primary_activity = ActivityType.UNKNOWN
            confidence = 0.0
        else:
            primary_activity = max(activity_scores.items(), key=lambda x: x[1])[0]
            confidence = activity_scores[primary_activity]
        
        # Get relevant domains for this activity
        relevant_domains = self.domain_mappings.get(primary_activity, [])
        
        return GovernanceContext(
            activity_type=primary_activity,
            confidence=confidence,
            detected_keywords=list(set(detected_keywords)),  # Remove duplicates
            user_intent=user_message,
            relevant_domains=relevant_domains,
            project_id=project_id,
        )
    
    async def should_activate_governance(self, context: GovernanceContext) -> bool:
        """
        Determine if governance should be activated based on context
        
        Args:
            context: The analyzed governance context
            
        Returns:
            True if governance should be activated
        """
        # Activate if we have reasonable confidence in detecting an activity
        if context.confidence >= 0.3 and context.activity_type != ActivityType.UNKNOWN:
            return True
            
        # Also activate for certain high-impact keywords regardless of confidence
        high_impact_keywords = [
            "security", "authentication", "database", "production", 
            "deploy", "performance", "architecture", "api"
        ]
        
        if any(keyword in context.detected_keywords for keyword in high_impact_keywords):
            return True
            
        return False
    
    async def get_governance_recommendations(self, context: GovernanceContext) -> GovernanceRecommendation:
        """
        Retrieve and synthesize governance recommendations for the detected context
        
        Args:
            context: The analyzed governance context
            
        Returns:
            GovernanceRecommendation with relevant rules and guidance
        """
        # This would integrate with the existing Neural Forge rule system
        # For now, we'll create a structured response based on the context
        
        relevant_rules = await self._get_relevant_rules(context)
        summary = self._generate_summary(context, relevant_rules)
        key_principles = self._extract_key_principles(context, relevant_rules)
        warnings = self._generate_warnings(context, relevant_rules)

        try:
            await self._record_token_metrics(context, relevant_rules)
        except Exception as exc:
            logger.debug("Failed to update governance token metrics: %s", exc)

        return GovernanceRecommendation(
            activity_type=context.activity_type,
            relevant_rules=relevant_rules,
            summary=summary,
            key_principles=key_principles,
            warnings=warnings,
            confidence=context.confidence
        )
    
    async def _get_relevant_rules(self, context: GovernanceContext) -> List[Dict[str, Any]]:
        """Retrieve relevant Neural Forge rules based on context"""
        # This will integrate with the existing rule loading system
        # For now, return structured rule data based on domains
        
        rules = []
        for domain in context.relevant_domains:
            domain_rules = await self._load_domain_rules(domain)
            rules.extend(domain_rules)
        
        return rules[:10]  # Limit to top 10 most relevant rules
    
    async def _load_domain_rules(self, domain: str) -> List[Dict[str, Any]]:
        """Load rules for a specific domain from Neural Forge memory"""
        try:
            # Import Neural Forge clients to access real rule data
            import os
            import sys
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
            
            from server.nf_client.tokens import fetch_tokens
            
            # Map domain names to Neural Forge categories
            domain_mapping = {
                "security": ["security"],
                "performance": ["performance"], 
                "code-quality": ["code-quality"],
                "architecture": ["architecture"],
                "reliability": ["reliability"],
                "data": ["data"],
                "testing": ["testing"],
                "ai-learning": ["ai-learning"]
            }
            
            rules = []
            
            # Get tokens for this domain
            if domain in domain_mapping:
                categories = domain_mapping[domain]
                tokens_response = fetch_tokens("neural-forge", categories)
                tokens_data = tokens_response.get("tokens", [])
                metrics_overlay: Dict[str, Dict[str, Any]] = {}
                if tokens_data:
                    metrics_overlay = await self._load_metrics_for_tokens(tokens_data)

                for token in tokens_data:
                    token_ref = self._token_metric_key(token)
                    overlay = metrics_overlay.get(token_ref) or self.token_metrics_cache.get(token_ref)
                    # Extract rule information from token structure
                    rule = {
                        "name": token.get("name", "Unknown"),
                        "description": token.get("description", "No description available"),
                        "priority": self._determine_priority(token),
                        "triggers": self._extract_triggers(token),
                        "category": token.get("kind", domain),  # Use 'kind' from token structure
                        "rules": token.get("rules", []),
                        "tokenRef": token_ref,
                        "source": token.get("source"),
                    }
                    if overlay:
                        rule["usageMetrics"] = overlay
                        self.token_metrics_cache[token_ref] = overlay
                    rules.append(rule)

            return rules

        except Exception as e:
            logger.warning(f"Failed to load real Neural Forge rules for {domain}: {e}")
            # Fallback to essential mock rules if real data fails
            return self._get_fallback_rules(domain)

    def _token_metric_key(self, token: Dict[str, Any]) -> str:
        """Derive a stable identifier for a token for metric storage."""
        source = token.get("source")
        if isinstance(source, str) and source.strip():
            return source.strip()
        kind = token.get("kind") or token.get("category") or "unknown"
        name = token.get("name") or token.get("tag") or "unknown"
        return f"{kind}::{name}"

    def _determine_priority(self, token: Dict[str, Any]) -> str:
        """Determine rule priority based on token metadata"""
        # Check for priority indicators in token data
        name = token.get("name", "").lower()
        description = token.get("description", "").lower()
        rules = token.get("rules", [])
        
        # Critical priority indicators
        critical_keywords = ["security", "authentication", "authorization", "vulnerability", "exploit"]
        if any(keyword in name or keyword in description for keyword in critical_keywords):
            return "critical"
        
        # High priority indicators  
        high_keywords = ["performance", "scalability", "reliability", "data integrity", "solid"]
        if any(keyword in name or keyword in description for keyword in high_keywords):
            return "high"
        
        # Check rule count - more rules might indicate higher importance
        if len(rules) > 5:
            return "high"
        elif len(rules) > 2:
            return "medium"
        
        return "medium"
    
    def _extract_triggers(self, token: Dict[str, Any]) -> List[str]:
        """Extract trigger keywords from token data"""
        triggers = []
        
        # Extract from name and description
        name = token.get("name", "")
        description = token.get("description", "")
        
        # Add name as a trigger
        if name:
            triggers.append(name.lower())
        
        # Extract key terms from description
        if description:
            # Simple keyword extraction
            keywords = ["api", "database", "security", "performance", "testing", "authentication", 
                       "caching", "optimization", "refactoring", "architecture", "design"]
            for keyword in keywords:
                if keyword in description.lower():
                    triggers.append(keyword)
        
        return list(set(triggers))  # Remove duplicates
    
    def _get_fallback_rules(self, domain: str) -> List[Dict[str, Any]]:
        """Fallback rules if real Neural Forge data is unavailable"""
        fallback_rules: Dict[str, List[Dict[str, Any]]] = {
            "security": [
                {
                    "name": "InputValidation",
                    "description": "Always validate and sanitize user inputs",
                    "priority": "critical",
                    "triggers": ["input", "validation", "sanitization"],
                }
            ],
            "performance": [
                {
                    "name": "AlgorithmComplexity",
                    "description": "Consider algorithm complexity and optimize for performance",
                    "priority": "high",
                    "triggers": ["algorithm", "performance", "optimization"],
                }
            ],
            "code-quality": [
                {
                    "name": "CodeQuality",
                    "description": "Follow coding best practices and maintain clean code",
                    "priority": "high",
                    "triggers": ["code quality", "refactoring", "maintainability"],
                }
            ],
        }

        selected = fallback_rules.get(domain, [])
        enriched: List[Dict[str, Any]] = []
        for rule in selected:
            item = dict(rule)
            token_ref = f"fallback::{domain}::{item.get('name', 'Unknown')}"
            item["tokenRef"] = token_ref
            item["source"] = None
            overlay = self.token_metrics_cache.get(token_ref)
            if overlay:
                item["usageMetrics"] = overlay
            enriched.append(item)

        return enriched

    async def _load_metrics_for_tokens(
        self, tokens: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        engine = get_async_engine()
        if engine is None or not tokens:
            return {}

        seen: Dict[str, None] = {}
        token_ids: List[str] = []
        for token in tokens:
            key = self._token_metric_key(token)
            if key and key not in seen:
                seen[key] = None
                token_ids.append(key)

        if not token_ids:
            return {}

        try:
            rows = await fetch_governance_token_metrics_pg(
                engine,
                token_ids=token_ids,
            )
        except Exception as exc:
            logger.debug("Failed to fetch token metrics overlay: %s", exc)
            return {}

        overlay = {row["tokenId"]: row for row in rows if row.get("tokenId")}
        if overlay:
            self.token_metrics_cache.update(overlay)
        return overlay

    def _priority_weight(self, priority: str | None) -> float:
        weights = {
            "critical": 1.0,
            "high": 0.85,
            "medium": 0.65,
            "low": 0.5,
        }
        if not priority:
            return 0.6
        return weights.get(priority.lower(), 0.6)

    def _compute_effectiveness_sample(
        self, context: GovernanceContext, rule: Dict[str, Any]
    ) -> float:
        base = max(0.0, min(context.confidence, 1.0))
        weight = self._priority_weight(rule.get("priority"))
        triggers = rule.get("triggers") or []
        if triggers and context.detected_keywords:
            lower_triggers = {t.lower() for t in triggers}
            overlap = len(lower_triggers.intersection({k.lower() for k in context.detected_keywords}))
            if overlap:
                weight = min(1.0, weight + min(overlap * 0.05, 0.15))
        return max(0.0, min(base * weight, 1.0))

    async def _record_token_metrics(
        self, context: GovernanceContext, rules: List[Dict[str, Any]]
    ) -> None:
        if not rules:
            return

        engine = get_async_engine()
        if engine is None:
            return

        now = datetime.now(timezone.utc)
        project_id = context.project_id

        for rule in rules:
            token_ref = rule.get("tokenRef") or rule.get("source")
            if not token_ref:
                continue
            try:
                sample = self._compute_effectiveness_sample(context, rule)
                record = await record_governance_token_metric_pg(
                    engine,
                    token_id=str(token_ref),
                    project_id=project_id,
                    sample_effectiveness=sample,
                    applied_at=now,
                )
            except Exception as exc:
                logger.debug("Failed to record token metrics for %s: %s", token_ref, exc)
                continue
            if record:
                self.token_metrics_cache[record["tokenId"]] = record
                rule["usageMetrics"] = record
    
    def _generate_summary(self, context: GovernanceContext, rules: List[Dict[str, Any]]) -> str:
        """Generate a summary of governance recommendations"""
        activity_name = context.activity_type.value.replace("_", " ").title()
        rule_count = len(rules)
        
        if rule_count == 0:
            return f"No specific governance rules found for {activity_name} activities."
        
        high_priority_count = sum(1 for rule in rules if rule.get("priority") == "high")
        critical_count = sum(1 for rule in rules if rule.get("priority") == "critical")
        
        summary = f"For {activity_name} activities, {rule_count} relevant governance rules apply."
        
        if critical_count > 0:
            summary += f" {critical_count} are CRITICAL priority."
        if high_priority_count > 0:
            summary += f" {high_priority_count} are HIGH priority."
            
        return summary
    
    def _extract_key_principles(self, context: GovernanceContext, rules: List[Dict[str, Any]]) -> List[str]:
        """Extract key principles from relevant rules"""
        principles = []
        
        for rule in rules:
            if rule.get("priority") in ["critical", "high"]:
                principles.append(f"• {rule.get('name', 'Unknown')}: {rule.get('description', 'No description')}")
        
        return principles[:5]  # Limit to top 5 principles
    
    def _generate_warnings(self, context: GovernanceContext, rules: List[Dict[str, Any]]) -> List[str]:
        """Generate warnings based on activity type and rules"""
        warnings = []
        
        # Activity-specific warnings
        if context.activity_type == ActivityType.SECURITY:
            warnings.append("⚠️ Security implementation detected - ensure thorough testing and review")
        elif context.activity_type == ActivityType.DATABASE:
            warnings.append("⚠️ Database operations detected - consider performance and data integrity")
        elif context.activity_type == ActivityType.API_DESIGN:
            warnings.append("⚠️ API design detected - ensure proper authentication and input validation")
        
        # Rule-based warnings
        critical_rules = [rule for rule in rules if rule.get("priority") == "critical"]
        if critical_rules:
            warnings.append(f"⚠️ {len(critical_rules)} CRITICAL governance rules must be followed")
        
        return warnings
    
    async def format_governance_output(self, recommendation: GovernanceRecommendation) -> str:
        """Format governance recommendation for injection into AI planning"""
        
        output = []
        output.append("🧠 **NEURAL FORGE GOVERNANCE ACTIVATED**")
        output.append("")
        output.append(f"**Activity Detected:** {recommendation.activity_type.value.replace('_', ' ').title()}")
        output.append(f"**Confidence:** {recommendation.confidence:.1%}")
        output.append("")
        
        if recommendation.summary:
            output.append(f"**Summary:** {recommendation.summary}")
            output.append("")
        
        if recommendation.key_principles:
            output.append("**Key Principles to Follow:**")
            output.extend(recommendation.key_principles)
            output.append("")
        
        if recommendation.warnings:
            output.append("**⚠️ Important Warnings:**")
            output.extend(recommendation.warnings)
            output.append("")
        
        output.append("**Recommendation:** Apply these governance principles during planning and implementation.")
        output.append("")
        output.append("---")
        
        return "\n".join(output)


# Global instance for use across the application
governance_engine = PreActionGovernanceEngine()


async def activate_pre_action_governance(
    user_message: str,
    conversation_history: Optional[List[str]] = None,
    project_id: Optional[str] = None,
) -> Optional[str]:
    """
    Main entry point for pre-action governance activation
    
    Analyzes user intent and returns governance guidance if engineering
    activity is detected with sufficient confidence.
    
    Args:
        user_message: Current user message to analyze
        conversation_history: Previous conversation messages for context
        project_id: Optional project identifier to scope governance metrics
        
    Returns:
        Formatted governance guidance string or None if no activation needed
    """
    if conversation_history is None:
        conversation_history = []
    
    # Analyze context
    context = await governance_engine.analyze_context(
        user_message, conversation_history, project_id=project_id
    )
    
    # Only activate if confidence is above threshold (lowered for better coverage)
    if context.confidence < 0.10:  # 10% confidence threshold
        return None
    
    if not await governance_engine.should_activate_governance(context):
        return None
        
    # Get governance recommendations
    recommendation = await governance_engine.get_governance_recommendations(context)
    
    # Format for output
    governance_output = await governance_engine.format_governance_output(recommendation)
    
    logger.info(f"Pre-action governance activated for {context.activity_type.value} with {context.confidence:.1%} confidence")
    
    return governance_output
