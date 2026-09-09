import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { getCurrentJobId, getCurrentSurveyId, listSurveys, setCurrentJobId, setCurrentSurveyId } from '../api';

// The real backend is per-survey; this context is the frontend's only
// notion of "which survey am I looking at right now" (and, since the
// Ingest -> Pipeline -> Triage flow spans routes, "which processing job is
// in flight"). Selected in Layout.jsx's header or set automatically after a
// new upload (Ingest screen) -- persisted to localStorage so it survives a
// reload or a direct visit to /pipeline.
const SurveyContext = createContext(null);

export function SurveyProvider({ children }) {
  const [surveyId, setSurveyIdState] = useState(() => getCurrentSurveyId());
  const [jobId, setJobIdState] = useState(() => getCurrentJobId());
  const [surveys, setSurveys] = useState([]);
  const [loadingSurveys, setLoadingSurveys] = useState(true);

  const refreshSurveys = useCallback(async () => {
    setLoadingSurveys(true);
    try {
      const { items } = await listSurveys({ limit: 100 });
      setSurveys(items);
      return items;
    } finally {
      setLoadingSurveys(false);
    }
  }, []);

  useEffect(() => {
    refreshSurveys();
  }, [refreshSurveys]);

  const selectSurvey = useCallback((id) => {
    setCurrentSurveyId(id);
    setSurveyIdState(id);
  }, []);

  const selectJob = useCallback((id) => {
    setCurrentJobId(id);
    setJobIdState(id);
  }, []);

  return (
    <SurveyContext.Provider
      value={{ surveyId, jobId, surveys, loadingSurveys, selectSurvey, selectJob, refreshSurveys }}
    >
      {children}
    </SurveyContext.Provider>
  );
}

export function useSurvey() {
  const ctx = useContext(SurveyContext);
  if (!ctx) throw new Error('useSurvey must be used within a SurveyProvider');
  return ctx;
}
