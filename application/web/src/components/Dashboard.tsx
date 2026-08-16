import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { DashboardStats } from "../types";

interface Props {
  onBack: () => void;
}

function formatWhen(value?: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function Dashboard({ onBack }: Props) {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getAdminDashboard();
      setStats(data);
    } catch (err) {
      setStats(null);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const summary = stats?.summary;

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div>
          <h1>Dashboard</h1>
          <p>가입자 현황과 접속 현황</p>
        </div>
        <div className="dashboard-header-actions">
          <button type="button" className="sidebar-menu-btn" onClick={() => void load()}>
            새로고침
          </button>
          <button type="button" className="sidebar-menu-btn" onClick={onBack}>
            채팅으로 돌아가기
          </button>
        </div>
      </header>

      {loading && <div className="dashboard-status">불러오는 중…</div>}
      {error && <div className="dashboard-error">{error}</div>}

      {!loading && !error && summary && (
        <>
          <section className="dashboard-section">
            <h2>요약</h2>
            <div className="dashboard-metrics">
              <div className="dashboard-metric">
                <span className="dashboard-metric-label">전체 사용자</span>
                <strong>{summary.total_users}</strong>
              </div>
              <div className="dashboard-metric">
                <span className="dashboard-metric-label">Google 가입</span>
                <strong>{summary.google_users}</strong>
              </div>
              <div className="dashboard-metric">
                <span className="dashboard-metric-label">레거시 User ID</span>
                <strong>{summary.legacy_users}</strong>
              </div>
              <div className="dashboard-metric">
                <span className="dashboard-metric-label">오늘 로그인</span>
                <strong>{summary.logins_today}</strong>
              </div>
              <div className="dashboard-metric">
                <span className="dashboard-metric-label">오늘 접속자</span>
                <strong>{summary.active_users_today}</strong>
              </div>
              <div className="dashboard-metric">
                <span className="dashboard-metric-label">7일 로그인</span>
                <strong>{summary.logins_7d}</strong>
              </div>
              <div className="dashboard-metric">
                <span className="dashboard-metric-label">7일 접속자</span>
                <strong>{summary.active_users_7d}</strong>
              </div>
              <div className="dashboard-metric">
                <span className="dashboard-metric-label">태스크 / 메시지</span>
                <strong>
                  {summary.total_tasks} / {summary.total_messages}
                </strong>
              </div>
            </div>
          </section>

          <section className="dashboard-section">
            <h2>일별 접속 (최근 14일)</h2>
            {stats.daily_logins.length === 0 ? (
              <p className="dashboard-empty">아직 기록된 로그인이 없습니다.</p>
            ) : (
              <div className="dashboard-table-wrap">
                <table className="dashboard-table">
                  <thead>
                    <tr>
                      <th>날짜</th>
                      <th>로그인 수</th>
                      <th>고유 사용자</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...stats.daily_logins].reverse().map((row) => (
                      <tr key={row.date}>
                        <td>{row.date}</td>
                        <td>{row.logins}</td>
                        <td>{row.unique_users}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="dashboard-section">
            <h2>가입자 현황</h2>
            <div className="dashboard-table-wrap">
              <table className="dashboard-table">
                <thead>
                  <tr>
                    <th>사용자</th>
                    <th>인증</th>
                    <th>태스크</th>
                    <th>메시지</th>
                    <th>로그인</th>
                    <th>최초 활동</th>
                    <th>최근 활동</th>
                    <th>최근 로그인</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.users.map((user) => (
                    <tr key={user.user_id}>
                      <td className="dashboard-user-cell">{user.user_id}</td>
                      <td>{user.is_google ? "Google" : "Legacy"}</td>
                      <td>{user.task_count}</td>
                      <td>{user.message_count}</td>
                      <td>{user.login_count}</td>
                      <td>{formatWhen(user.first_seen)}</td>
                      <td>{formatWhen(user.last_active)}</td>
                      <td>{formatWhen(user.last_login)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="dashboard-section">
            <h2>최근 접속</h2>
            {stats.recent_logins.length === 0 ? (
              <p className="dashboard-empty">
                로그인 이벤트는 Google(또는 로컬 우회) 로그인 시점부터 기록됩니다.
              </p>
            ) : (
              <div className="dashboard-table-wrap">
                <table className="dashboard-table">
                  <thead>
                    <tr>
                      <th>시각</th>
                      <th>사용자</th>
                      <th>이름</th>
                      <th>방식</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.recent_logins.map((login) => (
                      <tr key={login.id}>
                        <td>{formatWhen(login.logged_at)}</td>
                        <td className="dashboard-user-cell">{login.user_id}</td>
                        <td>{login.name || "—"}</td>
                        <td>{login.method}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
