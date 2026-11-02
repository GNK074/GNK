export type Theme = "light" | "carbon_black" | "royal_blue";
export type User = {
  id: string;
  name: string;
  email: string;
  role: string;
  verified?: boolean;
  active?: boolean;
  gender?: string | null;
  date_of_birth?: string | null;
  mobile?: string | null;
  theme?: Theme;
  avatar_url?: string | null;
  created?: string;
  mfa_enabled?: boolean;
};
