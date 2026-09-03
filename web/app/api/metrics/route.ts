/**
 * BFF das métricas. O painel é um componente de servidor e lê direto pelo
 * `buscarMetricas`; esta rota existe para consumo externo (um monitor, um
 * script) sem que ninguém precise saber o endereço do núcleo.
 */

import { NextResponse } from "next/server";

import { buscarMetricas } from "@/lib/metrics";

export const dynamic = "force-dynamic";

export async function GET(): Promise<NextResponse> {
  const metricas = await buscarMetricas();
  if (!metricas) {
    return NextResponse.json({ error: "núcleo indisponível" }, { status: 503 });
  }
  return NextResponse.json(metricas);
}
