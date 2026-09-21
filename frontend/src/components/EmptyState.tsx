export function EmptyState() {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl bg-brand-light px-8 py-16 text-center">
      <p className="text-lg font-medium text-brand-dark">Not enough usage history yet</p>
      <p className="max-w-sm text-sm text-brand-darker">
        This subscription hasn't synced enough days of cost data to show a spend trend or
        forecast. Check back once more usage history has come in.
      </p>
    </div>
  );
}
