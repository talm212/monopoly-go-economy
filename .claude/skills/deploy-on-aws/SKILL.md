---
name: deploy-on-aws
description: "Deploy applications to AWS. Triggers on phrases like: deploy to AWS, host on AWS, run this on AWS, AWS architecture, estimate AWS cost, generate infrastructure. Analyzes any codebase and deploys to optimal AWS services."
allowed-tools:
  - Bash(cdk *)
  - Bash(aws *)
  - Bash(docker *)
---

# Deploy on AWS

Take any application and deploy it to AWS with minimal user decisions.

## Philosophy

**Minimize cognitive burden.** User has code, wants it on AWS. Pick the most
straightforward services. Don't ask questions with obvious answers.

## Workflow

1. **Analyze** - Scan codebase for framework, database, dependencies
2. **Recommend** - Select AWS services, concisely explain rationale
3. **Estimate** - Show monthly cost before proceeding
4. **Generate** - Write IaC code with security defaults applied
5. **Deploy** - Run security checks, then execute with user confirmation

## Service Selection for This Project

### Streamlit Dashboard
- **ECS Fargate** - containerized Streamlit app, auto-scaling
- **ALB** - load balancer for HTTPS access
- **ECR** - container registry for Docker images

### Data Storage
- **S3** - input CSV files, simulation results, large datasets
- **DynamoDB** - simulation configs, run history metadata

### Processing (if needed for batch)
- **ECS Fargate Tasks** - for heavy simulation jobs (millions of rows)
- **Step Functions** - orchestrate multi-step simulation pipelines

## Defaults

Core principle: Default to **dev-sized** (cost-conscious: small instance sizes,
minimal redundancy, single-AZ) unless user says "production-ready".

## Security Defaults (Applied Automatically)

- Encryption at rest for all storage (S3, DynamoDB)
- Private subnets for compute resources
- Least privilege IAM roles
- HTTPS only for ALB
- Security groups with minimal ingress
- VPC with proper network isolation

## Principles

- Concisely explain why each service was chosen
- Always show cost estimate before generating code
- Apply security defaults automatically
- Run IaC security scans before deployment
- Don't ask obvious questions - just pick the right service
- If genuinely ambiguous, then ask
