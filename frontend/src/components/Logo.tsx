import { Link } from "react-router-dom";
export function Logo() {
  return (
    <Link to="/" className="logo gnk-logo" aria-label="GNK ALGO home">
      <span className="gnk-symbol" aria-hidden="true" />
      GNK<span className="word">ALGO</span>
    </Link>
  );
}
