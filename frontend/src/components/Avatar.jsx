/* Circular initial avatar. Uses the first letter of the full name, else email. */
export function initialOf(user) {
  const src = user?.fullName?.trim() || user?.email?.trim() || "?";
  return src.charAt(0).toUpperCase();
}

export default function Avatar({ user, size = 34 }) {
  return (
    <span
      className="avatar"
      style={{ width: size, height: size, fontSize: size * 0.44 }}
    >
      {initialOf(user)}
    </span>
  );
}
