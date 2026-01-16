# AWS Security Hub Multi-Account Product Disablement Script

## Overview

This script automates the process of disabling specific AWS Security Hub product integrations across multiple AWS accounts. 

## License Summary

This sample code is made available under a modified MIT license. See the LICENSE file.

## Account Roles

This script works in a Security Hub multi-account setup with two types of accounts:

**Delegated Administrator (DA) Account:**
- This is where you RUN the script
- Has visibility into all Security Hub member accounts
- Can list members and assume roles in member accounts
- Example: Your central security account

**Member Accounts:**
- These are the accounts where products will be DISABLED
- Must have an IAM role that trusts the DA account
- Must be enabled as Security Hub members
- Example: Your application accounts, workload accounts

## Prerequisites

### Delegated Administrator (DA) Account

The DA account (where you run the script) must have these permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "securityhub:ListMembers",
                "sts:AssumeRole"
            ],
            "Resource": "*"
        }
    ]
}
```

This allows the DA account to:
- List all Security Hub member accounts
- Assume roles in member accounts to disable products

### Member Accounts (Target Accounts)

Each member account must have an IAM role with:

1. **IAM permissions** to disable products:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "securityhub:DisableImportFindingsForProduct"
            ],
            "Resource": "*"
        }
    ]
}
```

2. **Trust policy** that grants the DA account permission to assume this role:
```json
{
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {
            "AWS": "arn:aws:iam::DA_ACCOUNT_ID:root"
        },
        "Action": "sts:AssumeRole"
    }]
}
```

**Important:** 
- The role name must be the same in ALL member accounts (e.g., `SecurityHubRole`)
- Replace `DA_ACCOUNT_ID` with your actual DA account ID
- The trust policy is what grants the DA account STS access to assume the role

See `iam-policy-example.json` for a complete policy template and `trust-policy-example.json` for the trust relationship.

### Quick Setup Summary

1. **In DA Account (where you run the script):**
   - Attach permissions: `securityhub:ListMembers`, `sts:AssumeRole`

2. **In Each Member Account (where products will be disabled):**
   - Create IAM role named `SecurityHubRole`
   - Attach permission: `securityhub:DisableImportFindingsForProduct`
   - Set trust policy to allow DA account to assume the role (grants STS access)

3. **Ensure accounts are Security Hub members:**
   - From DA account: `aws securityhub create-members --region REGION --account-details ...`

### Optional: CSV File

A CSV file with account IDs to process. Accounts should be listed one per line with the account ID. Format: `AccountId`. See `accounts.csv.example` for a sample file.
- If CSV is provided: Script processes **accounts from the CSV file**
- If CSV is not provided: Script processes **all Security Hub member accounts**

### Software Requirements

Python 2.7+ or Python 3.x with boto3 library installed

## Important: STS Regional Endpoint Configuration

⚠️ **CRITICAL:** This script requires regional STS endpoints to be enabled.

### Quick Setup (Run Before Script)

```bash
export AWS_STS_REGIONAL_ENDPOINTS=regional
```

### Permanent Setup (Recommended)

Add to your `~/.aws/config` file:

```ini
[default]
sts_regional_endpoints = regional
region = us-east-1  # or your preferred region
```

Or use the following command to append it automatically:

```bash
cat >> ~/.aws/config << 'EOF'

[default]
sts_regional_endpoints = regional
EOF
```

### Why This Is Required

AWS is enforcing regional STS endpoints for security and compliance. Without this setting, you'll encounter errors like:

```
AccessDenied when calling GetCallerIdentity operation: 
You are currently using the legacy global endpoint. 
Please switch to the regional endpoint instead.
```

**What it does:** This setting tells the AWS SDK to use regional STS endpoints (e.g., `sts.us-east-1.amazonaws.com`) instead of the legacy global endpoint (`sts.amazonaws.com`).

**Impact:** This setting applies to ALL STS operations and works across ALL regions the script processes.

For more information: [AWS STS Regionalized Endpoints Documentation](https://docs.aws.amazon.com/sdkref/latest/guide/feature-sts-regionalized-endpoints.html)

## Creating the IAM Role

If the SecurityHubRole doesn't exist in your member accounts, create it using the AWS CLI:

```bash
# Run these commands in EACH MEMBER ACCOUNT (not the DA account)

# 1. Create trust policy
# Replace 123456789012 with your DA account ID (where you run the script)
cat > trust-policy.json << 'EOF'
{
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {
            "AWS": "arn:aws:iam::123456789012:root"
        },
        "Action": "sts:AssumeRole"
    }]
}
EOF

# 2. Create IAM policy
cat > iam-policy.json << 'EOF'
{
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Action": [
            "securityhub:DisableImportFindingsForProduct"
        ],
        "Resource": "*"
    }]
}
EOF

# 3. Create role
aws iam create-role \
    --role-name SecurityHubRole \
    --assume-role-policy-document file://trust-policy.json

# 4. Attach policy
aws iam put-role-policy \
    --role-name SecurityHubRole \
    --policy-name SecurityHubProductManagement \
    --policy-document file://iam-policy.json
```

**Note:** The trust policy (step 1) grants the DA account STS access to assume this role. This is required for cross-account access.

See `trust-policy-example.json` and `iam-policy-example.json` for complete templates.

## Steps

### 1. Setup Execution Environment

#### Option 1: Launch EC2 Instance
* Launch an EC2 instance https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EC2_GetStarted.html
* Attach an IAM role to the instance that has permissions to call AssumeRole for the target accounts
* Install required software:
    * APT: `sudo apt-get -y install python-pip python git`
    * RPM: `sudo yum -y install python-pip python git`
    * `sudo pip install boto3`
* Clone the repository:
    * `git clone https://github.com/awslabs/aws-securityhub-multiaccount-scripts.git`
    * `cd aws-securityhub-multiaccount-scripts/multiaccount-product-disablement`
* Copy your CSV file to the instance

#### Option 2: Run Locally
* Ensure you have credentials configured on your local machine that have permission to call AssumeRole
* Install required software:
    * **Windows:**
        * Install Python https://www.python.org/downloads/windows/
        * `pip install boto3`
        * `git clone https://github.com/awslabs/aws-securityhub-multiaccount-scripts.git`
        * `cd aws-securityhub-multiaccount-scripts\multiaccount-product-disablement`
    * **Mac:**
        * Install Python https://www.python.org/downloads/mac-osx/
        * `pip install boto3`
        * `git clone https://github.com/awslabs/aws-securityhub-multiaccount-scripts.git`
        * `cd aws-securityhub-multiaccount-scripts/multiaccount-product-disablement`
    * **Linux:**
        * `sudo apt-get -y install python-pip python git` or `sudo yum -y install python-pip python git`
        * `sudo pip install boto3`
        * `git clone https://github.com/awslabs/aws-securityhub-multiaccount-scripts.git`
        * `cd aws-securityhub-multiaccount-scripts/multiaccount-product-disablement`

### 2. Create CSV File

Create a CSV file with your account information. Each line should contain an account ID:

**Format:**
```
123456789012
234567890123
345678901234
```

### 3. Execute Script

```
usage: productdisablement.py [-h] --assume_role ASSUME_ROLE
                              --regions-to-disable REGIONS_TO_DISABLE
                              --products PRODUCTS
                              input_file

Disable Security Hub CSPM product integrations across multiple AWS accounts

positional arguments:
  input_file            Path to CSV file containing account IDs (one per
                        line)

required arguments:
  --assume_role ASSUME_ROLE
                        Role Name to assume in each account
  --regions-to-disable REGIONS_TO_DISABLE
                        Comma separated list of regions to disable products,
                        or 'ALL' for all available regions
  --products PRODUCTS   Comma separated list of product identifiers to disable
                        (e.g., 'aws/guardduty,aws/macie' or product ARNs)

optional arguments:
  -h, --help            show this help message and exit
```

## Usage Examples

### Using Auto-Discovery (No CSV File)

When running from the Security Hub delegated administrator account, the script can automatically discover all Security Hub member accounts:

```bash
# Disable GuardDuty across ALL Security Hub member accounts in all regions
python productdisablement.py \
    --assume_role SecurityHubRole \
    --regions-to-disable ALL \
    --products "aws/guardduty"
```

```bash
# Disable multiple products across ALL Security Hub member accounts in specific regions
python productdisablement.py \
    --assume_role SecurityHubRole \
    --regions-to-disable us-east-1,us-west-2,eu-west-1 \
    --products "aws/guardduty,aws/macie,aws/inspector2"
```

### Using CSV File

When providing a CSV file, the script processes the accounts listed in the CSV:

```bash
# Disable GuardDuty for specific accounts (intersection of CSV and members)
python productdisablement.py accounts.csv \
    --assume_role SecurityHubRole \
    --regions-to-disable ALL \
    --products "aws/guardduty"
```

```bash
# Disable multiple products in specific accounts and regions
python productdisablement.py accounts.csv \
    --assume_role SecurityHubRole \
    --regions-to-disable us-east-1,us-west-2,eu-west-1 \
    --products "aws/guardduty,aws/macie,aws/inspector2"
```

```bash
# Disable Access Analyzer and Firewall Manager in specific accounts, us-east-1 only
python productdisablement.py accounts.csv \
    --assume_role SecurityHubRole \
    --regions-to-disable us-east-1 \
    --products "aws/access-analyzer,aws/firewall-manager"
```

## Product Identifiers

You can specify products using either format:
- **Short name format**: `aws/guardduty`, `aws/macie`, `aws/inspector2`
- **Full ARN format**: `arn:aws:securityhub:us-east-1:123456789012:product-subscription/aws/guardduty`

### Common AWS Product Identifiers

| Product Identifier | Service |
|-------------------|---------|
| `aws/guardduty` | Amazon GuardDuty |
| `aws/macie` | Amazon Macie |
| `aws/inspector2` | Amazon Inspector |
| `aws/access-analyzer` | IAM Access Analyzer |
| `aws/firewall-manager` | AWS Firewall Manager |
| `aws/health` | AWS Health |
| `aws/systems-manager-patch-manager` | Systems Manager Patch Manager |

## How the Script Works

1. **Discovers accounts to process:**
   - **If CSV provided:** Reads account IDs directly from the CSV file
   - **If no CSV:** Uses Security Hub `list_members` API to get all member accounts
2. **For each account and region:**
   - Checks if account is a Security Hub member in that specific region
   - If yes, assumes the specified IAM role in that account
   - Directly disables each specified product (idempotent - safe if already disabled)
   - If account is not a member in a region, skips that region
3. **Reports results** including any failures

### Account Discovery Logic

The script uses the following logic to determine which accounts to process:

| CSV File Provided? | Accounts Processed |
|-------------------|-------------------|
| ✅ Yes | **Accounts from CSV file** |
| ❌ No | **All Security Hub member accounts** |

**Example scenarios:**
- CSV has [A, B, C] → Attempts to process [A, B, C] (skips regions where not a member)
- No CSV provided, Security Hub members are [A, B, C] → Processes [A, B, C] (only in regions where they're members)

**Note:** When using a CSV, the script will still check per-region membership. If an account in the CSV is not a Security Hub member in a specific region, that region will be skipped for that account.

## Important Notes

* **Products not currently enabled are skipped** - The script will not error if a specified product is not enabled in an account/region
* **Idempotent operation** - Safe to run multiple times; products already disabled will not cause errors
* **Per-account, per-region processing** - Each account's enabled products are queried independently; the script only disables products that match the specified identifiers
* **Continues on failure** - If one account fails, the script continues processing remaining accounts
* **Works with any account type** - Standalone accounts, organization member accounts, or delegated administrator accounts

## Error Handling

* **Security Hub CSPM not enabled:** If Security Hub CSPM is not enabled in an account/region, that region is skipped with an informational message - this is NOT considered a failure since there are no products to disable
* **Role assumption failures:** If the script cannot assume the role in an account, that account is skipped and reported in the failed accounts summary
* **Product not enabled:** If a specified product is not enabled in a specific account/region, it is silently skipped (not an error)
* **Other errors:** All genuine errors are collected and reported at the end of execution
* **Continues on failure:** Processing continues even if some accounts or regions encounter errors
