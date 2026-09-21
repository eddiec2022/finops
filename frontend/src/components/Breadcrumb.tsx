export interface BreadcrumbSegment {
  label: string;
  onClick?: () => void;
}

export function Breadcrumb({ segments }: { segments: BreadcrumbSegment[] }) {
  return (
    <nav className="mb-6 flex flex-wrap items-center gap-1.5 text-sm">
      {segments.map((segment, index) => (
        <span key={`${index}-${segment.label}`} className="flex items-center gap-1.5">
          {index > 0 && (
            <span aria-hidden="true" className="text-stone-300">
              /
            </span>
          )}
          {segment.onClick ? (
            <button type="button" onClick={segment.onClick} className="text-brand hover:underline">
              {segment.label}
            </button>
          ) : (
            <span className="font-medium text-stone-700">{segment.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}
