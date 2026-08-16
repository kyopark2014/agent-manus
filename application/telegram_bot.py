import asyncio
import logging
import sys
import os

os.environ["DEV"] = "true"

import chat
import utils

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ChatAction, ParseMode

logging.basicConfig(
    level=logging.INFO,
    format='%(filename)s:%(lineno)d | %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("telegram_bot")

TELEGRAM_BOT_TOKEN = utils.telegram_api_key

DEFAULT_MODEL = "Claude 5.0 Sonnet"


def get_default_tool_selection() -> tuple[list[str], list[str]]:
    skill_list, mcp_servers = utils.get_initial_tool_defaults()
    return mcp_servers, skill_list

chat.update(modelName=DEFAULT_MODEL, debugMode="Enable", memoryEnabled=True)

MAX_MSG_LEN = 4096


async def send_long_message(chat_id, text, context):
    """Telegram 4096자 제한을 고려하여 메시지를 분할 전송"""
    for i in range(0, len(text), MAX_MSG_LEN):
        chunk = text[i:i + MAX_MSG_LEN]
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=chunk,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            await context.bot.send_message(
                chat_id=chat_id,
                text=chunk,
            )


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "안녕하세요! Agent Skills 봇입니다.\n"
        "메시지를 보내시면 AI Agent가 답변해 드립니다.\n\n"
        "명령어:\n"
        "/start - 이 안내 메시지\n"
        "/model <모델명> - 모델 변경\n"
        "/mcp - 현재 MCP 서버 목록 확인"
    )


async def model_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(f"현재 모델: {DEFAULT_MODEL}\n\n사용법: /model <모델명>")
        return

    model_name = " ".join(context.args)
    try:
        chat.update(modelName=model_name, debugMode="Enable")
        await update.message.reply_text(f"모델이 변경되었습니다: {model_name}")
    except Exception as e:
        logger.error(f"Model change failed: {e}")
        await update.message.reply_text(f"모델 변경 실패: {e}")


async def mcp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    default_mcp_servers, _ = get_default_tool_selection()
    servers = "\n".join(f"  - {s}" for s in default_mcp_servers)
    await update.message.reply_text(f"현재 MCP 서버:\n{servers}")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    chat_id = update.effective_chat.id
    logger.info(f"[chat_id={chat_id}] message: {user_message}")

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    try:
        chat.update(userId=str(chat_id), modelName=chat.model_name, debugMode="Enable")
        default_mcp_servers, default_skill_list = get_default_tool_selection()
        response, image_url = await chat.run_langgraph_agent(
            query=user_message,
            mcp_servers=default_mcp_servers,
            skill_list=default_skill_list,
        )
        logger.info(f"[chat_id={chat_id}] response length: {len(response)}")

        await send_long_message(chat_id, response, context)

        for url in image_url:
            try:
                await context.bot.send_photo(chat_id=chat_id, photo=url)
            except Exception as e:
                logger.error(f"Failed to send image {url}: {e}")

    except Exception as e:
        logger.error(f"Agent error: {e}")
        await update.message.reply_text("처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")


def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_API_KEY is not set. Register the secret in AWS Secrets Manager.")
        sys.exit(1)

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("model", model_handler))
    app.add_handler(CommandHandler("mcp", mcp_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("Telegram bot is starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
