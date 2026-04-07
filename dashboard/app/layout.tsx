import './globals.css';

export const metadata = {
  title: 'Devin Autopilot',
  description: 'AI-driven GitHub issue triage and dispatch'
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
