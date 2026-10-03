/**
 * Handles two kinds of Telegram updates:
 * 1. callback_query -- Approve/Reject button taps (existing flow)
 * 2. message with video/document -- you sent a clip to post (new flow)
 *
 * Worker secrets: TELEGRAM_BOT_TOKEN, GITHUB_TOKEN, GITHUB_REPO
 */

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("OK", { status: 200 });
    }

    const update = await request.json();

    // --- Approve/Reject button taps ---
    const callback = update.callback_query;
    if (callback && callback.data) {
      const [action, postId] = callback.data.split(":");
      const eventType = action === "approve" ? "approve_post" : "reject_post";

      await dispatchToGitHub(env, eventType, { post_id: postId });

      await answerCallback(env, callback.id, `${action}d!`);
      return new Response("OK", { status: 200 });
    }

    // --- Incoming video from you ---
    const message = update.message;
    if (message && (message.video || message.document)) {
      const fileId =
        message.video?.file_id || message.document?.file_id;
      const caption = message.caption || "";

      await dispatchToGitHub(env, "receive_video", {
        file_id: fileId,
        caption: caption,
      });

      // Acknowledge immediately so you know it was received
      await sendMessage(
        env,
        message.chat.id,
        "⏳ Got your video! Processing and posting — I'll confirm when it's live."
      );
    }

    return new Response("OK", { status: 200 });
  },
};

async function dispatchToGitHub(env, eventType, payload) {
  return fetch(
    `https://api.github.com/repos/${env.GITHUB_REPO}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "wyrd-viral-automation-worker",
      },
      body: JSON.stringify({
        event_type: eventType,
        client_payload: payload,
      }),
    }
  );
}

async function answerCallback(env, callbackQueryId, text) {
  return fetch(
    `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ callback_query_id: callbackQueryId, text }),
    }
  );
}

async function sendMessage(env, chatId, text) {
  return fetch(
    `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, text }),
    }
  );
}
