import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import ScrollToTop from './components/ScrollToTop';
import { SurveyProvider } from './context/SurveyContext';
import Landing from './pages/Landing';
import MissionOverview from './pages/MissionOverview';
import SonarViewer from './pages/SonarViewer';
import Pipeline from './pages/Pipeline';
import Triage from './pages/Triage';
import TargetDetails from './pages/TargetDetails';
import PriorityMap from './pages/PriorityMap';
import MissionPlanner from './pages/MissionPlanner';
import Report from './pages/Report';
import More from './pages/More';

function App() {
  return (
    <SurveyProvider>
      <BrowserRouter>
        <ScrollToTop />
        <Routes>
          <Route path="/welcome" element={<Landing />} />
          <Route path="/" element={<Layout />}>
            <Route index element={<MissionOverview />} />
            <Route path="sonar" element={<SonarViewer />} />
            <Route path="pipeline" element={<Pipeline />} />
            <Route path="triage" element={<Triage />} />
            <Route path="target/:id" element={<TargetDetails />} />
            <Route path="map" element={<PriorityMap />} />
            <Route path="planner" element={<MissionPlanner />} />
            <Route path="report" element={<Report />} />
            <Route path="more" element={<More />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </SurveyProvider>
  );
}

export default App;
