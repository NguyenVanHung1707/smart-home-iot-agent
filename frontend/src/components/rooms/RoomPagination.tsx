import { Icon } from "../shared/Icon";

export function RoomPagination({
  page,
  totalPages,
  onChange,
}: {
  page: number;
  totalPages: number;
  onChange: (page: number) => void;
}) {
  if (totalPages <= 1) return null;
  return (
    <nav className="hm-room-pagination" aria-label="Phân trang phòng">
      <button
        type="button"
        disabled={page === 0}
        onClick={() => onChange(page - 1)}
        aria-label="Trang phòng trước"
      >
        <Icon name="arrowLeft" />
      </button>
      <span aria-live="polite" aria-label={`Trang ${page + 1} trên ${totalPages}`}>
        {page + 1} / {totalPages}
      </span>
      <button
        type="button"
        disabled={page >= totalPages - 1}
        onClick={() => onChange(page + 1)}
        aria-label="Trang phòng sau"
      >
        <Icon name="arrowRight" />
      </button>
    </nav>
  );
}
