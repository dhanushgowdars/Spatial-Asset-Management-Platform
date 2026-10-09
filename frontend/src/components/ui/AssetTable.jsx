const formatCoordinates = (value) => (Number.isFinite(Number(value)) ? Number(value).toFixed(5) : "—");

const formatDate = (value) => {
  if (!value) return "—";

  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
};

const getStatusBadge = (status) => {
  const statusColors = {
    ONLINE: "badge-online",
    OFFLINE: "badge-offline",
    MAINTENANCE: "badge-maintenance",
    RETIRED: "badge-retired",
  };
  return statusColors[status] || "badge-default";
};

function AssetTable({ assets, isLoading, error, onRetry, searchTerm, onEdit, onDelete }) {
  if (isLoading) {
    return (
      <div className="asset-table-wrap" aria-label="Loading assets" aria-busy="true">
        <table className="asset-table asset-table-skeleton">
          <thead><tr><th>Serial</th><th>Name</th><th>Type</th><th>Status</th><th>Description</th><th>Latitude</th><th>Longitude</th><th>Created</th><th>Actions</th></tr></thead>
          <tbody>
            {[0, 1, 2, 3, 4].map((row) => (
              <tr key={row}><td><span /></td><td><span /></td><td><span /></td><td><span /></td><td><span /></td><td><span /></td><td><span /></td><td><span /></td><td><span /></td></tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (error) {
    return (
      <div className="asset-state asset-error" role="alert">
        <strong>Unable to load assets</strong>
        <p>{error}</p>
        <button type="button" onClick={onRetry}>Try again</button>
      </div>
    );
  }

  if (!assets.length) {
    return (
      <div className="asset-state">
        <strong>{searchTerm ? "No matching assets" : "No assets yet"}</strong>
        <p>{searchTerm ? "Try a different search term." : "Assets created for your account will appear here."}</p>
      </div>
    );
  }

  return (
    <div className="asset-table-wrap">
      <table className="asset-table">
        <thead>
          <tr><th>Serial</th><th>Name</th><th>Type</th><th>Status</th><th>Description</th><th>Latitude</th><th>Longitude</th><th>Created</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {assets.map((asset) => (
            <tr key={asset.id}>
              <td data-label="Serial"><code>{asset.serial_number}</code></td>
              <td data-label="Name"><strong>{asset.name}</strong></td>
              <td data-label="Type"><span className="asset-type-badge">{asset.asset_type}</span></td>
              <td data-label="Status"><span className={`status-badge ${getStatusBadge(asset.status)}`}>{asset.status}</span></td>
              <td data-label="Description">{asset.description || "—"}</td>
              <td data-label="Latitude">{formatCoordinates(asset.latitude)}</td>
              <td data-label="Longitude">{formatCoordinates(asset.longitude)}</td>
              <td data-label="Created">{formatDate(asset.created_at)}</td>
              <td data-label="Actions">
                <div className="asset-actions">
                  <button
                    className="asset-action-btn"
                    type="button"
                    onClick={() => onEdit(asset)}
                    aria-label={`Edit ${asset.name}`}
                  >
                    <svg aria-hidden="true" viewBox="0 0 24 24">
                      <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
                      <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
                    </svg>
                    Edit
                  </button>
                  <button
                    className="asset-action-btn asset-action-btn-delete"
                    type="button"
                    onClick={() => onDelete(asset)}
                    aria-label={`Delete ${asset.name}`}
                  >
                    <svg aria-hidden="true" viewBox="0 0 24 24">
                      <path d="M3 6h18" />
                      <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                      <path d="M10 11v6" />
                      <path d="M14 11v6" />
                    </svg>
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default AssetTable;
