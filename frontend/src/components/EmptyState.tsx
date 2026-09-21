interface EmptyStateProps {
  title?: string;
  description?: string;
}

export function EmptyState({
  title = "Not enough usage history yet",
  description = "This subscription hasn't synced enough days of cost data to show a spend trend or forecast. Check back once more usage history has come in.",
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl bg-brand-light px-8 py-16 text-center">
      <p className="text-lg font-medium text-brand-dark">{title}</p>
      <p className="max-w-sm text-sm text-brand-darker">{description}</p>
    </div>
  );
}
