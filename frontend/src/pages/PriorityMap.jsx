import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { useNavigate } from 'react-router-dom';
import { useSurvey } from '../context/SurveyContext';
import SubHeader from '../components/SubHeader';
import { getSurvey, getSurveyTargets } from '../api';

// Marker colors match the v2 design tokens' risk palette.
const createIcon = (color, isPulse = false) =>
  L.divIcon({
    className: 'custom-icon',
    html: `<div style="background-color: ${color}; width: 20px; height: 20px; border-radius: 50%; border: 2px solid #dfe2ef; box-shadow: 0 0 12px ${color};" class="${isPulse ? 'pulse-anim' : ''}"></div>`,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  });

const icons = {
  CRITICAL: createIcon('#ffb4ab', true),
  HIGH: createIcon('#ffb2b7'),
  MEDIUM: createIcon('#6fffdb'),
  LOW: createIcon('#84948e'),
};
const pendingIcon = createIcon('#3b4a45');

const PriorityMap = () => {
  const { surveyId } = useSurvey();
  const [targets, setTargets] = useState(null);
  const [survey, setSurvey] = useState(null);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!surveyId) {
      setTargets(null);
      setSurvey(null);
      return;
    }
    setError(null);
    setTargets(null);
    Promise.all([getSurveyTargets(surveyId), getSurvey(surveyId)])
      .then(([rows, s]) => {
        setTargets(rows);
        setSurvey(s);
      })
      .catch((err) => setError(err.message));
  }, [surveyId]);

  if (!surveyId) {
    return (
      <>
        <SubHeader pageLabel="Priority Map" title="Priority Map" />
        <EmptyState text="No survey selected. Upload or select one from the header." />
      </>
    );
  }
  if (error) {
    return (
      <>
        <SubHeader pageLabel="Priority Map" title="Priority Map" />
        <EmptyState text={error} tone="text-error" />
      </>
    );
  }
  if (!targets) {
    return (
      <>
        <SubHeader pageLabel="Priority Map" title="Priority Map" />
        <EmptyState text="Loading priority map..." />
      </>
    );
  }

  const geolocated = targets.filter((t) => t.latitude != null && t.longitude != null);
  const center =
    geolocated.length > 0
      ? [geolocated[0].latitude, geolocated[0].longitude]
      : survey?.origin_latitude != null && survey?.origin_longitude != null
        ? [survey.origin_latitude, survey.origin_longitude]
        : [0, 0];

  return (
    <>
      <SubHeader pageLabel="Priority Map" title="Priority Map" />
      <div className="max-w-max-content-width mx-auto px-margin-desktop py-space-xl flex flex-col gap-space-md">
        <p className="font-body-md text-body-md text-on-surface-variant">
          Real target positions colored by ecological risk level.{' '}
          {targets.length - geolocated.length > 0
            ? `${targets.length - geolocated.length} target(s) have no coordinates yet and aren't shown.`
            : ''}
        </p>

        {geolocated.length === 0 ? (
          <EmptyState text="No geolocated targets yet -- upload a survey with origin coordinates + meters_per_pixel to see it here." inline />
        ) : (
          <div className="rounded-DEFAULT overflow-hidden shadow-lg" style={{ height: '65vh' }}>
            {/* CartoDB's free anonymous dark_all tiles now render an "API KEY
                REQUIRED" watermark -- pre-existing, not a regression. Real
                target markers still render correctly on top. */}
            <MapContainer center={center} zoom={14} style={{ height: '100%', width: '100%' }}>
              <TileLayer
                url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
              />
              {geolocated.map((target) => (
                <Marker
                  key={target.target_id}
                  position={[target.latitude, target.longitude]}
                  icon={target.risk_level ? icons[target.risk_level] || pendingIcon : pendingIcon}
                  eventHandlers={{ click: () => navigate(`/target/${target.target_id}`) }}
                >
                  <Popup>
                    <div className="font-body-sm text-body-sm">
                      <div className="font-headline-sm text-headline-sm mb-1">
                        {(target.debris_subclass || target.classification || 'uncertain').replace(/_/g, ' ')}
                      </div>
                      <div>
                        Risk: <strong>{target.risk_level || 'pending'}</strong>
                      </div>
                      <div>
                        Priority action: <strong>{target.priority_action || 'pending'}</strong>
                      </div>
                      {target.inside_mpa != null && (
                        <div>
                          Inside MPA: <strong>{target.inside_mpa ? 'yes' : 'no'}</strong>
                        </div>
                      )}
                      {target.inside_reef != null && (
                        <div>
                          Inside reef: <strong>{target.inside_reef ? 'yes' : 'no'}</strong>
                        </div>
                      )}
                    </div>
                  </Popup>
                </Marker>
              ))}
            </MapContainer>
          </div>
        )}
      </div>
    </>
  );
};

const EmptyState = ({ text, tone, inline }) => (
  <div className={`flex flex-col items-center justify-center gap-space-sm text-center ${inline ? 'py-space-xl' : 'max-w-max-content-width mx-auto px-margin-desktop py-space-2xl'}`}>
    <span className={`material-symbols-outlined text-[36px] ${tone || 'text-on-surface-variant'}`}>map</span>
    <p className={`font-body-sm text-body-sm ${tone || 'text-on-surface-variant'}`}>{text}</p>
  </div>
);

export default PriorityMap;
