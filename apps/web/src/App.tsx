/**
 * The frontend's [Routes](/architecture/services/frontend.md#routes): only the ones this task
 * builds. `RequireAuth` sends an anonymous visitor to Sign in (`FR-006`); `RequireAdmin` guards
 * the Admin-only ones, matching their roles column.
 */
import { Navigate, Route, Routes } from "react-router-dom";

import { AccountImportScreen } from "./features/accounts-and-discovery/account-import/AccountImportScreen";
import { AccountProfileScreen } from "./features/accounts-and-discovery/account-profile/AccountProfileScreen";
import { AccountsScreen } from "./features/accounts-and-discovery/accounts/AccountsScreen";
import { AccountDetailScreen } from "./features/prospect-dashboard/account-detail/AccountDetailScreen";
import { ProspectsScreen } from "./features/prospect-dashboard/prospects/ProspectsScreen";
import { SignInScreen } from "./features/identity-and-access/sign-in/SignInScreen";
import { UsersScreen } from "./features/identity-and-access/users/UsersScreen";
import { ServiceEditorScreen } from "./features/service-configuration/service-editor/ServiceEditorScreen";
import { ServicesScreen } from "./features/service-configuration/services/ServicesScreen";
import { RunsScreen } from "./features/signal-pipeline/runs/RunsScreen";
import { RequireAdmin } from "./shell/RequireAdmin";
import { RequireAuth } from "./shell/RequireAuth";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<SignInScreen />} />
      <Route element={<RequireAuth />}>
        <Route index element={<Navigate to="/prospects" replace />} />
        <Route path="/accounts" element={<AccountsScreen />} />
        <Route path="/accounts/import" element={<AccountImportScreen />} />
        <Route path="/accounts/:id/profile" element={<AccountProfileScreen />} />
        <Route path="/runs" element={<RunsScreen />} />
        <Route path="/prospects" element={<ProspectsScreen />} />
        <Route path="/accounts/:id" element={<AccountDetailScreen />} />
        <Route element={<RequireAdmin />}>
          <Route path="/users" element={<UsersScreen />} />
          <Route path="/services" element={<ServicesScreen />} />
          <Route path="/services/:id" element={<ServiceEditorScreen />} />
        </Route>
      </Route>
    </Routes>
  );
}
