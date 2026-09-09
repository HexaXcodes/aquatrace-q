// Real fetch()-backed client for the AquaTrace-Q backend. Every export here
// used to be a hardcoded-mock/simulated-delay stub -- see git history for
// the previous shape if you need to compare.
//
// The real backend is per-survey (surveys own detections/targets/reports),
// but this frontend's pages were designed around one flat, global target
// list. `getCurrentSurveyId()` / `setCurrentSurveyId()` (persisted to
// localStorage) resolve that: pages read/act on whichever survey is
// "current," selected via the sidebar (see components/Layout.jsx) or set by
// uploading a new one in Sonar Viewer.

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

const CURRENT_SURVEY_KEY = 'aquatrace.currentSurveyId';
const CURRENT_JOB_KEY = 'aquatrace.currentJobId';

export class ApiError extends Error {
  constructor(message, { status, body } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  const contentType = response.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');
  const body = isJson ? await response.json().catch(() => null) : await response.text();

  if (!response.ok) {
    const message =
      (isJson && body && (body.message || (Array.isArray(body.detail) ? body.detail[0]?.msg : body.detail))) ||
      `${response.status} ${response.statusText}`;
    throw new ApiError(message, { status: response.status, body });
  }
  return body;
}

// --- Current-survey persistence -------------------------------------------

export function getCurrentSurveyId() {
  try {
    return localStorage.getItem(CURRENT_SURVEY_KEY);
  } catch {
    return null;
  }
}

export function setCurrentSurveyId(surveyId) {
  try {
    if (surveyId) localStorage.setItem(CURRENT_SURVEY_KEY, surveyId);
    else localStorage.removeItem(CURRENT_SURVEY_KEY);
  } catch {
    // localStorage unavailable (private browsing, etc.) -- current survey
    // just won't persist across reloads; not fatal.
  }
}

// The Ingest screen kicks off processing and immediately navigates to the
// Pipeline screen (rather than blocking on the full poll like the old
// combined uploadAndProcessSurvey() below) -- so "which job is the Pipeline
// screen watching" needs the same kind of persistence current-survey has,
// for a direct visit/reload of that route.
export function getCurrentJobId() {
  try {
    return localStorage.getItem(CURRENT_JOB_KEY);
  } catch {
    return null;
  }
}

export function setCurrentJobId(jobId) {
  try {
    if (jobId) localStorage.setItem(CURRENT_JOB_KEY, jobId);
    else localStorage.removeItem(CURRENT_JOB_KEY);
  } catch {
    // not fatal, see getCurrentSurveyId's note above
  }
}

// --- Surveys ----------------------------------------------------------------

export function listSurveys({ limit = 50, offset = 0 } = {}) {
  return apiFetch(`/surveys?limit=${limit}&offset=${offset}`);
}

export function getSurvey(surveyId) {
  return apiFetch(`/surveys/${surveyId}`);
}

export function getSurveyImageUrl(surveyId) {
  return `${API_BASE}/surveys/${surveyId}/image`;
}

export function createSurvey(name) {
  return apiFetch('/surveys', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
}

export function uploadSurveyFile(surveyId, file, metadata = {}) {
  const form = new FormData();
  form.append('file', file);
  for (const [key, value] of Object.entries(metadata)) {
    if (value !== null && value !== undefined && value !== '') form.append(key, value);
  }
  return apiFetch(`/surveys/${surveyId}/upload`, { method: 'POST', body: form });
}

export function processSurvey(surveyId, { startLatitude, startLongitude } = {}) {
  return apiFetch(`/surveys/${surveyId}/process`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      start_latitude: startLatitude ?? null,
      start_longitude: startLongitude ?? null,
    }),
  });
}

export function getJob(jobId) {
  return apiFetch(`/jobs/${jobId}`);
}

/** Polls GET /jobs/{id} until status is COMPLETED/FAILED (or timeout). */
export async function pollJob(jobId, { intervalMs = 1000, timeoutMs = 120000, onUpdate } = {}) {
  const startedAt = Date.now();
  // eslint-disable-next-line no-constant-condition
  while (true) {
    const job = await getJob(jobId);
    onUpdate?.(job);
    if (job.status === 'COMPLETED' || job.status === 'FAILED') return job;
    if (Date.now() - startedAt > timeoutMs) {
      throw new ApiError(`Processing job ${jobId} did not finish within ${timeoutMs}ms`, { status: 0 });
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}

/**
 * Real two-step (three-step, counting processing) replacement for the old
 * uploadSonar() mock: create a survey, attach the file, kick off the full
 * pipeline, and poll until it finishes. Sets the new survey as "current."
 */
export async function uploadAndProcessSurvey({ name, file, metadata = {}, onStageUpdate }) {
  const survey = await createSurvey(name);
  await uploadSurveyFile(survey.id, file, metadata);
  const startLatitude = metadata.origin_latitude;
  const startLongitude = metadata.origin_longitude;
  const job = await processSurvey(survey.id, { startLatitude, startLongitude });
  const finalJob = await pollJob(job.id, { onUpdate: onStageUpdate });
  setCurrentSurveyId(survey.id);
  return { survey, job: finalJob };
}

// --- Survey-wide report (one real endpoint that already flattens
// classification + risk + priority + environment per target -- see
// SurveyReportSchema / ReportRowSchema in app/schemas/report.py). Powers
// Mission Overview, Priority Map, and the Report page. -----------------------

export function getSurveyReport(surveyId) {
  return apiFetch(`/surveys/${surveyId}/report`);
}

function triggerBlobDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export async function downloadSurveyReportCsv(surveyId) {
  const response = await fetch(`${API_BASE}/surveys/${surveyId}/report.csv`);
  if (!response.ok) throw new ApiError(`Failed to fetch report.csv (${response.status})`, { status: response.status });
  const text = await response.text();
  triggerBlobDownload(new Blob([text], { type: 'text/csv' }), `${surveyId}_report.csv`);
}

export function downloadSurveyReportJson(surveyId, report) {
  triggerBlobDownload(
    new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }),
    `${surveyId}_report.json`,
  );
}

const RISK_LEVELS = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];

/**
 * Real replacement for getPrioritySummary(): buckets a survey's real report
 * rows by RiskScoreRead.level (see the "Badge mapping" decision -- risk
 * level, not priority.action, drives the CRITICAL/HIGH/MEDIUM/LOW badges
 * everywhere in this app now). Targets with no risk score yet (pipeline
 * hasn't reached RISK_SCORING) are counted separately as `pending`, never
 * silently folded into LOW.
 */
export async function getPrioritySummary(surveyId) {
  const [report, survey] = await Promise.all([getSurveyReport(surveyId), getSurvey(surveyId)]);

  const counts = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, pending: 0, total: report.targets.length };
  for (const row of report.targets) {
    if (row.risk_level && RISK_LEVELS.includes(row.risk_level)) counts[row.risk_level] += 1;
    else counts.pending += 1;
  }

  const surveyAreaSqKm =
    survey.width && survey.height && survey.meters_per_pixel
      ? (survey.width * survey.meters_per_pixel * (survey.height * survey.meters_per_pixel)) / 1e6
      : null;

  return { surveyAreaSqKm, counts, report, survey };
}

/** Real replacement for getDetections(): the survey's real target rows
 * (already risk/priority/environment-enriched by the report endpoint),
 * used for the Priority Map markers and the Sonar Viewer overlay. */
export async function getSurveyTargets(surveyId) {
  const report = await getSurveyReport(surveyId);
  return report.targets;
}

export function getSurveyDetections(surveyId) {
  return apiFetch(`/surveys/${surveyId}/detections`);
}

/** Raw TargetRead rows (id + bbox + classification, no risk/priority/
 * environment enrichment) -- used where a real target id + pixel bbox is
 * needed together, e.g. Sonar Viewer's detection overlay. */
export async function getSurveyTargetsRaw(surveyId) {
  const { items } = await apiFetch(`/surveys/${surveyId}/targets`);
  return items;
}

/**
 * Full per-target "dossier" for every target in a survey: the raw
 * TargetRead row (bbox, debris_subclass, classification, confidence,
 * coordinate_source) plus its risk/priority/environment, composed the same
 * way getTargetDetail() does for one target -- used by the Triage Overlay
 * page's target cards, which need the full breakdown inline, not just a
 * summary. Any target's risk/priority/environment can legitimately be null
 * (pipeline hasn't reached that stage yet) -- never thrown as an error.
 */
export async function getSurveyTargetDossiers(surveyId) {
  const targets = await getSurveyTargetsRaw(surveyId);
  return Promise.all(
    targets.map(async (target) => {
      const [risk, priority, environment] = await Promise.all([
        getOptional(`/targets/${target.id}/risk`),
        getOptional(`/targets/${target.id}/priority`),
        getOptional(`/targets/${target.id}/environment`),
      ]);
      return { target, risk, priority, environment };
    }),
  );
}

// --- Per-target detail (TargetDetails page) ---------------------------------

async function getOptional(path) {
  try {
    return await apiFetch(path);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

/**
 * Composes GET /targets/{id} + /risk + /priority + /environment into one
 * object, since TargetDetails needs all four together. Any of the latter
 * three can legitimately 404 if the survey hasn't finished processing yet
 * (see frontend-contract.md: render that honestly, not as an error) -- they
 * come back `null` rather than throwing.
 */
export async function getTargetDetail(targetId) {
  const [target, risk, priority, environment] = await Promise.all([
    apiFetch(`/targets/${targetId}`),
    getOptional(`/targets/${targetId}/risk`),
    getOptional(`/targets/${targetId}/priority`),
    getOptional(`/targets/${targetId}/environment`),
  ]);
  return { target, risk, priority, environment };
}

/** Repurposes the old (backend-less) classifyTarget(id): there is no
 * per-target reclassify endpoint, only the full survey pipeline. Re-runs it
 * for the target's parent survey (see the "Classify button" decision). */
export async function reprocessSurveyForTarget(targetId, { startLatitude, startLongitude } = {}, onStageUpdate) {
  const target = await apiFetch(`/targets/${targetId}`);
  const job = await processSurvey(target.survey_id, { startLatitude, startLongitude });
  return pollJob(job.id, { onUpdate: onStageUpdate });
}

// --- Missions -----------------------------------------------------------------

export function buildMission(surveyId, { startLatitude, startLongitude, vehicleSpeedMps } = {}) {
  return apiFetch(`/surveys/${surveyId}/missions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      start_latitude: startLatitude,
      start_longitude: startLongitude,
      vehicle_speed_mps: vehicleSpeedMps ?? null,
    }),
  });
}

export function getMission(missionId) {
  return apiFetch(`/missions/${missionId}`);
}
