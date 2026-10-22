export async function fetchAllPages<TItem, TPage extends { items: TItem[]; total: number }>(
  fetchPage: (page: number) => Promise<TPage>,
): Promise<TPage> {
  const first = await fetchPage(1);
  const items = [...first.items];
  for (let page = 2; items.length < first.total; page += 1) {
    const next = await fetchPage(page);
    if (next.items.length === 0) break;
    items.push(...next.items);
  }
  return { ...first, items };
}
