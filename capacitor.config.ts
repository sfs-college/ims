import { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'in.sfscollege.blixtro',
  appName: 'Blixtro IMS',
  webDir: 'www',
  server: {
    // ── Points to live Django server ──────────────────────────────────
    url: 'https://blixtro.sfscollege.app/core/app/?app=1',
    cleartext: false,
    allowNavigation: [
      'blixtro.sfscollege.app',
      '*.firebaseapp.com',
      '*.googleapis.com',
      'accounts.google.com',
    ],
  },
  android: {
    allowMixedContent: false,
    captureInput: true,
    webContentsDebuggingEnabled: false,
    overrideUserAgent: "Mozilla/5.0 (Linux; Android 10; Mobile Safari/537.36) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36",
  },
  ios: {
    contentInset: 'automatic',
    scrollEnabled: true,
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 800,
      launchAutoHide: true,
      backgroundColor: '#0d0f14',
      androidSplashResourceName: 'splash',
      androidScaleType: 'CENTER_CROP',
      showSpinner: false,
    },
    StatusBar: {
      style: 'DARK',
      backgroundColor: '#0d0f14',
    },
  },
};

export default config;
