import { type Configuration, type RedirectRequest, PublicClientApplication } from "@azure/msal-browser";

export const msalConfig: Configuration = {
  auth: {
    clientId: import.meta.env.VITE_AZURE_CLIENT_ID,
    authority: `https://login.microsoftonline.com/${import.meta.env.VITE_AZURE_TENANT_ID}`,
    redirectUri: window.location.origin,
    postLogoutRedirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: "localStorage",
  },
};

export const msalInstance = new PublicClientApplication(msalConfig);

// Initialize MSAL and handle any redirect tokens if we accidentally enter that flow
msalInstance.initialize().then(() => {
  msalInstance.handleRedirectPromise().catch(e => {
    console.error("MSAL Redirect Error:", e);
  });
});

export const loginRequest: RedirectRequest = {
  scopes: ["User.Read", "Tasks.ReadWrite", "openid", "profile", "offline_access"],
  prompt: "select_account",
};
