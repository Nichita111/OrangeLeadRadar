import { ApiError } from "../../api/client";
import { Callout } from "../../components/Callout";
import { screenWording } from "../../shell/states/degradation";

/** The unavailable wording of a `503` or `429` (FR-027 States), else the error's message. */
export function PreviewErrorNotice({ error }: { error: Error }) {
  const wording =
    error instanceof ApiError
      ? screenWording(error.envelope.error.code, error.envelope.error.details?.dependency)
      : null;
  return <Callout kind="error">{wording?.headline ?? error.message}</Callout>;
}
