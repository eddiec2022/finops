import { vi } from "vitest";

type FetchResponseValue = unknown | ((url: string) => unknown);

/**
 * Stubs global fetch to resolve based on which URL fragment a request
 * matches. A response value can be a plain object, or a function of the full
 * matched URL for tests that need to vary the response by query string (e.g.
 * a resource_group-scoped request vs. the unscoped one).
 */
export function mockFetchResponses(responses: Record<string, FetchResponseValue>) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      const matchedKey = Object.keys(responses).find((fragment) => url.includes(fragment));
      if (!matchedKey) {
        return Promise.reject(new Error(`Unexpected fetch to ${url}`));
      }
      const value = responses[matchedKey];
      const body = typeof value === "function" ? (value as (url: string) => unknown)(url) : value;
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(body),
      } as Response);
    }),
  );
}
