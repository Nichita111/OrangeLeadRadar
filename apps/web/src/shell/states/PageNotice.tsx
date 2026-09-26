import { ButtonLink } from "../../components/Button";
import { PageHeader } from "../PageHeader";

interface PageNoticeProps {
  title: string;
  lead: string;
  linkLabel: string;
}

/** A page that says one thing and links to Prospects. */
export function PageNotice({ title, lead, linkLabel }: PageNoticeProps) {
  return (
    <div className="flex flex-col items-start gap-4">
      <PageHeader title={title} lead={lead} />
      <ButtonLink to="/prospects" variant="secondary">
        {linkLabel}
      </ButtonLink>
    </div>
  );
}
