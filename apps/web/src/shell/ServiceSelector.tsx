/** The header's service selector (`FR-003`, WF-01): a native select labelled "Service". */
import { useServiceSelection } from "./selected-service";

export function ServiceSelector() {
  const { active, service, select } = useServiceSelection();
  if (service === null) {
    return null;
  }
  return (
    <label className="ml-auto flex items-center gap-2 text-sm text-text-secondary">
      Service
      <select
        value={service.id}
        onChange={(event) => {
          select(event.target.value);
        }}
        className="rounded-control border border-border bg-surface px-3 text-sm text-text"
        style={{ height: "var(--ctl-input)" }}
      >
        {active.map((candidate) => (
          <option key={candidate.id} value={candidate.id}>
            {candidate.name}
          </option>
        ))}
      </select>
    </label>
  );
}
