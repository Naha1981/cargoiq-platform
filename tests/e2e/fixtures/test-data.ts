/**
 * CargoIQ Test Data — Real SA freight forwarding scenarios
 */
export const USERS = {
  opsManager: {
    email: "ops@demo-freight.co.za", password: "TestPass1234!",
    name: "Riaan van der Merwe", role: "operations_manager", org: "Demo Freight (Pty) Ltd",
  },
  owner: {
    email: "ghameeda@gidalene.co.za", password: "TestPass1234!",
    name: "Ghameeda Idalene", role: "admin", org: "G Idalene Accounting & Clearing",
  },
  itDirector: {
    email: "it@afrigo.co.za", password: "TestPass1234!",
    name: "Karel-Jan Nöthnagel", role: "admin", org: "Afrigo Global Logistics",
  },
  operator: {
    email: "operator@demo-freight.co.za", password: "TestPass1234!",
    name: "Sipho Dlamini", role: "operator", org: "Demo Freight (Pty) Ltd",
  },
  viewer: {
    email: "viewer@demo-freight.co.za", password: "TestPass1234!",
    name: "Lindiwe Mokoena", role: "viewer", org: "Demo Freight (Pty) Ltd",
  },
};

export const CLEAN_AIR_IMPORT = {
  shipper: "Shenzhen Electronics Co Ltd", consignee: "Demo Freight Imports (Pty) Ltd",
  awb: "176-12345678", originPort: "CNSHA", destinationPort: "ZADUR",
  hsCode: "85171100", grossWeight: "245.5", invoiceValue: "12500",
  currency: "USD", incoterms: "FOB", description: "Electronic components",
  packages: "48",
};

export const COMPLIANCE_FAILURE_SHIPMENT = {
  shipper: "Mumbai Textiles Pvt Ltd", consignee: "SA Fashion Imports",
  awb: "083-98765432", originPort: "INBOM", destinationPort: "ZACPT",
  hsCode: "6205",  // Only 4 digits — will fail shield
  grossWeight: "180", invoiceValue: "8750", currency: "USD",
  incoterms: "CIF", description: "Mens woven shirts cotton",
};

export const SACU_SHIPMENT = {
  shipper: "Namibia Mining Supplies CC", consignee: "Joburg Industrial (Pty) Ltd",
  originPort: "NAWDH", destinationPort: "ZAJNB", hsCode: "84749000",
  grossWeight: "1250", invoiceValue: "45000", currency: "ZAR",
  incoterms: "DAP", description: "Mining equipment parts",
};

export const API_BASE = process.env.API_URL || "http://localhost:8000";
export const WEB_BASE = process.env.BASE_URL || "http://localhost:3000";
