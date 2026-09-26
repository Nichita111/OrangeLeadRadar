/**
 * The frontend's [Routes](/architecture/services/frontend.md#routes): only the ones this task
 * builds. `RequireAuth` sends an anonymous visitor to Sign in (`FR-006`); `RequireAdmin` guards
 * the Admin-only ones, matching their roles column.
 */
import { Navigate, Route, Routes } from "react-router-dom";

import { SignInScreen } from "./features/identity-and-access/sign-in/SignInScreen";
import { UsersScreen } from "./features/identity-and-access/users/UsersScreen";
import { RequireAdmin } from "./shell/RequireAdmin";
import { RequireAuth } from "./shell/RequireAuth";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<SignInScreen />} />
      <Route element={<RequireAuth />}>
        <Route index element={<Navigate to="/prospects" replace />} />
        <Route element={<RequireAdmin />}>
          <Route path="/users" element={<UsersScreen />} />
        </Route>
      </Route>
    </Routes>
  );
}
