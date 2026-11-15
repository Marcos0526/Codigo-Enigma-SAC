const BACKEND_URL = (
  process.env.API_BACKEND_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");

function backendTarget(request: Request, path: string[]): string {
  const requestUrl = new URL(request.url);
  return `${BACKEND_URL}/api/v1/${path.join("/")}${requestUrl.search}`;
}

function forwardableHeaders(request: Request): Headers {
  const headers = new Headers(request.headers);
  ["host", "connection", "content-length", "accept-encoding"].forEach((name) =>
    headers.delete(name),
  );
  return headers;
}

function responseHeaders(backendResponse: Response): Headers {
  const headers = new Headers(backendResponse.headers);
  [
    "content-encoding",
    "content-length",
    "transfer-encoding",
    "connection",
  ].forEach((name) => headers.delete(name));
  return headers;
}

async function proxyRequest(
  request: Request,
  context: { params: { path: string[] } },
): Promise<Response> {
  const method = request.method.toUpperCase();
  const body =
    method === "GET" || method === "HEAD"
      ? undefined
      : await request.arrayBuffer();

  try {
    const backendResponse = await fetch(backendTarget(request, context.params.path), {
      method,
      headers: forwardableHeaders(request),
      body,
      cache: "no-store",
    });
    return new Response(backendResponse.body, {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      headers: responseHeaders(backendResponse),
    });
  } catch (error) {
    console.error("API proxy failed", {
      method,
      path: context.params.path.join("/"),
      error: error instanceof Error ? error.message : String(error),
    });
    return Response.json(
      {
        error: {
          code: "API_PROXY_UNAVAILABLE",
          message: "The Enigma SAC API is currently unavailable.",
        },
      },
      { status: 502 },
    );
  }
}

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const PATCH = proxyRequest;
export const DELETE = proxyRequest;
export const OPTIONS = proxyRequest;
