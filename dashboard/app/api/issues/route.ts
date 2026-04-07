const BACKEND = process.env.BACKEND_URL || 'http://localhost:4000';

export async function GET() {
  const res = await fetch(`${BACKEND}/api/issues`, { cache: 'no-store' });
  const data = await res.json();
  return Response.json(data);
}
