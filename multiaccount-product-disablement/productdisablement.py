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
    Assumes the provided role in each account and returns a SecurityHub client
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
        RoleSessionName='DisableSecurityHubProducts'
    )
    
    # Storing STS credentials
    session = boto3.Session(
        aws_access_key_id=response['Credentials']['AccessKeyId'],
        aws_secret_access_key=response['Credentials']['SecretAccessKey'],
        aws_session_token=response['Credentials']['SessionToken']
    )

    print("Assumed session for {}.".format(aws_account_id))

    return session


if __name__ == '__main__':
    
    # Setup command line arguments
    parser = argparse.ArgumentParser(description='Disable Security Hub CSPM product integrations across multiple AWS accounts')
    parser.add_argument('input_file', type=argparse.FileType('r'), help='Path to CSV file containing account IDs (one per line, optional email addresses ignored)')
    parser.add_argument('--assume_role', type=str, required=True, help="Role Name to assume in each account")
    parser.add_argument('--enabled_regions', type=str, help="Comma separated list of regions to disable products. If not specified, all available regions disabled")
    parser.add_argument('--products', type=str, required=True, help="Comma separated list of product identifiers to disable (e.g., 'aws/guardduty,aws/macie' or product ARNs)")
    args = parser.parse_args()
    
    # Parse product list
    product_identifiers = [str(item).strip() for item in args.products.split(',')]
    print("Products to disable: {}".format(product_identifiers))
    
    # Generate dict with account information
    aws_account_dict = OrderedDict()
    
    for acct in args.input_file.readlines():
        split_line = acct.rstrip().split(",")
        if len(split_line) < 1:
            print("Unable to process line: {}".format(acct))
            continue
        
        account_id = split_line[0].strip()
        
        if not re.match(r'[0-9]{12}', account_id):
            print("Invalid account number {}, skipping".format(account_id))
            continue
            
        aws_account_dict[account_id] = True
    
    # Getting Security Hub CSPM regions
    session = boto3.session.Session()
    
    securityhub_regions = []
    if args.enabled_regions:
        securityhub_regions = [str(item).strip() for item in args.enabled_regions.split(',')]
        print("Disabling products in these regions: {}".format(securityhub_regions))
    else:
        securityhub_regions = session.get_available_regions('securityhub')
        print("Disabling products in all available Security Hub CSPM regions {}".format(securityhub_regions))
    
    # Processing accounts
    failed_accounts = []
    for account in aws_account_dict.keys():
        try:
            session = assume_role(account, args.assume_role)
            
            for aws_region in securityhub_regions:
                print('Beginning {account} in {region}'.format(
                    account=account,
                    region=aws_region
                ))
                
                sh_client = session.client('securityhub', region_name=aws_region)
                
                # Get list of enabled products for this account/region
                try:
                    enabled_products_response = sh_client.list_enabled_products_for_import()
                    enabled_products = enabled_products_response.get('ProductSubscriptions', [])
                    
                    if not enabled_products:
                        print('  No products enabled in account {account} region {region}'.format(
                            account=account,
                            region=aws_region
                        ))
                        continue
                    
                    # Disable specified products
                    for product_subscription_arn in enabled_products:
                        # Check if this product matches any of our identifiers
                        # ProductSubscriptionArn format: arn:aws:securityhub:region:account-id:product-subscription/product-provider/product-name
                        product_name = product_subscription_arn.split('/')[-2] + '/' + product_subscription_arn.split('/')[-1]
                        
                        # Check if this product should be disabled
                        should_disable = False
                        for identifier in product_identifiers:
                            if identifier in product_subscription_arn or identifier == product_name:
                                should_disable = True
                                break
                        
                        if should_disable:
                            try:
                                sh_client.disable_import_findings_for_product(
                                    ProductSubscriptionArn=product_subscription_arn
                                )
                                print('  Disabled product {product} in account {account} region {region}'.format(
                                    product=product_name,
                                    account=account,
                                    region=aws_region
                                ))
                            except ClientError as e:
                                print("  Error disabling product {product} in account {account} region {region}: {error}".format(
                                    product=product_name,
                                    account=account,
                                    region=aws_region,
                                    error=repr(e)
                                ))
                                failed_accounts.append({
                                    account: "Error disabling {}: {}".format(product_name, repr(e))
                                })
                    
                except ClientError as e:
                    print("Error listing products for account {account} in region {region}: {error}".format(
                        account=account,
                        region=aws_region,
                        error=repr(e)
                    ))
                    failed_accounts.append({
                        account: repr(e)
                    })
                    continue
                
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
