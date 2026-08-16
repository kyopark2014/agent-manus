import {
  ClipboardEvent,
  CompositionEvent,
  FormEvent,
  KeyboardEvent,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import {
  isImageFile,
  collectClipboardImages,
  useFileUpload,
} from "../hooks/useFileUpload";

interface QueuedMessage {
  id: string;
  text: string;
  files: string[];
}

interface Props {
  disabled?: boolean;
  /** True while waiting for an assistant response (shows stop icon + progress animation). */
  waiting?: boolean;
  queuedMessages?: QueuedMessage[];
  queuePaused?: boolean;
  onRemoveQueued?: (id: string) => void;
  onSteerQueued?: (id: string) => void;
  onResumeQueue?: () => void;
  onStop?: () => void;
  onSend: (text: string, files?: string[]) => void;
  onRagUploadComplete?: (message: string) => void;
}

const RAG_ACCEPT =
  ".pdf,.txt,.md,.csv,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.html,.htm,.json,.py,.js";
const IMAGE_ACCEPT = "image/png,image/jpeg,image/webp,image/gif,.png,.jpg,.jpeg,.webp,.gif";
const MIN_INPUT_HEIGHT = 24;
const MAX_INPUT_HEIGHT = 160;
const MENU_VERTICAL_OFFSET = 8; // gap between the input box and the popup menu above it

export function ChatInput({
  disabled,
  waiting = false,
  queuedMessages = [],
  queuePaused = false,
  onRemoveQueued,
  onSteerQueued,
  onResumeQueue,
  onStop,
  onSend,
  onRagUploadComplete,
}: Props) {
  const [value, setValue] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuPosition, setMenuPosition] = useState<{
    left: number;
    top: number;
    width: number;
  } | null>(null);
  const addWrapRef = useRef<HTMLDivElement>(null);
  const menuPortalRef = useRef<HTMLDivElement>(null);
  const addBtnRef = useRef<HTMLButtonElement>(null);
  const inputWrapRef = useRef<HTMLFormElement>(null);
  const ragInputRef = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const isComposingRef = useRef(false);
  const submitAfterCompositionRef = useRef(false);

  const {
    uploading,
    uploadError,
    attachments,
    dragOver,
    isUploading,
    clearUploadError,
    uploadImageFiles,
    uploadRagFile,
    removeAttachment,
    clearAttachments,
    onDragEnter,
    onDragOver,
    onDragLeave,
    onDrop,
  } = useFileUpload({ disabled });

  function adjustInputHeight() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const next = Math.min(
      Math.max(el.scrollHeight, MIN_INPUT_HEIGHT),
      MAX_INPUT_HEIGHT,
    );
    el.style.height = `${next}px`;
  }

  useLayoutEffect(() => {
    adjustInputHeight();
  }, [value]);

  function updateMenuPosition() {
    const rect = inputWrapRef.current?.getBoundingClientRect();
    if (!rect) return;
    setMenuPosition({
      left: rect.left,
      top: rect.top - MENU_VERTICAL_OFFSET,
      width: rect.width,
    });
  }

  useEffect(() => {
    if (!menuOpen) {
      setMenuPosition(null);
      return;
    }

    updateMenuPosition();
    window.addEventListener("resize", updateMenuPosition);
    window.addEventListener("scroll", updateMenuPosition, true);

    function onPointerDown(e: MouseEvent) {
      const target = e.target as Node;
      if (addWrapRef.current?.contains(target)) return;
      if (menuPortalRef.current?.contains(target)) return;
      setMenuOpen(false);
    }
    function onKeyDown(e: globalThis.KeyboardEvent) {
      if (e.key === "Escape") setMenuOpen(false);
    }

    document.addEventListener("mousedown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("resize", updateMenuPosition);
      window.removeEventListener("scroll", updateMenuPosition, true);
      document.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [menuOpen]);

  function submit(textOverride?: string) {
    const text = (textOverride ?? value).trim();
    const files = attachments.map((item) => item.url);
    if ((!text && files.length === 0) || disabled || uploading) return;
    onSend(text, files);
    setValue("");
    clearAttachments();
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key !== "Enter" || e.shiftKey) return;
    // Korean/CJK IME: Enter confirms composition — do not send mid-compose.
    // keyCode 229 covers browsers that omit isComposing on the confirming Enter.
    if (
      e.nativeEvent.isComposing ||
      e.keyCode === 229 ||
      isComposingRef.current
    ) {
      submitAfterCompositionRef.current = true;
      return;
    }
    // Some browsers fire a second Enter after 229; compositionend will submit.
    if (submitAfterCompositionRef.current) {
      e.preventDefault();
      return;
    }
    e.preventDefault();
    submit();
  }

  function onCompositionStart() {
    isComposingRef.current = true;
  }

  function onCompositionEnd(e: CompositionEvent<HTMLTextAreaElement>) {
    isComposingRef.current = false;
    if (!submitAfterCompositionRef.current) return;
    submitAfterCompositionRef.current = false;
    // React state can lag behind the DOM after compositionend; use live value.
    submit(e.currentTarget.value);
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (isComposingRef.current || submitAfterCompositionRef.current) return;
    submit();
  }

  async function onPaste(e: ClipboardEvent<HTMLTextAreaElement>) {
    if (disabled || isUploading()) return;
    const imageFiles = collectClipboardImages(e.clipboardData);
    if (imageFiles.length === 0) return;

    e.preventDefault();
    await uploadImageFiles(imageFiles);
  }

  function openImageUpload() {
    setMenuOpen(false);
    clearUploadError();
    imageInputRef.current?.click();
  }

  function openRagUpload() {
    setMenuOpen(false);
    clearUploadError();
    ragInputRef.current?.click();
  }

  async function onImageSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []).filter(isImageFile);
    e.target.value = "";
    await uploadImageFiles(files);
  }

  async function onRagFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    await uploadRagFile(file, onRagUploadComplete);
  }

  const inputDisabled = disabled || uploading;
  const canSend =
    !inputDisabled && (value.trim().length > 0 || attachments.length > 0);
  const showInputSteer = queuedMessages.length > 0 && canSend;

  function onLeftButtonClick() {
    if (showInputSteer) {
      submit();
      return;
    }
    setMenuOpen((open) => !open);
  }

  const menu =
    menuOpen && menuPosition
      ? createPortal(
          <div
            ref={menuPortalRef}
            className="chat-add-menu chat-add-menu-portal"
            role="menu"
            style={{
              left: menuPosition.left,
              top: menuPosition.top,
              width: menuPosition.width,
            }}
          >
            <button
              type="button"
              className="chat-add-menu-item"
              role="menuitem"
              onClick={openImageUpload}
            >
              <span className="chat-add-menu-icon" aria-hidden="true">
                <svg width="16" height="16" viewBox="0 0 16 16">
                  <rect
                    x="2.5"
                    y="3.5"
                    width="11"
                    height="9"
                    rx="1.5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.2"
                  />
                  <circle cx="6" cy="7" r="1.2" fill="currentColor" />
                  <path
                    d="M4.5 11.5 7 9l2 1.5 2.5-3 2 4"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>
              <span className="chat-add-menu-text">
                <span className="chat-add-menu-label">사진 첨부</span>
                <span className="chat-add-menu-desc">
                  이미지를 첨부하거나 Ctrl/⌘+V로 붙여넣기
                </span>
              </span>
            </button>
            <button
              type="button"
              className="chat-add-menu-item"
              role="menuitem"
              onClick={openRagUpload}
            >
              <span className="chat-add-menu-icon" aria-hidden="true">
                <svg width="16" height="16" viewBox="0 0 16 16">
                  <path
                    d="M4 2.5h5.5L12 5v8.5a.5.5 0 0 1-.5.5H4a.5.5 0 0 1-.5-.5v-11a.5.5 0 0 1 .5-.5Z"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.2"
                  />
                  <path
                    d="M9.5 2.5V5H12"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.2"
                  />
                </svg>
              </span>
              <span className="chat-add-menu-text">
                <span className="chat-add-menu-label">Upload to RAG</span>
                <span className="chat-add-menu-desc">
                  S3에 업로드하고 Knowledge Base 동기화
                </span>
              </span>
            </button>
          </div>,
          document.body,
        )
      : null;

  return (
    <div className="chat-input-area">
      {uploadError && (
        <div className="chat-upload-error" role="alert">
          {uploadError}
        </div>
      )}
      {uploading && (
        <div className="chat-upload-status" role="status">
          업로드 중...
        </div>
      )}
      {queuedMessages.length > 0 && (
        <div
          className={`chat-queue-panel${queuePaused ? " is-paused" : ""}`}
          aria-label="대기 중인 메시지"
        >
          {queuePaused && (
            <div className="chat-queue-header">
              <span className="chat-queue-paused-label">
                Queue paused because you interrupted
              </span>
              <button
                type="button"
                className="chat-queue-resume"
                onClick={() => onResumeQueue?.()}
              >
                Resume
              </button>
            </div>
          )}
          <ul className="chat-queue">
            {queuedMessages.map((item) => {
              const label =
                item.text.trim() ||
                (item.files.length > 0
                  ? `첨부 ${item.files.length}개`
                  : "메시지");
              return (
                <li key={item.id} className="chat-queue-item">
                  <span className="chat-queue-text" title={label}>
                    {label}
                  </span>
                  <div className="chat-queue-actions">
                    <button
                      type="button"
                      className="chat-queue-steer"
                      title="진행 중인 응답을 멈추고 이 메시지로 전환"
                      aria-label={`이 메시지로 전환: ${label}`}
                      onClick={() => onSteerQueued?.(item.id)}
                    >
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 16 16"
                        aria-hidden="true"
                      >
                        <path
                          d="M5 3.5 2.5 6 5 8.5M2.5 6H10a3.5 3.5 0 0 1 0 7H8"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="1.4"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    </button>
                    <button
                      type="button"
                      className="chat-queue-remove"
                      aria-label={`대기 메시지 삭제: ${label}`}
                      onClick={() => onRemoveQueued?.(item.id)}
                    >
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 16 16"
                        aria-hidden="true"
                      >
                        <path
                          d="M5.5 3.5h5M6.5 3.5V2.75A.75.75 0 0 1 7.25 2h1.5a.75.75 0 0 1 .75.75V3.5m2 0V13a1 1 0 0 1-1 1H5.5a1 1 0 0 1-1-1V3.5h8ZM7 6.5v5M9 6.5v5"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="1.2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
      <form
        className={`chat-input-wrap${dragOver ? " is-dragover" : ""}`}
        ref={inputWrapRef}
        onSubmit={onSubmit}
        onDragEnter={onDragEnter}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      >
        <input
          ref={imageInputRef}
          type="file"
          className="chat-file-input"
          accept={IMAGE_ACCEPT}
          multiple
          onChange={onImageSelected}
          tabIndex={-1}
          aria-hidden="true"
        />
        <input
          ref={ragInputRef}
          type="file"
          className="chat-file-input"
          accept={RAG_ACCEPT}
          onChange={onRagFileSelected}
          tabIndex={-1}
          aria-hidden="true"
        />
        {attachments.length > 0 && (
          <div className="chat-attachments" aria-label="첨부 이미지">
            {attachments.map((item) => (
              <div key={item.url} className="chat-attachment">
                <img src={item.previewUrl} alt={item.name} />
                <button
                  type="button"
                  className="chat-attachment-remove"
                  aria-label={`${item.name} 제거`}
                  onClick={() => removeAttachment(item.url)}
                  disabled={inputDisabled}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
        <textarea
          ref={textareaRef}
          className="chat-input"
          rows={1}
          placeholder="메시지를 입력하거나 이미지를 붙여넣으세요..."
          value={value}
          disabled={inputDisabled}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          onCompositionStart={onCompositionStart}
          onCompositionEnd={onCompositionEnd}
          onPaste={onPaste}
        />
        <div className="chat-input-toolbar">
          <div className="chat-input-add-wrap" ref={addWrapRef}>
            <button
              ref={addBtnRef}
              type="button"
              className={showInputSteer ? "chat-steer-btn" : "chat-add-btn"}
              aria-label={
                showInputSteer
                  ? "진행 중인 응답을 멈추지 않고 대기열에 추가"
                  : "추가"
              }
              title={
                showInputSteer
                  ? "진행 중인 응답을 멈추지 않고 대기열에 추가"
                  : undefined
              }
              aria-expanded={showInputSteer ? undefined : menuOpen}
              disabled={inputDisabled}
              onClick={onLeftButtonClick}
            >
              {showInputSteer ? (
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 16 16"
                  aria-hidden="true"
                >
                  <path
                    d="M5 3.5 2.5 6 5 8.5M2.5 6H10a3.5 3.5 0 0 1 0 7H8"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.4"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                  <path
                    d="M8 3v10M3 8h10"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  />
                </svg>
              )}
            </button>
          </div>
          {waiting ? (
            <button
              className="chat-send-btn is-waiting"
              type="button"
              aria-label="응답 중지"
              aria-busy="true"
              onClick={() => onStop?.()}
            >
              <span className="chat-send-progress" aria-hidden="true" />
              <span className="chat-send-stop" aria-hidden="true" />
            </button>
          ) : (
            <button
              className="chat-send-btn"
              type="submit"
              aria-label="전송"
              disabled={!canSend}
            >
              <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                <path
                  d="M8 12.5V3.5M4.5 7 8 3.5 11.5 7"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          )}
        </div>
      </form>
      {menu}
    </div>
  );
}
