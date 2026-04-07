const BACKEND = process.env.BACKEND_URL || 'http://localhost:4000';

export async function POST(req: Request, { params }: { params: Promise<{ number: string }> }) {
  const { number } = await params;
  const body = await req.text();
  const res = await fetch(`${BACKEND}/api/issues/${number}/prioritize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body || '{"user":"dashboard"}'
  });
  return Response.json(await res.json());
}
