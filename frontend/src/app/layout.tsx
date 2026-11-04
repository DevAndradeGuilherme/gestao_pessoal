import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Gestão Pessoal",
  description: "Agenda, tarefas e rotinas integradas ao WhatsApp e ao Google Agenda.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="pt-BR" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
