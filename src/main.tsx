import { createRoot } from 'react-dom/client'
import { MsalProvider } from "@azure/msal-react";
import { msalInstance } from "./services/msalConfig";
import './index.css'
import App from './App.tsx'

// Initialize MSAL and handle any redirect responses before rendering
msalInstance.initialize().then(() => {
  msalInstance.handleRedirectPromise().then((response) => {
    if (response) {
      console.log("Login redirect successful:", response.account?.username);
    }

    createRoot(document.getElementById('root')!).render(
      <MsalProvider instance={msalInstance}>
        <App />
      </MsalProvider>
    )
  }).catch(err => {
    console.error("MSAL Redirect Error:", err);
    // Render even on error so user can see the login screen
    createRoot(document.getElementById('root')!).render(
      <MsalProvider instance={msalInstance}>
        <App />
      </MsalProvider>
    )
  });
});
