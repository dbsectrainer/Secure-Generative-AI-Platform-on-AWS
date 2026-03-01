# Detailed Network Architecture

## VPC Design

### CIDR Allocation

| Account | VPC CIDR | Purpose |
|---------|----------|---------|
| Dev | `10.0.0.0/16` | Development workloads |
| Prod | `10.1.0.0/16` | Production workloads |
| Security | `10.2.0.0/16` | Centralised security tooling |

### Subnet Layout (Per Account VPC, 3 AZs)

```
VPC: 10.0.0.0/16  (example: Dev)
│
├── Public Subnets (NAT Gateways only — no application workloads)
│   ├── 10.0.0.0/24   (AZ-a)  – NAT Gateway, ALB (if public-facing)
│   ├── 10.0.1.0/24   (AZ-b)  – NAT Gateway
│   └── 10.0.2.0/24   (AZ-c)  – NAT Gateway
│
├── Private Application Subnets (Lambda, API Gateway VPC Link)
│   ├── 10.0.10.0/24  (AZ-a)
│   ├── 10.0.11.0/24  (AZ-b)
│   └── 10.0.12.0/24  (AZ-c)
│
├── Private Data Subnets (OpenSearch, RDS/Aurora if required)
│   ├── 10.0.20.0/24  (AZ-a)
│   ├── 10.0.21.0/24  (AZ-b)
│   └── 10.0.22.0/24  (AZ-c)
│
└── VPC Endpoint Subnets (Interface endpoints ENIs)
    ├── 10.0.30.0/24  (AZ-a)
    ├── 10.0.31.0/24  (AZ-b)
    └── 10.0.32.0/24  (AZ-c)
```

### NAT Gateway Justification

NAT Gateways are provisioned in each public subnet (one per AZ) for high availability. They are used **only** for:
- Lambda functions that require outbound internet access to third-party APIs not available via VPC endpoints
- OS patch downloads during build stages

AWS-native service calls (Bedrock, S3, KMS, CloudWatch Logs, SSM) are routed entirely through Interface VPC Endpoints to avoid NAT Gateway data processing charges and to eliminate traffic over the public internet.

**Cost control**: If no Lambda functions require public internet egress, NAT Gateways can be removed and the public subnets reduced to a minimal footprint.

## Route Tables

### Public Subnet Route Table

| Destination | Target |
|-------------|--------|
| `0.0.0.0/0` | Internet Gateway |
| `10.0.0.0/16` | local |

### Private Application Subnet Route Table

| Destination | Target |
|-------------|--------|
| `0.0.0.0/0` | NAT Gateway (AZ-specific) |
| `10.0.0.0/16` | local |
| `com.amazonaws.*.bedrock` | VPC Endpoint (bedrock) |
| `com.amazonaws.*.bedrock-runtime` | VPC Endpoint (bedrock-runtime) |
| `com.amazonaws.*.s3` | VPC Endpoint (s3-gateway) |
| `com.amazonaws.*.kms` | VPC Endpoint (kms) |
| `com.amazonaws.*.logs` | VPC Endpoint (logs) |

### Private Data Subnet Route Table

| Destination | Target |
|-------------|--------|
| `10.0.0.0/16` | local |
| `com.amazonaws.*.s3` | VPC Endpoint (s3-gateway) |
| `com.amazonaws.*.kms` | VPC Endpoint (kms) |

> **Note**: Data subnets have no route to NAT Gateway. They are fully isolated from the internet.

## Security Groups

### `sg-lambda-orchestrator`
Attached to: Lambda Orchestrator functions

| Direction | Protocol | Port | Source/Destination | Reason |
|-----------|----------|------|--------------------|--------|
| Egress | TCP | 443 | `sg-vpc-endpoints` | HTTPS to VPC endpoints |
| Egress | TCP | 443 | `pl-s3` (S3 prefix list) | S3 Gateway endpoint |

No ingress rules. Lambda is invoked by API Gateway via VPC Link (no inbound network rules needed).

### `sg-vpc-endpoints`
Attached to: Interface VPC Endpoint ENIs

| Direction | Protocol | Port | Source/Destination | Reason |
|-----------|----------|------|--------------------|--------|
| Ingress | TCP | 443 | `sg-lambda-orchestrator` | Allow Lambda HTTPS calls to AWS services |
| Ingress | TCP | 443 | `sg-opensearch` | Allow OpenSearch HTTPS calls to AWS services |

### `sg-opensearch`
Attached to: OpenSearch Serverless VPC endpoints

| Direction | Protocol | Port | Source/Destination | Reason |
|-----------|----------|------|--------------------|--------|
| Ingress | TCP | 443 | `sg-lambda-orchestrator` | Lambda queries OpenSearch |
| Egress | TCP | 443 | `sg-vpc-endpoints` | OpenSearch calls to KMS, S3 for encryption/snapshots |

### Default Security Group
**All traffic denied** on the default security group (enforced by AWS Config rule `restricted-default-security-group`).

## Network ACLs (NACLs)

NACLs provide a stateless subnet-level defence in addition to security groups.

### Public Subnet NACL

| Rule | Type | Protocol | Port Range | Source | Action |
|------|------|----------|------------|--------|--------|
| 100 | Inbound | TCP | 443 | `0.0.0.0/0` | ALLOW |
| 200 | Inbound | TCP | 1024–65535 | `0.0.0.0/0` | ALLOW (return traffic) |
| * | Inbound | All | All | `0.0.0.0/0` | DENY |
| 100 | Outbound | TCP | 443 | `0.0.0.0/0` | ALLOW |
| 200 | Outbound | TCP | 1024–65535 | `0.0.0.0/0` | ALLOW (return traffic) |
| * | Outbound | All | All | `0.0.0.0/0` | DENY |

### Private Application Subnet NACL

| Rule | Type | Protocol | Port Range | Source | Action |
|------|------|----------|------------|--------|--------|
| 100 | Inbound | TCP | 443 | `10.0.0.0/16` | ALLOW (intra-VPC) |
| 200 | Inbound | TCP | 1024–65535 | `10.0.0.0/16` | ALLOW (return traffic) |
| * | Inbound | All | All | `0.0.0.0/0` | DENY |
| 100 | Outbound | TCP | 443 | `10.0.0.0/16` | ALLOW |
| 200 | Outbound | TCP | 1024–65535 | `10.0.0.0/16` | ALLOW |
| * | Outbound | All | All | `0.0.0.0/0` | DENY |

### Private Data Subnet NACL

| Rule | Type | Protocol | Port Range | Source | Action |
|------|------|----------|------------|--------|--------|
| 100 | Inbound | TCP | 443 | `10.0.10.0/22` | ALLOW (from app subnets only) |
| 200 | Inbound | TCP | 1024–65535 | `10.0.10.0/22` | ALLOW (return traffic) |
| * | Inbound | All | All | `0.0.0.0/0` | DENY |
| 100 | Outbound | TCP | 443 | `10.0.10.0/22` | ALLOW |
| 200 | Outbound | TCP | 1024–65535 | `10.0.10.0/22` | ALLOW |
| * | Outbound | All | All | `0.0.0.0/0` | DENY |

## Interface VPC Endpoints

All Interface VPC Endpoints have endpoint policies that restrict access to the owning account and require `aws:SourceVpc` conditions.

| Endpoint | Service | Justification |
|----------|---------|---------------|
| `vpce-bedrock` | `com.amazonaws.REGION.bedrock` | Bedrock model discovery |
| `vpce-bedrock-runtime` | `com.amazonaws.REGION.bedrock-runtime` | Model inference invocation |
| `vpce-s3` | `com.amazonaws.REGION.s3` (Interface) | S3 bucket operations from Lambda |
| `vpce-kms` | `com.amazonaws.REGION.kms` | KMS CMK encrypt/decrypt operations |
| `vpce-logs` | `com.amazonaws.REGION.logs` | CloudWatch Logs from Lambda |
| `vpce-monitoring` | `com.amazonaws.REGION.monitoring` | CloudWatch metrics from Lambda |
| `vpce-ssm` | `com.amazonaws.REGION.ssm` | Parameter Store access |
| `vpce-ssmmessages` | `com.amazonaws.REGION.ssmmessages` | SSM Session Manager (no bastion host required) |
| `vpce-execute-api` | `com.amazonaws.REGION.execute-api` | API Gateway private invocation |

> **S3 Gateway Endpoint** (`com.amazonaws.REGION.s3`) is also provisioned as a Gateway Endpoint on private route tables. Gateway endpoints are free and route S3 traffic through the AWS network without using NAT Gateway bandwidth.

## VPC Flow Logs

VPC Flow Logs are enabled on all VPCs and delivered to:
1. CloudWatch Logs (1-day retention) for near-real-time GuardDuty analysis
2. S3 bucket in the Security account (90-day retention, Athena queryable) for incident investigation

Flow logs capture `ACCEPT` and `REJECT` records with extended format fields including `pkt-src-addr`, `pkt-dst-addr`, `traffic-path`, and `tcp-flags`.
