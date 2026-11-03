// Liveness do servidor Next.js; não consulta a API nem serviços externos.
export function GET() {
  return Response.json({ status: "ok", service: "gestao-pessoal-web" });
}
