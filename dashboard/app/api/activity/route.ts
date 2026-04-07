const BACKEND = process.env.BACKEND_URL || 'http://localhost:4000';

export async function GET() {
  const res = await fetch(`${BACKEND}/api/activity`, { cache: 'no-store' });
  return Response.json(await res.json());
}
