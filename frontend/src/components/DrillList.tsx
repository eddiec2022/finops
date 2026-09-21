export interface DrillListItem {
  key: string;
  primary: string;
  secondary?: string;
  onClick: () => void;
}

interface DrillListProps {
  title: string;
  items: DrillListItem[];
  emptyMessage: string;
}

export function DrillList({ title, items, emptyMessage }: DrillListProps) {
  return (
    <div className="rounded-xl bg-white p-6 shadow-sm">
      <h2 className="mb-3 text-sm font-medium text-stone-700">{title}</h2>

      {items.length === 0 ? (
        <p className="text-sm text-stone-400">{emptyMessage}</p>
      ) : (
        <div className="divide-y divide-stone-100">
          {items.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={item.onClick}
              className="flex w-full items-center justify-between gap-4 rounded-lg px-2 py-3 text-left transition-colors hover:bg-brand-light"
            >
              <span className="truncate text-sm font-medium text-stone-800">{item.primary}</span>
              <span className="flex shrink-0 items-center gap-2 text-xs text-stone-400">
                {item.secondary}
                <span aria-hidden="true">&rarr;</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
