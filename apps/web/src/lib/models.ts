// F05-AC10: which model answered, in words a nurse understands. Cloud models get their
// product name, local models (Ollama, F05-AC13) are marked as local.

export function modelLabel(model: string): string {
  if (model.startsWith("mistral-small")) return "Mistral Small";
  if (model.includes("(")) return model; // test stand-ins name themselves
  return `${model} (lokal)`;
}
