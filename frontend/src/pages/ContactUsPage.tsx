import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowUpRight,
  Phone,
  Mail,
  MapPin,
  Clock3,
  Globe,
  ShieldCheck,
  Send,
  Instagram,
  Facebook,
  Linkedin,
  Twitter,
  ArrowRight,
  FileText,
  ChartNoAxesCombined,
  Headphones,
} from "lucide-react";
import { Logo } from "../components/Logo";
import { api } from "../services/api";
type Item = { label: string; href: string };
type Contact = {
  company: {
    name: string;
    registration_verified: boolean;
    sebi_registration: string | null;
    basl_membership: string | null;
    description: string;
  };
  channels_verified: boolean;
  phones: (Item & { display: string })[];
  emails: string[];
  website: string;
  office_hours: string;
  location: string;
  maps_address: string | null;
  services: Item[];
  quick_links: Item[];
  socials: Item[];
  security_policy: string;
  regulatory_notice: string | null;
  disclaimer: string;
};
const socialIcons: Record<string, typeof Send> = {
  Telegram: Send,
  Instagram: Instagram,
  Facebook: Facebook,
  LinkedIn: Linkedin,
  "X (Twitter)": Twitter,
};
function ExternalLink({
  item,
  children,
}: {
  item: Item;
  children?: React.ReactNode;
}) {
  return (
    <a href={item.href} target="_blank" rel="noopener noreferrer">
      {children}
      {item.label}
      <ArrowUpRight size={13} />
    </a>
  );
}
export function RegulatoryDisclaimer({ data }: { data: Contact }) {
  return (
    <div className="contact-regulatory">
      {data.regulatory_notice && (
        <section>
          <h3>Mandatory Regulatory Notice (BASL Standard)</h3>
          <p>{data.regulatory_notice}</p>
        </section>
      )}
      <section>
        <h3>Disclaimer</h3>
        <p>{data.disclaimer}</p>
      </section>
    </div>
  );
}
export function ContactUsPage({ signedIn }: { signedIn: boolean }) {
  const [data, setData] = useState<Contact | null>(null),
    [error, setError] = useState(""),
    [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    setError("");
    api("/public/contact")
      .then((d) => live && setData(d))
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [attempt]);
  return (
    <div className="contact-page">
      <nav className="contact-topnav" aria-label="Main navigation">
        <Logo />
        <div>
          <Link to="/">Home</Link>
          <Link to="/#features">Platform</Link>
          <Link className="active" to="/contact-us">
            Contact Us
          </Link>
          <Link
            className="contact-nav-button"
            to={signedIn ? "/user/dashboard" : "/login"}
          >
            {signedIn ? "Dashboard" : "Sign in"}
            <ArrowRight size={14} />
          </Link>
        </div>
      </nav>
      <main className="contact-main">
        <header className="contact-hero">
          <div>
            <p className="contact-eyebrow">LET’S CONNECT</p>
            <h1>
              Contact Us<span>.</span>
            </h1>
            <p>
              We are here to help you with your trading platform,
              <br className="desktop-break" /> research services and technical
              support.
            </p>
          </div>
          <div className="contact-hero-art" aria-hidden="true">
            <Headphones size={52} />
            <span>
              <ShieldCheck size={17} />
            </span>
          </div>
        </header>
        {error ? (
          <div className="contact-error" role="alert">
            <p>{error}</p>
            <button
              className="settings-primary"
              onClick={() => setAttempt((n) => n + 1)}
            >
              Try again
            </button>
          </div>
        ) : !data ? (
          <p className="contact-loading" role="status">
            Loading contact information…
          </p>
        ) : (
          <>
            <div className="contact-columns">
              <section className="contact-company">
                <span className="contact-section-icon">
                  <Globe size={19} />
                </span>
                <h2>About Company</h2>
                <h3>{data.company.name}</h3>
                <p>{data.company.description}</p>
                {data.company.registration_verified && (
                  <div className="company-registration">
                    <span>SEBI Registration</span>
                    <strong>{data.company.sebi_registration}</strong>
                    {data.company.basl_membership && (
                      <>
                        <span>BASL Membership</span>
                        <strong>{data.company.basl_membership}</strong>
                      </>
                    )}
                  </div>
                )}
                <div className="contact-identity">
                  <ShieldCheck size={15} />
                  <span>
                    Your decisions.
                    <br />
                    Our technology.
                  </span>
                </div>
              </section>
              <section>
                <span className="contact-section-icon">
                  <ChartNoAxesCombined size={19} />
                </span>
                <h2>Our Services</h2>
                <div className="contact-link-list">
                  {data.services.map((item) => (
                    <ExternalLink key={item.href} item={item} />
                  ))}
                </div>
                <small>
                  Contact us to confirm availability and the applicable service
                  provider.
                </small>
              </section>
              <section>
                <span className="contact-section-icon">
                  <FileText size={19} />
                </span>
                <h2>Quick Links</h2>
                <div className="contact-link-list">
                  {data.quick_links.map((item) => (
                    <ExternalLink key={item.href} item={item} />
                  ))}
                </div>
              </section>
              <section>
                <span className="contact-section-icon">
                  <Headphones size={19} />
                </span>
                <h2>Get In Touch</h2>
                {!data.channels_verified && (
                  <p className="contact-pending">
                    Support contact channels are awaiting verification before
                    publication.
                  </p>
                )}
                {data.phones.map((phone) => (
                  <a
                    className="contact-detail"
                    href={phone.href}
                    key={phone.href}
                  >
                    <Phone size={15} />
                    <span>
                      <small>{phone.label}</small>
                      <strong>{phone.display}</strong>
                    </span>
                  </a>
                ))}
                {data.emails.length > 0 && (
                  <div className="contact-detail">
                    <Mail size={15} />
                    <span>
                      <small>Email Addresses</small>
                      {data.emails.map((email) => (
                        <a key={email} href={`mailto:${email}`}>
                          {email}
                        </a>
                      ))}
                    </span>
                  </div>
                )}
                <a className="contact-detail" href={data.website}>
                  <Globe size={15} />
                  <span>
                    <small>Website</small>gnkalgo.com
                    <ArrowUpRight size={12} />
                  </span>
                </a>
                <div className="contact-detail">
                  <Clock3 size={15} />
                  <span>
                    <small>Office Hours</small>
                    {data.office_hours}
                  </span>
                </div>
                <div className="contact-detail">
                  <MapPin size={15} />
                  <span>
                    <small>Office Location</small>
                    {data.location}
                    {data.maps_address && (
                      <a
                        href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(data.maps_address)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        View on Google Maps ↗
                      </a>
                    )}
                  </span>
                </div>
              </section>
            </div>
            <section className="contact-social">
              <div>
                <h2>Stay connected.</h2>
                <p>News, updates and investor awareness.</p>
              </div>
              <div className="social-links">
                {data.socials.length ? (
                  data.socials.map((item) => {
                    const Icon = socialIcons[item.label] || Globe;
                    return (
                      <a
                        key={item.href}
                        href={item.href}
                        aria-label={item.label}
                        title={item.label}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <Icon size={18} />
                      </a>
                    );
                  })
                ) : (
                  <p>
                    Official social channels will appear after verification.
                  </p>
                )}
              </div>
            </section>
            <section className="contact-security">
              <ShieldCheck size={24} />
              <div>
                <h2>Official Security Policy</h2>
                <p>{data.security_policy}</p>
              </div>
              <span>STAY VIGILANT</span>
            </section>
            <RegulatoryDisclaimer data={data} />
          </>
        )}
      </main>
      <footer className="contact-footer">
        <span>© {new Date().getFullYear()} GNK ALGO</span>
        <span>Intelligence Behind Every Trade.</span>
        <Link to="/user/dashboard">
          Go to workspace
          <ArrowRight size={13} />
        </Link>
      </footer>
    </div>
  );
}
