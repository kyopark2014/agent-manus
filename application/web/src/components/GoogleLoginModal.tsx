import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { formatBrandTitle } from "../formatBrandTitle";

interface Props {
  clientId: string;
  onCredential: (credential: string) => void;
  onAccessToken?: (accessToken: string) => void;
  onLocalUserId?: (userId: string) => void;
  localAuthBypass?: boolean;
  error?: string | null;
  projectName?: string | null;
}

type TokenClient = {
  requestAccessToken: (overrideConfig?: { prompt?: string }) => void;
};

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: Record<string, unknown>) => void;
          disableAutoSelect: () => void;
        };
        oauth2: {
          initTokenClient: (config: {
            client_id: string;
            scope: string;
            callback: (response: {
              access_token?: string;
              error?: string;
              error_description?: string;
            }) => void;
            error_callback?: (error: { type?: string; message?: string }) => void;
          }) => TokenClient;
        };
      };
    };
  }
}

const GSI_SCRIPT_ID = "google-gsi-client";
const GSI_SRC = "https://accounts.google.com/gsi/client";

function loadGsiScript(): Promise<void> {
  if (window.google?.accounts?.oauth2) {
    return Promise.resolve();
  }
  const existing = document.getElementById(GSI_SCRIPT_ID) as HTMLScriptElement | null;
  if (existing) {
    return new Promise((resolve, reject) => {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener(
        "error",
        () => reject(new Error("Google 로그인 스크립트 로드 실패")),
        { once: true },
      );
    });
  }
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.id = GSI_SCRIPT_ID;
    script.src = GSI_SRC;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Google 로그인 스크립트 로드 실패"));
    document.head.appendChild(script);
  });
}

function isBrowserLocalHost(): boolean {
  const host = window.location.hostname.toLowerCase();
  return (
    host === "localhost" ||
    host === "127.0.0.1" ||
    host === "::1" ||
    host.endsWith(".local")
  );
}

function GoogleMark({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 48 48" aria-hidden="true">
      <path
        fill="#EA4335"
        d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
      />
      <path
        fill="#FBBC05"
        d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
      />
    </svg>
  );
}

export function GoogleLoginModal({
  clientId,
  onCredential: _onCredential,
  onAccessToken,
  onLocalUserId,
  localAuthBypass = false,
  error,
  projectName,
}: Props) {
  const title = formatBrandTitle(projectName ?? "agent");
  const tokenClientRef = useRef<TokenClient | null>(null);
  const [scriptError, setScriptError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const showLocalBypass = Boolean(localAuthBypass || isBrowserLocalHost());

  const handleTokenResponse = useCallback(
    (response: {
      access_token?: string;
      error?: string;
      error_description?: string;
    }) => {
      setBusy(false);
      if (response?.error) {
        setScriptError(response.error_description || response.error);
        return;
      }
      const token = response?.access_token?.trim();
      if (!token) {
        setScriptError("Google 액세스 토큰을 받지 못했습니다.");
        return;
      }
      if (onAccessToken) {
        onAccessToken(token);
        return;
      }
      setScriptError("Google 로그인 핸들러가 설정되지 않았습니다.");
    },
    [onAccessToken],
  );

  useEffect(() => {
    if (!clientId) return;
    let cancelled = false;

    (async () => {
      try {
        await loadGsiScript();
        if (cancelled || !window.google?.accounts?.oauth2) return;

        tokenClientRef.current = window.google.accounts.oauth2.initTokenClient({
          client_id: clientId,
          scope: "openid email profile",
          callback: handleTokenResponse,
          error_callback: (err) => {
            if (cancelled) return;
            setBusy(false);
            const msg = err?.message || err?.type || "Google 로그인 오류";
            setScriptError(
              `${msg}. OAuth 원본에 ${window.location.origin} 등록 여부를 확인하세요.`,
            );
          },
        });
      } catch (err) {
        if (!cancelled) {
          setScriptError(err instanceof Error ? err.message : String(err));
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [clientId, handleTokenResponse]);

  function handleGoogleClick() {
    setScriptError(null);
    if (!clientId) {
      setScriptError("google_client_id가 설정되지 않았습니다.");
      return;
    }
    if (!tokenClientRef.current) {
      setScriptError("Google 로그인을 준비 중입니다. 잠시 후 다시 시도하세요.");
      return;
    }
    setBusy(true);
    try {
      tokenClientRef.current.requestAccessToken({ prompt: "select_account" });
    } catch (err) {
      setBusy(false);
      setScriptError(err instanceof Error ? err.message : String(err));
    }
  }

  function handleLocalSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!onLocalUserId) return;
    const form = new FormData(e.currentTarget);
    const userId = String(form.get("user_id") ?? "").trim();
    if (userId) onLocalUserId(userId);
  }

  const displayError = error || scriptError;

  const googleButton = (
    <button
      type="button"
      className="auth-google-btn"
      onClick={handleGoogleClick}
      disabled={busy || !clientId}
    >
      <GoogleMark className="auth-google-mark" />
      <span>{busy ? "Google 연결 중…" : "Google로 계속하기"}</span>
    </button>
  );

  return createPortal(
    <div className="auth-screen">
      <div className="auth-backdrop" aria-hidden="true" />
      <div
        className="modal-overlay auth-overlay"
        role="dialog"
        aria-modal="true"
        aria-labelledby="google-login-title"
      >
        <div className="auth-card">
          <div className="auth-card-glow" aria-hidden="true" />
          <div className="auth-brand-mark" aria-hidden="true" />
          <h2 id="google-login-title">{title}</h2>

          {showLocalBypass && onLocalUserId ? (
            <>
              <p className="auth-subtitle">시작하려면 User ID를 입력하세요.</p>
              {displayError && <p className="modal-error">{displayError}</p>}
              <form className="local-auth-bypass" onSubmit={handleLocalSubmit}>
                <label className="auth-field">
                  <span className="auth-field-label">User ID</span>
                  <input
                    name="user_id"
                    placeholder="예: user01"
                    autoComplete="username"
                    autoFocus
                    required
                  />
                </label>
                <button type="submit" className="auth-primary-btn">
                  시작하기
                </button>
              </form>
              {clientId ? (
                <>
                  <div className="google-login-divider">
                    <span>또는</span>
                  </div>
                  {googleButton}
                </>
              ) : null}
            </>
          ) : (
            <>
              <p className="auth-subtitle">시작하려면 Google 계정으로 로그인하세요.</p>
              {displayError && <p className="modal-error">{displayError}</p>}
              {!clientId && (
                <p className="modal-error">google_client_id가 설정되지 않았습니다.</p>
              )}
              {googleButton}
            </>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
