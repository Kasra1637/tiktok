import React, { act } from "react";
import { createRoot } from "react-dom/client";
import PlatformPreview from "./PlatformPreview";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

async function mount(props = {}) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<PlatformPreview {...props} />);
  });
  const q = (id) => container.querySelector(`[data-testid="${id}"]`);
  return {
    container, q,
    unmount: async () => { await act(async () => root.unmount()); container.remove(); },
  };
}

const heightPct = (px) => `${(px / 1920) * 100}%`;
const widthPct = (px) => `${(px / 1080) * 100}%`;

describe("PlatformPreview", () => {
  test("shows the honest placeholder before any render", async () => {
    const view = await mount();
    expect(view.q("platform-preview-video")).toBeNull();
    expect(view.container.textContent).toContain("The frame previews here once it renders.");
    await view.unmount();
  });

  test("shows the finished clip inside the frame", async () => {
    const view = await mount({ videoUrl: "/api/media/videos/gen-1.mp4?exp=1&sig=abc" });
    const video = view.q("platform-preview-video");
    expect(video).not.toBeNull();
    expect(video.getAttribute("src")).toContain("/api/media/videos/gen-1.mp4");
    await view.unmount();
  });

  test("a broken clip says so inside the frame, in the panels' words", async () => {
    const view = await mount({ videoUrl: "/api/media/videos/gen-1.mp4", videoBroken: true });
    expect(view.q("platform-preview-video")).toBeNull();
    expect(view.container.textContent).toContain("Preview unavailable — download it to view.");
    await view.unmount();
  });

  test("renders the Instagram zones with the recovered geometry", async () => {
    const view = await mount({ videoUrl: "/api/media/videos/gen-1.mp4" });
    const zones = view.q("platform-preview-zones");
    expect(zones.dataset.platform).toBe("instagram");
    const bands = [...zones.children];
    // Top, bottom, left, right — no rail on Instagram.
    expect(bands).toHaveLength(4);
    expect(bands[0].style.height).toBe(heightPct(250));
    expect(bands[1].style.height).toBe(heightPct(340));
    expect(bands[2].style.width).toBe(widthPct(65));
    expect(bands[3].style.width).toBe(widthPct(65));
    await view.unmount();
  });

  test("the toggle switches to the TikTok zones, rail included, and never the video", async () => {
    const view = await mount({ videoUrl: "/api/media/videos/gen-1.mp4" });
    await act(async () => { view.q("platform-preview-platform-tiktok").click(); });
    const zones = view.q("platform-preview-zones");
    expect(zones.dataset.platform).toBe("tiktok");
    const bands = [...zones.children];
    expect(bands).toHaveLength(5);
    expect(bands[0].style.height).toBe(heightPct(240));
    expect(bands[1].style.height).toBe(heightPct(660));
    expect(bands[2].style.width).toBe(widthPct(120));
    const rail = bands[4];
    expect(rail.style.width).toBe(widthPct(300));
    expect(rail.style.top).toBe(heightPct(840));
    expect(rail.style.height).toBe(heightPct(1920 - 660 - 840));
    // The video itself is untouched by the toggle.
    expect(view.q("platform-preview-video").getAttribute("src")).toContain("/api/media/videos/gen-1.mp4");
    await view.unmount();
  });
});
