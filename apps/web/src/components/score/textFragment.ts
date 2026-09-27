/** Words a long quote's range starts and ends with; a shorter quote is matched whole. */
const RANGE_WORDS = 5;

/** A text-directive value: percent-encoded, with `-`, `,` and `&` escaped as the syntax needs. */
function encode(text: string): string {
  return encodeURIComponent(text).replace(/-/g, "%2D");
}

/**
 * FR-116: the original page's address with a text fragment (`#:~:text=`) of the quote, so the
 * browser scrolls to the quoted line and highlights it; a browser without text fragments, or a
 * page that no longer holds the line, opens at the top.
 */
export function textFragmentUrl(url: string, quote: string): string {
  const words = quote.split(/\s+/).filter((word) => word !== "");
  if (words.length === 0) {
    return url;
  }
  const directive =
    words.length <= RANGE_WORDS * 2
      ? encode(words.join(" "))
      : `${encode(words.slice(0, RANGE_WORDS).join(" "))},${encode(words.slice(-RANGE_WORDS).join(" "))}`;
  return `${url}${url.includes("#") ? "" : "#"}:~:text=${directive}`;
}
