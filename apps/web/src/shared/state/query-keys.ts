export interface QueryPeriod {
  from: string;
  to: string;
}

export function createActorQueryKeys(feature: string) {
  const root = [feature] as const;

  return {
    all: (actorId: string) => [...root, { actorId }] as const,
    byBusinessDate: (actorId: string, businessDate: string) =>
      [...root, { actorId, businessDate }] as const,
    byPeriod: (actorId: string, period: QueryPeriod) =>
      [...root, { actorId, period }] as const,
  };
}
