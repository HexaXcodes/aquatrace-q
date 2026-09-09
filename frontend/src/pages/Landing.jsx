import React from 'react';
import { useNavigate } from 'react-router-dom';
import Header from '../components/Header';

// Marketing/entry screen, matching 01-landing.html. The capability cards
// and hero copy are illustrative launch-page marketing copy (no backend
// field claims made), consistent with the design README's own framing --
// no fabricated stats/telemetry/hardware-affiliation language, matching
// what the README's audit confirmed was already cleaned from this screen.
const CAPABILITIES = [
  { icon: 'explore', title: 'Detect', body: 'Real trained segmentation model isolates acoustic anomalies from side-scan sonar imagery.', tag: 'E004 Compact U-Net' },
  { icon: 'hub', title: 'Classify', body: 'Classical and quantum-kernel classifiers assign a debris subclass to every detected target.', tag: 'Classical + QSVC' },
  { icon: 'layers', title: 'Contextualize', body: 'Geodesic geolocation plus reef and marine-protected-area proximity, where a GIS dataset is configured.', tag: 'WGS84 geodesic' },
  { icon: 'shield', title: 'Prioritize', body: 'Transparent, weighted risk and priority scoring recommends which targets need verification first.', tag: 'Risk + priority engine' },
];

const Landing = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-surface-container-lowest text-on-surface antialiased">
      <Header />
      <main className="w-full pt-16 bg-surface-container-lowest min-h-screen">
        <section className="relative w-full overflow-hidden -mt-16 pt-40 pb-28 flex items-center justify-center min-h-[600px]">
          <div className="absolute inset-0 z-0">
            <div className="w-full h-full bg-gradient-to-br from-surface-container-low via-surface-container-lowest to-surface-container-lowest" />
            <div className="absolute inset-0 opacity-20" style={{ backgroundImage: 'linear-gradient(90deg, #6fffdb 1px, transparent 1px), linear-gradient(#6fffdb 1px, transparent 1px)', backgroundSize: '48px 48px' }} />
            <div className="absolute inset-0 bg-gradient-to-b from-surface-container-lowest via-surface-container-lowest/70 to-surface-container-lowest" />
          </div>
          <div className="relative z-10 max-w-max-content-width mx-auto px-margin-desktop w-full flex flex-col items-center text-center">
            <div className="inline-flex items-center gap-space-xs px-space-md py-space-2xs rounded-full bg-surface-container-high/70 backdrop-blur-md mb-space-lg shadow-sm">
              <span className="w-2 h-2 rounded-full bg-primary-container animate-ping" />
              <span className="w-1.5 h-1.5 rounded-full bg-primary-container -ml-space-sm" />
              <span className="font-telemetry-sm text-telemetry-sm text-primary uppercase tracking-widest font-semibold">
                Autonomous Oceanic Surveillance
              </span>
            </div>
            <h1 className="font-display-xl text-display-xl-mobile md:text-display-xl text-on-surface max-w-4xl tracking-tight leading-tight">
              AI-Powered <span className="text-primary-container italic font-normal">Marine Debris</span> Detection
            </h1>
            <p className="mt-space-lg font-body-lg text-body-lg text-on-surface-variant max-w-2xl leading-relaxed">
              Real-time acoustic sonar analysis and autonomous ghost gear triage for ocean conservation, running
              against the actual AquaTrace-Q backend.
            </p>
            <div className="mt-space-2xl flex flex-wrap items-center justify-center gap-space-md">
              <button
                type="button"
                onClick={() => navigate('/sonar')}
                className="inline-flex items-center gap-space-xs px-space-xl py-space-sm rounded-full bg-primary-container text-on-primary font-label-lg text-label-lg transition-all duration-200 transform hover:-translate-y-0.5 hover:shadow-[0_0_28px_rgba(0,229,190,0.45)]"
              >
                <span className="material-symbols-outlined text-[20px]">radar</span>
                <span>Start Survey</span>
              </button>
              <button
                type="button"
                onClick={() => navigate('/more')}
                className="inline-flex items-center gap-space-xs px-space-xl py-space-sm rounded-full bg-surface-container-high/60 backdrop-blur-md text-on-surface hover:text-primary hover:bg-surface-container-highest transition-all duration-200"
              >
                <span className="material-symbols-outlined text-[20px]">play_circle</span>
                <span>View Existing Surveys</span>
              </button>
            </div>
            <div className="mt-space-3xl flex items-center justify-center gap-space-2xl text-on-surface-variant/80">
              <div className="flex items-center gap-space-xs">
                <span className="material-symbols-outlined text-primary-container text-[18px]">waves</span>
                <span className="font-telemetry-sm text-telemetry-sm">Sub-surface Sonar Analysis</span>
              </div>
              <div className="w-1 h-1 rounded-full bg-outline-variant" />
              <div className="flex items-center gap-space-xs">
                <span className="material-symbols-outlined text-primary-container text-[18px]">radar</span>
                <span className="font-telemetry-sm text-telemetry-sm">Acoustic Target Triage</span>
              </div>
            </div>
          </div>
        </section>

        <section className="w-full py-space-3xl bg-surface-container-lowest relative z-20">
          <div className="max-w-max-content-width mx-auto px-margin-desktop">
            <div className="flex flex-col items-center text-center mb-space-3xl">
              <div className="font-telemetry-sm text-telemetry-sm uppercase tracking-widest text-primary font-medium mb-space-xs">
                Architected for Conservation Fleets
              </div>
              <h2 className="font-headline-lg text-headline-lg-mobile md:text-headline-lg text-on-surface font-semibold">
                Core Capabilities
              </h2>
              <div className="w-12 h-0.5 bg-primary-container/40 rounded-full mt-space-md" />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-gutter-desktop">
              {CAPABILITIES.map((c) => (
                <div
                  key={c.title}
                  className="group flex flex-col p-space-xl rounded-DEFAULT bg-surface-container-low hover:bg-surface-container transition-all duration-300 transform hover:-translate-y-1 shadow-md"
                >
                  <div className="w-12 h-12 rounded-full bg-surface-container-high flex items-center justify-center text-primary-container mb-space-lg group-hover:bg-primary-container group-hover:text-on-primary transition-colors duration-300">
                    <span className="material-symbols-outlined text-[24px]">{c.icon}</span>
                  </div>
                  <div className="font-headline-sm text-headline-sm text-on-surface mb-space-xs group-hover:text-primary transition-colors">
                    {c.title}
                  </div>
                  <p className="font-body-sm text-body-sm text-on-surface-variant leading-relaxed">{c.body}</p>
                  <div className="mt-space-lg pt-space-md flex items-center gap-space-xs text-primary/80 font-telemetry-sm text-telemetry-sm opacity-0 group-hover:opacity-100 transition-opacity">
                    <span>{c.tag}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="w-full py-space-2xl bg-surface-container-lowest border-t border-outline-variant/10">
          <div className="max-w-max-content-width mx-auto px-margin-desktop flex flex-col md:flex-row items-center justify-between gap-space-lg p-space-xl rounded-DEFAULT bg-gradient-to-r from-surface-container-low via-surface-container to-surface-container-low">
            <div className="flex flex-col">
              <span className="font-headline-sm text-headline-sm text-on-surface font-medium">
                Ready to run a real survey through ReefGuard-Q?
              </span>
              <span className="font-body-sm text-body-sm text-on-surface-variant">Accessible via web console.</span>
            </div>
            <button
              type="button"
              onClick={() => navigate('/sonar')}
              className="w-full md:w-auto text-center px-space-lg py-space-xs rounded-full bg-primary text-on-primary font-label-lg text-label-lg hover:bg-primary-fixed-dim transition-all shadow-md"
            >
              Launch Console
            </button>
          </div>
        </section>
      </main>
      <footer className="w-full bg-surface-container-low/40 border-t border-outline-variant/20 py-space-xl">
        <div className="max-w-max-content-width mx-auto px-margin-desktop flex flex-col md:flex-row items-center justify-between gap-space-md">
          <span className="font-headline-sm text-headline-sm text-on-surface font-semibold tracking-tight">ReefGuard-Q</span>
          <span className="font-telemetry-sm text-telemetry-sm text-on-surface-variant">
            © 2026 ReefGuard-Q. Autonomous Oceanic Acoustic Intelligence. All rights reserved.
          </span>
        </div>
      </footer>
    </div>
  );
};

export default Landing;
