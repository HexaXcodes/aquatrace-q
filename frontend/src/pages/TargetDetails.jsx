import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import SubHeader from '../components/SubHeader';
import { getTargetDetail, reprocessSurveyForTarget } from '../api';

const formatLabel = (value) =>
  value ? value.split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ') : 'Unclassified';

const RISK_BADGE = {
  CRITICAL: 'bg-error-container text-on-error-container',
  HIGH: 'bg-tertiary-container/80 text-on-tertiary-container',
  MEDIUM: 'bg-surface-container-highest text-primary',
  LOW: 'bg-primary/10 text-primary',
};

const TargetDetails = () => {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [reprocessing, setReprocessing] = useState(false);
  const [stageLog, setStageLog] = useState([]);

  const load = () => {
    setError(null);
    getTargetDetail(id)
      .then(setData)
      .catch((err) => setError(err.message));
  };

  useEffect(() => {
    setData(null);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const handleReprocess = async () => {
    setReprocessing(true);
    setStageLog([]);
    try {
      await reprocessSurveyForTarget(id, {}, (job) => setStageLog(job.stage_log));
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setReprocessing(false);
    }
  };

  if (error) {
    return (
      <>
        <SubHeader pageLabel="Target Detail" title="Target Detail" />
        <EmptyState text={error} tone="text-error" />
      </>
    );
  }
  if (!data) {
    return (
      <>
        <SubHeader pageLabel="Target Detail" title="Target Detail" />
        <EmptyState text="Loading target..." />
      </>
    );
  }

  const { target, risk, priority, environment } = data;
  const riskLevel = risk?.level;
  const label = formatLabel(target.debris_subclass || target.classification);

  return (
    <>
      <SubHeader
        pageLabel="Target Detail"
        title={label}
        right={
          <>
            <span className={`px-space-md py-space-2xs rounded-full font-label-md text-label-md font-bold uppercase ${riskLevel ? RISK_BADGE[riskLevel] : 'bg-surface-container text-on-surface-variant'}`}>
              {riskLevel ? `${riskLevel} risk` : 'Risk pending'}
            </span>
            {environment?.inside_mpa && (
              <span className="px-space-md py-space-2xs rounded-full font-label-md text-label-md font-bold bg-primary/10 text-primary">Inside MPA</span>
            )}
            {priority?.verification_required && (
              <span className="flex items-center gap-1 px-space-md py-space-2xs rounded-full bg-error-container text-on-error-container font-label-md text-label-md font-bold">
                <span className="material-symbols-outlined text-[15px]">warning</span>
                {priority.action}
              </span>
            )}
          </>
        }
      />

      <div className="max-w-max-content-width mx-auto px-margin-desktop py-space-xl grid grid-cols-1 lg:grid-cols-2 gap-gutter-desktop items-start">
        <div className="bg-surface-container rounded-DEFAULT p-space-lg shadow-md">
          <h3 className="flex items-center gap-space-xs font-headline-sm text-headline-sm text-on-surface mb-space-md">
            <span className="material-symbols-outlined text-primary text-[20px]">graphic_eq</span>
            Target Telemetry &amp; Classification
          </h3>

          <div className="grid grid-cols-2 gap-space-md mb-space-lg">
            <TelemetryField label="Classification" value={target.classification || 'Uncertain'} />
            <TelemetryField label="Confidence" value={target.confidence != null ? `${(target.confidence * 100).toFixed(1)}%` : 'N/A'} accent />
            <TelemetryField label="Area Estimated" value={target.estimated_area_m2 != null ? `${target.estimated_area_m2} m²` : 'Not estimated'} />
            <TelemetryField label="Depth" value={target.depth_m != null ? `${target.depth_m} m` : 'Not recorded'} />
          </div>

          {risk?.factors?.length > 0 && (
            <div className="rounded-DEFAULT bg-surface-container-lowest p-space-md mb-space-lg flex flex-col gap-1">
              <span className="font-label-md text-label-md text-on-surface-variant mb-space-2xs uppercase">
                Risk factors (score {risk.score.toFixed(1)}, weights {risk.weights_version})
              </span>
              {risk.factors.map((f) => (
                <div key={f.name} className="flex justify-between items-center text-on-surface-variant font-telemetry-sm text-telemetry-sm py-1 border-b border-outline-variant/20 last:border-b-0">
                  <span>
                    {f.name} <span className="text-outline">[{f.detail}]</span>
                  </span>
                  <span className="text-on-surface font-medium">+{f.contribution}</span>
                </div>
              ))}
            </div>
          )}

          <button
            type="button"
            onClick={handleReprocess}
            disabled={reprocessing}
            title="No per-target reclassify endpoint exists; this reprocesses the whole survey (detection -> classification -> risk -> priority) and reloads this target."
            className="w-full flex items-center justify-center gap-2 py-space-sm px-space-md rounded-full bg-surface-container-high text-on-surface font-label-lg text-label-lg font-semibold disabled:opacity-50 hover:bg-surface-container-highest transition-colors"
          >
            <span className={`material-symbols-outlined text-[18px] ${reprocessing ? 'animate-spin' : ''}`}>refresh</span>
            {reprocessing ? 'Reprocessing survey...' : 'Reprocess Survey'}
          </button>
          {stageLog.length > 0 && (
            <div className="mt-space-md font-telemetry-sm text-telemetry-sm text-on-surface-variant flex flex-col gap-0.5">
              {stageLog.map((entry, i) => (
                <div key={i}>
                  [{entry.status}] {entry.stage}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-surface-container rounded-DEFAULT p-space-lg shadow-md">
          <h3 className="flex items-center gap-space-xs font-headline-sm text-headline-sm text-on-surface mb-space-md">
            <span className="material-symbols-outlined text-primary text-[20px]">share_location</span>
            Spatial Context
          </h3>

          <div className="flex flex-col gap-space-sm">
            <div className="rounded-DEFAULT bg-surface-container-low p-space-md">
              <div className="flex items-center justify-between">
                <span className="font-label-md text-label-md text-on-surface-variant uppercase">Geodetic Position (WGS84)</span>
                <span className="font-telemetry-sm text-telemetry-sm text-primary bg-surface-container px-space-xs py-space-2xs rounded-full">
                  {target.coordinate_source || 'SOURCE: NONE'}
                </span>
              </div>
              <div className="font-telemetry-md text-telemetry-md text-on-surface mt-space-xs">
                {target.latitude != null && target.longitude != null ? (
                  `${target.latitude.toFixed(6)}°N, ${target.longitude.toFixed(6)}°E`
                ) : (
                  <span className="italic text-on-surface-variant">NO ORIGIN METADATA</span>
                )}
              </div>
            </div>

            <div className="rounded-DEFAULT bg-surface-container-low p-space-md">
              <span className="font-label-md text-label-md text-on-surface-variant uppercase">Distance to Nearest Reef</span>
              <div className="font-telemetry-md text-telemetry-md text-on-surface mt-space-xs">
                {!environment
                  ? 'Not enriched yet'
                  : environment.reef_status !== 'OK' && environment.reef_status !== 'TEST_FIXTURE'
                    ? environment.reef_status
                    : environment.reef_distance_m != null
                      ? `${environment.reef_distance_m.toFixed(0)} meters [${environment.reef_id || 'Not Reported'}]`
                      : 'Unknown'}
              </div>
            </div>

            <div className="rounded-DEFAULT bg-surface-container-low p-space-md">
              <span className="font-label-md text-label-md text-on-surface-variant uppercase">Marine Protected Area</span>
              <div className="font-telemetry-md text-telemetry-md text-on-surface mt-space-xs">
                {!environment
                  ? 'Not enriched yet'
                  : environment.mpa_status !== 'OK' && environment.mpa_status !== 'TEST_FIXTURE'
                    ? environment.mpa_status
                    : environment.inside_mpa
                      ? `Inside ${environment.mpa_name || 'Not Reported'}`
                      : environment.mpa_distance_m != null
                        ? `${environment.mpa_distance_m.toFixed(0)} meters away [${environment.mpa_id || 'Not Reported'}]`
                        : 'Unknown'}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

const TelemetryField = ({ label, value, accent }) => (
  <div>
    <div className="font-label-md text-label-md text-on-surface-variant mb-space-2xs uppercase">{label}</div>
    <div className={`font-headline-sm text-headline-sm ${accent ? 'text-primary' : 'text-on-surface'}`}>{value}</div>
  </div>
);

const EmptyState = ({ text, tone }) => (
  <div className="max-w-max-content-width mx-auto px-margin-desktop py-space-2xl flex flex-col items-center justify-center gap-space-sm text-center">
    <span className={`material-symbols-outlined text-[36px] ${tone || 'text-on-surface-variant'}`}>radar</span>
    <p className={`font-body-sm text-body-sm ${tone || 'text-on-surface-variant'}`}>{text}</p>
  </div>
);

export default TargetDetails;
