const BACKEND = process.env.BACKEND_URL || 'http://localhost:4000';

export async function POST(_: Request, { params }: { params: Promise<{ number: string }> }) {
  const { number } = await params;
  const res = await fetch(`${BACKEND}/api/issues/${number}/pause`, { method: 'POST' });
  return Response.json(await res.json());
}
