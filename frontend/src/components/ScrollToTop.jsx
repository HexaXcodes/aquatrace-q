import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

// react-router doesn't reset scroll position on navigation. Without this,
// navigating from a scrolled-down page (e.g. a Triage card) to a shorter
// page leaves the viewport scrolled past that page's fixed header, hiding
// its title/breadcrumb.
const ScrollToTop = () => {
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  return null;
};

export default ScrollToTop;
