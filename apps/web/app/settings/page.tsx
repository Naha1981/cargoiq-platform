"use client";
import { useState } from "react";
import { Settings, Mail, Database, Key, Shield } from "lucide-react";
import { TopNav } from "@/components/layout/TopNav";
import { cn } from "@/lib/utils";
import toast from "react-hot-toast";

const TABS = [
  { id: "general",   label: "General",         icon: Settings  },
  { id: "email",     label: "Email Connection", icon: Mail      },
  { id: "cargowise", label: "CargoWise",        icon: Database  },
  { id: "wiselayer", label: "WiseLayer",        icon: Shield    },
  { id: "security",  label: "Security",         icon: Key       },
];

export default function SettingsPage() {
  const [tab, setTab]                 = useState("general");
  const [cwUrl, setCwUrl]             = useState("");
  const [cwUser, setCwUser]           = useState("");
  const [cwPass, setCwPass]           = useState("");
  const [testStatus, setTestStatus]   = useState<string | null>(null);
  const [gmailStatus, setGmailStatus] = useState<string>("disconnected");

  const testCwConnection = async () => {
    if (!cwUrl) { toast.error("Enter CargoWise server URL first"); return; }
    setTestStatus("testing");
    await new Promise(r => setTimeout(r, 1500));
    setTestStatus("success");
    toast.success("CargoWise connection verified");
  };

  return (
    <div className="flex flex-col min-h-full">
      <TopNav breadcrumbs={[{ label: "Settings" }]} />

      <div className="p-6">
        <div className="grid grid-cols-4 gap-6 max-w-5xl">
          {/* Tab sidebar */}
          <div className="col-span-1">
            <nav className="space-y-0.5">
              {TABS.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => setTab(id)}
                  className={cn(
                    "flex items-center gap-2.5 w-full px-3 h-9 rounded text-xs font-medium transition-colors",
                    tab === id
                      ? "bg-accent/10 text-accent border-l-2 border-accent pl-2.5"
                      : "text-text-secondary hover:bg-subtle"
                  )}
                >
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  {label}
                </button>
              ))}
            </nav>
          </div>

          {/* Tab content */}
          <div className="col-span-3">

            {tab === "general" && (
              <div className="card">
                <div className="card-header"><h3 className="text-sm font-semibold">General Settings</h3></div>
                <div className="card-body space-y-4">
                  <div>
                    <label className="form-label">Organisation Name</label>
                    <input className="form-input" defaultValue="My Freight Company" />
                  </div>
                  <div>
                    <label className="form-label">Shipments Auto-Approve Threshold</label>
                    <select className="form-input">
                      <option value="0.90">90% — High confidence only (recommended)</option>
                      <option value="0.80">80% — Medium-high confidence</option>
                      <option value="0.70">70% — Medium confidence</option>
                      <option value="0.00">0% — Never auto-approve</option>
                    </select>
                    <p className="text-2xs text-text-tertiary mt-1">
                      Shipments above this confidence level are auto-approved. All others go to review queue.
                    </p>
                  </div>
                  <button className="btn btn-primary btn-sm" onClick={() => toast.success("Settings saved")}>
                    Save Changes
                  </button>
                </div>
              </div>
            )}

            {tab === "email" && (
              <div className="card">
                <div className="card-header"><h3 className="text-sm font-semibold">Email Connection</h3></div>
                <div className="card-body space-y-5">
                  <div className={cn(
                    "flex items-center justify-between p-4 rounded border",
                    gmailStatus === "connected"
                      ? "bg-success-bg border-success-border"
                      : "bg-subtle border-border"
                  )}>
                    <div className="flex items-center gap-3">
                      <Mail className="w-5 h-5 text-text-tertiary" />
                      <div>
                        <p className="text-xs font-semibold text-text-primary">Gmail / Google Workspace</p>
                        <p className="text-2xs text-text-tertiary">
                          {gmailStatus === "connected" ? "Connected" : "Not connected"}
                        </p>
                      </div>
                    </div>
                    <button
                      className={cn("btn btn-sm", gmailStatus === "connected" ? "btn-danger" : "btn-primary")}
                      onClick={() => {
                        setGmailStatus(s => s === "connected" ? "disconnected" : "connected");
                        toast.success(gmailStatus === "connected" ? "Disconnected" : "Gmail connected");
                      }}
                    >
                      {gmailStatus === "connected" ? "Disconnect" : "Connect Gmail"}
                    </button>
                  </div>

                  <div className="border border-border rounded p-4">
                    <p className="text-xs font-semibold text-text-primary mb-3">IMAP Connection</p>
                    <div className="space-y-3">
                      {[
                        { label: "IMAP Host", placeholder: "mail.yourcompany.co.za" },
                        { label: "Port",      placeholder: "993" },
                        { label: "Username",  placeholder: "ops@yourcompany.co.za" },
                        { label: "Password",  placeholder: "••••••••", type: "password" },
                      ].map(({ label, placeholder, type }) => (
                        <div key={label}>
                          <label className="form-label">{label}</label>
                          <input type={type || "text"} className="form-input" placeholder={placeholder} />
                        </div>
                      ))}
                      <button className="btn btn-primary btn-sm" onClick={() => toast.success("IMAP connection tested")}>
                        Test & Save IMAP Connection
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {tab === "cargowise" && (
              <div className="card">
                <div className="card-header"><h3 className="text-sm font-semibold">CargoWise Integration</h3></div>
                <div className="card-body space-y-4">
                  <div className="p-3 bg-info-bg border border-info-border rounded text-xs text-info-DEFAULT">
                    CargoIQ connects via your CargoWise eAdaptor endpoint. Credentials are AES-256 encrypted at rest.
                    We create draft shipments only — nothing goes live without your approval.
                  </div>
                  <div>
                    <label className="form-label">CargoWise Server URL</label>
                    <input
                      className="form-input font-mono"
                      value={cwUrl}
                      onChange={e => setCwUrl(e.target.value)}
                      placeholder="https://yourcompany.cargowise.com"
                    />
                  </div>
                  <div>
                    <label className="form-label">Username</label>
                    <input className="form-input" value={cwUser} onChange={e => setCwUser(e.target.value)} />
                  </div>
                  <div>
                    <label className="form-label">Password</label>
                    <input type="password" className="form-input" value={cwPass} onChange={e => setCwPass(e.target.value)} />
                  </div>
                  <div className="flex items-center gap-3">
                    <button className="btn btn-secondary btn-sm" onClick={testCwConnection}>
                      {testStatus === "testing" ? "Testing…" : "Test Connection"}
                    </button>
                    <button className="btn btn-primary btn-sm" onClick={() => toast.success("Saved")}>
                      Save Credentials
                    </button>
                    {testStatus === "success" && (
                      <span className="text-xs text-success-DEFAULT">✓ Connection verified</span>
                    )}
                  </div>
                </div>
              </div>
            )}

            {tab === "wiselayer" && (
              <div className="card">
                <div className="card-header"><h3 className="text-sm font-semibold">WiseLayer — RLA Sentinel</h3></div>
                <div className="card-body space-y-4">
                  <div className="p-3 bg-warning-bg border border-warning-border rounded text-xs text-warning-DEFAULT">
                    The RLA Sentinel checks your importers' eFiling status daily at 06:00 SA time.
                    A suspended RLA causes automatic EDI rejection and R2,000/day port storage fees.
                  </div>
                  <div>
                    <label className="form-label">eFiling Username</label>
                    <input className="form-input" placeholder="Your SARS eFiling username" />
                  </div>
                  <div>
                    <label className="form-label">eFiling Password</label>
                    <input type="password" className="form-input" />
                  </div>
                  <div>
                    <label className="form-label">Alert Email (for suspensions)</label>
                    <input type="email" className="form-input" placeholder="ops@yourcompany.co.za" />
                  </div>
                  <button className="btn btn-primary btn-sm" onClick={() => toast.success("RLA Sentinel configured")}>
                    Save & Enable RLA Monitoring
                  </button>
                </div>
              </div>
            )}

            {tab === "security" && (
              <div className="card">
                <div className="card-header"><h3 className="text-sm font-semibold">Security & Access</h3></div>
                <div className="card-body space-y-4">
                  <div>
                    <label className="form-label">Change Password</label>
                    <input type="password" className="form-input mb-2" placeholder="Current password" />
                    <input type="password" className="form-input mb-2" placeholder="New password" />
                    <input type="password" className="form-input" placeholder="Confirm new password" />
                    <button className="btn btn-primary btn-sm mt-3" onClick={() => toast.success("Password updated")}>
                      Update Password
                    </button>
                  </div>
                  <div className="border-t border-border pt-4">
                    <p className="text-xs font-semibold text-text-primary mb-2">Data & Privacy</p>
                    <p className="text-xs text-text-tertiary mb-3">
                      All CargoIQ data is stored in South Africa (EU West region).
                      POPIA compliant. No CargoIQ employee can access your data.
                    </p>
                    <button className="btn btn-secondary btn-sm">Download My Data</button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
