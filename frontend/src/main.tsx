import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { SignInPage } from "./components/auth/SignInPage";
import { LandingPage } from "./components/landing/LandingPage";
import { App } from "./components/layout/App";
import { useAuth } from "./hooks/useAuth";
import { useThemeMode } from "./hooks/useThemeMode";
import "./styles.css";

type GuestScreen = "landing" | "signin";

function Root() {
  const { theme, toggleTheme } = useThemeMode();
  const { status, user, role, signIn, signOut } = useAuth();
  const [guestScreen, setGuestScreen] = useState<GuestScreen>("landing");

  if (status === "loading") {
    return (
      <main className="hm-boot" role="status" aria-live="polite">
        <span className="hm-boot-dot" />
        <p>Đang khôi phục phiên đăng nhập...</p>
      </main>
    );
  }

  if (status === "authenticated" && user && role) {
    return (
      <App
        role={role}
        userName={user.display_name}
        theme={theme}
        onToggleTheme={toggleTheme}
        onSignOut={() => {
          setGuestScreen("landing");
          void signOut();
        }}
      />
    );
  }

  if (guestScreen === "signin") {
    return (
      <SignInPage
        theme={theme}
        onToggleTheme={toggleTheme}
        onSignIn={signIn}
        onBack={() => setGuestScreen("landing")}
      />
    );
  }

  return (
    <LandingPage theme={theme} onToggleTheme={toggleTheme} onSignIn={() => setGuestScreen("signin")} />
  );
}

const root = document.getElementById("root");

if (!root) {
  throw new Error("Missing #root element");
}

createRoot(root).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
);
