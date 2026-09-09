import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useSurvey } from '../context/SurveyContext';
import SubHeader from '../components/SubHeader';
import { buildMission, getSurvey, getSurveyTargets } from '../api';

const RISK_BADGE = {
  CRITICAL: 'bg-error-container text-on-error-container',
  HIGH: 'bg-tertiary-container/80 text-on-tertiary-container',
  MEDIUM: 'bg-surface-container-highest text-primary',
  LOW: 'bg-surface-container-low text-on-surface-variant',
};

const MissionPlanner = () => {
  const { surveyId } = useSurvey();
  const navigate = useNavigate();
  const location = useLocation();

  const [targetsById, setTargetsById] = useState({});
  const [startLatitude, setStartLatitude] = useState('');
  const [startLongitude, setStartLongitude] = useState('');
  // A mission can arrive pre-built via router state (Triage Overlay's "Build
  // Verification Mission" button already calls the real endpoint before
  // navigating here, so this screen doesn't rebuild it redundantly).
  const [mission, setMission] = useState(location.state?.mission ?? null);
  const [building, setBuilding] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!location.state?.mission) setMission(null);
    setError(null);
    if (!surveyId) {
      setTargetsById({});
      return;
    }
    getSurvey(surveyId).then((s) => {
      if (s.origin_latitude != null) setStartLatitude(String(s.origin_latitude));
      if (s.origin_longitude != null) setStartLongitude(String(s.origin_longitude));
    });
    getSurveyTargets(surveyId).then((rows) => {
      const map = {};
      for (const row of rows) map[row.target_id] = row;
      setTargetsById(map);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [surveyId]);

  const handleBuild = async (event) => {
    event.preventDefault();
    if (!startLatitude || !startLongitude) return;
    setBuilding(true);
    setError(null);
    try {
      const built = await buildMission(surveyId, {
        startLatitude: Number(startLatitude),
        startLongitude: Number(startLongitude),
      });
      setMission(built);
    } catch (err) {
      setError(err.message);
    } finally {
      setBuilding(false);
    }
  };

  if (!surveyId) {
    return (
      <>
        <SubHeader pageLabel="Mission Planner" title="Mission Planner" />
        <EmptyState text="No survey selected. Upload or select one from the header." />
      </>
    );
  }

  return (
    <>
      <SubHeader pageLabel="Mission Planner" title="Mission Planner" />
      <div className="max-w-max-content-width mx-auto px-margin-desktop py-space-xl flex flex-col gap-space-lg">
        <p className="font-body-md text-body-md text-on-surface-variant">
          Real nearest-neighbor ROV verification route (POST /surveys/&#123;id&#125;/missions)
        </p>

        <form onSubmit={handleBuild} className="bg-surface-container rounded-DEFAULT p-space-lg shadow-md flex flex-col md:flex-row items-end gap-space-md">
          <Field label="Vehicle Start Latitude" className="flex-1">
            <input
              required
              type="number"
              step="any"
              value={startLatitude}
              onChange={(e) => setStartLatitude(e.target.value)}
              className="h-11 px-space-md bg-surface-container-lowest rounded-full border border-outline-variant/30 text-on-surface font-telemetry-md w-full outline-none focus:border-primary"
            />
          </Field>
          <Field label="Vehicle Start Longitude" className="flex-1">
            <input
              required
              type="number"
              step="any"
              value={startLongitude}
              onChange={(e) => setStartLongitude(e.target.value)}
              className="h-11 px-space-md bg-surface-container-lowest rounded-full border border-outline-variant/30 text-on-surface font-telemetry-md w-full outline-none focus:border-primary"
            />
          </Field>
          <button
            type="submit"
            disabled={building}
            className="h-11 px-space-xl rounded-full bg-primary text-on-primary font-label-lg text-label-lg font-bold shadow-[0_0_16px_rgba(0,229,190,0.25)] disabled:opacity-50 transition-all flex items-center gap-space-xs shrink-0"
          >
            <span className="material-symbols-outlined text-[18px]">navigation</span>
            {building ? 'Building...' : mission ? 'Rebuild Route' : 'Build Route'}
          </button>
        </form>

        {error && (
          <div className="bg-error-container text-on-error-container rounded-DEFAULT p-space-md font-body-sm text-body-sm">{error}</div>
        )}

        {!mission ? (
          <EmptyState text="No route built yet for this survey -- set a start position above." inline />
        ) : (
          <>
            <div className="flex items-center gap-space-lg flex-wrap font-telemetry-sm text-telemetry-sm text-on-surface-variant bg-surface-container-low rounded-full px-space-lg py-space-sm w-fit">
              <span>
                Total distance: <strong className="text-on-surface">{mission.total_distance_m?.toFixed(0) ?? 'N/A'} m</strong>
              </span>
              <span>
                Estimated duration:{' '}
                <strong className="text-on-surface">
                  {mission.estimated_duration_s ? `${Math.round(mission.estimated_duration_s / 60)} min` : 'N/A'}
                </strong>
              </span>
              <span>
                Stops: <strong className="text-on-surface">{mission.targets.length}</strong>
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-gutter-desktop">
              {mission.targets.map((stop) => {
                const row = targetsById[stop.target_id];
                const riskLevel = row?.risk_level;
                return (
                  <button
                    key={stop.target_id}
                    type="button"
                    onClick={() => navigate(`/target/${stop.target_id}`)}
                    className="text-left bg-surface-container rounded-DEFAULT p-space-lg shadow-md flex items-center gap-space-md hover:bg-surface-container-high transition-colors"
                  >
                    <div className="w-10 h-10 rounded-full bg-surface-container-high flex items-center justify-center font-telemetry-md text-telemetry-md text-primary font-bold shrink-0">
                      {stop.sequence}
                    </div>
                    <div className="flex flex-col min-w-0 flex-1">
                      <span className="font-headline-sm text-headline-sm text-on-surface truncate">
                        {(row?.debris_subclass || row?.classification || 'unknown').replace(/_/g, ' ')}
                      </span>
                      <span className="font-telemetry-sm text-telemetry-sm text-on-surface-variant">
                        {row?.priority_action || 'PENDING'} //{' '}
                        {stop.distance_from_previous_m != null ? `${stop.distance_from_previous_m.toFixed(0)}m leg` : '--'} //{' '}
                        {stop.cumulative_distance_m != null ? `${stop.cumulative_distance_m.toFixed(0)}m total` : '--'}
                      </span>
                    </div>
                    <span
                      className={`px-space-md py-space-2xs rounded-full font-telemetry-sm text-telemetry-sm font-bold shrink-0 ${
                        riskLevel ? RISK_BADGE[riskLevel] : 'bg-surface-container-low text-on-surface-variant'
                      }`}
                    >
                      {riskLevel || 'PENDING'}
                    </span>
                  </button>
                );
              })}
            </div>
          </>
        )}
      </div>
    </>
  );
};

const Field = ({ label, children, className = '' }) => (
  <label className={`flex flex-col gap-space-2xs ${className}`}>
    <span className="font-label-md text-label-md text-on-surface-variant">{label}</span>
    {children}
  </label>
);

const EmptyState = ({ text, tone, inline }) => (
  <div className={`flex flex-col items-center justify-center gap-space-sm text-center ${inline ? 'py-space-xl' : 'max-w-max-content-width mx-auto px-margin-desktop py-space-2xl'}`}>
    <span className={`material-symbols-outlined text-[36px] ${tone || 'text-on-surface-variant'}`}>alt_route</span>
    <p className={`font-body-sm text-body-sm ${tone || 'text-on-surface-variant'}`}>{text}</p>
  </div>
);

export default MissionPlanner;
