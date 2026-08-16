#!/usr/bin/env python3
"""
AWS Infrastructure Installer using boto3
This script creates AWS infrastructure resources for local development.
"""

import boto3
import json
import time
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional
from botocore.exceptions import ClientError
from bedrock_agentcore.memory import MemoryClient

# Configuration
project_name = "mcp-manus"  # at least 3 characters
region = "us-west-2"
AGENTCORE_GATEWAY_REGION = "us-east-1"
AGENTCORE_WEBSEARCH_GATEWAY_NAME = "gateway-websearch"
AGENTCORE_WEBSEARCH_TARGET_NAME = "websearch"
vector_index_name = project_name
cloudfront_comment = "CloudFront-for-rag-project"
oai_comment = f"OAI for {vector_index_name}"

sts_client = boto3.client("sts", region_name=region)
account_id = sts_client.get_caller_identity()["Account"]

# Parsing model for Knowledge Base data source
# Alternative: global.anthropic.claude-haiku-4-5-20251001-v1:0
parsing_model_arn = (
    f"arn:aws:bedrock:{region}:{account_id}:inference-profile/global.anthropic.claude-sonnet-4-6"
)

knowledge_base_name = project_name
knowledge_base_role_name = f"role-knowledge-base-for-{project_name}-{region}"

s3_client = boto3.client("s3", region_name=region)
iam_client = boto3.client("iam", region_name=region)
secrets_client = boto3.client("secretsmanager", region_name=region)
opensearch_client = boto3.client("opensearchserverless", region_name=region)
cloudfront_client = boto3.client("cloudfront", region_name=region)
agentcore_control_client = boto3.client(
    "bedrock-agentcore-control",
    region_name=AGENTCORE_GATEWAY_REGION,
)

bucket_name = f"storage-for-rag-project-{account_id}-{region}"

def setup_logging(log_level=logging.INFO):
    """Setup logging configuration."""
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(),
            # logging.FileHandler(f"installer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        ]
    )
    
    return logging.getLogger(__name__)


logger = setup_logging()


def create_s3_bucket() -> str:
    """Create S3 bucket with CORS configuration."""
    logger.info(f"[2/6] Creating S3 bucket: {bucket_name}")
    
    try:
        # Create bucket
        logger.debug(f"Creating bucket in region: {region}")
        if region == "us-east-1":
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": region}
            )
        logger.debug("Bucket created successfully")
        
        # Configure bucket
        logger.debug("Configuring public access block")
        s3_client.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True
            }
        )
        
        # Set CORS configuration
        logger.debug("Setting CORS configuration")
        cors_configuration = {
            "CORSRules": [
                {
                    "AllowedHeaders": ["*"],
                    "AllowedMethods": ["GET", "POST", "PUT"],
                    "AllowedOrigins": ["*"]
                }
            ]
        }
        s3_client.put_bucket_cors(
            Bucket=bucket_name,
            CORSConfiguration=cors_configuration
        )
        
        # Enable versioning (set to false means suspend)
        logger.debug("Configuring versioning")
        s3_client.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={"Status": "Suspended"}
        )
        
        # Create docs/{project_name}/ folder (data source inclusion prefix)
        docs_prefix = f"docs/{project_name}/"
        logger.debug("Creating %s folder", docs_prefix)
        try:
            s3_client.put_object(
                Bucket=bucket_name,
                Key=docs_prefix,
                Body=b""
            )
            logger.debug("%s folder created successfully", docs_prefix)
        except ClientError as e:
            logger.warning(f"Failed to create {docs_prefix} folder: {e}")
        
        logger.info(f"✓ S3 bucket created successfully: {bucket_name}")
        return bucket_name
    
    except ClientError as e:
        if e.response["Error"]["Code"] in ["BucketAlreadyExists", "BucketAlreadyOwnedByYou"]:
            logger.warning(f"S3 bucket already exists: {bucket_name}")
            # Create docs/{project_name}/ folder if bucket already exists
            docs_prefix = f"docs/{project_name}/"
            logger.debug("Creating %s folder in existing bucket", docs_prefix)
            try:
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=docs_prefix,
                    Body=b""
                )
                logger.debug("%s folder created successfully", docs_prefix)
            except ClientError as folder_error:
                if folder_error.response["Error"]["Code"] != "NoSuchBucket":
                    logger.warning(f"Failed to create {docs_prefix} folder: {folder_error}")
            return bucket_name
        logger.error(f"Failed to create S3 bucket: {e}")
        raise


def create_iam_role(role_name: str, assume_role_policy: Dict, managed_policies: Optional[List[str]] = None) -> str:
    """Create IAM role."""
    logger.debug(f"Creating IAM role: {role_name}")
    
    try:
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(assume_role_policy),
            Description=f"Role for {role_name}"
        )
        role_arn = response["Role"]["Arn"]
        logger.debug(f"Role created: {role_arn}")
        
        if managed_policies:
            logger.debug(f"Attaching {len(managed_policies)} managed policies")
            for policy_arn in managed_policies:
                iam_client.attach_role_policy(
                    RoleName=role_name,
                    PolicyArn=policy_arn
                )
                logger.debug(f"Attached policy: {policy_arn}")
        
        logger.info(f"✓ IAM role created: {role_name}")
        return role_arn
    
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            logger.warning(f"IAM role already exists: {role_name}")
            response = iam_client.get_role(RoleName=role_name)
            role_arn = response["Role"]["Arn"]
            
            # Update trust policy for existing role
            try:
                logger.info(f"Updating trust policy for existing role: {role_name}")
                iam_client.update_assume_role_policy(
                    RoleName=role_name,
                    PolicyDocument=json.dumps(assume_role_policy)
                )
                logger.info(f"✓ Updated trust policy for role: {role_name}")
                
                # Verify trust policy was updated correctly
                updated_role = iam_client.get_role(RoleName=role_name)
                policy_doc = updated_role["Role"]["AssumeRolePolicyDocument"]
                # Handle both string and dict formats (boto3 may return either)
                if isinstance(policy_doc, str):
                    updated_policy = json.loads(policy_doc)
                else:
                    updated_policy = policy_doc
                logger.debug(f"Verified trust policy: {json.dumps(updated_policy, indent=2)}")
            except ClientError as trust_policy_error:
                logger.error(f"✗ Failed to update trust policy for role {role_name}: {trust_policy_error}")
                logger.error(f"  Error Code: {trust_policy_error.response.get('Error', {}).get('Code')}")
                logger.error(f"  Error Message: {trust_policy_error.response.get('Error', {}).get('Message')}")
                raise
            
            # Update managed policies if provided
            if managed_policies:
                logger.debug(f"Updating managed policies for existing role")
                # Get currently attached managed policies
                try:
                    attached_policies = iam_client.list_attached_role_policies(RoleName=role_name)
                    current_policy_arns = {policy["PolicyArn"] for policy in attached_policies["AttachedPolicies"]}
                    
                    # Attach missing policies
                    for policy_arn in managed_policies:
                        if policy_arn not in current_policy_arns:
                            iam_client.attach_role_policy(
                                RoleName=role_name,
                                PolicyArn=policy_arn
                            )
                            logger.debug(f"Attached missing policy: {policy_arn}")
                except ClientError as policy_error:
                    logger.warning(f"Could not update managed policies: {policy_error}")
            
            return role_arn
        logger.error(f"Failed to create IAM role {role_name}: {e}")
        raise


def attach_inline_policy(role_name: str, policy_name: str, policy_document: Dict):
    """Attach or update inline policy to IAM role."""
    logger.debug(f"Attaching/updating inline policy {policy_name} to {role_name}")
    
    try:
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document)
        )
        logger.debug(f"Policy {policy_name} attached/updated successfully")
    except ClientError as e:
        logger.error(f"Error attaching/updating policy {policy_name}: {e}")
        raise


def create_knowledge_base_role() -> str:
    """Create Knowledge Base IAM role."""
    logger.info("[3/6] Creating Knowledge Base IAM role")
    role_name = knowledge_base_role_name
    
    assume_role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    role_arn = create_iam_role(role_name, assume_role_policy)
    
    # Always attach/update inline policies (put_role_policy will create or update)
    bedrock_invoke_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock:*",
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:GetInferenceProfile",
                    "bedrock:GetFoundationModel"
                ],
                "Resource": [
                    "*",
                    f"arn:aws:bedrock:{region}:{account_id}:inference-profile/*",
                    f"arn:aws:bedrock:{region}:*:inference-profile/*",
                    "arn:aws:bedrock:*::foundation-model/*"
                ]
            }
        ]
    }
    attach_inline_policy(role_name, f"bedrock-invoke-policy-for-{project_name}", bedrock_invoke_policy)
    
    s3_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:*"],
                "Resource": ["*"]
            }
        ]
    }
    attach_inline_policy(role_name, f"knowledge-base-s3-policy-for-{project_name}", s3_policy)
    
    opensearch_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["aoss:APIAccessAll"],
                "Resource": ["*"]
            }
        ]
    }
    attach_inline_policy(role_name, f"bedrock-agent-opensearch-policy-for-{project_name}", opensearch_policy)
    
    bedrock_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock:*",
                    "bedrock:GetInferenceProfile"
                ],
                "Resource": [
                    "*",
                    f"arn:aws:bedrock:{region}:*:inference-profile/*"
                ]
            }
        ]
    }
    attach_inline_policy(role_name, f"bedrock-agent-bedrock-policy-for-{project_name}", bedrock_policy)
    
    return role_arn


def create_agent_role() -> str:
    """Create Agent IAM role."""
    logger.info("[3/6] Creating Agent IAM role")
    role_name = f"role-agent-for-{project_name}-{region}"
    
    assume_role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    role_arn = create_iam_role(role_name, assume_role_policy, ["arn:aws:iam::aws:policy/AWSLambdaExecute"])
    
    # Always attach/update inline policies
    bedrock_retrieve_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["bedrock:Retrieve"],
                "Resource": [f"arn:aws:bedrock:{region}:{account_id}:knowledge-base/*"]
            }
        ]
    }
    attach_inline_policy(role_name, f"bedrock-retrieve-policy-for-{project_name}", bedrock_retrieve_policy)
    
    inference_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:GetInferenceProfile",
                    "bedrock:GetFoundationModel"
                ],
                "Resource": [
                    f"arn:aws:bedrock:{region}:{account_id}:inference-profile/*",
                    "arn:aws:bedrock:*::foundation-model/*"
                ]
            }
        ]
    }
    attach_inline_policy(role_name, f"agent-inference-policy-for-{project_name}", inference_policy)
    
    lambda_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["lambda:InvokeFunction", "cloudwatch:*"],
                "Resource": ["*"]
            }
        ]
    }
    attach_inline_policy(role_name, f"lambda-invoke-policy-for-{project_name}", lambda_policy)
    
    bedrock_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["bedrock:*"],
                "Resource": ["*"]
            }
        ]
    }
    attach_inline_policy(role_name, f"bedrock-policy-agent-for-{project_name}", bedrock_policy)
    
    return role_arn


def create_secrets() -> Dict[str, str]:
    """Create Secrets Manager secrets."""
    logger.info("[1/6] Creating Secrets Manager secrets")
    logger.info("Please enter API keys when prompted (press Enter to skip and leave empty):")
    
    secrets = {
        "weather": {
            "name": "openweathermap",
            "description": "secret for weather api key",
            "secret_value": {
                "project_name": project_name,
                "weather_api_key": ""
            }
        },
        "tavily": {
            "name": "tavilyapikey",
            "description": "secret for tavily api key",
            "secret_value": {
                "project_name": project_name,
                "tavily_api_key": "",
                "nova_act_api_key": ""
            }
        },
        "notion": {
            "name": "notionapikey",
            "description": "secret for notion api key",
            "secret_value": {
                "project_name": project_name,
                "notion_api_key": ""
            }
        },
        "telegram": {
            "name": "telegramapikey",
            "description": "secret for telegram api key",
            "secret_value": {
                "project_name": project_name,
                "telegram_api_key": ""
            }
        },
        "discord": {
            "name": "discordapikey",
            "description": "secret for discord bot token",
            "secret_value": {
                "project_name": project_name,
                "discord_bot_token": ""
            }
        },
        "slack": {
            "name": "slackapikey",
            "description": "secret for slack api key",
            "secret_value": {
                "project_name": project_name,
                "slack_team_id": "",
                "slack_bot_token": ""
            }
        }
    }
    
    secret_arns = {}
    
    for key, secret_config in secrets.items():
        # Check if secret already exists before prompting for input
        try:
            response = secrets_client.describe_secret(SecretId=secret_config["name"])
            secret_arns[key] = response["ARN"]
            logger.warning(f"  Secret already exists: {secret_config['name']}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                # Secret doesn't exist, prompt for API key and create it
                if key == "tavily":
                    logger.info(f"Enter credential of {secret_config['name']} (Tavily API Key):")
                    api_key = input(f"Creating {secret_config['name']} - Tavily API Key: ").strip()
                    secret_config["secret_value"]["tavily_api_key"] = api_key
                    secret_config["secret_value"]["nova_act_api_key"] = api_key
                elif key == "notion":
                    logger.info(f"Enter credential of {secret_config['name']} (Notion API Key):")
                    api_key = input(f"Creating {secret_config['name']} - Notion API Key: ").strip()
                    secret_config["secret_value"]["notion_api_key"] = api_key
                elif key == "telegram":
                    logger.info(f"Enter credential of {secret_config['name']} (Telegram Bot API Key):")
                    api_key = input(f"Creating {secret_config['name']} - Telegram Bot API Key: ").strip()
                    secret_config["secret_value"]["telegram_api_key"] = api_key
                elif key == "discord":
                    logger.info(f"Enter credential of {secret_config['name']} (Discord Bot Token):")
                    api_key = input(f"Creating {secret_config['name']} - Discord Bot Token: ").strip()
                    secret_config["secret_value"]["discord_bot_token"] = api_key
                elif key == "slack":
                    logger.info(f"Enter credential of {secret_config['name']} (Slack Team ID and Bot Token):")
                    team_id = input(f"Creating {secret_config['name']} - Slack Team ID: ").strip()
                    bot_token = input(f"Creating {secret_config['name']} - Slack Bot Token: ").strip()
                    secret_config["secret_value"]["slack_team_id"] = team_id
                    secret_config["secret_value"]["slack_bot_token"] = bot_token
                
                # Create the secret
                try:
                    response = secrets_client.create_secret(
                        Name=secret_config["name"],
                        Description=secret_config["description"],
                        SecretString=json.dumps(secret_config["secret_value"])
                    )
                    secret_arns[key] = response["ARN"]
                    logger.info(f"  ✓ Created secret: {secret_config['name']}")
                except ClientError as create_error:
                    logger.error(f"  Failed to create secret {secret_config['name']}: {create_error}")
                    raise
            else:
                logger.error(f"  Failed to check secret {secret_config['name']}: {e}")
                raise
    
    logger.info(f"✓ Created {len(secret_arns)} secrets")
    
    return secret_arns


def _get_installer_iam_arn() -> str:
    """Return IAM ARN for the credentials running this installer."""
    identity = sts_client.get_caller_identity()
    arn = identity["Arn"]
    if ":assumed-role/" in arn:
        role_name = arn.split(":assumed-role/")[1].split("/")[0]
        return f"arn:aws:iam::{identity['Account']}:role/{role_name}"
    return arn


def _opensearch_policy_names() -> Dict[str, str]:
    """Policy names for this project's OpenSearch collection."""
    return {
        "enc": f"enc-{project_name}-{region}",
        "net": f"net-{project_name}-{region}",
        "data": f"data-{project_name}",
    }


def _build_opensearch_data_policy_document(collection_name: str, principals: List[str]) -> List[Dict]:
    """Build OpenSearch Serverless data access policy document."""
    return [
        {
            "Rules": [
                {
                    "Resource": [f"collection/{collection_name}"],
                    "Permission": [
                        "aoss:CreateCollectionItems",
                        "aoss:DeleteCollectionItems",
                        "aoss:UpdateCollectionItems",
                        "aoss:DescribeCollectionItems",
                    ],
                    "ResourceType": "collection",
                },
                {
                    "Resource": [f"index/{collection_name}/*"],
                    "Permission": [
                        "aoss:CreateIndex",
                        "aoss:DeleteIndex",
                        "aoss:UpdateIndex",
                        "aoss:DescribeIndex",
                        "aoss:ReadDocument",
                        "aoss:WriteDocument",
                    ],
                    "ResourceType": "index",
                },
            ],
            "Principal": principals,
        }
    ]


def _opensearch_data_access_principals(knowledge_base_role_arn: Optional[str] = None) -> List[str]:
    principals = [
        f"arn:aws:iam::{account_id}:root",
        _get_installer_iam_arn(),
    ]
    if knowledge_base_role_arn:
        principals.append(knowledge_base_role_arn)
    return principals


def _ensure_opensearch_security_policies(collection_name: str) -> None:
    """Create shared encryption/network policies when missing (e.g. after cleanup)."""
    policy_names = _opensearch_policy_names()
    enc_policy_name = policy_names["enc"]
    net_policy_name = policy_names["net"]

    enc_policy = {
        "Rules": [
            {
                "ResourceType": "collection",
                "Resource": [f"collection/{collection_name}"],
            }
        ],
        "AWSOwnedKey": True,
    }
    try:
        opensearch_client.create_security_policy(
            name=enc_policy_name,
            type="encryption",
            description=f"opensearch encryption policy for {project_name}",
            policy=json.dumps(enc_policy),
        )
        logger.info(f"  Created encryption policy: {enc_policy_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConflictException":
            raise
        logger.debug(f"  Encryption policy already exists: {enc_policy_name}")

    net_policy = [
        {
            "Rules": [
                {
                    "ResourceType": "dashboard",
                    "Resource": [f"collection/{collection_name}"],
                },
                {
                    "ResourceType": "collection",
                    "Resource": [f"collection/{collection_name}"],
                },
            ],
            "AllowFromPublic": True,
        }
    ]
    try:
        opensearch_client.create_security_policy(
            name=net_policy_name,
            type="network",
            description=f"opensearch network policy for {project_name}",
            policy=json.dumps(net_policy),
        )
        logger.info(f"  Created network policy: {net_policy_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConflictException":
            raise
        logger.debug(f"  Network policy already exists: {net_policy_name}")


def _find_opensearch_data_policy_name(collection_name: str) -> Optional[str]:
    """Find the data access policy attached to this project's OpenSearch collection."""
    candidates = [
        f"data-{project_name}",
        f"data-{vector_index_name}",
    ]
    for name in candidates:
        try:
            opensearch_client.get_access_policy(name=name, type="data")
            return name
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise

    collection_resource = f"collection/{collection_name}"
    next_token = None
    while True:
        kwargs: Dict = {"type": "data"}
        if next_token:
            kwargs["nextToken"] = next_token
        response = opensearch_client.list_access_policies(**kwargs)
        for summary in response.get("accessPolicySummaries", []):
            name = summary["name"]
            detail = opensearch_client.get_access_policy(name=name, type="data")
            policy = detail["accessPolicyDetail"]["policy"]
            policy_str = policy if isinstance(policy, str) else json.dumps(policy)
            if collection_resource in policy_str:
                logger.info(f"  Found existing data access policy for {collection_name}: {name}")
                return name
        next_token = response.get("nextToken")
        if not next_token:
            break
    return None


def _create_opensearch_data_policy(
    collection_name: str,
    knowledge_base_role_arn: Optional[str] = None,
) -> str:
    """Create the data access policy for this project's OpenSearch collection."""
    data_policy_name = _opensearch_policy_names()["data"]
    principals = _opensearch_data_access_principals(knowledge_base_role_arn)
    data_policy = _build_opensearch_data_policy_document(collection_name, principals)
    opensearch_client.create_access_policy(
        name=data_policy_name,
        type="data",
        policy=json.dumps(data_policy),
    )
    logger.info(f"  Created data access policy: {data_policy_name}")
    logger.info("  Waiting for OpenSearch data access policy to propagate...")
    time.sleep(20)
    return data_policy_name


def _ensure_opensearch_data_access_principals(
    collection_name: str,
    knowledge_base_role_arn: Optional[str] = None,
) -> None:
    """Ensure collection data policy grants access to installer and KB role."""
    policy_name = _find_opensearch_data_policy_name(collection_name)
    if not policy_name:
        logger.warning(
            f"  No data access policy found for collection {collection_name}; "
            "recreating OpenSearch policies..."
        )
        _ensure_opensearch_security_policies(collection_name)
        try:
            _create_opensearch_data_policy(collection_name, knowledge_base_role_arn)
        except ClientError as e:
            if e.response["Error"]["Code"] != "ConflictException":
                raise
            policy_name = _find_opensearch_data_policy_name(collection_name)
            if not policy_name:
                raise
        else:
            return

    policy_detail = opensearch_client.get_access_policy(name=policy_name, type="data")
    current_policy = policy_detail["accessPolicyDetail"]["policy"]
    if isinstance(current_policy, str):
        current_policy = json.loads(current_policy)

    principals_to_add = _opensearch_data_access_principals(knowledge_base_role_arn)

    needs_update = False
    for rule in current_policy:
        if "Principal" not in rule:
            continue
        current_principals = rule["Principal"]
        if not isinstance(current_principals, list):
            current_principals = [current_principals]
        for principal in principals_to_add:
            if principal and principal not in current_principals:
                current_principals.append(principal)
                needs_update = True
                logger.info(f"  Adding principal to {policy_name}: {principal}")
        rule["Principal"] = current_principals

    if needs_update:
        opensearch_client.update_access_policy(
            name=policy_name,
            type="data",
            policy=json.dumps(current_policy),
            policyVersion=policy_detail["accessPolicyDetail"]["policyVersion"],
        )
        logger.info(f"  Updated data access policy: {policy_name}")
        logger.info("  Waiting for OpenSearch data access policy to propagate...")
        time.sleep(20)
    else:
        logger.debug(f"  Required principals already present in {policy_name}")


def create_opensearch_collection(knowledge_base_role_arn: str = None) -> Dict[str, str]:
    """Create OpenSearch Serverless collection and policies."""
    logger.info("[4/6] Creating OpenSearch Serverless collection")
    
    collection_name = vector_index_name
    policy_names = _opensearch_policy_names()
    enc_policy_name = policy_names["enc"]
    net_policy_name = policy_names["net"]
    data_policy_name = policy_names["data"]
    
    # Check if collection already exists first
    try:
        existing_collections = opensearch_client.list_collections()
        for collection in existing_collections.get("collectionSummaries", []):
            if collection["name"] == collection_name and collection["status"] == "ACTIVE":
                logger.warning(f"OpenSearch collection already exists: {collection['name']}")
                collection_arn = collection["arn"]
                collection_id = collection["id"]
                
                # Get collection endpoint
                collection_details = opensearch_client.batch_get_collection(names=[collection_name])
                collection_detail = collection_details["collectionDetails"][0]
                collection_endpoint = collection_detail.get("collectionEndpoint")
                
                # If endpoint is not available, wait for collection to be ready
                if not collection_endpoint:
                    logger.info("  Collection endpoint not yet available, waiting for collection to be ready...")
                    wait_count = 0
                    while True:
                        response = opensearch_client.batch_get_collection(names=[collection_name])
                        collection_detail = response["collectionDetails"][0]
                        status = collection_detail.get("status")
                        wait_count += 1
                        if wait_count % 6 == 0:  # Log every minute
                            logger.debug(f"  Collection status: {status} (waited {wait_count * 10} seconds)")
                        
                        if "collectionEndpoint" in collection_detail and collection_detail["collectionEndpoint"]:
                            collection_endpoint = collection_detail["collectionEndpoint"]
                            if status == "ACTIVE":
                                break
                        elif status == "ACTIVE":
                            # If active but no endpoint, try one more time after a short wait
                            time.sleep(10)
                            response = opensearch_client.batch_get_collection(names=[collection_name])
                            collection_detail = response["collectionDetails"][0]
                            collection_endpoint = collection_detail.get("collectionEndpoint")
                            if collection_endpoint:
                                break
                        
                        if wait_count > 60:  # Timeout after 10 minutes
                            raise Exception(f"Timeout waiting for collection endpoint. Collection status: {status}")
                        time.sleep(10)
                
                # Update data access policy for project collection
                _ensure_opensearch_data_access_principals(collection_name, knowledge_base_role_arn)
                
                return {
                    "arn": collection_arn,
                    "endpoint": collection_endpoint
                }
    except Exception as e:
        logger.debug(f"Error checking existing collections: {e}")
    
    # Create encryption policy
    _ensure_opensearch_security_policies(collection_name)
    
    # Create data access policy
    principals = _opensearch_data_access_principals(knowledge_base_role_arn)
    data_policy = _build_opensearch_data_policy_document(collection_name, principals)
    
    try:
        opensearch_client.create_access_policy(
            name=data_policy_name,
            type="data",
            policy=json.dumps(data_policy)
        )
        logger.debug(f"Created data access policy: {data_policy_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConflictException":
            logger.warning(f"Data access policy already exists: {data_policy_name}")
            _ensure_opensearch_data_access_principals(collection_name, knowledge_base_role_arn)
        else:
            logger.error(f"Failed to create data access policy: {e}")
            raise
    
    # Wait for policies to be ready
    logger.debug("Waiting for policies to be ready...")
    time.sleep(5)
    
    # Create collection
    try:
        response = opensearch_client.create_collection(
            name=collection_name,
            description=f"opensearch correction for {project_name}",
            type="VECTORSEARCH"
        )
        collection_detail = response["createCollectionDetail"]
        collection_arn = collection_detail["arn"]
        
        # Wait for collection to be active and get endpoint
        logger.info("  Waiting for collection to be active (this may take a few minutes)...")
        collection_endpoint = None
        wait_count = 0
        while True:
            response = opensearch_client.batch_get_collection(
                names=[collection_name]
            )
            collection_detail = response["collectionDetails"][0]
            status = collection_detail["status"]
            wait_count += 1
            if wait_count % 6 == 0:  # Log every minute
                logger.debug(f"  Collection status: {status} (waited {wait_count * 10} seconds)")
            
            # Check if endpoint is available
            if "collectionEndpoint" in collection_detail:
                collection_endpoint = collection_detail["collectionEndpoint"]
                if status == "ACTIVE":
                    break
            time.sleep(10)

        # Wait for opensearch correction to be ready
        logger.debug("Waiting for opensearch correction to be ready...")
        time.sleep(30)
            
        logger.info(f"✓ OpenSearch collection created: {collection_name}")
        logger.info(f"  Endpoint: {collection_endpoint}")
        return {
            "arn": collection_arn,
            "endpoint": collection_endpoint
        }
    
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConflictException":
            logger.warning(f"OpenSearch collection already exists: {collection_name}")
            # Wait for collection endpoint to be available
            logger.info("  Waiting for collection endpoint to be available...")
            wait_count = 0
            collection_endpoint = None
            while True:
                response = opensearch_client.batch_get_collection(names=[collection_name])
                collection_detail = response["collectionDetails"][0]
                status = collection_detail.get("status")
                wait_count += 1
                if wait_count % 6 == 0:  # Log every minute
                    logger.debug(f"  Collection status: {status} (waited {wait_count * 10} seconds)")
                
                if "collectionEndpoint" in collection_detail and collection_detail["collectionEndpoint"]:
                    collection_endpoint = collection_detail["collectionEndpoint"]
                    if status == "ACTIVE":
                        break
                elif status == "ACTIVE":
                    # If active but no endpoint, try one more time after a short wait
                    time.sleep(10)
                    response = opensearch_client.batch_get_collection(names=[collection_name])
                    collection_detail = response["collectionDetails"][0]
                    collection_endpoint = collection_detail.get("collectionEndpoint")
                    if collection_endpoint:
                        break
                
                if wait_count > 60:  # Timeout after 10 minutes
                    raise Exception(f"Timeout waiting for collection endpoint. Collection status: {status}")
                time.sleep(10)
            
            if not collection_endpoint:
                raise Exception("Collection endpoint is not available even after waiting")
            
            _ensure_opensearch_data_access_principals(collection_name, knowledge_base_role_arn)
            return {
                "arn": collection_detail["arn"],
                "endpoint": collection_endpoint
            }
        logger.error(f"Failed to create OpenSearch collection: {e}")
        raise

def delete_knowledge_base(knowledge_base_id: str) -> None:
    """Delete Knowledge Base and its data sources."""
    bedrock_agent_client = boto3.client("bedrock-agent", region_name=region)
    
    try:
        # Delete all data sources first
        try:
            data_sources = bedrock_agent_client.list_data_sources(
                knowledgeBaseId=knowledge_base_id,
                maxResults=100
            )
            for ds in data_sources.get("dataSourceSummaries", []):
                try:
                    bedrock_agent_client.delete_data_source(
                        knowledgeBaseId=knowledge_base_id,
                        dataSourceId=ds["dataSourceId"]
                    )
                    logger.debug(f"Deleted data source: {ds['dataSourceId']}")
                except Exception as e:
                    logger.warning(f"Failed to delete data source {ds['dataSourceId']}: {e}")
        except Exception as e:
            logger.debug(f"Error listing/deleting data sources: {e}")
        
        # Delete the knowledge base
        bedrock_agent_client.delete_knowledge_base(knowledgeBaseId=knowledge_base_id)
        logger.info(f"Deleted Knowledge Base: {knowledge_base_id}")
        
        # Wait for deletion to complete
        logger.debug("Waiting for Knowledge Base deletion to complete...")
        max_wait = 60  # Wait up to 60 seconds
        waited = 0
        while waited < max_wait:
            try:
                kb_response = bedrock_agent_client.get_knowledge_base(knowledgeBaseId=knowledge_base_id)
                status = kb_response["knowledgeBase"]["status"]
                if status == "DELETED":
                    break
                time.sleep(5)
                waited += 5
            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceNotFoundException":
                    logger.debug("Knowledge Base deletion confirmed")
                    break
                raise
        
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.debug(f"Knowledge Base {knowledge_base_id} already deleted")
        else:
            logger.error(f"Failed to delete Knowledge Base {knowledge_base_id}: {e}")
            raise


def create_vector_index_in_opensearch(collection_endpoint: str, index_name: str) -> bool:
    """Create vector index in OpenSearch Serverless collection."""
    try:
        # Validate collection_endpoint
        if not collection_endpoint or not collection_endpoint.strip():
            logger.error(f"  Invalid collection endpoint: '{collection_endpoint}'. Collection endpoint is required.")
            return False
        
        # Ensure endpoint has proper scheme
        if not collection_endpoint.startswith(('http://', 'https://')):
            logger.error(f"  Invalid collection endpoint format: '{collection_endpoint}'. Must start with http:// or https://")
            return False
        
        # Try to import required packages, install if missing
        try:
            import requests
            from requests_aws4auth import AWS4Auth
        except ImportError:
            logger.info("  Installing required packages for OpenSearch index creation...")
            import subprocess
            import sys
            subprocess.check_call([sys.executable, "-m", "pip", "install", "requests-aws4auth"])
            import requests
            from requests_aws4auth import AWS4Auth
        
        # Get AWS credentials
        session = boto3.Session()
        credentials = session.get_credentials()
        awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, 'aoss', session_token=credentials.token)
        
        # Check if index already exists (retry while data access policy propagates)
        url = f"{collection_endpoint}/{index_name}"
        for attempt in range(6):
            response = requests.get(url, auth=awsauth, timeout=30)
            if response.status_code == 200:
                logger.debug(f"Vector index '{index_name}' already exists")
                return True
            if response.status_code in (401, 403) and attempt < 5:
                wait_seconds = 10 * (attempt + 1)
                logger.info(
                    f"  OpenSearch returned {response.status_code}; "
                    f"waiting {wait_seconds}s for data access policy propagation "
                    f"(attempt {attempt + 1}/5)..."
                )
                time.sleep(wait_seconds)
                continue
            if response.status_code == 401:
                logger.error(
                    "  Unauthorized (401) accessing OpenSearch. "
                    f"Ensure {_get_installer_iam_arn()} is in the collection data access policy."
                )
                return False
            if response.status_code == 403:
                logger.error(f"  Forbidden (403) accessing OpenSearch index '{index_name}'")
                return False
            break
        
        # Index mapping for vector search
        index_mapping = {
            "settings": {
                "index": {
                    "knn": True,
                    "knn.algo_param.ef_search": 512
                }
            },
            "mappings": {
                "properties": {
                    "vector_field": {
                        "type": "knn_vector",
                        "dimension": 1024,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "faiss",
                            "parameters": {
                                "ef_construction": 512,
                                "m": 16
                            }
                        }
                    },
                    "AMAZON_BEDROCK_TEXT": {
                        "type": "text"
                    },
                    "AMAZON_BEDROCK_METADATA": {
                        "type": "text"
                    }
                }
            }
        }
        
        # Create index
        headers = {"Content-Type": "application/json"}
        response = requests.put(
            url,
            auth=awsauth,
            headers=headers,
            data=json.dumps(index_mapping),
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            logger.info(f"  ✓ Vector index '{index_name}' created successfully")
            logger.info("  Waiting for index to be ready...")
            time.sleep(30)  # Wait for index to be ready
            return True
        else:
            logger.error(f"  Failed to create vector index: {response.status_code} - {response.text}")
            return False
            
    except ImportError:
        logger.error("  requests-aws4auth package is required. Install with: pip install requests-aws4auth")
        return False
    except Exception as e:
        logger.error(f"  Error creating vector index: {e}")
        return False


def _foundation_model_vector_ingestion_configuration() -> Dict:
    """Vector ingestion config with Foundation Model parser."""
    return {
        "chunkingConfiguration": {
            "chunkingStrategy": "HIERARCHICAL",
            "hierarchicalChunkingConfiguration": {
                "levelConfigurations": [
                    {"maxTokens": 1500},
                    {"maxTokens": 300},
                ],
                "overlapTokens": 60,
            },
        },
        "parsingConfiguration": {
            "parsingStrategy": "BEDROCK_FOUNDATION_MODEL",
            "bedrockFoundationModelConfiguration": {
                "modelArn": parsing_model_arn,
            },
        },
    }


def _data_source_parsing_strategy(details: Dict) -> Optional[str]:
    parsing = (
        details.get("dataSource", {})
        .get("vectorIngestionConfiguration", {})
        .get("parsingConfiguration", {})
        or {}
    )
    return parsing.get("parsingStrategy")


def ensure_data_source_with_foundation_model_parser(
    bedrock_agent_client,
    knowledge_base_id: str,
    s3_bucket_name: str,
) -> str:
    """Create/update Foundation Model parser data source scoped to docs/{project_name}/."""
    expected_bucket_arn = f"arn:aws:s3:::{s3_bucket_name}"
    expected_prefix = f"docs/{project_name}/"
    vector_ingestion = _foundation_model_vector_ingestion_configuration()
    description = f"S3 data source with Foundation Model parser: {s3_bucket_name}"

    data_sources = bedrock_agent_client.list_data_sources(
        knowledgeBaseId=knowledge_base_id,
        maxResults=100,
    )
    for ds in data_sources.get("dataSourceSummaries", []):
        if ds["name"] != s3_bucket_name:
            continue
        ds_id = ds["dataSourceId"]
        details = bedrock_agent_client.get_data_source(
            knowledgeBaseId=knowledge_base_id,
            dataSourceId=ds_id,
        )
        s3_cfg = (
            details["dataSource"]
            .get("dataSourceConfiguration", {})
            .get("s3Configuration")
            or {}
        )
        bucket_arn = s3_cfg.get("bucketArn", "")
        prefixes = s3_cfg.get("inclusionPrefixes") or []
        strategy = _data_source_parsing_strategy(details)

        # Parsing strategy type cannot be changed in-place; recreate if not FM.
        if strategy != "BEDROCK_FOUNDATION_MODEL":
            logger.warning(
                f"  Data source {ds_id} uses {strategy or 'DEFAULT'}; "
                "recreating with BEDROCK_FOUNDATION_MODEL..."
            )
            try:
                bedrock_agent_client.delete_data_source(
                    knowledgeBaseId=knowledge_base_id,
                    dataSourceId=ds_id,
                )
            except ClientError as e:
                logger.warning(f"  Failed to delete data source {ds_id}: {e}")
            break

        if bucket_arn == expected_bucket_arn and expected_prefix in prefixes:
            logger.info(
                f"  Data source already exists with Foundation Model parser "
                f"(prefix={expected_prefix}): {ds_id}"
            )
            return ds_id

        logger.warning(
            f"  Updating data source {ds_id} inclusionPrefixes "
            f"{prefixes} -> {[expected_prefix]}"
        )
        bedrock_agent_client.update_data_source(
            knowledgeBaseId=knowledge_base_id,
            dataSourceId=ds_id,
            name=s3_bucket_name,
            description=description,
            dataSourceConfiguration={
                "type": "S3",
                "s3Configuration": {
                    "bucketArn": expected_bucket_arn,
                    "inclusionPrefixes": [expected_prefix],
                },
            },
            vectorIngestionConfiguration=vector_ingestion,
        )
        logger.info(f"  ✓ Data source updated: {ds_id}")
        return ds_id

    logger.info(
        f"  Creating data source with Foundation Model parser "
        f"(prefix={expected_prefix}, model={parsing_model_arn})..."
    )
    data_source_response = bedrock_agent_client.create_data_source(
        knowledgeBaseId=knowledge_base_id,
        name=s3_bucket_name,
        description=description,
        dataDeletionPolicy="RETAIN",
        dataSourceConfiguration={
            "type": "S3",
            "s3Configuration": {
                "bucketArn": expected_bucket_arn,
                "inclusionPrefixes": [expected_prefix],
            },
        },
        vectorIngestionConfiguration=vector_ingestion,
    )
    data_source_id = data_source_response["dataSource"]["dataSourceId"]
    logger.info(f"  ✓ Data source created: {data_source_id}")
    return data_source_id


def create_knowledge_base_with_opensearch(opensearch_info: Dict[str, str], knowledge_base_role_arn: str, s3_bucket_name: str) -> str:
    """Create Knowledge Base with correct OpenSearch collection."""
    logger.info("[5/6] Creating Knowledge Base with OpenSearch collection")
    
    # Create vector index first
    logger.info("  Creating vector index in OpenSearch collection...")
    if not create_vector_index_in_opensearch(opensearch_info["endpoint"], vector_index_name):
        raise Exception("Failed to create vector index in OpenSearch collection")
    
    bedrock_agent_client = boto3.client("bedrock-agent", region_name=region)
    
    # Check if Knowledge Base already exists
    try:
        logger.info("  Checking if Knowledge Base already exists...")
        kb_list = bedrock_agent_client.list_knowledge_bases()
        for kb in kb_list.get("knowledgeBaseSummaries", []):
            if kb["name"] == project_name:
                logger.warning(f"Knowledge Base already exists: {kb['knowledgeBaseId']}")
                
                # Verify it's using the correct OpenSearch collection
                kb_details = bedrock_agent_client.get_knowledge_base(knowledgeBaseId=kb["knowledgeBaseId"])
                kb_collection_arn = kb_details["knowledgeBase"]["storageConfiguration"]["opensearchServerlessConfiguration"]["collectionArn"]
                
                if kb_collection_arn != opensearch_info["arn"]:
                    logger.warning(f"Knowledge Base is using wrong OpenSearch collection:")
                    logger.warning(f"  Current: {kb_collection_arn}")
                    logger.warning(f"  Expected: {opensearch_info['arn']}")

                    delete_knowledge_base(kb["knowledgeBaseId"])
                    break

                logger.info("Knowledge Base is using correct OpenSearch collection")
                knowledge_base_id = kb["knowledgeBaseId"]
                ensure_data_source_with_foundation_model_parser(
                    bedrock_agent_client, knowledge_base_id, s3_bucket_name
                )
                return knowledge_base_id
        logger.info("  Knowledge Base does not exist. Creating new one...")
    except Exception as e:
        logger.debug(f"Error checking existing Knowledge Base: {e}")
    
    # Verify Knowledge Base role before creating
    logger.info("  Verifying Knowledge Base role configuration...")
    try:
        role_response = iam_client.get_role(RoleName=knowledge_base_role_name)
        policy_doc = role_response["Role"]["AssumeRolePolicyDocument"]
        # Handle both string and dict formats (boto3 may return either)
        if isinstance(policy_doc, str):
            trust_policy = json.loads(policy_doc)
        else:
            trust_policy = policy_doc
        logger.debug(f"  Role trust policy: {json.dumps(trust_policy, indent=2)}")
        
        # Verify trust policy allows bedrock.amazonaws.com
        statements = trust_policy.get("Statement", [])
        bedrock_allowed = False
        for statement in statements:
            if statement.get("Effect") == "Allow":
                principal = statement.get("Principal", {})
                if principal.get("Service") == "bedrock.amazonaws.com":
                    bedrock_allowed = True
                    break
        
        if not bedrock_allowed:
            logger.error("  ✗ Knowledge Base role trust policy does not allow bedrock.amazonaws.com")
            logger.error("  Please update the role trust policy manually or delete and recreate the role")
            raise Exception("Knowledge Base role trust policy is incorrect")
        
        logger.info("  ✓ Knowledge Base role trust policy is correct")
    except ClientError as role_error:
        logger.error(f"  ✗ Failed to verify Knowledge Base role: {role_error}")
        raise
    
    # Create Knowledge Base
    logger.debug(f"Creating Knowledge Base with OpenSearch collection: {opensearch_info['arn']}")
    response = bedrock_agent_client.create_knowledge_base(
        name=project_name,
        description="Knowledge base based on OpenSearch",
        roleArn=knowledge_base_role_arn,
        tags={
            project_name: 'true'
        },
        knowledgeBaseConfiguration={
            "type": "VECTOR",
            "vectorKnowledgeBaseConfiguration": {
                "embeddingModelArn": f"arn:aws:bedrock:{region}::foundation-model/amazon.titan-embed-text-v2:0",
                "embeddingModelConfiguration": {
                    "bedrockEmbeddingModelConfiguration": {
                        "dimensions": 1024
                    }
                }
            }
        },
        storageConfiguration={
            "type": "OPENSEARCH_SERVERLESS",
            "opensearchServerlessConfiguration": {
                "collectionArn": opensearch_info["arn"],
                "fieldMapping": {
                    "metadataField": "AMAZON_BEDROCK_METADATA",
                    "textField": "AMAZON_BEDROCK_TEXT",
                    "vectorField": "vector_field"
                },
                "vectorIndexName": vector_index_name
            }
        }
    )
    
    knowledge_base_id = response["knowledgeBase"]["knowledgeBaseId"]
    logger.info(f"✓ Knowledge Base created: {knowledge_base_id}")
    
    # Wait for Knowledge Base to be active
    logger.info("  Waiting for Knowledge Base to be active...")
    while True:
        kb_response = bedrock_agent_client.get_knowledge_base(knowledgeBaseId=knowledge_base_id)
        status = kb_response["knowledgeBase"]["status"]
        
        if status == "ACTIVE":
            logger.info("  Knowledge Base is now active")
            break
        elif status == "FAILED":
            raise Exception("Knowledge Base creation failed")
        
        logger.debug(f"  Knowledge Base status: {status} (waiting...)")
        time.sleep(10)
    
    ensure_data_source_with_foundation_model_parser(
        bedrock_agent_client, knowledge_base_id, s3_bucket_name
    )
    
    return knowledge_base_id


USER_PREFERENCE_PROMPT = (
    "You are tasked with analyzing conversations to extract the user's preferences. You'll be analyzing two sets of data:\n"
    "<past_conversation>\n"
    "[Past conversations between the user and system will be placed here for context]\n"
    "</past_conversation>\n"
    "<current_conversation>\n"
    "[The current conversation between the user and system will be placed here]\n"
    "</current_conversation>\n"
    "Your job is to identify and categorize the user's preferences into two main types:\n"
    "- Explicit preferences: Directly stated preferences by the user.\n"
    "- Implicit preferences: Inferred from patterns, repeated inquiries, or contextual clues. Take a close look at user's request for implicit preferences.\n"
    "For explicit preference, extract only preference that the user has explicitly shared. Do not infer user's preference.\n"
    "For implicit preference, it is allowed to infer user's preference, but only the ones with strong signals, such as requesting something multiple times.\n"
    "Use Korean.\n"
)


SUMMARY_PROMPT = (
    "You will be given a text block and a list of summaries you previously generated when available.\n"
    "<task>\n"
    "- When the previously generated is not available, your goal is to summarize the given text block.\n"
    "- When there is existing summary, your goal is to extend summary by taking into account the given text block.\n"
    "- If there are queries/topics specified in the text block, your generated summary need to cover those queries/topics.\n"
    "- If there are instructions in the text block **guiding you how to generate summary**, you MUST follow them.\n"
    "</task>\n"
    "Use Korean.\n"
)

SEMANTIC_PROMPT = (
    "You are a long-term memory extraction agent supporting a lifelong learning system.\n"
    "Your task is to identify and extract meaningful information about the users from a given list of messages.\n"
    "Analyze the conversation and extract structured information about the user according to the schema below.\n"
    "Only include details that are explicitly stated or can be logically inferred from the conversation.\n"
    "- Extract information ONLY from the user messages. You should use assistant messages only as supporting context.\n"
    "- If the conversation contains no relevant or noteworthy information, return an empty list.\n"
    "- Do NOT extract anything from prior conversation history, even if provided. Use it solely for context.\n"
    "- Do NOT incorporate external knowledge.\n"
    "- Avoid duplicate extractions.\n"
    "Use Korean.\n"
)

SEMANTIC_CONSOLIDATION_PROMPT = (
    "You consolidate newly extracted facts with existing long-term semantic memories.\n"
    "- Merge duplicates; keep the most specific and recent facts.\n"
    "- Do not invent facts that were not extracted.\n"
    "- Prefer clear, atomic statements in Korean.\n"
    "Use Korean.\n"
)

MEMORY_EXTRACTION_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


def _shared_memory_strategies() -> list:
    """UserPreference + Summary + Semantic (one of each kind per memory_id)."""
    return [
        {
            "customMemoryStrategy": {
                "name": "UserPreference",
                "namespaces": ["/users/{actorId}/preferences"],
                "configuration": {
                    "userPreferenceOverride": {
                        "extraction": {
                            "modelId": MEMORY_EXTRACTION_MODEL_ID,
                            "appendToPrompt": USER_PREFERENCE_PROMPT,
                        }
                    }
                },
            }
        },
        {
            "customMemoryStrategy": {
                "name": "Summary",
                "namespaces": ["/users/{actorId}/sessions/{sessionId}"],
                "configuration": {
                    "summaryOverride": {
                        "consolidation": {
                            "modelId": MEMORY_EXTRACTION_MODEL_ID,
                            "appendToPrompt": SUMMARY_PROMPT,
                        }
                    }
                },
            }
        },
        {
            "customMemoryStrategy": {
                "name": "Semantic",
                "namespaces": ["/users/{actorId}/facts"],
                "configuration": {
                    "semanticOverride": {
                        "extraction": {
                            "modelId": MEMORY_EXTRACTION_MODEL_ID,
                            "appendToPrompt": SEMANTIC_PROMPT,
                        },
                        "consolidation": {
                            "modelId": MEMORY_EXTRACTION_MODEL_ID,
                            "appendToPrompt": SEMANTIC_CONSOLIDATION_PROMPT,
                        },
                    }
                },
            }
        },
    ]


def create_agentcore_memory_role() -> str:
    """Create AgentCore Memory IAM role."""
    logger.info("[2/10] Creating AgentCore Memory IAM role")
    role_name = f"role-agentcore-memory-for-{project_name}-{region}"

    # Trust must include aws:SourceAccount / aws:SourceArn; CreateMemory rejects otherwise.
    # https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-configuring-custom-strategies.html
    assume_role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "MemoryAssumeRolePolicy",
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock-agentcore.amazonaws.com"
                },
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {
                        "aws:SourceAccount": account_id
                    },
                    "ArnLike": {
                        "aws:SourceArn": (
                            f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"
                        )
                    },
                },
            }
        ],
    }

    role_existed = False
    try:
        iam_client.get_role(RoleName=role_name)
        role_existed = True
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") not in (
            "NoSuchEntity",
            "NoSuchEntityException",
        ):
            raise

    role_arn = create_iam_role(role_name, assume_role_policy)

    memory_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                "Resource": [
                    "arn:aws:bedrock:*::foundation-model/*",
                    "arn:aws:bedrock:*:*:inference-profile/*",
                ],
                "Condition": {
                    "StringEquals": {
                        "aws:ResourceAccount": account_id
                    }
                },
            }
        ],
    }
    attach_inline_policy(role_name, f"agentcore-memory-policy-for-{project_name}", memory_policy)

    # CreateMemory validates trust immediately after a brand-new role.
    if not role_existed:
        logger.info("  Waiting for IAM role trust policy to propagate...")
        time.sleep(10)
    else:
        logger.info("  Skipping IAM wait (memory role already exists)")

    return role_arn


def create_agentcore_memory(role_arn: str, user_id: str = "installer") -> str:
    """
    Create AgentCore Memory with shared UserPreference / Summary / Semantic strategies.

    user_id is unused for strategy naming — kept for call-site compatibility.
    User isolation uses {actorId}/{sessionId} namespace templates from CreateEvent.
    """
    logger.info("[2/10] Creating AgentCore Memory")

    memory_client = MemoryClient(region_name=region)
    memory_name = project_name.replace("-", "_")

    memories = memory_client.list_memories()
    for memory in memories:
        if memory.get("id", "").split("-")[0] == memory_name:
            memory_id = memory.get("id")
            logger.info(f"  Memory already exists: {memory_id}")
            return memory_id

    strategies = _shared_memory_strategies()
    result = memory_client.create_memory_and_wait(
        name=memory_name,
        description=f"Memory for {project_name}",
        event_expiry_days=365,
        strategies=strategies,
        memory_execution_role_arn=role_arn,
    )
    memory_id = result.get("id")
    names = [s["customMemoryStrategy"]["name"] for s in strategies]
    logger.info(f"  ✓ Memory created: {memory_id} (strategies={names})")
    return memory_id

def _agentcore_websearch_tool_arn() -> str:
    return (
        f"arn:aws:bedrock-agentcore:{AGENTCORE_GATEWAY_REGION}:"
        f"aws:tool/web-search.v1"
    )


def _list_all_agentcore_gateways() -> List[Dict]:
    gateways: List[Dict] = []
    next_token = None
    while True:
        kwargs = {}
        if next_token:
            kwargs["nextToken"] = next_token
        response = agentcore_control_client.list_gateways(**kwargs)
        gateways.extend(response.get("items", []))
        next_token = response.get("nextToken")
        if not next_token:
            break
    return gateways


def _list_all_agentcore_gateway_targets(gateway_id: str) -> List[Dict]:
    targets: List[Dict] = []
    next_token = None
    while True:
        kwargs = {"gatewayIdentifier": gateway_id}
        if next_token:
            kwargs["nextToken"] = next_token
        response = agentcore_control_client.list_gateway_targets(**kwargs)
        targets.extend(response.get("items", []))
        next_token = response.get("nextToken")
        if not next_token:
            break
    return targets


def wait_for_agentcore_gateway_ready(gateway_id: str, timeout_seconds: int = 600) -> Dict:
    """Wait until an AgentCore gateway reaches READY status."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        gateway = agentcore_control_client.get_gateway(gatewayIdentifier=gateway_id)
        status = gateway.get("status", "")
        if status == "READY":
            logger.info(f"  AgentCore gateway is ready: {gateway_id}")
            return gateway
        if status in ("FAILED", "DELETING", "DELETE_UNSUCCESSFUL", "UPDATE_UNSUCCESSFUL"):
            raise RuntimeError(
                f"AgentCore gateway {gateway_id} entered terminal status: {status}"
            )
        logger.info(f"  Waiting for AgentCore gateway ({gateway_id}) status: {status}")
        time.sleep(10)
    raise TimeoutError(f"Timed out waiting for AgentCore gateway {gateway_id} to become READY")


def create_agentcore_websearch_gateway_role() -> str:
    """Create IAM service role for the AgentCore Web Search gateway."""
    logger.info("[3/6] Creating AgentCore Web Search gateway IAM role")
    role_name = f"role-agentcore-gateway-websearch-for-{project_name}"

    assume_role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "GatewayAssumeRolePolicy",
                "Effect": "Allow",
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": account_id},
                    "ArnLike": {
                        "aws:SourceArn": (
                            f"arn:aws:bedrock-agentcore:{AGENTCORE_GATEWAY_REGION}:"
                            f"{account_id}:gateway/{AGENTCORE_WEBSEARCH_GATEWAY_NAME}-*"
                        )
                    },
                },
            }
        ],
    }
    role_arn = create_iam_role(role_name, assume_role_policy)

    gateway_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "InvokeGateway",
                "Effect": "Allow",
                "Action": ["bedrock-agentcore:InvokeGateway"],
                "Resource": [
                    (
                        f"arn:aws:bedrock-agentcore:{AGENTCORE_GATEWAY_REGION}:"
                        f"{account_id}:gateway/*"
                    )
                ],
            },
            {
                "Sid": "InvokeWebSearchTool",
                "Effect": "Allow",
                "Action": ["bedrock-agentcore:InvokeWebSearch"],
                "Resource": [_agentcore_websearch_tool_arn()],
            },
        ],
    }
    attach_inline_policy(
        role_name,
        f"agentcore-gateway-websearch-policy-for-{project_name}",
        gateway_policy,
    )
    return role_arn


def _ensure_websearch_gateway_target(gateway_id: str) -> str:
    """Create the managed web-search connector target if it does not exist."""
    for target in _list_all_agentcore_gateway_targets(gateway_id):
        if target.get("name") == AGENTCORE_WEBSEARCH_TARGET_NAME:
            target_id = target["targetId"]
            logger.warning(
                f"  AgentCore websearch target already exists: {target_id}"
            )
            return target_id

    logger.info("  Creating AgentCore websearch gateway target")
    response = agentcore_control_client.create_gateway_target(
        gatewayIdentifier=gateway_id,
        name=AGENTCORE_WEBSEARCH_TARGET_NAME,
        description=f"Managed Web Search connector for {project_name}",
        targetConfiguration={
            "mcp": {
                "connector": {
                    "source": {
                        "connectorId": "web-search",
                    },
                    "configurations": [
                        {
                            "name": "WebSearch",
                            "parameterValues": {},
                        }
                    ],
                }
            }
        },
        credentialProviderConfigurations=[
            {"credentialProviderType": "GATEWAY_IAM_ROLE"}
        ],
    )
    target_id = response["targetId"]
    logger.info(f"  ✓ AgentCore websearch target created: {target_id}")

    try:
        agentcore_control_client.synchronize_gateway_targets(
            gatewayIdentifier=gateway_id,
            targetIdList=[target_id],
        )
    except ClientError as e:
        logger.warning(f"  Could not synchronize gateway target immediately: {e}")

    return target_id


def get_or_create_agentcore_websearch_gateway(gateway_service_role_arn: str) -> Dict[str, str]:
    """Create gateway-websearch with the managed web-search connector in us-east-1."""
    logger.info("[3/6] Creating AgentCore Web Search gateway")

    gateway_id = None
    for gateway in _list_all_agentcore_gateways():
        if gateway.get("name") == AGENTCORE_WEBSEARCH_GATEWAY_NAME:
            gateway_id = gateway["gatewayId"]
            logger.warning(
                f"  AgentCore gateway already exists: "
                f"{AGENTCORE_WEBSEARCH_GATEWAY_NAME} ({gateway_id})"
            )
            break

    if not gateway_id:
        response = agentcore_control_client.create_gateway(
            name=AGENTCORE_WEBSEARCH_GATEWAY_NAME,
            description=f"AgentCore Web Search gateway for {project_name}",
            roleArn=gateway_service_role_arn,
            protocolType="MCP",
            authorizerType="AWS_IAM",
            tags={"project": project_name},
        )
        gateway_id = response["gatewayId"]
        logger.info(f"  ✓ AgentCore gateway created: {gateway_id}")
        wait_for_agentcore_gateway_ready(gateway_id)

    gateway = wait_for_agentcore_gateway_ready(gateway_id)
    target_id = _ensure_websearch_gateway_target(gateway_id)
    gateway_url = gateway.get("gatewayUrl", "").rstrip("/")

    return {
        "gateway_id": gateway_id,
        "gateway_name": AGENTCORE_WEBSEARCH_GATEWAY_NAME,
        "gateway_region": AGENTCORE_GATEWAY_REGION,
        "gateway_url": gateway_url,
        "gateway_arn": gateway.get("gatewayArn", ""),
        "gateway_service_role_arn": gateway_service_role_arn,
        "target_id": target_id,
    }


def _apply_websearch_gateway_config(
    env: Dict[str, str],
    agentcore_websearch_gateway_info: Optional[Dict[str, str]] = None,
) -> None:
    """Add AgentCore websearch gateway settings to an environment/config dict."""
    if not agentcore_websearch_gateway_info:
        return
    env["agentcore_websearch_gateway_name"] = agentcore_websearch_gateway_info.get(
        "gateway_name", AGENTCORE_WEBSEARCH_GATEWAY_NAME
    )
    env["agentcore_websearch_gateway_region"] = agentcore_websearch_gateway_info.get(
        "gateway_region", AGENTCORE_GATEWAY_REGION
    )
    env["agentcore_websearch_gateway_id"] = agentcore_websearch_gateway_info.get(
        "gateway_id", ""
    )
    env["agentcore_websearch_gateway_url"] = agentcore_websearch_gateway_info.get(
        "gateway_url", ""
    )
    env["agentcore_websearch_gateway_role"] = agentcore_websearch_gateway_info.get(
        "gateway_service_role_arn", ""
    )


def create_cloudfront_distribution(s3_bucket_name: str) -> Dict[str, str]:
    """Create CloudFront distribution with S3 origin (shared RAG project)."""
    logger.info("[6/6] Creating CloudFront distribution")

    try:
        distributions = cloudfront_client.list_distributions()
        for dist in distributions.get("DistributionList", {}).get("Items", []):
            if cloudfront_comment in dist.get("Comment", ""):
                if dist.get("Enabled", False):
                    logger.warning(f"CloudFront distribution already exists: {dist['DomainName']}")
                    return {"id": dist["Id"], "domain": dist["DomainName"]}
                logger.warning(f"CloudFront distribution exists but is disabled: {dist['DomainName']}")
                dist_config_response = cloudfront_client.get_distribution_config(Id=dist["Id"])
                dist_config = dist_config_response["DistributionConfig"]
                dist_config["Enabled"] = True
                cloudfront_client.update_distribution(
                    Id=dist["Id"],
                    DistributionConfig=dist_config,
                    IfMatch=dist_config_response["ETag"],
                )
                return {"id": dist["Id"], "domain": dist["DomainName"]}
    except Exception as e:
        logger.debug(f"Error checking existing CloudFront distributions: {e}")

    oai_id = None
    try:
        oai_list = cloudfront_client.list_cloud_front_origin_access_identities()
        for oai in oai_list.get("CloudFrontOriginAccessIdentityList", {}).get("Items", []):
            if oai_comment in oai.get("Comment", ""):
                oai_id = oai["Id"]
                logger.info(f"  Using existing Origin Access Identity: {oai_id}")
                break
        if not oai_id:
            oai_response = cloudfront_client.create_cloud_front_origin_access_identity(
                CloudFrontOriginAccessIdentityConfig={
                    "CallerReference": f"{vector_index_name}-s3-oai-{int(time.time())}",
                    "Comment": oai_comment,
                }
            )
            oai_id = oai_response["CloudFrontOriginAccessIdentity"]["Id"]
            logger.info(f"  Created Origin Access Identity: {oai_id}")
    except ClientError as e:
        logger.error(f"Failed to handle Origin Access Identity: {e}")
        raise

    bucket_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowCloudFrontAccess",
                "Effect": "Allow",
                "Principal": {
                    "AWS": f"arn:aws:iam::cloudfront:user/CloudFront Origin Access Identity {oai_id}"
                },
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{s3_bucket_name}/*",
            }
        ],
    }
    try:
        time.sleep(10)
        s3_client.put_bucket_policy(Bucket=s3_bucket_name, Policy=json.dumps(bucket_policy))
        logger.info("  Updated S3 bucket policy for CloudFront access")
    except ClientError as e:
        logger.error(f"Failed to update S3 bucket policy: {e}")
        raise

    origin_id = f"s3-{project_name}"
    distribution_config = {
        "CallerReference": f"{project_name}-{int(time.time())}",
        "Comment": cloudfront_comment,
        "DefaultRootObject": "index.html",
        "DefaultCacheBehavior": {
            "TargetOriginId": origin_id,
            "ViewerProtocolPolicy": "redirect-to-https",
            "AllowedMethods": {
                "Quantity": 2,
                "Items": ["GET", "HEAD"],
                "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]},
            },
            "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6",
            "Compress": True,
        },
        "Origins": {
            "Quantity": 1,
            "Items": [
                {
                    "Id": origin_id,
                    "DomainName": f"{s3_bucket_name}.s3.{region}.amazonaws.com",
                    "S3OriginConfig": {
                        "OriginAccessIdentity": f"origin-access-identity/cloudfront/{oai_id}"
                    },
                }
            ],
        },
        "Enabled": True,
        "PriceClass": "PriceClass_200",
    }

    response = cloudfront_client.create_distribution(DistributionConfig=distribution_config)
    distribution_id = response["Distribution"]["Id"]
    distribution_domain = response["Distribution"]["DomainName"]
    logger.info(f"CloudFront distribution created: {distribution_domain}")
    logger.info(f"  S3 origin: {s3_bucket_name}")
    return {"id": distribution_id, "domain": distribution_domain}


def build_app_environment(
    knowledge_base_role_arn: str,
    opensearch_info: Dict[str, str],
    s3_bucket_name: str,
    cloudfront_domain: str,
    knowledge_base_id: str,
    agentcore_memory_role_arn: str = "",
    memory_id: str = "",
    agentcore_websearch_gateway_info: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    env = {
        "projectName": project_name,
        "accountId": account_id,
        "region": region,
        "knowledge_base_id": knowledge_base_id,
        "knowledge_base_name": knowledge_base_name,
        "knowledge_base_role": knowledge_base_role_arn,
        "collectionArn": opensearch_info["arn"],
        "opensearch_url": opensearch_info["endpoint"],
        "s3_bucket": s3_bucket_name,
        "s3_arn": f"arn:aws:s3:::{s3_bucket_name}",
        "sharing_url": f"https://{cloudfront_domain}",
    }
    if agentcore_memory_role_arn:
        env["agentcore_memory_role"] = agentcore_memory_role_arn
    if memory_id:
        env["memory_id"] = memory_id
    _apply_websearch_gateway_config(env, agentcore_websearch_gateway_info)
    return env


def _application_config_path() -> str:
    project_root = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(project_root, "application", "config.json")


def write_application_config(config_data: Dict, *, merge_existing: bool = True) -> bool:
    config_path = _application_config_path()
    existing = {}
    if merge_existing:
        try:
            with open(config_path, "r") as f:
                existing = json.load(f)
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"Could not read existing {config_path}: {e}")
    existing.update(config_data)
    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(existing, f, indent=2)
        return True
    except Exception as e:
        logger.warning(f"Could not write {config_path}: {e}")
        return False


def build_config_from_deployment_state(
    knowledge_base_id: Optional[str] = None,
    knowledge_base_role_arn: Optional[str] = None,
    agentcore_memory_role_arn: Optional[str] = None,
    memory_id: Optional[str] = None,
    agentcore_websearch_gateway_info: Optional[Dict[str, str]] = None,
    opensearch_info: Optional[Dict[str, str]] = None,
    s3_bucket_name: Optional[str] = None,
    cloudfront_info: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    config_data: Dict[str, str] = {
        "projectName": project_name,
        "accountId": account_id,
        "region": region,
        "knowledge_base_name": knowledge_base_name,
    }
    if knowledge_base_id:
        config_data["knowledge_base_id"] = knowledge_base_id
    if knowledge_base_role_arn:
        config_data["knowledge_base_role"] = knowledge_base_role_arn
    if opensearch_info:
        config_data["collectionArn"] = opensearch_info.get("arn", "")
        config_data["opensearch_url"] = opensearch_info.get("endpoint", "")
    if s3_bucket_name:
        config_data["s3_bucket"] = s3_bucket_name
        config_data["s3_arn"] = f"arn:aws:s3:::{s3_bucket_name}"
    if cloudfront_info:
        config_data["sharing_url"] = f"https://{cloudfront_info.get('domain', '')}"
    if agentcore_memory_role_arn:
        config_data["agentcore_memory_role"] = agentcore_memory_role_arn
    if memory_id:
        config_data["memory_id"] = memory_id
    _apply_websearch_gateway_config(config_data, agentcore_websearch_gateway_info)
    return config_data


def main():
    logger.info("=" * 60)
    logger.info("Starting AWS Infrastructure Deployment")
    logger.info("=" * 60)
    logger.info(f"Project: {project_name}")
    logger.info(f"Region: {region}")
    logger.info(f"Account ID: {account_id}")
    logger.info(f"Bucket Name: {bucket_name}")
    logger.info("=" * 60)

    start_time = time.time()
    s3_bucket_name = None
    knowledge_base_role_arn = None
    agentcore_memory_role_arn = None
    memory_id = None
    agentcore_websearch_gateway_info = None
    opensearch_info = None
    knowledge_base_id = None
    cloudfront_info = None
    app_environment = None
    deployment_success = False

    try:
        create_secrets()
        s3_bucket_name = create_s3_bucket()
        knowledge_base_role_arn = create_knowledge_base_role()
        create_agent_role()
        agentcore_memory_role_arn = create_agentcore_memory_role()
        memory_id = create_agentcore_memory(agentcore_memory_role_arn)
        agentcore_websearch_gateway_role_arn = create_agentcore_websearch_gateway_role()
        agentcore_websearch_gateway_info = get_or_create_agentcore_websearch_gateway(
            agentcore_websearch_gateway_role_arn
        )
        opensearch_info = create_opensearch_collection(knowledge_base_role_arn)
        knowledge_base_id = create_knowledge_base_with_opensearch(
            opensearch_info, knowledge_base_role_arn, s3_bucket_name
        )
        cloudfront_info = create_cloudfront_distribution(s3_bucket_name)
        app_environment = build_app_environment(
            knowledge_base_role_arn,
            opensearch_info,
            s3_bucket_name,
            cloudfront_info["domain"],
            knowledge_base_id,
            agentcore_memory_role_arn,
            memory_id,
            agentcore_websearch_gateway_info,
        )
        deployment_success = True

        elapsed_time = time.time() - start_time
        logger.info("")
        logger.info("=" * 60)
        logger.info("Infrastructure Deployment Completed Successfully!")
        logger.info("=" * 60)
        logger.info(f"  S3 Bucket: {s3_bucket_name}")
        logger.info(f"  CloudFront Domain: https://{cloudfront_info['domain']}")
        logger.info(f"  OpenSearch Endpoint: {opensearch_info['endpoint']}")
        logger.info(f"  Knowledge Base ID: {knowledge_base_id}")
        logger.info(f"  Knowledge Base Role: {knowledge_base_role_arn}")
        logger.info(f"  AgentCore Memory Role: {agentcore_memory_role_arn}")
        logger.info(f"  Memory ID: {memory_id}")
        logger.info(f"Total deployment time: {elapsed_time / 60:.2f} minutes")
        logger.info("Run locally: ./run_local.sh  (or uvicorn application.server:app --port 8501)")
        logger.info("=" * 60)
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"Deployment Failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise
    finally:
        if app_environment is not None:
            config_data = app_environment
        else:
            config_data = build_config_from_deployment_state(
                knowledge_base_id=knowledge_base_id,
                knowledge_base_role_arn=knowledge_base_role_arn,
                agentcore_memory_role_arn=agentcore_memory_role_arn,
                memory_id=memory_id,
                agentcore_websearch_gateway_info=agentcore_websearch_gateway_info,
                opensearch_info=opensearch_info,
                s3_bucket_name=s3_bucket_name,
                cloudfront_info=cloudfront_info,
            )
        if write_application_config(config_data):
            if deployment_success:
                logger.info(f"Updated {_application_config_path()}")
            else:
                logger.info(f"Saved partial deployment info to {_application_config_path()}")


if __name__ == "__main__":
    main()
