import { Capacitor, registerPlugin } from "@capacitor/core";
import { Geolocation } from "@capacitor/geolocation";

export {
  getConnectivitySnapshot,
  getServerConnectivitySnapshot,
  subscribeToConnectivity,
  useConnectivity,
} from "./connectivity";
export { subscribeToHardwareBack } from "./hardware-back";

interface NativeSettingsPlugin {
  openLocationPermissionSettings(): Promise<void>;
}

const NativeSettings = registerPlugin<NativeSettingsPlugin>("NativeSettings");

export interface GeoCoordinates {
  latitude: number;
  longitude: number;
  accuracyMeters: number;
  capturedAt: number;
}

interface ReverseGeocodeResult {
  locality?: string;
  city?: string;
  principalSubdivision?: string;
  postcode?: string;
  countryName?: string;
  localityInfo?: {
    administrative?: Array<{
      name?: string;
      adminLevel?: number;
    }>;
    informative?: Array<{
      name?: string;
      description?: string;
    }>;
  };
}

export interface KeyValueStore {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
  removeItem(key: string): Promise<void>;
}

export interface DeviceCapabilities {
  getCurrentLocation(): Promise<GeoCoordinates>;
  getCameraStream(constraints?: MediaStreamConstraints): Promise<MediaStream>;
  storage: KeyValueStore;
}

export class CapabilityUnavailableError extends Error {
  constructor(capabilityName: string) {
    super(`${capabilityName} capability is unavailable in this environment.`);
    this.name = "CapabilityUnavailableError";
  }
}

export async function openLocationPermissionSettings(): Promise<boolean> {
  if (!Capacitor.isNativePlatform() || Capacitor.getPlatform() !== "android") {
    return false;
  }

  await NativeSettings.openLocationPermissionSettings();
  return true;
}

export async function getCurrentDeviceLocation(): Promise<GeoCoordinates> {
  if (Capacitor.isNativePlatform()) {
    const currentPermission = await Geolocation.checkPermissions();
    if (currentPermission.location !== "granted") {
      const requestedPermission = await Geolocation.requestPermissions({
        permissions: ["location"],
      });
      if (requestedPermission.location !== "granted") {
        throw new CapabilityUnavailableError("geolocation");
      }
    }
  }

  const position = await Geolocation.getCurrentPosition({
    enableHighAccuracy: true,
    timeout: 15_000,
    maximumAge: 0,
  });

  return {
    latitude: position.coords.latitude,
    longitude: position.coords.longitude,
    accuracyMeters: position.coords.accuracy,
    capturedAt: position.timestamp,
  };
}

export async function getCurrentLocationLabel({
  latitude,
  longitude,
}: GeoCoordinates): Promise<string> {
  const url = new URL("https://api.bigdatacloud.net/data/reverse-geocode-client");
  url.searchParams.set("latitude", latitude.toString());
  url.searchParams.set("longitude", longitude.toString());
  url.searchParams.set("localityLanguage", "en");

  const response = await fetch(url);
  if (!response.ok) {
    throw new CapabilityUnavailableError("reverse geocoding");
  }

  const result = (await response.json()) as ReverseGeocodeResult;
  const broadLocations = [
    result.city,
    result.principalSubdivision,
    result.countryName,
  ];
  const detailedLocality = [
    result.locality,
    ...(result.localityInfo?.administrative ?? [])
      .filter(({ adminLevel }) => adminLevel !== undefined && adminLevel >= 8)
      .reverse()
      .map(({ name }) => name),
    ...(result.localityInfo?.informative ?? [])
      .filter(({ description }) =>
        /locality|neighbou?rhood|suburb|village|town/i.test(description ?? ""),
      )
      .reverse()
      .map(({ name }) => name),
  ].find((name) => Boolean(name) && !broadLocations.includes(name));
  const parts = [
    detailedLocality ?? result.locality,
    result.city,
    result.principalSubdivision,
    result.postcode,
  ].filter((part, index, values): part is string =>
    Boolean(part) && values.indexOf(part) === index,
  );
  const label = parts.join(", ") || result.countryName;
  if (!label) {
    throw new CapabilityUnavailableError("reverse geocoding");
  }

  return label;
}

export interface BrowserCapabilityDependencies {
  geolocation?: Pick<Geolocation, "getCurrentPosition">;
  mediaDevices?: Pick<MediaDevices, "getUserMedia">;
  storage?: Pick<Storage, "getItem" | "setItem" | "removeItem">;
}

function defaultDependencies(): BrowserCapabilityDependencies {
  const isBrowser = typeof window !== "undefined";
  return {
    geolocation: isBrowser ? window.navigator.geolocation : undefined,
    mediaDevices: isBrowser ? window.navigator.mediaDevices : undefined,
    storage: isBrowser ? window.localStorage : undefined,
  };
}

export function createBrowserCapabilities(
  dependencies: BrowserCapabilityDependencies = defaultDependencies(),
): DeviceCapabilities {
  const storage: KeyValueStore = {
    async getItem(key) {
      if (!dependencies.storage) {
        throw new CapabilityUnavailableError("storage");
      }
      return dependencies.storage.getItem(key);
    },
    async setItem(key, value) {
      if (!dependencies.storage) {
        throw new CapabilityUnavailableError("storage");
      }
      dependencies.storage.setItem(key, value);
    },
    async removeItem(key) {
      if (!dependencies.storage) {
        throw new CapabilityUnavailableError("storage");
      }
      dependencies.storage.removeItem(key);
    },
  };

  return {
    async getCurrentLocation() {
      if (!dependencies.geolocation) {
        throw new CapabilityUnavailableError("geolocation");
      }

      return new Promise<GeoCoordinates>((resolve, reject) => {
        dependencies.geolocation?.getCurrentPosition(
          (position) =>
            resolve({
              latitude: position.coords.latitude,
              longitude: position.coords.longitude,
              accuracyMeters: position.coords.accuracy,
              capturedAt: position.timestamp,
            }),
          () => reject(new CapabilityUnavailableError("geolocation")),
          { enableHighAccuracy: true, timeout: 12_000, maximumAge: 0 },
        );
      });
    },

    async getCameraStream(constraints = { video: true }) {
      if (!dependencies.mediaDevices) {
        throw new CapabilityUnavailableError("camera");
      }
      return dependencies.mediaDevices.getUserMedia(constraints);
    },

    storage,
  };
}
