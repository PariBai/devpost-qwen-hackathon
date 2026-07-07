/* Main chat screen: top nav + ticker + sidebar + conversation + composer.
 * Orchestrates the useChat state machine; the message list auto-scrolls as the
 * assistant streams. */
import { useEffect, useRef, useState } from "react";
import TopNav from "../components/chat/TopNav";
import Ticker from "../components/chat/Ticker";
import Sidebar from "../components/chat/Sidebar";
import ChatHeader from "../components/chat/ChatHeader";
import WelcomeHero from "../components/chat/WelcomeHero";
import Message from "../components/chat/Message";
import Composer from "../components/chat/Composer";
import { useChat } from "../hooks/useChat";

import "../styles/chat.css";

export default function Chat() {
  const {
    chats,
    activeChatId,
    messages,
    sending,
    loadingHistory,
    startNewChat,
    selectChat,
    removeChat,
    send,
  } = useChat();

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const scrollRef = useRef(null);

  // Keep the latest message in view as it streams.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const showHero = messages.length === 0 && !loadingHistory;

  return (
    <div className="chat-root">
      <TopNav onToggleSidebar={() => setSidebarOpen((v) => !v)} />
      <Ticker />

      <div className="shell">
        <Sidebar
          chats={chats}
          activeChatId={activeChatId}
          onNew={startNewChat}
          onSelect={selectChat}
          onDelete={removeChat}
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />

        <main className="chatcol">
          <ChatHeader />

          <div className="messages" ref={scrollRef}>
            <div className="messages__inner">
              {showHero ? (
                <WelcomeHero onStarter={send} />
              ) : (
                messages.map((m) => <Message key={m.id} message={m} />)
              )}
            </div>
          </div>

          <Composer onSend={send} sending={sending} />
        </main>
      </div>
    </div>
  );
}
