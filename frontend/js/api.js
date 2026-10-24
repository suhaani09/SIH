/**
 * SIH26261 API Client
 * Manages JWT tokens, authenticated requests, and handles fallbacks.
 */

const API_BASE = (window.location.origin.includes("localhost") || window.location.origin.includes("127.0.0.1"))
  ? window.location.origin + "/api/v1"
  : "/api/v1";

class ApiClient {
  constructor() {
    this.token = sessionStorage.getItem("sih_jwt_token") || null;
    this.currentUser = JSON.parse(sessionStorage.getItem("sih_user") || "null");
  }

  setToken(token, user) {
    this.token = token;
    this.currentUser = user;
    if (token) {
      sessionStorage.setItem("sih_jwt_token", token);
      sessionStorage.setItem("sih_user", JSON.stringify(user));
    } else {
      sessionStorage.removeItem("sih_jwt_token");
      sessionStorage.removeItem("sih_user");
    }
  }

  async request(path, options = {}) {
    const headers = options.headers || {};
    // Include credentials so HttpOnly session cookie is transmitted automatically
    options.credentials = "include";

    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }

    try {
      const res = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers,
      });

      if (res.status === 401) {
        // If unauthenticated on a protected call (not login itself), redirect to login
        if (!path.includes("/auth/login")) {
          this.setToken(null, null);
          if (!window.location.pathname.includes("login")) {
            window.location.href = "/login";
          }
        }
      }

      if (!res.ok) {
        let errMessage = `HTTP error ${res.status}`;
        try {
          const errData = await res.json();
          errMessage = errData.detail || errMessage;
        } catch (_) {}
        throw new Error(errMessage);
      }

      // Check if response is JSON or blob (PDF)
      const contentType = res.headers.get("content-type");
      if (contentType && contentType.includes("application/pdf")) {
        return await res.blob();
      }
      return await res.json();
    } catch (err) {
      console.warn(`API request to ${path} failed:`, err.message);
      throw err;
    }
  }

  // Auth: Login
  async login(identifierOrEmail, password, isSwitch = false) {
    if (!password) {
      throw new Error("Password is required.");
    }
    const headers = { "Content-Type": "application/json" };
    if (isSwitch) {
      headers["X-Switch-Account"] = "true";
    }
    const data = await this.request("/auth/login", {
      method: "POST",
      headers,
      body: JSON.stringify({ identifier: identifierOrEmail, email: identifierOrEmail, password }),
    });

    const user = {
      id: data.user.id,
      officer_id: data.user.officer_id,
      name: data.user.name,
      role: data.user.role,
      email: data.user.email,
    };
    this.setToken(data.access_token, user);
    return { success: true, user };
  }

  // Auth: Logout
  async logout() {
    try {
      await this.request("/auth/logout", { method: "POST" });
    } catch (err) {
      console.warn("Logout request failed:", err);
    } finally {
      this.setToken(null, null);
      window.location.href = "/login";
    }
  }

  // Auth: Get current authenticated user profile
  async getCurrentUser() {
    try {
      const user = await this.request("/auth/me");
      this.currentUser = user;
      sessionStorage.setItem("sih_user", JSON.stringify(user));
      return user;
    } catch (err) {
      this.setToken(null, null);
      throw err;
    }
  }

  // Applications
  async getApplications() {
    try {
      return await this.request("/applications");
    } catch (err) {
      return [
        {
          id: "app-demo-0042",
          institution_name: "Sunrise Institute of Technology, Demo City",
          academic_year: "2026-27",
          program_type: "UG Engineering",
          category: "Extension of Approval",
          status: "UNDER_REVIEW",
          current_version_no: 1,
        }
      ];
    }
  }

  async getApplication(appId) {
    try {
      return await this.request(`/applications/${appId}`);
    } catch (err) {
      return {
        id: appId,
        institution_name: "Sunrise Institute of Technology, Demo City",
        academic_year: "2026-27",
        program_type: "UG Engineering",
        category: "Extension of Approval",
        status: "UNDER_REVIEW",
        versions: [{ version_no: 1, status: "UNDER_REVIEW" }],
      };
    }
  }

  // Documents
  async getDocuments(appId, vno = 1) {
    try {
      return await this.request(`/applications/${appId}/versions/${vno}/documents`);
    } catch (err) {
      console.warn("Could not fetch remote documents:", err.message);
      return null;
    }
  }

  /**
   * Fetch the raw PDF binary for a document by its document ID.
   * Returns a Blob suitable for use with URL.createObjectURL().
   * Throws on auth failures or missing documents.
   */
  async getDocumentPdf(docId) {
    const headers = {};
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    const res = await fetch(`${API_BASE}/documents/${docId}/pdf`, {
      credentials: "include",
      headers,
    });
    if (res.status === 401) {
      this.setToken(null, null);
      if (!window.location.pathname.includes("login")) {
        window.location.href = "/login";
      }
      throw new Error("Authentication required");
    }
    if (!res.ok) {
      let errMessage = `HTTP error ${res.status}`;
      try {
        const errData = await res.json();
        errMessage = errData.detail || errMessage;
      } catch (_) {}
      throw new Error(errMessage);
    }
    return await res.blob();
  }

  async uploadDocument(appId, vno = 1, file, docType = "AUTO") {
    if (!this.token) {
      throw new Error("Authentication required. Please sign in to upload documents.");
    }

    const formData = new FormData();
    formData.append("doc_type", docType);
    formData.append("file", file);

    const headers = {};
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }

    const res = await fetch(`${API_BASE}/applications/${appId}/versions/${vno}/documents`, {
      method: "POST",
      headers,
      body: formData,
    });

    if (!res.ok) {
      let errMessage = `HTTP error ${res.status}`;
      try {
        const errData = await res.json();
        errMessage = errData.detail || errMessage;
      } catch (_) {}
      throw new Error(errMessage);
    }
    return await res.json();
  }

  // Report & Verification Results
  async getReport(appId, vno = 1, format = "json") {
    try {
      return await this.request(`/applications/${appId}/versions/${vno}/report?format=${format}`);
    } catch (err) {
      return {
        app_id: appId,
        version_no: vno,
        institution_name: "Sunrise Institute of Technology, Demo City",
        program_type: "UG Engineering",
        academic_year: "2026-27",
        overall_status: "FAIL",
        counts: { PASS: 5, FAIL: 1, INDETERMINATE: 0, NOT_APPLICABLE: 0 },
        findings: [
          {
            rule_key: "FAC_RATIO_UG_ENGG",
            title: "Faculty to Student Ratio (UG Engineering)",
            clause_ref: "APH 2026-27 Clause 7.1",
            status: "FAIL",
            severity: "CRITICAL",
            confidence: 0.98,
            required_value: "0.0667 (1:15)",
            observed_value: "58 / 1200 = 0.0483 (1:20.7)",
            explanation: "Faculty count of 58 is deficient for sanctioned intake of 1200. Minimum 80 faculty required.",
            evidence: [
              { doc_id: "9bee6b08-f094-407e-91da-45715e0c1f0f", doc_name: "02_FACULTY_LIST.pdf", page_no: 1, bbox: [46, 500, 300, 520], snippet: "Total Teaching Faculty: 58" },
              { doc_id: "9d961595-e6b6-4446-8916-7b42b0ed75bc", doc_name: "01_APPLICATION_FORM.pdf", page_no: 1, bbox: [46, 260, 300, 280], snippet: "Sanctioned Intake Total: 1200" }
            ]
          },
          {
            rule_key: "CADRE_DIST_UG_ENGG",
            title: "Cadre Distribution (Prof:Assoc:Asst)",
            clause_ref: "APH 2026-27 Clause 7.2",
            status: "PASS",
            severity: "MAJOR",
            confidence: 0.95,
            required_value: "1:2:6 ratio (Prof >= 10%)",
            observed_value: "6 Professors / 58 = 10.3%",
            explanation: "Cadre proportion is compliant with cadre norms.",
            evidence: [{ doc_id: "9bee6b08-f094-407e-91da-45715e0c1f0f", doc_name: "02_FACULTY_LIST.pdf", page_no: 1, bbox: [46, 320, 300, 340], snippet: "Professors: 6" }]
          },
          {
            rule_key: "BUILTUP_AREA_UG_ENGG",
            title: "Instructional and Administrative Built-up Area",
            clause_ref: "APH 2026-27 Clause 6.4",
            status: "PASS",
            severity: "MAJOR",
            confidence: 0.96,
            required_value: "15.0 sqm/student",
            observed_value: "24,000 sqm / 1200 = 20.0 sqm/student",
            explanation: "Observed area 20.0 sqm/student meets minimum requirement 15.0.",
            evidence: [{ doc_id: "9d961595-e6b6-4446-8916-7b42b0ed75bc", doc_name: "01_APPLICATION_FORM.pdf", page_no: 1, bbox: [46, 300, 350, 320], snippet: "Built-up Area: 24,000 sq m" }]
          },
          {
            rule_key: "LAND_AREA_UG_ENGG",
            title: "Minimum Land Area Requirement",
            clause_ref: "APH 2026-27 Clause 6.1",
            status: "PASS",
            severity: "CRITICAL",
            confidence: 0.97,
            required_value: "2.5 Acres",
            observed_value: "3.0 Acres",
            explanation: "Land area 3.0 Acres satisfies the minimum requirement of 2.5 Acres.",
            evidence: [{ doc_id: "9d961595-e6b6-4446-8916-7b42b0ed75bc", doc_name: "01_APPLICATION_FORM.pdf", page_no: 1, bbox: [46, 280, 300, 300], snippet: "Land Area: 3.0 Acres" }]
          },
          {
            rule_key: "FIN_CORPUS_UG_ENGG",
            title: "Financial Corpus / Surplus Norms",
            clause_ref: "APH 2026-27 Clause 8.2",
            status: "PASS",
            severity: "MAJOR",
            confidence: 0.94,
            required_value: "Rs. 5.00 Crore",
            observed_value: "Rs. 6.00 Crore",
            explanation: "Audited financial corpus meets normative financial safety threshold.",
            evidence: [{ doc_id: "b9c5da61-db67-4d7f-bcd6-e21668ea3b70", doc_name: "03_FINANCIAL_STATEMENT.pdf", page_no: 1, bbox: [46, 200, 350, 220], snippet: "Corpus Fund: Rs. 6.00 Crores" }]
          },
          {
            rule_key: "DOC_COMPLETENESS",
            title: "Mandatory Document Completeness",
            clause_ref: "APH 2026-27 Appendix 1",
            status: "PASS",
            severity: "CRITICAL",
            confidence: 1.0,
            required_value: "6 Mandatory Documents",
            observed_value: "All 6 Documents Uploaded & Verified",
            explanation: "All 6 required documents are present in submission.",
            evidence: []
          }
        ],
        consistency_findings: [
          {
            relation: "land_area_cross_check",
            status: "MISMATCH",
            similarity: 57.1,
            detail: "Land Deed states 2.1 Acres (Doc 04), while Application Form declares 3.0 Acres (Doc 01). Variance: 42.8%."
          },
          {
            relation: "buildup_area_cross_check",
            status: "MISMATCH",
            similarity: 66.7,
            detail: "Building Plan drawings sum to 18,000 sq m (Doc 05), while Application Form states 24,000 sq m (Doc 01). Variance: 33.3%."
          }
        ],
        deficiencies: []
      };
    }
  }

  // Officer Review Actions
  async recordReview(resultId, action, reason) {
    return await this.request(`/results/${resultId}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, reason }),
    });
  }

  // Issue Deficiency
  async issueDeficiencies(appId, vno, deficiencies) {
    return await this.request(`/applications/${appId}/versions/${vno}/deficiencies`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ deficiencies }),
    });
  }

  // Trigger Verification
  async runVerification(appId, vno = 1) {
    return await this.request(`/applications/${appId}/versions/${vno}/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
  }

  // Rulebooks
  async getRulebooks() {
    try {
      return await this.request("/rulebooks");
    } catch (err) {
      return [
        {
          id: "rb-demo-2026-27",
          name: "AICTE Approval Process Handbook 2024-27 (Demo)",
          academic_year: "2026-27",
          rules_count: 6,
          status: "PUBLISHED"
        }
      ];
    }
  }

  // Audit Events
  async getAuditEvents() {
    try {
      return await this.request("/audit");
    } catch (err) {
      return [
        {
          id: 1,
          action: "APPLICATION_SUBMITTED",
          actor_id: "user-inst-admin-001",
          object_type: "application",
          object_id: "app-demo-0042",
          prev_hash: "0000000000000000000000000000000000000000000000000000000000000000",
          event_hash: "3a8f1b9c7e2d4a5b6c8e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c",
          created_at: new Date().toISOString(),
        },
        {
          id: 2,
          action: "VERIFICATION_COMPLETED",
          actor_id: "system",
          object_type: "verification_run",
          object_id: "run-001",
          prev_hash: "3a8f1b9c7e2d4a5b6c8e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c",
          event_hash: "8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9f8e7d",
          created_at: new Date().toISOString(),
        }
      ];
    }
  }
}

export const api = new ApiClient();
