import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import Login from "../pages/Login/Login";
import Register from "../pages/Register/Register";
import Dashboard from "../pages/Dashboard/Dashboard";
import Assets from "../pages/Assets/Assets";
import Map from "../pages/Map/Map";
import Settings from "../pages/Settings/Settings";
import Geospatial from "../pages/Geospatial/Geospatial";

import NotFound from "../pages/NotFound/NotFound";
import AppLayout from "../layouts/AppLayout";
import { getToken } from "../utils/storage";

const SpatialIntelligence = lazy(() => import("../pages/SpatialIntelligence/SpatialIntelligence"));
const GeoGuide = lazy(() => import("../pages/GeoGuide/GeoGuide"));

function ProtectedRoute({ children }) {
  return getToken() ? children : <Navigate to="/" replace />;
}

function PublicRoute({ children }) {
  return getToken() ? <Navigate to="/dashboard" replace /> : children;
}

function AppRoutes() {
  return (
    <Routes>
      {/* Public evaluation entrypoint; existing auth-protected app is unchanged. */}
      <Route path="/geospatial" element={<Geospatial />} />
      <Route path="/geospatial/quality" element={<Suspense fallback={<div role="status" className="sx-loading">Loading quality workspace…</div>}><SpatialIntelligence key="quality" mode="quality" /></Suspense>} />
      <Route path="/geospatial/compare" element={<Suspense fallback={<div role="status" className="sx-loading">Loading comparison workspace…</div>}><SpatialIntelligence key="compare" mode="compare" /></Suspense>} />
      <Route path="/geospatial/topology" element={<Suspense fallback={<div role="status" className="sx-loading">Loading topology workspace…</div>}><SpatialIntelligence key="topology" mode="topology" /></Suspense>} />
      <Route path="/geospatial/routes" element={<Suspense fallback={<div role="status" className="sx-loading">Loading route workspace…</div>}><SpatialIntelligence key="routes" mode="routes" /></Suspense>} />
      <Route path="/geospatial/guide" element={<Suspense fallback={<div role="status" className="sx-loading">Loading GeoInsight guide…</div>}><GeoGuide /></Suspense>} />
      <Route path="/geospatial/intelligence" element={<Navigate to="/geospatial/quality" replace />} />
      <Route path="/" element={<PublicRoute><Login /></PublicRoute>} />
      <Route path="/register" element={<PublicRoute><Register /></PublicRoute>} />
      <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/assets" element={<Assets />} />
        <Route path="/map" element={<Map />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}

export default AppRoutes;
