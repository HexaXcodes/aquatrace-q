import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSurvey } from '../context/SurveyContext';
import SubHeader from '../components/SubHeader';
import { getJob, getSurvey, getSurveyDetections, getSurveyTargetsRaw } from '../api';

// Real ProcessingJobStatus order (app/models/enums.py's PROCESSING_STAGE_ORDER),
// grouped into the 4 visual phases from the design -- the design's own
// grouping labels, driven by the real enum rather than a fixed 4-item list.
const STAGE_ORDER = [
  'QUEUED', 'VALIDATING', 'PREPROCESSING', 'DETECTING', 'CLASSIFYING', 'QML_CLASSIFYING',
  'GEOLOCATING', 'GIS_ENRICHMENT', 'RISK_SCORING', 'PRIORITIZING', 'MISSION_PLANNING', 'REPORTING', 'COMPLETED',
];
const GROUPS = [
  { label: 'Validating & Preprocessing', stages: ['VALIDATING', 'PREPROCESSING'] },
  { label: 'Detecting & Classifying', stages: ['DETECTING', 'CLASSIFYING'] },
  { label: 'QML Classifying & Geolocating', stages: ['QML_CLASSIFYING', 'GEOLOCATING'] },
  { label: 'GIS Enrichment, Risk Scoring & Prioritizing', stages: ['GIS_ENRICHMENT', 'RISK_SCORING', 'PRIORITIZING', 'MISSION_PLANNING', 'REPORTING'] },
];
const KNOWN_SUBCLASSES = ['ghost_net', 'crab_pot', 'pipe', 'metal_debris', 'shipwreck', 'other_debris', 'unknown'];

function groupState(group, currentStage, isFailed) {
  if (isFailed) return 'failed';
  const currentIndex = STAGE_ORDER.indexOf(currentStage);
  const stageIndices = group.stages.map((s) => STAGE_ORDER.indexOf(s));
  if (currentStage === 'COMPLETED' || currentIndex > Math.max(...stageIndices)) return 'done';
  if (stageIndices.includes(currentIndex)) return 'active';
  return 'pending';
}

function formatElapsed(startIso, endIso) {
  if (!startIso) return '--:--:--';
  const start = new Date(startIso).getTime();
  const end = endIso ? new Date(endIso).getTime() : Date.now();
  const totalSeconds = Math.max(0, Math.floor((end - start) / 1000));
  const h = String(Math.floor(totalSeconds / 3600)).padStart(2, '0');
  const m = String(Math.floor((totalSeconds % 3600) / 60)).padStart(2, '0');
  const s = String(totalSeconds % 60).padStart(2, '0');
  return `${h}:${m}:${s}`;
}

const Pipeline = () => {
  const { jobId, surveyId } = useSurvey();
  const navigate = useNavigate();

  const [job, setJob] = useState(null);
  const [survey, setSurvey] = useState(null);
  const [targets, setTargets] = useState([]);
  const [detections, setDetections] = useState([]);
  const [error, setError] = useState(null);
  const [, forceTick] = useState(0);
  const pollRef = useRef(null);
  const tickRef = useRef(null);

  useEffect(() => {
    if (surveyId) getSurvey(surveyId).then(setSurvey).catch(() => {});
  }, [surveyId]);

  useEffect(() => {
    if (!jobId) return undefined;
    setError(null);
    setJob(null);

    let cancelled = false;
    const poll = async () => {
      try {
        const current = await getJob(jobId);
        if (cancelled) return;
        setJob(current);
        if (current.status === 'COMPLETED' || current.status === 'FAILED') {
          if (pollRef.current) clearInterval(pollRef.current);
          if (surveyId) {
            getSurveyTargetsRaw(surveyId).then((t) => !cancelled && setTargets(t)).catch(() => {});
            getSurveyDetections(surveyId).then((d) => !cancelled && setDetections(d.items)).catch(() => {});
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message);
          if (pollRef.current) clearInterval(pollRef.current);
        }
      }
    };

    poll();
    pollRef.current = setInterval(poll, 1200);
    tickRef.current = setInterval(() => forceTick((n) => n + 1), 1000);
    return () => {
      cancelled = true;
      if (pollRef.current) clearInterval(pollRef.current);
      if (tickRef.current) clearInterval(tickRef.current);
    };
  }, [jobId, surveyId]);

  if (!jobId) {
    return (
      <>
        <SubHeader pageLabel="Pipeline" title="Acoustic Processing Pipeline" />
        <EmptyState text="No pipeline run in progress. Upload a survey on the Ingest & Metadata screen to start one." />
      </>
    );
  }
  if (error) {
    return (
      <>
        <SubHeader pageLabel="Pipeline" title="Acoustic Processing Pipeline" />
        <EmptyState text={error} tone="text-error" />
      </>
    );
  }
  if (!job) {
    return (
      <>
        <SubHeader pageLabel="Pipeline" title="Acoustic Processing Pipeline" />
        <EmptyState text="Loading job status..." />
      </>
    );
  }

  const running = job.status !== 'COMPLETED' && job.status !== 'FAILED';
  const isFailed = job.status === 'FAILED';
  const firstLog = job.stage_log[0]?.at;
  const lastLog = job.stage_log[job.stage_log.length - 1]?.at;
  const avgLatency = detections.length
    ? detections.reduce((sum, d) => sum + (d.inference_time_ms || 0), 0) / detections.length
    : null;
  const subclassCounts = {};
  for (const t of targets) subclassCounts[t.debris_subclass || 'uncertain'] = (subclassCounts[t.debris_subclass || 'uncertain'] || 0) + 1;
  const detectionModel = detections[0]?.model_name || null;
  const hasImagery = survey?.width && survey?.height;

  return (
    <>
      <SubHeader
        pageLabel="Pipeline"
        title="Acoustic Processing Pipeline"
        right={
          <div className={`flex items-center gap-space-xs px-space-sm py-space-2xs rounded-full ${isFailed ? 'bg-error-container/20 text-error' : 'bg-primary-container/15 text-primary'}`}>
            <span className={`w-2 h-2 rounded-full ${running ? 'bg-current animate-ping' : 'bg-current'}`} />
            <span className="font-telemetry-sm text-telemetry-sm uppercase font-semibold">
              status={job.status}
            </span>
          </div>
        }
      />

      <div className="max-w-max-content-width mx-auto px-margin-desktop py-space-xl flex flex-col gap-space-xl">
        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-space-md pb-space-xs">
          <div className="flex flex-col gap-space-2xs">
            <div className="flex items-center gap-space-xs">
              <span className="font-telemetry-sm text-telemetry-sm uppercase tracking-widest text-primary">Job #{job.id.slice(0, 8)}</span>
              <span className="text-outline-variant font-telemetry-sm text-telemetry-sm">•</span>
              <span className="font-telemetry-sm text-telemetry-sm text-on-surface-variant">{survey?.name || 'Survey'}</span>
            </div>
          </div>
          <div className="flex items-center gap-space-lg bg-surface-container-low px-space-lg py-space-sm rounded-full shadow-sm">
            <Stat label="Run Elapsed" value={formatElapsed(firstLog, running ? null : lastLog)} />
            <div className="w-px h-8 bg-surface-variant" />
            <Stat label="Targets Detected" value={String(targets.length)} accent />
          </div>
        </div>

        {/* Grouped stage stepper */}
        <div className="w-full bg-surface-container-low rounded-xl p-space-md shadow-sm">
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-space-md">
            {GROUPS.map((group) => {
              const state = groupState(group, job.status, isFailed);
              return (
                <div
                  key={group.label}
                  className={`flex flex-col gap-space-2xs p-space-md rounded-DEFAULT relative overflow-hidden ${
                    state === 'active' ? 'bg-surface-container-high shadow-[0_0_20px_rgba(0,229,190,0.12)]' : state === 'failed' ? 'bg-error-container/10' : 'bg-surface-container'
                  } ${state === 'pending' ? 'opacity-70' : ''}`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-space-2xs">
                      {state === 'done' && <span className="material-symbols-outlined text-primary text-[18px]">check_circle</span>}
                      {state === 'active' && <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />}
                      {state === 'failed' && <span className="material-symbols-outlined text-error text-[18px]">error</span>}
                      {state === 'pending' && <span className="material-symbols-outlined text-on-surface-variant text-[18px]">schedule</span>}
                      <span className={`font-telemetry-sm text-telemetry-sm uppercase font-bold ${state === 'active' ? 'text-primary' : state === 'failed' ? 'text-error' : 'text-on-surface-variant'}`}>
                        {state === 'active' ? 'Active' : state === 'done' ? 'Complete' : state === 'failed' ? 'Failed' : 'Queued'}
                      </span>
                    </div>
                  </div>
                  <p className="font-label-lg text-label-lg text-on-surface truncate">{group.label}</p>
                  <div className="w-full bg-surface-container-highest h-1.5 rounded-full overflow-hidden mt-space-xs">
                    <div
                      className={`h-full rounded-full ${state === 'done' ? 'bg-primary w-full' : state === 'active' ? 'bg-primary w-2/3 animate-pulse' : state === 'failed' ? 'bg-error w-full' : 'bg-surface-variant w-0'}`}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-12 gap-space-lg items-start">
          {/* LEFT: telemetry + log */}
          <div className="xl:col-span-7 flex flex-col gap-space-lg">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-space-md">
              <MetricCard icon="dynamic_feed" label="Targets Detected" value={String(targets.length)} sub={running ? 'Awaiting completion' : `${Object.keys(subclassCounts).length} subclass(es)`} />
              <MetricCard
                icon="speed"
                label="Avg Inference Latency"
                value={avgLatency != null ? `${avgLatency.toFixed(1)} ms` : '--'}
                sub={detectionModel || 'Awaiting detections'}
              />
              <MetricCard
                icon="warning"
                label="Non-Seabed Targets"
                value={String(targets.filter((t) => t.classification !== 'NATURAL_SEABED').length)}
                sub={Object.entries(subclassCounts).map(([k, v]) => `${v} ${k}`).join(' / ') || 'None yet'}
                tone="text-tertiary-fixed-dim"
              />
            </div>

            <div className="bg-surface-container-low rounded-DEFAULT p-space-lg shadow-sm flex flex-col gap-space-md">
              <div className="flex items-center justify-between pb-space-2xs">
                <div className="flex items-center gap-space-xs">
                  <span className="material-symbols-outlined text-primary text-[20px]">terminal</span>
                  <h3 className="font-headline-sm text-headline-sm text-on-surface">Execution Event Stream</h3>
                </div>
                <div className="flex items-center gap-space-xs font-telemetry-sm text-telemetry-sm text-on-surface-variant">
                  <span className={`w-2 h-2 rounded-full ${running ? 'bg-primary animate-ping' : 'bg-outline-variant'}`} />
                  <span>{running ? 'LIVE LOG BUFFER' : 'FINAL LOG'}</span>
                </div>
              </div>
              <div className="bg-surface-container-lowest rounded-DEFAULT p-space-md font-telemetry-sm text-telemetry-sm text-on-surface flex flex-col gap-space-xs h-[300px] overflow-y-auto shadow-inner">
                {job.stage_log.length === 0 && (
                  <span className="text-on-surface-variant">Waiting for the first stage to report in...</span>
                )}
                {job.stage_log.map((entry, i) => (
                  <div key={`${entry.stage}-${i}`} className="flex items-start gap-space-xs leading-relaxed">
                    <span className="text-outline shrink-0">[{new Date(entry.at).toLocaleTimeString()}]</span>
                    <span className={`font-semibold shrink-0 ${entry.status === 'FAILED' ? 'text-error' : entry.status === 'SKIPPED' ? 'text-on-surface-variant' : 'text-primary'}`}>
                      [{entry.stage}]
                    </span>
                    <span className="text-on-surface-variant">{entry.message}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* RIGHT: detection overlay preview + config + taxonomy */}
          <div className="xl:col-span-5 flex flex-col gap-space-lg">
            <div className="bg-surface-container-low rounded-DEFAULT p-space-lg shadow-sm flex flex-col gap-space-md">
              <div className="flex items-center justify-between pb-space-2xs">
                <div>
                  <h3 className="font-headline-sm text-headline-sm text-on-surface">Sonar Detection Preview</h3>
                  <p className="font-telemetry-sm text-telemetry-sm text-on-surface-variant">{survey?.sensor_name || 'Sensor not recorded'}</p>
                </div>
                <div className="flex items-center gap-space-xs px-space-xs py-space-2xs rounded-full bg-primary-container/20 text-primary">
                  <span className="material-symbols-outlined text-[16px]">radar</span>
                  <span className="font-telemetry-sm text-telemetry-sm font-semibold uppercase">{detectionModel || 'AWAITING DETECTIONS'}</span>
                </div>
              </div>
              <div className="relative w-full h-[280px] rounded-DEFAULT overflow-hidden bg-surface-container-lowest">
                <div className="absolute inset-0 opacity-20" style={{ backgroundImage: 'linear-gradient(90deg, #6fffdb 1px, transparent 1px), linear-gradient(#6fffdb 1px, transparent 1px)', backgroundSize: '28px 28px' }} />
                {hasImagery &&
                  targets.map((t) => {
                    if (!t.bbox) return null;
                    const [x1, y1, x2, y2] = t.bbox;
                    return (
                      <div
                        key={t.id}
                        className="absolute border border-primary/70 bg-primary/5 rounded-xs"
                        style={{
                          left: `${(x1 / survey.width) * 100}%`,
                          top: `${(y1 / survey.height) * 100}%`,
                          width: `${Math.max(((x2 - x1) / survey.width) * 100, 3)}%`,
                          height: `${Math.max(((y2 - y1) / survey.height) * 100, 3)}%`,
                        }}
                      />
                    );
                  })}
                {!hasImagery && (
                  <div className="absolute inset-0 flex items-center justify-center text-on-surface-variant font-body-sm text-body-sm text-center px-space-md">
                    {running ? 'Processing -- detections will appear here once DETECTING completes.' : 'No pixel dimensions recorded for this survey.'}
                  </div>
                )}
              </div>
            </div>

            <div className="bg-surface-container-low rounded-DEFAULT p-space-lg shadow-sm flex flex-col gap-space-md">
              <div className="flex items-center justify-between pb-space-2xs">
                <div>
                  <h3 className="font-headline-sm text-headline-sm text-on-surface">Pipeline Configuration</h3>
                  <p className="font-telemetry-sm text-telemetry-sm text-on-surface-variant">Active Execution Context</p>
                </div>
              </div>
              <div className="flex flex-col gap-space-sm pt-space-xs">
                <ConfigRow label="Detection Model" value={detectionModel || 'Not yet run'} />
                <ConfigRow label="Classical Classifier" value="scikit-learn (logistic regression)" />
                <ConfigRow label="Quantum Kernel" value="QSVC (ZZFeatureMap + FidelityQuantumKernel)" accent />
                <ConfigRow label="Coordinate Projection" value="WGS84 geodesic" last />
              </div>
            </div>

            <div className="bg-surface-container-low rounded-DEFAULT p-space-lg shadow-sm flex flex-col gap-space-md">
              <div className="flex items-center justify-between pb-space-2xs">
                <div>
                  <h3 className="font-headline-sm text-headline-sm text-on-surface">Detection Manifest &amp; Taxonomy</h3>
                  <p className="font-telemetry-sm text-telemetry-sm text-on-surface-variant">Real KNOWN_DEBRIS_SUBCLASSES vocabulary</p>
                </div>
                <span className="px-space-xs py-space-2xs rounded-full bg-secondary-fixed/10 text-secondary-fixed font-telemetry-sm text-telemetry-sm font-semibold uppercase">
                  {KNOWN_SUBCLASSES.length} CLASSES
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-space-xs pt-space-xs">
                {KNOWN_SUBCLASSES.map((cls) => {
                  const matches = targets.filter((t) => t.debris_subclass === cls);
                  const detected = matches.length > 0;
                  const maxConf = detected ? Math.max(...matches.map((t) => t.confidence || 0)) : null;
                  return (
                    <div
                      key={cls}
                      className={`flex items-center justify-between p-space-xs rounded-DEFAULT border ${detected ? 'bg-surface-container border-primary/40' : 'bg-surface-container-lowest border-outline-variant/20'}`}
                    >
                      <div className="flex items-center gap-space-2xs">
                        <span className={`w-2 h-2 rounded-full ${detected ? 'bg-primary animate-pulse' : 'bg-outline-variant/40'}`} />
                        <span className={`font-mono text-xs font-semibold ${detected ? 'text-primary' : 'text-on-surface-variant/60'}`}>{cls}</span>
                      </div>
                      <span className={`font-telemetry-sm text-[10px] px-1 rounded-xs ${detected ? 'text-primary bg-primary/10' : 'text-outline'}`}>
                        {detected ? `Conf: ${maxConf.toFixed(2)}` : 'None'}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {job.error_message && (
          <div className="bg-error-container text-on-error-container rounded-DEFAULT p-space-md font-body-sm text-body-sm">
            {job.error_message}
          </div>
        )}

        <div className="w-full bg-surface-container-low/95 backdrop-blur-md rounded-full px-space-lg py-space-sm shadow-xl flex items-center justify-between gap-space-md">
          <div className="flex items-center gap-space-xs font-telemetry-sm text-telemetry-sm text-on-surface-variant">
            <span className={`w-2 h-2 rounded-full ${running ? 'bg-primary animate-pulse' : 'bg-outline-variant'}`} />
            <span>{running ? 'Pipeline job active' : isFailed ? 'Pipeline job failed' : 'Pipeline job complete'}</span>
          </div>
          <button
            type="button"
            disabled={job.status !== 'COMPLETED'}
            onClick={() => navigate('/triage')}
            className="px-space-xl h-[44px] rounded-full bg-primary hover:bg-primary-fixed-dim text-on-primary font-label-lg text-label-lg flex items-center gap-space-xs transition-all shadow-[0_0_20px_rgba(0,229,190,0.35)] disabled:opacity-40 disabled:shadow-none"
          >
            <span>View Triage Results</span>
            <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
          </button>
        </div>
      </div>
    </>
  );
};

const Stat = ({ label, value, accent }) => (
  <div className="flex flex-col">
    <span className="font-telemetry-sm text-telemetry-sm text-on-surface-variant uppercase">{label}</span>
    <span className={`font-telemetry-lg text-telemetry-lg font-semibold tracking-wider ${accent ? 'text-primary' : 'text-on-surface'}`}>{value}</span>
  </div>
);

const MetricCard = ({ icon, label, value, sub, tone }) => (
  <div className="bg-surface-container-low p-space-md rounded-DEFAULT flex flex-col justify-between gap-space-xs shadow-sm">
    <div className="flex items-center justify-between">
      <span className="font-telemetry-sm text-telemetry-sm text-on-surface-variant uppercase">{label}</span>
      <span className={`material-symbols-outlined text-[20px] ${tone || 'text-primary'}`}>{icon}</span>
    </div>
    <div className="flex flex-col">
      <span className={`font-headline-sm text-headline-sm font-semibold tracking-tight ${tone || 'text-on-surface'}`}>{value}</span>
      <span className="font-telemetry-sm text-telemetry-sm text-on-surface-variant mt-space-2xs truncate">{sub}</span>
    </div>
  </div>
);

const ConfigRow = ({ label, value, accent, last }) => (
  <div className={`flex items-center justify-between py-space-2xs ${last ? '' : 'border-b border-surface-container-high/40'}`}>
    <span className="font-body-sm text-body-sm text-on-surface-variant">{label}</span>
    <span className={`font-telemetry-sm text-telemetry-sm font-medium ${accent ? 'text-primary' : 'text-on-surface'}`}>{value}</span>
  </div>
);

const EmptyState = ({ text, tone }) => (
  <div className="max-w-max-content-width mx-auto px-margin-desktop py-space-2xl flex flex-col items-center justify-center gap-space-sm text-center">
    <span className={`material-symbols-outlined text-[36px] ${tone || 'text-on-surface-variant'}`}>graphic_eq</span>
    <p className={`font-body-sm text-body-sm ${tone || 'text-on-surface-variant'}`}>{text}</p>
  </div>
);

export default Pipeline;
