import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    status: "ok",
    app_name: "Before You Pay",
    version: "0.1.0",
  });
}
