# AWS Security Hub Multi-Account Product Disablement Script

## Overview

This script automates the process of disabling specific AWS Security Hub product integrations across multiple AWS accounts. 

## License Summary

This sample code is made available under a modified MIT license. See the LICENSE file.

## Prerequisites

* The script depends on a pre-existing IAM role in all target accounts that will be processed. The role name must be the same in all accounts and the role trust relationship needs to allow your instance or local credentials to assume the role. The policy document below contains the required permissions for the script to succeed:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "securityhub:ListEnabledProductsForImport",
                "securityhub:DisableImportFindingsForProduct"
            ],
            "Resource": "*"
        }
    ]
}
```

**Execution Account Permissions:** The account/role executing this script (typically the delegated administrator) needs `securityhub:ListMembers` permission to auto-discover member accounts:

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

If you do not have a common role that includes at least the above permissions, you will need to create a role in each account with these permissions. When creating the role, ensure you use the same role name in every account. See `iam-policy-example.json` for a complete policy template and `trust-policy-example.json` for the trust relationship.

* **Optional:** A CSV file that includes the list of accounts to be processed. Accounts should be listed one per line with the account ID. Format: `AccountId`. See `accounts.csv.example` for a sample file.
  - If CSV is provided: Script processes the **intersection** of CSV accounts and Security Hub member accounts
  - If CSV is not provided: Script processes **all** Security Hub member accounts

## Creating the IAM Role

If the SecurityHubRole doesn't exist in your target accounts, create it using the AWS CLI:

```bash
# In each target account, run:

# 1. Create trust policy (replace EXECUTION_ACCOUNT_ID with your account)
cat > trust-policy.json << 'EOF'
{
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {
            "AWS": "arn:aws:iam::EXECUTION_ACCOUNT_ID:root"
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
            "securityhub:ListEnabledProductsForImport",
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

**Execution account needs:**
```json
{
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Action": "sts:AssumeRole",
        "Resource": "arn:aws:iam::*:role/SecurityHubRole"
    }]
}
```

See `trust-policy-example.json` and `iam-policy-example.json` for complete templates.

* Python 2.7+ or Python 3.x with boto3 library installed

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

When running from a delegated administrator account, the script can automatically discover all Security Hub member accounts:

```bash
# Disable GuardDuty across ALL member accounts in all regions
python productdisablement.py \
    --assume_role SecurityHubRole \
    --regions-to-disable ALL \
    --products "aws/guardduty"
```

```bash
# Disable multiple products across ALL member accounts in specific regions
python productdisablement.py \
    --assume_role SecurityHubRole \
    --regions-to-disable us-east-1,us-west-2,eu-west-1 \
    --products "aws/guardduty,aws/macie,aws/inspector2"
```

### Using CSV File (Intersection with Member Accounts)

When providing a CSV file, the script processes only accounts that are BOTH in the CSV and in Security Hub members:

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
   - **If CSV provided:** Reads account IDs from CSV and finds intersection with Security Hub member accounts
   - **If no CSV:** Uses Security Hub `list_members` API to get all member accounts
2. **For each account:**
   - Assumes the specified IAM role in that account
   - Queries Security Hub to list all currently enabled product integrations in each region
   - Compares enabled products against the products specified in `--products` parameter
   - Disables any matching products
3. **Reports results** including any failures

### Account Discovery Logic

The script uses the following logic to determine which accounts to process:

| CSV File Provided? | Accounts Processed |
|-------------------|-------------------|
| ✅ Yes | **Intersection** of CSV accounts AND Security Hub members |
| ❌ No | **All** Security Hub member accounts |

**Example scenarios:**
- CSV has [A, B, C], Security Hub members are [B, C, D] → Processes [B, C]
- CSV has [A, B], Security Hub members are [X, Y, Z] → Warning: no common accounts
- No CSV provided, Security Hub members are [A, B, C] → Processes [A, B, C]

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
