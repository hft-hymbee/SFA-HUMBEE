import { notFound } from "next/navigation";
import { ManagementFeaturePage } from "@/src/features/management/screens";
import {
  isManagementView,
  managementViews,
} from "@/src/features/management/service";

export const dynamicParams = false;

export function generateStaticParams() {
  return managementViews
    .filter((view) => view !== "dashboard")
    .map((view) => ({ view }));
}

export default async function ManagerViewPage({
  params,
}: {
  params: Promise<{ view: string }>;
}) {
  const { view } = await params;
  if (!isManagementView(view) || view === "dashboard") notFound();
  return <ManagementFeaturePage view={view} />;
}
