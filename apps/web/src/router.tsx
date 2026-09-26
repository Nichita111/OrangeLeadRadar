import { Navigate, createBrowserRouter, type RouteObject } from "react-router";

import { AccountDetailScreen } from "./features/prospect-dashboard/account-detail/AccountDetailScreen";
import { ProspectsScreen } from "./features/prospect-dashboard/prospects/ProspectsScreen";
import { SignIn } from "./features/identity-and-access/sign-in/SignIn";
import { Users } from "./features/identity-and-access/users/Users";
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
            path: "/users",
            element: (
              <RequireAdmin>
                <Users />
              </RequireAdmin>
            ),
            handle: handle({ title: "Users", adminOnly: true }),
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
