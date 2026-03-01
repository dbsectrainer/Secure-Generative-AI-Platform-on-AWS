# IAM Role Design

## Design Principles

1. **Least Privilege** – Every role grants the minimum permissions required for its function.
2. **Explicit Deny** – Sensitive actions are explicitly denied regardless of other grants.
3. **No Wildcard Resources** – `Resource: "*"` is avoided except where AWS requires it.
4. **No Wildcard Actions on Sensitive Services** – Actions on KMS, IAM, S3 (sensitive operations) are always scoped to specific resources.
5. **Privilege Escalation Prevention** – Roles cannot create, modify, or attach IAM policies/roles.
6. **SCP Guardrails** – Organisation-level SCPs enforce baselines that cannot be overridden by account-level policies.

## Role Inventory

### 1. `role-lambda-bedrock-orchestrator`

**Purpose**: Assumed by the Lambda Orchestrator function to invoke Bedrock models and read from S3.

**Trust Policy**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "lambda.amazonaws.com" },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "aws:SourceAccount": "${account_id}"
        }
      }
    }
  ]
}
```

**Permission Policy** (`policy-lambda-bedrock-orchestrator`):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BedrockInvoke",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "arn:aws:bedrock:${region}::foundation-model/*",
      "Condition": {
        "StringEquals": { "aws:RequestedRegion": "${region}" }
      }
    },
    {
      "Sid": "S3DocumentRead",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:GetObjectVersion"
      ],
      "Resource": "arn:aws:s3:::${document_bucket_name}/*"
    },
    {
      "Sid": "KMSDecrypt",
      "Effect": "Allow",
      "Action": [
        "kms:Decrypt",
        "kms:GenerateDataKey"
      ],
      "Resource": "arn:aws:kms:${region}:${account_id}:key/${kms_key_id}"
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:${region}:${account_id}:log-group:/aws/lambda/*"
    },
    {
      "Sid": "XRayTrace",
      "Effect": "Allow",
      "Action": [
        "xray:PutTraceSegments",
        "xray:PutTelemetryRecords"
      ],
      "Resource": "*"
    },
    {
      "Sid": "VPCAccess",
      "Effect": "Allow",
      "Action": [
        "ec2:CreateNetworkInterface",
        "ec2:DescribeNetworkInterfaces",
        "ec2:DeleteNetworkInterface"
      ],
      "Resource": "*"
    }
  ]
}
```

**Explicit Deny** (appended as a separate policy `policy-deny-privilege-escalation`):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyIAMEscalation",
      "Effect": "Deny",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:CreatePolicy",
        "iam:DeletePolicy",
        "iam:CreatePolicyVersion",
        "iam:DeletePolicyVersion",
        "iam:SetDefaultPolicyVersion",
        "iam:PassRole",
        "sts:AssumeRole"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DenyKMSAdminActions",
      "Effect": "Deny",
      "Action": [
        "kms:CreateKey",
        "kms:ScheduleKeyDeletion",
        "kms:DisableKey",
        "kms:DeleteImportedKeyMaterial"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DenyS3BucketAdminActions",
      "Effect": "Deny",
      "Action": [
        "s3:DeleteBucket",
        "s3:DeleteBucketPolicy",
        "s3:PutBucketPolicy",
        "s3:PutBucketPublicAccessBlock"
      ],
      "Resource": "*"
    }
  ]
}
```

---

### 2. `role-lambda-document-ingestion`

**Purpose**: Assumed by the document ingestion Lambda to write documents to S3 with checksum validation.

**Permission Policy**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3DocumentWrite",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectTagging",
        "s3:GetObject",
        "s3:GetObjectAttributes"
      ],
      "Resource": "arn:aws:s3:::${document_bucket_name}/*"
    },
    {
      "Sid": "KMSEncrypt",
      "Effect": "Allow",
      "Action": [
        "kms:GenerateDataKey",
        "kms:Decrypt"
      ],
      "Resource": "arn:aws:kms:${region}:${account_id}:key/${kms_key_id}"
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:${region}:${account_id}:log-group:/aws/lambda/*"
    }
  ]
}
```

---

### 3. `role-terraform-deploy`

**Purpose**: Assumed by CI/CD pipeline (CodeBuild / GitHub Actions OIDC) for Terraform plan/apply.

**Trust Policy**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::${account_id}:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:${github_org}/${github_repo}:ref:refs/heads/main"
        },
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        }
      }
    }
  ]
}
```

This role grants only the permissions required to create/modify the infrastructure resources defined in Terraform. It explicitly denies deletion of CloudTrail trails, Config recorders, and GuardDuty detectors to prevent security control tampering.

---

### 4. `role-security-audit` (Security Account)

**Purpose**: Read-only cross-account role assumed by security team members and automated tooling for audit purposes.

**Policy**: AWS managed `SecurityAudit` + `ReadOnlyAccess` with an explicit Deny on any write actions.

---

## Permission Boundary

All human and service IAM roles in the Dev and Prod accounts have a **Permission Boundary** (`boundary-max-permissions`) attached. This boundary prevents any role from exceeding the following maximum permissions:
- No `iam:*` except read-only
- No `organizations:*`
- No `account:*`
- Region-locked to the specified deployment region
- No ability to create or modify CloudTrail, Config, or GuardDuty resources

## Service Control Policies (SCPs)

SCPs are applied at the Organisation level to enforce non-negotiable baselines.

### `scp-deny-root-usage`
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyRootUserActions",
      "Effect": "Deny",
      "Action": "*",
      "Resource": "*",
      "Condition": {
        "StringLike": { "aws:PrincipalArn": "arn:aws:iam::*:root" }
      }
    }
  ]
}
```

### `scp-require-region-restriction`
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyNonApprovedRegions",
      "Effect": "Deny",
      "NotAction": [
        "iam:*",
        "organizations:*",
        "account:*",
        "sts:*",
        "cloudfront:*",
        "route53:*",
        "waf:*"
      ],
      "Resource": "*",
      "Condition": {
        "StringNotEquals": {
          "aws:RequestedRegion": ["eu-west-1", "us-east-1"]
        }
      }
    }
  ]
}
```

### `scp-deny-disable-security-services`
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyDisableCloudTrail",
      "Effect": "Deny",
      "Action": [
        "cloudtrail:StopLogging",
        "cloudtrail:DeleteTrail",
        "cloudtrail:UpdateTrail"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DenyDisableGuardDuty",
      "Effect": "Deny",
      "Action": [
        "guardduty:DeleteDetector",
        "guardduty:DisassociateFromMasterAccount",
        "guardduty:StopMonitoringMembers"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DenyDisableConfig",
      "Effect": "Deny",
      "Action": [
        "config:DeleteConfigurationRecorder",
        "config:StopConfigurationRecorder"
      ],
      "Resource": "*"
    }
  ]
}
```

### `scp-require-encryption`
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyUnencryptedS3Objects",
      "Effect": "Deny",
      "Action": "s3:PutObject",
      "Resource": "*",
      "Condition": {
        "StringNotEquals": {
          "s3:x-amz-server-side-encryption": "aws:kms"
        }
      }
    },
    {
      "Sid": "DenyPublicS3Buckets",
      "Effect": "Deny",
      "Action": [
        "s3:PutBucketPublicAccessBlock",
        "s3:DeletePublicAccessBlock"
      ],
      "Resource": "*",
      "Condition": {
        "Bool": { "s3:PublicAccessBlockEnabled": false }
      }
    }
  ]
}
```

## Privilege Escalation Prevention

The following controls prevent privilege escalation:

1. **Permission Boundaries** on all roles limit maximum privilege ceiling.
2. **`iam:PassRole` restrictions** – Roles can only pass roles with the `iam:PassRole` permission scoped to specific ARN patterns (e.g., Lambda execution roles only).
3. **SCP denial** of `iam:CreateRole` and `iam:AttachRolePolicy` in production accounts (Terraform deploy role is the only exception, and it is scoped to CI/CD pipeline trust).
4. **IAM Access Analyzer** continuously validates that no overly permissive policies are created.
5. **Config rule `iam-no-inline-policies`** alerts on inline policy creation.
6. **Config rule `iam-policy-no-statements-with-admin-access`** blocks policies with `Action: *` and `Resource: *`.
