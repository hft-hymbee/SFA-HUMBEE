export interface GeoZoneOption {
  id: string;
  label: string;
}

export interface GeoStateOption {
  id: string;
  label: string;
  zoneId: string;
}

export interface GeoDistrictOption {
  id: string;
  label: string;
  stateId: string;
  outletCount?: number;
}

export interface GeoShopCategoryOption {
  id: string;
  label: string;
  outletShare?: number;
}

export interface GeoScopeValue {
  zones: string[];
  states: string[];
  districts: string[];
  shopCategories: string[];
}

export interface GeoScopeSelection extends GeoScopeValue {
  outletCount: number;
}

export interface GeoScopeAssignment {
  zones?: string[];
  states?: string[];
  districts?: string[];
  shopCategories?: string[];
}

export interface GeoScopeData {
  zones: GeoZoneOption[];
  states: GeoStateOption[];
  districts: GeoDistrictOption[];
  shopCategories: GeoShopCategoryOption[];
}

export interface GeoScopePickerProps {
  zones?: GeoZoneOption[];
  states?: GeoStateOption[];
  districts?: GeoDistrictOption[];
  shopCategories?: GeoShopCategoryOption[];
  value?: GeoScopeValue;
  defaultValue?: GeoScopeValue;
  assigned?: GeoScopeAssignment;
  onChange?: (selection: GeoScopeSelection) => void;
  getOutletCount?: (scope: GeoScopeValue, data: GeoScopeData) => number;
  cascadeChildren?: boolean;
  readOnly?: boolean;
  disabled?: boolean;
  showScopeSummary?: boolean;
  locale?: string;
  style?: React.CSSProperties;
}

export declare function GeoScopePicker(props: GeoScopePickerProps): JSX.Element;
export default GeoScopePicker;
