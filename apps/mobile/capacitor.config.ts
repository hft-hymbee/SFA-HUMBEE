import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.humbee.sfa",
  appName: "Humbee GO",
  webDir: "../web/out",
  bundledWebRuntime: false,
  server: {
    hostname: "localhost",
    androidScheme: "https",
  },
  android: {
    allowMixedContent: false,
  },
  ios: {
    contentInset: "always",
    scrollEnabled: true,
  },
  plugins: {
    StatusBar: {
      overlaysWebView: false,
    },
  },
};

export default config;