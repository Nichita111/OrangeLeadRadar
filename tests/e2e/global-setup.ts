import { startStack } from "./support/stack";

export default async function globalSetup(): Promise<void> {
  await startStack();
}
