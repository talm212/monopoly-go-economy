# 003 — System Design & Project Planning

## The Ask
Create full system design (HLD + LLD), plan all features with proper dependency chains, load into AutoForge, and ensure reusability for future game features. AWS infrastructure before AI features. Define AI infrastructure needs.

## Key Decisions

### Phase Order
```
Foundation → Coin Flip → Streamlit → AWS → AI
```
AWS before AI because AI features need Bedrock/Secrets Manager infrastructure in place.

### AI Infrastructure
- **Dual adapter pattern**: `LLMClient` protocol with `AnthropicAdapter` (local dev) and `BedrockAdapter` (production)
- Switch via `LLM_PROVIDER` environment variable
- Bedrock recommended for prod (IAM auth, no API keys, VPC endpoint)
- Anthropic API for local dev (latest models, easier iteration)

### Reusability Architecture
- Core protocols: `SimulatorConfig`, `SimulationResult`, `Simulator[TConfig, TResult]`
- `SimulatorRegistry` for dynamic feature discovery
- 10 of 23 features are reusable — new game features only need simulator + one Streamlit page
- AI features work with any simulator via protocol-based contracts

### What Was Added (Missing from Initial Plan)
- Simulation history store (DynamoDB) for run comparison
- Data validation layer in I/O
- `SimulatorRegistry` for auto-discovery
- Comparison mode in dashboard
- CI/CD pipeline
- Secrets management (Secrets Manager + SSM)

## Agreed Plan
- 23 features across 5 phases loaded into AutoForge
- Full system design document at `docs/plans/2026-03-19-system-design.md`
- Dependency graph verified — Feature #1 (Python project setup) is the only unblocked feature

## Outcome & Deviations
- System design document written (HLD + LLD + directory structure + performance strategy)
- 23 features created in AutoForge with proper dependency chains
- PROJECT.md updated with complete feature tracker and AI architecture
- CLAUDE.md already reflected architecture from previous session
- No deviations from plan
