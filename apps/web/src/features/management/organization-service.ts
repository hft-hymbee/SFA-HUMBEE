import {
  assignGeographyScopeApiV1OrgEmployeesEmployeeIdGeographyScopePut,
  createEmployeeApiV1OrgEmployeesPost,
  deactivateEmployeeApiV1OrgEmployeesEmployeeIdDeactivatePost,
  getEmployeeApiV1OrgEmployeesEmployeeIdGet,
  getGeographyScopeApiV1OrgEmployeesEmployeeIdGeographyScopeGet,
  getTreeApiV1OrgTreeGet,
  listEmployeesApiV1OrgEmployeesGet,
  listMoveCandidatesApiV1OrgEmployeesEmployeeIdMoveCandidatesGet,
  moveEmployeeApiV1OrgEmployeesEmployeeIdMovePost,
  updateEmployeeApiV1OrgEmployeesEmployeeIdPatch,
  type AssignGeoScopeBody,
  type CreateEmployeeBody,
  type EmployeeListResponse,
  type EmployeeResponse,
  type GeoScopeResponse,
  type MoveCandidateListResponse,
  type TreeResponse,
  type UpdateEmployeeBody,
} from "@humbee/api-contract";
import {
  createIdempotencyKey,
  ApiClientError,
  getBrowserApiClient,
  idempotencyHeaders,
} from "@/src/shared/api";
import {
  readGeographyMaster,
  type GeographyMasterResponse,
} from "@/src/shared/geography-master";
import { fetchAllPages } from "@/src/shared/pagination";

export type { GeographyMasterResponse };

function unwrap<T>(result: { data: T }): T {
  return result.data;
}

const EMPLOYEE_PAGE_SIZE = 100;

export interface EmployeeFilters {
  query?: string;
  role?: string;
  status?: string;
}

export const organizationService = {
  async listEmployees(filters: EmployeeFilters = {}, signal?: AbortSignal): Promise<EmployeeListResponse> {
    return fetchAllPages(async (page) => unwrap(await listEmployeesApiV1OrgEmployeesGet({
      client: getBrowserApiClient(),
      query: {
        page,
        page_size: EMPLOYEE_PAGE_SIZE,
        q: filters.query || undefined,
        role: filters.role || undefined,
        status: filters.status || undefined,
      },
      signal,
      throwOnError: true,
    })));
  },

  async getEmployee(employeeId: string, signal?: AbortSignal): Promise<EmployeeResponse> {
    return unwrap(await getEmployeeApiV1OrgEmployeesEmployeeIdGet({
      client: getBrowserApiClient(),
      path: { employee_id: employeeId },
      signal,
      throwOnError: true,
    }));
  },

  async createEmployee(body: CreateEmployeeBody): Promise<EmployeeResponse> {
    return unwrap(await createEmployeeApiV1OrgEmployeesPost({
      client: getBrowserApiClient(),
      body,
      headers: idempotencyHeaders(createIdempotencyKey()),
      throwOnError: true,
    }));
  },

  async updateEmployee(employeeId: string, body: UpdateEmployeeBody): Promise<EmployeeResponse> {
    return unwrap(await updateEmployeeApiV1OrgEmployeesEmployeeIdPatch({
      client: getBrowserApiClient(),
      path: { employee_id: employeeId },
      body,
      headers: idempotencyHeaders(createIdempotencyKey()),
      throwOnError: true,
    }));
  },

  async deactivateEmployee(employeeId: string, reason?: string): Promise<EmployeeResponse> {
    return unwrap(await deactivateEmployeeApiV1OrgEmployeesEmployeeIdDeactivatePost({
      client: getBrowserApiClient(),
      path: { employee_id: employeeId },
      body: { reason: reason || undefined },
      headers: idempotencyHeaders(createIdempotencyKey()),
      throwOnError: true,
    }));
  },

  async getTree(signal?: AbortSignal): Promise<TreeResponse> {
    return unwrap(await getTreeApiV1OrgTreeGet({
      client: getBrowserApiClient(),
      signal,
      throwOnError: true,
    }));
  },

  async getMoveCandidates(employeeId: string, signal?: AbortSignal): Promise<MoveCandidateListResponse> {
    return unwrap(await listMoveCandidatesApiV1OrgEmployeesEmployeeIdMoveCandidatesGet({
      client: getBrowserApiClient(),
      path: { employee_id: employeeId },
      signal,
      throwOnError: true,
    }));
  },

  async moveEmployee(employeeId: string, newManagerEmployeeId: string | null): Promise<EmployeeResponse> {
    return unwrap(await moveEmployeeApiV1OrgEmployeesEmployeeIdMovePost({
      client: getBrowserApiClient(),
      path: { employee_id: employeeId },
      body: { new_manager_employee_id: newManagerEmployeeId },
      headers: idempotencyHeaders(createIdempotencyKey()),
      throwOnError: true,
    }));
  },

  async getGeographyMaster(signal?: AbortSignal): Promise<GeographyMasterResponse> {
    return readGeographyMaster({
      client: getBrowserApiClient(),
      signal,
    });
  },

  async getGeographyScope(employeeId: string, signal?: AbortSignal): Promise<GeoScopeResponse> {
    try {
      return unwrap(await getGeographyScopeApiV1OrgEmployeesEmployeeIdGeographyScopeGet({
        client: getBrowserApiClient(),
        path: { employee_id: employeeId },
        signal,
        throwOnError: true,
      }));
    } catch (error) {
      if (error instanceof ApiClientError && error.code === "geography_scope_not_assigned") {
        return {
          employee_id: employeeId,
          zones: [],
          states: [],
          districts: [],
          geo_labels: {},
          assigned_by: null,
          assigned_at: null,
        };
      }
      throw error;
    }
  },

  async assignGeographyScope(employeeId: string, body: AssignGeoScopeBody): Promise<GeoScopeResponse> {
    return unwrap(await assignGeographyScopeApiV1OrgEmployeesEmployeeIdGeographyScopePut({
      client: getBrowserApiClient(),
      path: { employee_id: employeeId },
      body,
      headers: idempotencyHeaders(createIdempotencyKey()),
      throwOnError: true,
    }));
  },
};
