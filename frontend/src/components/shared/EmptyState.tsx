export function EmptyState({ title, text }: { title: string; text: string }) {
  return (
    <section className="hm-empty">
      <strong>{title}</strong>
      <p>{text}</p>
    </section>
  );
}
