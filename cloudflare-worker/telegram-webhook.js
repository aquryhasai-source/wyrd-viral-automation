/**
 * Telegram -> GitHub bridge.
 *
 * Conversation (state in Cloudflare KV, binding SESSIONS, 1 hour expiry):
 *   send video -> title -> description -> tags
 *              -> [On-screen title: On/Off] -> [Subtitles: On/Off]
 *              -> dispatches "receive_video" to GitHub Actions
 * The pipeline then renders the video and sends it back with Approve / Reject
 * buttons; tapping a button dispatches "approve_post" / "reject_post".
 *
 * Worker secrets: TELEGRAM_BOT_TOKEN, GITHUB_TOKEN, GITHUB_REPO
 * Optional secret: ALLOWED_CHAT_ID -- if set, other chats are ignored
 */

const SESSION_TTL_SECONDS = 3600;
const TG_DOWNLOAD_LIMIT = 20 * 1024 * 1024; // Bot API getFile limit
const YT_TITLE_MAX = 100;

const OK = () => new Response("OK", { status: 200 });

export default {
  async fetch(request, env) {
    if (request.method !== "POST") return OK();

    const update = await request.json();

    // ---------------------------------------------------------- button taps
    const callback = update.callback_query;
    if (callback && callback.data) {
      const chatId = callback.message && callback.message.chat.id;
      if (env.ALLOWED_CHAT_ID && String(chatId) !== String(env.ALLOWED_CHAT_ID)) return OK();
      return handleCallback(env, callback, chatId);
    }

    const message = update.message;
    if (!message) return OK();

    const chatId = message.chat.id;
    if (env.ALLOWED_CHAT_ID && String(chatId) !== String(env.ALLOWED_CHAT_ID)) return OK();
    const key = `sess:${chatId}`;

    // ------------------------------------------- incoming video: start over
    const media = message.video || message.document;
    if (media) {
      if (message.document && !(media.mime_type || "").startsWith("video/")) {
        await sendMessage(env, chatId, "That file isn't a video. Send an mp4 or mov.");
        return OK();
      }
      if (media.file_size && media.file_size > TG_DOWNLOAD_LIMIT) {
        await sendMessage(
          env,
          chatId,
          "⚠️ That video is over 20 MB, which is Telegram's limit for bots. Compress or trim it and send again."
        );
        return OK();
      }
      await putSession(env, key, { step: "title", file_id: media.file_id });
      await sendMessage(
        env,
        chatId,
        "Got the video ✅\n\n1/5 — Send the TITLE (this is the YouTube title)."
      );
      return OK();
    }

    // ------------------------------------------------------------ text answers
    const text = (message.text || "").trim();
    if (!text) return OK();

    if (text === "/cancel") {
      await env.SESSIONS.delete(key);
      await sendMessage(env, chatId, "Cancelled. Send a new video whenever you're ready.");
      return OK();
    }
    if (text.startsWith("/")) return OK(); // ignore other commands (e.g. /start)

    const raw = await env.SESSIONS.get(key);
    if (!raw) {
      await sendMessage(env, chatId, "Send me a video first, then I'll ask for the title, description and tags.");
      return OK();
    }
    const session = JSON.parse(raw);

    if (session.step === "title") {
      if (text.length > YT_TITLE_MAX) {
        await sendMessage(
          env,
          chatId,
          `That title is ${text.length} characters; YouTube's limit is ${YT_TITLE_MAX}. Send a shorter one.`
        );
        return OK();
      }
      session.title = text;
      session.step = "description";
      await putSession(env, key, session);
      await sendMessage(env, chatId, "2/5 — Send the DESCRIPTION.");
    } else if (session.step === "description") {
      session.description = text;
      session.step = "tags";
      await putSession(env, key, session);
      await sendMessage(env, chatId, "3/5 — Send the TAGS (comma-separated or #hashtags).");
    } else if (session.step === "tags") {
      session.tags = text;
      session.step = "opt_title";
      await putSession(env, key, session);
      await askToggle(
        env,
        chatId,
        "4/5 — Show the TITLE on the video? (top of the screen for the first 3 seconds)",
        "title"
      );
    } else {
      // waiting on a button tap
      await sendMessage(env, chatId, "Please tap one of the buttons above, or send /cancel.");
    }
    return OK();
  },
};

// -------------------------------------------------------------- callbacks
async function handleCallback(env, callback, chatId) {
  const parts = callback.data.split(":");
  const kind = parts[0];
  const messageId = callback.message.message_id;

  // Approve / Reject on a rendered preview
  if (kind === "approve" || kind === "reject") {
    const postId = parts[1];
    await dispatchToGitHub(env, kind === "approve" ? "approve_post" : "reject_post", { post_id: postId });
    await answerCallback(env, callback.id, kind === "approve" ? "Approved — uploading…" : "Rejected");
    await clearButtons(env, chatId, messageId);
    await sendMessage(
      env,
      chatId,
      kind === "approve" ? "✅ Approved. Uploading to YouTube…" : "🗑 Rejected. The preview was discarded."
    );
    return OK();
  }

  // On/Off toggles during the questions: opt:<title|subs>:<1|0>
  if (kind === "opt") {
    const which = parts[1];
    const on = parts[2] === "1";
    const key = `sess:${chatId}`;
    const raw = await env.SESSIONS.get(key);
    if (!raw) {
      await answerCallback(env, callback.id, "Session expired — send the video again.");
      await clearButtons(env, chatId, messageId);
      return OK();
    }
    const session = JSON.parse(raw);
    if (session.step !== `opt_${which}`) {
      await answerCallback(env, callback.id, "That button is out of date.");
      return OK();
    }
    await answerCallback(env, callback.id, on ? "On" : "Off");

    if (which === "title") {
      session.title_on = on ? "1" : "0";
      session.step = "opt_subs";
      await putSession(env, key, session);
      await editText(env, chatId, messageId, `On-screen title: ${on ? "ON ✅" : "OFF 🚫"}`);
      await askToggle(
        env,
        chatId,
        "5/5 — Add SUBTITLES from the narration? (auto-transcribed, shown at the bottom)",
        "subs"
      );
    } else {
      session.subs_on = on ? "1" : "0";
      await editText(env, chatId, messageId, `Subtitles: ${on ? "ON ✅" : "OFF 🚫"}`);
      await dispatchToGitHub(env, "receive_video", {
        file_id: session.file_id,
        title: session.title,
        description: session.description,
        tags: session.tags,
        title_on: session.title_on || "1",
        subs_on: session.subs_on,
      });
      await env.SESSIONS.delete(key);
      await sendMessage(
        env,
        chatId,
        `⏳ Rendering "${session.title}" — I'll send a preview with Approve / Reject buttons. Nothing is posted until you approve.`
      );
    }
    return OK();
  }

  await answerCallback(env, callback.id, "");
  return OK();
}

// ---------------------------------------------------------------- helpers
async function putSession(env, key, session) {
  await env.SESSIONS.put(key, JSON.stringify(session), { expirationTtl: SESSION_TTL_SECONDS });
}

async function askToggle(env, chatId, text, which) {
  return tg(env, "sendMessage", {
    chat_id: chatId,
    text,
    reply_markup: {
      inline_keyboard: [[
        { text: "✅ On", callback_data: `opt:${which}:1` },
        { text: "🚫 Off", callback_data: `opt:${which}:0` },
      ]],
    },
  });
}

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

function tg(env, method, body) {
  return fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

const answerCallback = (env, id, text) => tg(env, "answerCallbackQuery", { callback_query_id: id, text });
const sendMessage = (env, chatId, text) => tg(env, "sendMessage", { chat_id: chatId, text });
const clearButtons = (env, chatId, messageId) =>
  tg(env, "editMessageReplyMarkup", {
    chat_id: chatId,
    message_id: messageId,
    reply_markup: { inline_keyboard: [] },
  });
const editText = (env, chatId, messageId, text) =>
  tg(env, "editMessageText", { chat_id: chatId, message_id: messageId, text });
