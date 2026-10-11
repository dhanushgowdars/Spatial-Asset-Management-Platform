/** Bounded DOM presentation for already-fetched measurement rows. Not API pagination. */
export const MEASUREMENT_PAGE_SIZE = 50;

export function paginateMeasurements(rows, requestedPage, pageSize = MEASUREMENT_PAGE_SIZE) {
  if (!Array.isArray(rows)) return { rows: [], total: 0, page: 1, pageCount: 1, start: 0, end: 0 };
  const size = Number.isSafeInteger(pageSize) && pageSize > 0 && pageSize <= 100 ? pageSize : MEASUREMENT_PAGE_SIZE;
  const total = rows.length;
  const pageCount = Math.max(1, Math.ceil(total / size));
  const wanted = Number.isSafeInteger(requestedPage) ? requestedPage : 1;
  const page = Math.min(pageCount, Math.max(1, wanted));
  const offset = (page - 1) * size;
  return {
    rows: rows.slice(offset, offset + size),
    total, page, pageCount,
    start: total === 0 ? 0 : offset + 1,
    end: Math.min(total, offset + size),
  };
}
