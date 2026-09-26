import { Toaster as SonnerToaster } from "sonner";
import type { ReactElement } from "react";
import { MOTION } from "../../styles/motion";

export function Toaster(): ReactElement {
  return (
    <div role="status">
      <SonnerToaster duration={MOTION.toastVisibleMs} closeButton richColors />
    </div>
  );
}
