"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Package, Eye, EyeOff, AlertCircle } from "lucide-react";
import { authApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import Link from "next/link";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw]     = useState(false);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await authApi.signIn({ email, password });
      localStorage.setItem("cargoiq_token", res.access_token);
      localStorage.setItem("cargoiq_user",  JSON.stringify(res.user));
      localStorage.setItem("cargoiq_org",   JSON.stringify(res.organisation));
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "Invalid credentials. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-canvas flex items-center justify-center p-4">
      <div className="w-full max-w-sm">

        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-10 h-10 bg-nav rounded-lg mb-4">
            <Package className="w-5 h-5 text-accent" />
          </div>
          <h1 className="text-xl font-semibold text-text-primary">
            Cargo<span className="text-accent">IQ</span>
          </h1>
          <p className="text-xs text-text-tertiary mt-1">
            AI Compliance & Operations Platform
          </p>
        </div>

        {/* Card */}
        <div className="card">
          <div className="card-header">
            <h2 className="text-sm font-semibold text-text-primary">Sign in to your organisation</h2>
          </div>
          <div className="card-body">
            <form onSubmit={handleSubmit} className="space-y-4">

              {error && (
                <div className="flex items-start gap-2 p-3 bg-error-bg border border-error-border rounded text-xs text-error-DEFAULT">
                  <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              <div>
                <label className="form-label" htmlFor="email">Email address</label>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  className="form-input"
                  placeholder="you@yourcompany.co.za"
                />
              </div>

              <div>
                <label className="form-label" htmlFor="password">Password</label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPw ? "text" : "password"}
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    className="form-input pr-10"
                    placeholder="••••••••"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw(!showPw)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-text-tertiary hover:text-text-secondary"
                  >
                    {showPw
                      ? <EyeOff className="w-4 h-4" />
                      : <Eye className="w-4 h-4" />
                    }
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="btn btn-primary w-full justify-center"
              >
                {loading ? "Signing in…" : "Sign In"}
              </button>
            </form>

            <div className="mt-4 pt-4 border-t border-border text-center">
              <p className="text-xs text-text-tertiary">
                New to CargoIQ?{" "}
                <Link href="/auth/signup" className="text-accent hover:underline font-medium">
                  Create an account
                </Link>
              </p>
            </div>
          </div>
        </div>

        <p className="text-center text-2xs text-text-tertiary mt-6">
          POPIA Compliant · South Africa Hosted · Encrypted
        </p>
      </div>
    </div>
  );
}
