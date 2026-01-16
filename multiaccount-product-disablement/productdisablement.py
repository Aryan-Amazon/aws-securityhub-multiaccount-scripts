#!/usr/bin/env python
"""
Copyright 2024 Amazon.com, Inc. or its affiliates. All Rights Reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the "Software"), to deal in the Software
without restriction, including without limitation the rights to use, copy, modify,
merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

import boto3
import re
import argparse
import time

from collections import OrderedDict
from botocore.exceptions import ClientError


def assume_role(aws_account_id, role_name):
    """
    Assumes the provided role in each account and returns a Security Hub CSPM client
    :param aws_account_id: AWS Account ID
    :param role_name: Role to assume in target account
    :return: boto3 Session object
    """
    
    sts_client = boto3.client('sts')
    
    # Get the current partition
    partition = sts_client.get_caller_identity()['Arn'].split(":")[1]
    
    response = sts_client.assume_role(
        RoleArn='arn:{}:iam::{}:role/{}'.format(
            partition,
            aws_account_id,
            role_name
        ),
        RoleSessionName='DisableSecurityHubCSPMProducts'
    )
    
    # Storing STS credentials
    session = boto3.Session(
        aws_access_key_id=response['Credentials']['AccessKeyId'],
        aws_secret_access_key=response['Credentials']['SecretAccessKey'],
        aws_session_token=response['Credentials']['SessionToken']
    )

    print("Assumed session for {}.".format(aws_account_id))

    return session


def get_admin_members(sh_client, aws_region):
    """
    Returns a dict of current members of the Security Hub Administrator account
    :param sh_client: SecurityHub client
    :param aws_region: AWS Region of the Security Hub Administrator account
    :return: dict of AwsAccountId:RelationshipStatus
    """
    
    member_dict = dict()
    
    results = sh_client.list_members(
        OnlyAssociated=False
    )
    
    for member in results['Members']:
        member_dict.update({member['AccountId']: member['MemberStatus']})
        
    while results.get("NextToken"):
        results = sh_client.list_members(
            OnlyAssociated=False,
            NextToken=results['NextToken']
        )
        
        for member in results['Members']:
            member_dict.update({member['AccountId']: member['MemberStatus']})
            
    return member_dict


if __name__ == '__main__':
    
    # Setup command line arguments
    parser = argparse.ArgumentParser(description='Disable Security Hub CSPM product integrations across multiple AWS accounts')
    parser.add_argument('input_file', nargs='?', type=argparse.FileType('r'), help='Optional: Path to CSV file containing account IDs (one per line). If not provided, uses all Security Hub member accounts')
    parser.add_argument('--assume_role', type=str, required=True, help="Role Name to assume in each account")
    parser.add_argument('--regions-to-disable', type=str, required=True, help="Comma separated list of regions to disable products, or 'ALL' for all available regions")
    parser.add_argument('--products', type=str, required=True, help="Comma separated list of product identifiers to disable (e.g., 'aws/guardduty,aws/macie' or product ARNs)")
    args = parser.parse_args()
    
    # Parse product list
    product_identifiers = [str(item).strip() for item in args.products.split(',')]
    print("Products to disable: {}".format(product_identifiers))
    
    # Getting Security Hub regions
    session = boto3.session.Session()
    
    securityhub_regions = []
    if args.regions_to_disable.upper() == 'ALL':
        securityhub_regions = session.get_available_regions('securityhub')
        print("Will check for members in all available Security Hub CSPM regions: {}".format(securityhub_regions))
    else:
        securityhub_regions = [str(item).strip() for item in args.regions_to_disable.split(',')]
        print("Will check for members in these regions: {}".format(securityhub_regions))
    
    # Get Security Hub member accounts from all regions
    admin_clients = {}
    members = {}
    all_member_accounts = set()
    
    for aws_region in securityhub_regions:
        admin_clients[aws_region] = session.client('securityhub', region_name=aws_region)
        try:
            members[aws_region] = get_admin_members(admin_clients[aws_region], aws_region)
            all_member_accounts.update(members[aws_region].keys())
            print("Found {} member accounts in region {}".format(len(members[aws_region]), aws_region))
        except ClientError as e:
            print("Error listing members in region {}: {}".format(aws_region, repr(e)))
            members[aws_region] = {}
    
    print("Total unique Security Hub CSPM member accounts across all regions: {}".format(len(all_member_accounts)))
    
    # Generate dict with account information
    aws_account_dict = OrderedDict()
    csv_accounts = set()
    
    # If CSV file provided, read account IDs from it
    if args.input_file:
        print("CSV file provided - will process accounts from CSV")
        for acct in args.input_file.readlines():
            split_line = acct.rstrip().split(",")
            if len(split_line) < 1:
                print("Unable to process line: {}".format(acct))
                continue
            
            account_id = split_line[0].strip()
            
            if not re.match(r'[0-9]{12}', account_id):
                print("Invalid account number {}, skipping".format(account_id))
                continue
                
            csv_accounts.add(account_id)
        
        # Use CSV accounts directly
        accounts_to_process = csv_accounts
        print("Processing {} accounts from CSV file".format(len(accounts_to_process)))
            
    else:
        # No CSV provided - use all member accounts
        print("No CSV file provided - will process all Security Hub member accounts")
        accounts_to_process = all_member_accounts
    
    # Build ordered dict from accounts to process
    for account_id in sorted(accounts_to_process):
        aws_account_dict[account_id] = True
    
    if len(aws_account_dict) == 0:
        print("ERROR: No accounts to process. Exiting.")
        exit(1)
    
    print("Total accounts to process: {}".format(len(aws_account_dict)))
    print("Disabling products in regions: {}".format(securityhub_regions))
    
    # Processing accounts
    failed_accounts = []
    for account in aws_account_dict.keys():
        try:
            session = assume_role(account, args.assume_role)
            
            for aws_region in securityhub_regions:
                # Check if account is a member in this specific region
                if account not in members[aws_region]:
                    print('Account {account} is not a Security Hub CSPM member in region {region} - skipping'.format(
                        account=account,
                        region=aws_region
                    ))
                    continue
                
                print('Beginning {account} in {region}'.format(
                    account=account,
                    region=aws_region
                ))
                
                sh_client = session.client('securityhub', region_name=aws_region)
                
                # Directly disable specified products (idempotent - safe if already disabled)
                for product_identifier in product_identifiers:
                    try:
                        # Construct ProductSubscriptionArn
                        # Format: arn:aws:securityhub:region:account-id:product-subscription/provider/product
                        product_arn = 'arn:aws:securityhub:{region}:{account}:product-subscription/{product}'.format(
                            region=aws_region,
                            account=account,
                            product=product_identifier
                        )
                        
                        sh_client.disable_import_findings_for_product(
                            ProductSubscriptionArn=product_arn
                        )
                        print('  Disabled product {product} in account {account} region {region}'.format(
                            product=product_identifier,
                            account=account,
                            region=aws_region
                        ))
                        
                    except ClientError as e:
                        error_code = e.response['Error']['Code']
                        # These errors are expected and not failures
                        if error_code == 'ResourceNotFoundException':
                            # Product not enabled or already disabled - this is fine
                            print('  Product {product} not enabled in account {account} region {region} - skipping'.format(
                                product=product_identifier,
                                account=account,
                                region=aws_region
                            ))
                        elif error_code in ['InvalidAccessException']:
                            # Security Hub not enabled
                            print('  Security Hub CSPM not enabled in account {account} region {region} - skipping'.format(
                                account=account,
                                region=aws_region
                            ))
                        else:
                            # Actual error - record it
                            print("  Error disabling product {product} in account {account} region {region}: {error}".format(
                                product=product_identifier,
                                account=account,
                                region=aws_region,
                                error=repr(e)
                            ))
                            failed_accounts.append({
                                account: "Error disabling {}: {}".format(product_identifier, repr(e))
                            })
                
                print('Finished {account} in {region}'.format(account=account, region=aws_region))
                    
        except ClientError as e:
            print("Error Processing Account {}".format(account))
            failed_accounts.append({
                account: repr(e)
            })

    if len(failed_accounts) > 0:
        print("---------------------------------------------------------------")
        print("Failed Accounts")
        print("---------------------------------------------------------------")
        for account in failed_accounts:
            for account_id, message in account.items():
                print("{}: \n\t{}".format(account_id, message))
        print("---------------------------------------------------------------")
