---
name: aws-cdk-development
description: AWS Cloud Development Kit (CDK) expert for building cloud infrastructure with TypeScript/Python. Use when creating CDK stacks, defining CDK constructs, implementing infrastructure as code, or when the user mentions CDK, CloudFormation, IaC, cdk synth, cdk deploy, or wants to define AWS infrastructure programmatically. Covers CDK app structure, construct patterns, stack composition, and deployment workflows.
allowed-tools:
  - Bash(cdk *)
  - Bash(npm *)
  - Bash(npx *)
  - Bash(aws cloudformation *)
  - Bash(aws sts get-caller-identity)
---

# AWS CDK Development

This skill provides comprehensive guidance for developing AWS infrastructure using the Cloud Development Kit (CDK).

## When to Use This Skill

Use this skill when:
- Creating new CDK stacks or constructs
- Refactoring existing CDK infrastructure
- Implementing Lambda functions within CDK
- Following AWS CDK best practices
- Validating CDK stack configurations before deployment

## Core CDK Principles

### Resource Naming

**CRITICAL**: Do NOT explicitly specify resource names when they are optional in CDK constructs.

**Why**: CDK-generated names enable:
- **Reusable patterns**: Deploy the same construct/pattern multiple times without conflicts
- **Parallel deployments**: Multiple stacks can deploy simultaneously in the same region
- **Stack isolation**: Each stack gets uniquely identified resources automatically

```typescript
// BAD - Explicit naming prevents reusability
new lambda.Function(this, 'MyFunction', {
  functionName: 'my-lambda',  // Avoid this
});

// GOOD - Let CDK generate unique names
new lambda.Function(this, 'MyFunction', {
  // No functionName specified
});
```

### Lambda Function Development

**Python**: Use `@aws-cdk/aws-lambda-python`
```typescript
import { PythonFunction } from '@aws-cdk/aws-lambda-python-alpha';

new PythonFunction(this, 'MyFunction', {
  entry: 'lambda',
  index: 'handler.py',
  handler: 'handler',
});
```

**TypeScript**: Use `@aws-cdk/aws-lambda-nodejs`
```typescript
import { NodejsFunction } from 'aws-cdk-lib/aws-lambda-nodejs';

new NodejsFunction(this, 'MyFunction', {
  entry: 'lambda/handler.ts',
  handler: 'handler',
});
```

### Pre-Deployment Validation

1. **Synthesis**: `cdk synth` to generate CloudFormation
2. **Install cdk-nag** for security/best practice checks:
   ```bash
   npm install --save-dev cdk-nag
   ```
3. **Build**: Ensure compilation succeeds
4. **Tests**: Run unit tests
5. **Deploy**: `cdk deploy` with user confirmation

### Stack Organization

- Use nested stacks for complex applications
- Separate concerns into logical construct boundaries
- Export values that other stacks may need
- Use CDK context for environment-specific configuration
- Default to **dev-sized** (cost-conscious) unless "production-ready" is specified

### Testing Strategy

- Unit test individual constructs
- Integration test stack synthesis
- Snapshot test CloudFormation templates
- Validate resource properties and relationships

## Workflow

1. **Design**: Plan infrastructure resources and relationships
2. **Implement**: Write CDK constructs following best practices
3. **Validate**: Run pre-deployment checks
4. **Synthesize**: Generate CloudFormation templates
5. **Review**: Examine synthesized templates
6. **Deploy**: Deploy to target environment
7. **Verify**: Confirm resources are created correctly
