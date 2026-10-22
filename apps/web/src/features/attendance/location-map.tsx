"use client";

import { Map as MapLibreMap, Marker, setWorkerUrl } from "maplibre-gl";
import { useEffect, useRef } from "react";
import "maplibre-gl/dist/maplibre-gl.css";

const OPENFREEMAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";

setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");

export function PunchLocationMap({
  lat,
  lng,
  captured,
  label,
}: {
  lat: number;
  lng: number;
  captured: boolean;
  label: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markerRef = useRef<Marker | null>(null);

  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;
    const map = new MapLibreMap({
      container: node,
      style: OPENFREEMAP_STYLE,
      center: [lng, lat],
      zoom: 14,
      pitch: 0,
      bearing: 0,
      maxPitch: 0,
      dragRotate: false,
      interactive: false,
      attributionControl: { compact: true },
    });
    map.dragRotate.disable();
    map.touchZoomRotate.disableRotation();
    mapRef.current = map;
    const frame = node.parentElement;
    const observer = new ResizeObserver(() => map.resize());
    if (frame) observer.observe(frame);
    else observer.observe(node);
    return () => {
      observer.disconnect();
      markerRef.current?.remove();
      markerRef.current = null;
      map.remove();
      mapRef.current = null;
    };
  }, [lat, lng]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      if (mapRef.current !== map) return;
      if (captured) {
        if (!markerRef.current) {
          markerRef.current = new Marker({ color: "var(--color-error)" })
            .setLngLat([lng, lat])
            .addTo(map);
        } else {
          markerRef.current.setLngLat([lng, lat]);
        }
        map.easeTo({ center: [lng, lat], zoom: 16, pitch: 0, bearing: 0, duration: 700 });
        return;
      }
      markerRef.current?.remove();
      markerRef.current = null;
    };
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
    return () => {
      map.off("load", apply);
    };
  }, [captured, lat, lng]);

  return (
    <div
      className="sp-punch-map"
      style={{
        background: "var(--color-neutral-100)",
        borderRadius: "inherit",
        overflow: "hidden",
        position: "relative",
      }}
    >
      <div ref={containerRef} style={{ height: "100%", width: "100%" }} />
      <div
        className="sp-meta sp-meta--strong"
        style={{
          alignItems: "center",
          background: "color-mix(in srgb, var(--surface-card) 94%, transparent)",
          border: "thin solid var(--color-neutral-300)",
          borderRadius: "var(--radius-md)",
          bottom: "var(--space-sm)",
          color: "var(--color-text-primary)",
          display: "flex",
          gap: "var(--space-xs)",
          left: "var(--space-sm)",
          maxWidth: "calc(100% - var(--space-2xl))",
          overflow: "hidden",
          padding: "var(--space-xs) var(--space-sm)",
          position: "absolute",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          zIndex: 1,
        }}
        title={label}
      >
        <span
          aria-hidden
          style={{
            background: "var(--color-error)",
            borderRadius: "var(--radius-pill)",
            flexShrink: 0,
            height: "var(--space-sm)",
            width: "var(--space-sm)",
          }}
        />
        <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{label}</span>
      </div>
    </div>
  );
}
