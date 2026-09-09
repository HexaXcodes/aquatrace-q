import React, { useEffect, useState } from 'react';
import { getPrioritySummary } from '../api';
import { useNavigate } from 'react-router-dom';
import { useSurvey } from '../context/SurveyContext';
import SubHeader from '../components/SubHeader';

const RISK_TILE = {
  CRITICAL: { bg: 'bg-error-container', text: 'text-on-error-container', icon: 'shield_moon', desc: 'Immediate verification needed' },
  HIGH: { bg: 'bg-tertiary-container/80', text: 'text-on-tertiary-container', icon: 'warning', desc: 'Elevated ecological risk' },
  MEDIUM: { bg: 'bg-surface-container-high', text: 'text-on-surface', icon: 'radar', desc: 'Queue for next survey' },
  LOW: { bg: 'bg-surface-container-low', text: 'text-on-surface', icon: 'check_circle', desc: 'Low risk, log only' },
};

const MissionOverview = () => {
  const { surveyId } = useSurvey();
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!surveyId) {
      setSummary(null);
      return;
    }
    setError(null);
    setSummary(null);
    getPrioritySummary(surveyId)
      .then(setSummary)
      .catch((err) => setError(err.message));
  }, [surveyId]);

  if (!surveyId) {
    return (
      <>
        <SubHeader pageLabel="Overview" title="Mission Overview" />
        <EmptyState text="No survey selected. Upload or select one from the header." />
      </>
    );
  }
  if (error) {
    return (
      <>
        <SubHeader pageLabel="Overview" title="Mission Overview" />
        <EmptyState text={error} tone="text-error" />
      </>
    );
  }
  if (!summary) {
    return (
      <>
        <SubHeader pageLabel="Overview" title="Mission Overview" />
        <EmptyState text="Loading mission overview..." />
      </>
    );
  }

  const { counts } = summary;

  return (
    <>
      <SubHeader
        pageLabel="Overview"
        title="Mission Overview"
        right={
          <button
            type="button"
            onClick={() => navigate('/map')}
            className="flex items-center gap-space-xs px-space-lg py-space-xs rounded-full bg-primary text-on-primary font-label-lg text-label-lg shadow-md hover:bg-primary-fixed-dim transition-all"
          >
            <span className="material-symbols-outlined text-[18px]">map</span>
            Priority Map
          </button>
        }
      />

      <div className="max-w-max-content-width mx-auto px-margin-desktop py-space-xl flex flex-col gap-space-xl">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-space-md">
          <StatTile label="TOTAL ANOMALIES" value={counts.total} />
          <StatTile
            label="SURVEY AREA"
            value={summary.surveyAreaSqKm != null ? summary.surveyAreaSqKm.toFixed(3) : 'N/A'}
            unit={summary.surveyAreaSqKm != null ? 'km²' : null}
            hint={summary.surveyAreaSqKm == null ? 'meters_per_pixel not set' : null}
          />
        </div>

        <div>
          <div className="flex items-center gap-space-xs px-space-2xs mb-space-md">
            <span className="material-symbols-outlined text-primary text-[18px]">query_stats</span>
            <h2 className="font-headline-md text-headline-md text-on-surface">Risk Breakdown</h2>
            <span className="font-telemetry-sm text-telemetry-sm text-on-surface-variant">(RiskScore.level)</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-space-md">
            {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((level) => {
              const t = RISK_TILE[level];
              return (
                <div key={level} className={`flex flex-col p-space-lg rounded-DEFAULT shadow-sm ${t.bg}`}>
                  <div className="flex items-start justify-between">
                    <div>
                      <div className={`font-label-lg text-label-lg font-bold ${t.text}`}>{level}</div>
                      <div className={`font-body-sm text-body-sm ${t.text} opacity-80`}>{t.desc}</div>
                    </div>
                    <span className={`material-symbols-outlined text-[22px] ${t.text}`}>{t.icon}</span>
                  </div>
                  <div className={`font-headline-lg text-headline-lg mt-space-sm ${t.text}`}>{counts[level]}</div>
                </div>
              );
            })}
          </div>
        </div>

        {counts.pending > 0 && (
          <div className="flex items-center justify-between bg-surface-container rounded-DEFAULT p-space-lg shadow-sm">
            <div className="flex items-center gap-space-xs">
              <span className="material-symbols-outlined text-on-surface-variant text-[18px]">hourglass_empty</span>
              <div className="flex flex-col">
                <span className="font-label-lg text-label-lg text-on-surface-variant font-bold">PENDING</span>
                <span className="font-body-sm text-body-sm text-on-surface-variant">Risk not yet scored</span>
              </div>
            </div>
            <span className="font-telemetry-lg text-telemetry-lg text-on-surface">{counts.pending}</span>
          </div>
        )}
      </div>
    </>
  );
};

const StatTile = ({ label, value, unit, hint }) => (
  <div className="p-space-lg bg-surface-container-low rounded-DEFAULT flex flex-col justify-between shadow-sm">
    <span className="font-label-md text-label-md text-on-surface-variant mb-space-xs uppercase">{label}</span>
    <div className="font-headline-lg text-headline-lg text-primary">
      {value} {unit && <span className="font-body-md text-body-md text-on-surface-variant">{unit}</span>}
    </div>
    {hint && <span className="font-body-sm text-body-sm text-on-surface-variant mt-1">{hint}</span>}
  </div>
);

const EmptyState = ({ text, tone }) => (
  <div className="max-w-max-content-width mx-auto px-margin-desktop py-space-2xl flex flex-col items-center justify-center gap-space-sm text-center">
    <span className={`material-symbols-outlined text-[36px] ${tone || 'text-on-surface-variant'}`}>layers</span>
    <p className={`font-body-sm text-body-sm ${tone || 'text-on-surface-variant'}`}>{text}</p>
  </div>
);

export default MissionOverview;
