// Typed fixtures of the alerts contracts (`API-48`, `API-49`) for the development mock (TypeScript
// Mock layer): the alerts the latest scoring of the prospects fixtures would have raised.
import type { Schemas } from "../api/contract";

type AlertView = Schemas["AlertView"];

const intelligentAutomation = { id: "svc-1", name: "Intelligent Automation" };

export const alerts: AlertView[] = [
  {
    id: "alr-dhl-signal",
    created_at: "2026-09-25T06:00:00Z",
    kind: "STRONG_SIGNAL",
    account: { id: "acc-dhl", name: "DHL Group" },
    service: intelligentAutomation,
    finding: {
      id: "fnd-dhl-ai",
      question_text: "AI and automation projects",
      strength: "STRONG",
      quote: "Wir führen KI-gestützte Automatisierung in allen Paketzentren ein.",
    },
    band_change: null,
    acknowledged_at: null,
    acknowledged_by_name: null,
  },
  {
    id: "alr-dhl-band",
    created_at: "2026-09-25T06:00:00Z",
    kind: "BAND_UP",
    account: { id: "acc-dhl", name: "DHL Group" },
    service: intelligentAutomation,
    finding: null,
    band_change: { from: "WARM", to: "HOT" },
    acknowledged_at: null,
    acknowledged_by_name: null,
  },
  {
    id: "alr-lh-signal",
    created_at: "2026-08-13T06:00:00Z",
    kind: "STRONG_SIGNAL",
    account: { id: "acc-lh", name: "Lufthansa Group" },
    service: intelligentAutomation,
    finding: {
      id: "fnd-cost",
      question_text: "Cost programme",
      strength: "STRONG",
      quote: "Wir senken die Kosten um 500 Millionen Euro.",
    },
    band_change: null,
    acknowledged_at: "2026-08-14T09:12:00Z",
    acknowledged_by_name: "Ana Sales",
  },
];
