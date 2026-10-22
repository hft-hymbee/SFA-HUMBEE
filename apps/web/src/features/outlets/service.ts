import {
  documentLookupApiV1OutletsOnboardingDocumentLookupGet,
  firmAddressDistrictsApiV1OutletsOnboardingAddressDistrictsGet,
  firmAddressOptionsApiV1OutletsOnboardingAddressOptionsGet,
  firmAddressStatesApiV1OutletsOnboardingAddressStatesGet,
  getCandidateApiV1OutletsOnboardingCandidatesCandidateIdGet,
  getOutletInsightBenefitsApiV1OutletsOutletIdInsightsBenefitsGet,
  getOutletInsightManufacturersApiV1OutletsOutletIdInsightsManufacturersGet,
  getOutletInsightPerformanceApiV1OutletsOutletIdInsightsPerformanceGet,
  getOutletInsightProfilerApiV1OutletsOutletIdInsightsProfilerGet,
  getOutletInsightRewardsApiV1OutletsOutletIdInsightsRewardsGet,
  industriesApiV1OutletsOnboardingIndustriesGet,
  manufacturerRolesApiV1OutletsOnboardingManufacturerRolesGet,
  requestOwnerOtpApiV1OutletsOnboardingOwnerOtpRequestPost,
  submitCandidateApiV1OutletsOnboardingCandidatesPost,
  verifyOwnerOtpApiV1OutletsOnboardingOwnerOtpVerifyPost,
  type CandidateDetailResponse,
  type DocumentLookupResponse,
  type FirmAddressDistrictsResponse,
  type FirmAddressOptionsResponse,
  type FirmAddressStatesResponse,
  type IndustriesResponse,
  type ManufacturerRolesResponse,
  type OutletInsightManufacturersResponse,
  type OutletInsightProfilerResponse,
  type OutletInsightSectionResponse,
  type OwnerOtpRequestResponse,
  type OwnerOtpVerifyResponse,
  type SubmitCandidateBody,
} from "@humbee/api-contract";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getBrowserApiClient, idempotencyHeaders } from "@/src/shared/api";
import { readSessionSync } from "@/src/shared/auth/session";

function unwrap<T>(result: { data: T }): T {
  return result.data;
}

function actorId() {
  return readSessionSync()?.employeeId ?? "";
}

export const outletOnboardingKeys = {
  all: (id: string) => ["outlet-onboarding", { actorId: id }] as const,
  candidates: (id: string, status = "all") => [...outletOnboardingKeys.all(id), "candidates", status] as const,
  candidate: (id: string, candidateId: string) => [...outletOnboardingKeys.all(id), "candidate", candidateId] as const,
  addressStates: (id: string) => [...outletOnboardingKeys.all(id), "address-states"] as const,
  addressDistricts: (id: string, stateId: string) => [...outletOnboardingKeys.all(id), "address-districts", stateId] as const,
  addressOptions: (id: string, districtId: string, pincode?: string, locationId?: string) =>
    [...outletOnboardingKeys.all(id), "address-options", districtId, pincode ?? "", locationId ?? ""] as const,
  manufacturerRoles: (id: string) => [...outletOnboardingKeys.all(id), "manufacturer-roles"] as const,
  industries: (id: string) => [...outletOnboardingKeys.all(id), "industries"] as const,
};

export const outletOnboardingService = {
  async getCandidate(candidateId: string, signal?: AbortSignal): Promise<CandidateDetailResponse> {
    return unwrap(await getCandidateApiV1OutletsOnboardingCandidatesCandidateIdGet({
      client: getBrowserApiClient(),
      path: { candidate_id: candidateId },
      signal,
      throwOnError: true,
    }));
  },

  async addressStates(signal?: AbortSignal): Promise<FirmAddressStatesResponse> {
    return unwrap(await firmAddressStatesApiV1OutletsOnboardingAddressStatesGet({
      client: getBrowserApiClient(),
      signal,
      throwOnError: true,
    }));
  },

  async addressDistricts(stateId: string, signal?: AbortSignal): Promise<FirmAddressDistrictsResponse> {
    return unwrap(await firmAddressDistrictsApiV1OutletsOnboardingAddressDistrictsGet({
      client: getBrowserApiClient(),
      query: { state_id: stateId },
      signal,
      throwOnError: true,
    }));
  },

  async addressOptions(
    input: { districtId: string; pincode?: string; locationId?: string },
    signal?: AbortSignal,
  ): Promise<FirmAddressOptionsResponse> {
    return unwrap(await firmAddressOptionsApiV1OutletsOnboardingAddressOptionsGet({
      client: getBrowserApiClient(),
      query: {
        district_id: input.districtId,
        pincode: input.pincode || undefined,
        location_id: input.locationId || undefined,
      },
      signal,
      throwOnError: true,
    }));
  },

  async manufacturerRoles(signal?: AbortSignal): Promise<ManufacturerRolesResponse> {
    return unwrap(await manufacturerRolesApiV1OutletsOnboardingManufacturerRolesGet({
      client: getBrowserApiClient(),
      signal,
      throwOnError: true,
    }));
  },

  async industries(signal?: AbortSignal): Promise<IndustriesResponse> {
    return unwrap(await industriesApiV1OutletsOnboardingIndustriesGet({
      client: getBrowserApiClient(),
      signal,
      throwOnError: true,
    }));
  },

  async documentLookup(input: { gstin?: string; pan?: string }, signal?: AbortSignal): Promise<DocumentLookupResponse> {
    return unwrap(await documentLookupApiV1OutletsOnboardingDocumentLookupGet({
      client: getBrowserApiClient(),
      query: { gstin: input.gstin || undefined, pan: input.pan || undefined },
      signal,
      throwOnError: true,
    }));
  },

  async requestOwnerOtp(phoneE164: string, idempotencyKey: string): Promise<OwnerOtpRequestResponse> {
    return unwrap(await requestOwnerOtpApiV1OutletsOnboardingOwnerOtpRequestPost({
      client: getBrowserApiClient(),
      body: { phone_e164: phoneE164 },
      headers: idempotencyHeaders(idempotencyKey),
      throwOnError: true,
    }));
  },

  async verifyOwnerOtp(input: { challengeId: string; code: string }, idempotencyKey: string): Promise<OwnerOtpVerifyResponse> {
    return unwrap(await verifyOwnerOtpApiV1OutletsOnboardingOwnerOtpVerifyPost({
      client: getBrowserApiClient(),
      body: { challenge_id: input.challengeId, code: input.code },
      headers: idempotencyHeaders(idempotencyKey),
      throwOnError: true,
    }));
  },

  async submitCandidate(body: SubmitCandidateBody, idempotencyKey: string): Promise<CandidateDetailResponse> {
    return unwrap(await submitCandidateApiV1OutletsOnboardingCandidatesPost({
      client: getBrowserApiClient(),
      body,
      headers: idempotencyHeaders(idempotencyKey),
      throwOnError: true,
    }));
  },
};

export function useFirmAddressStates() {
  const id = actorId();
  return useQuery({
    queryKey: outletOnboardingKeys.addressStates(id),
    queryFn: ({ signal }) => outletOnboardingService.addressStates(signal),
    enabled: Boolean(id),
    staleTime: 86_400_000,
  });
}

export function useFirmAddressDistricts(stateId: string) {
  const id = actorId();
  return useQuery({
    queryKey: outletOnboardingKeys.addressDistricts(id, stateId),
    queryFn: ({ signal }) => outletOnboardingService.addressDistricts(stateId, signal),
    enabled: Boolean(id && stateId),
    placeholderData: keepPreviousData,
    staleTime: 86_400_000,
  });
}

export function useFirmAddressOptions(input: { districtId: string; pincode?: string; locationId?: string }) {
  const id = actorId();
  return useQuery({
    queryKey: outletOnboardingKeys.addressOptions(id, input.districtId, input.pincode, input.locationId),
    queryFn: ({ signal }) => outletOnboardingService.addressOptions(input, signal),
    enabled: Boolean(id && input.districtId),
    placeholderData: keepPreviousData,
    staleTime: 300_000,
  });
}

export function useManufacturerRoles(enabled = true) {
  const id = actorId();
  return useQuery({
    queryKey: outletOnboardingKeys.manufacturerRoles(id),
    queryFn: ({ signal }) => outletOnboardingService.manufacturerRoles(signal),
    enabled: Boolean(id) && enabled,
    staleTime: 300_000,
  });
}

export function useIndustries(enabled = true) {
  const id = actorId();
  return useQuery({
    queryKey: outletOnboardingKeys.industries(id),
    queryFn: ({ signal }) => outletOnboardingService.industries(signal),
    enabled: Boolean(id) && enabled,
    staleTime: Number.POSITIVE_INFINITY,
  });
}

export function useOutletCandidate(candidateId: string) {
  const id = actorId();
  return useQuery({
    queryKey: outletOnboardingKeys.candidate(id, candidateId),
    queryFn: ({ signal }) => outletOnboardingService.getCandidate(candidateId, signal),
    enabled: Boolean(id && candidateId),
    refetchOnWindowFocus: true,
  });
}

export function useOutletOnboardingMutations() {
  const id = actorId();
  const queryClient = useQueryClient();
  const invalidateCandidates = () => queryClient.invalidateQueries({ queryKey: outletOnboardingKeys.candidates(id) });

  const requestOtp = useMutation({
    mutationFn: ({ phoneE164, idempotencyKey }: { phoneE164: string; idempotencyKey: string }) =>
      outletOnboardingService.requestOwnerOtp(phoneE164, idempotencyKey),
  });

  const verifyOtp = useMutation({
    mutationFn: ({ challengeId, code, idempotencyKey }: { challengeId: string; code: string; idempotencyKey: string }) =>
      outletOnboardingService.verifyOwnerOtp({ challengeId, code }, idempotencyKey),
  });

  const lookupDocument = useMutation({
    mutationFn: (input: { gstin?: string; pan?: string }) => outletOnboardingService.documentLookup(input),
  });

  const submitCandidate = useMutation({
    mutationFn: ({ body, idempotencyKey }: { body: SubmitCandidateBody; idempotencyKey: string }) =>
      outletOnboardingService.submitCandidate(body, idempotencyKey),
    onSuccess: async () => {
      await invalidateCandidates();
      await queryClient.invalidateQueries({ queryKey: ["approvals", { actorId: id }] });
      await queryClient.invalidateQueries({ queryKey: ["notifications", { actorId: id }] });
    },
  });

  return { requestOtp, verifyOtp, lookupDocument, submitCandidate };
}

export type OutletInsightSectionName = "performance" | "benefits" | "rewards";

export const outletInsightKeys = {
  all: (actor: string) => ["outlet-insights", { actorId: actor }] as const,
  section: (
    actor: string,
    outletId: string,
    manufacturerId: string,
    outletEsiId: string,
    section: OutletInsightSectionName,
  ) => [...outletInsightKeys.all(actor), section, outletId, manufacturerId, outletEsiId] as const,
  profiler: (actor: string, outletId: string, manufacturerId: string, outletEsiId: string) =>
    [...outletInsightKeys.all(actor), "profiler", outletId, manufacturerId, outletEsiId] as const,
  manufacturers: (actor: string, outletId: string) =>
    [...outletInsightKeys.all(actor), "manufacturers", outletId] as const,
};

const insightSectionReaders = {
  performance: getOutletInsightPerformanceApiV1OutletsOutletIdInsightsPerformanceGet,
  benefits: getOutletInsightBenefitsApiV1OutletsOutletIdInsightsBenefitsGet,
  rewards: getOutletInsightRewardsApiV1OutletsOutletIdInsightsRewardsGet,
};

export const outletInsightService = {
  async section(
    outletId: string,
    manufacturerId: string,
    outletEsiId: string,
    section: OutletInsightSectionName,
    signal?: AbortSignal,
  ): Promise<OutletInsightSectionResponse> {
    return unwrap(await insightSectionReaders[section]({
      client: getBrowserApiClient(),
      path: { outlet_id: outletId },
      query: { manufacturer_id: manufacturerId, outlet_esi_id: outletEsiId },
      signal,
      throwOnError: true,
    }));
  },
  async manufacturers(outletId: string, signal?: AbortSignal): Promise<OutletInsightManufacturersResponse> {
    return unwrap(await getOutletInsightManufacturersApiV1OutletsOutletIdInsightsManufacturersGet({
      client: getBrowserApiClient(),
      path: { outlet_id: outletId },
      signal,
      throwOnError: true,
    }));
  },
  async profiler(
    outletId: string,
    manufacturerId: string,
    outletEsiId: string,
    signal?: AbortSignal,
  ): Promise<OutletInsightProfilerResponse> {
    return unwrap(await getOutletInsightProfilerApiV1OutletsOutletIdInsightsProfilerGet({
      client: getBrowserApiClient(),
      path: { outlet_id: outletId },
      query: { manufacturer_id: manufacturerId, outlet_esi_id: outletEsiId },
      signal,
      throwOnError: true,
    }));
  },
};

export function useOutletInsightManufacturers(outletId: string) {
  const id = actorId();
  return useQuery({
    queryKey: outletInsightKeys.manufacturers(id, outletId),
    queryFn: ({ signal }) => outletInsightService.manufacturers(outletId, signal),
    enabled: Boolean(id && outletId),
    staleTime: 0,
  });
}

export function useOutletInsightSection(
  outletId: string,
  manufacturerId: string,
  outletEsiId: string,
  section: OutletInsightSectionName,
  active: boolean,
) {
  const id = actorId();
  return useQuery({
    queryKey: outletInsightKeys.section(id, outletId, manufacturerId, outletEsiId, section),
    queryFn: ({ signal }) => outletInsightService.section(
      outletId,
      manufacturerId,
      outletEsiId,
      section,
      signal,
    ),
    enabled: Boolean(id && outletId && manufacturerId && outletEsiId && active),
    staleTime: 0,
  });
}

export function useOutletInsightProfiler(
  outletId: string,
  manufacturerId: string,
  outletEsiId: string,
  active: boolean,
) {
  const id = actorId();
  return useQuery({
    queryKey: outletInsightKeys.profiler(id, outletId, manufacturerId, outletEsiId),
    queryFn: ({ signal }) => outletInsightService.profiler(outletId, manufacturerId, outletEsiId, signal),
    enabled: Boolean(id && outletId && manufacturerId && outletEsiId && active),
    staleTime: 0,
    gcTime: 0,
  });
}
