# 002 — Architecture & Tooling Decisions

## The Ask
Set up the right architecture, tools, skills, and plugins for building an economy simulation platform. First feature: Coin Flip simulator. Must handle millions of rows, be reusable and scalable for future game features.

## Questions & Answers
- **Q**: AWS CDK + Streamlit — right stack?
- **A**: Yes, but with important nuances:
  - **Streamlit**: Perfect for economy team dashboard. Upload CSVs, tweak params, visualize distributions.
  - **AWS CDK**: Right for deployment, but start local-first. Don't over-engineer infra before the simulation works.
  - **Critical addition**: Polars + NumPy for performance. Pandas is too slow for millions of rows.

- **Q**: What about the processing engine?
- **A**: Python with vectorized operations:
  - NumPy for generating millions of random flips in one shot (no Python loops)
  - Polars for data ingestion and aggregation (10-50x faster than Pandas)
  - Target: <10s for 1M players locally

## Agreed Plan

### Tech Stack
| Layer | Technology | Why |
|-------|-----------|-----|
| Simulation Engine | Python + NumPy + Polars | Vectorized operations for millions of rows |
| Dashboard | Streamlit | Economy team self-service, rapid iteration |
| Infrastructure | AWS CDK (Python) | IaC, deploys Streamlit on Fargate, S3 for data |
| Testing | pytest | TDD, deterministic with seeded RNG |
| Packaging | Docker + Poetry/uv | Reproducible builds |

### Architecture (Clean Architecture)
```
domain/          — Pure simulation logic (no I/O, no framework deps)
application/     — Orchestration (run simulation, coordinate I/O)
infrastructure/  — CSV reading, S3, file I/O
ui/              — Streamlit pages and components
```

### Skills & Plugins Installed
| Tool | Source | Purpose |
|------|--------|---------|
| superpowers | claude-plugins-official | Core Claude enhancements |
| document-skills | anthropic-agent-skills | Document generation |
| everything-claude-code | everything-claude-code | Comprehensive toolkit |
| aws-cdk | aws-skills (zxkane) | CDK best practices, construct patterns |
| aws-cost-ops | aws-skills (zxkane) | Pre-deployment cost estimation |
| deploy-on-aws | agent-plugins (awslabs) | Automated AWS deployment |
| Streamlit skills | streamlit/agent-skills | 17 sub-skills for dashboard development |
| AutoForge | MCP server | Feature/task tracking |

### Removed (Not Needed)
- **playwright-cli**: Browser automation — irrelevant for data simulation dashboard
- **example-skills**: Low value noise
- **i18n-expert**: No internationalization needed

## Outcome & Deviations
- Cleaned up previous generic setup, replaced with project-specific configuration
- Installed 3 new skill categories (Streamlit, AWS CDK, Deploy on AWS)
- Updated CLAUDE.md with complete project architecture
- Updated permissions for Python/Streamlit/CDK/AWS workflow
- No deviations from plan
