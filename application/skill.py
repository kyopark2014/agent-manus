import os
import yaml
import logging
import sys
import utils
import yaml

from dataclasses import dataclass
from langchain_core.tools import tool
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(filename)s:%(lineno)d | %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("skill")

WORKING_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(WORKING_DIR, "skills")
# Per-user artifacts / skills under SESSION_STORAGE_DIR (via set_user_workspace).
ARTIFACTS_DIR = utils.get_user_artifacts_dir("default")
USER_SKILLS_DIR = utils.get_user_skills_dir("default")

config = utils.load_config()
sharing_url = config.get("sharing_url")


def set_user_artifacts(user_id: str | None) -> str:
    """Point ARTIFACTS_DIR at {SESSION_STORAGE_DIR}/{user_id}/artifacts for skill prompts."""
    global ARTIFACTS_DIR
    artifacts_dir = utils.ensure_user_artifacts_dir(user_id)
    ARTIFACTS_DIR = artifacts_dir
    logger.info(f"skill ARTIFACTS_DIR set for user {user_id!r}: {artifacts_dir}")
    return artifacts_dir


def set_user_skills(user_id: str | None) -> str:
    """Point USER_SKILLS_DIR and ensure per-user skills.list exists."""
    global USER_SKILLS_DIR
    skills_dir = utils.ensure_user_skills_dir(user_id)
    USER_SKILLS_DIR = skills_dir
    utils.ensure_user_skills_list(user_id)
    logger.info(f"skill USER_SKILLS_DIR set for user {user_id!r}: {skills_dir}")
    return skills_dir


def set_user_workspace(user_id: str | None) -> tuple[str, str]:
    """Configure per-user artifacts + skills dirs; create skills.list if missing."""
    artifacts_dir = set_user_artifacts(user_id)
    skills_dir = set_user_skills(user_id)
    return artifacts_dir, skills_dir

# ═══════════════════════════════════════════════════════════════════
#  Skill Manager – implementation of Anthropic Agent Skills spec
#     (https://agentskills.io/specification)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Skill:
    name: str
    description: str
    instructions: str
    path: str

class SkillManager:
    """Discovers, loads and selects Agent Skills following the Anthropic spec."""

    def __init__(self, skills_dir: str = SKILLS_DIR):
        self.skills_dir = skills_dir
        self.registry: dict[str, Skill] = {}
        self._discover(skills_dir)

    # ---- discovery & metadata loading ----
    def _discover(self, skills_dir: str):
        """Scan a skills directory and load metadata (frontmatter only) into registry."""
        if not os.path.isdir(skills_dir):
            logger.info(f"skills directory is not found: {skills_dir}")
            return

        for entry in os.listdir(skills_dir):
            skill_md = os.path.join(skills_dir, entry, "SKILL.md")
            if os.path.isfile(skill_md):
                try:
                    meta, instructions = self._parse_skill_md(skill_md)
                    skill = Skill(
                        name=meta.get("name", entry),
                        description=meta.get("description", ""),
                        instructions=instructions,
                        path=os.path.join(skills_dir, entry),
                    )
                    self.registry[skill.name] = skill
                    logger.info(f"Skill discovered: {skill.name}")
                except Exception as e:
                    logger.warning(f"Failed to load skill '{entry}': {e}")

    def discover_plugin_skills(self, skills_dir: str):
        """Scan a plugin's skills directory and add to registry (merge, do not replace)."""
        if not os.path.isdir(skills_dir):
            return
        for entry in os.listdir(skills_dir):
            skill_md = os.path.join(skills_dir, entry, "SKILL.md")
            if os.path.isfile(skill_md):
                try:
                    meta, instructions = self._parse_skill_md(skill_md)
                    skill = Skill(
                        name=meta.get("name", entry),
                        description=meta.get("description", ""),
                        instructions=instructions,
                        path=os.path.join(skills_dir, entry),
                    )
                    self.registry[skill.name] = skill
                    logger.info(f"Plugin skill discovered: {skill.name}")
                except Exception as e:
                    logger.warning(f"Failed to load plugin skill '{entry}': {e}")

    @staticmethod
    def _parse_skill_md(filepath: str) -> tuple[dict, str]:
        """Parse YAML frontmatter + markdown body from a SKILL.md file."""
        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()

        if not raw.startswith("---"):
            return {}, raw

        parts = raw.split("---", 2)
        if len(parts) < 3:
            return {}, raw

        frontmatter = yaml.safe_load(parts[1]) or {}
        body = parts[2].strip()
        return frontmatter, body

    def get_skill_instructions(self, name: str) -> Optional[str]:
        """Return full instructions for a skill (loaded on demand)."""
        skill = self.registry.get(name)
        return skill.instructions if skill else None

# define global skill_managers
skill_managers: dict[str, SkillManager] = {}

def get_skills_xml(skill_info: list) -> str:
    lines = ["<available_skills>"]
    for s in skill_info:
        lines.append("  <skill>")
        lines.append(f"    <name>{s['name']}</name>")
        lines.append(f"    <description>{s['description']}</description>")
        lines.append("  </skill>")
    lines.append("</available_skills>")
    return "\n".join(lines)

def register_plugin_skills(plugin_name: str):
    """Register skills from a plugin's skills directory into SkillManager's registry."""    
    if plugin_name == "base": # base skills
        skills_dir = SKILLS_DIR
    else:   # plugin skills
        skills_dir = os.path.join(WORKING_DIR, "plugins", plugin_name, "skills")
    
    skill_manager = skill_managers.get(plugin_name)
    if skill_manager is None:
        skill_manager = SkillManager(skills_dir)
        skill_managers[plugin_name] = skill_manager

    skill_manager.discover_plugin_skills(skills_dir)


def get_skill_info(skill_list: list) -> list:
    skill_manager = skill_managers.get('base')
    if skill_manager is None:
        skill_manager = SkillManager(SKILLS_DIR)
        skill_managers['base'] = skill_manager
        skill_manager.discover_plugin_skills(SKILLS_DIR)

    # Merge per-user skill-creator skills from .session_storage/{user}/skills.
    if USER_SKILLS_DIR and os.path.isdir(USER_SKILLS_DIR):
        skill_manager.discover_plugin_skills(USER_SKILLS_DIR)

    registry = skill_manager.registry
    
    if not registry:
        return []
    
    skill_info = []
    for s in registry.values():
        if s.name in skill_list:
            skill_info.append({"name": s.name, "description": s.description})
        
    return skill_info


def get_plugin_skill_info(plugin_name: str) -> list:
    skill_manager = skill_managers.get(plugin_name)
    if skill_manager is None:
        skills_dir = os.path.join(WORKING_DIR, "plugins", plugin_name, "skills")
        skill_manager = SkillManager(skills_dir)
        skill_managers[plugin_name] = skill_manager
        skill_manager.discover_plugin_skills(skills_dir)

    registry = skill_manager.registry
    return registry.values()


def available_skill_info(plugin_name: str) -> list:
    skill_manager = skill_managers.get(plugin_name)
    if skill_manager is None:
        if plugin_name == "base": # base skills
            skills_dir = SKILLS_DIR
        else:   # plugin skills
            skills_dir = os.path.join(WORKING_DIR, "plugins", plugin_name, "skills")
        skill_manager = SkillManager(skills_dir)
        skill_managers[plugin_name] = skill_manager

    registry = skill_manager.registry
    
    if not registry:
        return []
    
    skill_info = []
    for s in registry.values():
        skill_info.append({"name": s.name, "description": s.description})
        
    return skill_info


def selected_skill_info(plugin_name: str) -> list:
    if plugin_name == "base":
        skill_list, _ = utils.get_initial_tool_defaults()
    else:   # plugin skills
        config = utils.load_config()
        skill_list = config.get("plugin_skills", {}).get(plugin_name) or []
    logger.info(f"plugin_name: {plugin_name}, skill_list: {skill_list}")

    skill_info = available_skill_info(plugin_name)

    selected_skill_info = []
    for s in skill_info:
        if s["name"] in skill_list:
            selected_skill_info.append(s)
    return selected_skill_info


SKILL_SYSTEM_PROMPT = (
    "당신의 이름은 서연이고, 질문에 친근한 방식으로 대답하도록 설계된 대화형 AI입니다.\n"
    "상황에 맞는 구체적인 세부 정보를 충분히 제공합니다.\n"
    "모르는 질문을 받으면 솔직히 모른다고 말합니다.\n"
    "한국어로 답변하세요.\n\n"
    "## Agent Workflow\n"
    "1. 사용자 입력을 받는다\n"
    "2. 요청에 맞는 skill이 있으면 get_skill_instructions 도구로 상세 지침을 로드한다\n"
    "3. skill 지침에 따라 execute_code, write_file 등의 도구를 사용하여 작업을 수행한다\n"
    "4. 결과 파일이 있으면 upload_file_to_s3로 업로드하여 URL을 제공한다\n"
    "5. 최종 결과를 사용자에게 전달한다\n\n"
)

# Injected only when MCP "memory" is selected (see chat.append_tool_guidance_to_prompt).
MEMORY_RECALL_GUIDANCE = (
    "## Memory\n"
    "답변 전에 MCP 도구 recall_memory(action=\"retrieve\", query=<사용자 질문>)를 "
    "1회 이상 호출하세요.\n"
    "execute_code 안에서 recall_memory를 호출하지 마세요 "
    "(execute_code 환경에는 정의되어 있지 않습니다).\n"
    "skill 지침이 없는 질문이더라도 사용자 맥락이 필요하면 recall_memory로 "
    "먼저 조회한 뒤 답변하세요. 개인 정보·선호·위치는 추측하지 마세요.\n"
)

SKILL_USAGE_GUIDE = (
    "\n## Skill 사용 가이드\n"
    "위의 <available_skills>에 나열된 skill이 사용자의 요청과 관련될 때:\n"
    "1. 먼저 get_skill_instructions(plugin_name=\"base\", "
    "skill_name=\"<available_skills의 name>\")로 상세 지침을 로드하세요.\n"
    "   - plugin_name은 항상 \"base\" (MCP 서버 이름·구 skill 이름 금지).\n"
    "   - skill_name은 <name>과 정확히 일치해야 합니다 "
    "(예: architecture-drawer).\n"
    "2. **중요: 지침을 읽기 전에 어떤 작업을 할지 단정짓지 마세요.** "
    "skill의 description에 서브커맨드(query, path, explain 등)가 있다면, "
    "사용자 명령의 서브커맨드를 정확히 파악한 후 그에 맞는 동작을 설명하세요.\n"
    "3. 지침에 포함된 코드 패턴을 execute_code 도구로 실행하세요.\n"
)

def build_skill_prompt(skill_info: list) -> str:
    """Build skill-related prompt: path info, available skills XML, and usage guide."""
        
    path_info = (
        f"## Paths (use absolute paths for write_file, read_file)\n"
        f"- WORKING_DIR: {WORKING_DIR}\n"
        f"- ARTIFACTS_DIR: {ARTIFACTS_DIR}\n"
        f"- USER_SKILLS_DIR: {USER_SKILLS_DIR}\n"
        f"Example: write_file(filepath='{os.path.join(ARTIFACTS_DIR, 'report.drawio')}', content='...')\n"
        f"New skills: write under USER_SKILLS_DIR/<skill-name>/SKILL.md "
        f"(not under WORKING_DIR/skills/).\n\n"
    )

    skills_xml = get_skills_xml(skill_info)
    if skills_xml:
        return f"{SKILL_SYSTEM_PROMPT}\n{path_info}\n{skills_xml}\n{SKILL_USAGE_GUIDE}"
    return f"{SKILL_SYSTEM_PROMPT}\n{path_info}"

def get_command_instructions(plugin_name: str, command_name: str) -> str:
    """Load the full instructions for a specific command by name.

    Use this when you need detailed instructions for a command.
    """
    logger.info(f"###### get_command_instructions: {command_name} ######")

    commands_dir = os.path.join(WORKING_DIR, "plugins", plugin_name, "commands")
    if not os.path.isdir(commands_dir):
        return f"Plugin '{plugin_name}' has no commands directory."

    command_name_normalized = command_name.lower().strip()
    filepath = os.path.join(commands_dir, f"{command_name_normalized}.md")

    if not os.path.isfile(filepath):
        available = [
            p[:-3] for p in os.listdir(commands_dir)
            if p.endswith(".md")
        ]
        return f"Command '{command_name}' not found. Available commands: {', '.join(available)}"

    frontmatter, body = SkillManager._parse_skill_md(filepath)
    # Return body (instructions); optionally prefix with frontmatter summary
    if frontmatter:
        desc = frontmatter.get("description", "")
        hint = frontmatter.get("argument-hint", "")
        header = f"**{desc}**\n"
        if hint:
            header += f"Argument hint: {hint}\n\n"
        return header + body
    return body

COMMAND_USAGE_GUIDE = (
    "\n## Command 사용 가이드\n"
    "위의 <command_instructions>에 따라 사용자 요청을 처리하세요.\n"
    "필요한 경우 get_skill_instructions로 skill 지침을 추가 로드하거나, execute_code, write_file 등 도구를 사용하세요.\n"
)


def build_command_prompt(plugin_name: str, command: str) -> str:
    """Build prompt for command mode: path info, command instructions, and available skills."""
    skill_info = selected_skill_info(plugin_name)
    logger.info(f"plugin_name: {plugin_name}, command: {command}, skill_info: {skill_info}")

    if plugin_name != "base":
        default_skill_info = selected_skill_info("base")
        if default_skill_info:
            skill_info.extend(default_skill_info)
            logger.info(f"default_skill_info: {default_skill_info}")

    path_info = (
        f"## Paths (use absolute paths for write_file, read_file)\n"
        f"- WORKING_DIR: {WORKING_DIR}\n"
        f"- ARTIFACTS_DIR: {ARTIFACTS_DIR}\n"
        f"- USER_SKILLS_DIR: {USER_SKILLS_DIR}\n"
        f"Example: write_file(filepath='{os.path.join(ARTIFACTS_DIR, 'report.drawio')}', content='...')\n"
        f"New skills: write under USER_SKILLS_DIR/<skill-name>/SKILL.md.\n\n"
    )

    command_instructions = get_command_instructions(plugin_name, command)
    command_section = f"## Command Instructions\n<command_instructions>\n{command_instructions}\n</command_instructions>\n\n"

    skills_xml = get_skills_xml(skill_info)
    skills_section = f"{skills_xml}\n" if skills_xml else ""

    return f"{SKILL_SYSTEM_PROMPT}\n{path_info}\n{command_section}\n{skills_section}\n{COMMAND_USAGE_GUIDE}"


# Renamed / legacy skill names → current registry name.
SKILL_ALIASES = {}


def _resolve_skill_name(skill_name: str) -> str:
    key = (skill_name or "").strip()
    return SKILL_ALIASES.get(key, key)


def _get_or_create_skill_manager(plugin_name: str) -> SkillManager:
    skill_manager = skill_managers.get(plugin_name)
    if skill_manager is not None:
        return skill_manager
    if plugin_name == "base":
        skills_dir = SKILLS_DIR
    else:
        skills_dir = os.path.join(WORKING_DIR, "plugins", plugin_name, "skills")
    skill_manager = SkillManager(skills_dir)
    skill_managers[plugin_name] = skill_manager
    return skill_manager


# ═══════════════════════════════════════════════════════════════════
#  2. Skill Tools – get_skill_instructions
# ═══════════════════════════════════════════════════════════════════

@tool
def get_skill_instructions(plugin_name: str, skill_name: str) -> str:
    """Load the full instructions for a specific skill by name.

    Use this when you need detailed instructions for a task that matches
    one of the available skills listed in the system prompt.

    Args:
        plugin_name: Use "base" for application skills in <available_skills>.
        skill_name: Exact <name> from <available_skills>
            (e.g. 'architecture-drawer', 'pdf').

    Returns:
        The full skill instructions, or an error message if not found.
    """
    requested = skill_name
    skill_name = _resolve_skill_name(skill_name)
    if skill_name != requested:
        logger.info(
            "skill alias resolved: %s -> %s", requested, skill_name
        )
    # MCP / legacy names are sometimes passed as plugin_name; treat as base.
    if plugin_name != "base" and not os.path.isdir(
        os.path.join(WORKING_DIR, "plugins", plugin_name, "skills")
    ):
        logger.info(
            "unknown plugin %r; falling back to base for skill %r",
            plugin_name,
            skill_name,
        )
        plugin_name = "base"

    logger.info(f"###### get_skill_instructions: {skill_name} ######")
    skill_manager = _get_or_create_skill_manager(plugin_name)

    instructions = skill_manager.get_skill_instructions(skill_name)
    if instructions:
        return instructions

    # Also search per-user skills when base manager misses the name.
    if plugin_name == "base" and USER_SKILLS_DIR and os.path.isdir(USER_SKILLS_DIR):
        skill_manager.discover_plugin_skills(USER_SKILLS_DIR)
        instructions = skill_manager.get_skill_instructions(skill_name)
        if instructions:
            return instructions

    # fallback to base skills
    skill_manager = _get_or_create_skill_manager("base")
    if USER_SKILLS_DIR and os.path.isdir(USER_SKILLS_DIR):
        skill_manager.discover_plugin_skills(USER_SKILLS_DIR)
    instructions = skill_manager.get_skill_instructions(skill_name)
    if instructions:
        return instructions

    available = ", ".join(skill_manager.registry.keys())
    return f"Skill '{requested}' not found. Available skills: {available}"


def get_skill_tools():
    """Return the list of skill tools for the skill-aware agent."""
    return [get_skill_instructions]

