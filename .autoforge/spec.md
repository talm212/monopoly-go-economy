# Monopoly Go Economy — App Spec

## Project Overview
Economy simulation platform for Monopoly Go game mechanics. The economy team uploads player data, configures game mechanic parameters, runs simulations at scale (1M+ players), and uses AI to analyze results and optimize configurations.

### Architecture
- **Simulation Engine**: Python 3.12+, NumPy (vectorized RNG), Polars (data processing)
- **Dashboard**: Streamlit (multi-page, self-service for economy team)
- **Infrastructure**: AWS CDK (Python) — ECS Fargate, S3, DynamoDB, Bedrock
- **AI**: Claude via Bedrock (prod) / Anthropic API (dev) — insights, chat, optimizer

## Goals
1. Build reusable simulator framework (protocol-based, any game feature plugs in)
2. First feature: Coin Flip simulator with full dashboard
3. Deploy on AWS with CI/CD pipeline
4. AI-powered analysis: insights, chat assistant, config optimizer
5. Handle 1M+ players in <10 seconds

## Technical Standards
- Clean Architecture: domain (no I/O) → application → infrastructure → UI
- All simulators implement SimulatorProtocol[TConfig, TResult]
- Polars only (never Pandas) for DataFrame operations
- NumPy for vectorized random generation (no Python loops at scale)
- TDD: write failing test first, implement, verify pass
- Type hints everywhere (strict mypy)
- Dependency injection via constructor
- Seed all randomness in tests

## Feature Simulators
| Simulator | Status |
|-----------|--------|
| Coin Flip | Current (Phase 2) |
| Loot Tables | Planned |
| Reward Distributions | Planned |
| Event Economies | Planned |

## Phases
1. Foundation (project setup, testing, system design)
2. Simulator Core (protocols, I/O, coin flip engine, CLI)
3. Streamlit Dashboard (upload, run, results, export)
4. AWS Infrastructure (Docker, CDK, Fargate, CI/CD)
5. AI Features (LLM client, insights, chat, optimizer)
