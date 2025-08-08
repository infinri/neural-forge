#!/usr/bin/env python3
"""
Test script for pre-action governance activation system

This script tests the autonomous governance activation functionality
to ensure it properly detects AI activities and provides relevant
Neural Forge engineering guidance.
"""

import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from server.governance.pre_action_engine import activate_pre_action_governance, governance_engine


async def test_governance_scenarios():
    """Test various scenarios that should trigger governance activation"""
    
    test_scenarios = [
        {
            "name": "Homepage Creation",
            "message": "I want to create a homepage for my website",
            "expected_activity": "planning",
            "should_activate": True
        },
        {
            "name": "API Development", 
            "message": "Let's build a REST API with authentication",
            "expected_activity": "api_design",
            "should_activate": True
        },
        {
            "name": "Database Design",
            "message": "I need to design a database schema for user data",
            "expected_activity": "database", 
            "should_activate": True
        },
        {
            "name": "Security Implementation",
            "message": "How should I implement OAuth2 authentication?",
            "expected_activity": "security",
            "should_activate": True
        },
        {
            "name": "Performance Optimization",
            "message": "My application is slow, need to optimize performance",
            "expected_activity": "performance",
            "should_activate": True
        },
        {
            "name": "Code Refactoring",
            "message": "This code is messy, let's refactor it to be cleaner",
            "expected_activity": "refactoring", 
            "should_activate": True
        },
        {
            "name": "Testing Strategy",
            "message": "What's the best approach for testing this component?",
            "expected_activity": "testing",
            "should_activate": True
        },
        {
            "name": "General Question",
            "message": "What's the weather like today?",
            "expected_activity": "unknown",
            "should_activate": False
        },
        {
            "name": "Architecture Planning",
            "message": "I'm planning a microservices architecture for scalability",
            "expected_activity": "architecture",
            "should_activate": True
        },
        {
            "name": "Deployment Setup",
            "message": "Let's deploy this to production using Docker and Kubernetes",
            "expected_activity": "deployment",
            "should_activate": True
        }
    ]
    
    print("🧠 Testing Neural Forge Pre-Action Governance System")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for scenario in test_scenarios:
        print(f"\n📋 Testing: {scenario['name']}")
        print(f"Message: \"{scenario['message']}\"")
        
        try:
            # Test context analysis
            context = await governance_engine.analyze_context(scenario['message'])
            print(f"Detected Activity: {context.activity_type.value}")
            print(f"Confidence: {context.confidence:.1%}")
            print(f"Keywords: {context.detected_keywords}")
            
            # Test governance activation
            governance_output = await activate_pre_action_governance(scenario['message'])
            
            activated = governance_output is not None
            print(f"Governance Activated: {activated}")
            
            # Check if results match expectations
            if activated == scenario['should_activate']:
                print("✅ PASS - Activation behavior matches expectation")
                passed += 1
            else:
                print(f"❌ FAIL - Expected activation: {scenario['should_activate']}, Got: {activated}")
                failed += 1
            
            # Show governance output if activated
            if governance_output:
                print("\n🎯 Governance Output:")
                print("-" * 40)
                # Show first few lines of output
                lines = governance_output.split('\n')[:8]
                for line in lines:
                    print(line)
                if len(governance_output.split('\n')) > 8:
                    print("... (truncated)")
                    
        except Exception as e:
            print(f"❌ ERROR: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! Pre-action governance system is working correctly.")
        return True
    else:
        print("⚠️ Some tests failed. Check the implementation.")
        return False


async def test_conversation_context():
    """Test governance activation with conversation history"""
    
    print("\n🔄 Testing Conversation Context Analysis")
    print("=" * 50)
    
    conversation_history = [
        "I'm building a web application",
        "It needs user authentication",
        "I'm thinking about using JWT tokens"
    ]
    
    current_message = "Let's implement the login endpoint"
    
    print("Conversation History:")
    for i, msg in enumerate(conversation_history, 1):
        print(f"  {i}. {msg}")
    
    print(f"\nCurrent Message: \"{current_message}\"")
    
    try:
        context = await governance_engine.analyze_context(current_message, conversation_history)
        print(f"\nDetected Activity: {context.activity_type.value}")
        print(f"Confidence: {context.confidence:.1%}")
        print(f"Relevant Domains: {context.relevant_domains}")
        
        governance_output = await activate_pre_action_governance(current_message, conversation_history)
        
        if governance_output:
            print("\n✅ Governance activated with conversation context")
            print("🎯 Context-aware governance guidance provided")
            return True
        else:
            print("\n❌ Governance not activated - unexpected")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


async def main():
    """Run all governance tests"""
    
    print("🚀 Starting Neural Forge Pre-Action Governance Tests")
    print("This will test the autonomous governance activation system\n")
    
    # Test basic scenarios
    scenario_results = await test_governance_scenarios()
    
    # Test conversation context
    context_results = await test_conversation_context()
    
    # Overall results
    print("\n" + "=" * 60)
    if scenario_results and context_results:
        print("🎉 ALL TESTS PASSED!")
        print("Neural Forge pre-action governance system is ready for deployment.")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("Review the implementation before deployment.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
