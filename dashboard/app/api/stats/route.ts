const BACKEND = process.env.BACKEND_URL || 'http://localhost:4000';

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const period = searchParams.get('period') || '7d';
  const res = await fetch(`${BACKEND}/api/stats?period=${period}`, { cache: 'no-store' });
  return Response.json(await res.json());
}
