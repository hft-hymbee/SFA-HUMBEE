import { getMeApiV1MeGet } from "@humbee/api-contract";
import { getBrowserApiClient } from "@/src/shared/api";

export interface ProfileView {
  id: string;
  name: string;
  initials: string;
  employeeCode: string;
  manager: string | null;
  geography: string[];
  phone: string;
  joined: string | null;
  role: string;
  status: string;
}

function unwrap<T>(result: { data: T }): T {
  return result.data;
}

function initials(name: string) {
  return name
    .split(" ")
    .filter(Boolean)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

export async function getProfile(signal?: AbortSignal): Promise<ProfileView> {
  const me = unwrap(await getMeApiV1MeGet({
    client: getBrowserApiClient(),
    signal,
    throwOnError: true,
  }));

  return {
    id: me.id,
    name: me.full_name,
    initials: initials(me.full_name),
    employeeCode: me.id,
    manager: null,
    geography: [],
    phone: me.phone_e164,
    joined: null,
    role: me.role,
    status: me.status,
  };
}
