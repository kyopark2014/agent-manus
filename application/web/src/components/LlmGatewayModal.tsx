import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { api, type LlmGatewayVerifyResult } from "../api";

interface Props {
  enabled: boolean;
  isAdmin: boolean;
  gatewayConfigured: boolean;
  onConfirmEnable: (uiModels?: string[]) => Promise<void> | void;
  onDisable: () => Promise<void> | void;
  onClose: () => void;
}

export function LlmGatewayModal({
  enabled,
  isAdmin,
  gatewayConfigured,
  onConfirmEnable,
  onDisable,
  onClose,
}: Props) {
  const [url, setUrl] = useState("");
  const [key, setKey] = useState("");
  const [keyConfigured, setKeyConfigured] = useState(false);
  const [loading, setLoading] = useState(isAdmin);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (!isAdmin) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.getLlmGateway();
        if (!cancelled) {
          setUrl(data.url || "");
          setKeyConfigured(Boolean(data.key_configured || data.configured));
          // Never prefill the secret; empty means keep existing.
          setKey("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isAdmin]);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && !busy) onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [busy, onClose]);

  async function handleConfirm() {
    setError(null);
    setSuccess(null);

    if (!isAdmin) {
      setBusy(true);
      setError(null);
      try {
        const status = await api.getLlmGateway();
        if (!status.configured) {
          setError(
            gatewayConfigured
              ? "LLM Gateway가 설정되어 있지 않아 활성화할 수 없습니다. 관리자에게 설정을 요청하세요."
              : "관리자가 LLM Gateway를 먼저 설정해야 합니다.",
          );
          return;
        }
        await onConfirmEnable();
        onClose();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setBusy(false);
      }
      return;
    }

    const nextUrl = url.trim();
    const nextKey = key.trim();
    if (!nextUrl) {
      setError("URL이 필요합니다.");
      return;
    }
    if (!nextKey && !keyConfigured) {
      setError("처음 설정 시 Key가 필요합니다.");
      return;
    }

    setBusy(true);
    try {
      const result: LlmGatewayVerifyResult = await api.verifyLlmGateway({
        url: nextUrl,
        key: nextKey,
      });
      if (!result.ok) {
        setError(result.message || "LLM Gateway 모델 확인에 실패했습니다.");
        return;
      }
      setSuccess(result.message || "모델 확인 성공");
      setKeyConfigured(true);
      setKey("");
      await onConfirmEnable(result.ui_models);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleDisable() {
    setBusy(true);
    setError(null);
    try {
      await onDisable();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const description = isAdmin
    ? "URL을 확인하고, Key는 변경할 때만 입력하세요(비우면 기존 키 유지). 모델 목록 조회에 성공하면 저장·활성화합니다."
    : gatewayConfigured
      ? "이 태스크에서 LLM Gateway 사용을 켜거나 끕니다. 공용 API 키는 서버에만 보관됩니다."
      : "LLM Gateway가 아직 설정되지 않았습니다. 관리자에게 설정을 요청하세요.";

  return createPortal(
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="llm-gateway-title"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !busy) onClose();
      }}
    >
      <div className="modal llm-gateway-modal">
        <h2 id="llm-gateway-title">LLM Gateway</h2>
        <p>
          {description}
          {enabled ? " (현재 사용 중)" : ""}
        </p>

        {isAdmin &&
          (loading ? (
            <p className="llm-gateway-muted">설정 불러오는 중…</p>
          ) : (
            <form
              className="llm-gateway-fields"
              onSubmit={(e) => {
                e.preventDefault();
                if (!busy && !loading) void handleConfirm();
              }}
            >
              <label className="llm-gateway-field">
                <span>URL</span>
                <input
                  type="text"
                  value={url}
                  disabled={busy}
                  autoComplete="off"
                  placeholder="https://gateway.example.com"
                  onChange={(e) => setUrl(e.target.value)}
                />
              </label>
              <label className="llm-gateway-field">
                <span>
                  Key
                  {keyConfigured ? " (저장된 키 있음 — 변경 시에만 입력)" : ""}
                </span>
                <input
                  type="password"
                  value={key}
                  disabled={busy}
                  autoComplete="new-password"
                  placeholder={
                    keyConfigured ? "비워두면 기존 키 유지" : "sk-..."
                  }
                  onChange={(e) => setKey(e.target.value)}
                />
              </label>
              <button type="submit" hidden aria-hidden="true" tabIndex={-1} />
            </form>
          ))}

        {!isAdmin && (
          <p className="llm-gateway-muted">
            {gatewayConfigured
              ? "서버에 Gateway가 구성되어 있습니다."
              : "Gateway 미구성 — 활성화할 수 없습니다."}
          </p>
        )}

        {error && (
          <p className="modal-error" role="alert">
            {error}
          </p>
        )}
        {success && <p className="llm-gateway-success">{success}</p>}

        <div className="modal-actions">
          <button
            type="button"
            className="modal-btn-secondary"
            disabled={busy}
            onClick={onClose}
          >
            취소
          </button>
          {enabled && (
            <button
              type="button"
              className="modal-btn-secondary"
              disabled={busy || loading}
              onClick={handleDisable}
            >
              끄기
            </button>
          )}
          <button
            type="button"
            className="send-btn"
            disabled={
              busy || loading || (!isAdmin && !gatewayConfigured && !enabled)
            }
            onClick={handleConfirm}
          >
            {busy ? "확인 중…" : isAdmin ? "확인" : "켜기"}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
