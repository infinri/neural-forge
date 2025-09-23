"""
Activate Governance MCP Tool

This tool provides the pre-action governance activation functionality
as an MCP tool that can be called by Windsurf/Cursor to automatically
apply Neural Forge governance before AI planning and coding activities.
"""

import uuid
from typing import Any, Dict

from server.governance.pre_action_engine import activate_pre_action_governance
from server.utils.logger import log_json
from server.utils.time import utc_now_iso_z


async def activate_governance(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Activate pre-action governance analysis for AI planning/coding activities
    
    This tool analyzes user intent and conversation context to determine if
    governance should be activated, then provides relevant Neural Forge
    engineering principles and warnings.
    
    Args:
        args: Dictionary containing:
            - user_message (str): The current user message to analyze
            - conversation_history (List[str], optional): Previous conversation messages for context
            - force_activation (bool, optional): Force governance activation regardless of confidence
    
    Returns:
        Dictionary with governance recommendations or indication that no governance is needed
    """
    start_time = utc_now_iso_z()
    request_id = str(uuid.uuid4())
    
    try:
        # Extract parameters
        user_message = args.get("user_message", "")
        conversation_history = args.get("conversation_history", [])
        project_id = args.get("projectId")
        force_activation = args.get("force_activation", False)
        
        if not user_message:
            return {
                "success": False,
                "error": "user_message is required",
                "timestamp": start_time,
                "requestId": request_id,
            }
        
        # Activate pre-action governance
        governance_output = await activate_pre_action_governance(
            user_message=user_message,
            conversation_history=conversation_history,
            project_id=project_id,
        )
        
        # Handle force activation
        if force_activation and not governance_output:
            # Force activation even if confidence is low
            from server.governance.pre_action_engine import governance_engine
            
            context = await governance_engine.analyze_context(
                user_message, conversation_history, project_id=project_id
            )
            recommendation = await governance_engine.get_governance_recommendations(context)
            governance_output = await governance_engine.format_governance_output(recommendation)
        
        if governance_output:
            result = {
                "success": True,
                "governance_activated": True,
                "guidance": governance_output,
                "message": "Neural Forge governance activated - apply these principles during planning and implementation",
                "timestamp": start_time,
                "requestId": request_id,
            }
        else:
            result = {
                "success": True,
                "governance_activated": False,
                "guidance": None,
                "message": "No governance activation needed for this context",
                "timestamp": start_time,
                "requestId": request_id,
            }

        # Log the tool call
        log_json("info", "activate_governance completed",
            endpoint="activate_governance",
            success=True,
            start_time=start_time,
            governance_activated=result["governance_activated"],
            message_length=len(user_message),
            history_length=len(conversation_history),
            requestId=request_id,
        )
        
        return result
        
    except Exception as e:
        error_msg = f"Error activating governance: {str(e)}"
        
        # Log the error
        log_json("error", "activate_governance failed",
            endpoint="activate_governance",
            success=False,
            start_time=start_time,
            error=error_msg,
            requestId=request_id,
        )

        return {
            "success": False,
            "error": error_msg,
            "timestamp": start_time,
            "requestId": request_id,
        }
