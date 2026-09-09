import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSurvey } from '../context/SurveyContext';
import SubHeader from '../components/SubHeader';
import {
  buildMission,
  downloadSurveyReportCsv,
  downloadSurveyReportJson,
  getSurvey,
  getSurveyImageUrl,
  getSurveyReport,
  getSurveyTargetDossiers,
} from '../api';

const RISK_BADGE = {
  CRITICAL: 'bg-error-container text-on-error-container',
  HIGH: 'bg-tertiary-container/80 text-on-tertiary-container',
  MEDIUM: 'bg-surface-container-highest text-primary',
  LOW: 'bg-primary/10 text-primary',
};
const ACTION_ICON = { VERIFY_NOW: 'priority_high', VERIFY_NEXT: 'schedule', VERIFY_LATER: 'update', IGNORE: 'block' };

const Triage = () => {
  const { surveyId } = useSurvey();
  const navigate = useNavigate();

  const [survey, setSurvey] = useState(null);
  const [dossiers, setDossiers] = useState(null);
  const [error, setError] = useState(null);
  const [building, setBuilding] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [downloadingJson, setDownloadingJson] = useState(false);
  const [vectorsVisible, setVectorsVisible] = useState(true);

  useEffect(() => {
    if (!surveyId) {
      setSurvey(null);
      setDossiers(null);
      return;
    }
    setError(null);
    setDossiers(null);
    Promise.all([getSurvey(surveyId), getSurveyTargetDossiers(surveyId)])
      .then(([s, d]) => {
        setSurvey(s);
        setDossiers(d.sort((a, b) => (b.risk?.score ?? -1) - (a.risk?.score ?? -1)));
      })
      .catch((err) => setError(err.message));
  }, [surveyId]);

  if (!surveyId) {
    return (
      <>
        <SubHeader pageLabel="Triage" title="Triage Overlay &amp; Acoustic Inspection" />
        <EmptyState text="No survey selected. Upload one on the Ingest & Metadata screen first." />
      </>
    );
  }
  if (error) {
    return (
      <>
        <SubHeader pageLabel="Triage" title="Triage Overlay &amp; Acoustic Inspection" />
        <EmptyState text={error} tone="text-error" />
      </>
    );
  }
  if (!dossiers || !survey) {
    return (
      <>
        <SubHeader pageLabel="Triage" title="Triage Overlay &amp; Acoustic Inspection" />
        <EmptyState text="Loading triage overlay..." />
      </>
    );
  }

  const hasImagery = survey.width && survey.height;

  const handleExportCsv = async () => {
    setDownloading(true);
    try {
      await downloadSurveyReportCsv(surveyId);
    } catch (err) {
      setError(err.message);
    } finally {
      setDownloading(false);
    }
  };

  const handleExportJson = async () => {
    setDownloadingJson(true);
    try {
      const report = await getSurveyReport(surveyId);
      downloadSurveyReportJson(surveyId, report);
    } catch (err) {
      setError(err.message);
    } finally {
      setDownloadingJson(false);
    }
  };

  const handleBuildMission = async () => {
    if (survey.origin_latitude == null || survey.origin_longitude == null) {
      navigate('/planner');
      return;
    }
    setBuilding(true);
    try {
      const mission = await buildMission(surveyId, {
        startLatitude: survey.origin_latitude,
        startLongitude: survey.origin_longitude,
      });
      navigate('/planner', { state: { mission } });
    } catch (err) {
      setError(err.message);
    } finally {
      setBuilding(false);
    }
  };

  return (
    <>
      <SubHeader
        pageLabel="Triage"
        title="Triage Overlay & Acoustic Inspection"
        right={
          <>
            <div className="flex items-center gap-space-xs px-space-md py-space-xs rounded-full bg-surface-container-low text-primary">
              <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
              <span className="font-telemetry-sm text-telemetry-sm font-semibold tracking-wider uppercase">Triage Complete</span>
            </div>
            <button
              type="button"
              onClick={() => setVectorsVisible((v) => !v)}
              className="flex items-center gap-space-xs px-space-lg py-space-xs rounded-full bg-surface-container text-on-surface hover:bg-surface-container-high transition-all font-label-md text-label-md"
            >
              <span className="material-symbols-outlined text-[18px]">layers</span>
              <span>Toggle Vectors</span>
            </button>
            <button
              type="button"
              onClick={handleExportCsv}
              disabled={downloading}
              className="flex items-center gap-space-xs px-space-lg py-space-xs rounded-full bg-primary text-on-primary font-label-lg text-label-lg shadow-md hover:bg-primary-fixed-dim transition-all disabled:opacity-50"
            >
              <span className="material-symbols-outlined text-[18px]">send</span>
              <span>{downloading ? 'Sending...' : 'Transmit Report'}</span>
            </button>
          </>
        }
      />

      <div className="max-w-max-content-width mx-auto px-margin-desktop py-space-xl flex flex-col gap-space-2xl">
        <div className="flex flex-wrap items-center gap-space-sm font-telemetry-md text-telemetry-md text-on-surface-variant -mt-space-lg">
          <span>{survey.name}</span>
          <span className="w-1 h-1 rounded-full bg-outline" />
          <span>{survey.sensor_name || 'Sensor not recorded'}</span>
          <span className="w-1 h-1 rounded-full bg-outline" />
          <span className="text-primary font-medium">Target Count: {dossiers.length}</span>
        </div>

        {/* Side-by-side comparison */}
        <div className="relative w-full flex flex-col xl:flex-row items-stretch gap-space-md">
          <Panel
            title="Uploaded (Raw Acoustic Sonar)"
            icon="graphic_eq"
            badge={hasImagery ? `${survey.width}x${survey.height}px` : 'DIMENSIONS UNKNOWN'}
            footer={[
              ['File type', survey.file_type?.toUpperCase() || 'Unknown'],
              ['Meters/pixel', survey.meters_per_pixel ? `${survey.meters_per_pixel} m/px` : 'Not set'],
              ['Origin', survey.origin_latitude != null ? `${survey.origin_latitude}°, ${survey.origin_longitude}°` : 'Not set'],
            ]}
          >
            {hasImagery ? (
              <img
                src={getSurveyImageUrl(surveyId)}
                alt={survey.name || 'Uploaded Acoustic Sonar'}
                className="w-full h-full object-contain"
              />
            ) : (
              <>
                <div className="absolute inset-0 opacity-25" style={gridStyle} />
                <div className="absolute inset-0 flex items-center justify-center text-on-surface-variant font-telemetry-sm text-telemetry-sm text-center px-space-md">
                  No uploaded sonar image available.
                </div>
              </>
            )}
          </Panel>

          <div className="self-center flex xl:flex-col items-center justify-center gap-space-xs z-10 my-space-xs xl:my-0">
            <div className="hidden xl:block h-6 w-[2px] bg-outline-variant/40" />
            <div className="px-space-md py-space-xs rounded-full bg-surface-container-high text-primary font-telemetry-sm text-telemetry-sm uppercase tracking-wider flex items-center gap-space-xs shadow-md">
              <span className="w-1.5 h-1.5 rounded-full bg-primary" />
              <span>AI Segmentation &amp; Triage</span>
              <span className="material-symbols-outlined text-[16px] text-primary">arrow_forward</span>
            </div>
            <div className="hidden xl:block h-6 w-[2px] bg-outline-variant/40" />
          </div>

          <Panel
            title="Detected (Real Target Overlay)"
            icon="smart_toy"
            badge={`${dossiers.length} ANOMALIES BOUNDED`}
            footer={[
              ['Model', dossiers.length > 0 ? 'e004-unet-shipwreck-segmentation' : 'Not yet run'],
              ['Threshold', 'sigmoid(logits) > 0.5'],
              ['Mask resolution', '1024x1024'],
            ]}
          >
            <div className="absolute inset-0 opacity-25" style={gridStyle} />
            {hasImagery && vectorsVisible &&
              dossiers.map(({ target, risk }) => {
                if (!target.bbox) return null;
                const [x1, y1, x2, y2] = target.bbox;
                const level = risk?.level;
                return (
                  <button
                    key={target.id}
                    type="button"
                    onClick={() => navigate(`/target/${target.id}`)}
                    className={`absolute rounded-xs border-2 border-dashed flex flex-col justify-between p-1 text-left ${
                      level === 'CRITICAL' || level === 'HIGH' ? 'border-error/80 bg-error/10' : 'border-primary/70 bg-primary/5'
                    }`}
                    style={{
                      left: `${(x1 / survey.width) * 100}%`,
                      top: `${(y1 / survey.height) * 100}%`,
                      width: `${Math.max(((x2 - x1) / survey.width) * 100, 5)}%`,
                      height: `${Math.max(((y2 - y1) / survey.height) * 100, 5)}%`,
                    }}
                  >
                    <span
                      className={`font-telemetry-sm text-[10px] px-1 rounded-xs inline-block self-start font-bold uppercase ${
                        level === 'CRITICAL' || level === 'HIGH' ? 'bg-error text-on-error' : 'bg-primary text-on-primary'
                      }`}
                    >
                      {(target.debris_subclass || target.classification || 'uncertain')}: {target.confidence != null ? target.confidence.toFixed(2) : 'n/a'}
                    </span>
                  </button>
                );
              })}
            {(!hasImagery || dossiers.length === 0) && (
              <div className="absolute inset-0 flex items-center justify-center text-on-surface-variant font-body-sm text-body-sm">
                {dossiers.length === 0 ? 'No non-seabed targets detected.' : 'No pixel dimensions recorded.'}
              </div>
            )}
          </Panel>
        </div>

        {/* Target dossiers */}
        <div className="flex flex-col gap-space-lg">
          <div className="flex items-center justify-between pb-space-xs flex-wrap gap-space-sm">
            <div className="flex items-center gap-space-sm">
              <h2 className="font-headline-md text-headline-md text-on-surface">Target Verification Manifest</h2>
              <span className="font-telemetry-sm text-telemetry-sm px-space-xs py-space-2xs rounded-full bg-surface-container-high text-on-surface-variant">
                {dossiers.length} OBJECT{dossiers.length === 1 ? '' : 'S'} REGISTERED
              </span>
            </div>
            <span className="font-telemetry-sm text-telemetry-sm text-outline">SORT BY: RISK SCORE DESC</span>
          </div>

          {dossiers.length === 0 && (
            <div className="flex flex-col items-center gap-space-xs py-space-2xl text-center">
              <span className="material-symbols-outlined text-[32px] text-on-surface-variant">check_circle</span>
              <p className="font-body-sm text-body-sm text-on-surface-variant">No non-seabed targets detected for this survey.</p>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-gutter-desktop">
            {dossiers.map(({ target, risk, priority, environment }, i) => (
              <TargetCard
                key={target.id}
                index={i + 1}
                target={target}
                risk={risk}
                priority={priority}
                environment={environment}
                onViewDetails={() => navigate(`/target/${target.id}`)}
              />
            ))}
          </div>
        </div>

        <div className="flex items-center justify-between bg-surface-container-low rounded-DEFAULT p-space-md shadow-sm">
          <button
            type="button"
            onClick={handleExportJson}
            disabled={downloadingJson}
            className="flex items-center gap-space-xs px-space-lg py-space-xs rounded-full bg-surface-container text-on-surface-variant hover:bg-surface-container-high transition-colors font-label-md text-label-md disabled:opacity-50"
          >
            <span className="material-symbols-outlined text-[16px]">data_object</span>
            {downloadingJson ? 'Downloading...' : 'Export raw JSON'}
          </button>
          <button
            type="button"
            onClick={handleBuildMission}
            disabled={building}
            className="flex items-center gap-space-xs px-space-xl py-space-sm rounded-full bg-surface-container text-primary font-label-lg text-label-lg hover:bg-surface-container-high transition-colors disabled:opacity-50"
          >
            <span className="material-symbols-outlined text-[18px]">alt_route</span>
            {building ? 'Building route...' : 'Build Verification Mission'}
          </button>
        </div>

        {error && (
          <div className="bg-error-container text-on-error-container rounded-DEFAULT p-space-md font-body-sm text-body-sm">{error}</div>
        )}
      </div>
    </>
  );
};

const gridStyle = {
  backgroundImage: 'linear-gradient(90deg, #6fffdb 1px, transparent 1px), linear-gradient(#6fffdb 1px, transparent 1px)',
  backgroundSize: '32px 32px',
};

const Panel = ({ title, icon, badge, footer, children }) => (
  <div className="flex-1 flex flex-col rounded-DEFAULT bg-surface-container-low overflow-hidden shadow-lg">
    <div className="px-space-lg py-space-md flex items-center justify-between bg-surface-container">
      <div className="flex items-center gap-space-sm">
        <span className="material-symbols-outlined text-on-surface-variant text-[20px]">{icon}</span>
        <span className="font-label-lg text-label-lg text-on-surface tracking-wide uppercase font-semibold">{title}</span>
      </div>
      <span className="px-space-sm py-space-2xs rounded-full bg-surface-container-highest text-on-surface-variant font-telemetry-sm text-telemetry-sm">{badge}</span>
    </div>
    <div className="relative aspect-[16/9] w-full overflow-hidden bg-surface-container-lowest">{children}</div>
    <div className="p-space-md flex items-center justify-between bg-surface-container text-on-surface-variant font-telemetry-sm text-telemetry-sm flex-wrap gap-space-xs">
      {footer.map(([label, value]) => (
        <span key={label}>
          {label}: <span className="text-on-surface">{value}</span>
        </span>
      ))}
    </div>
  </div>
);

const TargetCard = ({ index, target, risk, priority, environment, onViewDetails }) => {
  const label = target.debris_subclass || target.classification || 'uncertain';
  const riskLevel = risk?.level;

  return (
    <div className="rounded-DEFAULT bg-surface-container p-space-lg flex flex-col justify-between gap-space-md shadow-md">
      <div className="flex flex-col gap-space-sm">
        <div className="flex items-start justify-between gap-space-sm">
          <div className="flex flex-col gap-space-2xs">
            <span className={`font-telemetry-sm text-telemetry-sm uppercase font-medium ${riskLevel ? 'text-primary' : 'text-on-surface-variant'}`}>
              {target.classification || 'UNCERTAIN'}
            </span>
            <h3 className="font-headline-sm text-headline-sm text-on-surface">
              TARGET {String(index).padStart(2, '0')} — {label}
            </h3>
          </div>
          <div className="flex flex-col items-end gap-1 shrink-0">
            <span className={`px-space-md py-space-2xs rounded-full font-telemetry-sm text-telemetry-sm uppercase font-bold tracking-wider ${riskLevel ? RISK_BADGE[riskLevel] : 'bg-surface-container-high text-on-surface-variant'}`}>
              {riskLevel ? `${riskLevel} RISK` : 'RISK PENDING'}
            </span>
            {risk && <span className="font-telemetry-sm text-telemetry-sm text-on-surface-variant font-semibold">Total Risk Score: {risk.score.toFixed(0)} / 100</span>}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-space-md py-space-2xs border-t border-b border-outline-variant/20 font-telemetry-sm text-telemetry-sm text-on-surface-variant">
          {target.coordinate_source && target.latitude != null ? (
            <>
              <span>Lat: <strong className="text-on-surface">{target.latitude.toFixed(4)}°</strong></span>
              <span>Lon: <strong className="text-on-surface">{target.longitude.toFixed(4)}°</strong></span>
            </>
          ) : (
            <span>Coords: <strong className="text-outline">NO ORIGIN METADATA</strong></span>
          )}
          <span>
            MPA:{' '}
            <strong className={environment?.mpa_status === 'OK' || environment?.mpa_status === 'TEST_FIXTURE' ? 'text-primary' : 'text-outline'}>
              {!environment
                ? 'NOT ENRICHED'
                : environment.mpa_status !== 'OK' && environment.mpa_status !== 'TEST_FIXTURE'
                  ? environment.mpa_status
                  : environment.inside_mpa
                    ? environment.mpa_name || 'Not Reported'
                    : `${environment.mpa_distance_m?.toFixed(0) ?? '?'}m away`}
            </strong>
          </span>
        </div>
        <div className="flex items-center gap-space-xs">
          <span className="flex items-center gap-1 px-space-xs py-1 rounded-full bg-surface-container-highest text-primary font-label-md text-label-md">
            <span className="material-symbols-outlined text-[14px]">{ACTION_ICON[priority?.action] || 'hourglass_empty'}</span>
            {priority?.action || 'PENDING'}
          </span>
          {priority?.verification_required && (
            <span className="px-space-xs py-1 rounded-full bg-error-container/30 text-error font-label-md text-label-md">Verification required</span>
          )}
        </div>
      </div>

      {risk && (
        <div className="flex flex-col gap-space-xs bg-surface-container-low p-space-md rounded-DEFAULT">
          <span className="font-telemetry-sm text-telemetry-sm text-outline uppercase font-medium pb-space-2xs border-b border-outline-variant/20">
            Real Risk Factor Breakdown
          </span>
          <div className="flex flex-col gap-1 pt-space-2xs">
            {risk.factors.map((f) => (
              <div key={f.name} className="flex items-center justify-between py-1 border-b border-outline-variant/20 font-telemetry-sm text-telemetry-sm last:border-b-0">
                <span className="text-outline font-medium tracking-wide uppercase">{f.name}</span>
                <span className="text-on-surface font-semibold">
                  +{f.contribution} <span className="text-outline font-normal normal-case">({f.detail})</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex items-center justify-end pt-space-xs">
        <button
          type="button"
          onClick={onViewDetails}
          className="px-space-lg py-space-xs rounded-full bg-surface-container-high text-on-surface hover:bg-surface-container-highest transition-all font-label-md text-label-md flex items-center gap-space-2xs"
        >
          <span className="material-symbols-outlined text-[16px]">visibility</span>
          <span>View Full Details</span>
        </button>
      </div>
    </div>
  );
};

const EmptyState = ({ text, tone }) => (
  <div className="max-w-max-content-width mx-auto px-margin-desktop py-space-2xl flex flex-col items-center justify-center gap-space-sm text-center">
    <span className={`material-symbols-outlined text-[36px] ${tone || 'text-on-surface-variant'}`}>radar</span>
    <p className={`font-body-sm text-body-sm ${tone || 'text-on-surface-variant'}`}>{text}</p>
  </div>
);

export default Triage;
