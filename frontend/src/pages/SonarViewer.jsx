import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSurvey } from '../context/SurveyContext';
import SubHeader from '../components/SubHeader';
import { createSurvey, processSurvey, uploadSurveyFile } from '../api';

const EMPTY_FORM = {
  name: '',
  file: null,
  origin_latitude: '',
  origin_longitude: '',
  meters_per_pixel: '',
  sensor_name: '',
};

const SonarViewer = () => {
  const { selectSurvey, selectJob, refreshSurveys } = useSurvey();
  const navigate = useNavigate();

  const [form, setForm] = useState(EMPTY_FORM);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!form.file) {
      setPreviewUrl(null);
      return undefined;
    }
    const url = URL.createObjectURL(form.file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [form.file]);

  const reset = () => {
    setForm(EMPTY_FORM);
    setError(null);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!form.file || !form.name.trim()) return;

    setSubmitting(true);
    setError(null);
    try {
      const survey = await createSurvey(form.name.trim());
      await uploadSurveyFile(survey.id, form.file, {
        origin_latitude: form.origin_latitude ? Number(form.origin_latitude) : undefined,
        origin_longitude: form.origin_longitude ? Number(form.origin_longitude) : undefined,
        meters_per_pixel: form.meters_per_pixel ? Number(form.meters_per_pixel) : undefined,
        sensor_name: form.sensor_name || undefined,
      });
      const job = await processSurvey(survey.id, {
        startLatitude: form.origin_latitude ? Number(form.origin_latitude) : undefined,
        startLongitude: form.origin_longitude ? Number(form.origin_longitude) : undefined,
      });

      selectSurvey(survey.id);
      selectJob(job.id);
      await refreshSurveys();
      navigate('/pipeline');
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const readyToCommit = form.file && form.name.trim();
  const statusChip = submitting
    ? { label: 'COMMITTING...', tone: 'bg-primary-container/15 text-primary' }
    : readyToCommit
      ? { label: 'READY TO COMMIT', tone: 'bg-primary-container/15 text-primary' }
      : { label: 'AWAITING FILE & METADATA', tone: 'bg-surface-container-high text-tertiary' };

  return (
    <>
      <SubHeader
        pageLabel="Ingest"
        title="Ingest & Acoustic Metadata"
        right={
          <div className={`flex items-center gap-space-xs px-space-sm py-space-xs rounded-full shadow-sm ${statusChip.tone}`}>
            <span className="w-2 h-2 rounded-full bg-current animate-pulse" />
            <span className="font-telemetry-sm text-telemetry-sm uppercase tracking-wider font-semibold">
              {statusChip.label}
            </span>
          </div>
        }
      />

      <div className="max-w-max-content-width mx-auto px-margin-desktop py-space-xl">
        <form onSubmit={handleSubmit}>
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-gutter-desktop items-start">
            {/* LEFT COLUMN */}
            <div className="lg:col-span-7 flex flex-col gap-space-xl">
              <div className="bg-surface-container rounded-DEFAULT p-space-lg shadow-md flex flex-col gap-space-md">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-space-xs">
                    <span className="material-symbols-outlined text-primary text-[22px]">upload_file</span>
                    <h2 className="font-headline-sm text-headline-sm text-on-surface">Upload Sonar Bathymetry &amp; Acoustic Files</h2>
                  </div>
                  <span className="font-telemetry-sm text-telemetry-sm text-on-surface-variant">PNG / JPG / TIFF</span>
                </div>

                <label htmlFor="sonar-file" className="cursor-pointer">
                  {previewUrl ? (
                    <div className="relative rounded-DEFAULT overflow-hidden bg-surface-container-lowest h-64">
                      <img src={previewUrl} alt="Selected sonar file preview" className="w-full h-full object-cover" />
                    </div>
                  ) : (
                    <div className="group relative rounded-DEFAULT bg-surface-container-lowest p-space-xl flex flex-col items-center justify-center text-center transition-all hover:bg-surface-container-low">
                      <div className="w-12 h-12 rounded-full bg-surface-container-high flex items-center justify-center text-primary group-hover:scale-110 group-hover:bg-primary group-hover:text-on-primary transition-all mb-space-xs shadow-sm">
                        <span className="material-symbols-outlined text-[26px]">cloud_upload</span>
                      </div>
                      <div className="font-label-lg text-label-lg text-on-surface mb-space-2xs">
                        Drop raw hydrographic data or <span className="text-primary underline">browse filesystem</span>
                      </div>
                      <p className="font-body-sm text-body-sm text-on-surface-variant max-w-md">
                        Supported formats: PNG, JPG, JPEG, TIFF only (XTF/JSF unsupported). Maximum file size limit: 200 MB.
                      </p>
                    </div>
                  )}
                </label>
                <input
                  id="sonar-file"
                  type="file"
                  required
                  accept=".png,.jpg,.jpeg,.tif,.tiff"
                  className="hidden"
                  onChange={(e) => setForm((f) => ({ ...f, file: e.target.files?.[0] || null }))}
                />

                {form.file && (
                  <div className="rounded-full bg-surface-container-high px-space-md py-space-xs flex items-center justify-between gap-space-sm shadow-sm">
                    <div className="flex items-center gap-space-xs min-w-0">
                      <span className="material-symbols-outlined text-primary text-[20px] shrink-0">data_object</span>
                      <span className="font-telemetry-md text-telemetry-md text-on-surface font-medium truncate">{form.file.name}</span>
                      <span className="font-telemetry-sm text-telemetry-sm text-primary shrink-0 px-space-xs py-space-2xs rounded-full bg-surface-container-lowest">
                        {(form.file.size / (1024 * 1024)).toFixed(1)} MB
                      </span>
                    </div>
                    <div className="flex items-center gap-space-xs shrink-0">
                      <span className="material-symbols-outlined text-primary text-[18px]">check_circle</span>
                      <button
                        type="button"
                        aria-label="Remove File"
                        onClick={() => setForm((f) => ({ ...f, file: null }))}
                        className="text-on-surface-variant hover:text-error transition-colors p-space-2xs"
                      >
                        <span className="material-symbols-outlined text-[18px]">close</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>

              <div className="bg-surface-container rounded-DEFAULT p-space-lg shadow-md flex flex-col gap-space-lg">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-space-xs">
                    <span className="material-symbols-outlined text-primary text-[22px]">edit_document</span>
                    <h3 className="font-headline-sm text-headline-sm text-on-surface">Survey Parameters &amp; Metadata</h3>
                  </div>
                  <span className="font-telemetry-sm text-telemetry-sm text-on-surface-variant">USER INPUTS</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-space-md">
                  <Field label="Survey Name" required className="md:col-span-2">
                    <input
                      required
                      type="text"
                      placeholder="e.g. Pacific-Transect-04-Survey"
                      className={inputClass}
                      value={form.name}
                      onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                    />
                  </Field>
                  <Field label="Origin Latitude (°N/°S)" hint="(optional)">
                    <input
                      type="number"
                      step="any"
                      placeholder="e.g. 14.3522"
                      className={`${inputClass} font-telemetry-md`}
                      value={form.origin_latitude}
                      onChange={(e) => setForm((f) => ({ ...f, origin_latitude: e.target.value }))}
                    />
                  </Field>
                  <Field label="Origin Longitude (°E/°W)" hint="(optional)">
                    <input
                      type="number"
                      step="any"
                      placeholder="e.g. 144.5867"
                      className={`${inputClass} font-telemetry-md`}
                      value={form.origin_longitude}
                      onChange={(e) => setForm((f) => ({ ...f, origin_longitude: e.target.value }))}
                    />
                  </Field>
                  <Field label="Meters per Pixel" hint="(optional)">
                    <input
                      type="number"
                      step="any"
                      placeholder="e.g. 0.05"
                      className={`${inputClass} font-telemetry-md`}
                      value={form.meters_per_pixel}
                      onChange={(e) => setForm((f) => ({ ...f, meters_per_pixel: e.target.value }))}
                    />
                  </Field>
                  <Field label="Sensor Name" hint="(optional)">
                    <input
                      type="text"
                      placeholder="e.g. EdgeTech 4200"
                      className={inputClass}
                      value={form.sensor_name}
                      onChange={(e) => setForm((f) => ({ ...f, sensor_name: e.target.value }))}
                    />
                  </Field>
                </div>
                <p className="font-body-sm text-body-sm text-on-surface-variant">
                  Origin coordinates + meters/pixel are optional but required for geolocation -- without them, targets
                  are still detected and classified, just with no lat/lon (coordinate_source stays null).
                </p>
              </div>
            </div>

            {/* RIGHT COLUMN */}
            <div className="lg:col-span-5 flex flex-col gap-space-xl">
              <div className="bg-surface-container rounded-DEFAULT p-space-lg shadow-md flex flex-col gap-space-lg">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-space-xs">
                    <span className="material-symbols-outlined text-primary text-[22px]">description</span>
                    <h3 className="font-headline-sm text-headline-sm text-on-surface">Batch Summary &amp; Ingest Specs</h3>
                  </div>
                </div>
                <div className="flex flex-col gap-space-sm">
                  <span className="font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">Ingest Requirements</span>
                  <div className="flex flex-col gap-space-xs">
                    <SpecItem icon="image" title="Supported Image Formats" body="PNG, JPG, JPEG, TIFF. Raw sonar formats (XTF, JSF) must be converted prior to ingest." />
                    <SpecItem icon="folder_zip" title="Volume Limit" body="Maximum single-file upload size is 200 MB." />
                    <SpecItem icon="location_on" title="Georeferencing Accuracy" body="Origin lat/lng and meters per pixel provide the geodesic transform used for target geolocation." />
                  </div>
                </div>
                <div className="flex flex-col gap-space-sm">
                  <span className="font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">Pending Batch Summary</span>
                  <div className="bg-surface-container-lowest rounded-DEFAULT p-space-md flex flex-col gap-space-xs font-telemetry-sm text-telemetry-sm">
                    <SummaryRow label="Attached Files" value={form.file ? `1 File (${(form.file.size / (1024 * 1024)).toFixed(1)} MB)` : 'None'} />
                    <SummaryRow label="Survey Identifier" value={form.name || '--'} accent />
                    <SummaryRow
                      label="Origin Anchor"
                      value={form.origin_latitude && form.origin_longitude ? `${form.origin_latitude}°N, ${form.origin_longitude}°E` : 'Not set'}
                    />
                    <SummaryRow label="Resolution Scale" value={form.meters_per_pixel ? `${form.meters_per_pixel} m/px` : 'Not set'} last />
                  </div>
                </div>
                <div className="bg-surface-container-lowest p-space-md rounded-DEFAULT flex items-start gap-space-xs">
                  <span className="material-symbols-outlined text-secondary text-[20px] shrink-0 mt-0.5">info</span>
                  <p className="font-body-sm text-body-sm text-on-surface-variant">
                    Clicking &quot;Commit to Pipeline&quot; creates the survey, uploads the file, and dispatches the real
                    detection → classification → risk → priority pipeline (POST /surveys, then /upload, then /process).
                  </p>
                </div>
              </div>

              <div className="bg-surface-container rounded-DEFAULT p-space-md flex items-center justify-between gap-space-md shadow-md">
                <button
                  type="button"
                  onClick={reset}
                  className="px-space-lg py-space-xs rounded-full font-label-lg text-label-lg text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-all"
                >
                  Reset Ingest
                </button>
                <button
                  type="submit"
                  disabled={!readyToCommit || submitting}
                  className="px-space-xl py-space-xs rounded-full bg-primary-container text-on-primary-container font-label-lg text-label-lg font-bold hover:bg-primary-fixed hover:text-on-primary-fixed shadow-[0_0_20px_rgba(0,229,190,0.35)] disabled:opacity-40 disabled:shadow-none transition-all flex items-center gap-space-xs"
                >
                  <span>{submitting ? 'Committing...' : 'Commit to Pipeline'}</span>
                  {!submitting && <span className="material-symbols-outlined text-[18px]">arrow_forward</span>}
                </button>
              </div>

              {error && (
                <div className="bg-error-container text-on-error-container rounded-DEFAULT p-space-md font-body-sm text-body-sm">
                  {error}
                </div>
              )}
            </div>
          </div>
        </form>
      </div>
    </>
  );
};

const inputClass =
  'h-11 px-space-md bg-surface-container-lowest rounded-full border border-outline-variant/30 text-on-surface font-body-md focus:border-primary focus:outline-none placeholder:text-outline/60 w-full';

const Field = ({ label, required, hint, className = '', children }) => (
  <div className={`flex flex-col gap-space-2xs ${className}`}>
    <label className="font-label-md text-label-md text-on-surface-variant">
      {label} {required && <span className="text-error">*</span>}
      {hint && <span className="text-on-surface-variant font-telemetry-sm"> {hint}</span>}
    </label>
    {children}
  </div>
);

const SpecItem = ({ icon, title, body }) => (
  <div className="flex items-start gap-space-sm p-space-sm rounded-DEFAULT bg-surface-container-low shadow-sm">
    <span className="material-symbols-outlined text-primary text-[18px] shrink-0 mt-0.5">{icon}</span>
    <div className="flex flex-col gap-space-2xs min-w-0">
      <span className="font-label-md text-label-md text-on-surface">{title}</span>
      <span className="font-body-sm text-body-sm text-on-surface-variant">{body}</span>
    </div>
  </div>
);

const SummaryRow = ({ label, value, accent, last }) => (
  <div className={`flex justify-between items-center py-space-2xs ${last ? '' : 'border-b border-outline-variant/20'}`}>
    <span className="text-on-surface-variant">{label}</span>
    <span className={`font-medium truncate max-w-[180px] ${accent ? 'text-primary' : 'text-on-surface'}`}>{value}</span>
  </div>
);

export default SonarViewer;
