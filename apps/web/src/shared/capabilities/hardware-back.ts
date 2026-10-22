"use client";

import { App } from "@capacitor/app";
import { Capacitor } from "@capacitor/core";

export const hardwareBackEventName = "humbee:hardware-back";

export function subscribeToHardwareBack() {
  if (typeof window === "undefined") {
    return () => {};
  }
  if (!Capacitor.isNativePlatform() || Capacitor.getPlatform() !== "android") {
    return () => {};
  }

  const listener = App.addListener("backButton", ({ canGoBack }) => {
    const event = new CustomEvent(hardwareBackEventName, { cancelable: true });
    if (!window.dispatchEvent(event)) return;
    if (canGoBack) {
      window.history.back();
    } else {
      void App.minimizeApp();
    }
  });

  return () => {
    void listener.then((handle) => handle.remove());
  };
}
