import './globals.css';

export const metadata = {
  title: 'FinServ Issue Ops',
  description: 'AI-powered issue triage and resolution for FinServ engineering'
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
