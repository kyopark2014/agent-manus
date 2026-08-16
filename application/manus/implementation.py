import json
import logging
import os
import random
import re
import string
import sys
from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.graph import CurveStyle, MermaidDrawMethod
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.constants import END
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict

try:
    from application import agent, chat, mcp_config, skill, utils
    from application import langgraph_agent
    from application.manus.stub import ManusAgent
    from application.notify_adapter import make_containers
except ImportError:
    import agent
    import chat
    import mcp_config
    import skill
    import utils
    import langgraph_agent
    from manus.stub import ManusAgent
    from notify_adapter import make_containers

logging.basicConfig(
    level=logging.INFO,
    format="%(filename)s:%(lineno)d | %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("graph-implementation")

status_msg = []
response_msg = []
collected_image_urls: list[str] = []
index = 0

config = utils.load_config()
s3_bucket = config.get("s3_bucket")
if s3_bucket is None:
    raise Exception("No storage!")


def get_status_msg(status):
    global status_msg
    status_msg.append(status)
    joined = " -> ".join(status_msg)
    if status != "end":
        return "[status]\n" + joined + "..."
    return "[status]\n" + joined


def _coerce_text(message) -> str:
    if message is None:
        return ""
    if isinstance(message, str):
        return message
    if isinstance(message, list):
        parts = []
        for block in message:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("text"):
                parts.append(str(block["text"]))
            else:
                text = getattr(block, "text", None)
                parts.append(str(text if text is not None else block))
        return "\n".join(parts)
    text = getattr(message, "content", None)
    if text is not None and text is not message:
        return _coerce_text(text)
    return str(message)


def _nq(config: RunnableConfig | dict | None):
    """notification_queue from RunnableConfig (agent-skills style)."""
    return _cfg(config, "notification_queue")


def add_notification(containers_or_config, message):
    """Show intermediate manus output via chat._notify_stream (agent-skills)."""
    global index
    text = _coerce_text(message).strip()
    if not text:
        return

    nq = None
    if isinstance(containers_or_config, dict):
        nq = containers_or_config.get("notification_queue")
        if nq is None and "configurable" in containers_or_config:
            nq = _cfg(containers_or_config, "notification_queue")

    chat._notify_stream(nq, text)
    index += 1


def _cfg(config: RunnableConfig | dict | None, key: str, default=None):
    """Read from configurable first, then top-level (legacy)."""
    if not config:
        return default
    conf = config.get("configurable") or {}
    if key in conf:
        return conf.get(key, default)
    return config.get(key, default)


def _emit_debug_status(config: RunnableConfig | dict | None, label: str) -> None:
    """Pipeline status as Info notification (same card style as other notifies)."""
    if chat.debug_mode != "Enable":
        return
    nq = _nq(config)
    if nq is not None:
        nq.notify(get_status_msg(label))

def get_prompt_template(prompt_name: str) -> str:
    template = open(os.path.join(os.path.dirname(__file__), f"{prompt_name}.md")).read()
    return template

def get_mcp_tools(tools):
    mcp_tools = []
    for tool in tools:
        name = tool.name
        description = tool.description
        description = description.replace("\n", "")
        mcp_tools.append(f"{name}: {description}")
        # logger.info(f"mcp_tools: {mcp_tools}")

    return mcp_tools


def build_markdown_viewer_html(
    *,
    request_id: str,
    md_file: str,
    title: str = "결과 리포트",
) -> str:
    """HTML shell that fetches a markdown artifact and renders it with marked."""
    template_path = os.path.join(os.path.dirname(__file__), "report_md.html")
    template = open(template_path, encoding="utf-8").read()
    sharing_url = (chat.path or "").rstrip("/")
    return (
        template.replace("{request_id}", request_id)
        .replace("{sharing_url}", sharing_url)
        .replace("{md_file}", md_file)
        .replace("{title}", title)
    )


def publish_markdown_report_html(request_id: str) -> str:
    """Write artifacts/{id}_report.html as a markdown viewer (not pre-converted HTML)."""
    md_file = f"{request_id}_report.md"
    html = build_markdown_viewer_html(
        request_id=request_id,
        md_file=md_file,
        title="결과 리포트",
    )
    html_key = f"artifacts/{request_id}_report.html"
    chat.create_object(html_key, html)
    url = f"{(chat.path or '').rstrip('/')}/{html_key}"
    logger.info(f"url of html viewer: {url}")
    return url


async def create_final_report(request_id, question, body, urls):
    # Report MD "최종 결과" lists only HTML viewer + DOCX (not steps .html / PDF).
    final_links = []

    report_html_url = publish_markdown_report_html(request_id)
    final_links.append(report_html_url)

    output = await utils.generate_docx_report(body, request_id)
    logger.info(f"result of generate_docx_report: {output}")
    docx_filename = f"artifacts/{request_id}.docx"
    docx_url = f"{(chat.path or '').rstrip('/')}/artifacts/{request_id}.docx"
    if output and os.path.isfile(docx_filename):
        with open(docx_filename, "rb") as f:
            docx_bytes = f.read()
            chat.upload_to_s3_artifacts(docx_bytes, f"{request_id}.docx")
        logger.info(f"url of docx: {docx_url}")
        final_links.append(docx_url)

    key = f"artifacts/{request_id}_report.md"
    time = f"# {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    final_result = body + "\n\n" + f"## 최종 결과\n\n" + "\n\n".join(final_links)
    chat.create_object(key, time + final_result)

    for link in final_links:
        if link not in urls:
            urls.append(link)

    logger.info(f"final_links: {final_links}")
    return urls


class State(TypedDict):
    full_plan: str
    messages: Annotated[list, add_messages]
    appendix: list[str]
    final_response: str
    report: str

async def Coordinator(state: State, config: RunnableConfig) -> dict:
    """Coordinator node that communicate with customers."""
    logger.info(f"###### Coordinator ######")

    question = state["messages"][0].content
    logger.info(f"question: {question}")

    prompt_name = "coordinator"
    containers = _cfg(config, "containers")

    _emit_debug_status(config, prompt_name)

    system_prompt = get_prompt_template(prompt_name)
    logger.info(f"system_prompt: {system_prompt}")

    llm = chat.get_chat()
    coordinator_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{question}"),
        ]
    )

    chain = coordinator_prompt | llm
    result = chain.invoke({
        "question": question
    })
    logger.info(f"result of Coordinator: {result}")

    final_response = ""
    content = result.content
    if not isinstance(content, str):
        content = _coerce_text(content)

    # User-facing text without control tags like <next>to_planner</next>
    display_content = re.sub(r"<next>.*?</next>", "", content, flags=re.DOTALL).strip()

    if content.find("to_planner") == -1:
        content = content.split("<next>")[0].strip()
        logger.info(f"next: END")
        final_response = content
        display_content = content

    if chat.debug_mode == "Enable" and display_content:
        add_notification(config, display_content)

    return {
        "final_response": final_response
    }

async def to_planner(state: State) -> str:
    logger.info(f"###### to_planner ######")
    # logger.info(f"state: {state}")

    if "final_response" in state and state["final_response"] != "":
        next = END
    else:
        next ="Planner"

    return next

async def Planner(state: State, config: RunnableConfig) -> dict:
    logger.info(f"###### Planner ######")
    # logger.info(f"state: {state}")

    request_id = _cfg(config, "request_id", "")
    logger.info(f"request_id: {request_id}")

    containers = _cfg(config, "containers")
    tools = _cfg(config, "tools")

    mcp_tools = get_mcp_tools(tools)
    
    prompt_name = "planner"

    _emit_debug_status(config, prompt_name)

    system = get_prompt_template(prompt_name)
    # logger.info(f"system_prompt of planner: {system}")

    human = "{input}" 

    llm = chat.get_chat()
    planner_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system),
            ("human", human),
        ]
    )

    chain = planner_prompt | llm 
    result = chain.invoke({
        "mcp_tools": mcp_tools,
        "input": state
    })
    logger.info(f"Planner: {result.content}")

    plan_text = result.content
    if not isinstance(plan_text, str):
        plan_text = _coerce_text(plan_text)
    # Hide planner control tags from the Plan card
    plan_text = re.sub(r"<status>.*?</status>", "", plan_text, flags=re.DOTALL).strip()

    if chat.debug_mode == "Enable" and plan_text:
        chat._notify_plan(_nq(config), plan_text)

    # Update the plan into s3
    key = f"artifacts/{request_id}_plan.md"
    time = f"## {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    chat.updata_object(key, time + result.content, 'prepend')

    output = result.content
    if output.find("<status>") != -1:
        status = output.split("<status>")[1].split("</status>")[0]
        logger.info(f"status: {status}")

        if status == "Completed":
            final_response = state["messages"][-1].content
            logger.info(f"final_response: {final_response}")

            return {
                "full_plan": result.content,
                "final_response": final_response                
            }

    return {
        "full_plan": result.content,
    }

async def to_operator(state: State, config: RunnableConfig) -> str:
    logger.info(f"###### to_operator ######")
    # logger.info(f"state: {state}")

    request_id = _cfg(config, "request_id", "")
    logger.info(f"request_id: {request_id}")

    if "final_response" in state and state["final_response"] != "":
        logger.info(f"Finished!!!")
        next = "Reporter"

        key = f"artifacts/{request_id}.md"
        body = f"# Final Response\n\n{state.get('final_response', '')}\n\n"
        chat.updata_object(key, body, 'append')

    else:
        logger.info(f"go to Operator...")
        next = "Operator"

    return next

async def Operator(state: State, config: RunnableConfig) -> dict:
    logger.info(f"###### Operator ######")
    # logger.info(f"state: {state}")
    appendix = state["appendix"] if "appendix" in state else []

    containers = _cfg(config, "containers")
    tools = _cfg(config, "tools")

    mcp_tools = get_mcp_tools(tools)
    
    last_state = state["messages"][-1].content
    logger.info(f"last_state: {last_state}")

    full_plan = state["full_plan"]
    logger.info(f"full_plan: {full_plan}")

    request_id = _cfg(config, "request_id", "")
    prompt_name = "operator"

    _emit_debug_status(config, prompt_name)

    system = get_prompt_template(prompt_name)
    # logger.info(f"system_prompt: {system}")

    human = (
        "<full_plan>{full_plan}</full_plan>\n"
        "<tools>{mcp_tools}</tools>\n"
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system),
            ("human", human),
        ]
    )

    logger.info(f"mcp_tools: {mcp_tools}")

    llm = chat.get_chat()
    chain = prompt | llm 
    result = chain.invoke({
        "full_plan": full_plan,
        "mcp_tools": mcp_tools
    })
    logger.info(f"result: {result}")
    
    content = result.content
    # Remove control characters
    content = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', content)
    # Try to extract JSON string
    try:
        # Regular expression to find JSON object
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            content = json_match.group(0)
        result_dict = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        logger.error(f"Problematic content: {content}")
        return {
            "messages": [
                HumanMessage(content="JSON parsing error occurred. Please try again.")
            ]
        }

    next = result_dict["next"]
    logger.info(f"next: {next}")

    task = result_dict["task"]
    logger.info(f"task: {task}")

    if next == "FINISHED":
        return
    else:
        tool_info = []
        for tool in tools:
            if tool.name == next:
                tool_info.append(tool)
                logger.info(f"tool_info: {tool_info}")
                
        global status_msg, response_msg
        # Pass manus containers (includes notification_queue) into the nested agent.
        result, image_url, status_msg, response_msg = await agent.run_task(
            task,
            tool_info,
            None,
            containers,
            "Disable",
            status_msg,
            response_msg,
        )
        logger.info(f"response of Operator: {result}, {image_url}")

        result_text = result if isinstance(result, str) else str(result or "")
        output_images = ""
        if image_url:
            global collected_image_urls
            for url in image_url:
                if url and url not in collected_image_urls:
                    collected_image_urls.append(url)
            for url in image_url:
                output_images += f"![{task}]({url})\n\n"
            appendix.append(output_images)
            logger.info(f"output_images: {output_images}")

        # Persist steps with a markdown heading; UI uses Info for the task label.
        body = f"# {task}\n\n{result_text}\n\n{output_images}"

        nq = _nq(config)
        if nq is not None:
            nq.notify(task)

        display = result_text.strip()
        if output_images:
            display = f"{display}\n\n{output_images}".strip()
        if display:
            add_notification(config, display)

        key = f"artifacts/{request_id}_steps.md"
        time = f"## {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        chat.updata_object(key, time + body, 'append')
        
        # with open(key, "a", encoding="utf-8") as f:
        #     f.write(body)
        
        return {
            "messages": [
                HumanMessage(content=json.dumps(task)),
                AIMessage(content=body)
            ],
            "appendix": appendix
        }

async def Reporter(state: State, config: RunnableConfig) -> dict:
    logger.info(f"###### Reporter ######")

    prompt_name = "reporter"

    containers = _cfg(config, "containers")

    _emit_debug_status(config, prompt_name)

    request_id = _cfg(config, "request_id", "")    
    
    key = f"artifacts/{request_id}_steps.md"
    context = chat.get_object(key)

    logger.info(f"context: {context}")

    system_prompt=get_prompt_template(prompt_name)
    # logger.info(f"system_prompt: {system_prompt}")
    
    llm = chat.get_chat()

    human = (
        "다음의 context를 바탕으로 사용자의 질문에 대한 답변을 작성합니다.\n"
        "<question>{question}</question>\n"
        "<context>{context}</context>"
    )
    reporter_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", human)
        ]
    )

    question = state["messages"][0].content
    logger.info(f"question: {question}")

    chain = reporter_prompt | llm 
    result = chain.invoke({
        "context": context,
        "question": question
    })
    logger.info(f"result of Reporter: {result}")

    if chat.debug_mode == "Enable":
        add_notification(config, result.content)

    key = f"artifacts/{request_id}_report.md"
    time = f"# {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    appendix = state["appendix"] if "appendix" in state else []
    values = '\n\n'.join(appendix)
    logger.info(f"values: {values}")

    chat.create_object(key, time + result.content + values)

    # HTML viewer loads the markdown artifact directly (no server-side md→html).
    publish_markdown_report_html(request_id)

    logger.info(f"url: {chat.path}/artifacts/{request_id}_report.html")

    _emit_debug_status(config, "end")

    return {
        "report": result.content
    }

app = ManusAgent(
    state_schema=State,
    impl=[
        ("Coordinator", Coordinator),
        ("Planner", Planner),
        ("Operator", Operator),
        ("to_planner", to_planner),
        ("to_operator", to_operator),
        ("Reporter", Reporter),
    ]
)

manus_agent = app.compile()

async def run(question: str, tools: list[BaseTool], containers, request_id, report_url, notification_queue=None):
    logger.info(f"request_id: {request_id}")
    logger.info(f"report_url: {report_url}")

    inputs = {
        "messages": [HumanMessage(content=question)],
        "final_response": "",
        "appendix": [],
    }
    config = {
        "recursion_limit": 50,
        "configurable": {
            "request_id": request_id,
            "containers": containers,
            "tools": tools,
            "notification_queue": notification_queue
            if notification_queue is not None
            else (
                containers.get("notification_queue")
                if isinstance(containers, dict)
                else None
            ),
        },
    }

    if chat.debug_mode == "Enable":
        _emit_debug_status(config, "start")

    try:
        graph_diagram = manus_agent.get_graph().draw_mermaid_png(
            draw_method=MermaidDrawMethod.API,
            curve_style=CurveStyle.LINEAR,
        )
        random_id = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=8))
        image_filename = f"workflow_{random_id}.png"
        url = chat.upload_to_s3(graph_diagram, image_filename)
        logger.info(f"url: {url}")
        if url:
            key = f"artifacts/{request_id}_plan.md"
            task = "실행 계획"
            output_images = f"![{task}]({url})\n\n"
            body = f"## {task}\n\n{output_images}"
            chat.updata_object(key, body, "prepend")
    except Exception as e:
        logger.warning(f"Failed to draw/upload workflow graph: {e}")

    value = None
    async for output in manus_agent.astream(inputs, config):
        for key, value in output.items():
            logger.info(f"Finished running: {key}")
    logger.info(f"value: {value}")

    if not value:
        result = "답변을 찾지 못하였습니다."
    elif "report" in value:
        result = value["report"]
    else:
        result = value.get("final_response") or ""
    logger.info(f"result: {result}")

    urls = [report_url] if report_url else []
    urls = await create_final_report(request_id, question, result, urls)
    logger.info(f"urls: {urls}")

    return result, urls


def get_tool_info(tools, containers):
    tool_list = [tool.name for tool in tools]
    msg = f"Tools: {', '.join(tool_list)}"
    if containers and containers.get("tools"):
        containers["tools"].info(msg)
    logger.info(msg)


async def _load_manus_tools(mcp_servers: list, skill_list: list, user_id: str | None):
    """Load MCP + skill tools using agent-skills style config."""
    tools = []
    mcp_json = mcp_config.load_selected_config(mcp_servers or [])
    chat.mcp_json = mcp_json
    server_params = langgraph_agent.load_multiple_mcp_server_parameters(mcp_json)

    for server_name in (
        "memory",
        "graph memory",
        "kb_retriever",
        "kb-retriever",
        "imageGeneration",
        "image_generation",
    ):
        params = server_params.get(server_name)
        if params and params.get("transport") == "stdio":
            env = dict(params.get("env") or {})
            env["AGENTCORE_USER_ID"] = user_id or chat.user_id
            params["env"] = env

    for server_name, params in server_params.items():
        try:
            client = MultiServerMCPClient({server_name: params})
            mcp_tools = await client.get_tools()
            for tool in mcp_tools:
                if tool.name not in [t.name for t in tools]:
                    tools.append(tool)
        except Exception as e:
            logger.error(f"Failed to load MCP server '{server_name}': {e}")

    tools.extend(skill.get_skill_tools())
    if skill_list:
        skill.set_user_workspace(user_id)
    logger.info(f"manus tool_list: {[t.name for t in tools]}")
    return tools


async def run_manus(
    query,
    notification_queue=None,
    mcp_servers=None,
    skill_list=None,
    user_id=None,
    historyMode="Enable",
):
    """Run Manus pipeline; returns (response, image_url, urls)."""
    global status_msg, response_msg, collected_image_urls, index
    status_msg = []
    response_msg = []
    collected_image_urls = []
    index = 0

    containers = make_containers(notification_queue)
    tools = await _load_manus_tools(mcp_servers or [], skill_list or [], user_id)

    if chat.debug_mode == "Enable":
        get_tool_info(tools, containers)

    request_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    template = open(os.path.join(os.path.dirname(__file__), "report.html")).read()
    template = template.replace("{request_id}", request_id)
    template = template.replace("{sharing_url}", chat.path or "")
    chat.create_object(f"artifacts/{request_id}.html", template)

    report_url = f"{(chat.path or '').rstrip('/')}/artifacts/{request_id}.html"
    logger.info(f"report_url: {report_url}")
    if notification_queue is not None:
        notification_queue.notify(f"report_url: {report_url}")

    response, urls = await run(
        query, tools, containers, request_id, report_url, notification_queue=notification_queue
    )
    logger.info(f"response: {response}")

    if urls:
        url_block = "\n\n".join(urls)
        response = (response or "") + "\n\n## 최종 결과\n\n" + url_block
        chat._notify_stream(notification_queue, url_block)

    image_url = list(collected_image_urls)
    chat._notify_result(notification_queue, response or "")

    return response, image_url, urls
