/*
 * Assistant answer renderer. Uses react-markdown + remark-gfm so full GitHub-
 * flavored markdown works — tables, headings, blockquotes, horizontal rules,
 * lists, code, bold/italic. Tables are wrapped so they scroll on narrow screens
 * instead of breaking the layout. Styling lives under `.md` in chat.css.
 */
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const COMPONENTS = {
  // Wrap tables so wide finance tables scroll horizontally within the bubble.
  table: (props) => (
    <div className="md-table-wrap">
      <table {...props} />
    </div>
  ),
  // Open links safely in a new tab.
  a: (props) => <a target="_blank" rel="noopener noreferrer" {...props} />,
};

export default function Markdown({ text }) {
  return (
    <div className="md">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
        {text}
      </ReactMarkdown>
    </div>
  );
}
