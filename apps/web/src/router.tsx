import { Navigate, createBrowserRouter, type RouteObject } from "react-router";

import { AuditLogScreen } from "./features/audit-trail/AuditLogScreen";
import { SuggestedAccountsScreen } from "./features/accounts-and-discovery/suggested-accounts/SuggestedAccountsScreen";
import { LabellingScreen } from "./features/evaluation-and-feedback/labelling/LabellingScreen";
import { QualityReportScreen } from "./features/evaluation-and-feedback/quality-report/QualityReportScreen";
import { AccountDetailScreen } from "./features/prospect-dashboard/account-detail/AccountDetailScreen";
import { ProspectsScreen } from "./features/prospect-dashboard/prospects/ProspectsScreen";
import { SourcePluginsScreen } from "./features/signal-pipeline/source-plug-ins/SourcePluginsScreen";
import { SignIn } from "./features/identity-and-access/sign-in/SignIn";
import { Users } from "./features/identity-and-access/users/Users";
import { IndustriesAndMarketsScreen } from "./features/service-configuration/industries-and-markets/IndustriesAndMarketsScreen";
import { ServiceEditorScreen } from "./features/service-configuration/service-editor/ServiceEditorScreen";
import { ServicesScreen } from "./features/service-configuration/services/ServicesScreen";
import { ScoringSettingsScreen } from "./features/service-configuration/scoring-settings/ScoringSettingsScreen";
import { DocumentTitle } from "./shell/DocumentTitle";
import { RequireAdmin } from "./shell/RequireAdmin";
import { RequireSession } from "./shell/RequireSession";
import type { RouteHandle } from "./shell/routeHandle";
import { NotFound } from "./shell/states/NotFound";

function handle(value: RouteHandle): RouteHandle {
  return value;
}

/**
 * The routes this client has so far. Every other route of the Routes table shows Not found until the
 * task that builds its screen adds it.
 */
export const routes: RouteObject[] = [
  {
    element: <DocumentTitle />,
    children: [
      { path: "/login", element: <SignIn />, handle: handle({ title: "Sign in" }) },
      {
        element: <RequireSession />,
        children: [
          { path: "/", element: <Navigate to="/prospects" replace /> },
          {
            path: "/prospects",
            element: <ProspectsScreen />,
            handle: handle({ title: "Prospects" }),
          },
          {
            path: "/accounts/:id",
            element: <AccountDetailScreen />,
            handle: handle({ title: "Account detail" }),
          },
          {
            path: "/suggested-accounts",
            element: <SuggestedAccountsScreen />,
            handle: handle({ title: "Suggested accounts" }),
          },
          {
            path: "/labelling",
            element: <LabellingScreen />,
            handle: handle({ title: "Labelling" }),
          },
          {
            path: "/quality",
            element: (
              <RequireAdmin>
                <QualityReportScreen />
              </RequireAdmin>
            ),
            handle: handle({ title: "Quality report", adminOnly: true }),
          },
          {
            path: "/users",
            element: (
              <RequireAdmin>
                <Users />
              </RequireAdmin>
            ),
            handle: handle({ title: "Users", adminOnly: true }),
          },
          {
            path: "/audit",
            element: (
              <RequireAdmin>
                <AuditLogScreen />
              </RequireAdmin>
            ),
            handle: handle({ title: "Audit log", adminOnly: true }),
          },
          {
            path: "/services",
            element: (
              <RequireAdmin>
                <ServicesScreen />
              </RequireAdmin>
            ),
            handle: handle({ title: "Services", adminOnly: true }),
          },
          {
            path: "/services/:id",
            element: (
              <RequireAdmin>
                <ServiceEditorScreen />
              </RequireAdmin>
            ),
            handle: handle({
              title: "Service editor",
              adminOnly: true,
              parent: { title: "Services", route: "/services" },
            }),
          },
          {
            path: "/services/:id/scoring",
            element: (
              <RequireAdmin>
                <ScoringSettingsScreen />
              </RequireAdmin>
            ),
            handle: handle({
              title: "Scoring settings",
              adminOnly: true,
              parent: { title: "Services", route: "/services" },
            }),
          },
          {
            path: "/settings/industries-markets",
            element: (
              <RequireAdmin>
                <IndustriesAndMarketsScreen />
              </RequireAdmin>
            ),
            handle: handle({ title: "Industries and markets", adminOnly: true }),
          },
          {
            path: "/settings/source-plugins",
            element: (
              <RequireAdmin>
                <SourcePluginsScreen />
              </RequireAdmin>
            ),
            handle: handle({ title: "Source plug-ins", adminOnly: true }),
          },
          { path: "*", element: <NotFound />, handle: handle({ title: "Page not found" }) },
        ],
      },
    ],
  },
];

export function createAppRouter() {
  return createBrowserRouter(routes);
}
