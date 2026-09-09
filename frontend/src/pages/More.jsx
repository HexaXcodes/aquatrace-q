import React from 'react';
import { Link } from 'react-router-dom';
import SubHeader from '../components/SubHeader';

// See Header.jsx's comment: the design's nav has room for exactly the 4
// mockup screens, so this menu is how these four pre-existing pages stay
// reachable.
const LINKS = [
  { to: '/', icon: 'layers', label: 'Mission Overview', desc: 'Survey-wide risk breakdown' },
  { to: '/map', icon: 'map', label: 'Priority Map', desc: 'Geolocated targets by risk level' },
  { to: '/planner', icon: 'alt_route', label: 'Mission Planner', desc: 'Real nearest-neighbor ROV route' },
  { to: '/report', icon: 'file_download', label: 'Survey Report', desc: 'CSV / JSON export' },
];

const More = () => (
  <>
    <SubHeader pageLabel="More" title="More Consoles" />
    <div className="max-w-max-content-width mx-auto px-margin-desktop py-space-xl flex flex-col gap-space-lg">
      <p className="font-body-md text-body-md text-on-surface-variant">
        Survey-wide views not part of the primary Ingest → Pipeline → Triage flow.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-gutter-desktop">
        {LINKS.map((link) => (
          <Link
            key={link.to}
            to={link.to}
            className="flex items-center gap-space-md bg-surface-container rounded-DEFAULT p-space-lg shadow-md hover:bg-surface-container-high transition-colors"
          >
            <div className="w-12 h-12 rounded-full bg-surface-container-high flex items-center justify-center text-primary-container shrink-0">
              <span className="material-symbols-outlined text-[22px]">{link.icon}</span>
            </div>
            <div className="flex flex-col min-w-0">
              <span className="font-headline-sm text-headline-sm text-on-surface">{link.label}</span>
              <span className="font-body-sm text-body-sm text-on-surface-variant truncate">{link.desc}</span>
            </div>
            <span className="material-symbols-outlined text-outline text-[18px] ml-auto shrink-0">chevron_right</span>
          </Link>
        ))}
      </div>
    </div>
  </>
);

export default More;
