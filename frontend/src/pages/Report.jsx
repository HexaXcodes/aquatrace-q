import React, { useEffect, useState } from 'react';
import { useSurvey } from '../context/SurveyContext';
import SubHeader from '../components/SubHeader';
import { downloadSurveyReportCsv, downloadSurveyReportJson, getPrioritySummary } from '../api';

const LEVELS = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'pending'];
const LEVEL_BAR = {
  CRITICAL: 'bg-error',
  HIGH: 'bg-tertiary-fixed-dim',
  MEDIUM: 'bg-primary',
  LOW: 'bg-outline',
  pending: 'bg-on-surface-variant',
};
const LEVEL_BADGE = {
  CRITICAL: 'bg-error-container text-on-error-container',
  HIGH: 'bg-tertiary-container/80 text-on-tertiary-container',
  MEDIUM: 'bg-surface-container-highest text-primary',
  LOW: 'bg-surface-container-low text-on-surface-variant',
  pending: 'bg-surface-container text-on-surface-variant',
};

const Report = () => {
  const { surveyId } = useSurvey();
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(false);

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
        <SubHeader pageLabel="Report" title="Survey Report" />
        <EmptyState text="No survey selected. Upload or select one from the header." />
      </>
    );
  }
  if (error) {
    return (
      <>
        <SubHeader pageLabel="Report" title="Survey Report" />
        <EmptyState text={error} tone="text-error" />
      </>
    );
  }
  if (!summary) {
    return (
      <>
        <SubHeader pageLabel="Report" title="Survey Report" />
        <EmptyState text="Loading report..." />
      </>
    );
  }

  const { report, survey, counts } = summary;

  const handleDownloadCsv = async () => {
    setDownloading(true);
    try {
      await downloadSurveyReportCsv(surveyId);
    } catch (err) {
      setError(err.message);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <>
      <SubHeader
        pageLabel="Report"
        title="Survey Report"
        right={<span className="font-telemetry-sm text-telemetry-sm text-on-surface-variant">Generated {new Date(report.generated_at).toLocaleString()}</span>}
      />
      <div className="max-w-max-content-width mx-auto px-margin-desktop py-space-xl flex flex-col gap-space-lg">
        <div className="flex gap-space-sm">
          <button
            type="button"
            onClick={handleDownloadCsv}
            disabled={downloading}
            className="flex items-center justify-center gap-2 py-space-xs px-space-xl rounded-full bg-primary text-on-primary font-label-lg text-label-lg font-bold shadow-[0_0_16px_rgba(0,229,190,0.25)] disabled:opacity-50 transition-all"
          >
            <span className="material-symbols-outlined text-[18px]">file_download</span>
            {downloading ? 'Downloading...' : 'Download CSV'}
          </button>
          <button
            type="button"
            onClick={() => downloadSurveyReportJson(surveyId, report)}
            className="flex items-center justify-center gap-2 py-space-xs px-space-xl rounded-full bg-surface-container text-on-surface font-label-lg text-label-lg font-semibold hover:bg-surface-container-high transition-colors"
          >
            <span className="material-symbols-outlined text-[18px]">data_object</span>
            Download JSON
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-gutter-desktop">
          <div className="bg-surface-container rounded-DEFAULT p-space-lg shadow-md">
            <h3 className="flex items-center gap-space-xs font-headline-sm text-headline-sm text-on-surface mb-space-md">
              <span className="material-symbols-outlined text-primary text-[20px]">description</span>
              Survey Metadata
            </h3>
            <div className="flex flex-col gap-space-xs">
              <Row label="Survey ID" value={report.survey_id} mono />
              <Row label="Survey Name" value={report.survey_name} />
              <Row label="Sensor" value={survey.sensor_name || 'Not recorded'} />
              <Row
                label="Area Covered"
                value={summary.surveyAreaSqKm != null ? `${summary.surveyAreaSqKm.toFixed(3)} km²` : 'N/A (no meters_per_pixel)'}
              />
              <Row label="Total Targets" value={report.target_count} last />
            </div>
          </div>

          <div className="bg-surface-container rounded-DEFAULT p-space-lg shadow-md">
            <h3 className="flex items-center gap-space-xs font-headline-sm text-headline-sm text-on-surface mb-space-md">
              <span className="material-symbols-outlined text-primary text-[20px]">query_stats</span>
              Risk Summary
            </h3>
            <div className="flex flex-col gap-space-sm">
              {LEVELS.map((level) => (
                <div key={level} className="flex items-center gap-space-sm">
                  <span className={`w-24 shrink-0 text-center px-space-xs py-1 rounded-full font-label-md text-label-md font-bold uppercase ${LEVEL_BADGE[level]}`}>
                    {level === 'pending' ? 'PENDING' : level}
                  </span>
                  <div className="flex-1 h-2 bg-surface-container-lowest rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${LEVEL_BAR[level]}`}
                      style={{ width: counts.total ? `${(counts[level] / counts.total) * 100}%` : '0%' }}
                    />
                  </div>
                  <span className="font-telemetry-sm text-telemetry-sm text-on-surface font-bold w-6 text-right">{counts[level]}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

const Row = ({ label, value, mono, last }) => (
  <div className={`flex justify-between items-center pb-space-xs ${last ? '' : 'border-b border-surface-container-highest'}`}>
    <span className="font-label-md text-label-md text-on-surface-variant uppercase">{label}</span>
    <span className={`text-on-surface font-semibold text-right ${mono ? 'font-telemetry-sm text-telemetry-sm' : 'font-body-sm text-body-sm'}`}>{value}</span>
  </div>
);

const EmptyState = ({ text, tone }) => (
  <div className="max-w-max-content-width mx-auto px-margin-desktop py-space-2xl flex flex-col items-center justify-center gap-space-sm text-center">
    <span className={`material-symbols-outlined text-[36px] ${tone || 'text-on-surface-variant'}`}>description</span>
    <p className={`font-body-sm text-body-sm ${tone || 'text-on-surface-variant'}`}>{text}</p>
  </div>
);

export default Report;
