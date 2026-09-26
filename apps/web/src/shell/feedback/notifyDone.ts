import { toast } from "sonner";
import { MOTION } from "../../styles/motion";

export function notifyDone(message: string): void {
  toast.success(message, { duration: MOTION.toastVisibleMs });
}
