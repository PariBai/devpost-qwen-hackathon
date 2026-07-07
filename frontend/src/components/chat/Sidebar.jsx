/* Conversation sidebar: new-chat button + chats grouped into Today / Earlier,
 * each row deletable on hover. (No "Pro / Upgrade" card — dropped per spec.) */
import { PlusIcon, TrashIcon } from "../icons";

function isToday(iso) {
  const d = new Date(iso);
  const now = new Date();
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  );
}

function ConvoRow({ chat, active, onSelect, onDelete }) {
  return (
    <div
      className={`convo${active ? " convo--active" : ""}`}
      onClick={() => onSelect(chat.chat_id)}
      title={chat.title}
    >
      <span className="convo__title">{chat.title || "New Chat"}</span>
      <button
        className="convo__del"
        aria-label="Delete conversation"
        onClick={(e) => {
          e.stopPropagation();
          onDelete(chat.chat_id);
        }}
      >
        <TrashIcon />
      </button>
    </div>
  );
}

export default function Sidebar({
  chats,
  activeChatId,
  onNew,
  onSelect,
  onDelete,
  open,
  onClose,
}) {
  const today = chats.filter((c) => isToday(c.updated_at));
  const earlier = chats.filter((c) => !isToday(c.updated_at));

  const renderGroup = (label, list) =>
    list.length > 0 && (
      <>
        <div className="sidebar__section">{label}</div>
        <div className="sidebar__list">
          {list.map((c) => (
            <ConvoRow
              key={c.chat_id}
              chat={c}
              active={c.chat_id === activeChatId}
              onSelect={(id) => {
                onSelect(id);
                onClose?.();
              }}
              onDelete={onDelete}
            />
          ))}
        </div>
      </>
    );

  return (
    <>
      <div
        className={`sidebar__backdrop${open ? " sidebar__backdrop--open" : ""}`}
        onClick={onClose}
      />
      <aside className={`sidebar${open ? " sidebar--open" : ""}`}>
        <button
          className="sidebar__new"
          onClick={() => {
            onNew();
            onClose?.();
          }}
        >
          <PlusIcon />
          New conversation
        </button>

        {chats.length === 0 && (
          <div className="sidebar__section" style={{ marginTop: 22 }}>
            <span style={{ fontWeight: 500, letterSpacing: 0, textTransform: "none" }}>
              No conversations yet.
            </span>
          </div>
        )}

        {renderGroup("TODAY", today)}
        {renderGroup("EARLIER", earlier)}
      </aside>
    </>
  );
}
