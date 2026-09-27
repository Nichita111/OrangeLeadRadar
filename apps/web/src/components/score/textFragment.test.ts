import { describe, expect, it } from "vitest";

import { textFragmentUrl } from "./textFragment";

describe("textFragmentUrl (FR-116)", () => {
  it("adds the whole quote when it is short", () => {
    expect(textFragmentUrl("https://example.com/news", "Wir senken die Kosten.")).toBe(
      "https://example.com/news#:~:text=Wir%20senken%20die%20Kosten.",
    );
  });

  it("uses the first and last words of a long quote as the start and end of the range", () => {
    expect(
      textFragmentUrl(
        "https://example.com/news",
        "By combining the real and the digital worlds, Siemens empowers customers to accelerate their transformations.",
      ),
    ).toBe(
      "https://example.com/news#:~:text=By%20combining%20the%20real%20and,customers%20to%20accelerate%20their%20transformations.",
    );
  });

  it("encodes the characters the directive uses as syntax", () => {
    expect(textFragmentUrl("https://example.com/", "Cost-cutting, jobs & more")).toBe(
      "https://example.com/#:~:text=Cost%2Dcutting%2C%20jobs%20%26%20more",
    );
  });

  it("appends the directive after a fragment the address already has", () => {
    expect(textFragmentUrl("https://example.com/report#strategy", "Automation first")).toBe(
      "https://example.com/report#strategy:~:text=Automation%20first",
    );
  });

  it("collapses whitespace, as the page's rendered text does", () => {
    expect(textFragmentUrl("https://example.com/", "  Automation \n first ")).toBe(
      "https://example.com/#:~:text=Automation%20first",
    );
  });

  it("leaves the address as it is when the quote is empty", () => {
    expect(textFragmentUrl("https://example.com/", "   ")).toBe("https://example.com/");
  });
});
