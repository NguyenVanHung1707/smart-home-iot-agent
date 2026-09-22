import type { ReactNode } from "react";

export function SectionHeading({ eyebrow, title, aside }: { eyebrow?: string; title: string; aside?: ReactNode }) {
  return (
    <div className="hm-section-heading">
      <div>
        {eyebrow ? <p className="hm-eyebrow">{eyebrow}</p> : null}
        <h2 className="hm-page-title">{title}</h2>
      </div>
      {aside}
    </div>
  );
}
