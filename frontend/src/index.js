import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import { WrappedApp } from './App';
import { Auth0Provider } from '@auth0/auth0-react';

// Auth0 tenant is configurable so the same build can point at any tenant.
// Defaults keep the demo tenant working out of the box.
const auth0Domain = process.env.REACT_APP_AUTH0_DOMAIN || 'dev-ro5w3rfa3erdaxmg.us.auth0.com';
const auth0ClientId = process.env.REACT_APP_AUTH0_CLIENT_ID || 'ILdcyEyMGFOA5U9WE3iLUIumFlOqzk9E';

const root = ReactDOM.createRoot(document.getElementById('root'));

root.render(
  <React.StrictMode>
    <Auth0Provider
      domain={auth0Domain}
      clientId={auth0ClientId}
      authorizationParams={{
        redirect_uri: window.location.origin,
        scope: "openid profile email"
      }}
    >
      <WrappedApp />
    </Auth0Provider>
  </React.StrictMode>
);
