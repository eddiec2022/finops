import { vi } from "vitest";

/** Stubs global fetch to resolve based on which URL fragment a request matches. */
export function mockFetchResponses(responses: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      const matchedKey = Object.keys(responses).find((fragment) => url.includes(fragment));
      if (!matchedKey) {
        return Promise.reject(new Error(`Unexpected fetch to ${url}`));
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(responses[matchedKey]),
      } as Response);
    }),
  );
}
