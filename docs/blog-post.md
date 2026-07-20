*My journey building Hikmat PSX for the Global AI Hackathon Series with Qwen Cloud — Track 1: MemoryAgent.*

## Why I started

Every chatbot I have ever used has the same blind spot: it forgets me the moment the chat ends. For casual questions that is fine. But I wanted to build something for investing on the **Pakistan Stock Exchange (PSX)**, and there it becomes a real problem.

If I tell an assistant that I only invest in **Shariah-compliant** stocks, that I am a conservative long-term investor, and that I prefer answers in Urdu, I should not have to repeat all of that every single time I open a new conversation. A good assistant should *remember* — and, more importantly, it should let that memory change the advice it gives.

That is exactly the challenge of **Track 1: MemoryAgent** — an agent with persistent memory that accumulates preferences, forgets what is no longer true, and recalls the right things within a limited context window. So I built **Hikmat PSX**, and this post is the story of building it with Qwen on Alibaba Cloud.

## What I built

Hikmat PSX is a finance and Shariah-compliance assistant for PSX-listed companies. It answers questions about financials, ratios, comparisons, and Shariah status — while quietly learning your durable preferences from ordinary conversation and applying them to every future answer.

The moment that makes the whole idea click: teach it once *"I only want Shariah-compliant stocks,"* then start a completely new chat and ask it to compare two banks. It automatically flags the non-compliant one and steers you to a compliant alternative — without you ever repeating yourself.

## Choosing Qwen on Alibaba Cloud

I used **Qwen models through the Alibaba Cloud DashScope** OpenAI-compatible endpoint (`https://dashscope-intl.aliyuncs.com/compatible-mode/v1`). Two things made this easy:

1. **OpenAI-compatible API.** Because DashScope exposes an OpenAI-compatible interface, I could wire Qwen into my LangChain/LangGraph stack with almost no friction — just a base URL, an API key, and a model name.
2. **A family of models for different jobs.** I used a fast Qwen model for the interactive chat (streaming answers feel instant), and Qwen embeddings (`text-embedding-v3`) for the semantic memory recall. Same platform, same key, two different capabilities.

The whole backend runs on an **Alibaba Cloud ECS** instance as a Docker Compose stack — PostgreSQL, a FastAPI backend, and an nginx-served React frontend.

## The interesting part: how memory actually works

Storing data is easy. The real problem in a MemoryAgent is **curation** — deciding what is worth remembering, recalling only what matters, and forgetting on time. I split memory into three layers, each with a clear owner and lifetime:

- **Chat history** — the questions and answers shown in the UI, per conversation.
- **Per-session working memory** — a LangGraph Postgres checkpointer holding one conversation's state, trimmed with a sliding window so the context stays small.
- **Long-term memory** — durable user preferences, keyed by **user ID** so they survive new chats, logout, and new sessions. This is what makes it a MemoryAgent.

On top of that, three mechanisms keep the memory correct:

### Remembering — reflection, not reflex
The agent never decides to save something in the middle of answering. Instead, *after* the answer has streamed to the user, a dedicated reflection step reviews the finished turn and produces a short list of upsert/delete operations over a fixed set of preference keys (`language`, `risk_tolerance`, `shariah_only`, and so on). On an ordinary question it saves **nothing** — which keeps memory precise. Because it runs after the response, it adds zero latency.

### Recalling within a limited context window
I do not dump every stored preference into every prompt — that does not scale and it pollutes the context. Instead, hard constraints (language, the Shariah filter) are always applied, and everything else is ranked by **semantic similarity** to the current question using Qwen embeddings. Only the top few memories are injected. The prompt stays small and focused even as a user's memory grows.

### Forgetting — at two timescales
Within a session, older turns are trimmed away by the sliding window. Across sessions, preferences are deleted when the user revokes them ("forget the Shariah filter"), and the user can also delete chats and clear stored preferences directly. Memory is something the user can see and control, not a black box.

To make all of this visible, the UI streams a **live memory feed** ("remembered / forgot", with reasons) and shows a **recall indicator** on each answer ("recalled N of M memories").

## Challenges I ran into

**Structured output from smaller models.** Faster Qwen models sometimes returned valid JSON in the *wrong shape* — a bare list instead of the wrapped object my schema expected. Rather than fight it, I built a tolerant parsing layer that tries tool-calling first, falls back to JSON mode, and coerces mis-shaped payloads back into the schema. This made the agent robust across different Qwen model sizes.

**Knowing when NOT to remember.** The hardest part of memory is precision. Saving a one-off question as if it were a preference is worse than forgetting it. I spent real time tuning the reflection prompt so it stores nothing on normal turns and only captures genuine, durable choices.

**Staying alive under quota limits.** During testing my free-tier quota on one model ran out mid-demo. So I added **sticky model fail-over**: if a request hits a quota error, the app permanently promotes the next Qwen model in a configured list and keeps going — no downtime, no manual intervention. A small thing, but it is the difference between a demo that survives judging and one that dies at the worst moment.

## What I learned

The lesson that stuck with me: a MemoryAgent is not really a database problem, it is a **judgment** problem. What to keep, what to surface, what to let go — and doing all three in a way the user can trust and inspect. Making memory *visible and controllable* turned out to matter as much as the retrieval algorithm itself. Watching the agent remember, recall, and forget is what makes it feel like it actually knows you.

Qwen on Alibaba Cloud made the model side of this refreshingly boring — in the best way. The OpenAI-compatible endpoint meant I could spend my time on the memory architecture, not on plumbing.

## What's next

- **Proactive memory** — a personalized daily market brief generated from a user's stored preferences.
- **A fuller Shariah-compliance dataset** covering the entire PSX universe.
- **Live news/sentiment** via a search API to enrich answers with current market context.

---

*Hikmat PSX is open source (MIT) and live for testing. Built with Qwen (Alibaba Cloud DashScope), LangGraph, FastAPI, PostgreSQL, and React.*

- **Live demo:** http://47.84.234.2
- **Code:** https://github.com/PariBai/devpost-qwen-hackathon

*#QwenCloud #AlibabaCloud #MemoryAgent #AI #Hackathon*
