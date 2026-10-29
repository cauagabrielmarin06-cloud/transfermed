// Descadastro em um clique pelo próprio programa de e-mail (RFC 8058: botão "Cancelar inscrição" do Gmail, Outlook
// e Yahoo). O cabeçalho List-Unsubscribe dos alertas aponta para cá com o token da pessoa; o programa faz um POST
// com "List-Unsubscribe=One-Click" e a função chama descadastrar() do schema.sql (apaga o cadastro e o histórico).
// GET (alguém que abriu o endereço no navegador) só leva à página de descadastro do site.
// Implantar no painel do Supabase: Edge Functions › Deploy a new function › Via Editor, nome "descadastrar",
// colar este arquivo e DESLIGAR "Verify JWT" (o programa de e-mail não manda chave).
const SITE = "https://www.transfermed.com.br/alerta/descadastrar/";
const TOKEN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

Deno.serve(async (req) => {
  const t = new URL(req.url).searchParams.get("t") ?? "";
  if (req.method === "GET") {
    return Response.redirect(SITE + (TOKEN.test(t) ? "?t=" + t : ""), 303);
  }
  if (req.method !== "POST") return new Response(null, { status: 405, headers: { Allow: "GET, POST" } });
  if (!TOKEN.test(t)) return new Response("Endereço de descadastro inválido.", { status: 400 });
  const chave = Deno.env.get("SUPABASE_ANON_KEY")!;
  const r = await fetch(Deno.env.get("SUPABASE_URL") + "/rest/v1/rpc/descadastrar", {
    method: "POST",
    headers: { apikey: chave, Authorization: `Bearer ${chave}`, "Content-Type": "application/json" },
    body: JSON.stringify({ p_token: t }),
  });
  // "ok" ou "nao_encontrado" (já descadastrado): para o programa de e-mail, as duas respostas encerram o pedido
  return new Response(r.ok ? "Pronto: você não recebe mais os alertas do Transfermed." : "Tente de novo mais tarde.",
    { status: r.ok ? 200 : 502, headers: { "Content-Type": "text/plain; charset=utf-8" } });
});
