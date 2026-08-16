export function formatBrandTitle(projectName: string, userId?: string | null): string {
  const cleaned = projectName.replace(/-/g, " ").trim();
  const base = !cleaned ? "Agent" : cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
  const id = userId?.trim();
  return id ? `${base} (${id})` : base;
}
