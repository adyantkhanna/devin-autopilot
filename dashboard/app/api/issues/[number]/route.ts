const BACKEND = process.env.BACKEND_URL || 'http://localhost:4000';

export async function GET(_: Request, { params }: { params: Promise<{ number: string }> }) {
  const { number } = await params;
  const res = await fetch(`${BACKEND}/api/issues/${number}`, { cache: 'no-store' });
  const data = await res.json();
  return Response.json(data);
}
