import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.autoaudiodiagnostics.diago",
  appName: "Autopilot",
  webDir: "dist",
  server: {
    // In production, the mobile app talks to the cloud API
    // During development, you can override with a local URL
    // url: "http://YOUR_DEV_MACHINE_IP:8000",
    androidScheme: "https",
  },
  plugins: {
    SplashScreen: {
      launchAutoHide: true,
      backgroundColor: "#1e1e2e",
      showSpinner: false,
    },
  },
};

export default config;
