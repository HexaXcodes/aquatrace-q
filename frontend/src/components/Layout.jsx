import React from 'react';
import { Outlet } from 'react-router-dom';
import { useSurvey } from '../context/SurveyContext';
import Header from './Header';

const Layout = () => {
  const { surveyId, surveys } = useSurvey();
  const currentSurvey = surveys.find((s) => s.id === surveyId);

  return (
    <div className="min-h-screen bg-surface-container-lowest text-on-surface antialiased">
      <Header statusLabel={currentSurvey ? currentSurvey.status : 'NO SURVEY'} statusActive={!!currentSurvey} />
      <main className="w-full pt-16 bg-surface-container-lowest min-h-screen">
        <Outlet />
      </main>
      <footer className="w-full bg-surface-container-low/40 border-t border-outline-variant/20 py-space-xl">
        <div className="max-w-max-content-width mx-auto px-margin-desktop flex flex-col md:flex-row items-center justify-between gap-space-md">
          <span className="font-headline-sm text-headline-sm text-on-surface-variant">ReefGuard-Q</span>
          <span className="font-telemetry-sm text-telemetry-sm text-on-surface-variant">
            © 2026 ReefGuard-Q. Autonomous Oceanic Acoustic Intelligence.
          </span>
        </div>
      </footer>
    </div>
  );
};

export default Layout;
