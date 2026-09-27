import { stopStack } from "./support/stack";

export default async function globalTeardown(): Promise<void> {
  stopStack();
}
