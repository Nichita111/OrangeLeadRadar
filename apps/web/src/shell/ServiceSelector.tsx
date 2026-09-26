import { Select } from "../components/controls";
import { useServiceSelection } from "./SelectedService";

/** FR-003: the header's service selector, a native select labelled "Service". */
export function ServiceSelector() {
  const { active, service, select } = useServiceSelection();
  if (service === null) {
    return null;
  }
  return (
    <label className="flex items-center gap-2 text-text-secondary">
      Service
      <Select
        value={service.id}
        className="w-auto"
        onChange={(event) => {
          select(event.target.value);
        }}
      >
        {active.map((candidate) => (
          <option key={candidate.id} value={candidate.id}>
            {candidate.name}
          </option>
        ))}
      </Select>
    </label>
  );
}
