/**
 * Telegram -> GitHub bridge.
 *
 * 1. callback_query  -- Approve/Reject button taps (existing flow)
 * 2. video/document  -- starts a short chat: title -> description -> tags,
 *                       then dispatches "receive_video" to GitHub Actions
 * 3. text            -- the answers to those three questions (/cancel to abort)
 *
 * Conversation state lives in Cloudflare KV (binding SESSIONS), 1 hour expiry.
 *
 * Worker secrets: TELEGRAM_BOT_TOKEN, GITHUB_TOKEN, GITHUB_REPO
 * Optional secret: ALLOWED_CHAT_ID -- if set, messages from any other chat are ignored
 */

const SESSION_TTL_SECONDS = 3600;
const TG_DOWNLOAD_LIMIT = 20 * 1024 * 1024; // Bot API getFile limit
const YT_TITLE_MAX = 100;

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

    const message = update.message;
    if (!message) return new Response("OK", { status: 200 });

    const chatId = message.chat.id;
    if (env.ALLOWED_CHAT_ID && String(chatId) !== String(env.ALLOWED_CHAT_ID)) {
      return new Response("OK", { status: 200 });
    }
    const key = `sess:${chatId}`;

    // --- Incoming video: start (or restart) the conversation ---
    const media = message.video || message.document;
    if (media) {
      if (message.document && !(media.mime_type || "").startsWith("video/")) {
        await sendMessage(env, chatId, "That file isn't a video. Send an mp4 or mov.");
        return new Response("OK", { status: 200 });
      }
      if (media.file_size && media.file_size > TG_DOWNLOAD_LIMIT) {
        await sendMessage(
          env,
          chatId,
          "⚠️ That video is over 20 MB, which is Telegram's limit for bots. Compress or trim it and send again."
        );
        return new Response("OK", { status: 200 });
      }
      await env.SESSIONS.put(
        key,
        JSON.stringify({ step: "title", file_id: media.file_id }),
        { expirationTtl: SESSION_TTL_SECONDS }
      );
      await sendMessage(
        env,
        chatId,
        "Got the video ✅\n\n1/3 — Send the TITLE (it will also be burned onto the video)."
      );
      return new Response("OK", { status: 200 });
    }

    // --- Text answers ---
    const text = (message.text || "").trim();
    if (!text) return new Response("OK", { status: 200 });

    if (text === "/cancel") {
      await env.SESSIONS.delete(key);
      await sendMessage(env, chatId, "Cancelled. Send a new video whenever you're ready.");
      return new Response("OK", { status: 200 });
    }
    if (text.startsWith("/")) {
      return new Response("OK", { status: 200 }); // ignore other commands (e.g. /start)
    }

    const raw = await env.SESSIONS.get(key);
    if (!raw) {
      await sendMessage(env, chatId, "Send me a video first, then I'll ask for the title, description and tags.");
      return new Response("OK", { status: 200 });
    }
    const session = JSON.parse(raw);

    if (session.step === "title") {
      if (text.length > YT_TITLE_MAX) {
        await sendMessage(
          env,
          chatId,
          `That title is ${text.length} characters; YouTube's limit is ${YT_TITLE_MAX}. Send a shorter one.`
        );
        return new Response("OK", { status: 200 });
      }
      session.title = text;
      session.step = "description";
      await env.SESSIONS.put(key, JSON.stringify(session), { expirationTtl: SESSION_TTL_SECONDS });
      await sendMessage(env, chatId, "2/3 — Send the DESCRIPTION.");
    } else if (session.step === "description") {
      session.description = text;
      session.step = "tags";
      await env.SESSIONS.put(key, JSON.stringify(session), { expirationTtl: SESSION_TTL_SECONDS });
      await sendMessage(env, chatId, "3/3 — Send the TAGS (comma-separated or #hashtags).");
    } else if (session.step === "tags") {
      await dispatchToGitHub(env, "receive_video", {
        file_id: session.file_id,
        title: session.title,
        description: session.description,
        tags: text,
      });
      await env.SESSIONS.delete(key);
      await sendMessage(
        env,
        chatId,
        `⏳ Processing and posting "${session.title}" to YouTube — I'll confirm when it's live.`
      );
    }

    return new Response("OK", { status: 200 });
  },
};

async function dispatchToGitHub(env, eventType, payload) {
  return fetch(`https://api.github.com/repos/${env.GITHUB_REPO}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "wyrd-viral-automation-worker",
    },
    body: JSON.stringify({ event_type: eventType, client_payload: payload }),
  });
}

async function answerCallback(env, callbackQueryId, text) {
  return fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ callback_query_id: callbackQueryId, text }),
  });
}

async function sendMessage(env, chatId, text) {
  return fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text }),
  });
}
