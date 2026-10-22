"use client";

import {
  GeoJSONSource,
  LngLatBounds,
  Map as MapLibreMap,
  Marker,
  NavigationControl,
  Popup,
  setWorkerUrl,
} from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import "maplibre-gl/dist/maplibre-gl.css";
import styles from "./management.module.css";

export interface LivePositionMarker {
  id: string;
  name: string;
  initials: string;
  territory: string;
  punchIn: string;
  duty: "on" | "late" | "off";
  lat: number;
  lng: number;
  pin?: "stop" | "current";
  caption?: string;
}

const OPENFREEMAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";
const BENGALURU: [number, number] = [77.5946, 12.9716];
const PATH_SOURCE = "humbee-day-path";
const PATH_CASING = "humbee-day-path-casing";
const PATH_LINE = "humbee-day-path-line";
const OSRM_ENDPOINTS = [
  "https://router.project-osrm.org/route/v1/driving",
  "https://routing.openstreetmap.de/routed-car/route/v1/driving",
];

const routeCache = new Map<string, Array<[number, number]>>();
const NO_PATH: Array<[number, number]> = [];

function waypointKey(path: Array<[number, number]>) {
  return path.map(([lng, lat]) => `${lng.toFixed(5)},${lat.toFixed(5)}`).join(";");
}

async function fetchOsrm(path: Array<[number, number]>, signal: AbortSignal) {
  const coords = path.map(([lng, lat]) => `${lng},${lat}`).join(";");
  const query = "overview=full&geometries=geojson&steps=false";
  for (const base of OSRM_ENDPOINTS) {
    try {
      const response = await fetch(`${base}/${coords}?${query}`, { signal });
      if (!response.ok) continue;
      const body = await response.json() as {
        code?: string;
        routes?: Array<{ geometry?: { coordinates?: Array<[number, number]> } }>;
      };
      const coordinates = body.code === "Ok" ? body.routes?.[0]?.geometry?.coordinates : undefined;
      if (!coordinates || coordinates.length < 2) continue;
      return coordinates;
    } catch (error) {
      if (signal.aborted) throw error;
    }
  }
  return null;
}

async function fetchDrivingRoute(path: Array<[number, number]>, signal: AbortSignal) {
  const key = waypointKey(path);
  const cached = routeCache.get(key);
  if (cached) return cached;
  const direct = await fetchOsrm(path, signal);
  if (direct) {
    routeCache.set(key, direct);
    return direct;
  }
  const merged: Array<[number, number]> = [];
  for (let index = 0; index < path.length - 1; index += 1) {
    const from = path[index];
    const to = path[index + 1];
    if (!from || !to) continue;
    const leg = await fetchOsrm([from, to], signal);
    if (!leg) continue;
    if (merged.length) merged.pop();
    merged.push(...leg);
  }
  if (merged.length < 2) throw new Error("route unavailable");
  routeCache.set(key, merged);
  return merged;
}

setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");

function flattenBuildings(map: MapLibreMap) {
  for (const layer of map.getStyle()?.layers ?? []) {
    if (layer.type === "fill-extrusion") {
      map.removeLayer(layer.id);
    }
  }
  if (map.getLayer("building")) {
    map.setLayerZoomRange("building", 13, 24);
  }
}

function tokenColor(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function pinClass(marker: LivePositionMarker) {
  if (marker.pin === "stop") return styles.pinStop;
  if (marker.pin === "current") return styles.pinCurrent;
  return marker.duty === "late" ? styles.pinLate : styles.pinOn;
}

function createPin(marker: LivePositionMarker) {
  const el = document.createElement("div");
  el.className = `${styles.pin} ${pinClass(marker)}`;
  const label = document.createElement("span");
  label.textContent = marker.initials;
  el.append(label);
  return el;
}

function createPopup(marker: LivePositionMarker) {
  const root = document.createElement("div");
  const name = document.createElement("strong");
  name.textContent = marker.name;
  const territory = document.createElement("span");
  territory.textContent = marker.caption ?? marker.territory;
  root.append(name, territory);
  if (!marker.caption) {
    const punch = document.createElement("span");
    punch.textContent = marker.punchIn === "—" ? "No punch-in" : `In ${marker.punchIn}`;
    root.append(punch);
  }
  return root;
}

function fitToMarkers(map: MapLibreMap, markers: LivePositionMarker[], path: Array<[number, number]> = []) {
  const points = [
    ...markers.map((marker) => ({ lng: marker.lng, lat: marker.lat })),
    ...path.map(([lng, lat]) => ({ lng, lat })),
  ];
  if (!points.length) {
    map.jumpTo({ center: BENGALURU, zoom: 12, pitch: 0, bearing: 0 });
    return;
  }
  const only = points[0];
  if (points.length === 1 && only) {
    map.jumpTo({ center: [only.lng, only.lat], zoom: 14, pitch: 0, bearing: 0 });
    return;
  }
  const bounds = new LngLatBounds();
  points.forEach((point) => bounds.extend([point.lng, point.lat]));
  map.fitBounds(bounds, { padding: 36, maxZoom: 14, duration: 0, pitch: 0, bearing: 0 });
}

function pathData(path: Array<[number, number]>) {
  return {
    type: "Feature" as const,
    properties: {},
    geometry: {
      type: "LineString" as const,
      coordinates: path.length >= 2 ? path : [],
    },
  };
}

function applyPath(map: MapLibreMap, path: Array<[number, number]>) {
  if (!map.getStyle() || !map.isStyleLoaded()) return false;
  const data = pathData(path);
  const existing = map.getSource(PATH_SOURCE) as GeoJSONSource | undefined;
  if (existing) {
    existing.setData(data);
    return true;
  }
  if (path.length < 2) return true;
  map.addSource(PATH_SOURCE, { type: "geojson", data });
  map.addLayer({
    id: PATH_CASING,
    type: "line",
    source: PATH_SOURCE,
    layout: { "line-cap": "round", "line-join": "round" },
    paint: {
      "line-color": tokenColor("--color-white"),
      "line-width": 7,
      "line-opacity": 0.9,
    },
  });
  map.addLayer({
    id: PATH_LINE,
    type: "line",
    source: PATH_SOURCE,
    layout: { "line-cap": "round", "line-join": "round" },
    paint: {
      "line-color": tokenColor("--color-primary"),
      "line-width": 3.5,
    },
  });
  return true;
}

function whenStyleReady(map: MapLibreMap, fn: () => void) {
  if (map.isStyleLoaded()) {
    fn();
    return () => {};
  }
  map.once("load", fn);
  return () => {
    map.off("load", fn);
  };
}

function applyMarkers(map: MapLibreMap, markers: LivePositionMarker[], overlay: Marker[]) {
  overlay.splice(0).forEach((marker) => marker.remove());
  markers.forEach((item) => {
    const pin = new Marker({ element: createPin(item), anchor: "center" })
      .setLngLat([item.lng, item.lat])
      .setPopup(new Popup({ offset: item.pin ? 14 : 22, className: styles.markerPopup }).setDOMContent(createPopup(item)))
      .addTo(map);
    overlay.push(pin);
  });
}

export function LivePositionsMap({
  label,
  markers,
  path = NO_PATH,
}: {
  label?: string;
  markers: LivePositionMarker[];
  path?: Array<[number, number]>;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const overlayRef = useRef<Marker[]>([]);
  const markersRef = useRef(markers);
  const routeRef = useRef<Array<[number, number]>>([]);
  const [routeResult, setRouteResult] = useState<{
    key: string;
    route: Array<[number, number]>;
  } | null>(null);
  const pathKey = waypointKey(path);
  const route = path.length < 2
    ? NO_PATH
    : routeCache.get(pathKey)
      ?? (routeResult?.key === pathKey ? routeResult.route : NO_PATH);

  useEffect(() => {
    markersRef.current = markers;
  }, [markers]);

  useEffect(() => {
    routeRef.current = route;
  }, [route]);

  useEffect(() => {
    if (path.length < 2 || routeCache.has(pathKey)) return;
    const controller = new AbortController();
    fetchDrivingRoute(path, controller.signal).then(
      (geometry) => {
        if (!controller.signal.aborted) {
          setRouteResult({ key: pathKey, route: geometry });
        }
      },
      (error: unknown) => {
        if (controller.signal.aborted) return;
        if (error instanceof DOMException && error.name === "AbortError") return;
      },
    );
    return () => controller.abort();
  }, [path, pathKey]);

  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;
    const overlay: Marker[] = [];
    overlayRef.current = overlay;
    const map = new MapLibreMap({
      container: node,
      style: OPENFREEMAP_STYLE,
      center: BENGALURU,
      zoom: 12,
      pitch: 0,
      bearing: 0,
      maxPitch: 0,
      dragRotate: false,
      touchPitch: false,
      scrollZoom: false,
      attributionControl: { compact: true },
    });
    map.dragRotate.disable();
    map.touchZoomRotate.disableRotation();
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    mapRef.current = map;
    const onStyleLoad = () => flattenBuildings(map);
    const onLoad = () => {
      flattenBuildings(map);
      applyMarkers(map, markersRef.current, overlay);
      applyPath(map, routeRef.current);
      fitToMarkers(map, markersRef.current, routeRef.current);
    };
    map.on("style.load", onStyleLoad);
    map.on("load", onLoad);
    const frame = node.parentElement;
    let lastWidth = 0;
    let lastHeight = 0;
    const observer = new ResizeObserver((entries) => {
      const size = entries[0]?.contentRect;
      if (!size) return;
      if (Math.abs(size.width - lastWidth) < 1 && Math.abs(size.height - lastHeight) < 1) return;
      lastWidth = size.width;
      lastHeight = size.height;
      map.resize();
    });
    if (frame) observer.observe(frame);
    return () => {
      map.off("style.load", onStyleLoad);
      map.off("load", onLoad);
      observer.disconnect();
      overlay.splice(0).forEach((marker) => marker.remove());
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    return whenStyleReady(map, () => {
      if (mapRef.current !== map) return;
      applyMarkers(map, markers, overlayRef.current);
      fitToMarkers(map, markers, routeRef.current);
    });
  }, [markers]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    let cancelled = false;
    const paint = () => {
      if (cancelled || mapRef.current !== map) return;
      if (!applyPath(map, route)) {
        map.once("idle", paint);
        return;
      }
      fitToMarkers(map, markersRef.current, route);
    };
    const stopReady = whenStyleReady(map, paint);
    return () => {
      cancelled = true;
      stopReady();
      map.off("idle", paint);
    };
  }, [route]);

  return (
    <div className={styles.mapFrame}>
      <div className={styles.mapCanvas} ref={containerRef} />
      {label ? <p className={styles.mapLabel}>{label}</p> : null}
    </div>
  );
}
