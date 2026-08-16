import logging
import sys
import os
from typing import Optional

os.environ["DEV"] = "true"

import chat
import utils

import discord
from discord import app_commands
from discord.ext import commands

logging.basicConfig(
    level=logging.INFO,
    format="%(filename)s:%(lineno)d | %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("discord_bot")

DISCORD_BOT_TOKEN = (
    getattr(utils, "discord_bot_token", None) or os.environ.get("DISCORD_BOT_TOKEN") or ""
)

DEFAULT_MODEL = "Claude 5.0 Sonnet"


def get_default_tool_selection() -> tuple[list[str], list[str]]:
    skill_list, mcp_servers = utils.get_initial_tool_defaults()
    return mcp_servers, skill_list

chat.update(modelName=DEFAULT_MODEL, debugMode="Enable", memoryEnabled=True)

# Discord 메시지 본문 제한(일반 전송 기준)
MAX_MSG_LEN = 2000


async def send_long_message(channel: discord.abc.Messageable, text: str):
    """Discord 2000자 제한을 고려하여 메시지를 분할 전송"""
    for i in range(0, len(text), MAX_MSG_LEN):
        chunk = text[i : i + MAX_MSG_LEN]
        await channel.send(chunk)


class AgentSkillsBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="\0", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()


bot = AgentSkillsBot()


@bot.tree.command(name="start", description="봇 안내")
async def start_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(
        "안녕하세요! Agent Skills 봇입니다.\n"
        "메시지를 보내시면 AI Agent가 답변해 드립니다.\n\n"
        "명령어:\n"
        "/start - 이 안내 메시지\n"
        "/model - 현재 모델 확인 또는 변경\n"
        "/mcp - 현재 MCP 서버 목록 확인"
    )


@bot.tree.command(name="model", description="모델 확인 또는 변경")
@app_commands.describe(model_name="변경할 모델명 (비우면 현재 모델만 표시)")
async def model_cmd(interaction: discord.Interaction, model_name: Optional[str] = None):
    if not model_name or not model_name.strip():
        await interaction.response.send_message(
            f"현재 모델: {DEFAULT_MODEL}\n\n변경: `/model` 에 model_name 을 입력하세요."
        )
        return

    name = model_name.strip()
    try:
        chat.update(modelName=name, debugMode="Enable")
        await interaction.response.send_message(f"모델이 변경되었습니다: {name}")
    except Exception as e:
        logger.error(f"Model change failed: {e}")
        await interaction.response.send_message(f"모델 변경 실패: {e}")


@bot.tree.command(name="mcp", description="현재 MCP 서버 목록")
async def mcp_cmd(interaction: discord.Interaction):
    default_mcp_servers, _ = get_default_tool_selection()
    servers = "\n".join(f"  - {s}" for s in default_mcp_servers)
    await interaction.response.send_message(f"현재 MCP 서버:\n{servers}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    user_message = message.content
    if not user_message or not user_message.strip():
        return

    channel = message.channel
    user_label = message.author.display_name
    logger.info(f"[{channel.id} @{user_label}] message: {user_message}")

    async with channel.typing():
        try:
            chat.update(
                userId=str(message.author.id),
                modelName=chat.model_name,
                debugMode="Enable",
            )
            default_mcp_servers, default_skill_list = get_default_tool_selection()
            response, image_url = await chat.run_langgraph_agent(
                query=user_message,
                mcp_servers=default_mcp_servers,
                skill_list=default_skill_list,
            )
            logger.info(f"[{channel.id}] response length: {len(response)}")

            await send_long_message(channel, response)

            for url in image_url:
                try:
                    embed = discord.Embed()
                    embed.set_image(url=url)
                    await channel.send(embed=embed)
                except Exception as e:
                    logger.error(f"Failed to send image {url}: {e}")

        except Exception as e:
            logger.error(f"Agent error: {e}")
            await channel.send("처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")


def main():
    if not DISCORD_BOT_TOKEN:
        logger.error(
            "DISCORD_BOT_TOKEN is not set. "
            "Use env or register discord_bot_token in AWS Secrets Manager (discordapikey)."
        )
        sys.exit(1)

    logger.info("Discord bot is starting...")
    bot.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    main()
