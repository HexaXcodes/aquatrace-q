import React from 'react';
import { NavLink } from 'react-router-dom';

// Persistent top nav, shared by Landing and the console Layout -- matches
// the v2 design's header exactly (logo, pill nav group, status chip,
// action button, avatar). The "Overview" tab is the marketing/landing page
// per the design README ("01-landing.html -- marketing/entry screen
// ('Overview' in the nav)"); the app's own real survey dashboard lives at
// "/" and is reached via the More menu, same as Priority Map/Mission
// Planner/Report -- see More.jsx for why those four have no dedicated nav
// slot (the design's nav has room for exactly the 4 mockup screens).
const TABS = [
  { to: '/welcome', label: 'Overview' },
  { to: '/sonar', label: 'Ingest & Metadata' },
  { to: '/pipeline', label: 'Acoustic Pipeline' },
  { to: '/triage', label: 'Triage Overlay' },
  { to: '/more', label: 'More' },
];

const pillClasses = ({ isActive }) =>
  `px-space-md py-space-xs rounded-full font-label-md text-label-md transition-all ${
    isActive ? 'bg-surface-container-high text-primary font-bold' : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high'
  }`;

const Header = ({ statusLabel = 'NO SURVEY', statusActive = false }) => {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-surface-container-lowest/90 backdrop-blur-xl border-b border-outline-variant/30 shadow-[0_1px_8px_rgba(0,0,0,0.4)]">
      <div className="h-16 max-w-max-content-width mx-auto px-margin-desktop flex items-center justify-between gap-space-md">
        <div className="flex items-center gap-space-sm shrink-0">
          <div className="w-8 h-8 rounded-full bg-surface-container-high flex items-center justify-center text-primary-container">
            <span className="material-symbols-outlined text-[20px]">waves</span>
          </div>
          <div className="flex items-center gap-space-xs">
            <span className="font-headline-sm text-headline-sm text-on-surface tracking-tight font-bold">ReefGuard-Q</span>
            <span className="hidden lg:inline-flex bg-primary/10 border border-primary/20 text-primary px-space-xs py-space-2xs rounded-full font-telemetry-sm text-telemetry-sm uppercase tracking-wider">
              Acoustic Survey AI
            </span>
          </div>
        </div>
        <nav className="hidden md:flex items-center gap-space-xs bg-surface-container-low/60 p-space-2xs rounded-full border border-outline-variant/20 overflow-x-auto">
          {TABS.map((tab) => (
            <NavLink key={tab.to} to={tab.to} className={pillClasses} end={tab.to === '/welcome'}>
              {tab.label}
            </NavLink>
          ))}
        </nav>
        <div className="flex items-center gap-space-md shrink-0">
          <div className="hidden lg:flex items-center gap-space-xs px-space-sm py-space-2xs rounded-full bg-surface-container-low border border-outline-variant/30">
            <span className={`w-2 h-2 rounded-full ${statusActive ? 'bg-primary animate-pulse' : 'bg-outline-variant'}`} />
            <span className={`font-telemetry-sm text-telemetry-sm uppercase font-medium ${statusActive ? 'text-primary' : 'text-on-surface-variant'}`}>
              {statusLabel}
            </span>
          </div>
          <NavLink
            to="/sonar"
            className="hidden sm:inline-flex items-center justify-center px-space-lg py-space-xs rounded-full bg-primary text-on-primary font-label-lg text-label-lg hover:bg-primary-fixed-dim hover:text-on-primary-fixed transition-all shadow-[0_0_16px_rgba(0,229,190,0.25)]"
          >
            New Survey
          </NavLink>
          <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center shrink-0">
            <span className="material-symbols-outlined text-on-primary text-[18px]">person</span>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
