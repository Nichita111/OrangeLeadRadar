/**
 * The data of the Landing scene (WF-27, FR-164). DHL Group's quote, rules and scores and Lufthansa
 * Group's band and scores are those of WF-24 and the demo dataset; every other account's position,
 * documents and Priority are illustrative.
 */

export type SceneBand = "hot" | "warm" | "cold";

/** Name, sector (0 to 5), Priority, band, documents, and the documents that answer a question. */
export const ACCOUNTS: readonly (readonly [
  string,
  number,
  number,
  SceneBand | null,
  number,
  readonly number[],
])[] = [
  ["Lufthansa Group", 0, 58, "warm", 7, [4]],
  ["SWISS", 0, 24, null, 3, []],
  ["Air France-KLM", 0, 21, null, 3, []],
  ["DHL Group", 1, 78, "hot", 9, [3, 6, 8]],
  ["Kuehne+Nagel", 1, 53, "warm", 6, [2]],
  ["DB Schenker", 1, 38, "cold", 5, [2]],
  ["DSV", 1, 22, null, 3, []],
  ["Siemens", 2, 41, "cold", 5, [1]],
  ["Bosch", 3, 27, null, 4, []],
  ["ZF Group", 3, 18, null, 2, []],
  ["Continental", 3, 25, null, 3, []],
  ["Schaeffler", 3, 16, null, 2, []],
  ["Commerzbank", 4, 26, null, 3, []],
  ["Erste Group", 4, 15, null, 2, []],
  ["Raiffeisen Bank International", 4, 14, null, 2, []],
  ["UBS", 4, 20, null, 3, []],
  ["Allianz", 5, 35, "cold", 4, [1]],
  ["Munich Re", 5, 23, null, 3, []],
  ["Zurich Insurance Group", 5, 17, null, 2, []],
  ["Generali", 5, 13, null, 2, []],
];

export const DHL = 3;
export const LUFTHANSA = 0;

export const SOURCES: readonly { name: string; angle: number }[] = [
  { name: "News", angle: 3.5 },
  { name: "Company sites", angle: 4.2 },
  { name: "Job boards", angle: 4.95 },
  { name: "Investor relations", angle: 5.7 },
];

export const QUOTE = "DHL setzt in über 1.000 Prozessen KI-Agenten ein…";
export const TRANSLATION = "DHL uses AI agents in more than 1,000 processes…";
export const QUOTE_SOURCE = "group.dhl.com, press release, 3 weeks ago";

/** DHL Group's score as rule segments: column 0 is Fit, column 1 Intent. */
export const RULES: readonly {
  col: 0 | 1;
  pts: number;
  label: string;
  val: string;
  txt: string;
  unknown?: true;
}[] = [
  { col: 0, pts: 37.5, label: "Sector", val: "Logistics", txt: "+37.5" },
  { col: 0, pts: 25.0, label: "Region", val: "Germany", txt: "+25.0" },
  { col: 0, pts: 12.5, label: "Size", val: "unknown", txt: "+12.5", unknown: true },
  { col: 0, pts: 12.5, label: "Complexity", val: "High", txt: "+12.5" },
  { col: 1, pts: 53.0, label: "AI projects", val: "Strong", txt: "+53.0" },
  { col: 1, pts: 19.0, label: "Cost programme", val: "Clear", txt: "" },
];

export const DHL_SCORES = { fit: 88, intent: 72, priority: 78 };

/**
 * The dies of the Sift wafer: LeadRadar's flows FL-01 to FL-22 in miniature, from diagrams/src/.
 * `n` lanes; each message is [from lane, to lane, position 0 to 1, 1 when it calls a model].
 */
export const FLOWS: readonly {
  id: string;
  n: number;
  m: readonly (readonly [number, number, number, number])[];
}[] = [
  {
    id: "FL-01",
    n: 6,
    m: [
      [0, 1, 0.0, 0],
      [1, 2, 0.07, 0],
      [2, 3, 0.14, 0],
      [2, 1, 0.211, 0],
      [0, 1, 0.324, 0],
      [1, 2, 0.395, 0],
      [2, 3, 0.465, 0],
      [2, 3, 0.535, 0],
      [4, 3, 0.605, 0],
      [4, 5, 0.676, 1],
      [4, 3, 0.746, 0],
      [0, 1, 0.86, 0],
      [1, 2, 0.93, 0],
      [2, 3, 1.0, 0],
    ],
  },
  {
    id: "FL-02",
    n: 5,
    m: [
      [0, 1, 0.0, 0],
      [1, 2, 0.089, 0],
      [2, 3, 0.178, 0],
      [0, 1, 0.322, 0],
      [1, 2, 0.411, 0],
      [2, 1, 0.5, 0],
      [0, 1, 0.644, 0],
      [1, 2, 0.733, 0],
      [2, 3, 0.822, 0],
      [4, 3, 0.911, 0],
      [1, 2, 1.0, 0],
    ],
  },
  {
    id: "FL-03",
    n: 6,
    m: [
      [0, 1, 0.0, 0],
      [1, 2, 0.121, 0],
      [2, 3, 0.318, 1],
      [2, 4, 0.439, 0],
      [2, 5, 0.636, 1],
      [5, 2, 0.757, 1],
      [2, 4, 0.879, 0],
      [2, 1, 1.0, 0],
    ],
  },
  {
    id: "FL-04",
    n: 5,
    m: [
      [0, 1, 0.0, 0],
      [1, 2, 0.138, 0],
      [2, 1, 0.276, 0],
      [0, 1, 0.5, 0],
      [1, 2, 0.638, 0],
      [2, 3, 0.776, 0],
      [4, 3, 1.0, 0],
    ],
  },
  {
    id: "FL-05",
    n: 6,
    m: [
      [0, 1, 0.0, 0],
      [1, 2, 0.089, 0],
      [2, 3, 0.178, 0],
      [5, 3, 0.267, 0],
      [0, 1, 0.411, 0],
      [1, 2, 0.5, 0],
      [2, 4, 0.589, 1],
      [2, 3, 0.678, 0],
      [0, 1, 0.822, 0],
      [1, 2, 0.911, 0],
      [2, 3, 1.0, 0],
    ],
  },
  {
    id: "FL-06",
    n: 7,
    m: [
      [0, 1, 0.0, 0],
      [1, 2, 0.104, 0],
      [2, 3, 0.208, 0],
      [4, 5, 0.312, 0],
      [4, 6, 0.416, 1],
      [4, 3, 0.52, 0],
      [1, 2, 0.688, 0],
      [0, 1, 0.792, 0],
      [1, 2, 0.896, 0],
      [2, 3, 1.0, 0],
    ],
  },
  {
    id: "FL-07",
    n: 8,
    m: [
      [0, 1, 0.0, 0],
      [1, 2, 0.078, 0],
      [2, 3, 0.156, 0],
      [4, 5, 0.281, 0],
      [5, 4, 0.359, 0],
      [4, 6, 0.437, 1],
      [4, 3, 0.515, 0],
      [4, 7, 0.641, 1],
      [4, 7, 0.719, 1],
      [4, 3, 0.796, 0],
      [4, 3, 0.922, 0],
      [1, 2, 1.0, 0],
    ],
  },
  {
    id: "FL-08",
    n: 3,
    m: [
      [0, 1, 0.0, 0],
      [0, 1, 0.138, 0],
      [0, 1, 0.276, 0],
      [2, 1, 0.5, 0],
      [2, 1, 0.638, 0],
      [2, 1, 0.776, 0],
      [0, 1, 1.0, 0],
    ],
  },
  {
    id: "FL-09",
    n: 6,
    m: [
      [0, 1, 0.0, 0],
      [1, 2, 0.121, 0],
      [2, 3, 0.243, 0],
      [4, 3, 0.439, 0],
      [4, 3, 0.561, 0],
      [4, 5, 0.682, 1],
      [4, 3, 0.803, 0],
      [4, 3, 1.0, 0],
    ],
  },
  {
    id: "FL-10",
    n: 5,
    m: [
      [0, 1, 0.0, 0],
      [1, 2, 0.178, 0],
      [2, 3, 0.356, 0],
      [4, 3, 0.644, 0],
      [4, 3, 0.822, 0],
      [4, 3, 1.0, 0],
    ],
  },
  {
    id: "FL-11",
    n: 4,
    m: [
      [0, 1, 0.0, 0],
      [1, 2, 0.121, 0],
      [2, 3, 0.243, 0],
      [2, 1, 0.364, 0],
      [0, 1, 0.561, 0],
      [1, 2, 0.682, 0],
      [0, 1, 0.879, 0],
      [0, 1, 1.0, 0],
    ],
  },
  {
    id: "FL-12",
    n: 4,
    m: [
      [0, 1, 0.0, 0],
      [1, 2, 0.089, 0],
      [1, 2, 0.178, 0],
      [2, 3, 0.267, 0],
      [2, 1, 0.356, 0],
      [0, 1, 0.5, 0],
      [1, 2, 0.589, 0],
      [2, 1, 0.678, 0],
      [0, 1, 0.822, 0],
      [1, 2, 0.911, 0],
      [2, 1, 1.0, 0],
    ],
  },
  {
    id: "FL-13",
    n: 5,
    m: [
      [0, 1, 0.0, 0],
      [1, 2, 0.098, 0],
      [2, 1, 0.195, 0],
      [0, 1, 0.353, 0],
      [1, 2, 0.451, 0],
      [2, 3, 0.549, 0],
      [4, 3, 0.647, 0],
      [0, 1, 0.805, 0],
      [1, 2, 0.902, 0],
      [2, 3, 1.0, 0],
    ],
  },
  {
    id: "FL-14",
    n: 5,
    m: [
      [0, 1, 0.0, 0],
      [3, 2, 0.197, 0],
      [4, 3, 0.318, 0],
      [3, 2, 0.439, 0],
      [2, 3, 0.561, 0],
      [4, 3, 0.757, 0],
      [3, 2, 0.879, 0],
      [2, 1, 1.0, 0],
    ],
  },
  {
    id: "FL-15",
    n: 5,
    m: [
      [0, 1, 0.0, 0],
      [1, 2, 0.178, 0],
      [2, 3, 0.356, 0],
      [4, 3, 0.644, 0],
      [1, 2, 0.822, 0],
      [2, 1, 1.0, 0],
    ],
  },
  {
    id: "FL-16",
    n: 7,
    m: [
      [0, 2, 0.0, 0],
      [2, 3, 0.094, 0],
      [3, 4, 0.188, 0],
      [0, 2, 0.283, 0],
      [2, 3, 0.377, 0],
      [3, 4, 0.471, 0],
      [1, 2, 0.623, 0],
      [2, 3, 0.717, 0],
      [5, 6, 0.812, 1],
      [5, 4, 0.906, 0],
      [2, 3, 1.0, 0],
    ],
  },
  {
    id: "FL-17",
    n: 5,
    m: [
      [0, 1, 0.0, 0],
      [1, 2, 0.131, 0],
      [2, 3, 0.263, 0],
      [2, 4, 0.394, 1],
      [4, 2, 0.525, 1],
      [2, 3, 0.656, 0],
      [0, 1, 0.869, 0],
      [1, 2, 1.0, 0],
    ],
  },
  {
    id: "FL-18",
    n: 5,
    m: [
      [0, 1, 0.0, 0],
      [0, 1, 0.151, 0],
      [1, 2, 0.396, 0],
      [2, 3, 0.547, 0],
      [3, 2, 0.698, 0],
      [2, 4, 0.849, 0],
      [2, 1, 1.0, 0],
    ],
  },
  {
    id: "FL-19",
    n: 4,
    m: [
      [0, 1, 0.0, 0],
      [1, 0, 0.116, 0],
      [0, 1, 0.232, 0],
      [1, 2, 0.348, 0],
      [2, 3, 0.464, 0],
      [2, 1, 0.58, 0],
      [0, 1, 0.768, 0],
      [1, 2, 0.884, 0],
      [2, 3, 1.0, 0],
    ],
  },
  {
    id: "FL-20",
    n: 4,
    m: [
      [0, 1, 0.0, 0],
      [1, 2, 0.151, 0],
      [2, 3, 0.302, 0],
      [0, 1, 0.547, 0],
      [1, 2, 0.698, 0],
      [2, 3, 0.849, 0],
      [2, 1, 1.0, 0],
    ],
  },
  {
    id: "FL-21",
    n: 4,
    m: [
      [0, 1, 0.0, 0],
      [1, 2, 0.178, 0],
      [2, 3, 0.356, 0],
      [2, 1, 0.534, 0],
      [0, 1, 0.822, 0],
      [1, 2, 1.0, 0],
    ],
  },
  {
    id: "FL-22",
    n: 4,
    m: [
      [0, 1, 0.0, 0],
      [1, 2, 0.108, 0],
      [2, 3, 0.216, 0],
      [0, 1, 0.392, 0],
      [1, 2, 0.5, 0],
      [2, 3, 0.608, 0],
      [0, 1, 0.784, 0],
      [1, 2, 0.892, 0],
      [2, 3, 1.0, 0],
    ],
  },
];
