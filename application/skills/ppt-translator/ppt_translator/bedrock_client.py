"""
AWS Bedrock client wrapper with connection management
"""
import os
import logging
from typing import Optional, Any
from .dependencies import DependencyManager
from .retry import bedrock_retry

logger = logging.getLogger(__name__)


def _build_boto_config():
    """Build a botocore Config with a minimal adaptive retry layer.

    Adaptive mode gives us the client-side throttle token bucket which smooths
    bursts across concurrent calls. We cap max_attempts at 2 here because
    tenacity handles the retry count (keeping the two layers from multiplying).
    """
    try:
        from botocore.config import Config as BotoConfig
    except ImportError:
        return None
    return BotoConfig(retries={'mode': 'adaptive', 'max_attempts': 2})


class BedrockClient:
    """AWS Bedrock client wrapper with connection management"""

    def __init__(self, region: str = None):
        self._client = None
        self._initialized = False
        self.region = region or os.getenv('AWS_REGION', 'us-east-1')
        self.deps = DependencyManager()

    @property
    def client(self) -> Optional[Any]:
        """Lazy initialization of Bedrock client"""
        if not self._initialized:
            self._initialize()
        return self._client

    def _initialize(self) -> bool:
        """Initialize the AWS Bedrock client"""
        try:
            boto3 = self.deps.require('boto3')
            logger.info(f"Initializing Bedrock client with region: {self.region}")
            boto_config = _build_boto_config()
            client_kwargs = {'region_name': self.region}
            if boto_config is not None:
                client_kwargs['config'] = boto_config

            # Try default credential chain first
            try:
                self._client = boto3.client('bedrock-runtime', **client_kwargs)
                logger.info("✅ Bedrock client initialized with default credentials")
                self._initialized = True
                return True
            except Exception as e:
                logger.warning(f"Default credentials failed: {str(e)}")

            # Fallback to explicit credentials
            access_key = os.getenv('AWS_ACCESS_KEY_ID')
            secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')

            if access_key and secret_key and not access_key.startswith('${'):
                self._client = boto3.client(
                    'bedrock-runtime',
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    **client_kwargs,
                )
                logger.info("✅ Bedrock client initialized with explicit credentials")
                self._initialized = True
                return True
            else:
                logger.error("❌ AWS credentials not properly configured")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to initialize AWS Bedrock client: {str(e)}")
            return False

    def is_ready(self) -> bool:
        """Check if client is ready"""
        return self.client is not None

    @bedrock_retry
    def converse(self, **kwargs) -> Any:
        """Wrapper for converse API call with automatic retry on transient errors."""
        if not self.is_ready():
            raise Exception("AWS Bedrock client not initialized")
        return self.client.converse(**kwargs)
