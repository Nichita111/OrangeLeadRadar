/**
 * Typed reading of `EvaluationResult.metrics`, the `metrics` object of [Evaluation metrics]
 * (/architecture/rules.md#evaluation-metrics): the api types it as a plain JSON object, so the
 * screen parses it once here rather than casting it apart wherever it is read.
 */

export interface ClassifierOnly {
  precision: number | null;
  recall: number | null;
}

export interface PerQuestionRow {
  key: string;
  service_id: string;
  items: number;
  precision: number | null;
  recall: number | null;
}

export interface PerSourceTypeRow {
  items: number;
  precision: number | null;
  recall: number | null;
}

export interface MissedEvidence {
  items: number;
  positive_rate: number | null;
}

export interface CalibrationBin {
  count: number;
  mean_p: number | null;
  positive_rate: number | null;
}

export interface MistakeDocument {
  title: string | null;
  url: string;
}

export interface Mistake {
  item_id: string;
  expected: string;
  predicted: string;
  p_positive: number;
  escalated: boolean;
  question_key: string | null;
  passage_text: string | null;
  document: MistakeDocument | null;
}

export interface LeadVerdictCounts {
  RELEVANT: number;
  NOT_RELEVANT: number;
}

export interface Metrics {
  items: number;
  tp: number;
  fp: number;
  tn: number;
  fn: number;
  precision: number | null;
  recall: number | null;
  strength_agreement: number | null;
  escalation_rate: number | null;
  classifier_only: ClassifierOnly;
  per_question: Record<string, PerQuestionRow>;
  per_source_type: Record<string, PerSourceTypeRow>;
  missed_evidence: MissedEvidence;
  calibration: CalibrationBin[];
  errors: Mistake[];
  lead_verdicts: Record<string, LeadVerdictCounts>;
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" ? value : fallback;
}

function asNullableNumber(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}

function asNullableString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function asBoolean(value: unknown): boolean {
  return value === true;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function classifierOnly(value: unknown): ClassifierOnly {
  const record = asRecord(value);
  return {
    precision: asNullableNumber(record["precision"]),
    recall: asNullableNumber(record["recall"]),
  };
}

function perQuestion(value: unknown): Record<string, PerQuestionRow> {
  const record = asRecord(value);
  const result: Record<string, PerQuestionRow> = {};
  for (const [questionId, raw] of Object.entries(record)) {
    const row = asRecord(raw);
    result[questionId] = {
      key: asNullableString(row["key"]) ?? questionId,
      service_id: asNullableString(row["service_id"]) ?? "",
      items: asNumber(row["items"]),
      precision: asNullableNumber(row["precision"]),
      recall: asNullableNumber(row["recall"]),
    };
  }
  return result;
}

function perSourceType(value: unknown): Record<string, PerSourceTypeRow> {
  const record = asRecord(value);
  const result: Record<string, PerSourceTypeRow> = {};
  for (const [sourceType, raw] of Object.entries(record)) {
    const row = asRecord(raw);
    result[sourceType] = {
      items: asNumber(row["items"]),
      precision: asNullableNumber(row["precision"]),
      recall: asNullableNumber(row["recall"]),
    };
  }
  return result;
}

function missedEvidence(value: unknown): MissedEvidence {
  const record = asRecord(value);
  return {
    items: asNumber(record["items"]),
    positive_rate: asNullableNumber(record["positive_rate"]),
  };
}

function calibration(value: unknown): CalibrationBin[] {
  return asArray(value).map((entry) => {
    const row = asRecord(entry);
    return {
      count: asNumber(row["count"]),
      mean_p: asNullableNumber(row["mean_p"]),
      positive_rate: asNullableNumber(row["positive_rate"]),
    };
  });
}

function mistakeDocument(value: unknown): MistakeDocument | null {
  if (value === null || value === undefined) {
    return null;
  }
  const row = asRecord(value);
  const url = row["url"];
  return typeof url === "string" ? { title: asNullableString(row["title"]), url } : null;
}

function errors(value: unknown): Mistake[] {
  return asArray(value).map((entry) => {
    const row = asRecord(entry);
    return {
      item_id: asNullableString(row["item_id"]) ?? "",
      expected: asNullableString(row["expected"]) ?? "",
      predicted: asNullableString(row["predicted"]) ?? "",
      p_positive: asNumber(row["p_positive"]),
      escalated: asBoolean(row["escalated"]),
      question_key: asNullableString(row["question_key"]),
      passage_text: asNullableString(row["passage_text"]),
      document: mistakeDocument(row["document"]),
    };
  });
}

function leadVerdicts(value: unknown): Record<string, LeadVerdictCounts> {
  const record = asRecord(value);
  const result: Record<string, LeadVerdictCounts> = {};
  for (const [band, raw] of Object.entries(record)) {
    const row = asRecord(raw);
    result[band] = {
      RELEVANT: asNumber(row["RELEVANT"]),
      NOT_RELEVANT: asNumber(row["NOT_RELEVANT"]),
    };
  }
  return result;
}

/** Parses `EvaluationResult.metrics` into the typed shape [Evaluation metrics]
 * (/architecture/rules.md#evaluation-metrics) defines. */
export function parseMetrics(raw: Record<string, unknown>): Metrics {
  return {
    items: asNumber(raw["items"]),
    tp: asNumber(raw["tp"]),
    fp: asNumber(raw["fp"]),
    tn: asNumber(raw["tn"]),
    fn: asNumber(raw["fn"]),
    precision: asNullableNumber(raw["precision"]),
    recall: asNullableNumber(raw["recall"]),
    strength_agreement: asNullableNumber(raw["strength_agreement"]),
    escalation_rate: asNullableNumber(raw["escalation_rate"]),
    classifier_only: classifierOnly(raw["classifier_only"]),
    per_question: perQuestion(raw["per_question"]),
    per_source_type: perSourceType(raw["per_source_type"]),
    missed_evidence: missedEvidence(raw["missed_evidence"]),
    calibration: calibration(raw["calibration"]),
    errors: errors(raw["errors"]),
    lead_verdicts: leadVerdicts(raw["lead_verdicts"]),
  };
}
