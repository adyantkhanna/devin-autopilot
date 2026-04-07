const BACKEND = process.env.BACKEND_URL || 'http://localhost:4000';

export async function POST(req: Request) {
  const body = await req.text();
  const res = await fetch(`${BACKEND}/api/config/mode`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body
  });
  return Response.json(await res.json());
}
