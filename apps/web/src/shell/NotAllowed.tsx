/** `FR-006`: a `403` shows a "Not allowed" page naming the role required. Named `requiredRole`,
 * not `role`, so jsx-a11y's `aria-role` rule does not read this as an ARIA role. */
export function NotAllowed({ requiredRole }: { requiredRole: string }) {
  return (
    <div className="flex flex-col items-center gap-2 py-24 text-center">
      <h1 className="text-[24px] font-semibold text-text">Not allowed</h1>
      <p className="text-sm text-text-secondary">This screen needs the {requiredRole} role.</p>
    </div>
  );
}
