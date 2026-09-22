import type { ReactNode } from "react";

export function PageShell({ children, home = false }: { children: ReactNode; home?: boolean }) {
  return <div className={`hm-main ${home ? "hm-main-home" : ""}`}>{children}</div>;
}
