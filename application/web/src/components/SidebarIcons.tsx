interface IconProps {
  className?: string;
}

export function NewTaskIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.15"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3 2.5h5.5L12.5 6.5V12.5A1 1 0 0 1 11.5 13.5H3A1 1 0 0 1 2 12.5V3.5A1 1 0 0 1 3 2.5Z" />
      <path d="M8.5 2.5V6h3.5" />
      <path d="M12 2.5 13.5 4" />
    </svg>
  );
}

export function SkillIcon({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" aria-hidden="true">
      <path
        fill="currentColor"
        d="M8 1 2 4v2l6 3 6-3V4L8 1Zm0 2.4L11.2 5 8 6.6 4.8 5 8 3.4ZM2 10v2l6 3 6-3v-2l-6 3-6-3Z"
      />
    </svg>
  );
}

export function McpIcon({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" aria-hidden="true">
      <path
        fill="currentColor"
        d="M6.5 1A1.5 1.5 0 0 0 5 2.5V3H3.75A1.75 1.75 0 0 0 2 4.75v2.5A1.75 1.75 0 0 0 3.75 9H5v.5A1.5 1.5 0 0 0 6.5 11h3A1.5 1.5 0 0 0 11 9.5V9h1.25A1.75 1.75 0 0 0 14 7.25v-2.5A1.75 1.75 0 0 0 12.25 3H11v-.5A1.5 1.5 0 0 0 9.5 1h-3ZM6.5 2h3a.5.5 0 0 1 .5.5V3h1.75c.69 0 1.25.56 1.25 1.25v2.5c0 .69-.56 1.25-1.25 1.25H10v.5a.5.5 0 0 1-.5.5h-3a.5.5 0 0 1-.5-.5V9H4.75A1.25 1.25 0 0 1 3.5 7.75v-2.5C3.5 4.56 4.06 4 4.75 4H6v-.5a.5.5 0 0 1 .5-.5ZM8 11.5a1 1 0 0 0-1 1V14h2v-1.5a1 1 0 0 0-1-1Z"
      />
    </svg>
  );
}

export function ModelIcon({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" aria-hidden="true">
      <path
        fill="currentColor"
        d="M3 3h10v10H3V3Zm2 2v6h6V5H5Zm1 1h4v1H6V6Zm0 2h4v1H6V8Zm0 2h3v1H6v-1Z"
      />
    </svg>
  );
}

export function GuardrailIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.15"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M8 1.75 3 4v4c0 3.1 2.13 5.99 5 6.75 2.87-.76 5-3.65 5-6.75V4L8 1.75Z" />
      <path d="M8 7.25v2.5" />
      <circle cx="8" cy="5.75" r="0.75" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function LlmGatewayIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.15"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="2.5" y="5.5" width="4" height="5" rx="0.75" />
      <rect x="9.5" y="5.5" width="4" height="5" rx="0.75" />
      <path d="M6.5 8h3" />
      <path d="M4.5 3.5v2" />
      <path d="M11.5 3.5v2" />
      <path d="M4.5 10.5v2" />
      <path d="M11.5 10.5v2" />
    </svg>
  );
}

export function MemoryIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.15"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="2.5" y="3.5" width="11" height="9" rx="1.25" />
      <path d="M5 3.5v9" />
      <path d="M11 3.5v9" />
      <path d="M2.5 6.5h2.5" />
      <path d="M2.5 9.5h2.5" />
      <path d="M11 6.5h2.5" />
      <path d="M11 9.5h2.5" />
    </svg>
  );
}

export function MenuIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.15"
      strokeLinecap="round"
    >
      <path d="M2.5 4h11" />
      <path d="M2.5 8h11" />
      <path d="M2.5 12h11" />
    </svg>
  );
}

export function CloseIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.15"
      strokeLinecap="round"
    >
      <path d="M4 4l8 8" />
      <path d="M12 4l-8 8" />
    </svg>
  );
}

export function LogoutIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.15"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M6 2.5H3A1 1 0 0 0 2 3.5v9a1 1 0 0 0 1 1h3" />
      <path d="M10.5 11.5 14 8l-3.5-3.5" />
      <path d="M14 8H6" />
    </svg>
  );
}

export function DashboardIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.15"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M2.5 2.5h4.5v4.5H2.5z" />
      <path d="M9 2.5h4.5v6H9z" />
      <path d="M2.5 9h4.5v4.5H2.5z" />
      <path d="M9 10.5h4.5v3H9z" />
    </svg>
  );
}

export function ChevronIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.35"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M6 4l4 4-4 4" />
    </svg>
  );
}

export function SettingsIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

export function AppearanceIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.15"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="8" cy="8" r="5.25" />
      <path d="M8 2.75v10.5A5.25 5.25 0 0 0 8 2.75Z" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function KnowledgeGraphIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.15"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="4" cy="4" r="1.75" />
      <circle cx="12" cy="4.5" r="1.75" />
      <circle cx="8" cy="12" r="1.75" />
      <path d="M5.4 5.1 10.6 5.4" />
      <path d="M4.7 5.7 7.2 10.5" />
      <path d="M11.3 6.1 8.8 10.5" />
    </svg>
  );
}
