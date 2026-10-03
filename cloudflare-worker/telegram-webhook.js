/**
 * Receives Telegram's webhook callback when you tap Approve/Reject, and
 * relays it to GitHub as a repository_dispatch event, which triggers
 * .github/workflows/publish.yml.
 *
 * Deploy with Wrangler (see README). Set these as Worker secrets:
 *   TELEGRAM_BOT_TOKEN
 *   GITHUB_TOKEN        -- a fine-grained PAT scoped to just this repo,
 *                          "Contents: read" + "Actions: read and write"
 *   GITHUB_REPO         -- "yourusername/wyrd-viral-automation"
 *
 * After deploying, set the webhook once:
 *   curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=<worker-url>"
 */

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("OK", { status: 200 });
    }

    const update = await request.json();
    const callback = update.callback_query;

    if (!callback || !callback.data) {
      return new Response("No callback data", { status: 200 });
    }

    const [action, postId] = callback.data.split(":");
    const eventType = action === "approve" ? "approve_post" : "reject_post";

    const dispatchResponse = await fetch(
      `https://api.github.com/repos/${env.GITHUB_REPO}/dispatches`,
      {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
          "Accept": "application/vnd.github+json",
          "User-Agent": "wyrd-viral-automation-worker",
        },
        body: JSON.stringify({
          event_type: eventType,
          client_payload: { post_id: postId },
        }),
      }
    );

    // Acknowledge the tap in Telegram so the loading spinner clears
    await fetch(
      `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          callback_query_id: callback.id,
          text: dispatchResponse.ok ? `${action}d!` : "Something went wrong",
        }),
      }
    );

    return new Response("OK", { status: 200 });
  },
};
