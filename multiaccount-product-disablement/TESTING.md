# Testing Guide for Multi-Account Product Disablement Script

## Overview

This guide provides a comprehensive approach to test the productdisablement.py script safely before using it in production.

## Testing Strategy

Follow this progression:
1. **Syntax Validation** - Ensure the script has no errors
2. **Single Account Test** - Test with one account first
3. **Dry-Run Simulation** - Verify what would be disabled
4. **Small-Scale Test** - Test with 2-3 accounts
5. **Production Run** - Full deployment

---

## Phase 1: Prerequisites Validation

### 1.1 Verify Python and Dependencies

```bash
# Check Python version (2.7+ or 3.x required)
python --version

# Check boto3 is installed
python -c "import boto3; print(boto3.__version__)"

# If boto3 not installed:
pip install boto3
```

### 1.2 Verify Script Syntax

```bash
cd multiaccount-product-disablement
python -m py_compile productdisablement.py

# Should complete without errors
```

### 1.3 Verify AWS Credentials

```bash
# Verify you have valid AWS credentials
aws sts get-caller-identity

# Should return your account ID, user ARN, and user ID
```

---

## Phase 2: IAM Role Setup

### 2.1 Create Test Role in Target Account(s)

**Option A: Using AWS Console**
1. Go to IAM → Roles → Create Role
2. Select "Another AWS Account"
3. Enter the Account ID that will run the script
4. Attach policy using `iam-policy-example.json` content
5. Name it: `SecurityHubProductDisablementRole` (or your preferred name)

**Option B: Using AWS CLI**

```bash
# Replace 111111111111 with your script execution account ID
aws iam create-role \
    --role-name SecurityHubProductDisablementRole \
    --assume-role-policy-document file://trust-policy-example.json

# Attach the policy
aws iam put-role-policy \
    --role-name SecurityHubProductDisablementRole \
    --policy-name SecurityHubProductDisablement \
    --policy-document file://iam-policy-example.json
```

### 2.2 Verify Role Can Be Assumed

```bash
# Replace 222222222222 with target account ID
aws sts assume-role \
    --role-arn arn:aws:iam::222222222222:role/SecurityHubProductDisablementRole \
    --role-session-name TestSession

# Should return temporary credentials
```

---

## Phase 3: Test Account Preparation

### 3.1 Create Test CSV with ONE Account

Create `test-single-account.csv`:
```
222222222222,test-account@example.com
```

### 3.2 Verify Products Are Enabled in Test Account

**Using AWS Console:**
1. Log into test account
2. Go to Security Hub → Integrations
3. Note which products are currently enabled

**Using AWS CLI:**
```bash
# Assume role into test account first
aws securityhub list-enabled-products-for-import \
    --region us-east-1

# Save this output - you'll need it to verify
```

---

## Phase 4: Dry-Run Test

Since the script doesn't have a built-in dry-run mode, we'll test with a non-existent product first to ensure the script runs without actually disabling anything.

### 4.1 Test Script Execution (Safe)

```bash
# Test with a product that doesn't exist - this will run but skip everything
python productdisablement.py test-single-account.csv \
    --assume_role SecurityHubProductDisablementRole \
    --enabled_regions us-east-1 \
    --products "fake/product-that-does-not-exist"
```

**Expected Output:**
```
Products to disable: ['fake/product-that-does-not-exist']
Disabling products in these regions: ['us-east-1']
Assumed session for 222222222222.
Beginning 222222222222 in us-east-1
Finished 222222222222 in us-east-1
```

**Success Criteria:**
- ✅ Script runs without errors
- ✅ Successfully assumes role
- ✅ Processes account without failures
- ✅ No actual products were disabled

---

## Phase 5: Single Account Real Test

### 5.1 Choose a Non-Critical Product to Test

Pick a product that's safe to disable temporarily (one you can easily re-enable):
- `aws/health` (AWS Health findings)
- Or another non-critical integration in your test environment

### 5.2 Document Current State

```bash
# Before running, document what products are enabled
aws securityhub list-enabled-products-for-import \
    --region us-east-1 > before-test.txt
```

### 5.3 Run Real Disablement

```bash
# Disable AWS Health in ONE account, ONE region
python productdisablement.py test-single-account.csv \
    --assume_role SecurityHubProductDisablementRole \
    --enabled_regions us-east-1 \
    --products "aws/health"
```

**Expected Output:**
```
Products to disable: ['aws/health']
Disabling products in these regions: ['us-east-1']
Assumed session for 222222222222.
Beginning 222222222222 in us-east-1
  Disabled product aws/health in account 222222222222 region us-east-1
Finished 222222222222 in us-east-1
```

### 5.4 Verify Disablement

```bash
# Check products now
aws securityhub list-enabled-products-for-import \
    --region us-east-1 > after-test.txt

# Compare
diff before-test.txt after-test.txt
```

**Verification in Console:**
1. Log into Security Hub → Integrations
2. Confirm aws/health is no longer enabled
3. Check that other products are still enabled

---

## Phase 6: Re-enable Test Product

### 6.1 Re-enable the Disabled Product

```bash
# Get product ARN (from before-test.txt or docs)
aws securityhub enable-import-findings-for-product \
    --product-arn arn:aws:securityhub:us-east-1::product/aws/health \
    --region us-east-1
```

### 6.2 Verify Re-enablement

```bash
aws securityhub list-enabled-products-for-import --region us-east-1
```

**Success Criteria:**
- ✅ Product was successfully disabled
- ✅ Other products remained enabled
- ✅ Product can be re-enabled
- ✅ No errors in script execution

---

## Phase 7: Multi-Account Small-Scale Test

### 7.1 Create Multi-Account Test CSV

Create `test-multi-account.csv` with 2-3 test accounts:
```
222222222222,account1@example.com
333333333333,account2@example.com
444444444444,account3@example.com
```

### 7.2 Run Multi-Account Test

```bash
# Test with non-critical product across 3 accounts
python productdisablement.py test-multi-account.csv \
    --assume_role SecurityHubProductDisablementRole \
    --enabled_regions us-east-1 \
    --products "aws/health"
```

### 7.3 Verify All Accounts

For each account:
```bash
# Check each account
aws securityhub list-enabled-products-for-import \
    --region us-east-1 \
    --profile account1

aws securityhub list-enabled-products-for-import \
    --region us-east-1 \
    --profile account2
```

---

## Phase 8: Production Deployment

### 8.1 Final Pre-Production Checklist

- [ ] IAM roles deployed in ALL target accounts
- [ ] Trust relationships configured correctly
- [ ] Complete CSV file created with all production accounts
- [ ] Product identifiers verified (check product names carefully)
- [ ] Rollback plan documented (how to re-enable if needed)
- [ ] Stakeholders notified
- [ ] Backup of current SecurityHub configurations

### 8.2 Production Run

```bash
# Create production CSV
cp accounts.csv.example accounts-prod.csv
# Edit accounts-prod.csv with real account IDs

# Run with real products to disable
python productdisablement.py accounts-prod.csv \
    --assume_role SecurityHubProductDisablementRole \
    --products "aws/guardduty,aws/macie" \
    2>&1 | tee disable-products-$(date +%Y%m%d-%H%M%S).log
```

**Note:** The `tee` command saves output to both screen and log file for audit trail.

---

## Troubleshooting Common Issues

### Issue: "Error Processing Account"

**Possible Causes:**
- Role doesn't exist in that account
- Trust relationship not configured
- Role name mismatch

**Solution:**
```bash
# Verify role exists
aws iam get-role --role-name SecurityHubProductDisablementRole

# Verify you can assume it
aws sts assume-role \
    --role-arn arn:aws:iam::ACCOUNT_ID:role/SecurityHubProductDisablementRole \
    --role-session-name Test
```

### Issue: "No products enabled"

**Possible Causes:**
- SecurityHub not enabled in that account/region
- No products actually enabled
- Wrong region specified

**Solution:**
- Log into account, check Security Hub is enabled
- Verify products are enabled: Security Hub → Integrations

### Issue: Product not being disabled

**Possible Causes:**
- Product name typo
- Product not actually enabled
- Wrong product identifier

**Solution:**
```bash
# List what's actually enabled
aws securityhub list-enabled-products-for-import --region us-east-1

# Check the product identifiers carefully
```

---

## Rollback Procedure

If you need to re-enable products:

### Method 1: AWS Console (Simple)
1. Log into each account
2. Go to Security Hub → Integrations
3. Click "Enable" on each product

### Method 2: AWS CLI (Batch)

```bash
# Re-enable GuardDuty in us-east-1
aws securityhub enable-import-findings-for-product \
    --product-arn arn:aws:securityhub:us-east-1::product/aws/guardduty \
    --region us-east-1
```

### Method 3: Create Re-enablement Script

Save before-state, then create a script to restore:
```bash
# Save current state before disabling
aws securityhub list-enabled-products-for-import > backup-products.txt
```

---

## Best Practices

1. **Always test in non-production first**
2. **Start with one account before scaling**
3. **Document current state before changes**
4. **Save script output for audit trail**
5. **Have rollback plan ready**
6. **Notify stakeholders before large-scale changes**
7. **Test with non-critical products first**

---

## Success Indicators

Your testing is successful when:
- ✅ Script runs without Python errors
- ✅ Successfully assumes roles in all accounts
- ✅ Products are correctly identified and disabled
- ✅ Non-matching products remain enabled
- ✅ Can re-enable products when needed
- ✅ Error handling works (failed accounts are reported)
- ✅ Works across multiple regions
- ✅ Idempotent (can run multiple times safely)
