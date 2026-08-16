import { useCallback, useEffect, useRef, type ReactNode } from "react";
import type { Message, ToolEvent } from "../types";
import { MessageBubble, MessageFromRecord } from "./MessageBubble";
import { MenuIcon } from "./SidebarIcons";

const SCROLL_THRESHOLD_PX = 64;

function isNearBottom(el: HTMLElement): boolean {
  return el.scrollHeight - el.scrollTop - el.clientHeight <= SCROLL_THRESHOLD_PX;
}

interface Props {
  messages: Message[];
  streaming: boolean;
  streamText: string;
  streamEvents: ToolEvent[];
  taskTitle: string;
  onMenuClick?: () => void;
  footer?: ReactNode;
}

export function ChatThread({
  messages,
  streaming,
  streamText,
  streamEvents,
  taskTitle,
  onMenuClick,
  footer,
}: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);

  const updateAutoScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    shouldAutoScrollRef.current = isNearBottom(el);
  }, []);

  const taskId = messages[0]?.task_id ?? null;

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.addEventListener("scroll", updateAutoScroll, { passive: true });
    return () => el.removeEventListener("scroll", updateAutoScroll);
  }, [updateAutoScroll]);

  useEffect(() => {
    shouldAutoScrollRef.current = true;
    bottomRef.current?.scrollIntoView({ behavior: "auto" });
  }, [taskId]);

  useEffect(() => {
    if (!shouldAutoScrollRef.current) return;
    bottomRef.current?.scrollIntoView({
      behavior: streaming ? "auto" : "smooth",
    });
  }, [messages, streamText, streamEvents, streaming]);

  return (
    <>
      <header className="main-header">
        <button
          type="button"
          className="menu-btn"
          aria-label="메뉴 열기"
          onClick={onMenuClick}
        >
          <MenuIcon className="sidebar-icon" />
        </button>
        <span className="main-header-title">{taskTitle}</span>
      </header>
      <div className="chat-scroll" ref={scrollRef}>
        <div className="chat-thread">
          {messages.length === 0 && !streaming && (
            <div className="empty-state">
              <p>Amazon Bedrock AgentCore 기반 에이전트입니다.</p>
              <p>메뉴에서 Skill, MCP, Model을 설정하고 대화를 시작하세요.</p>
            </div>
          )}
          {messages.map((m) => (
            <MessageFromRecord key={m.id} message={m} />
          ))}
          {streaming && (
            <>
              {streamEvents.length > 0 || streamText ? (
                <MessageBubble
                  role="assistant"
                  content={streamText}
                  toolEvents={streamEvents}
                />
              ) : (
                <div className="message-row assistant">
                  <div className="streaming-indicator" aria-label="Thinking">
                    Thinking
                    <span className="thinking-ellipsis" aria-hidden="true" />
                  </div>
                </div>
              )}
            </>
          )}
          <div ref={bottomRef} />
        </div>
      </div>
      {footer}
    </>
  );
}
