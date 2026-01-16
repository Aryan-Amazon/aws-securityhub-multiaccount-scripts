# StackSet Test Deployment Guide

This guide walks you through testing CloudFormation StackSet deployment of the SecurityHub role.

## Prerequisites

1. **Management Account Access** - You need access to your AWS Organizations management account
2. **DA Account ID** - Your Security Hub Delegated Administrator account ID
3. **Test Member Accounts** - At least 1-2 member accounts for testing

## Step 1: Enable CloudFormation StackSets (One-Time Setup)

If this is your first time using StackSets with AWS Organizations, enable trusted access:

```bash
aws organizations enable-aws-service-access \
    --service-principal member.org.stacksets.cloudformation.amazonaws.com
```

Verify it's enabled:
```bash
aws organizations list-aws-service-access-for-organization \
    --query 'EnabledServicePrincipals[?ServicePrincipal==`member.org.stacksets.cloudformation.amazonaws.com`]'
```

## Step 2: Create the Test StackSet

Replace `YOUR_DA_ACCOUNT_ID` with your actual DA account ID:

```bash
aws cloudformation create-stack-set \
    --stack-set-name SecurityHubTestRoleDeployment \
    --template-body file://SecurityHubRole-StackSet-TEST.yaml \
    --description "TEST - Deploy SecurityHub test role to member accounts" \
    --parameters ParameterKey=DelegatedAdminAccountId,ParameterValue=YOUR_DA_ACCOUNT_ID \
    --permission-model SERVICE_MANAGED \
    --auto-deployment Enabled=true,RetainStacksOnAccountRemoval=false \
    --capabilities CAPABILITY_NAMED_IAM
```

Expected output:
```json
{
    "StackSetId": "SecurityHubTestRoleDeployment:..."
}
```

## Step 3: Deploy to Test Accounts

### Option A: Deploy to Specific Accounts (Recommended for Testing)

Replace with your actual test account IDs:

```bash
aws cloudformation create-stack-instances \
    --stack-set-name SecurityHubTestRoleDeployment \
    --deployment-targets Accounts=111111111111,222222222222 \
    --regions us-east-1 \
    --operation-preferences \
        FailureToleranceCount=0,\
        MaxConcurrentCount=2
```

### Option B: Deploy to Organizational Unit

If you have a test OU, use its ID:

```bash
aws cloudformation create-stack-instances \
    --stack-set-name SecurityHubTestRoleDeployment \
    --deployment-targets OrganizationalUnitIds=ou-xxxx-xxxxxxxx \
    --regions us-east-1 \
    --operation-preferences \
        FailureTolerancePercentage=10,\
        MaxConcurrentPercentage=20
```

Expected output:
```json
{
    "OperationId": "xxx-yyy-zzz"
}
```

## Step 4: Monitor Deployment

Check deployment status (replace OPERATION_ID with the one from previous step):

```bash
aws cloudformation describe-stack-set-operation \
    --stack-set-name SecurityHubTestRoleDeployment \
    --operation-id OPERATION_ID
```

Check which accounts succeeded/failed:

```bash
aws cloudformation list-stack-instances \
    --stack-set-name SecurityHubTestRoleDeployment
```

Wait until status shows `SUCCEEDED` for all accounts.

## Step 5: Verify Role Creation

SSH into your DA account and verify you can assume the test role:

```bash
# Test assuming the role in one of your member accounts
aws sts assume-role \
    --role-arn arn:aws:iam::MEMBER_ACCOUNT_ID:role/SecurityHubTestRole \
    --role-session-name TestSession

# If successful, you'll get credentials in the response
```

## Step 6: Test the Script

Update your test command to use the test role:

```bash
cd multiaccount-product-disablement

# Test with SecurityHubTestRole
python3 productdisablement.py \
    --assume_role SecurityHubTestRole \
    --regions-to-disable us-east-1 \
    --products aws/guardduty
```

## Step 7: Verify Results

1. Check the script output - should show successful product disablement
2. Log into a member account console
3. Navigate to Security Hub → Integrations
4. Verify that GuardDuty integration was disabled

## Cleanup After Testing

Once testing is complete, remove the test StackSet:

```bash
# First, delete all stack instances
aws cloudformation delete-stack-instances \
    --stack-set-name SecurityHubTestRoleDeployment \
    --deployment-targets Accounts=111111111111,222222222222 \
    --regions us-east-1 \
    --no-retain-stacks

# Wait for deletion to complete, then delete the StackSet
aws cloudformation delete-stack-set \
    --stack-set-name SecurityHubTestRoleDeployment
```

This will remove the `SecurityHubTestRole` from all member accounts.

## Troubleshooting

### Error: "StackSet not found"
- Verify you're in the management account
- Check the StackSet name spelling

### Error: "Insufficient permissions"
- Ensure StackSets trusted access is enabled (Step 1)
- Verify your user has CloudFormation permissions

### Stack Instance Failed
```bash
# Get detailed error
aws cloudformation describe-stack-instance \
    --stack-set-name SecurityHubTestRoleDeployment \
    --stack-instance-account ACCOUNT_ID \
    --stack-instance-region us-east-1
```

### Role assumption fails
- Verify the DA account ID is correct in the StackSet parameters
- Check that the member account has the role: `aws iam get-role --role-name SecurityHubTestRole`

## Next Steps After Successful Test

If testing is successful:
1. Clean up test resources (see Cleanup section)
2. Create production template: `SecurityHubRole-StackSet.yaml`
3. Deploy production StackSet with role name `SecurityHubRole`
4. Update all member accounts
5. Run production script

## Questions?

If you encounter issues, check:
- CloudFormation console → StackSets
- CloudTrail logs for detailed API errors
- Member account IAM console to verify role exists
