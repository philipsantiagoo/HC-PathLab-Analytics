type Entrada<T> = { valor: T; expiraEm: number };

const cache = new Map<string, Entrada<unknown>>();

export async function emCache<T>(chave: string, carregar: () => Promise<T>, ttlMs = 30_000): Promise<T> {
  const atual = cache.get(chave) as Entrada<T> | undefined;
  if (atual && atual.expiraEm > Date.now()) return atual.valor;
  const valor = await carregar();
  cache.set(chave, { valor, expiraEm: Date.now() + ttlMs });
  return valor;
}

export function invalidarCache(...chaves: string[]) {
  chaves.forEach(chave => cache.delete(chave));
}
