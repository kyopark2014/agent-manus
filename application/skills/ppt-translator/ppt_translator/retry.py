"""
Retry policy for AWS Bedrock API calls.

Centralizes which exceptions are worth retrying (throttling, transient
server errors, network hiccups) and which are not (validation errors,
permission issues). Uses tenacity for exponential backoff.

If tenacity is not installed, the `bedrock_retry` decorator degrades
to a no-op so the package still imports.
"""
import logging
import os

logger = logging.getLogger(__name__)

# Bedrock error codes that are worth retrying.
_RETRYABLE_CODES = {
    'ThrottlingException',
    'ServiceUnavailableException',
    'ModelStreamErrorException',
    'InternalServerException',
    'ModelTimeoutException',
    'ModelErrorException',
}

# Explicit non-retryable codes — retrying these just wastes tokens/time.
_NON_RETRYABLE_CODES = {
    'ValidationException',
    'AccessDeniedException',
    'ResourceNotFoundException',
    'ModelNotReadyException',
    'UnauthorizedOperation',
}


def is_retryable(exc: BaseException) -> bool:
    """Return True if the given exception should trigger a retry."""
    try:
        from botocore.exceptions import ClientError, ReadTimeoutError, EndpointConnectionError, ConnectTimeoutError
    except ImportError:
        return False

    if isinstance(exc, (ReadTimeoutError, EndpointConnectionError, ConnectTimeoutError)):
        return True

    if isinstance(exc, ClientError):
        code = exc.response.get('Error', {}).get('Code', '') if hasattr(exc, 'response') else ''
        if code in _NON_RETRYABLE_CODES:
            return False
        return code in _RETRYABLE_CODES

    return False


def _build_retry_decorator():
    """Build the tenacity retry decorator, or a no-op if tenacity isn't available."""
    try:
        from tenacity import (
            retry, stop_after_attempt, wait_exponential,
            retry_if_exception, before_sleep_log,
        )
    except ImportError:
        logger.warning(
            "tenacity not installed; Bedrock retries disabled. "
            "Install with `pip install tenacity` to enable automatic retry on throttling."
        )

        def _noop(func):
            return func
        return _noop

    try:
        max_attempts = int(os.getenv('BEDROCK_MAX_RETRIES', '5'))
    except ValueError:
        max_attempts = 5

    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=2, min=1, max=30),
        retry=retry_if_exception(is_retryable),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


bedrock_retry = _build_retry_decorator()
