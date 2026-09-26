import { describe, expect, it } from "vitest";

import { client } from "../client";
import { anaSales, authenticatedUser } from "../authenticationAndUsers.fixtures";
import { server } from "../../testServer";
import { createDevHandlers, readDevPassword } from "./devHandlers";

const DEV_PASSWORD = "dev-only-marker";

describe("readDevPassword (G15)", () => {
  it("returns the variable's value", () => {
    expect(readDevPassword({ VITE_DEV_MOCK_PASSWORD: "abc" })).toBe("abc");
  });

  it.each([undefined, "", 3])("throws naming VITE_DEV_MOCK_PASSWORD for %j", (value) => {
    expect(() => readDevPassword({ VITE_DEV_MOCK_PASSWORD: value })).toThrow(
      /VITE_DEV_MOCK_PASSWORD/,
    );
  });
});

describe("development handlers (G15, API-01 notes)", () => {
  it("a fixture email with the development password signs in, and API-03 then returns the user", async () => {
    server.use(...createDevHandlers(DEV_PASSWORD));
    const login = await client.POST("/api/v1/auth/login", {
      body: { email: anaSales.email, password: DEV_PASSWORD },
    });
    expect(login.data).toEqual(authenticatedUser(anaSales));
    const me = await client.GET("/api/v1/auth/me");
    expect(me.data).toEqual(authenticatedUser(anaSales));
  });

  it("a wrong password and an unknown email each answer the same 401 UNAUTHENTICATED", async () => {
    server.use(...createDevHandlers(DEV_PASSWORD));
    const failures = await Promise.all([
      client
        .POST("/api/v1/auth/login", { body: { email: anaSales.email, password: "wrong" } })
        .catch((error: unknown) => error),
      client
        .POST("/api/v1/auth/login", {
          body: { email: "nobody@leadradar.local", password: DEV_PASSWORD },
        })
        .catch((error: unknown) => error),
    ]);
    const [wrongPassword, unknownEmail] = failures as { status: number; envelope: unknown }[];
    expect(wrongPassword?.status).toBe(401);
    expect(unknownEmail?.status).toBe(401);
    expect(wrongPassword?.envelope).toEqual(unknownEmail?.envelope);
    expect(JSON.stringify(wrongPassword?.envelope)).toContain("UNAUTHENTICATED");
  });

  it("API-03 answers 401 until someone signs in, and API-02 ends the session", async () => {
    server.use(...createDevHandlers(DEV_PASSWORD));
    const before = await client.GET("/api/v1/auth/me").catch((error: unknown) => error);
    expect((before as { status: number }).status).toBe(401);
    await client.POST("/api/v1/auth/login", {
      body: { email: anaSales.email, password: DEV_PASSWORD },
    });
    await client.POST("/api/v1/auth/logout");
    const after = await client.GET("/api/v1/auth/me").catch((error: unknown) => error);
    expect((after as { status: number }).status).toBe(401);
  });

  it("lists users by display_name, creates and updates them", async () => {
    server.use(...createDevHandlers(DEV_PASSWORD));
    const created = await client.POST("/api/v1/users", {
      body: {
        email: "new@leadradar.local",
        display_name: "Aaron New",
        role: "SALES",
        password: "never-returned",
      },
    });
    expect(JSON.stringify(created.data)).not.toContain("never-returned");
    const list = await client.GET("/api/v1/users");
    expect(list.data?.map((user) => user.display_name)).toEqual([
      "Aaron New",
      "Ana Sales",
      "Olga Admin",
    ]);
    const id = created.data?.id ?? "";
    const updated = await client.PATCH("/api/v1/users/{id}", {
      params: { path: { id } },
      body: { status: "DISABLED" },
    });
    expect(updated.data?.status).toBe("DISABLED");
    expect(updated.data?.display_name).toBe("Aaron New");
  });

  it("a user created through API-05 signs in with the development password", async () => {
    server.use(...createDevHandlers(DEV_PASSWORD));
    await client.POST("/api/v1/users", {
      body: {
        email: "new@leadradar.local",
        display_name: "Aaron New",
        role: "SALES",
        password: "something-else",
      },
    });
    const login = await client.POST("/api/v1/auth/login", {
      body: { email: "new@leadradar.local", password: DEV_PASSWORD },
    });
    expect(login.data?.display_name).toBe("Aaron New");
  });
});
