// Bowling Bro' photo reader: a Supabase Edge Function.
// The app sends a cropped JPEG of a lane scoreboard; this asks Claude to read every bowler line
// and returns the marks, split markers and running totals exactly as printed. The app does the
// arithmetic and makes the bowler check every frame before anything is saved.
//
// Secrets (Supabase dashboard > Edge Functions > Secrets):
//   ANTHROPIC_API_KEY  required
//   READ_MODEL         optional, defaults to claude-sonnet-5-5
//   DAILY_READ_CAP     optional, photos per bowler per 24 hours, defaults to 25
// SUPABASE_URL and SUPABASE_PUBLISHABLE_KEYS are provided by Supabase automatically.
import { createClient } from "jsr:@supabase/supabase-js@2";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const MODEL = Deno.env.get("READ_MODEL") || "claude-sonnet-5-5";
const DAILY_CAP = Number(Deno.env.get("DAILY_READ_CAP") || "25");

const PROMPT = `This is a photo of a bowling center's lane scoreboard, usually cropped to one or a few bowler lines.
Read every bowler line you can see. For each line report:
- name: the bowler name exactly as printed.
- frames: all 10 frames in order. For each frame, "marks" lists what is printed in the small ball boxes, left to right, one character each:
  X = strike, / = spare, - = miss or gutter (use - for a printed 0 too), F = foul, or a digit 1-9.
  Frames 1-9 have one mark after a strike, otherwise two. Frame 10 has two or three.
  Leave marks empty for a frame that has not been bowled yet.
- first_ball_red: true when that frame's first-ball count is printed in red or circled. The scoreboard uses this to mark a split.
- total: the running score printed under that frame, or null if it is blank or unreadable.
- final: the game's final score as printed, or null.
Report only what is printed. Do not work out or correct any numbers, even if they do not seem to add up.
If this is not a bowling scoreboard or nothing can be read, set readable to false and say why in problem.
Give your answer by calling the report_scoreboard tool once. Do not reply with text.`;

const TOOL = {
  name: "report_scoreboard",
  description: "Report the bowler lines read from the scoreboard photo.",
  input_schema: {
    type: "object",
    properties: {
      readable: { type: "boolean" },
      problem: { type: "string" },
      lines: {
        type: "array",
        items: {
          type: "object",
          properties: {
            name: { type: "string" },
            frames: {
              type: "array",
              items: {
                type: "object",
                properties: {
                  marks: { type: "array", items: { type: "string" } },
                  first_ball_red: { type: "boolean" },
                  total: { type: ["integer", "null"] },
                },
                required: ["marks"],
              },
            },
            final: { type: ["integer", "null"] },
          },
          required: ["name", "frames"],
        },
      },
    },
    required: ["readable", "lines"],
  },
};

// the project's publishable key (the newer replacement for the anon key), with the legacy anon
// key as a fallback for older projects
function publishableKey(): string {
  try {
    const keys = JSON.parse(Deno.env.get("SUPABASE_PUBLISHABLE_KEYS") || "{}");
    const k = keys.default || Object.values(keys)[0];
    if (typeof k === "string" && k) return k;
  } catch (_e) { /* fall through */ }
  return Deno.env.get("SUPABASE_ANON_KEY") || "";
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json" } });
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json({ error: "method" }, 405);
  try {
    // only signed-in bowlers can read photos; the bowler's own token is used for the usage log,
    // so row-level security keeps each bowler to their own rows
    const auth = req.headers.get("Authorization") || "";
    const db = createClient(Deno.env.get("SUPABASE_URL")!, publishableKey(), {
      global: { headers: { Authorization: auth } },
    });
    const { data: { user } } = await db.auth.getUser(auth.replace(/^Bearer\s+/i, ""));
    if (!user) return json({ error: "signin" }, 401);

    const since = new Date(Date.now() - 24 * 3600 * 1000).toISOString();
    const { count } = await db.from("bb_photo_reads").select("id", { count: "exact", head: true })
      .eq("user_id", user.id).gte("read_at", since);
    if ((count || 0) >= DAILY_CAP) return json({ error: "daily_limit", cap: DAILY_CAP }, 429);

    const body = await req.json().catch(() => null);
    const image = body && body.image;
    const mediaType = (body && body.mediaType) || "image/jpeg";
    if (typeof image !== "string" || image.length < 100 || image.length > 7_000_000 ||
        !["image/jpeg", "image/png", "image/webp"].includes(mediaType)) {
      return json({ error: "bad_image" }, 400);
    }

    const r = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "x-api-key": Deno.env.get("ANTHROPIC_API_KEY")!,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: MODEL,
        max_tokens: 2500,
        tools: [TOOL],
        // newer models don't accept a forced tool call, so the tool is offered and the prompt asks for it
        tool_choice: { type: "auto" },
        messages: [{
          role: "user",
          content: [
            { type: "image", source: { type: "base64", media_type: mediaType, data: image } },
            { type: "text", text: PROMPT },
          ],
        }],
      }),
    });
    if (!r.ok) {
      const text = await r.text();
      console.error("anthropic", r.status, text);
      // pass Claude's own error message back (it never contains the key) so the app can show it
      let message = text.slice(0, 160);
      try { message = JSON.parse(text).error.message || message; } catch (_e) { /* keep raw text */ }
      return json({ error: "read_failed", message: "Claude " + r.status + ": " + message }, 502);
    }
    const out = await r.json();
    await db.from("bb_photo_reads").insert({
      user_id: user.id, model: MODEL,
      input_tokens: out.usage?.input_tokens ?? null, output_tokens: out.usage?.output_tokens ?? null,
    });
    const content = out.content || [];
    const use = content.find((c: { type: string }) => c.type === "tool_use");
    if (use) return json(use.input);
    // fallback: the answer came back as text; take the JSON object out of it
    const text = content.filter((c: { type: string }) => c.type === "text").map((c: { text: string }) => c.text).join("\n");
    const start = text.indexOf("{"), end = text.lastIndexOf("}");
    if (start !== -1 && end > start) {
      try {
        const parsed = JSON.parse(text.slice(start, end + 1));
        if (parsed && Array.isArray(parsed.lines)) return json(parsed);
      } catch (_e) { /* fall through */ }
    }
    return json({ error: "read_failed", message: "no answer (" + (out.stop_reason || "unknown") + ") " + text.slice(0, 100) }, 502);
  } catch (e) {
    console.error(e);
    return json({ error: "server", message: String((e as Error)?.message || e).slice(0, 160) }, 500);
  }
});
