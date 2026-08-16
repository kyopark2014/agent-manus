import logging

logger = logging.getLogger("runtime_mode")

BACKEND_MODE = "local"


def backend_mode_label() -> str:
    return BACKEND_MODE


def ensure_local_backend() -> None:
    """Agent runs in-process via Manus multi-agent pipeline."""
    logger.info("Agent backend: local (manus.run_manus)")


def run_agent(
    prompt,
    user_id,
    mcp_servers,
    model_name,
    runtime_session_id,
    notification_queue=None,
    skill_list=None,
    guardrail_enabled=None,
    llm_gateway_enabled=None,
    memory_enabled=None,
    files=None,
):
    """Run the co-located Manus agent (FastAPI chat entrypoint)."""
    from application import chat

    return chat.run_manus_agent(
        prompt=prompt,
        user_id=user_id,
        mcp_servers=mcp_servers,
        model_name=model_name,
        runtime_session_id=runtime_session_id,
        notification_queue=notification_queue,
        skill_list=skill_list,
        guardrail_enabled=guardrail_enabled,
        llm_gateway_enabled=llm_gateway_enabled,
        memory_enabled=memory_enabled,
        files=files,
    )
