"use client";

import { useSyncExternalStore } from "react";

type ConnectivityListener = () => void;

const listeners = new Set<ConnectivityListener>();
let online = true;
let listening = false;

function updateConnectivity() {
  const nextOnline = window.navigator.onLine;
  if (nextOnline === online) {
    return;
  }
  online = nextOnline;
  listeners.forEach((listener) => listener());
}

function startListening() {
  if (listening) {
    return;
  }
  listening = true;
  online = window.navigator.onLine;
  window.addEventListener("online", updateConnectivity);
  window.addEventListener("offline", updateConnectivity);
}

function stopListening() {
  if (!listening || listeners.size > 0) {
    return;
  }
  listening = false;
  window.removeEventListener("online", updateConnectivity);
  window.removeEventListener("offline", updateConnectivity);
}

export function subscribeToConnectivity(listener: ConnectivityListener) {
  listeners.add(listener);
  startListening();
  return () => {
    listeners.delete(listener);
    stopListening();
  };
}

export function getConnectivitySnapshot() {
  return typeof window === "undefined" ? true : online;
}

export function getServerConnectivitySnapshot() {
  return true;
}

export function useConnectivity() {
  const isOnline = useSyncExternalStore(
    subscribeToConnectivity,
    getConnectivitySnapshot,
    getServerConnectivitySnapshot,
  );
  return {
    isOnline,
    writesEnabled: isOnline,
  };
}
