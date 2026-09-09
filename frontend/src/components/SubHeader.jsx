import React from 'react';
import { useSurvey } from '../context/SurveyContext';

// Per-page breadcrumb bar, matching the "Sub-Header / Mission Breadcrumbs
// Bar" pattern from the v2 mockups (e.g. "Mission / Pacific-Transect-04 /
// Ingest"). The mockup's middle breadcrumb segment was a hardcoded example
// survey name -- here it's a real, functional survey selector, since this
// app actually needs one (repurposing the mockup's visual slot the same
// way the mobile round repurposed its header breadcrumb).
const SubHeader = ({ pageLabel, title, right }) => {
  const { surveyId, surveys, loadingSurveys, selectSurvey } = useSurvey();

  return (
    <section className="w-full bg-surface-container-low/80 backdrop-blur-md">
      <div className="max-w-max-content-width mx-auto px-margin-desktop py-space-md flex flex-wrap items-center justify-between gap-space-md">
        <div className="flex flex-col gap-space-2xs min-w-0">
          <div className="flex items-center gap-space-xs font-telemetry-sm text-telemetry-sm text-on-surface-variant">
            <span>Mission</span>
            <span className="text-outline">/</span>
            <select
              value={surveyId || ''}
              onChange={(e) => selectSurvey(e.target.value || null)}
              disabled={loadingSurveys || surveys.length === 0}
              className="bg-transparent text-secondary-fixed-dim font-telemetry-sm text-telemetry-sm border-none outline-none cursor-pointer max-w-[220px]"
            >
              <option value="" className="bg-surface-container text-on-surface-variant">
                {loadingSurveys ? 'Loading...' : surveys.length === 0 ? 'No surveys yet' : 'Select survey'}
              </option>
              {surveys.map((survey) => (
                <option key={survey.id} value={survey.id} className="bg-surface-container text-on-surface">
                  {survey.name}
                </option>
              ))}
            </select>
            <span className="text-outline">/</span>
            <span className="text-on-surface font-medium">{pageLabel}</span>
          </div>
          <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight">{title}</h1>
        </div>
        {right && <div className="flex items-center gap-space-sm flex-wrap">{right}</div>}
      </div>
    </section>
  );
};

export default SubHeader;
