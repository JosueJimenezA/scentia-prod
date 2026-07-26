import './globals.css';

export const metadata = {
  title: 'SCENTIA | High-End Perfumery Intelligence',
  description: 'Personalized fragrance discovery and collection platform.',
};

export default function RootLayout({ children }) {
  return (
    <html lang="es">
      <body className="bg-neutral-950 text-neutral-100 antialiased font-sans min-h-screen">
        {children}
      </body>
    </html>
  );
}