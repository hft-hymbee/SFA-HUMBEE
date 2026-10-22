import {
  getGeographyScopeApiV1OrgEmployeesEmployeeIdGeographyScopeGet,
  listGeographyDistrictsApiV1OrgGeographyDistrictsGet,
  listGeographyStatesApiV1OrgGeographyStatesGet,
  listGeographyZonesApiV1OrgGeographyZonesGet,
  listShopCategoriesApiV1BeatsShopCategoriesGet,
  type ContractClient,
  type DistrictOption,
  type ShopCategory,
  type StateOption,
  type ZoneOption,
} from "@humbee/api-contract";
import { ApiClientError } from "@/src/shared/api";

export interface GeographyMasterCategory {
  id: ShopCategory;
  name: string;
  share_of_outlets?: number | null;
}

export interface GeographyMasterResponse {
  zones: ZoneOption[];
  states: StateOption[];
  districts: DistrictOption[];
  cats: GeographyMasterCategory[];
  pool: {
    zones: string[];
    states: string[];
    districts: string[];
    cats: ShopCategory[];
  } | null;
}

function unwrap<T>(result: { data: T }): T {
  return result.data;
}

export function shopCategoryLabel(category: string): string {
  return category
    .toLowerCase()
    .split("_")
    .filter(Boolean)
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}

export async function readGeographyMaster(options: {
  client: ContractClient;
  signal?: AbortSignal;
  assignedEmployeeId?: string | null;
}): Promise<GeographyMasterResponse> {
  const assignedScopeRequest = options.assignedEmployeeId
    ? getGeographyScopeApiV1OrgEmployeesEmployeeIdGeographyScopeGet({
      client: options.client,
      path: { employee_id: options.assignedEmployeeId },
      signal: options.signal,
      throwOnError: true,
    }).then(unwrap).catch((error: unknown) => {
      if (error instanceof ApiClientError && error.code === "geography_scope_not_assigned") {
        return null;
      }
      throw error;
    })
    : Promise.resolve(null);

  const [zonesResponse, categoriesResponse, assignedScope] = await Promise.all([
    listGeographyZonesApiV1OrgGeographyZonesGet({
      client: options.client,
      signal: options.signal,
      throwOnError: true,
    }),
    listShopCategoriesApiV1BeatsShopCategoriesGet({
      client: options.client,
      signal: options.signal,
      throwOnError: true,
    }),
    assignedScopeRequest,
  ]);

  const zones = unwrap(zonesResponse).zones;
  const zoneIds = zones.map((zone) => zone.id);
  const statesResponse = await listGeographyStatesApiV1OrgGeographyStatesGet({
    client: options.client,
    query: zoneIds.length ? { zone_ids: zoneIds } : undefined,
    signal: options.signal,
    throwOnError: true,
  });
  const states = unwrap(statesResponse).states;
  const stateIds = states.map((state) => state.id);
  const districts = stateIds.length
    ? unwrap(await listGeographyDistrictsApiV1OrgGeographyDistrictsGet({
      client: options.client,
      query: { state_ids: stateIds },
      signal: options.signal,
      throwOnError: true,
    })).districts
    : [];
  const cats = unwrap(categoriesResponse).categories.map((category) => ({
    id: category,
    name: shopCategoryLabel(category),
  }));

  return {
    zones,
    states,
    districts,
    cats,
    pool: {
      zones: assignedScope?.zones ?? zones.map((zone) => zone.id),
      states: assignedScope?.states ?? states.map((state) => state.id),
      districts: assignedScope?.districts ?? districts.map((district) => district.id),
      cats: cats.map((category) => category.id),
    },
  };
}
