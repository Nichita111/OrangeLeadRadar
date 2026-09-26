import type { ReactElement } from "react";
import { Route, Routes } from "react-router";

import { AppShell } from "./AppShell";
import { RequireAdmin, RequireAuth } from "./guards";
import { ScreenPlaceholder } from "./ScreenPlaceholder";

/**
 * Every route of [Routes](/architecture/services/frontend.md#routes), each a placeholder until
 * its own task builds the screen. `/` and `/login` are anonymous; every other route is
 * signed-in, and the Admin routes also need the Admin role.
 */
export function AppRoutes(): ReactElement {
  return (
    <Routes>
      <Route path="/" element={<ScreenPlaceholder label="Landing" />} />
      <Route path="/login" element={<ScreenPlaceholder label="Sign in" />} />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route path="/prospects" element={<ScreenPlaceholder label="Prospects" />} />
        <Route path="/accounts/:id" element={<ScreenPlaceholder label="Account detail" />} />
        <Route path="/alerts" element={<ScreenPlaceholder label="Alerts" />} />
        <Route path="/accounts" element={<ScreenPlaceholder label="Accounts" />} />
        <Route
          path="/accounts/:id/profile"
          element={<ScreenPlaceholder label="Account profile" />}
        />
        <Route path="/accounts/import" element={<ScreenPlaceholder label="Account import" />} />
        <Route
          path="/suggested-accounts"
          element={<ScreenPlaceholder label="Suggested accounts" />}
        />
        <Route path="/runs" element={<ScreenPlaceholder label="Runs" />} />
        <Route path="/labelling" element={<ScreenPlaceholder label="Labelling" />} />
        <Route
          path="/accounts/:id/outreach"
          element={<ScreenPlaceholder label="Outreach composer" />}
        />
        <Route
          path="/services"
          element={
            <RequireAdmin>
              <ScreenPlaceholder label="Services" />
            </RequireAdmin>
          }
        />
        <Route
          path="/services/:id"
          element={
            <RequireAdmin>
              <ScreenPlaceholder label="Service editor" />
            </RequireAdmin>
          }
        />
        <Route
          path="/services/:id/scoring"
          element={
            <RequireAdmin>
              <ScreenPlaceholder label="Scoring settings" />
            </RequireAdmin>
          }
        />
        <Route
          path="/settings/industries-markets"
          element={
            <RequireAdmin>
              <ScreenPlaceholder label="Industries and markets" />
            </RequireAdmin>
          }
        />
        <Route
          path="/quality"
          element={
            <RequireAdmin>
              <ScreenPlaceholder label="Quality report" />
            </RequireAdmin>
          }
        />
        <Route
          path="/settings/source-plugins"
          element={
            <RequireAdmin>
              <ScreenPlaceholder label="Source plug-ins" />
            </RequireAdmin>
          }
        />
        <Route
          path="/users"
          element={
            <RequireAdmin>
              <ScreenPlaceholder label="Users" />
            </RequireAdmin>
          }
        />
        <Route
          path="/audit"
          element={
            <RequireAdmin>
              <ScreenPlaceholder label="Audit log" />
            </RequireAdmin>
          }
        />
      </Route>
    </Routes>
  );
}
