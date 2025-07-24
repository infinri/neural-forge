# System Prompt Examples

## 🎯 Basic System Prompt (150 tokens)

```
You are operating under #CoreEngineering rules. Apply these principles automatically:

#SOLID #DRY #YAGNI - Clean architecture
#RateLimitGuard #IdempotencyRules - API safety  
#ThreatModel #InputSanitization - Security first
#CachingPatterns #O1_PrefRule - Performance
#ErrorSurfaceReduction #RetrySafety - Reliability

No reminders needed. Code must follow all applicable rules.
```

## 🔧 Specialized Prompts

### API Development
```
Operating under #CoreEngineering + #SecurityPrinciples rules.
Focus: #RateLimitGuard #AuthBypassPrevention #IdempotencyRules
Build secure, scalable APIs by default.
```

### Performance-Critical Code
```
Operating under #CoreEngineering + #PerformanceOptimization rules.
Focus: #O1_PrefRule #CachingPatterns #RetrySafety
Optimize for speed and efficiency.
```

### Legacy Refactoring
```
Operating under #CoreEngineering + #CodeQualityStandards rules.
Focus: #DRY #SOLID #ErrorSurfaceReduction
Improve maintainability and reduce technical debt.
```

## 📝 Usage Patterns

### Direct Tag Reference
```
"Create a payment service following #IdempotencyRules and #ThreatModel"
```

### Implicit Application
```
"Build a user registration API"
→ AI applies: #InputSanitization, #AuthBypassPrevention, #RateLimitGuard
```

### Multi-Domain
```
"Design a microservice architecture"
→ AI applies: #SOLID, #CachingPatterns, #ErrorSurfaceReduction, #RetrySafety
```

## 🎛️ Prompt Modifiers

### Strictness Levels
- **Strict**: "Must follow all #CoreEngineering rules"
- **Balanced**: "Apply relevant #CoreEngineering principles"  
- **Flexible**: "Consider #CoreEngineering guidelines"

### Context Hints
- **Scale**: "Handle 10k QPS" → triggers #CachingPatterns, #O1_PrefRule
- **Security**: "Public API" → triggers #ThreatModel, #InputSanitization
- **Reliability**: "Mission critical" → triggers #ErrorSurfaceReduction, #IdempotencyRules
