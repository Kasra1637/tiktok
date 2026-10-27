const mockPost = jest.fn();

jest.mock("axios", () => ({
  __esModule: true,
  default: {
    create: () => ({
      get: jest.fn(),
      post: (...args) => mockPost(...args),
      patch: jest.fn(),
      delete: jest.fn(),
      interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } },
    }),
  },
}));

import { api, DEMO_CTA_PART_BYTES } from "./api";

beforeEach(() => {
  mockPost.mockReset();
  mockPost.mockResolvedValue({ data: { id: "saved-1" } });
});

test("a small export saves in one request to the generation path", async () => {
  const blob = new Blob([new Uint8Array(100)]);
  const row = await api.saveDemoCtaExport("gen-1", blob, "demo-cta.mp4");
  expect(row).toEqual({ id: "saved-1" });
  expect(mockPost).toHaveBeenCalledTimes(1);
  const [url, form] = mockPost.mock.calls[0];
  expect(url).toBe("/generations/gen-1/demo-cta-result");
  expect(form.get("file")).toBeInstanceOf(Blob);
  expect(form.get("file").size).toBe(100);
  expect(form.get("file").name).toBe("demo-cta.mp4");
});

test("a standalone small export posts to the bare path", async () => {
  const blob = new Blob([new Uint8Array(100)]);
  await api.saveDemoCtaExport(null, blob, "demo-cta.mp4");
  expect(mockPost).toHaveBeenCalledTimes(1);
  expect(mockPost.mock.calls[0][0]).toBe("/demo-cta-result");
});

test("an export past 8 MB goes up in parts, then completes under one id", async () => {
  const bytes = new Uint8Array(DEMO_CTA_PART_BYTES + 10);
  bytes.fill(7);
  const blob = new Blob([bytes]);
  mockPost.mockResolvedValue({ data: { id: "saved-9" } });
  const row = await api.saveDemoCtaExport("gen-2", blob, "big.mp4");
  expect(row).toEqual({ id: "saved-9" });
  // Two parts plus the complete call, in order.
  expect(mockPost).toHaveBeenCalledTimes(3);
  const partCalls = mockPost.mock.calls.slice(0, 2);
  const ids = partCalls.map(([url]) => url.match(/^\/demo-cta-uploads\/(.+)\/parts$/)[1]);
  expect(ids[0]).toMatch(/^[0-9a-f-]{36}$/);
  expect(ids[1]).toBe(ids[0]);
  expect(partCalls[0][1].get("index")).toBe("0");
  expect(partCalls[0][1].get("total")).toBe("2");
  expect(partCalls[1][1].get("index")).toBe("1");
  expect(partCalls[1][1].get("total")).toBe("2");
  expect(partCalls[0][1].get("chunk").size).toBe(DEMO_CTA_PART_BYTES);
  expect(partCalls[1][1].get("chunk").size).toBe(10);
  const [completeUrl, completeBody] = mockPost.mock.calls[2];
  expect(completeUrl).toBe(`/demo-cta-uploads/${ids[0]}/complete`);
  expect(completeBody).toEqual({ generation_id: "gen-2", filename: "big.mp4", total: 2 });
});

test("a standalone large export completes with a null generation", async () => {
  const bytes = new Uint8Array(DEMO_CTA_PART_BYTES + 1);
  const blob = new Blob([bytes]);
  await api.saveDemoCtaExport(null, blob, "big.mp4");
  const completeBody = mockPost.mock.calls[mockPost.mock.calls.length - 1][1];
  expect(completeBody).toEqual({ generation_id: null, filename: "big.mp4", total: 2 });
});
