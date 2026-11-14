import { Link } from "react-router-dom";
export function Logo({ signedIn = false }: { signedIn?: boolean }) {
  return (
    <Link to={signedIn ? "/user/dashboard" : "/"} className="logo gnk-logo" aria-label={signedIn ? "GNK ALGO dashboard" : "GNK ALGO home"}>
      <span className="gnk-symbol" aria-hidden="true" />
      GNK<span className="word">ALGO</span>
    </Link>
  );
}
