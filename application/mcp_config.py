import logging
import sys
import utils
import os
import json
import shutil
import boto3

logging.basicConfig(
    level=logging.INFO,  # Default to INFO level
    format='%(filename)s:%(lineno)d | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger("mcp-config")

script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, "config.json")

config = utils.load_config()
logger.info(f"config: {config}")

region = config["region"] if "region" in config else "us-west-2"
projectName = config["projectName"] if "projectName" in config else "mcp"
workingDir = os.path.dirname(os.path.abspath(__file__))
# 상위 디렉토리의 contents 폴더 경로 추가
parent_dir = os.path.dirname(workingDir)
contents_dir = os.path.join(parent_dir, "contents")
logger.info(f"workingDir: {workingDir}")
logger.info(f"contents_dir: {contents_dir}")

mcp_user_config = {}    

def get_secret_value(secret_name):
    session = boto3.Session()
    client = session.client('secretsmanager', region_name=region)
    
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except client.exceptions.ResourceNotFoundException:
        logger.info(f"Secret not found, creating new secret: {secret_name}")
        try:
            # Create secret value with bearer_key 
            secret_value = {
                "key": secret_name,
                "value": "need to update"
            }
            
            # Convert to JSON string
            secret_string = json.dumps(secret_value)

            client.create_secret(
                Name=secret_name,
                SecretString=secret_string,  
                Description=f"secret key and token for {secret_name}"
            )
            logger.info(f"Secret created: {secret_name}. Please update it with the actual value.")
            return None
        except Exception as create_error:
            logger.error(f"Failed to create secret: {create_error}")
            return None
    except Exception as e:
        logger.error(f"Error getting secret value: {e}")
        return None

def get_agentcore_gateway_mcp_url(gateway_name: str, gateway_region: str) -> str | None:
    client = boto3.client("bedrock-agentcore-control", region_name=gateway_region)
    try:
        response = client.list_gateways()
        for item in response.get("items", []):
            if item.get("name") != gateway_name:
                continue

            gateway_id = item["gatewayId"]
            gateway = client.get_gateway(gatewayIdentifier=gateway_id)
            return gateway["gatewayUrl"].rstrip("/")
    except Exception as e:
        logger.error(f"Error resolving AgentCore gateway URL for {gateway_name}: {e}")

    return None
    
def load_config(mcp_type):
    # Display-name aliases (aligned with agentic-work mcp.list)
    if mcp_type == "knowledge base":
        mcp_type = "kb-retriever"
    elif mcp_type == "aws documentation":
        mcp_type = "aws_documentation"
    elif mcp_type == "trade info":
        mcp_type = "trade_info"
    elif mcp_type == "image generation":
        mcp_type = "image_generation"
    elif mcp_type == "AWS Sentral (Employee)":
        mcp_type = "aws_sentral"
    elif mcp_type == "AWS Outlook (Employee)":
        mcp_type = "aws_outlook"
    elif mcp_type == "AWS Slack (Employee)":
        mcp_type = "aws_slack"
    elif mcp_type == "AWS Loop (Employee)":
        mcp_type = "aws_loop"

    if mcp_type == "tavily":
        return {
            "mcpServers": {
                "tavily-search": {
                    "command": "python",
                    "args": [
                        f"{workingDir}/mcp_server_tavily.py"
                    ]
                }
            }
        }
        
    elif mcp_type == "use-aws": 
        return {
            "mcpServers": {
                "use-aws": {
                    "command": "python",
                    "args": [
                        f"{workingDir}/mcp_server_use_aws.py"
                    ]
                }
            }
        }

    elif mcp_type == "image_generation":
        return {
            "mcpServers": {
                "imageGeneration": {
                    "command": "python",
                    "args": [
                        f"{workingDir}/mcp_server_image_generation.py"
                    ],
                    "env": {
                        "PYTHONPATH": workingDir,
                        # AGENTCORE_USER_ID is injected at runtime in chat.create_agent()
                    },
                }
            }
        }
    
    elif mcp_type == "kb-retriever":
        return {
            "mcpServers": {
                "kb_retriever": {
                    "command": "python",
                    "args": [f"{workingDir}/mcp_server_retrieve.py"],
                    "env": {
                        "PYTHONPATH": workingDir,
                        # AGENTCORE_USER_ID is injected at runtime in chat.create_agent()
                    },
                }
            }
        }

    elif mcp_type == "terminal (MAC)":
        return {
            "mcpServers": {
                "iterm-mcp": {
                    "command": "npx",
                    "args": [
                        "-y",
                        "iterm-mcp"
                    ]
                }
            }
        }
    
    elif mcp_type == "terminal (linux)":
        return {
            "mcpServers": {
                "terminal-control": {
                    "command": "terminal-control-mcp",
                    "args": [],
                    "env": {
                        "TERMINAL_CONTROL_SECURITY_LEVEL": "low"  # "off", "low", "medium", "high" 중 선택
                    }
                }
            }
        }    
    
    elif mcp_type == "filesystem":
        parent_dir = os.path.dirname(workingDir)
        contents_dir = os.path.join(parent_dir, "contents")
        return {
            "mcpServers": {
                "filesystem": {
                    "command": "npx",
                    "args": [
                        "-y",
                        "@modelcontextprotocol/server-filesystem",
                        f"{parent_dir}",
                        f"{workingDir}",
                        f"{contents_dir}"
                    ]
                }
            }
        }    
    
    elif mcp_type == "aws_documentation":
        # Prefer preinstalled binary (pip / uv tool install) over uvx so
        # each agent init does not re-resolve and install 40+ packages.
        env = {"FASTMCP_LOG_LEVEL": "ERROR"}
        command = shutil.which("awslabs.aws-documentation-mcp-server")
        args: list[str] = []
        if not command:
            logger.warning(
                "awslabs.aws-documentation-mcp-server is not preinstalled; "
                "falling back to uvx (install once with: "
                "uv tool install awslabs.aws-documentation-mcp-server)"
            )
            command = "uvx"
            args = ["awslabs.aws-documentation-mcp-server"]
        return {
            "mcpServers": {
                "awslabs.aws-documentation-mcp-server": {
                    "command": command,
                    "args": args,
                    "env": env,
                }
            }
        }

    elif mcp_type == "trade_info":
        return {
            "mcpServers": {
                "trade_info": {
                    "command": "python",
                    "args": [
                        f"{workingDir}/mcp_server_trade_info.py"
                    ]
                }
            }
        }

    elif mcp_type == "web_fetch":
        return {
            "mcpServers": {
                "web_fetch": {
                    "command": "npx",
                    "args": ["-y", "mcp-server-fetch-typescript"]
                }
            }
        }
    
    elif mcp_type == "text_extraction":
        return {
            "mcpServers": {
                "text_extraction": {
                    "command": "python",
                    "args": [f"{workingDir}/mcp_server_text_extraction.py"]
                }
            }
        }

    elif mcp_type == "memory":
        return {
            "mcpServers": {
                "memory": {
                    "command": "python",
                    "args": [f"{workingDir}/mcp_server_memory.py"],
                    "env": {
                        "PYTHONPATH": workingDir,
                        # AGENTCORE_USER_ID is injected at runtime in langgraph_agent.create_agent()
                    },
                }
            }
        }

    elif mcp_type == "graph memory":
        return {
            "mcpServers": {
                "graph memory": {
                    "command": "python",
                    "args": [f"{workingDir}/mcp_server_graph_memory.py"],
                    "env": {
                        "PYTHONPATH": workingDir,
                        # AGENTCORE_USER_ID is injected at runtime in chat.create_agent()
                    },
                }
            }
        }
    
    elif mcp_type == "outlook":
        secret_name = f"outlook-mcp-user-email"
        secret_value = json.loads(get_secret_value(secret_name))
        OUTLOOK_MCP_USER_EMAIL = secret_value['value']
        if not OUTLOOK_MCP_USER_EMAIL:
            logger.info(f"No outlook user email found in secret manager")
            return {}
        else:
            logger.info(f"outlook user email: {OUTLOOK_MCP_USER_EMAIL}")
            return {
                "mcpServers": {
                    "outlook": {
                        "command": f"{workingDir}/outlook-mac/outlook_mcp.py",
                        "env":{
                            "USER_EMAIL":OUTLOOK_MCP_USER_EMAIL,
                            "OUTLOOK_MCP_LOG_LEVEL":"INFO"
                        }
                    }
                }
            }
    
    elif mcp_type == "slack":
        slack_token = os.environ.get("SLACK_BOT_TOKEN", "")
        slack_team = os.environ.get("SLACK_TEAM_ID", "")
        if not slack_token:
            logger.info(
                "Slack MCP skipped: SLACK_BOT_TOKEN not set. "
                "Configure AWS Secrets Manager secret slackapikey "
                "or set SLACK_BOT_TOKEN in the environment."
            )
            return {}
        return {
            "mcpServers": {
                "slack": {
                    "command": "npx",
                    "args": [
                        "-y",
                        "@modelcontextprotocol/server-slack"
                    ],
                    "env": {
                        "SLACK_BOT_TOKEN": slack_token,
                        "SLACK_TEAM_ID": slack_team
                    }
                }
            }
        }
    
    elif mcp_type == "notion":
        return {
            "mcpServers": {
                "notionApi": {
                    "command": "npx",
                    "args": ["-y", "@notionhq/notion-mcp-server"],
                    "env": {
                        "NOTION_TOKEN": utils.notion_api_key
                    }
                }
            }
        }    

    elif mcp_type == "gog":
        return {
            "mcpServers": {
                "gog": {
                    "command": "python",
                    "args": [f"{workingDir}/mcp_server_gog.py"]
                }
            }
        }
    
    elif mcp_type == "obsidian":
        return {
            "mcpServers": {
                "obsidian": {
                    "command": "npx",
                    "args": ["-y", "obsidian-mcp", os.path.expanduser("~/Documents/memo")]
                }
            }
        }
    
    elif mcp_type == "aws_sentral":
        return {
            "mcpServers": {
                "aws_sentral": {
                "command": os.path.expanduser("~/.toolbox/bin/aws-sentral-mcp"),
                "args": []
                }
            }
        }

    elif mcp_type == "aws_outlook":
        return {
            "mcpServers": {
                "aws_outlook": {
                    "command": os.path.expanduser("~/.toolbox/bin/aws-outlook-mcp"),
                    "args": []
                }
            }
        }   
        
    elif mcp_type == "browser-use":
        return {
            "mcpServers": {
                "mcp-browser-use": {
                    "command": "python",
                    "args": [f"{workingDir}/mcp_server_brower_use.py"]
                }
            }
        }
    
    elif mcp_type == "aws_slack":
        return {
            "mcpServers" : {
                "slack-mcp" : {
                "command" : "slack-mcp",
                "args" : [ ]
                }
            }
        }
    
    elif mcp_type == "aws_loop":
        return {
            "mcpServers" : {
                "loop-mcp" : {
                    "command" : "loop-mcp",
                    "args" : [ ]
                }
            }
        }

    elif mcp_type == "websearch":
        gateway_url = get_agentcore_gateway_mcp_url("gateway-websearch", "us-east-1")
        if not gateway_url:
            logger.info(
                "AgentCore gateway websearch MCP skipped: "
                "gateway-websearch not found in us-east-1."
            )
            return {}
        return {
            "mcpServers": {
                "gateway-websearch": {
                    "type": "streamable_http",
                    "url": gateway_url,
                    "auth_type": "aws_sigv4",
                    "auth_region": "us-east-1",
                    "auth_service": "bedrock-agentcore",
                }
            }
        }

    elif mcp_type == "pubmed":
        return {
            "mcpServers": {
                "pubmed": {
                    "command": "python",
                    "args": [
                        f"{workingDir}/mcp_server_pubmed.py"
                    ]
                }
            }
        }

    elif mcp_type == "chembl":
        return {
            "mcpServers": {
                "chembl": {
                    "command": "python",
                    "args": [
                        f"{workingDir}/mcp_server_chembl.py"
                    ]
                }
            }
        }

    elif mcp_type == "clinicaltrial":
        return {
            "mcpServers": {
                "clinicaltrial": {
                    "command": "python",
                    "args": [
                        f"{workingDir}/mcp_server_clinicaltrial.py"
                    ]
                }
            }
        }

    elif mcp_type == "arxiv-manual":
        return {
            "mcpServers": {
                "arxiv-manual": {
                    "command": "python",
                    "args": [
                        f"{workingDir}/mcp_server_arxiv.py"
                    ]
                }
            }
        }

    elif mcp_type == "사용자 설정":
        return mcp_user_config

def load_selected_config(mcp_servers: dict):
    logger.info(f"mcp_servers: {mcp_servers}")
    
    loaded_config = {}
    for server in mcp_servers:
        config = load_config(server)
        if config:
            loaded_config.update(config["mcpServers"])
    return {
        "mcpServers": loaded_config
    }
