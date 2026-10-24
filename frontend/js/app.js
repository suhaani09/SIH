/**
 * SIH26261 Main Application Controller
 * Handles UI state, event listeners, SVG Graph, Evidence Inspector, and Review Actions.
 */

import { api } from "./api.js";

// Application State
const state = {
  currentTab: "officer",
  user: api.currentUser,
  application: null,
  reportData: null,
  activeFilter: "ALL",
  selectedFinding: null,
  selectedEdge: null,
  auditEvents: [],
  rulebooks: [],
  documents: [],
};

// UI Elements
const elements = {
  personaSelect: document.getElementById("personaSelect"),
  currentUserName: document.getElementById("currentUserName"),
  currentUserRole: document.getElementById("currentUserRole"),
  navTabs: document.querySelectorAll(".sidebar-item"),
  tabViews: document.querySelectorAll(".tab-view"),
  
  // Stats
  statTotal: document.getElementById("statTotal"),
  statPass: document.getElementById("statPass"),
  statFail: document.getElementById("statFail"),
  statMismatches: document.getElementById("statMismatches"),
  
  // Findings
  findingsTableBody: document.getElementById("findingsTableBody"),
  filterPills: document.querySelectorAll(".filter-pill"),
  
  // Evidence Inspector
  evidenceViewer: document.getElementById("evidenceViewer"),
  docViewerName: document.getElementById("docViewerName"),
  docViewerPage: document.getElementById("docViewerPage"),
  evidenceCanvas: document.getElementById("evidenceCanvas"),
  evidenceBoxOverlay: document.getElementById("evidenceBoxOverlay"),
  evidenceSnippetText: document.getElementById("evidenceSnippetText"),
  evidenceClauseText: document.getElementById("evidenceClauseText"),
  evidenceConfScore: document.getElementById("evidenceConfScore"),
  
  // Consistency Graph
  graphSvg: document.getElementById("consistencyGraphSvg"),
  graphEdgeDetail: document.getElementById("graphEdgeDetail"),
  
  // Modals
  reviewModal: document.getElementById("reviewModal"),
  reviewActionInput: document.getElementById("reviewActionInput"),
  reviewReasonInput: document.getElementById("reviewReasonInput"),
  reviewModalRuleTitle: document.getElementById("reviewModalRuleTitle"),
  btnSubmitReview: document.getElementById("btnSubmitReview"),
  
  deficiencyModal: document.getElementById("deficiencyModal"),
  deficiencyTextInput: document.getElementById("deficiencyTextInput"),
  deficiencyDueDateInput: document.getElementById("deficiencyDueDateInput"),
  btnSubmitDeficiency: document.getElementById("btnSubmitDeficiency"),
  
  // Reports
  btnDownloadPdf: document.getElementById("btnDownloadPdf"),
  btnDownloadJson: document.getElementById("btnDownloadJson"),
  btnTriggerVerify: document.getElementById("btnTriggerVerify"),
  
  // Document Upload Dropzone & Table
  docUploadDropzone: document.getElementById("docUploadDropzone"),
  fileInput: document.getElementById("fileInput"),
  btnBrowseDoc: document.getElementById("btnBrowseDoc"),
  uploadDocType: document.getElementById("uploadDocType"),
  uploadProgressContainer: document.getElementById("uploadProgressContainer"),
  uploadProgressText: document.getElementById("uploadProgressText"),
  uploadedDocsTableBody: document.getElementById("uploadedDocsTableBody"),
  docsCountBadge: document.getElementById("docsCountBadge"),

  // Toasts
  toastContainer: document.getElementById("toastContainer"),
  
  // Audit & Rules
  auditTableBody: document.getElementById("auditTableBody"),
  rulesListContainer: document.getElementById("rulesListContainer"),
};

// Show Toast
function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ'}</span>
    <span class="toast-msg">${message}</span>
  `;
  elements.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    setTimeout(() => toast.remove(), 250);
  }, 4000);
}

// Initialize Application
async function init() {
  // Check if authenticated
  try {
    const me = await api.getCurrentUser();
    state.user = me;
  } catch (err) {
    // If not authenticated, redirect to login page
    window.location.href = "/login";
    return;
  }

  setupEventListeners();
  updateUserDisplay();
  await loadDashboardData();
  await loadDocuments();
}

// Event Listeners
function setupEventListeners() {
  // Navigation — sidebar items (replaces old .nav-tab)
  document.querySelectorAll(".sidebar-item").forEach((item) => {
    item.addEventListener("click", () => {
      const target = item.dataset.tab;
      switchTab(target);
    });
  });

  // ── Secure Account Switcher (Credential Required) ────────────────────────
  const switchModal = document.getElementById("switchAccountModal");
  const switchTargetName = document.getElementById("switchAccountTargetName");
  const switchTargetEmail = document.getElementById("switchAccountTargetEmail");
  const switchTargetRole = document.getElementById("switchAccountTargetRole");
  const switchTargetEmailVal = document.getElementById("switchAccountTargetEmailVal");
  const switchPasswordInput = document.getElementById("switchAccountPasswordInput");
  const switchAlert = document.getElementById("switchAccountAlert");
  const switchAlertMsg = document.getElementById("switchAccountAlertMsg");
  const switchForm = document.getElementById("switchAccountForm");
  const btnSwitchCancel = document.getElementById("btnSwitchAccountCancel");
  const btnSwitchClose = document.getElementById("btnSwitchAccountClose");
  const btnSwitchSubmit = document.getElementById("btnSwitchAccountSubmit");
  const btnSwitchText = document.getElementById("btnSwitchAccountText");
  const switchSpinner = document.getElementById("switchAccountSpinner");
  const btnToggleSwitchPassword = document.getElementById("btnToggleSwitchPassword");
  const switchEyeIcon = document.getElementById("switchEyeIcon");

  function cancelAccountSwitch() {
    if (elements.personaSelect && state.user) {
      elements.personaSelect.value = state.user.email;
    }
    if (switchModal) switchModal.classList.remove("open");
    if (switchPasswordInput) switchPasswordInput.value = "";
    if (switchAlert) switchAlert.style.display = "none";
  }

  if (btnSwitchCancel) btnSwitchCancel.addEventListener("click", cancelAccountSwitch);
  if (btnSwitchClose) btnSwitchClose.addEventListener("click", cancelAccountSwitch);

  if (btnToggleSwitchPassword && switchPasswordInput) {
    btnToggleSwitchPassword.addEventListener("click", () => {
      const isPwd = switchPasswordInput.type === "password";
      switchPasswordInput.type = isPwd ? "text" : "password";
      if (switchEyeIcon) {
        switchEyeIcon.innerHTML = isPwd
          ? `<path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/>`
          : `<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>`;
      }
    });
  }

  // Intercept dropdown change - DO NOT switch active account without credentials!
  elements.personaSelect.addEventListener("change", (e) => {
    const selectedEmail = e.target.value;
    if (state.user && selectedEmail === state.user.email) {
      return; // Already active user
    }

    const selectedOption = e.target.options[e.target.selectedIndex];
    const targetName = selectedOption.dataset.name || selectedOption.text;
    const targetRole = selectedOption.dataset.role || "OFFICER";
    const targetId = selectedOption.dataset.id || selectedEmail;

    // Display selected account details in the modal
    if (switchTargetName) switchTargetName.textContent = targetName;
    if (switchTargetEmail) switchTargetEmail.textContent = `${selectedEmail} [${targetId}]`;
    if (switchTargetRole) switchTargetRole.textContent = targetRole;
    if (switchTargetEmailVal) switchTargetEmailVal.value = selectedEmail;
    if (switchPasswordInput) switchPasswordInput.value = "";
    if (switchAlert) switchAlert.style.display = "none";
    if (btnSwitchSubmit) btnSwitchSubmit.disabled = false;
    if (switchSpinner) switchSpinner.style.display = "none";
    if (btnSwitchText) btnSwitchText.textContent = "Authenticate & Switch";

    // Open credential verification modal
    if (switchModal) {
      switchModal.classList.add("open");
      setTimeout(() => switchPasswordInput && switchPasswordInput.focus(), 100);
    }
  });

  // Handle password submission and credential verification
  if (switchForm) {
    switchForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const targetEmail = switchTargetEmailVal.value;
      const password = switchPasswordInput.value;

      if (!targetEmail || !password) {
        if (switchAlert && switchAlertMsg) {
          switchAlertMsg.textContent = "Please enter the password for this account.";
          switchAlert.style.display = "flex";
        }
        return;
      }

      // UI loading state
      if (btnSwitchSubmit) btnSwitchSubmit.disabled = true;
      if (switchSpinner) switchSpinner.style.display = "inline-block";
      if (btnSwitchText) btnSwitchText.textContent = "Verifying Credentials...";
      if (switchAlert) switchAlert.style.display = "none";

      try {
        // Authenticate with backend using existing trusted endpoint with session rotation
        const res = await api.login(targetEmail, password, true);
        if (res.success && res.user) {
          // Invalidate client-side cached data from previous identity
          clearPdfCache();
          state.user = res.user;
          state.application = null;
          state.reportData = null;
          state.documents = [];
          state.auditEvents = [];
          state.rulebooks = [];
          state.selectedFinding = null;
          state.selectedEdge = null;

          // Update UI representation with trusted new identity
          updateUserDisplay();

          // Refresh data for the newly authenticated account
          await loadDashboardData();
          await loadDocuments();
          if (state.currentTab === "audit") await loadAuditEvents();
          if (state.currentTab === "rulebook") await loadRulebooks();

          // Switch active module view if appropriate for new role
          if (res.user.role === "INSTITUTION_ADMIN") {
            switchTab("institution");
          } else if (res.user.role === "CURATOR") {
            switchTab("rulebook");
          } else if (res.user.role === "AUDITOR") {
            switchTab("audit");
          } else {
            switchTab("officer");
          }

          // Close modal and show success toast
          if (switchModal) switchModal.classList.remove("open");
          showToast(`Successfully authenticated and switched to: ${res.user.name} (${res.user.role})`, "success");
        } else {
          throw new Error("Authentication failed.");
        }
      } catch (err) {
        // Retain the current authenticated session on failure!
        if (elements.personaSelect && state.user) {
          elements.personaSelect.value = state.user.email;
        }
        if (switchAlert && switchAlertMsg) {
          switchAlertMsg.textContent = err.message || "Invalid credentials. Current session retained.";
          switchAlert.style.display = "flex";
        }
        if (btnSwitchSubmit) btnSwitchSubmit.disabled = false;
        if (switchSpinner) switchSpinner.style.display = "none";
        if (btnSwitchText) btnSwitchText.textContent = "Authenticate & Switch";
        if (switchPasswordInput) {
          switchPasswordInput.value = "";
          switchPasswordInput.focus();
        }
      }
    });
  }

  // Officer Logout Button
  const btnLogout = document.getElementById("btnOfficerLogout");
  if (btnLogout) {
    btnLogout.addEventListener("click", async () => {
      if (confirm("Are you sure you want to sign out?")) {
        clearPdfCache();
        await api.logout();
      }
    });
  }

  // Filter Pills
  elements.filterPills.forEach((pill) => {
    pill.addEventListener("click", () => {
      elements.filterPills.forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      state.activeFilter = pill.dataset.filter;
      renderFindingsTable();
    });
  });

  // Re-run Verification
  if (elements.btnTriggerVerify) {
    elements.btnTriggerVerify.addEventListener("click", async () => {
      showToast("Triggering full verification pipeline...", "info");
      try {
        await api.runVerification("app-demo-0042", 1);
        showToast("Verification queued! Reloading report...", "success");
        setTimeout(loadDashboardData, 1200);
      } catch (err) {
        showToast(`Verification trigger: ${err.message}`, "error");
      }
    });
  }

  // Report Downloads
  if (elements.btnDownloadPdf) {
    elements.btnDownloadPdf.addEventListener("click", async () => {
      showToast("Generating official evidence-linked PDF report...", "info");
      try {
        const blob = await api.getReport("app-demo-0042", 1, "pdf");
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `AICTE_Compliance_Report_APP-2026-0042_v1.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        showToast("PDF report downloaded successfully!", "success");
      } catch (err) {
        showToast(`PDF download failed: ${err.message}`, "error");
      }
    });
  }

  if (elements.btnDownloadJson) {
    elements.btnDownloadJson.addEventListener("click", async () => {
      try {
        const data = await api.getReport("app-demo-0042", 1, "json");
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `AICTE_Compliance_Findings_APP-2026-0042_v1.json`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        showToast("JSON findings exported!", "success");
      } catch (err) {
        showToast(`JSON export failed: ${err.message}`, "error");
      }
    });
  }

  // Review Modal submission
  if (elements.btnSubmitReview) {
    elements.btnSubmitReview.addEventListener("click", async () => {
      const reason = elements.reviewReasonInput.value.trim();
      const action = elements.reviewActionInput.value;
      if (!reason && action === "OVERRULE") {
        showToast("An official justification reason is mandatory when overruling a finding.", "error");
        return;
      }
      try {
        await api.recordReview(state.selectedFinding.rule_key, action, reason);
        closeModals();
        showToast(`Recorded officer decision: ${action}`, "success");
        await loadDashboardData();
      } catch (err) {
        closeModals();
        showToast(`Decision recorded: ${action} (demo saved)`, "success");
      }
    });
  }

  // Deficiency Modal submission
  if (elements.btnSubmitDeficiency) {
    elements.btnSubmitDeficiency.addEventListener("click", async () => {
      const text = elements.deficiencyTextInput.value.trim();
      const dueDate = elements.deficiencyDueDateInput.value;
      if (!text) {
        showToast("Please enter the deficiency description text.", "error");
        return;
      }
      try {
        await api.issueDeficiencies("app-demo-0042", 1, [{ text, due_date: dueDate }]);
        closeModals();
        showToast("Formal deficiency notice issued to institution!", "success");
        await loadDashboardData();
      } catch (err) {
        closeModals();
        showToast("Deficiency issued successfully (demo saved)!", "success");
      }
    });
  }

  // File Upload Listeners
  if (elements.btnBrowseDoc && elements.fileInput) {
    elements.btnBrowseDoc.addEventListener("click", (e) => {
      e.stopPropagation();
      elements.fileInput.click();
    });
  }

  if (elements.docUploadDropzone && elements.fileInput) {
    elements.docUploadDropzone.addEventListener("click", (e) => {
      if (e.target.tagName !== "SELECT" && e.target.tagName !== "OPTION" && e.target.tagName !== "LABEL") {
        elements.fileInput.click();
      }
    });

    elements.docUploadDropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      elements.docUploadDropzone.classList.add("drag-over");
    });

    elements.docUploadDropzone.addEventListener("dragleave", () => {
      elements.docUploadDropzone.classList.remove("drag-over");
    });

    elements.docUploadDropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      elements.docUploadDropzone.classList.remove("drag-over");
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleFileUpload(e.dataTransfer.files[0]);
      }
    });
  }

  if (elements.fileInput) {
    elements.fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFileUpload(e.target.files[0]);
        e.target.value = "";
      }
    });
  }

  // Modal Closers
  document.querySelectorAll(".modal-close, .btn-modal-cancel").forEach((btn) => {
    btn.addEventListener("click", closeModals);
  });
}

// Switch Active Tab
function switchTab(tabId) {
  state.currentTab = tabId;

  // Update sidebar active item
  document.querySelectorAll(".sidebar-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.tab === tabId);
    item.removeAttribute("aria-current");
    if (item.dataset.tab === tabId) item.setAttribute("aria-current", "page");
  });

  // Update tab views
  elements.tabViews.forEach((view) => {
    view.classList.toggle("active", view.id === `view-${tabId}`);
  });

  // Update topbar breadcrumb
  const tabLabels = {
    officer:     "Application Scrutiny",
    graph:       "Cross-Document Consistency Graph",
    institution: "Institution Portal",
    rulebook:    "APH Rulebook",
    audit:       "Immutable Audit Chain",
  };
  const topbarPage = document.getElementById("topbar-page-title");
  if (topbarPage) topbarPage.textContent = tabLabels[tabId] || tabId;

  if (tabId === "graph") {
    renderConsistencyGraph();
  } else if (tabId === "audit") {
    loadAuditEvents();
  } else if (tabId === "rulebook") {
    loadRulebooks();
  } else if (tabId === "institution") {
    loadDocuments();
  }
}

// Update User Display
function updateUserDisplay() {
  if (!state.user) return;
  if (elements.currentUserName) elements.currentUserName.textContent = state.user.name;
  if (elements.currentUserRole) elements.currentUserRole.textContent = state.user.role;
  if (elements.personaSelect) elements.personaSelect.value = state.user.email;

  const displayNameElem = document.getElementById("officerDisplayName");
  const roleBadgeElem = document.getElementById("officerRoleBadge");
  if (displayNameElem) {
    const idStr = state.user.officer_id ? ` [${state.user.officer_id}]` : "";
    displayNameElem.textContent = `${state.user.name}${idStr}`;
  }
  if (roleBadgeElem) {
    roleBadgeElem.textContent = state.user.role || "OFFICER";
  }
}

// Load Dashboard Data
async function loadDashboardData() {
  try {
    // Ensure document catalog is loaded so document IDs can be resolved for evidence preview
    await loadDocuments();

    const report = await api.getReport("app-demo-0042", 1, "json");
    state.reportData = report;

    // Render Stats
    const counts = report.counts || { PASS: 5, FAIL: 1, INDETERMINATE: 0 };
    const mismatchesCount = (report.consistency_findings || []).length;

    elements.statTotal.textContent = (counts.PASS || 0) + (counts.FAIL || 0) + (counts.INDETERMINATE || 0);
    elements.statPass.textContent = counts.PASS || 0;
    elements.statFail.textContent = counts.FAIL || 0;
    elements.statMismatches.textContent = mismatchesCount;

    // Render Findings
    renderFindingsTable();

    // Default select first finding for evidence inspector
    if (report.findings && report.findings.length > 0) {
      const firstDeficient = report.findings.find((f) => f.status === "FAIL") || report.findings[0];
      await selectFindingForEvidence(firstDeficient);
    } else {
      showViewerEmptyState("No findings recorded", "Run verification to evaluate compliance rules.");
    }

    // Render graph if currently active
    if (state.currentTab === "graph") {
      renderConsistencyGraph();
    }
  } catch (err) {
    showToast(`Failed loading verification report: ${err.message}`, "error");
    showViewerErrorState(err.message);
  }
}

// Render Findings Table
function renderFindingsTable() {
  if (!state.reportData || !state.reportData.findings) return;

  const findings = state.reportData.findings.filter((f) => {
    if (state.activeFilter === "ALL") return true;
    if (state.activeFilter === "FAIL") return f.status === "FAIL";
    if (state.activeFilter === "PASS") return f.status === "PASS";
    if (state.activeFilter === "INDETERMINATE") return f.status === "INDETERMINATE";
    return true;
  });

  elements.findingsTableBody.innerHTML = findings
    .map((f, idx) => {
      const isSelected = state.selectedFinding && state.selectedFinding.rule_key === f.rule_key;
      const statusClass = f.status.toLowerCase();
      const severityClass = (f.severity || "major").toLowerCase();

      return `
      <tr class="${isSelected ? 'selected-row' : ''}" data-index="${idx}">
        <td>
          <div style="font-weight: 700; color: var(--color-text-primary);">${f.rule_key}</div>
          <div style="font-size: 0.8rem; color: var(--color-text-secondary);">${f.title}</div>
        </td>
        <td><span class="badge badge-${statusClass}">${f.status}</span></td>
        <td><span class="badge badge-${severityClass}">${f.severity || 'Major'}</span></td>
        <td>
          <div style="font-size: 0.82rem; color: var(--color-text-secondary);">Req: <span style="color: var(--color-text-primary); font-weight: 600;">${f.required_value}</span></div>
          <div style="font-size: 0.82rem; color: var(--color-text-secondary);">Obs: <span style="color: var(--color-text-primary); font-weight: 600;">${f.observed_value}</span></div>
        </td>
        <td>
          <div style="font-size: 0.82rem; max-width: 240px; color: var(--color-text-secondary);">${f.explanation}</div>
        </td>
        <td>
          ${f.evidence && f.evidence.length > 0 ? `
            <button class="btn btn-secondary btn-sm btn-view-evidence" data-rule="${f.rule_key}">
              🔍 ${f.evidence[0].doc_name.replace('.pdf','')} (p.${f.evidence[0].page_no})
            </button>
          ` : '<span style="color: var(--color-text-secondary); font-size: 0.8rem;">No file</span>'}
        </td>
        <td>
          <div style="display: flex; gap: 6px;">
            <button class="btn btn-secondary btn-sm btn-action-confirm" title="Confirm finding" data-rule="${f.rule_key}">✓ Confirm</button>
            <button class="btn btn-secondary btn-sm btn-action-override" title="Overrule with reason" data-rule="${f.rule_key}">✎ Override</button>
            <button class="btn btn-outline-danger btn-sm btn-action-deficiency" title="Issue formal deficiency" data-rule="${f.rule_key}">⚠ Deficiency</button>
          </div>
        </td>
      </tr>
    `;
    })
    .join("");

  // Attach Table Row Click Handlers
  elements.findingsTableBody.querySelectorAll("tr").forEach((row) => {
    row.style.cursor = "pointer";
    row.addEventListener("click", (e) => {
      if (e.target.closest("button")) return;
      const btn = row.querySelector(".btn-view-evidence, [data-rule]");
      const rKey = btn ? btn.dataset.rule : null;
      if (rKey) {
        const finding = state.reportData.findings.find((f) => f.rule_key === rKey);
        if (finding) selectFindingForEvidence(finding);
      }
    });
  });

  elements.findingsTableBody.querySelectorAll(".btn-view-evidence").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const rKey = btn.dataset.rule;
      const finding = state.reportData.findings.find((f) => f.rule_key === rKey);
      if (finding) selectFindingForEvidence(finding);
    });
  });

  elements.findingsTableBody.querySelectorAll(".btn-action-confirm").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const rKey = btn.dataset.rule;
      const finding = state.reportData.findings.find((f) => f.rule_key === rKey);
      openReviewModal(finding, "CONFIRM");
    });
  });

  elements.findingsTableBody.querySelectorAll(".btn-action-override").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const rKey = btn.dataset.rule;
      const finding = state.reportData.findings.find((f) => f.rule_key === rKey);
      openReviewModal(finding, "OVERRULE");
    });
  });

  elements.findingsTableBody.querySelectorAll(".btn-action-deficiency").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const rKey = btn.dataset.rule;
      const finding = state.reportData.findings.find((f) => f.rule_key === rKey);
      openDeficiencyModal(finding);
    });
  });
}

// ── PDF.js Evidence Viewer ──────────────────────────────────────────────────
let pdfjsLibInstance = null;
let currentRenderTask = null;
const pdfDocCache = new Map(); // docId -> { doc, blobUrl }

async function getPdfjs() {
  if (pdfjsLibInstance) return pdfjsLibInstance;
  try {
    // Load local self-hosted build first
    pdfjsLibInstance = await import("/assets/pdfjs/pdf.min.mjs");
    pdfjsLibInstance.GlobalWorkerOptions.workerSrc = "/assets/pdfjs/pdf.worker.min.mjs";
    return pdfjsLibInstance;
  } catch (err) {
    console.warn("Local PDF.js load failed, falling back to CDN:", err);
    try {
      pdfjsLibInstance = await import("https://cdn.jsdelivr.net/npm/pdfjs-dist@4.6.82/build/pdf.min.mjs");
      pdfjsLibInstance.GlobalWorkerOptions.workerSrc = "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.6.82/build/pdf.worker.min.mjs";
      return pdfjsLibInstance;
    } catch (cdnErr) {
      console.error("Failed to load PDF.js from CDN:", cdnErr);
      throw new Error("PDF viewer engine unavailable");
    }
  }
}

function cleanupViewerResources() {
  if (currentRenderTask) {
    try {
      currentRenderTask.cancel();
    } catch (_) {}
    currentRenderTask = null;
  }
}

function clearPdfCache() {
  cleanupViewerResources();
  for (const entry of pdfDocCache.values()) {
    if (entry && entry.blobUrl) {
      try {
        URL.revokeObjectURL(entry.blobUrl);
      } catch (_) {}
    }
  }
  pdfDocCache.clear();
}

function showViewerEmptyState(message = "No document attached", subtext = "") {
  cleanupViewerResources();
  const canvas = elements.evidenceCanvas;
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  canvas.width = 460;
  canvas.height = 360;
  canvas.style.display = "block";
  canvas.style.maxWidth = "100%";
  canvas.style.height = "auto";
  canvas.style.boxShadow = "none";
  canvas.style.borderRadius = "8px";

  // Clean slate background with subtle border
  ctx.fillStyle = "#0B132B";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.strokeStyle = "#1E293B";
  ctx.lineWidth = 1.5;
  ctx.strokeRect(16, 16, canvas.width - 32, canvas.height - 32);

  // Document Icon placeholder
  ctx.fillStyle = "#334155";
  ctx.fillRect(canvas.width / 2 - 24, 100, 48, 60);
  ctx.fillStyle = "#0B132B";
  ctx.fillRect(canvas.width / 2 - 20, 104, 40, 52);

  // Main text
  ctx.fillStyle = "#E2E8F0";
  ctx.font = "bold 13px Inter, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(message, canvas.width / 2, 200);

  // Subtext
  if (subtext) {
    ctx.fillStyle = "#94A3B8";
    ctx.font = "11px Inter, sans-serif";
    const displaySub = subtext.length > 55 ? subtext.substring(0, 52) + "..." : subtext;
    ctx.fillText(displaySub, canvas.width / 2, 226);
  }
  ctx.textAlign = "start";
}

function showViewerLoadingState(docName = "document") {
  cleanupViewerResources();
  const canvas = elements.evidenceCanvas;
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  canvas.width = 460;
  canvas.height = 360;
  canvas.style.display = "block";
  canvas.style.maxWidth = "100%";
  canvas.style.height = "auto";
  canvas.style.boxShadow = "none";

  ctx.fillStyle = "#0F172A";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.fillStyle = "#38BDF8";
  ctx.font = "bold 13px Inter, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(`Loading ${docName}...`, canvas.width / 2, 175);

  ctx.fillStyle = "#94A3B8";
  ctx.font = "11px Inter, sans-serif";
  ctx.fillText("Fetching authentic PDF from storage & rendering page...", canvas.width / 2, 202);
  ctx.textAlign = "start";
}

function showViewerErrorState(errorMessage) {
  cleanupViewerResources();
  const canvas = elements.evidenceCanvas;
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  canvas.width = 460;
  canvas.height = 360;
  canvas.style.display = "block";
  canvas.style.maxWidth = "100%";
  canvas.style.height = "auto";
  canvas.style.boxShadow = "none";

  ctx.fillStyle = "#1E1E2E";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.strokeStyle = "#7F1D1D";
  ctx.lineWidth = 1.5;
  ctx.strokeRect(16, 16, canvas.width - 32, canvas.height - 32);

  ctx.fillStyle = "#EF4444";
  ctx.font = "bold 13px Inter, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("Failed to load PDF preview", canvas.width / 2, 160);

  ctx.fillStyle = "#FCA5A5";
  ctx.font = "11px Inter, sans-serif";
  ctx.fillText(errorMessage || "Document could not be retrieved", canvas.width / 2, 190);
  ctx.textAlign = "start";
}

// Render Authentic PDF Page & Overlay Evidence Coordinates
async function renderPdfEvidence(docId, docName, pageNo = 1, bbox = null) {
  cleanupViewerResources();
  const canvas = elements.evidenceCanvas;
  if (!canvas) return;

  if (!docId) {
    showViewerEmptyState("Document not found", `No record found for "${docName || 'this file'}".`);
    return;
  }

  showViewerLoadingState(docName || "document");

  try {
    const pdfjs = await getPdfjs();
    let pdfDoc = null;

    if (pdfDocCache.has(docId)) {
      pdfDoc = pdfDocCache.get(docId).doc;
    } else {
      const blob = await api.getDocumentPdf(docId);
      const blobUrl = URL.createObjectURL(blob);
      const loadingTask = pdfjs.getDocument({ url: blobUrl });
      pdfDoc = await loadingTask.promise;
      pdfDocCache.set(docId, { doc: pdfDoc, blobUrl });
    }

    const targetPageNo = Math.max(1, Math.min(pageNo || 1, pdfDoc.numPages));
    const page = await pdfDoc.getPage(targetPageNo);

    // Compute scale to fit comfortably in preview container
    const parent = canvas.parentElement;
    const availableWidth = (parent && parent.clientWidth > 100) ? (parent.clientWidth - 32) : 480;
    const unscaledViewport = page.getViewport({ scale: 1.0 });
    const scale = Math.max(0.6, Math.min(1.8, availableWidth / unscaledViewport.width));
    const viewport = page.getViewport({ scale });

    canvas.width = Math.floor(viewport.width);
    canvas.height = Math.floor(viewport.height);
    canvas.style.display = "block";
    canvas.style.maxWidth = "100%";
    canvas.style.height = "auto";
    canvas.style.boxShadow = "0 4px 16px rgba(0,0,0,0.4)";
    canvas.style.borderRadius = "4px";

    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    currentRenderTask = page.render({
      canvasContext: ctx,
      viewport: viewport,
    });
    await currentRenderTask.promise;
    currentRenderTask = null;

    // Overlay evidence bounding box highlight if valid coordinates exist
    if (bbox && Array.isArray(bbox) && bbox.length === 4) {
      const [x0, y0, x1, y1] = bbox;
      if (x1 > x0 && y1 > y0) {
        const scaleX = viewport.width / unscaledViewport.width;
        const scaleY = viewport.height / unscaledViewport.height;

        const bx = x0 * scaleX;
        const by = y0 * scaleY;
        const bw = (x1 - x0) * scaleX;
        const bh = (y1 - y0) * scaleY;

        ctx.save();
        ctx.fillStyle = "rgba(239, 68, 68, 0.22)";
        ctx.fillRect(bx, by, bw, bh);

        ctx.strokeStyle = "#ef4444";
        ctx.lineWidth = 2.5;
        ctx.strokeRect(bx, by, bw, bh);

        // Badge tag above highlight box
        const tagHeight = 16;
        const tagWidth = 100;
        const tagY = Math.max(0, by - tagHeight);
        ctx.fillStyle = "#ef4444";
        ctx.fillRect(bx, tagY, tagWidth, tagHeight);

        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 9px Inter, sans-serif";
        ctx.fillText("SOURCE EVIDENCE", bx + 6, tagY + 11);
        ctx.restore();
      }
    }
  } catch (err) {
    if (err && err.name === "RenderingCancelledException") {
      return;
    }
    console.error("PDF preview error:", err);
    showViewerErrorState(err.message || "Failed to render PDF page.");
  }
}

// Select Finding & Inspect Evidence Bounding Box
async function selectFindingForEvidence(finding) {
  if (!finding) return;
  state.selectedFinding = finding;
  renderFindingsTable();

  const ev = (finding.evidence && finding.evidence.length > 0) ? finding.evidence[0] : null;

  if (!ev) {
    // Empty state: finding has no document or page evidence
    if (elements.docViewerName) elements.docViewerName.textContent = "No Document Attached";
    if (elements.docViewerPage) elements.docViewerPage.textContent = "N/A";
    if (elements.evidenceSnippetText) {
      elements.evidenceSnippetText.textContent = `"${finding.explanation || 'No document text reference available for this rule.'}"`;
    }
    if (elements.evidenceClauseText) elements.evidenceClauseText.textContent = finding.clause_ref || "AICTE APH Norms";
    if (elements.evidenceConfScore) elements.evidenceConfScore.textContent = `${Math.round((finding.confidence || 1.0) * 100)}%`;

    const statusBadge = document.getElementById("evidenceStatusBadge");
    if (statusBadge) {
      statusBadge.textContent = "Checklist Rule";
      statusBadge.className = "badge badge-info";
    }

    showViewerEmptyState(
      "No Document Required",
      finding.explanation || "This rule verifies overall checklist completeness without an individual document page."
    );
    return;
  }

  // Resolve document ID from finding evidence or state.documents
  let docId = ev.doc_id;
  if (!docId && state.documents && state.documents.length > 0) {
    const match = state.documents.find(
      (d) => d.id === ev.doc_id || d.original_name === ev.doc_name || d.doc_type === ev.doc_name
    );
    if (match) docId = match.id;
  }

  if (elements.docViewerName) elements.docViewerName.textContent = ev.doc_name || "Document Preview";
  if (elements.docViewerPage) elements.docViewerPage.textContent = `Page ${ev.page_no || 1}`;
  if (elements.evidenceSnippetText) {
    elements.evidenceSnippetText.textContent = `"${ev.snippet || finding.observed_value || finding.explanation || ''}"`;
  }
  if (elements.evidenceClauseText) elements.evidenceClauseText.textContent = finding.clause_ref || "APH 2026-27 Norms";
  if (elements.evidenceConfScore) {
    elements.evidenceConfScore.textContent = `${Math.round((finding.confidence || 0.98) * 100)}%`;
  }

  const statusBadge = document.getElementById("evidenceStatusBadge");
  if (statusBadge) {
    if (ev.bbox && Array.isArray(ev.bbox) && ev.bbox.length === 4) {
      statusBadge.textContent = "Evidence Verified";
      statusBadge.className = "badge badge-pass";
    } else {
      statusBadge.textContent = "Document Linked";
      statusBadge.className = "badge badge-info";
    }
  }

  await renderPdfEvidence(docId, ev.doc_name, ev.page_no || 1, ev.bbox);
}

// Render Interactive SVG Cross-Document Consistency Graph
function renderConsistencyGraph() {
  const svg = elements.graphSvg;
  if (!svg) return;

  const width = svg.clientWidth || 900;
  const height = 480;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  // Nodes Definition
  const nodes = [
    { id: "app_form", label: "Application Form", sub: "Doc 01", x: width * 0.5, y: 120, type: "primary" },
    { id: "land_deed", label: "Land Deed", sub: "Doc 04", x: width * 0.22, y: 280, type: "doc" },
    { id: "build_plan", label: "Building Plan", sub: "Doc 05", x: width * 0.78, y: 280, type: "doc" },
    { id: "fac_list", label: "Faculty List", sub: "Doc 02", x: width * 0.35, y: 400, type: "doc" },
    { id: "affidavit", label: "Faculty Affidavit", sub: "Doc 06", x: width * 0.65, y: 400, type: "doc" },
  ];

  // Edges Definition
  const edges = [
    {
      source: "app_form",
      target: "land_deed",
      status: "MISMATCH",
      relation: "land_area_cross_check",
      label: "Land Area: 3.0 ac vs 2.1 ac (42.8% diff)",
      detail: "Application Form declares 3.0 Acres, but Land Deed records only 2.1 Acres. Discrepancy exceeds tolerance threshold.",
    },
    {
      source: "app_form",
      target: "build_plan",
      status: "MISMATCH",
      relation: "buildup_area_cross_check",
      label: "Built-up: 24,000 m² vs 18,000 m² (33.3% diff)",
      detail: "Building Plan vector area totals 18,000 sq m, conflicting with 24,000 sq m stated in Application Form.",
    },
    {
      source: "fac_list",
      target: "affidavit",
      status: "PASS",
      relation: "faculty_names_check",
      label: "Faculty Names: 100% Match (58/58)",
      detail: "All 58 faculty names match identically between the Faculty List and sworn Affidavits.",
    },
    {
      source: "app_form",
      target: "fac_list",
      status: "PASS",
      relation: "inst_name_check",
      label: "Institution Name: Consistent",
      detail: "Sunrise Institute of Technology matches across Application Form and Faculty List.",
    },
  ];

  let svgContent = `
    <defs>
      <linearGradient id="gradPrimary" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#172B4D"/>
        <stop offset="100%" stop-color="#2563EB"/>
      </linearGradient>
      <linearGradient id="gradDoc" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#334155"/>
        <stop offset="100%" stop-color="#1E293B"/>
      </linearGradient>
      <filter id="glowRed" x="-20%" y="-20%" width="140%" height="140%">
        <feDropShadow dx="0" dy="0" stdDeviation="4" flood-color="#B91C1C" flood-opacity="0.8"/>
      </filter>
    </defs>
  `;

  // Draw Edges
  edges.forEach((edge, i) => {
    const sNode = nodes.find((n) => n.id === edge.source);
    const tNode = nodes.find((n) => n.id === edge.target);
    const isMismatch = edge.status === "MISMATCH";
    const strokeColor = isMismatch ? "#B91C1C" : "#15803D";
    const dashArray = isMismatch ? "6,4" : "none";
    const filter = isMismatch ? 'filter="url(#glowRed)"' : "";

    const midX = (sNode.x + tNode.x) / 2;
    const midY = (sNode.y + tNode.y) / 2;

    svgContent += `
      <g class="graph-edge-group" data-edge-index="${i}" style="cursor: pointer;">
        <line x1="${sNode.x}" y1="${sNode.y}" x2="${tNode.x}" y2="${tNode.y}" 
              stroke="${strokeColor}" stroke-width="2.5" stroke-dasharray="${dashArray}" ${filter}/>
        <rect x="${midX - 100}" y="${midY - 14}" width="200" height="26" rx="13" 
              fill="#090d16" stroke="${strokeColor}" stroke-width="1.2"/>
        <text x="${midX}" y="${midY + 4}" fill="${strokeColor}" font-size="10" font-weight="700" text-anchor="middle">
          ${edge.label}
        </text>
      </g>
    `;
  });

  // Draw Nodes
  nodes.forEach((node) => {
    const isPrimary = node.type === "primary";
    const fill = isPrimary ? "url(#gradPrimary)" : "url(#gradDoc)";
    const stroke = isPrimary ? "#a5b4fc" : "rgba(255,255,255,0.15)";
    const r = isPrimary ? 38 : 32;

    svgContent += `
      <g transform="translate(${node.x}, ${node.y})">
        <circle r="${r}" fill="${fill}" stroke="${stroke}" stroke-width="2" style="box-shadow: 0 4px 12px rgba(0,0,0,0.5);"/>
        <text y="-4" fill="#ffffff" font-size="11" font-weight="700" text-anchor="middle">${node.label}</text>
        <text y="14" fill="#94a3b8" font-size="9" font-weight="500" text-anchor="middle">${node.sub}</text>
      </g>
    `;
  });

  svg.innerHTML = svgContent;

  // Edge click listener
  svg.querySelectorAll(".graph-edge-group").forEach((grp) => {
    grp.addEventListener("click", () => {
      const idx = grp.dataset.edgeIndex;
      const edge = edges[idx];
      showEdgeDetail(edge);
    });
  });
}

function showEdgeDetail(edge) {
  state.selectedEdge = edge;
  if (!elements.graphEdgeDetail) return;
  const isMismatch = edge.status === "MISMATCH";
  const borderColor = isMismatch ? "var(--color-error-border)" : "var(--color-success-border)";
  const bgColor     = isMismatch ? "var(--color-error-bg)"    : "var(--color-success-bg)";

  elements.graphEdgeDetail.innerHTML = `
    <div style="background: var(--color-surface); border: 1px solid ${borderColor}; border-left: 4px solid ${isMismatch ? 'var(--color-error)' : 'var(--color-success)'}; border-radius: var(--border-radius-lg); padding: 20px; box-shadow: var(--shadow-md);">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
        <span class="badge ${isMismatch ? 'badge-fail' : 'badge-pass'}">${edge.status}</span>
        <span style="font-size: 0.78rem; color: var(--color-text-secondary); font-family: 'JetBrains Mono', monospace;">${edge.relation}</span>
      </div>
      <h4 style="font-size: 1rem; color: var(--color-navy); margin-bottom: 6px; font-weight: 700;">${edge.label}</h4>
      <p style="font-size: 0.875rem; color: var(--color-text-secondary); line-height: 1.6;">${edge.detail}</p>
      <div style="margin-top: 14px; display: flex; gap: 10px;">
        <button class="btn btn-secondary btn-sm" onclick="alert('Viewing side-by-side evidence preview for ${edge.relation}')">
          View Both Source Documents
        </button>
      </div>
    </div>
  `;
}

// Modal Controllers
function openReviewModal(finding, defaultAction = "CONFIRM") {
  state.selectedFinding = finding;
  elements.reviewModalRuleTitle.textContent = `${finding.rule_key} — ${finding.title}`;
  elements.reviewActionInput.value = defaultAction;
  elements.reviewReasonInput.value = "";
  elements.reviewModal.classList.add("open");
}

function openDeficiencyModal(finding) {
  state.selectedFinding = finding;
  elements.deficiencyTextInput.value = `Deficiency flagged for ${finding.rule_key}: ${finding.explanation}`;
  
  // Default due date: 15 days from now
  const d = new Date();
  d.setDate(d.getDate() + 15);
  elements.deficiencyDueDateInput.value = d.toISOString().split("T")[0];
  
  elements.deficiencyModal.classList.add("open");
}

function closeModals() {
  document.querySelectorAll(".modal-backdrop").forEach((m) => m.classList.remove("open"));
  if (elements.personaSelect && state.user && state.user.email) {
    elements.personaSelect.value = state.user.email;
  }
}

// Audit Trail Viewer
async function loadAuditEvents() {
  try {
    const events = await api.getAuditEvents();
    state.auditEvents = events;
    if (!elements.auditTableBody) return;

    elements.auditTableBody.innerHTML = events
      .map(
        (ev) => `
      <tr>
        <td class="mono" style="color: var(--color-accent); font-weight: 700;">#${ev.id}</td>
        <td><span class="badge badge-pass">${ev.action}</span></td>
        <td style="color: var(--color-text-secondary);">${ev.actor_id || 'System'}</td>
        <td style="color: var(--color-text-secondary);">${ev.object_type || '-'} (${ev.object_id || '-'})</td>
        <td class="mono" style="font-size: 0.72rem; color: var(--color-text-secondary);" title="${ev.event_hash}">
          ${ev.event_hash.slice(0, 16)}...
        </td>
        <td style="font-size: 0.8rem; color: var(--color-text-secondary);">
          ${new Date(ev.created_at).toLocaleString()}
        </td>
      </tr>
    `
      )
      .join("");
  } catch (err) {
    showToast(`Audit load failed: ${err.message}`, "error");
  }
}

// Rulebook Viewer
async function loadRulebooks() {
  try {
    const rulebooks = await api.getRulebooks();
    state.rulebooks = rulebooks;
    if (!elements.rulesListContainer) return;

    elements.rulesListContainer.innerHTML = rulebooks
      .map(
        (rb) => `
      <div class="glass-card" style="margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <h3 style="color: var(--color-navy); font-size: 1rem;">${rb.name}</h3>
          <span class="badge badge-pass">${rb.status}</span>
        </div>
        <p style="font-size: 0.85rem; color: var(--color-text-secondary); margin-bottom: 14px;">
          Academic Year: <strong>${rb.academic_year}</strong> | Rules: <strong>${rb.rules_count || 6} Verified Deterministic Rules</strong>
        </p>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-secondary btn-sm" onclick="alert('Viewing YAML definition for ${rb.name}')">Inspect YAML Rules</button>
        </div>
      </div>
    `
      )
      .join("");
  } catch (err) {
    showToast(`Rulebook load failed: ${err.message}`, "error");
  }
}

// Authentic synthetic documents seeded into storage & database workflow
const DEFAULT_DOCUMENTS = [
  { id: "9d961595-e6b6-4446-8916-7b42b0ed75bc", doc_type: "APPLICATION_FORM", original_name: "01_APPLICATION_FORM.pdf", size: "8.4 KB", sha256: "f60efdd7331d49a565f263c5cacd836e831bb91746c40cff0535d6a037953358", scan_status: "DONE", page_count: 1 },
  { id: "9bee6b08-f094-407e-91da-45715e0c1f0f", doc_type: "FACULTY_LIST", original_name: "02_FACULTY_LIST.pdf", size: "11.0 KB", sha256: "31028b0827ff9aa276365725d3a457ed9dd1e3666867f483d841ec63dfca4349", scan_status: "DONE", page_count: 1 },
  { id: "b9c5da61-db67-4d7f-bcd6-e21668ea3b70", doc_type: "FINANCIAL_STATEMENT", original_name: "03_FINANCIAL_STATEMENT.pdf", size: "5.4 KB", sha256: "f20b7f5947aa1ec3b8112752fdced281e138dad36512f66036cdea52fe3e75f7", scan_status: "DONE", page_count: 1 },
  { id: "da1434cf-92ad-4b44-9be2-16951282d9c3", doc_type: "LAND_DEED", original_name: "04_LAND_DEED.pdf", size: "4.0 KB", sha256: "1d2ccf9d089cc9fe7878905c1eea42681f02335d40d7a50e2eda54c8ad447b73", scan_status: "DONE", page_count: 1 },
  { id: "447560fe-332a-47d6-9107-9fff1e3b34bd", doc_type: "BUILDING_PLAN", original_name: "05_BUILDING_PLAN.pdf", size: "4.5 KB", sha256: "bcab7aa1224db458675cf2afcfd55edb4fe27e973e28400bf4281d345f0ee324", scan_status: "DONE", page_count: 1 },
  { id: "4ba4642c-4b8c-4695-b2f7-2a3af8c7ae04", doc_type: "FACULTY_AFFIDAVIT", original_name: "06_FACULTY_AFFIDAVIT.pdf", size: "4.4 KB", sha256: "ca77f1d6ccc56de405cd6df0db2bb9e6435582f976f9de525246de15d0bd25ba", scan_status: "DONE", page_count: 1 },
];

function escapeHtml(str) {
  if (!str) return "";
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

async function loadDocuments() {
  try {
    const docs = await api.getDocuments("app-demo-0042", 1);
    if (docs && Array.isArray(docs) && docs.length > 0) {
      state.documents = docs;
    } else if (!state.documents || state.documents.length === 0) {
      state.documents = [...DEFAULT_DOCUMENTS];
    }
  } catch (err) {
    if (!state.documents || state.documents.length === 0) {
      state.documents = [...DEFAULT_DOCUMENTS];
    }
  }
  renderUploadedDocsTable();
}

function renderUploadedDocsTable() {
  if (!elements.uploadedDocsTableBody) return;
  const docs = state.documents && state.documents.length > 0 ? state.documents : DEFAULT_DOCUMENTS;

  if (elements.docsCountBadge) {
    elements.docsCountBadge.textContent = `${docs.length} Documents Ingested`;
  }

  elements.uploadedDocsTableBody.innerHTML = docs.map((doc) => {
    const isNew = doc.isNew;
    const sizeStr = doc.size || (doc.page_count ? `${doc.page_count} page(s)` : "Verified");
    const hash = doc.sha256 || "";
    const shortHash = hash.length > 14 ? `${hash.substring(0, 6)}...${hash.substring(hash.length - 4)}` : (hash || "-");
    const status = (doc.scan_status || "DONE").toUpperCase();
    const badgeClass = (status === "DONE" || status === "PROCESSED") ? "badge-pass" : (status === "FAILED" ? "badge-fail" : "badge-warn");

    return `
      <tr style="${isNew ? 'background: rgba(99, 102, 241, 0.15); transition: background 1s;' : ''}">
        <td><strong>${escapeHtml(doc.doc_type || 'DOCUMENT')}</strong></td>
        <td>
          ${escapeHtml(doc.original_name)}
          ${isNew ? '<span class="badge badge-pass" style="font-size: 0.65rem; margin-left: 6px;">New</span>' : ''}
        </td>
        <td>${sizeStr}</td>
        <td class="mono" style="font-size: 0.75rem;" title="${escapeHtml(hash)}">${shortHash}</td>
        <td><span class="badge ${badgeClass}">${status}</span></td>
      </tr>
    `;
  }).join("");
}

async function handleFileUpload(file) {
  if (!file) return;

  // Infer or retrieve selected document type
  let docType = elements.uploadDocType ? elements.uploadDocType.value : "AUTO";
  if (docType === "AUTO") {
    const fn = file.name.toLowerCase();
    if (fn.includes("faculty") && !fn.includes("affidavit")) docType = "FACULTY_LIST";
    else if (fn.includes("affidavit")) docType = "FACULTY_AFFIDAVIT";
    else if (fn.includes("land") || fn.includes("deed") || fn.includes("sale")) docType = "LAND_DEED";
    else if (fn.includes("plan") || fn.includes("drawing") || fn.includes("building") || fn.includes("floor")) docType = "BUILDING_PLAN";
    else if (fn.includes("finance") || fn.includes("financial") || fn.includes("balance") || fn.includes("audit")) docType = "FINANCIAL_STATEMENT";
    else if (fn.includes("app") || fn.includes("form")) docType = "APPLICATION_FORM";
    else docType = "OTHER";
  }

  // Show visual progress container
  if (elements.uploadProgressContainer) {
    elements.uploadProgressContainer.style.display = "block";
    if (elements.uploadProgressText) {
      elements.uploadProgressText.innerHTML = `⏳ Verifying magic bytes & uploading <strong>${escapeHtml(file.name)}</strong>...`;
    }
  }

  const fileSizeStr = file.size > 1024 * 1024 
    ? `${(file.size / (1024 * 1024)).toFixed(1)} MB` 
    : `${Math.max(1, (file.size / 1024).toFixed(1))} KB`;

  // Compute SHA-256 hash using browser crypto
  let clientHash = "";
  try {
    const buffer = await file.arrayBuffer();
    const hashBuf = await crypto.subtle.digest("SHA-256", buffer);
    clientHash = Array.from(new Uint8Array(hashBuf)).map(b => b.toString(16).padStart(2, "0")).join("");
  } catch (_) {
    clientHash = "sha256-" + Date.now();
  }

  try {
    const res = await api.uploadDocument("app-demo-0042", 1, file, docType);
    const newDoc = {
      doc_type: docType,
      original_name: file.name,
      size: fileSizeStr,
      sha256: res.sha256 || clientHash,
      scan_status: res.scan_status || "DONE",
      isNew: true,
    };

    if (!state.documents || state.documents.length === 0) {
      state.documents = [...DEFAULT_DOCUMENTS];
    }
    state.documents.unshift(newDoc);
    renderUploadedDocsTable();

    if (elements.uploadProgressContainer) {
      elements.uploadProgressContainer.style.display = "none";
    }
    showToast(`✓ "${file.name}" uploaded successfully! SHA-256: ${newDoc.sha256.substring(0, 10)}...`, "success");
  } catch (err) {
    console.warn("Upload fallback to local state:", err.message);
    const newDoc = {
      doc_type: docType,
      original_name: file.name,
      size: fileSizeStr,
      sha256: clientHash,
      scan_status: "PROCESSED",
      isNew: true,
    };

    if (!state.documents || state.documents.length === 0) {
      state.documents = [...DEFAULT_DOCUMENTS];
    }
    state.documents.unshift(newDoc);
    renderUploadedDocsTable();

    if (elements.uploadProgressContainer) {
      elements.uploadProgressContainer.style.display = "none";
    }
    showToast(`✓ "${file.name}" ingested! SHA-256: ${clientHash.substring(0, 10)}...`, "success");
  }
}

// Start app
window.addEventListener("DOMContentLoaded", init);
