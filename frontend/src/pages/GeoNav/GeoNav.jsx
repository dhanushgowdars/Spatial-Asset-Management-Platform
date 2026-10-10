import { NavLink, Link } from 'react-router-dom';
import './GeoNav.css';
const items = [
  { to:'/geospatial', label:'Measure', icon:'measure' },
  { to:'/geospatial/quality', label:'Survey quality', icon:'quality' },
  { to:'/geospatial/compare', label:'Compare surveys', icon:'compare' },
  { to:'/geospatial/topology', label:'Topology', icon:'topology' },
  { to:'/geospatial/routes', label:'Routes & zones', icon:'routes' },
  { to:'/geospatial/guide', label:'About & guide', icon:'guide' },
];
function NavIcon({ icon }) {
  return <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    {icon==='measure'&&<><path d="M4 4h16v16H4z"/><path d="M8 4v5m4-5v3m4-3v5M4 12h5"/></>}
    {icon==='quality'&&<><path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7l8-4z"/><path d="m8.5 12 2.4 2.4 4.7-5"/></>}
    {icon==='compare'&&<><path d="M4 4h7v7H4zM13 13h7v7h-7z"/><path d="M13 4h7v7h-7zM4 13h7v7H4z"/></>}
    {icon==='topology'&&<><path d="M4 5h9v9H4zM10 10h10v10H10z"/><path d="M13 10v4h-3"/></>}
    {icon==='routes'&&<><circle cx="5" cy="18" r="2"/><circle cx="19" cy="6" r="2"/><path d="M7 18h5a4 4 0 0 0 0-8h-1a4 4 0 0 1 0-8h6"/></>}
    {icon==='guide'&&<><path d="M12 6a6 6 0 1 0 6 6c0-2.3-1-3.7-2.9-4.8"/><path d="M9.8 9.5a2.4 2.4 0 0 1 4.7.7c0 1.8-2.5 2.2-2.5 4"/><path d="M12 17.5h.01"/></>}
  </svg>;
}
export default function GeoNav() {
  return <header className="gn-shell">
    <div className="gn-inner">
      <Link className="gn-logo" to="/geospatial" aria-label="GeoInsight measurement workspace">
        <span className="gn-logo-mark" aria-hidden="true"><svg viewBox="0 0 32 32" width="27" height="27" fill="none"><path d="M16 3 29 10 16 17 3 10 16 3Z" stroke="white" strokeWidth="2" strokeLinejoin="round"/><path d="M3 16 16 23l13-7M3 22l13 7 13-7" stroke="#9de4d5" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg></span>
        <span className="gn-logo-text"><span className="gn-logo-name">Geo<strong>Insight</strong></span><small>GEOSPATIAL INTELLIGENCE</small></span>
      </Link>
      <nav className="gn-links" aria-label="GeoInsight workspace navigation">
        {items.map(item=><NavLink key={item.to} to={item.to} end className={({isActive})=>`gn-link${isActive?' is-active':''}`}><NavIcon icon={item.icon}/><span>{item.label}</span></NavLink>)}
      </nav>
      <a className="gn-api" href="/docs" target="_blank" rel="noreferrer"><span>API docs</span><span aria-hidden="true">↗</span></a>
    </div>
  </header>;
}
