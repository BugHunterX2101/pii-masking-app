import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import { WrappedApp } from './App';
import { Auth0Provider } from '@auth0/auth0-react';

const root = ReactDOM.createRoot(document.getElementById('root'));

root.render(
  <React.StrictMode>
    <Auth0Provider
      domain="dev-ro5w3rfa3erdaxmg.us.auth0.com"
      clientId="ILdcyEyMGFOA5U9WE3iLUIumFlOqzk9E"
      authorizationParams={{
        redirect_uri: window.location.origin,
        scope: "openid profile email"
      }}
    >
      <WrappedApp />
    </Auth0Provider>
  </React.StrictMode>
);