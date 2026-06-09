"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Package, AlertCircle } from "lucide-react";
import { authApi } from "@/lib/api";
import Link from "next/link";

export default function SignupPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    full_name: "", email: "", password: "", org_name: ""
  });
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState("");

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (form.password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    setLoading(true);
    try {
      const res = await authApi.signUp(form);
      localStorage.setItem("cargoiq_token", res.access_token);
      localStorage.setItem("cargoiq_user",  JSON.stringify(res.user));
      localStorage.setItem("cargoiq_org",   JSON.stringify(res.organisation));
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "Registration failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-canvas flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-10 h-10 bg-nav rounded-lg mb-4">
            <Package className="w-5 h-5 text-accent" />
          </div>
          <h1 className="text-xl font-semibold text-text-primary">
            Cargo<span className="text-accent">IQ</span>
          </h1>
          <p className="text-xs text-text-tertiary mt-1">Start your 14-day free trial</p>
        </div>

        <div className="card">
          <div className="card-header">
            <h2 className="text-sm font-semibold text-text-primary">Create your organisation</h2>
          </div>
          <div className="card-body">
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="flex items-start gap-2 p-3 bg-error-bg border border-error-border rounded text-xs text-error-DEFAULT">
                  <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}
              {[
                { key: "org_name",  label: "Company Name",  type: "text",     placeholder: "Acme Freight (Pty) Ltd" },
                { key: "full_name", label: "Your Full Name", type: "text",     placeholder: "Thabiso Ndlovu" },
                { key: "email",     label: "Work Email",     type: "email",    placeholder: "you@company.co.za" },
                { key: "password",  label: "Password",       type: "password", placeholder: "Min 8 characters" },
              ].map(({ key, label, type, placeholder }) => (
                <div key={key}>
                  <label className="form-label">{label}</label>
                  <input
                    type={type}
                    required
                    value={(form as any)[key]}
                    onChange={set(key)}
                    className="form-input"
                    placeholder={placeholder}
                    autoComplete={key === "password" ? "new-password" : undefined}
                  />
                </div>
              ))}

              <button
                type="submit"
                disabled={loading}
                className="btn btn-primary w-full justify-center"
              >
                {loading ? "Creating account…" : "Create Account — Free Trial"}
              </button>
            </form>

            <div className="mt-4 pt-4 border-t border-border text-center">
              <p className="text-xs text-text-tertiary">
                Already have an account?{" "}
                <Link href="/auth/login" className="text-accent hover:underline font-medium">
                  Sign in
                </Link>
              </p>
            </div>
          </div>
        </div>

        <p className="text-center text-2xs text-text-tertiary mt-6">
          No credit card required · Cancel anytime · POPIA compliant
        </p>
      </div>
    </div>
  );
}
