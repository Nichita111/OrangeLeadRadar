import type { components } from "../../api/schema.gen";

// PLACEHOLDER(invented): replace ids, versions and counts with seeded service records.
export const services: components["schemas"]["Service"][] = [
  {
    id: "service-automation",
    code: "INTELLIGENT_AUTOMATION",
    name: "Intelligent Automation",
    description:
      "Automating business processes end to end with RPA, AI, agentic AI and process mining, from discovery to operation.",
    value_proposition:
      "Orange Systems designs, builds and runs automation that removes manual work from finance, operations and customer processes, with measurable savings within months.",
    status: "ACTIVE",
    active_version: 1,
    draft_version: null,
    question_count: 9,
  },
  {
    id: "service-security",
    code: "CYBERSECURITY",
    name: "Cybersecurity services",
    description:
      "Security assessments, managed detection and response, and regulatory readiness for NIS2, DORA and the Cyber Resilience Act.",
    value_proposition:
      "Orange Systems assesses, strengthens and monitors a company's security posture and gets it audit-ready for European regulation.",
    status: "ACTIVE",
    active_version: 1,
    draft_version: null,
    question_count: 7,
  },
];
