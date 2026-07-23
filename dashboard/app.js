const API_BASE_URL = ["localhost", "127.0.0.1"].includes(window.location.hostname)
  && window.location.port === "3000"
  ? "http://localhost:8000"
  : window.location.origin;
const JOB_ROWS_TEMPLATE = "company|title|location|url|description|company_summary|tech_stack|role_fit|source_links|contact_email|contact_name|contact_url|source";
const CONTACT_CSV_TEMPLATE = "email,first_name,last_name,company,title,source,lead_grade,outreach_status,linkedin_url,notes";
const INDEED_CSV_TEMPLATE = "source_url,company_name,job_title,location,description,required_skills,contact_email,notes";
const DEFAULT_TARGET_ROLES = [
  "Junior AI Engineer",
  "Backend Developer",
  "Software Developer",
  "Web Developer",
  "Python Developer",
  "IT Support",
  "QA Analyst",
  "Automation Developer",
];
const DEFAULT_TARGET_LOCATIONS = [
  "Canada",
  "Remote Canada",
  "Vancouver",
  "British Columbia",
  "Alberta",
  "Saskatchewan",
  "Ontario",
  "Toronto",
  "Calgary",
  "Edmonton",
];
const DEFAULT_TARGET_SKILLS = [
  "Python",
  "FastAPI",
  "React",
  "JavaScript",
  "TypeScript",
  "Node.js",
  "SQL",
  "PostgreSQL",
  "REST API",
  "HTML",
  "CSS",
  "LLM",
  "AI",
  "Automation",
  "Git",
  "Docker",
  "GCP",
];
const JOB_SOURCE_OPTIONS = [
  {
    value: "remotive",
    label: "Remotive",
    detail: "Remote tech jobs without extra setup",
  },
  {
    value: "remoteok",
    label: "RemoteOK",
    detail: "Remote startup and software roles",
  },
  {
    value: "adzuna",
    label: "Adzuna",
    detail: "Canada coverage, needs API credentials",
    readinessKey: "adzuna_configured",
  },
];
const APPLICATION_STATUSES = [
  "SAVED",
  "APPLIED",
  "CONTACT_SEARCH_NEEDED",
  "CONTACT_FOUND",
  "OUTREACH_DRAFTED",
  "OUTREACH_APPROVED",
  "OUTREACH_SENT",
  "REPLIED",
  "INTERVIEW",
  "REJECTED",
  "FOLLOW_UP_DUE",
  "CLOSED",
];

const state = {
  leads: [],
  applications: [],
  careerSources: [],
  campaigns: [],
  drafts: [],
  replies: [],
  auditEvents: [],
  readiness: null,
  profile: null,
  selectedLeadId: "",
  leadFilters: {
    outreach: "",
    grade: "",
    search: "",
  },
  applicationFilters: {
    status: "",
    source: "",
    search: "",
  },
};

const elements = {
  apiStatus: document.querySelector("#api-status"),
  refreshAll: document.querySelector("#refresh-all"),
  readinessStatus: document.querySelector("#readiness-status"),
  readinessSummary: document.querySelector("#readiness-summary"),
  qaStatus: document.querySelector("#qa-status"),
  qaSummary: document.querySelector("#qa-summary"),
  qaChecklist: document.querySelector("#qa-checklist"),
  qaActions: document.querySelector(".qa-actions"),
  settingsStatus: document.querySelector("#settings-status"),
  settingsReadinessSummary: document.querySelector("#settings-readiness-summary"),
  settingsSafetySummary: document.querySelector("#settings-safety-summary"),
  settingsRefresh: document.querySelector("#settings-refresh"),
  connectGmail: document.querySelector("#connect-gmail"),
  deploymentChecklist: document.querySelector("#deployment-checklist"),
  profileSummary: document.querySelector("#profile-summary"),
  dashboardKpis: document.querySelector("#dashboard-kpis"),
  dashboardNextActions: document.querySelector("#dashboard-next-actions"),
  viewTabs: document.querySelectorAll("[data-view-target]"),
  sectionTabs: document.querySelectorAll("[data-section-target]"),
  workspacePanels: document.querySelectorAll("[data-workspace-panel]"),
  workflowView: document.querySelector("#workflow-view"),
  auditView: document.querySelector("#audit-view"),
  auditBack: document.querySelector("#audit-back"),
  leadForm: document.querySelector("#lead-form"),
  linkedinImportForm: document.querySelector("#linkedin-import-form"),
  indeedImportForm: document.querySelector("#indeed-import-form"),
  indeedCsvForm: document.querySelector("#indeed-csv-form"),
  applicationForm: document.querySelector("#application-form"),
  profileForm: document.querySelector("#profile-form"),
  careerSourceForm: document.querySelector("#career-source-form"),
  scanCareerSources: document.querySelector("#scan-career-sources"),
  jobUrlImportForm: document.querySelector("#job-url-import-form"),
  jobSearchForm: document.querySelector("#job-search-form"),
  jobSourceDiscoveryForm: document.querySelector("#job-source-discovery-form"),
  quickJobImportForm: document.querySelector("#quick-job-import-form"),
  jobDiscoveryForm: document.querySelector("#job-discovery-form"),
  batchLeadForm: document.querySelector("#batch-lead-form"),
  campaignForm: document.querySelector("#campaign-form"),
  draftForm: document.querySelector("#draft-form"),
  replyForm: document.querySelector("#reply-form"),
  leadsList: document.querySelector("#leads-list"),
  opportunityDetail: document.querySelector("#opportunity-detail"),
  applicationSummary: document.querySelector("#application-summary"),
  applicationsList: document.querySelector("#applications-list"),
  careerSourcesList: document.querySelector("#career-sources-list"),
  contactsList: document.querySelector("#contacts-list"),
  companyResearchList: document.querySelector("#company-research-list"),
  queueSummary: document.querySelector("#queue-summary"),
  findDraftEmails: document.querySelector("#find-draft-emails"),
  draftsList: document.querySelector("#drafts-list"),
  sentSummary: document.querySelector("#sent-summary"),
  sentList: document.querySelector("#sent-list"),
  replySummary: document.querySelector("#reply-summary"),
  syncEmailReplies: document.querySelector("#sync-email-replies"),
  repliesList: document.querySelector("#replies-list"),
  followupSummary: document.querySelector("#followup-summary"),
  followupDays: document.querySelector("#followup-days"),
  followupLimit: document.querySelector("#followup-limit"),
  followupCta: document.querySelector("#followup-cta"),
  generateFollowups: document.querySelector("#generate-followups"),
  followupList: document.querySelector("#followup-list"),
  auditList: document.querySelector("#audit-list"),
  leadCount: document.querySelector("#lead-count"),
  applicationCount: document.querySelector("#application-count"),
  applicationStatusFilter: document.querySelector("#application-status-filter"),
  applicationSourceFilter: document.querySelector("#application-source-filter"),
  applicationSearch: document.querySelector("#application-search"),
  clearApplicationFilters: document.querySelector("#clear-application-filters"),
  careerSourceCount: document.querySelector("#career-source-count"),
  leadOutreachFilter: document.querySelector("#lead-outreach-filter"),
  leadGradeFilter: document.querySelector("#lead-grade-filter"),
  leadSearch: document.querySelector("#lead-search"),
  clearLeadFilters: document.querySelector("#clear-lead-filters"),
  pipelineBatchLimit: document.querySelector("#pipeline-batch-limit"),
  runPipelineBatch: document.querySelector("#run-pipeline-batch"),
  contactCount: document.querySelector("#contact-count"),
  companyResearchCount: document.querySelector("#company-research-count"),
  draftCount: document.querySelector("#draft-count"),
  sentCount: document.querySelector("#sent-count"),
  replyCount: document.querySelector("#reply-count"),
  followupCount: document.querySelector("#followup-count"),
  auditCount: document.querySelector("#audit-count"),
  auditTabCount: document.querySelector("#audit-tab-count"),
  auditShownCount: document.querySelector("#audit-shown-count"),
  toast: document.querySelector("#toast"),
};

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;

  if (!response.ok) {
    throw new Error(formatApiError(payload?.detail, response.status));
  }

  return payload;
}

function formatApiError(detail, status) {
  if (!detail) return `Request failed: ${status}`;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      if (typeof item === "string") return item;
      const path = Array.isArray(item.loc) ? item.loc.filter((part) => part !== "body").join(".") : "";
      const message = item.msg || JSON.stringify(item);
      return path ? `${path}: ${message}` : message;
    }).join("; ");
  }
  if (typeof detail === "object") {
    return detail.message || detail.msg || JSON.stringify(detail);
  }
  return String(detail);
}

function formToObject(form) {
  const formData = new FormData(form);
  const payload = {};
  for (const [key, value] of formData.entries()) {
    payload[key] = typeof value === "string" ? value.trim() : value;
  }
  return payload;
}

function removeEmptyValues(payload) {
  return Object.fromEntries(
    Object.entries(payload).filter(([, value]) => value !== "" && value !== null),
  );
}

function parseLeadCsv(csv) {
  const lines = csv
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length < 2) {
    throw new Error("Add one contact row under the CSV header before importing.");
  }

  const headers = lines[0].split(",").map((header) => header.trim());
  const required = ["first_name"];
  for (const field of required) {
    if (!headers.includes(field)) {
      throw new Error(`CSV must include ${field}.`);
    }
  }

  return lines.slice(1).map((line) => {
    const values = line.split(",").map((value) => value.trim());
    const row = {};
    headers.forEach((header, index) => {
      row[header] = values[index] || "";
    });
    return removeEmptyValues(row);
  });
}

function parseList(value) {
  return String(value || "")
    .split(/[\n,;]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function uniqueList(values) {
  const seen = new Set();
  return values.filter((value) => {
    const normalized = value.trim().toLowerCase();
    if (!normalized || seen.has(normalized)) return false;
    seen.add(normalized);
    return true;
  });
}

function tagSuggestionsForField(name) {
  if (name === "target_roles") return DEFAULT_TARGET_ROLES;
  if (name === "target_locations") return DEFAULT_TARGET_LOCATIONS;
  if (name === "target_skills" || name === "required_skills") return DEFAULT_TARGET_SKILLS;
  return [];
}

function writeTextareaList(textarea, values) {
  textarea.value = uniqueList(values).join("\n");
}

function syncTagEditorForTextarea(textarea) {
  const editor = textarea?._tagEditor;
  if (editor) {
    renderTagEditor(editor);
  }
}

function renderTagEditor(editor) {
  const textarea = editor._textarea;
  if (!textarea) return;
  const values = uniqueList(parseList(textarea.value));
  const list = editor.querySelector(".tag-list");
  const suggestions = editor.querySelector(".tag-suggestions");
  const suggestionValues = tagSuggestionsForField(textarea.name).filter(
    (item) => !values.some((value) => value.toLowerCase() === item.toLowerCase()),
  );

  list.innerHTML = values.length
    ? values.map((value) => (
      `<button class="tag-chip" type="button" data-tag-remove="${escapeHtml(value)}">
        <span>${escapeHtml(value)}</span>
        <strong aria-hidden="true">x</strong>
      </button>`
    )).join("")
    : `<span class="tag-empty">No targets yet. Add one below.</span>`;

  suggestions.innerHTML = suggestionValues.slice(0, 8).map((value) => (
    `<button class="tag-suggestion" type="button" data-tag-add="${escapeHtml(value)}">${escapeHtml(value)}</button>`
  )).join("");
}

function addTagValues(editor, rawValue) {
  const textarea = editor._textarea;
  const values = uniqueList([...parseList(textarea.value), ...parseList(rawValue)]);
  writeTextareaList(textarea, values);
  syncTagEditorForTextarea(textarea);
}

function setupTagEditors(root = document) {
  root.querySelectorAll(
    'textarea[name="target_roles"], textarea[name="target_locations"], textarea[name="target_skills"], textarea[name="required_skills"]',
  ).forEach((textarea) => {
    if (textarea._tagEditor) {
      syncTagEditorForTextarea(textarea);
      return;
    }

    textarea.classList.add("raw-target-textarea");
    const editor = document.createElement("div");
    editor.className = "tag-editor";
    editor.innerHTML = `
      <div class="tag-list"></div>
      <div class="tag-input-row">
        <input class="tag-input" type="text" placeholder="Add one item, or paste several separated by commas">
        <button class="secondary tag-add-button" type="button">Add</button>
      </div>
      <div class="tag-suggestions" aria-label="Suggested targets"></div>
    `;
    textarea.insertAdjacentElement("afterend", editor);
    textarea._tagEditor = editor;
    editor._textarea = textarea;

    editor.addEventListener("click", (event) => {
      const removeButton = event.target.closest("[data-tag-remove]");
      const addButton = event.target.closest("[data-tag-add]");
      if (removeButton) {
        const nextValues = parseList(textarea.value).filter(
          (value) => value.toLowerCase() !== removeButton.dataset.tagRemove.toLowerCase(),
        );
        writeTextareaList(textarea, nextValues);
        syncTagEditorForTextarea(textarea);
        return;
      }
      if (addButton) {
        addTagValues(editor, addButton.dataset.tagAdd);
        return;
      }
      if (event.target.closest(".tag-add-button")) {
        const input = editor.querySelector(".tag-input");
        addTagValues(editor, input.value);
        input.value = "";
      }
    });

    editor.querySelector(".tag-input").addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      addTagValues(editor, event.currentTarget.value);
      event.currentTarget.value = "";
    });

    renderTagEditor(editor);
  });
}

function setupJobSourceToggles() {
  const textarea = elements.jobSearchForm?.elements?.sources;
  if (!textarea || textarea._sourceToggleEditor) return;

  textarea.classList.add("raw-target-textarea");
  const editor = document.createElement("div");
  editor.className = "source-toggle-grid";
  textarea.insertAdjacentElement("afterend", editor);
  textarea._sourceToggleEditor = editor;

  function syncFromChecks() {
    const selected = Array.from(editor.querySelectorAll("input[data-source-option]:checked"))
      .map((input) => input.value);
    textarea.value = selected.join("\n");
  }

  function render() {
    const selected = new Set(parseList(textarea.value));
    const readiness = state.readiness?.job_sources;
    editor.innerHTML = JOB_SOURCE_OPTIONS.map((source) => `
      <div class="source-toggle ${source.readinessKey && readiness && !readiness[source.readinessKey] ? "disabled" : ""}">
        <input
          type="checkbox"
          data-source-option
          value="${escapeHtml(source.value)}"
          ${selected.has(source.value) ? "checked" : ""}
          ${source.readinessKey && readiness && !readiness[source.readinessKey] ? "disabled" : ""}
        >
        <span>
          <strong>${escapeHtml(source.label)}</strong>
          <small>${escapeHtml(source.detail)}</small>
          ${source.readinessKey && readiness && !readiness[source.readinessKey] ? "<small>Setup needed before search</small>" : ""}
        </span>
      </div>
    `).join("");
    syncFromChecks();
  }

  editor.addEventListener("change", (event) => {
    if (event.target.matches("input[data-source-option]")) {
      syncFromChecks();
    }
  });
  editor._render = render;
  render();
}

function syncJobSourceToggles() {
  const editor = elements.jobSearchForm?.elements?.sources?._sourceToggleEditor;
  if (editor?._render) {
    editor._render();
  }
}

function parseJobDiscoveryRows(value) {
  const lines = String(value || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length < 2) {
    throw new Error("Add one job row under the job header before importing.");
  }

  const headers = lines[0].split("|").map((header) => header.trim());
  const required = ["company", "title"];
  for (const field of required) {
    if (!headers.includes(field)) {
      throw new Error(`Job rows must include ${field}.`);
    }
  }

  return lines.slice(1).map((line) => {
    const values = line.split("|").map((item) => item.trim());
    const row = {};
    headers.forEach((header, index) => {
      row[header] = values[index] || "";
    });
    return removeEmptyValues(row);
  });
}

function readableSourceName(form) {
  if (form.id.includes("linkedin")) return "LinkedIn";
  if (form.id.includes("indeed")) return "Indeed";
  return "Job";
}

function inferredJobTitle(raw, sourceName) {
  if (raw.job_title) return raw.job_title;
  const descriptionTitle = parseList(raw.description || raw.pasted_description || "")[0];
  return descriptionTitle || `${sourceName} Job Opportunity`;
}

function sourceOpportunityFromForm(form) {
  const raw = formToObject(form);
  const sourceName = readableSourceName(form);
  return removeEmptyValues({
    source_url: raw.source_url,
    company_name: raw.company_name || "Company from pasted job",
    job_title: inferredJobTitle(raw, sourceName),
    location: raw.location,
    description: raw.description,
    required_skills: parseList(raw.required_skills),
    recruiter_profile_url: raw.recruiter_profile_url,
    recruiter_name: raw.recruiter_name,
    contact_email: raw.contact_email,
    notes: raw.notes,
  });
}

function sourceTrackerPayload(opportunity) {
  return {
    target_roles: profileTargetList("target_roles", DEFAULT_TARGET_ROLES),
    target_locations: profileTargetList("target_locations", DEFAULT_TARGET_LOCATIONS),
    target_skills: profileTargetList("target_skills", DEFAULT_TARGET_SKILLS),
    opportunities: [opportunity],
  };
}

function jobUrlImportPayloadFromForm(form) {
  const raw = formToObject(form);
  return removeEmptyValues({
    source_url: raw.source_url,
    source_hint: raw.source_hint,
    company_name: raw.company_name,
    job_title: raw.job_title,
    location: raw.location,
    pasted_description: raw.pasted_description,
    recruiter_profile_url: raw.recruiter_profile_url,
    recruiter_name: raw.recruiter_name,
    contact_email: raw.contact_email,
    notes: raw.notes,
    target_roles: profileTargetList("target_roles", DEFAULT_TARGET_ROLES),
    target_locations: profileTargetList("target_locations", DEFAULT_TARGET_LOCATIONS),
    target_skills: profileTargetList("target_skills", DEFAULT_TARGET_SKILLS),
    import_result: form.elements.import_result.checked,
  });
}

function sourceTrackerCsvPayload(csvRows) {
  return {
    target_roles: profileTargetList("target_roles", DEFAULT_TARGET_ROLES),
    target_locations: profileTargetList("target_locations", DEFAULT_TARGET_LOCATIONS),
    target_skills: profileTargetList("target_skills", DEFAULT_TARGET_SKILLS),
    csv_rows: csvRows,
  };
}

function profileTargetList(key, fallback) {
  const values = state.profile?.[key];
  return Array.isArray(values) && values.length ? values : fallback;
}

function profilePayloadFromForm(form) {
  const raw = formToObject(form);
  return removeEmptyValues({
    owner_name: raw.owner_name,
    primary_email: raw.primary_email,
    outreach_email: raw.outreach_email,
    target_roles: parseList(raw.target_roles),
    target_locations: parseList(raw.target_locations),
    target_skills: parseList(raw.target_skills),
    resume_summary: raw.resume_summary,
    linkedin_profile_url: raw.linkedin_profile_url,
    github_url: raw.github_url,
    portfolio_url: raw.portfolio_url,
    default_resume_version: raw.default_resume_version,
  });
}

function setFieldValue(form, name, value) {
  if (form?.elements?.[name]) {
    form.elements[name].value = value || "";
    syncTagEditorForTextarea(form.elements[name]);
  }
}

function setTargetDefaultsForForm(form) {
  if (!form) return;
  setFieldValue(form, "target_roles", profileTargetList("target_roles", DEFAULT_TARGET_ROLES).join("\n"));
  setFieldValue(form, "target_locations", profileTargetList("target_locations", DEFAULT_TARGET_LOCATIONS).join("\n"));
  setFieldValue(form, "target_skills", profileTargetList("target_skills", DEFAULT_TARGET_SKILLS).join("\n"));
}

function applicationPayloadFromForm(form) {
  const raw = formToObject(form);
  return removeEmptyValues({
    company_name: raw.company_name,
    job_title: raw.job_title,
    source: raw.source,
    job_url: raw.job_url,
    location: raw.location,
    status: raw.status || "SAVED",
    applied_date: raw.applied_date,
    resume_version: raw.resume_version || state.profile?.default_resume_version,
    cover_letter_version: raw.cover_letter_version,
    contact_found: form.elements.contact_found.checked,
    gmail_thread_id: raw.gmail_thread_id,
    notes: raw.notes,
  });
}

function careerSourcePayloadFromForm(form) {
  const raw = formToObject(form);
  return removeEmptyValues({
    company_name: raw.company_name,
    careers_url: raw.careers_url,
    source_type: raw.source_type || "company_careers",
    notes: raw.notes,
    active: true,
  });
}

function quickJobImportPayloadFromForm(form) {
  const raw = formToObject(form);
  const requiredSkills = parseList(raw.required_skills);
  const job = removeEmptyValues({
    company: raw.company,
    title: raw.title,
    location: raw.location,
    url: raw.url,
    description: raw.description,
    tech_stack: requiredSkills.join(", "),
    role_fit: raw.notes,
    source_links: raw.url,
    contact_email: raw.contact_email,
    source: "manual_job_import",
  });

  return {
    target_roles: profileTargetList("target_roles", DEFAULT_TARGET_ROLES),
    target_locations: profileTargetList("target_locations", DEFAULT_TARGET_LOCATIONS),
    target_skills: profileTargetList("target_skills", DEFAULT_TARGET_SKILLS),
    jobs: [job],
  };
}

function careerSourceScanPayload(sourceIds = []) {
  return {
    career_source_ids: sourceIds,
    target_roles: profileTargetList("target_roles", DEFAULT_TARGET_ROLES),
    target_locations: profileTargetList("target_locations", DEFAULT_TARGET_LOCATIONS),
    target_skills: profileTargetList("target_skills", DEFAULT_TARGET_SKILLS),
    import_results: true,
  };
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.hidden = false;
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => {
    elements.toast.hidden = true;
  }, 3200);
}

async function withButtonState(button, workingLabel, doneLabel, action) {
  const originalLabel = button.textContent;
  button.disabled = true;
  button.classList.remove("is-done");
  button.classList.add("is-working");
  button.textContent = workingLabel;
  try {
    const result = await action();
    button.classList.remove("is-working");
    button.classList.add("is-done");
    button.textContent = doneLabel;
    return result;
  } catch (error) {
    button.classList.remove("is-working");
    button.textContent = originalLabel;
    throw error;
  } finally {
    window.setTimeout(() => {
      button.classList.remove("is-working", "is-done");
      button.disabled = false;
      button.textContent = originalLabel;
    }, 1200);
  }
}

function formatDate(value) {
  return new Date(value).toLocaleString();
}

function todayDateString() {
  return new Date().toLocaleDateString("en-CA");
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#039;",
  })[character]);
}

function normalizeUrl(value) {
  const url = String(value || "").trim();
  if (!url) return "";
  if (/^https?:\/\//i.test(url)) return url;
  if (/^(www\.|linkedin\.com)/i.test(url)) return `https://${url}`;
  return "";
}

function contactCell(lead) {
  const parts = [];
  if (lead.email) {
    parts.push(`<a href="mailto:${escapeHtml(lead.email)}">${escapeHtml(lead.email)}</a>`);
  }
  const sourceUrl = normalizeUrl(lead.contact_source_url || lead.linkedin_url);
  if (sourceUrl) {
    const sourceLabel = /linkedin\.com/i.test(sourceUrl) ? "LinkedIn" : "Source link";
    parts.push(
      `<a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">${sourceLabel}</a>`,
    );
  }
  return parts.length ? parts.join("<br>") : "<span class=\"muted\">Email needed to send</span>";
}

function sourceLabel(lead) {
  const source = String(lead.source || "manual").replace(/^job_discovery:/, "");
  return source.replace(/_/g, " ");
}

function isLinkedInSource(lead) {
  return sourceLabel(lead).toLowerCase().includes("linkedin")
    || /linkedin\.com/i.test(`${lead.opportunity_url || ""} ${lead.linkedin_url || ""} ${lead.contact_source_url || ""}`);
}

function isOpportunity(lead) {
  return Boolean(
    lead.opportunity_url
    || ["LINKEDIN", "INDEED"].includes(String(lead.source || "").toUpperCase())
    || String(lead.source || "").startsWith("job_discovery:"),
  );
}

function hasUsableContact(lead) {
  if (lead.email) return true;
  return Boolean(
    lead.contact_type
    && lead.contact_type !== "fallback"
    && lead.contact_verification_status !== "not_found",
  );
}

function hasEmailContact(lead) {
  return Boolean(lead?.email);
}

function looksLikeEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value || "").trim());
}

function displayContactName(lead) {
  return lead.contact_name || `${lead.first_name || ""} ${lead.last_name || ""}`.trim() || "Hiring Team";
}

function displayOpportunityStage(lead) {
  return lead.outreach_status || (isOpportunity(lead) ? "Opportunity Discovered" : "Contact Found");
}

function nextStepLabel(lead) {
  const activeDraft = activeDraftForLead(lead.id);
  if (activeDraft) return "Review Draft";
  const stage = displayOpportunityStage(lead);
  if (stage === "DISCOVERED" || lead.fit_score === null || lead.fit_score === undefined) return "Run Next: Analyze";
  if (stage === "ANALYZED" || !lead.company_summary) return "Run Next: Research";
  if (stage === "COMPANY_RESEARCHED") return "Run Next: Find Contact";
  if (stage === "CONTACT_FOUND") return "Run Next: Draft";
  if (stage === "PENDING_APPROVAL") return "Review Draft";
  if (stage === "APPROVED") return "Send / Dry Run";
  if (stage === "SENT") return "Check Replies";
  if (stage === "FOLLOW_UP_DUE") return "Follow Up";
  return "Review Status";
}

function truncate(value, maxLength = 180) {
  const text = String(value || "").trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 3)}...`;
}

function badge(value) {
  const className = String(value || "").replace(/[^a-z0-9_-]/gi, "-").toLowerCase();
  return `<span class="badge ${escapeHtml(className)}">${escapeHtml(value)}</span>`;
}

function filteredLeads() {
  const search = state.leadFilters.search.toLowerCase();
  return state.leads.filter((lead) => {
    if (state.leadFilters.outreach && lead.outreach_status !== state.leadFilters.outreach) {
      return false;
    }
    if (state.leadFilters.grade && lead.lead_grade !== state.leadFilters.grade) {
      return false;
    }
    if (!search) return true;

    const searchable = [
      lead.first_name,
      lead.last_name,
      lead.company,
      lead.title,
      lead.email,
      lead.linkedin_url,
      lead.opportunity_url,
      lead.opportunity_location,
      lead.company_summary,
      lead.tech_stack,
      lead.role_fit,
      lead.contact_name,
      lead.contact_role,
      lead.contact_type,
      lead.contact_source_url,
      lead.suggested_first_message,
    ].filter(Boolean).join(" ").toLowerCase();

    return searchable.includes(search);
  });
}

function applicationLead(application) {
  if (!application?.lead_id) return null;
  return state.leads.find((lead) => lead.id === application.lead_id) || null;
}

function applicationSourceUrl(application) {
  const lead = applicationLead(application);
  return normalizeUrl(application.job_url || lead?.opportunity_url || lead?.linkedin_url);
}

function applicationSearchText(application) {
  const lead = applicationLead(application);
  return [
    application.company_name,
    application.job_title,
    application.source,
    application.location,
    application.status,
    application.resume_version,
    application.cover_letter_version,
    application.gmail_thread_id,
    application.notes,
    lead?.company_summary,
    lead?.role_fit,
    lead?.tech_stack,
    lead?.contact_name,
    lead?.email,
  ].filter(Boolean).join(" ").toLowerCase();
}

function filteredApplications() {
  const search = state.applicationFilters.search.toLowerCase();
  return state.applications.filter((application) => {
    if (state.applicationFilters.status && application.status !== state.applicationFilters.status) {
      return false;
    }
    if (state.applicationFilters.source && application.source !== state.applicationFilters.source) {
      return false;
    }
    return !search || applicationSearchText(application).includes(search);
  });
}

function countBy(items, key) {
  return items.reduce((counts, item) => {
    const value = item[key] || "None";
    counts[value] = (counts[value] || 0) + 1;
    return counts;
  }, {});
}

function latestDraftForLead(leadId) {
  return state.drafts
    .filter((draft) => draft.lead_id === leadId)
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0] || null;
}

function activeDraftForLead(leadId) {
  return state.drafts.find((draft) => (
    draft.lead_id === leadId && ["pending_approval", "approved"].includes(draft.status)
  ));
}

function applicationForLead(leadId) {
  return state.applications.find((application) => application.lead_id === leadId) || null;
}

function draftsForLead(leadId) {
  return state.drafts
    .filter((draft) => draft.lead_id === leadId)
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
}

function sentDrafts() {
  return state.drafts
    .filter((draft) => draft.status === "sent")
    .sort((a, b) => new Date(b.sent_at || b.created_at) - new Date(a.sent_at || a.created_at));
}

function repliesForLead(leadId) {
  return state.replies
    .filter((reply) => reply.lead_id === leadId)
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
}

function followupLeads() {
  const repliedLeadIds = new Set(state.replies.map((reply) => reply.lead_id));
  return state.leads.filter((lead) => {
    if (["FOLLOW_UP_DUE", "Follow-up Due"].includes(displayOpportunityStage(lead))) return true;
    const sentDraft = state.drafts.find((draft) => draft.lead_id === lead.id && draft.status === "sent");
    return Boolean(sentDraft && !repliedLeadIds.has(lead.id));
  });
}

function auditEventsForLead(lead, application, drafts, replies) {
  const ids = new Set([
    lead.id,
    application?.id,
    ...drafts.map((draft) => draft.id),
    ...replies.map((reply) => reply.id),
  ].filter(Boolean));
  return state.auditEvents
    .filter((event) => ids.has(event.entity_id))
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
}

function applicationStatusOptions(currentStatus) {
  return APPLICATION_STATUSES.map((status) => (
    `<option value="${escapeHtml(status)}" ${status === currentStatus ? "selected" : ""}>${escapeHtml(status)}</option>`
  )).join("");
}

function stageCount(counts, ...names) {
  return names.reduce((total, name) => total + (counts[name] || 0), 0);
}

function renderQueueSummary() {
  const outreach = countBy(state.leads, "outreach_status");
  const grades = countBy(state.leads, "lead_grade");
  const applications = countBy(state.applications, "status");
  const draftPending = state.drafts.filter((draft) => draft.status === "pending_approval").length;
  const draftApproved = state.drafts.filter((draft) => draft.status === "approved").length;

  const cards = [
    ["DISCOVERED", stageCount(outreach, "DISCOVERED", "Opportunity Discovered"), "muted-card"],
    ["Applications", state.applications.length, "muted-card"],
    ["APPLIED", applications.APPLIED || 0, "success"],
    ["INTERVIEW", applications.INTERVIEW || 0, "success"],
    ["ANALYZED", stageCount(outreach, "ANALYZED"), "muted-card"],
    ["COMPANY_RESEARCHED", stageCount(outreach, "COMPANY_RESEARCHED", "Company Researched", "Contact Search Needed"), "muted-card"],
    ["CONTACT_FOUND", stageCount(outreach, "CONTACT_FOUND", "Contact Found"), "success"],
    ["PENDING_APPROVAL", stageCount(outreach, "PENDING_APPROVAL", "Pending Approval"), "warning"],
    ["Drafts Pending", draftPending, "warning"],
    ["Approved", draftApproved, "success"],
    ["SENT", stageCount(outreach, "SENT", "Sent"), "muted-card"],
    ["REPLIED", stageCount(outreach, "REPLIED", "Replied"), "success"],
    ["FOLLOW_UP_DUE", stageCount(outreach, "FOLLOW_UP_DUE", "Follow-up Due"), "warning"],
    ["High Priority", grades["High Priority"] || 0, "success"],
  ];

  elements.queueSummary.innerHTML = cards.map(([label, value, className]) => `
    <div class="summary-card ${className}">
      <strong>${value}</strong>
      <span>${escapeHtml(label)}</span>
    </div>
  `).join("");
}

function renderReadiness() {
  const readiness = state.readiness;
  if (!readiness) return;

  const checks = [
    ["Database", readiness.database.connected, "Connected", "Unavailable"],
    ["AI drafting", readiness.ai.enabled, "Enabled", "Fallback mode"],
    [
      `Email: ${readiness.email?.provider || "provider"}`,
      readiness.email?.configured,
      "Configured",
      "Not configured",
    ],
    ["Live sending", readiness.email?.sending_enabled, "Enabled", "Dry run"],
    ["Reply sync", readiness.email?.reply_sync_enabled, "Enabled", "Disabled"],
  ];

  elements.readinessStatus.textContent = readiness.status;
  elements.readinessStatus.classList.toggle("ok", readiness.status === "ready");
  elements.readinessStatus.classList.toggle("error", readiness.status !== "ready");
  elements.readinessSummary.innerHTML = checks.map(([label, enabled, yes, no]) => `
    <div class="summary-card ${enabled ? "success" : "muted-card"}">
      <strong>${enabled ? "Yes" : "No"}</strong>
      <span>${escapeHtml(label)} - ${escapeHtml(enabled ? yes : no)}</span>
    </div>
  `).join("");
}

function settingCard(label, value, detail, enabled = true) {
  return `
    <div class="summary-card setting-summary-card ${enabled ? "success" : "muted-card"}">
      <strong>${escapeHtml(value)}</strong>
      <span>${escapeHtml(label)}</span>
      <small>${escapeHtml(detail)}</small>
    </div>
  `;
}

function renderProfileSummary() {
  if (!elements.profileSummary || !state.profile) return;
  const profile = state.profile;
  const cards = [
    ["Owner", profile.owner_name || "Not set", "Displayed in generated context", Boolean(profile.owner_name)],
    ["Primary Email", profile.primary_email || "Not set", "Your real job-search email", Boolean(profile.primary_email)],
    ["Outreach Email", profile.outreach_email || "Not set", "Email identity used for outreach context", Boolean(profile.outreach_email)],
    ["Target Roles", String((profile.target_roles || []).length), "Roles used for discovery and fit scoring", Boolean((profile.target_roles || []).length)],
    ["Target Locations", String((profile.target_locations || []).length), "Canada and remote preferences", Boolean((profile.target_locations || []).length)],
    ["Target Skills", String((profile.target_skills || []).length), "Skills used for matching", Boolean((profile.target_skills || []).length)],
  ];

  elements.profileSummary.innerHTML = cards.map(([label, value, detail, enabled]) => (
    settingCard(label, value, detail, enabled)
  )).join("");
}

function renderSettingsOverview() {
  const readiness = state.readiness;
  if (!readiness) return;

  if (elements.settingsStatus) {
    elements.settingsStatus.textContent = readiness.status;
    elements.settingsStatus.classList.toggle("ok", readiness.status === "ready");
    elements.settingsStatus.classList.toggle("error", readiness.status !== "ready");
  }

  if (elements.settingsReadinessSummary) {
    const sender = readiness.email?.sender_email || readiness.gmail?.sender_email || "Not set";
    const inbox = readiness.email?.inbox_email || readiness.gmail?.inbox_email || sender;
    const cards = [
      ["Database", readiness.database?.connected ? "Connected" : "Unavailable", "Required for pipeline state", readiness.database?.connected],
      ["Gmail OAuth", readiness.gmail?.refresh_token_configured ? "Connected" : "Needs OAuth", "Required for Gmail send/reply sync", readiness.gmail?.refresh_token_configured],
      ["Sender", sender, "Configured sender identity", Boolean(readiness.email?.sender_email || readiness.gmail?.sender_email)],
      ["Inbox", inbox || "Not set", "Reply sync mailbox", Boolean(inbox)],
      ["AI Drafting", readiness.ai?.enabled ? "Enabled" : "Fallback", "LLM can be added later when you approve", true],
      ["Automation Token", readiness.automation?.token_required ? "Required" : "Local open", "Protects machine-triggered routes", true],
    ];
    elements.settingsReadinessSummary.innerHTML = cards.map(([label, value, detail, enabled]) => (
      settingCard(label, value, detail, enabled)
    )).join("");
  }

  if (elements.settingsSafetySummary) {
    const cards = [
      ["Human Approval", "Required", "Drafts must be approved before send", true],
      ["Live Sending", readiness.email?.sending_enabled ? "Enabled" : "Dry Run", "LIVE_SEND=false is safest while testing", !readiness.email?.sending_enabled],
      ["Reply Sync", readiness.email?.reply_sync_enabled ? "Enabled" : "Manual/Disabled", "Can sync Gmail replies when enabled", readiness.email?.reply_sync_enabled],
      ["LinkedIn", "Manual Only", "No scraping or auto-messaging", true],
      ["Secrets", "Server Only", "Tokens and client secrets stay out of the dashboard", true],
    ];
    elements.settingsSafetySummary.innerHTML = cards.map(([label, value, detail, enabled]) => (
      settingCard(label, value, detail, enabled)
    )).join("");
  }

  if (elements.deploymentChecklist) {
    const checklist = [
      ["Database ready", readiness.database?.connected],
      ["Gmail OAuth configured", readiness.gmail?.configured],
      ["Sender email set", readiness.gmail?.sender_configured],
      ["Human approval enforced", readiness.safety?.human_approval_required],
      ["Live send intentionally configured", !readiness.email?.sending_enabled || readiness.email?.configured],
      ["LLM decision pending", !readiness.ai?.enabled || readiness.ai?.provider_key_configured],
    ];
    elements.deploymentChecklist.innerHTML = checklist.map(([label, done]) => `
      <div class="checklist-item ${done ? "done" : "pending"}">
        <span>${done ? "Ready" : "Needed"}</span>
        <strong>${escapeHtml(label)}</strong>
      </div>
    `).join("");
  }
}

function renderDashboardOverview() {
  if (!elements.dashboardKpis || !elements.dashboardNextActions) return;
  const outreach = countBy(state.leads, "outreach_status");
  const applications = countBy(state.applications, "status");
  const pendingDrafts = state.drafts.filter((draft) => draft.status === "pending_approval").length;
  const approvedDrafts = state.drafts.filter((draft) => draft.status === "approved").length;
  const sentDrafts = state.drafts.filter((draft) => draft.status === "sent").length;
  const contacts = state.leads.filter(hasUsableContact).length;
  const followups = state.leads.filter((lead) => displayOpportunityStage(lead) === "FOLLOW_UP_DUE").length;

  const cards = [
    ["Opportunities", state.leads.length, "Total tracked targets"],
    ["Applications", state.applications.length, `${applications.APPLIED || 0} applied`],
    ["Need Research", stageCount(outreach, "DISCOVERED", "ANALYZED"), "Ready for safe batch"],
    ["Contact Found", stageCount(outreach, "CONTACT_FOUND") || contacts, "Ready for draft decision"],
    ["Draft Review", pendingDrafts, `${approvedDrafts} approved`],
    ["Sent", sentDrafts, `${state.replies.length} replies tracked`],
  ];

  elements.dashboardKpis.innerHTML = cards.map(([label, value, detail]) => `
    <div class="metric-card">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      <small>${escapeHtml(detail)}</small>
    </div>
  `).join("");

  const actionRows = [
    ["Run safe batch", stageCount(outreach, "DISCOVERED", "ANALYZED", "COMPANY_RESEARCHED"), "Opportunities"],
    ["Review drafts", pendingDrafts, "Drafts / Approval Queue"],
    ["Send approved", approvedDrafts, "Gmail Outreach"],
    ["Check replies", sentDrafts, "Replies"],
    ["Follow up", followups, "Follow-ups"],
  ];

  elements.dashboardNextActions.innerHTML = `
    <div class="next-action-header">
      <h3>Next Work</h3>
      <span class="muted">Safe actions stay human-approved before sending.</span>
    </div>
    <div class="next-action-grid">
      ${actionRows.map(([label, count, target]) => `
        <div class="next-action-item">
          <strong>${escapeHtml(count)}</strong>
          <span>${escapeHtml(label)}</span>
          <small>${escapeHtml(target)}</small>
        </div>
      `).join("")}
    </div>
  `;
}

function qaStep(done, label, evidence, target, actionLabel, sectionTarget) {
  return { done, label, evidence, target, actionLabel, sectionTarget };
}

function renderDryRunQa() {
  if (!elements.qaSummary || !elements.qaChecklist) return;

  const profileReady = Boolean(
    state.profile?.primary_email
    && state.profile?.outreach_email
    && (state.profile?.target_roles || []).length
    && (state.profile?.target_locations || []).length
    && (state.profile?.target_skills || []).length,
  );
  const dryRunEnabled = !state.readiness?.email?.sending_enabled;
  const gmailReady = Boolean(
    state.readiness?.email?.configured
    && state.readiness?.gmail?.refresh_token_configured
    && state.readiness?.gmail?.sender_configured,
  );
  const analyzedCount = state.leads.filter((lead) => (
    lead.fit_score !== null
    && lead.fit_score !== undefined
  )).length;
  const researchedCount = state.leads.filter((lead) => (
    lead.company_summary || lead.role_fit || lead.tech_stack
  )).length;
  const contactCount = state.leads.filter(hasUsableContact).length;
  const emailContactCount = state.leads.filter(hasEmailContact).length;
  const pendingDrafts = state.drafts.filter((draft) => draft.status === "pending_approval").length;
  const approvedDrafts = state.drafts.filter((draft) => draft.status === "approved").length;
  const sendReadyDrafts = state.drafts.filter((draft) => {
    const lead = state.leads.find((item) => item.id === draft.lead_id);
    return draft.status === "approved" && hasEmailContact(lead);
  }).length;
  const sent = sentDrafts();
  const followups = followupLeads();
  const qaSteps = [
    qaStep(profileReady, "Profile configured", "Email, roles, locations, and skills are saved", "Complete Settings profile", "Open Settings", "settings"),
    qaStep(dryRunEnabled, "Live sending disabled", "Dry run is the expected QA mode", "Keep LIVE_SEND / EMAIL_SENDING_ENABLED false", "Open Settings", "settings"),
    qaStep(gmailReady, "Gmail connected", "OAuth, sender, and token are configured", "Connect Gmail OAuth", "Open Settings", "settings"),
    qaStep(state.leads.length >= 3, "3-5 real opportunities imported", `${state.leads.length} opportunities tracked`, "Import at least 3 real targets", "Open Job Discovery", "job-discovery"),
    qaStep(analyzedCount >= 1, "Fit analysis works", `${analyzedCount} opportunities have fit scores`, "Run Analyze Fit or Run Next", "Open Opportunities", "opportunities"),
    qaStep(researchedCount >= 1, "Company research works", `${researchedCount} opportunities have research context`, "Run Research Company", "Open Company Research", "company-research"),
    qaStep(contactCount >= 1, "Contact/source lookup works", `${contactCount} opportunities have contact source context`, "Run Find Contact or add a public contact/source link", "Open Contact Finder", "contact-finder"),
    qaStep(emailContactCount >= 1, "Gmail recipient available", `${emailContactCount} opportunities have an email recipient`, "Add a recruiter, HR, careers, or hiring-team email before send/dry-run", "Open Contact Finder", "contact-finder"),
    qaStep(state.applications.length >= 1, "Application tracker linked", `${state.applications.length} applications tracked`, "Track at least one application", "Open Applications", "applications"),
    qaStep(pendingDrafts + approvedDrafts + sent.length >= 1, "Draft generation works", `${pendingDrafts} pending, ${approvedDrafts} approved, ${sent.length} sent`, "Generate a Gmail draft", "Open Drafts", "drafts"),
    qaStep(approvedDrafts + sent.length >= 1, "Human approval works", `${approvedDrafts} approved drafts, ${sent.length} sent`, "Approve one reviewed draft", "Open Drafts", "drafts"),
    qaStep(sendReadyDrafts + sent.length >= 1, "Approved draft is send-ready", `${sendReadyDrafts} approved drafts have recipient emails`, "Add contact email to an approved draft", "Open Drafts", "drafts"),
    qaStep(sent.length >= 1, "Send / dry-run works", `${sent.length} completed sent/dry-run messages`, "Run Send / Dry Run on an approved draft", "Open Gmail Outreach", "gmail-outreach"),
    qaStep(state.replies.length >= 1, "Reply classification works", `${state.replies.length} replies classified`, "Classify a pasted reply or sync Gmail replies", "Open Replies", "replies"),
    qaStep(followups.length >= 1 || state.drafts.some((draft) => /follow-up|follow up/i.test(`${draft.context_summary || ""} ${draft.body || ""}`)), "Follow-up flow visible", `${followups.length} opportunities currently need follow-up`, "Generate a follow-up draft after a sent item", "Open Follow-ups", "followups"),
    qaStep(state.auditEvents.length >= 5, "Audit trail records workflow", `${state.auditEvents.length} audit events saved`, "Complete more workflow steps", "Open Audit Logs", "audit-view"),
  ];

  const completed = qaSteps.filter((step) => step.done).length;
  const total = qaSteps.length;
  const coreReady = profileReady && dryRunEnabled && state.leads.length >= 3 && sent.length >= 1;
  const statusLabel = completed === total ? "passed" : coreReady ? "qa-ready" : "in-progress";

  elements.qaStatus.textContent = statusLabel;
  elements.qaStatus.classList.toggle("ok", coreReady);
  elements.qaStatus.classList.toggle("error", !coreReady);

  const summaryCards = [
    ["QA Progress", `${completed}/${total}`, "Checklist items complete", completed >= Math.ceil(total * 0.7)],
    ["Safety", dryRunEnabled ? "Dry Run" : "Live Send", "Live sending should stay off during QA", dryRunEnabled],
    ["Test Set", `${state.leads.length}/3`, "Minimum real opportunities for test pass", state.leads.length >= 3],
    ["Draft Review", `${pendingDrafts + approvedDrafts}`, "Drafts waiting for human decision", pendingDrafts + approvedDrafts > 0],
    ["Recipient Email", String(emailContactCount), "Needed before Gmail send/dry-run", emailContactCount > 0],
    ["Sent/Dry Run", String(sent.length), "Completed approved-send path", sent.length > 0],
    ["Replies", String(state.replies.length), "Reply classification coverage", state.replies.length > 0],
  ];

  elements.qaSummary.innerHTML = summaryCards.map(([label, value, detail, enabled]) => (
    settingCard(label, value, detail, enabled)
  )).join("");

  elements.qaChecklist.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Status</th>
          <th>QA Step</th>
          <th>Evidence</th>
          <th>Target</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        ${qaSteps.map((step) => `
          <tr>
            <td>${badge(step.done ? "pass" : "needed")}</td>
            <td class="application-job-cell">
              <strong>${escapeHtml(step.label)}</strong>
            </td>
            <td>${escapeHtml(step.evidence)}</td>
            <td>${escapeHtml(step.target)}</td>
            <td class="action-cell">
              <button class="secondary" type="button" data-qa-target="${escapeHtml(step.sectionTarget)}">${escapeHtml(step.actionLabel)}</button>
            </td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function renderProfileSettings() {
  const profile = state.profile;
  if (!profile || !elements.profileForm) return;
  setFieldValue(elements.profileForm, "owner_name", profile.owner_name);
  setFieldValue(elements.profileForm, "primary_email", profile.primary_email);
  setFieldValue(elements.profileForm, "outreach_email", profile.outreach_email);
  setFieldValue(elements.profileForm, "target_roles", (profile.target_roles || []).join("\n"));
  setFieldValue(elements.profileForm, "target_locations", (profile.target_locations || []).join("\n"));
  setFieldValue(elements.profileForm, "target_skills", (profile.target_skills || []).join("\n"));
  setFieldValue(elements.profileForm, "resume_summary", profile.resume_summary);
  setFieldValue(elements.profileForm, "linkedin_profile_url", profile.linkedin_profile_url);
  setFieldValue(elements.profileForm, "github_url", profile.github_url);
  setFieldValue(elements.profileForm, "portfolio_url", profile.portfolio_url);
  setFieldValue(elements.profileForm, "default_resume_version", profile.default_resume_version);
  renderProfileSummary();

  setTargetDefaultsForForm(elements.jobSearchForm);
  setTargetDefaultsForForm(elements.jobSourceDiscoveryForm);
  setTargetDefaultsForForm(elements.jobDiscoveryForm);
}

function setApiStatus(ok, label) {
  elements.apiStatus.textContent = label;
  elements.apiStatus.className = `status-pill ${ok ? "ok" : "error"}`;
}

function switchView(targetId) {
  const isAuditView = targetId === "audit-view";
  elements.workflowView.hidden = isAuditView;
  elements.auditView.hidden = !isAuditView;
  elements.viewTabs.forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.viewTarget === targetId);
  });
  elements.sectionTabs.forEach((tab) => {
    tab.classList.remove("active");
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function showWorkspaceSection(sectionName) {
  elements.workflowView.hidden = false;
  elements.auditView.hidden = true;
  elements.workspacePanels.forEach((panel) => {
    panel.hidden = panel.dataset.workspacePanel !== sectionName;
  });
  elements.sectionTabs.forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.sectionTarget === sectionName);
  });
  elements.viewTabs.forEach((tab) => {
    tab.classList.remove("active");
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function openOpportunityFromLeadId(leadId) {
  state.selectedLeadId = leadId;
  showWorkspaceSection("opportunities");
  renderLeads();
  renderOpportunityDetail();
  elements.opportunityDetail.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderLeads() {
  renderQueueSummary();
  const leads = filteredLeads();
  elements.leadCount.textContent = `${leads.length} / ${state.leads.length}`;
  if (!state.leads.length) {
    elements.leadsList.innerHTML = `<div class="empty">No opportunities yet.</div>`;
    return;
  }
  if (!leads.length) {
    elements.leadsList.innerHTML = `<div class="empty">No opportunities match the current filters.</div>`;
    return;
  }

  elements.leadsList.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Opportunity</th>
          <th>Stage</th>
          <th>Fit</th>
          <th>Contact</th>
          <th>Application / Draft</th>
          <th>Next Step</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        ${leads.map((lead) => {
          const latestDraft = latestDraftForLead(lead.id);
          const stage = displayOpportunityStage(lead);
          const sourceUrl = normalizeUrl(lead.opportunity_url || lead.linkedin_url || lead.contact_source_url);
          const trackedApplication = applicationForLead(lead.id);
          const contactStatus = lead.email
            ? lead.email
            : lead.contact_name || lead.contact_verification_status || "Contact search needed";
          const source = sourceUrl
            ? `<a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(sourceLabel(lead))}</a>`
            : `<span>${escapeHtml(sourceLabel(lead))}</span>`;
          const location = lead.opportunity_location ? `<span>${escapeHtml(lead.opportunity_location)}</span>` : "";
          const applicationDraft = [
            trackedApplication ? badge(trackedApplication.status) : "<span class=\"muted\">Not tracked</span>",
            latestDraft ? badge(latestDraft.status) : "<span class=\"muted\">No draft</span>",
          ].join(" ");
          return `
            <tr>
              <td class="opportunity-cell">
                <strong>${escapeHtml(lead.company || "-")}</strong>
                <span>${escapeHtml(lead.title || "-")}</span>
                <small>${source}${location ? ` - ${location}` : ""}</small>
              </td>
              <td>${badge(stage)}</td>
              <td>
                <strong>${lead.fit_score === null || lead.fit_score === undefined ? "-" : `${escapeHtml(lead.fit_score)}/100`}</strong>
                <span class="muted">${escapeHtml(lead.lead_grade || "No priority")}</span>
              </td>
              <td class="contact-summary">
                <span>${escapeHtml(contactStatus)}</span>
                ${lead.contact_confidence_score === null || lead.contact_confidence_score === undefined ? "" : `<small>${escapeHtml(lead.contact_confidence_score)}/100 confidence</small>`}
              </td>
              <td>${applicationDraft}</td>
              <td><button type="button" data-action="run-next-step" data-lead-id="${escapeHtml(lead.id)}">${escapeHtml(nextStepLabel(lead))}</button></td>
              <td class="action-cell">
                <button class="secondary" type="button" data-action="view-detail" data-lead-id="${escapeHtml(lead.id)}">Details</button>
                <button class="secondary" type="button" data-action="track-application" data-lead-id="${escapeHtml(lead.id)}" ${trackedApplication ? "disabled" : ""}>${trackedApplication ? "Tracked" : "Track"}</button>
                ${isLinkedInSource(lead) ? `<button class="secondary" type="button" data-action="linkedin-message" data-lead-id="${escapeHtml(lead.id)}">LinkedIn Msg</button>` : ""}
                <button class="danger" type="button" data-action="delete-lead" data-lead-id="${escapeHtml(lead.id)}">Delete</button>
              </td>
            </tr>
          `;
        }).join("")}
      </tbody>
    </table>
  `;
}

function renderOpportunityDetail() {
  if (!elements.opportunityDetail) return;
  const lead = state.leads.find((item) => item.id === state.selectedLeadId);
  if (!lead) {
    elements.opportunityDetail.innerHTML = `
      <div class="empty">Select Details on an opportunity to inspect the full workflow context.</div>
    `;
    return;
  }

  const application = applicationForLead(lead.id);
  const drafts = draftsForLead(lead.id);
  const replies = repliesForLead(lead.id);
  const auditEvents = auditEventsForLead(lead, application, drafts, replies);
  const sourceUrl = normalizeUrl(lead.opportunity_url || lead.linkedin_url || lead.contact_source_url);
  const contactUrl = normalizeUrl(lead.contact_source_url || lead.linkedin_url);

  elements.opportunityDetail.innerHTML = `
    <article class="detail-card">
      <div class="detail-header">
        <div>
          <p class="eyebrow">Opportunity Detail</p>
          <h3>${escapeHtml(lead.title || "Opportunity")} at ${escapeHtml(lead.company || "Unknown company")}</h3>
          <p class="muted compact-copy">${badge(displayOpportunityStage(lead))} ${lead.lead_grade ? badge(lead.lead_grade) : ""}</p>
        </div>
        <button class="secondary" type="button" data-action="close-detail">Close</button>
      </div>

      <div class="detail-grid">
        <section class="detail-section">
          <h4>Job</h4>
          <dl>
            <dt>Source</dt>
            <dd>${sourceUrl ? `<a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(sourceLabel(lead))}</a>` : escapeHtml(sourceLabel(lead))}</dd>
            <dt>Location</dt>
            <dd>${escapeHtml(lead.opportunity_location || "-")}</dd>
            <dt>Fit</dt>
            <dd>${lead.fit_score === null || lead.fit_score === undefined ? "-" : `${escapeHtml(lead.fit_score)}/100`}</dd>
            <dt>Skills</dt>
            <dd>${escapeHtml(lead.tech_stack || "-")}</dd>
          </dl>
        </section>

        <section class="detail-section">
          <h4>Contact</h4>
          <dl>
            <dt>Name</dt>
            <dd>${escapeHtml(displayContactName(lead))}</dd>
            <dt>Email / URL</dt>
            <dd>${contactCell(lead)}</dd>
            <dt>Type</dt>
            <dd>${escapeHtml(lead.contact_type || "-")}</dd>
            <dt>Confidence</dt>
            <dd>${lead.contact_confidence_score === null || lead.contact_confidence_score === undefined ? "-" : `${escapeHtml(lead.contact_confidence_score)}/100`}</dd>
            <dt>Evidence</dt>
            <dd>${contactUrl ? `<a href="${escapeHtml(contactUrl)}" target="_blank" rel="noopener noreferrer">Source</a>` : escapeHtml(lead.contact_verification_status || "-")}</dd>
          </dl>
        </section>

        <section class="detail-section">
          <h4>Application</h4>
          <dl>
            <dt>Status</dt>
            <dd>${application ? badge(application.status) : "Not tracked yet"}</dd>
            <dt>Applied</dt>
            <dd>${escapeHtml(application?.applied_date || "-")}</dd>
            <dt>Resume</dt>
            <dd>${escapeHtml(application?.resume_version || "-")}</dd>
            <dt>Thread</dt>
            <dd>${escapeHtml(application?.gmail_thread_id || "-")}</dd>
          </dl>
        </section>

        <section class="detail-section">
          <h4>Research</h4>
          <p>${escapeHtml(lead.company_summary || "Company research has not been run yet.")}</p>
          <p class="muted">${escapeHtml(lead.role_fit || lead.suggested_first_message || "No fit notes yet.")}</p>
        </section>
      </div>

      <div class="detail-columns">
        <section>
          <h4>Drafts</h4>
          ${drafts.length ? drafts.slice(0, 4).map((draft) => `
            <div class="detail-list-item">
              <strong>${escapeHtml(draft.subject)}</strong>
              <span>${badge(draft.status)} ${escapeHtml(draft.generated_by)} - ${formatDate(draft.created_at)}</span>
            </div>
          `).join("") : `<div class="empty">No drafts yet.</div>`}
        </section>
        <section>
          <h4>Replies</h4>
          ${replies.length ? replies.slice(0, 4).map((reply) => `
            <div class="detail-list-item">
              <strong>${badge(reply.intent)} ${escapeHtml(reply.from_email)}</strong>
              <span>${escapeHtml(truncate(reply.classification_reason || reply.body, 140))}</span>
            </div>
          `).join("") : `<div class="empty">No replies yet.</div>`}
        </section>
        <section>
          <h4>Audit Trail</h4>
          ${auditEvents.length ? auditEvents.slice(0, 6).map((event) => `
            <div class="detail-list-item">
              <strong>${escapeHtml(event.action)}</strong>
              <span>${escapeHtml(event.summary)} - ${formatDate(event.created_at)}</span>
            </div>
          `).join("") : `<div class="empty">No related audit events yet.</div>`}
        </section>
      </div>
    </article>
  `;
}

function renderApplicationSummary() {
  if (!elements.applicationSummary) return;
  const counts = countBy(state.applications, "status");
  const outreachReady = (counts.CONTACT_FOUND || 0)
    + (counts.OUTREACH_DRAFTED || 0)
    + (counts.OUTREACH_APPROVED || 0);
  const cards = [
    ["Saved", counts.SAVED || 0, "Targets not applied yet", "muted-card"],
    ["Applied", counts.APPLIED || 0, "Submitted applications", "success"],
    ["Outreach", outreachReady, "Contact or draft in progress", "warning"],
    ["Sent", counts.OUTREACH_SENT || 0, "Emails sent or dry-run sent", "muted-card"],
    ["Replies", (counts.REPLIED || 0) + (counts.INTERVIEW || 0), "Needs follow-through", "success"],
    ["Follow-up Due", counts.FOLLOW_UP_DUE || 0, "Needs next message", "warning"],
  ];

  elements.applicationSummary.innerHTML = cards.map(([label, value, detail, className]) => `
    <div class="summary-card ${className}">
      <strong>${value}</strong>
      <span>${escapeHtml(label)}</span>
      <small>${escapeHtml(detail)}</small>
    </div>
  `).join("");
}

function renderApplicationSourceFilter() {
  if (!elements.applicationSourceFilter) return;
  const currentValue = state.applicationFilters.source;
  const sources = Array.from(new Set(
    state.applications.map((application) => application.source).filter(Boolean),
  )).sort((a, b) => a.localeCompare(b));

  elements.applicationSourceFilter.innerHTML = `
    <option value="">All sources</option>
    ${sources.map((source) => (
      `<option value="${escapeHtml(source)}" ${source === currentValue ? "selected" : ""}>${escapeHtml(source)}</option>`
    )).join("")}
  `;
}

function renderApplications() {
  renderApplicationSummary();
  renderApplicationSourceFilter();
  const applications = filteredApplications();
  elements.applicationCount.textContent = `${applications.length} / ${state.applications.length}`;
  if (!state.applications.length) {
    elements.applicationsList.innerHTML = `
      <div class="empty">No applications tracked yet. Save one manually or use Track Application from Opportunities.</div>
    `;
    return;
  }
  if (!applications.length) {
    elements.applicationsList.innerHTML = `
      <div class="empty">No applications match the current filters.</div>
    `;
    return;
  }

  elements.applicationsList.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Job</th>
          <th>Status</th>
          <th>Applied</th>
          <th>Outreach</th>
          <th>Source</th>
          <th>Materials / Notes</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        ${applications.map((application) => {
          const jobUrl = applicationSourceUrl(application);
          const lead = applicationLead(application);
          const applied = application.applied_date || "-";
          const source = application.source || lead?.source || "Manual";
          const leadStage = lead ? displayOpportunityStage(lead) : "";
          const contactLabel = application.contact_found ? "Contact found" : "Contact needed";
          return `
            <tr>
              <td class="application-job-cell">
                <strong>${escapeHtml(application.company_name)}</strong>
                <span>${escapeHtml(application.job_title)}</span>
                <small>${escapeHtml(application.location || lead?.opportunity_location || "-")}</small>
              </td>
              <td>
                <select data-application-field="status" data-id="${escapeHtml(application.id)}">
                  ${applicationStatusOptions(application.status)}
                </select>
              </td>
              <td class="application-meta-cell">
                <span>${escapeHtml(applied)}</span>
                ${application.status !== "APPLIED" && application.status !== "OUTREACH_SENT"
                  ? `<button class="secondary compact-button" type="button" data-action="mark-application-applied" data-id="${escapeHtml(application.id)}">Mark Applied</button>`
                  : ""}
              </td>
              <td class="application-meta-cell">
                ${badge(contactLabel)}
                ${leadStage ? `<small>${escapeHtml(leadStage)}</small>` : ""}
                ${application.gmail_thread_id ? `<small>Thread: ${escapeHtml(application.gmail_thread_id)}</small>` : ""}
              </td>
              <td>${jobUrl ? `<a href="${escapeHtml(jobUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source)}</a>` : escapeHtml(source)}</td>
              <td class="application-notes-cell">
                <span>${escapeHtml(application.resume_version || "Resume not set")}</span>
                <small>${escapeHtml(application.cover_letter_version || "Cover letter not set")}</small>
                <p>${escapeHtml(truncate(application.notes || "-", 150))}</p>
              </td>
              <td class="action-cell">
                <button class="secondary" type="button" data-action="update-application" data-id="${escapeHtml(application.id)}">Update</button>
                ${application.lead_id ? `<button class="secondary" type="button" data-action="open-application-opportunity" data-lead-id="${escapeHtml(application.lead_id)}">Open Opportunity</button>` : ""}
                <button class="danger" type="button" data-action="delete-application" data-id="${escapeHtml(application.id)}">Delete</button>
              </td>
            </tr>
          `;
        }).join("")}
      </tbody>
    </table>
  `;
}

function renderCareerSources() {
  elements.careerSourceCount.textContent = state.careerSources.length;
  if (!state.careerSources.length) {
    elements.careerSourcesList.innerHTML = `
      <div class="empty">No saved company career sources yet. Add company career pages you want to check repeatedly.</div>
    `;
    return;
  }

  elements.careerSourcesList.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Company</th>
          <th>URL</th>
          <th>Type</th>
          <th>Active</th>
          <th>Last Scan</th>
          <th>Last Results</th>
          <th>Notes</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        ${state.careerSources.map((source) => `
          <tr>
            <td>${escapeHtml(source.company_name)}</td>
            <td><a href="${escapeHtml(source.careers_url)}" target="_blank" rel="noopener noreferrer">Career page</a></td>
            <td>${escapeHtml(source.source_type)}</td>
            <td>${source.active ? "Yes" : "No"}</td>
            <td>${source.last_scanned_at ? formatDate(source.last_scanned_at) : "-"}</td>
            <td>${source.last_error ? escapeHtml(source.last_error) : source.last_result_count ?? "-"}</td>
            <td class="message-preview">${escapeHtml(truncate(source.notes || "-"))}</td>
            <td class="action-cell">
              <button class="secondary" type="button" data-action="scan-career-source" data-id="${escapeHtml(source.id)}">Scan</button>
              <button class="secondary" type="button" data-action="toggle-career-source" data-id="${escapeHtml(source.id)}" data-active="${source.active ? "false" : "true"}">${source.active ? "Pause" : "Activate"}</button>
              <button class="danger" type="button" data-action="delete-career-source" data-id="${escapeHtml(source.id)}">Delete</button>
            </td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function renderContacts() {
  const contacts = state.leads.filter(hasUsableContact);
  elements.contactCount.textContent = contacts.length;
  if (!contacts.length) {
    elements.contactsList.innerHTML = `
      <div class="empty">No verified public contacts yet. Run Find Contact on discovered opportunities.</div>
    `;
    return;
  }

  elements.contactsList.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Contact</th>
          <th>Email / URL</th>
          <th>Company</th>
          <th>Role</th>
          <th>Type</th>
          <th>Confidence</th>
          <th>Verification</th>
          <th>Source</th>
        </tr>
      </thead>
      <tbody>
        ${contacts.map((lead) => {
          const sourceUrl = normalizeUrl(lead.contact_source_url || lead.linkedin_url || lead.opportunity_url);
          return `
            <tr>
              <td>${escapeHtml(displayContactName(lead))}</td>
              <td>${contactCell(lead)}</td>
              <td>${escapeHtml(lead.company || "-")}</td>
              <td>${escapeHtml(lead.contact_role || lead.title || "-")}</td>
              <td>${escapeHtml(lead.contact_type || "manual_contact")}</td>
              <td>${lead.contact_confidence_score === null || lead.contact_confidence_score === undefined ? "-" : `${escapeHtml(lead.contact_confidence_score)}/100`}</td>
              <td>${escapeHtml(lead.contact_verification_status || "manual_or_existing")}</td>
              <td>${sourceUrl ? `<a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">Source</a>` : "-"}</td>
            </tr>
          `;
        }).join("")}
      </tbody>
    </table>
  `;
}

function renderCompanyResearch() {
  const opportunities = state.leads.filter(isOpportunity);
  elements.companyResearchCount.textContent = opportunities.length;
  if (!opportunities.length) {
    elements.companyResearchList.innerHTML = `<div class="empty">No opportunities to research yet.</div>`;
    return;
  }

  elements.companyResearchList.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Company</th>
          <th>Role</th>
          <th>Stage</th>
          <th>Company Summary</th>
          <th>Required Skills</th>
          <th>Role Fit</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        ${opportunities.map((lead) => `
          <tr>
            <td>${escapeHtml(lead.company || "-")}</td>
            <td>${escapeHtml(lead.title || "-")}</td>
            <td>${escapeHtml(displayOpportunityStage(lead))}</td>
            <td class="message-preview">${escapeHtml(truncate(lead.company_summary || "Research not run yet."))}</td>
            <td>${escapeHtml(lead.tech_stack || "-")}</td>
            <td class="message-preview">${escapeHtml(truncate(lead.role_fit || lead.suggested_first_message || "-"))}</td>
            <td class="action-cell">
              <button class="secondary" type="button" data-action="analyze-fit" data-lead-id="${escapeHtml(lead.id)}">Analyze Fit</button>
              <button class="secondary" type="button" data-action="research-company" data-lead-id="${escapeHtml(lead.id)}">Research Company</button>
              ${isLinkedInSource(lead) ? `<button class="secondary" type="button" data-action="linkedin-message" data-lead-id="${escapeHtml(lead.id)}">Generate LinkedIn Message</button>` : ""}
              <button type="button" data-action="quick-draft" data-lead-id="${escapeHtml(lead.id)}">Generate Gmail Draft</button>
            </td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function renderDrafts() {
  const activeDrafts = state.drafts.filter((draft) => (
    draft.status === "pending_approval" || draft.status === "approved"
  ));

  elements.draftCount.textContent = activeDrafts.length;
  if (!activeDrafts.length) {
    elements.draftsList.innerHTML = `
      <div class="empty">
        No drafts need review right now. Rejected and sent drafts stay in Audit Events.
      </div>
    `;
    return;
  }

  elements.draftsList.innerHTML = activeDrafts.map((draft) => {
    const lead = state.leads.find((item) => item.id === draft.lead_id);
    const jobUrl = lead?.opportunity_url || lead?.linkedin_url;
    const contactUrl = lead?.contact_source_url && lead.contact_source_url !== jobUrl
      ? lead.contact_source_url
      : null;
    const sourceLinks = lead
      ? `
        <div class="draft-source-links">
          <span>${escapeHtml([lead.company, lead.title].filter(Boolean).join(" - ") || "Opportunity source")}</span>
          <div>
            ${jobUrl ? `<a class="secondary link-button" href="${escapeHtml(jobUrl)}" target="_blank" rel="noopener noreferrer">Open Job Post</a>` : ""}
            ${contactUrl ? `<a class="secondary link-button" href="${escapeHtml(contactUrl)}" target="_blank" rel="noopener noreferrer">Open Contact Source</a>` : ""}
          </div>
        </div>
      `
      : "";
    const leadSuggestedMessage = lead?.suggested_first_message
      ? `<details class="source-message"><summary>Original source note</summary><pre>${escapeHtml(lead.suggested_first_message)}</pre></details>`
      : "";
    const bodyContent = draft.status === "pending_approval"
      ? `
        <label>
          Subject
          <input data-draft-field="subject" data-id="${escapeHtml(draft.id)}" type="text" value="${escapeHtml(draft.subject)}">
        </label>
        <label>
          Body
          <textarea data-draft-field="body" data-id="${escapeHtml(draft.id)}" rows="8">${escapeHtml(draft.body)}</textarea>
        </label>
      `
      : `
        <h3>${escapeHtml(draft.subject)}</h3>
        <pre>${escapeHtml(draft.body)}</pre>
      `;
    let actions = `<p class="muted">No actions available for this status.</p>`;
    if (draft.status === "pending_approval") {
      actions = `
        <button class="secondary" type="button" data-action="save" data-id="${draft.id}">Save Edits</button>
        <button type="button" data-action="approve" data-id="${draft.id}">Approve</button>
        <button class="danger" type="button" data-action="reject" data-id="${draft.id}">Reject</button>
      `;
    }
    if (draft.status === "approved") {
      actions = lead?.email
        ? `<button class="warning" type="button" data-action="send" data-id="${draft.id}">Send / Dry Run</button>`
        : `
          <div class="missing-contact-panel">
            <strong>Needs contact email</strong>
            <span>Add a recruiter, HR, careers, or hiring-team email before Gmail send/dry-run. If you applied on the job page and no email is public, track it as an application instead.</span>
            <div class="inline-edit-row">
              <input data-contact-email-for="${escapeHtml(draft.id)}" type="email" placeholder="careers@company.com">
              <button class="secondary" type="button" data-action="save-contact-email" data-id="${escapeHtml(draft.id)}" data-lead-id="${escapeHtml(draft.lead_id)}">Save Email</button>
            </div>
            <button class="secondary" type="button" data-action="auto-find-email" data-id="${escapeHtml(draft.id)}" data-lead-id="${escapeHtml(draft.lead_id)}">Auto Find Email</button>
            <button class="secondary" type="button" data-action="mark-applied-no-email" data-id="${escapeHtml(draft.id)}" data-lead-id="${escapeHtml(draft.lead_id)}">Mark Applied / No Email Found</button>
          </div>
        `;
    }

    return `
      <article class="draft-card">
        <p class="muted">${lead ? escapeHtml(`${lead.first_name} ${lead.last_name || ""} - ${lead.email || lead.linkedin_url || "no email yet"}`) : escapeHtml(draft.lead_id)}</p>
        ${sourceLinks}
        <p>
          ${badge(draft.status)}
          <span class="badge">${escapeHtml(draft.generated_by)}</span>
          ${draft.qa_status ? badge(`QA: ${draft.qa_status}`) : ""}
        </p>
        ${leadSuggestedMessage}
        ${bodyContent}
        <p class="muted">${escapeHtml(draft.context_summary || "No context summary")}</p>
        <div class="card-actions">
          ${actions}
        </div>
      </article>
    `;
  }).join("");
}

function renderSentSummary() {
  if (!elements.sentSummary) return;
  const sent = sentDrafts();
  const dryRun = sent.filter((draft) => /dry/i.test(draft.sent_provider || "")).length;
  const liveSent = sent.length - dryRun;
  const withReplies = new Set(state.replies.map((reply) => reply.lead_id)).size;
  const waiting = sent.filter((draft) => !state.replies.some((reply) => reply.lead_id === draft.lead_id)).length;
  const cards = [
    ["Sent", sent.length, "Approved messages completed", "muted-card"],
    ["Dry Run", dryRun, "Local completion only", "warning"],
    ["Live Sent", liveSent, "Through Gmail when enabled", "success"],
    ["Replied", withReplies, "Opportunities with replies", "success"],
    ["Waiting", waiting, "No reply tracked yet", "warning"],
  ];

  elements.sentSummary.innerHTML = cards.map(([label, value, detail, className]) => `
    <div class="summary-card ${className}">
      <strong>${value}</strong>
      <span>${escapeHtml(label)}</span>
      <small>${escapeHtml(detail)}</small>
    </div>
  `).join("");
}

function renderReplySummary() {
  if (!elements.replySummary) return;
  const counts = countBy(state.replies, "intent");
  const cards = [
    ["Replies", state.replies.length, "Tracked responses", "muted-card"],
    ["Interested", (counts.interested || 0) + (counts.interview || 0), "Positive next step", "success"],
    ["Resume", counts.resume_requested || 0, "Resume requested", "success"],
    ["Not Interested", counts.not_interested || 0, "Closed or nurture later", "muted-card"],
    ["Unclear", (counts.unclear || 0) + (counts.out_of_office || 0), "Needs review", "warning"],
    ["Bounce", counts.bounce || 0, "Contact issue", "warning"],
  ];

  elements.replySummary.innerHTML = cards.map(([label, value, detail, className]) => `
    <div class="summary-card ${className}">
      <strong>${value}</strong>
      <span>${escapeHtml(label)}</span>
      <small>${escapeHtml(detail)}</small>
    </div>
  `).join("");
}

function renderFollowupSummary(followups) {
  if (!elements.followupSummary) return;
  const sent = sentDrafts();
  const repliedLeadIds = new Set(state.replies.map((reply) => reply.lead_id));
  const waiting = sent.filter((draft) => !repliedLeadIds.has(draft.lead_id)).length;
  const activeDrafts = state.drafts.filter((draft) => (
    draft.status === "pending_approval" || draft.status === "approved"
  )).length;
  const cards = [
    ["Needs Follow-up", followups.length, "Sent with no reply or marked due", "warning"],
    ["Waiting", waiting, "Sent outreach without reply", "muted-card"],
    ["Drafts Open", activeDrafts, "Review before sending", "success"],
    ["Replies", state.replies.length, "Already responded", "success"],
  ];

  elements.followupSummary.innerHTML = cards.map(([label, value, detail, className]) => `
    <div class="summary-card ${className}">
      <strong>${value}</strong>
      <span>${escapeHtml(label)}</span>
      <small>${escapeHtml(detail)}</small>
    </div>
  `).join("");
}

function renderReplies() {
  renderReplySummary();
  const replies = state.replies.slice().sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  elements.replyCount.textContent = replies.length;
  if (!replies.length) {
    elements.repliesList.innerHTML = `<div class="empty">No replies yet. Use Sync Gmail Replies or classify a pasted response after a sent draft exists.</div>`;
    return;
  }

  elements.repliesList.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Opportunity</th>
          <th>Reply</th>
          <th>Intent</th>
          <th>Thread</th>
          <th>Created</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        ${replies.map((reply) => {
          const lead = state.leads.find((item) => item.id === reply.lead_id);
          const application = applicationForLead(reply.lead_id);
          const title = application
            ? `${application.company_name} - ${application.job_title}`
            : lead
              ? `${lead.company || "Opportunity"} - ${lead.title || "Role"}`
              : "-";
          return `
            <tr>
              <td class="application-job-cell">
                <strong>${escapeHtml(title)}</strong>
                <small>${escapeHtml(lead?.opportunity_location || application?.location || "-")}</small>
              </td>
              <td class="application-notes-cell">
                <span>${escapeHtml(reply.from_email)}</span>
                <p>${escapeHtml(truncate(reply.body, 160))}</p>
              </td>
              <td class="application-notes-cell">
                ${badge(reply.intent)}
                <small>${escapeHtml(reply.classification_reason || "-")}</small>
              </td>
              <td>${escapeHtml(reply.provider_thread_id || reply.provider_message_id || "-")}</td>
              <td>${formatDate(reply.created_at)}</td>
              <td class="action-cell">
                ${reply.lead_id ? `<button class="secondary" type="button" data-action="open-reply-opportunity" data-lead-id="${escapeHtml(reply.lead_id)}">Open Opportunity</button>` : ""}
              </td>
            </tr>
          `;
        }).join("")}
      </tbody>
    </table>
  `;
}

function renderSentEmails() {
  const sent = sentDrafts();
  const approvedDrafts = state.drafts.filter((draft) => draft.status === "approved");
  const sendReadyDrafts = approvedDrafts.filter((draft) => {
    const lead = state.leads.find((item) => item.id === draft.lead_id);
    return Boolean(lead?.email);
  });
  const blockedDrafts = approvedDrafts.filter((draft) => {
    const lead = state.leads.find((item) => item.id === draft.lead_id);
    return !lead?.email;
  });
  renderSentSummary();
  elements.sentCount.textContent = sent.length;
  const sendReadyPanel = `
    <div class="table-section">
      <div class="table-section-header">
        <div>
          <h3>Approved Drafts Ready For Gmail</h3>
          <p class="muted compact-copy">Run dry-run sending here. Live Gmail send only happens when LIVE_SEND is enabled.</p>
        </div>
        <span class="count">${sendReadyDrafts.length}</span>
      </div>
      ${sendReadyDrafts.length ? `
        <table>
          <thead>
            <tr>
              <th>Opportunity</th>
              <th>Recipient</th>
              <th>Subject</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            ${sendReadyDrafts.map((draft) => {
              const lead = state.leads.find((item) => item.id === draft.lead_id);
              return `
                <tr>
                  <td class="application-job-cell">
                    <strong>${escapeHtml(lead?.company || "Unknown company")}</strong>
                    <span>${escapeHtml(lead?.title || "Opportunity")}</span>
                    <small>${escapeHtml(lead?.opportunity_location || "-")}</small>
                  </td>
                  <td>${lead ? contactCell(lead) : escapeHtml(draft.lead_id)}</td>
                  <td>${escapeHtml(draft.subject)}</td>
                  <td class="action-cell">
                    <button class="warning" type="button" data-action="send-approved-draft" data-id="${escapeHtml(draft.id)}">Send / Dry Run</button>
                    ${lead ? `<button class="secondary" type="button" data-action="open-sent-opportunity" data-lead-id="${escapeHtml(lead.id)}">Open Opportunity</button>` : ""}
                  </td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      ` : `<div class="empty">No approved drafts have recipient emails yet.</div>`}
    </div>
  `;
  const blockedPanel = blockedDrafts.length ? `
    <div class="table-section">
      <div class="table-section-header">
        <div>
          <h3>Approved But Missing Recipient</h3>
          <p class="muted compact-copy">Run email discovery or track these as application-only if no public email exists.</p>
        </div>
        <span class="count">${blockedDrafts.length}</span>
      </div>
      <table>
        <thead>
          <tr>
            <th>Opportunity</th>
            <th>Best Source</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          ${blockedDrafts.map((draft) => {
            const lead = state.leads.find((item) => item.id === draft.lead_id);
            const sourceUrl = normalizeUrl(lead?.contact_source_url || lead?.opportunity_url || lead?.linkedin_url);
            return `
              <tr>
                <td class="application-job-cell">
                  <strong>${escapeHtml(lead?.company || "Unknown company")}</strong>
                  <span>${escapeHtml(lead?.title || "Opportunity")}</span>
                  <small>${escapeHtml(lead?.contact_verification_status || "email needed")}</small>
                </td>
                <td>${sourceUrl ? `<a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">Open source</a>` : "-"}</td>
                <td class="action-cell">
                  ${lead ? `<button class="secondary" type="button" data-action="find-contact-from-gmail" data-lead-id="${escapeHtml(lead.id)}">Auto Find Email</button>` : ""}
                  ${lead ? `<button class="secondary" type="button" data-action="open-sent-opportunity" data-lead-id="${escapeHtml(lead.id)}">Open Opportunity</button>` : ""}
                </td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    </div>
  ` : "";

  const sentHistory = sent.length ? `
    <div class="table-section">
      <div class="table-section-header">
        <div>
          <h3>Sent / Dry-Run History</h3>
          <p class="muted compact-copy">Messages here can be matched with synced or pasted replies.</p>
        </div>
        <span class="count">${sent.length}</span>
      </div>
    <table>
      <thead>
        <tr>
          <th>Opportunity</th>
          <th>Contact</th>
          <th>Subject</th>
          <th>Delivery</th>
          <th>Sent At</th>
          <th>Reply</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        ${sent.map((draft) => {
          const lead = state.leads.find((item) => item.id === draft.lead_id);
          const replies = repliesForLead(draft.lead_id);
          const provider = draft.sent_provider || "dry-run/local";
          return `
            <tr>
              <td class="application-job-cell">
                <strong>${escapeHtml(lead?.company || "Unknown company")}</strong>
                <span>${escapeHtml(lead?.title || "Opportunity")}</span>
                <small>${escapeHtml(lead?.opportunity_location || "-")}</small>
              </td>
              <td>${lead ? contactCell(lead) : escapeHtml(draft.lead_id)}</td>
              <td class="application-notes-cell">
                <span>${escapeHtml(draft.subject)}</span>
                <small>${escapeHtml(draft.sent_thread_id || draft.sent_message_id || "-")}</small>
              </td>
              <td>${badge(provider)}</td>
              <td>${draft.sent_at ? formatDate(draft.sent_at) : "-"}</td>
              <td>${replies.length ? badge(replies[0].intent) : badge("waiting")}</td>
              <td class="action-cell">
                <button class="secondary" type="button" data-action="classify-sent-reply" data-id="${escapeHtml(draft.id)}" data-email="${escapeHtml(lead?.email || "")}">Classify Reply</button>
                ${lead ? `<button class="secondary" type="button" data-action="open-sent-opportunity" data-lead-id="${escapeHtml(lead.id)}">Open Opportunity</button>` : ""}
              </td>
            </tr>
          `;
        }).join("")}
      </tbody>
    </table>
    </div>
  ` : `<div class="empty">No sent or dry-run completed emails yet.</div>`;

  elements.sentList.innerHTML = `${sendReadyPanel}${blockedPanel}${sentHistory}`;
}

function renderFollowups() {
  const followups = followupLeads();
  renderFollowupSummary(followups);
  elements.followupCount.textContent = followups.length;
  if (!followups.length) {
    const sent = sentDrafts();
    const repliedLeadIds = new Set(state.replies.map((reply) => reply.lead_id));
    let message = "No follow-ups due yet. Once a sent message has no tracked reply, it will appear here.";
    if (!sent.length) {
      message = "No sent or dry-run messages yet. Approve a draft, add a real recipient email, then run Send / Dry Run before generating follow-ups.";
    } else if (sent.every((draft) => repliedLeadIds.has(draft.lead_id))) {
      message = "All sent messages already have tracked replies, so no follow-up is needed.";
    }
    elements.followupList.innerHTML = `<div class="empty">${escapeHtml(message)}</div>`;
    return;
  }

  elements.followupList.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Opportunity</th>
          <th>Contact</th>
          <th>Last Sent</th>
          <th>Stage</th>
          <th>Suggested Action</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        ${followups.map((lead) => {
          const sentDraft = sentDrafts().find((draft) => draft.lead_id === lead.id);
          return `
            <tr>
              <td class="application-job-cell">
                <strong>${escapeHtml(lead.company || "-")}</strong>
                <span>${escapeHtml(lead.title || "-")}</span>
                <small>${escapeHtml(lead.opportunity_location || "-")}</small>
              </td>
              <td>${contactCell(lead)}</td>
              <td>${sentDraft ? formatDate(sentDraft.sent_at || sentDraft.created_at) : "-"}</td>
              <td>${badge(displayOpportunityStage(lead))}</td>
              <td class="application-notes-cell">
                <span>${sentDraft ? "Generate a follow-up draft" : "Send the first approved draft"}</span>
                <small>Human approval remains required before any email goes out.</small>
              </td>
              <td class="action-cell">
                <button class="secondary" type="button" data-action="open-followup-opportunity" data-lead-id="${escapeHtml(lead.id)}">Open Opportunity</button>
              </td>
            </tr>
          `;
        }).join("")}
      </tbody>
    </table>
  `;
}

function renderAuditEvents() {
  const visibleEvents = state.auditEvents.slice().reverse().slice(0, 200);
  elements.auditCount.textContent = state.auditEvents.length;
  elements.auditTabCount.textContent = state.auditEvents.length;
  if (!state.auditEvents.length) {
    elements.auditList.innerHTML = `<div class="empty">No audit events yet.</div>`;
    elements.auditShownCount.textContent = "No audit activity yet";
    return;
  }

  elements.auditShownCount.textContent = `Showing latest ${visibleEvents.length} of ${state.auditEvents.length}`;
  elements.auditList.innerHTML = visibleEvents.map((event) => `
    <div class="event">
      <strong>${escapeHtml(event.action)}</strong>
      <span>${escapeHtml(event.summary)}</span>
      <div class="muted">${escapeHtml(event.entity_type)} - ${formatDate(event.created_at)}</div>
    </div>
  `).join("");
}

function updateSelects() {
  const leadSelect = elements.draftForm.elements.lead_id;
  leadSelect.innerHTML = state.leads.map((lead) => (
    `<option value="${escapeHtml(lead.id)}">${escapeHtml(`${lead.company || displayContactName(lead)} - ${lead.title || "Opportunity"} - ${lead.email || lead.contact_source_url || lead.linkedin_url || "contact search needed"}`)}</option>`
  )).join("");

  const campaignSelect = elements.draftForm.elements.campaign_id;
  campaignSelect.innerHTML = `<option value="">No campaign</option>${state.campaigns.map((campaign) => (
    `<option value="${escapeHtml(campaign.id)}">${escapeHtml(campaign.name)}</option>`
  )).join("")}`;

  const sentDrafts = state.drafts.filter((draft) => draft.status === "sent");
  const replyDraftSelect = elements.replyForm.elements.draft_id;
  replyDraftSelect.innerHTML = sentDrafts.map((draft) => (
    `<option value="${escapeHtml(draft.id)}">${escapeHtml(draft.subject)}</option>`
  )).join("");
}

function renderAll() {
  renderDashboardOverview();
  renderReadiness();
  renderDryRunQa();
  renderProfileSettings();
  renderSettingsOverview();
  syncJobSourceToggles();
  renderLeads();
  renderOpportunityDetail();
  renderApplications();
  renderCareerSources();
  renderCompanyResearch();
  renderContacts();
  renderDrafts();
  renderSentEmails();
  renderReplies();
  renderFollowups();
  renderAuditEvents();
  updateSelects();
}

async function loadAll() {
  try {
    await api("/api/v1/system/database");
    setApiStatus(true, "API connected");

    const [readiness, profile, leads, applications, careerSources, campaigns, drafts, replies, auditEvents] = await Promise.all([
      api("/api/v1/system/readiness"),
      api("/api/v1/profile"),
      api("/api/v1/leads"),
      api("/api/v1/applications"),
      api("/api/v1/career-sources"),
      api("/api/v1/campaigns"),
      api("/api/v1/drafts"),
      api("/api/v1/replies"),
      api("/api/v1/audit-events"),
    ]);

    state.readiness = readiness;
    state.profile = profile;
    state.leads = leads;
    state.applications = applications;
    state.careerSources = careerSources;
    state.campaigns = campaigns;
    state.drafts = drafts;
    state.replies = replies;
    state.auditEvents = auditEvents;
    if (state.selectedLeadId && !state.leads.some((lead) => lead.id === state.selectedLeadId)) {
      state.selectedLeadId = "";
    }
    renderAll();
  } catch (error) {
    setApiStatus(false, "API unavailable");
    showToast(error.message);
  }
}

elements.refreshAll.addEventListener("click", async (event) => {
  try {
    setApiStatus(true, "Refreshing local data");
    await withButtonState(event.currentTarget, "Refreshing...", "Refreshed", loadAll);
    setApiStatus(true, "Local data refreshed");
  } catch (error) {
    setApiStatus(false, "Refresh failed");
    showToast(error.message);
  }
});

elements.settingsRefresh.addEventListener("click", async (event) => {
  try {
    await withButtonState(event.currentTarget, "Refreshing...", "Refreshed", loadAll);
    showToast("Readiness refreshed");
  } catch (error) {
    showToast(error.message);
  }
});

elements.connectGmail.addEventListener("click", () => {
  window.open(`${API_BASE_URL}/auth/google/start`, "_blank", "noopener,noreferrer");
});

elements.viewTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    switchView(tab.dataset.viewTarget);
  });
});

elements.sectionTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    showWorkspaceSection(tab.dataset.sectionTarget);
  });
});

elements.auditBack.addEventListener("click", () => {
  showWorkspaceSection("dashboard");
});

if (elements.qaActions) {
  elements.qaActions.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-qa-target]");
    if (!button) return;
    if (button.dataset.qaTarget === "audit-view") {
      switchView("audit-view");
      return;
    }
    showWorkspaceSection(button.dataset.qaTarget);
  });
}

if (elements.qaChecklist) {
  elements.qaChecklist.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-qa-target]");
    if (!button) return;
    if (button.dataset.qaTarget === "audit-view") {
      switchView("audit-view");
      return;
    }
    showWorkspaceSection(button.dataset.qaTarget);
  });
}

elements.leadOutreachFilter.addEventListener("change", (event) => {
  state.leadFilters.outreach = event.currentTarget.value;
  renderLeads();
});

elements.leadGradeFilter.addEventListener("change", (event) => {
  state.leadFilters.grade = event.currentTarget.value;
  renderLeads();
});

elements.leadSearch.addEventListener("input", (event) => {
  state.leadFilters.search = event.currentTarget.value.trim();
  renderLeads();
});

elements.clearLeadFilters.addEventListener("click", () => {
  state.leadFilters.outreach = "";
  state.leadFilters.grade = "";
  state.leadFilters.search = "";
  elements.leadOutreachFilter.value = "";
  elements.leadGradeFilter.value = "";
  elements.leadSearch.value = "";
  renderLeads();
});

elements.applicationStatusFilter.addEventListener("change", (event) => {
  state.applicationFilters.status = event.currentTarget.value;
  renderApplications();
});

elements.applicationSourceFilter.addEventListener("change", (event) => {
  state.applicationFilters.source = event.currentTarget.value;
  renderApplications();
});

elements.applicationSearch.addEventListener("input", (event) => {
  state.applicationFilters.search = event.currentTarget.value.trim();
  renderApplications();
});

elements.clearApplicationFilters.addEventListener("click", () => {
  state.applicationFilters.status = "";
  state.applicationFilters.source = "";
  state.applicationFilters.search = "";
  elements.applicationStatusFilter.value = "";
  elements.applicationSourceFilter.value = "";
  elements.applicationSearch.value = "";
  renderApplications();
});

elements.runPipelineBatch.addEventListener("click", async (event) => {
  try {
    const limit = Number(elements.pipelineBatchLimit.value || 5);
    const result = await withButtonState(event.currentTarget, "Running...", "Batch Complete", async () => {
      return api("/api/v1/pipeline/run-batch", {
        method: "POST",
        body: JSON.stringify({
          stages: ["DISCOVERED", "ANALYZED", "COMPANY_RESEARCHED"],
          limit,
          allow_draft_generation: false,
        }),
      });
    });
    showToast(`Pipeline batch: ${result.advanced} advanced, ${result.skipped} skipped, ${result.scanned} scanned`);
    await loadAll();
  } catch (error) {
    showToast(error.message);
  }
});

elements.leadsList.addEventListener("click", async (event) => {
  const button = event.target.closest("button");
  if (!button) return;

  if (button.dataset.action === "view-detail") {
    state.selectedLeadId = button.dataset.leadId;
    renderOpportunityDetail();
    elements.opportunityDetail.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }

  if (button.dataset.action === "close-detail") {
    state.selectedLeadId = "";
    renderOpportunityDetail();
    return;
  }

  if (button.dataset.action === "run-next-step") {
    try {
      const result = await withButtonState(button, "Running...", "Updated", async () => {
        return api(`/api/v1/leads/${button.dataset.leadId}/run-next-step`, {
          method: "POST",
        });
      });
      showToast(result.message || `Pipeline action completed: ${result.action}`);
      await loadAll();
      if (result.draft || result.action === "human_review_required") {
        showWorkspaceSection("drafts");
      }
    } catch (error) {
      showToast(error.message);
    }
    return;
  }

  if (button.dataset.action === "delete-lead") {
    const row = button.closest("tr");
    const label = row?.querySelector("td")?.textContent?.trim() || "this contact";
    if (!window.confirm(`Delete ${label} and any related drafts/replies?`)) return;
    try {
      await withButtonState(button, "Deleting...", "Deleted", async () => {
        await api(`/api/v1/leads/${button.dataset.leadId}`, {
          method: "DELETE",
        });
      });
      showToast("Contact deleted");
      await loadAll();
    } catch (error) {
      showToast(error.message);
    }
    return;
  }

  if (button.dataset.action === "research-company") {
    try {
      await withButtonState(button, "Researching...", "Researched", async () => {
        await api(`/api/v1/leads/${button.dataset.leadId}/research-company`, {
          method: "POST",
        });
      });
      showToast("Company research updated");
      await loadAll();
    } catch (error) {
      showToast(error.message);
    }
    return;
  }

  if (button.dataset.action === "analyze-fit") {
    try {
      const result = await withButtonState(button, "Analyzing...", "Analyzed", async () => {
        return api(`/api/v1/leads/${button.dataset.leadId}/analyze-fit`, {
          method: "POST",
        });
      });
      showToast(`Fit analyzed: ${result.fit_score}/100`);
      await loadAll();
    } catch (error) {
      showToast(error.message);
    }
    return;
  }

  if (button.dataset.action === "find-contact") {
    try {
      const result = await withButtonState(button, "Searching...", "Contact Checked", async () => {
        return api(`/api/v1/leads/${button.dataset.leadId}/find-contact`, {
          method: "POST",
        });
      });
      const contactText = result.contact_found
        ? `Contact found: ${result.contact_email || result.source_url || result.verification_status}`
        : "No public contact found; fallback source saved";
      showToast(`${contactText} (${result.confidence_score}/100)`);
      await loadAll();
    } catch (error) {
      showToast(error.message);
    }
    return;
  }

  if (button.dataset.action === "linkedin-message") {
    try {
      const result = await withButtonState(button, "Generating...", "Message Ready", async () => {
        return api(`/api/v1/leads/${button.dataset.leadId}/linkedin-connection-message`, {
          method: "POST",
        });
      });
      window.prompt("Manual LinkedIn connection message. The app will not send it.", result.message);
      showToast(`LinkedIn message generated (${result.character_count}/${result.max_character_count})`);
      await loadAll();
    } catch (error) {
      showToast(error.message);
    }
    return;
  }

  if (button.dataset.action === "track-application") {
    try {
      const application = await withButtonState(button, "Tracking...", "Tracked", async () => {
        return api(`/api/v1/leads/${button.dataset.leadId}/track-application`, {
          method: "POST",
        });
      });
      showToast(`Application tracked: ${application.job_title} at ${application.company_name}`);
      await loadAll();
      showWorkspaceSection("applications");
    } catch (error) {
      showToast(error.message);
    }
    return;
  }

  if (button.dataset.action !== "quick-draft") return;

  try {
    await withButtonState(button, "Drafting...", "Draft Created", async () => {
      await api("/api/v1/drafts/generate", {
        method: "POST",
        body: JSON.stringify({
          lead_id: button.dataset.leadId,
          call_to_action: "Open to a 15-minute conversation?",
          extra_context: "Use the opportunity research, contact finder result, and source URL. Keep the tone warm, concise, career-focused, and human-approved.",
        }),
      });
    });
    showToast("Draft created from opportunity and contact context");
    await loadAll();
  } catch (error) {
    showToast(error.message);
  }
});

elements.opportunityDetail.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button || button.dataset.action !== "close-detail") return;
  state.selectedLeadId = "";
  renderOpportunityDetail();
});

elements.applicationForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button[type='submit']");
  try {
    const payload = applicationPayloadFromForm(form);
    await withButtonState(button, "Saving...", "Saved", async () => {
      await api("/api/v1/applications", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    });
    showToast("Application saved");
    form.reset();
    await loadAll();
  } catch (error) {
    showToast(error.message);
  }
});

elements.profileForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button[type='submit']");
  try {
    const profile = await withButtonState(button, "Saving...", "Saved", async () => {
      return api("/api/v1/profile", {
        method: "PUT",
        body: JSON.stringify(profilePayloadFromForm(event.currentTarget)),
      });
    });
    state.profile = profile;
    renderProfileSettings();
    showToast("Profile settings saved");
    await loadAll();
  } catch (error) {
    showToast(error.message);
  }
});

elements.careerSourceForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button[type='submit']");
  try {
    const source = await withButtonState(button, "Saving...", "Saved", async () => {
      return api("/api/v1/career-sources", {
        method: "POST",
        body: JSON.stringify(careerSourcePayloadFromForm(form)),
      });
    });
    showToast(`Career source saved: ${source.company_name}`);
    form.reset();
    await loadAll();
  } catch (error) {
    showToast(error.message);
  }
});

elements.scanCareerSources.addEventListener("click", async (event) => {
  try {
    const result = await withButtonState(event.currentTarget, "Scanning...", "Scan Complete", async () => {
      return api("/api/v1/career-sources/scan", {
        method: "POST",
        body: JSON.stringify(careerSourceScanPayload()),
      });
    });
    showToast(`Saved sources: ${result.discovered} found, ${result.imported} imported, ${result.skipped} skipped`);
    await loadAll();
    showWorkspaceSection("opportunities");
  } catch (error) {
    showToast(error.message);
  }
});

elements.careerSourcesList.addEventListener("click", async (event) => {
  const button = event.target.closest("button");
  if (!button) return;

  if (button.dataset.action === "scan-career-source") {
    try {
      const result = await withButtonState(button, "Scanning...", "Scanned", async () => {
        return api("/api/v1/career-sources/scan", {
          method: "POST",
          body: JSON.stringify(careerSourceScanPayload([button.dataset.id])),
        });
      });
      showToast(`Career source scan: ${result.discovered} found, ${result.imported} imported`);
      await loadAll();
      showWorkspaceSection("opportunities");
    } catch (error) {
      showToast(error.message);
    }
    return;
  }

  if (button.dataset.action === "toggle-career-source") {
    try {
      await withButtonState(button, "Saving...", "Updated", async () => {
        await api(`/api/v1/career-sources/${button.dataset.id}`, {
          method: "PATCH",
          body: JSON.stringify({ active: button.dataset.active === "true" }),
        });
      });
      showToast("Career source updated");
      await loadAll();
    } catch (error) {
      showToast(error.message);
    }
    return;
  }

  if (button.dataset.action !== "delete-career-source") return;
  if (!window.confirm("Delete this saved career source?")) return;
  try {
    await withButtonState(button, "Deleting...", "Deleted", async () => {
      await api(`/api/v1/career-sources/${button.dataset.id}`, {
        method: "DELETE",
      });
    });
    showToast("Career source deleted");
    await loadAll();
  } catch (error) {
    showToast(error.message);
  }
});

elements.applicationsList.addEventListener("click", async (event) => {
  const button = event.target.closest("button");
  if (!button) return;

  if (button.dataset.action === "open-application-opportunity") {
    state.selectedLeadId = button.dataset.leadId;
    showWorkspaceSection("opportunities");
    renderLeads();
    renderOpportunityDetail();
    elements.opportunityDetail.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }

  if (button.dataset.action === "mark-application-applied") {
    const application = state.applications.find((item) => item.id === button.dataset.id);
    try {
      const updated = await withButtonState(button, "Saving...", "Applied", async () => {
        return api(`/api/v1/applications/${button.dataset.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            status: "APPLIED",
            applied_date: application?.applied_date || todayDateString(),
          }),
        });
      });
      showToast(`Application status updated to ${updated.status}`);
      await loadAll();
    } catch (error) {
      showToast(error.message);
    }
    return;
  }

  if (button.dataset.action === "delete-application") {
    if (!window.confirm("Delete this tracked application?")) return;
    try {
      await withButtonState(button, "Deleting...", "Deleted", async () => {
        await api(`/api/v1/applications/${button.dataset.id}`, {
          method: "DELETE",
        });
      });
      showToast("Application deleted");
      await loadAll();
    } catch (error) {
      showToast(error.message);
    }
    return;
  }

  if (button.dataset.action !== "update-application") return;
  const row = button.closest("tr");
  const statusField = row.querySelector(`[data-application-field="status"][data-id="${CSS.escape(button.dataset.id)}"]`);
  try {
    const updated = await withButtonState(button, "Updating...", "Updated", async () => {
      return api(`/api/v1/applications/${button.dataset.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: statusField.value }),
      });
    });
    showToast(`Application status updated to ${updated.status}`);
    await loadAll();
  } catch (error) {
    showToast(error.message);
  }
});

elements.companyResearchList.addEventListener("click", async (event) => {
  const button = event.target.closest("button");
  if (!button) return;

  if (button.dataset.action === "research-company") {
    try {
      await withButtonState(button, "Researching...", "Researched", async () => {
        await api(`/api/v1/leads/${button.dataset.leadId}/research-company`, {
          method: "POST",
        });
      });
      showToast("Company research updated");
      await loadAll();
    } catch (error) {
      showToast(error.message);
    }
    return;
  }

  if (button.dataset.action === "analyze-fit") {
    try {
      const result = await withButtonState(button, "Analyzing...", "Analyzed", async () => {
        return api(`/api/v1/leads/${button.dataset.leadId}/analyze-fit`, {
          method: "POST",
        });
      });
      showToast(`Fit analyzed: ${result.fit_score}/100`);
      await loadAll();
    } catch (error) {
      showToast(error.message);
    }
    return;
  }

  if (button.dataset.action === "linkedin-message") {
    try {
      const result = await withButtonState(button, "Generating...", "Message Ready", async () => {
        return api(`/api/v1/leads/${button.dataset.leadId}/linkedin-connection-message`, {
          method: "POST",
        });
      });
      window.prompt("Manual LinkedIn connection message. The app will not send it.", result.message);
      showToast(`LinkedIn message generated (${result.character_count}/${result.max_character_count})`);
      await loadAll();
    } catch (error) {
      showToast(error.message);
    }
    return;
  }

  if (button.dataset.action !== "quick-draft") return;
  try {
    await withButtonState(button, "Drafting...", "Draft Created", async () => {
      await api("/api/v1/drafts/generate", {
        method: "POST",
        body: JSON.stringify({
          lead_id: button.dataset.leadId,
          call_to_action: "Open to a 15-minute conversation?",
          extra_context: "Use the analyzed opportunity, company research, and tracked source URL. Keep it concise and human-approved.",
        }),
      });
    });
    showToast("Draft created from company research");
    await loadAll();
  } catch (error) {
    showToast(error.message);
  }
});

elements.leadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button[type='submit']");
  try {
    await withButtonState(button, "Creating...", "Contact Created", async () => {
      await api("/api/v1/leads", {
        method: "POST",
        body: JSON.stringify(removeEmptyValues(formToObject(form))),
      });
    });
    showToast("Contact created");
    await loadAll();
  } catch (error) {
    showToast(error.message);
  }
});

elements.linkedinImportForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button[type='submit']");
  try {
    const opportunity = sourceOpportunityFromForm(form);
    const result = await withButtonState(button, "Importing...", "Imported", async () => {
      return api("/api/v1/source-trackers/linkedin/import", {
        method: "POST",
        body: JSON.stringify(sourceTrackerPayload(opportunity)),
      });
    });
    showToast(`LinkedIn tracker: ${result.imported} imported, ${result.skipped} skipped`);
    form.reset();
    await loadAll();
    showWorkspaceSection("opportunities");
  } catch (error) {
    showToast(error.message);
  }
});

elements.indeedImportForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button[type='submit']");
  try {
    const opportunity = sourceOpportunityFromForm(form);
    const result = await withButtonState(button, "Importing...", "Imported", async () => {
      return api("/api/v1/source-trackers/indeed/import", {
        method: "POST",
        body: JSON.stringify(sourceTrackerPayload(opportunity)),
      });
    });
    showToast(`Indeed tracker: ${result.imported} imported, ${result.skipped} skipped`);
    form.reset();
    await loadAll();
    showWorkspaceSection("opportunities");
  } catch (error) {
    showToast(error.message);
  }
});

elements.indeedCsvForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button[type='submit']");
  try {
    const csvRows = form.elements.csv_rows.value.trim();
    const result = await withButtonState(button, "Importing...", "CSV Imported", async () => {
      return api("/api/v1/source-trackers/indeed/import-csv", {
        method: "POST",
        body: JSON.stringify(sourceTrackerCsvPayload(csvRows)),
      });
    });
    showToast(`Indeed CSV: ${result.imported} imported, ${result.skipped} skipped`);
    await loadAll();
    showWorkspaceSection("opportunities");
  } catch (error) {
    showToast(error.message);
  }
});

elements.indeedCsvForm.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button || button.dataset.action !== "fill-indeed-template") return;
  const field = elements.indeedCsvForm.elements.csv_rows;
  field.value = INDEED_CSV_TEMPLATE;
  field.focus();
});

elements.jobUrlImportForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button[type='submit']");
  try {
    const result = await withButtonState(button, "Importing...", "URL Imported", async () => {
      return api("/api/v1/job-discovery/import-url", {
        method: "POST",
        body: JSON.stringify(jobUrlImportPayloadFromForm(form)),
      });
    });
    const warningText = result.warnings.length ? ` ${result.warnings.join(" ")}` : "";
    showToast(
      `URL import (${result.source}): ${result.imported} imported, ${result.skipped} skipped.${warningText}`,
    );
    form.reset();
    await loadAll();
    showWorkspaceSection("opportunities");
  } catch (error) {
    showToast(error.message);
  }
});

elements.jobSearchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button[type='submit']");
  try {
    const form = event.currentTarget;
    const payload = {
      target_roles: parseList(form.elements.target_roles.value),
      target_locations: parseList(form.elements.target_locations.value),
      target_skills: parseList(form.elements.target_skills.value),
      sources: parseList(form.elements.sources.value),
      max_jobs_per_source: Number(form.elements.max_jobs_per_source.value || 20),
      posted_within_days: Number(form.elements.posted_within_days.value || 14),
      import_results: form.elements.import_results.checked,
    };
    const result = await withButtonState(button, "Searching...", "Search Complete", async () => {
      return api("/api/v1/job-discovery/search", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    });
    const errorText = result.errors.length ? `. Source issue: ${result.errors.join("; ")}` : "";
    showToast(
      `Latest jobs from last ${payload.posted_within_days} days: ${result.discovered} found, ${result.imported} imported, ${result.skipped} skipped${errorText}`,
    );
    await loadAll();
  } catch (error) {
    showToast(error.message);
  }
});

elements.jobSourceDiscoveryForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button[type='submit']");
  try {
    const form = event.currentTarget;
    const payload = {
      target_roles: parseList(form.elements.target_roles.value),
      target_locations: parseList(form.elements.target_locations.value),
      target_skills: parseList(form.elements.target_skills.value),
      source_urls: parseList(form.elements.source_urls.value),
      import_results: form.elements.import_results.checked,
    };
    const result = await withButtonState(button, "Discovering...", "Discovery Complete", async () => {
      return api("/api/v1/job-discovery/discover", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    });
    const errorText = result.errors.length ? `, ${result.errors.length} source errors` : "";
    showToast(
      `Discovery: ${result.discovered} found, ${result.imported} imported, ${result.skipped} skipped${errorText}`,
    );
    await loadAll();
  } catch (error) {
    showToast(error.message);
  }
});

elements.quickJobImportForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button[type='submit']");
  try {
    const result = await withButtonState(button, "Importing...", "Imported", async () => {
      return api("/api/v1/job-discovery/import", {
        method: "POST",
        body: JSON.stringify(quickJobImportPayloadFromForm(form)),
      });
    });
    form.reset();
    setupTagEditors(form);
    showToast(`Quick import: ${result.imported} imported, ${result.skipped} skipped`);
    await loadAll();
    showWorkspaceSection("opportunities");
  } catch (error) {
    showToast(error.message);
  }
});

elements.jobDiscoveryForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button[type='submit']");
  try {
    const form = event.currentTarget;
    const payload = {
      target_roles: parseList(form.elements.target_roles.value),
      target_locations: parseList(form.elements.target_locations.value),
      target_skills: parseList(form.elements.target_skills.value),
      jobs: parseJobDiscoveryRows(form.elements.job_rows.value),
    };
    const result = await withButtonState(button, "Importing...", "Jobs Imported", async () => {
      return api("/api/v1/job-discovery/import", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    });
    showToast(`Job discovery: ${result.imported} imported, ${result.skipped} skipped`);
    await loadAll();
  } catch (error) {
    showToast(error.message);
  }
});

elements.jobDiscoveryForm.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button || button.dataset.action !== "fill-job-template") return;
  const field = elements.jobDiscoveryForm.elements.job_rows;
  field.value = JOB_ROWS_TEMPLATE;
  field.focus();
});

elements.batchLeadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button[type='submit']");
  try {
    const leads = parseLeadCsv(event.currentTarget.elements.csv.value);
    await withButtonState(button, "Importing...", "Imported", async () => {
      await api("/api/v1/leads/batch", {
        method: "POST",
        body: JSON.stringify(leads),
      });
    });
    showToast(`${leads.length} contacts imported`);
    await loadAll();
  } catch (error) {
    showToast(error.message);
  }
});

elements.batchLeadForm.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button || button.dataset.action !== "fill-contact-template") return;
  const field = elements.batchLeadForm.elements.csv;
  field.value = CONTACT_CSV_TEMPLATE;
  field.focus();
});

elements.campaignForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button[type='submit']");
  try {
    await withButtonState(button, "Creating...", "Campaign Created", async () => {
      await api("/api/v1/campaigns", {
        method: "POST",
        body: JSON.stringify(removeEmptyValues(formToObject(event.currentTarget))),
      });
    });
    showToast("Campaign created");
    await loadAll();
  } catch (error) {
    showToast(error.message);
  }
});

elements.draftForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button[type='submit']");
  try {
    await withButtonState(button, "Generating...", "Draft Created", async () => {
      await api("/api/v1/drafts/generate", {
        method: "POST",
        body: JSON.stringify(removeEmptyValues(formToObject(event.currentTarget))),
      });
    });
    showToast("Draft generated");
    await loadAll();
  } catch (error) {
    showToast(error.message);
  }
});

elements.replyForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button[type='submit']");
  try {
    await withButtonState(button, "Classifying...", "Classified", async () => {
      await api("/api/v1/replies/classify", {
        method: "POST",
        body: JSON.stringify(removeEmptyValues(formToObject(event.currentTarget))),
      });
    });
    showToast("Reply classified");
    await loadAll();
  } catch (error) {
    showToast(error.message);
  }
});

elements.syncEmailReplies.addEventListener("click", async (event) => {
  try {
    const result = await withButtonState(event.currentTarget, "Syncing...", "Synced", async () => (
      api("/api/v1/replies/sync", { method: "POST" })
    ));
    showToast(`Gmail sync: ${result.imported} imported, ${result.matched} matched, ${result.skipped} skipped`);
    await loadAll();
  } catch (error) {
    showToast(error.message);
  }
});

elements.sentList.addEventListener("click", async (event) => {
  const button = event.target.closest("button");
  if (!button) return;

  if (button.dataset.action === "send-approved-draft") {
    try {
      await withButtonState(button, "Sending...", "Send Complete", async () => {
        await api(`/api/v1/drafts/${button.dataset.id}/send`, {
          method: "POST",
          body: JSON.stringify({
            sender: "Prakriti",
            note: "Sent or dry-run completed from Gmail Outreach.",
          }),
        });
      });
      showToast("Send / dry-run completed. Check Replies next.");
      await loadAll();
    } catch (error) {
      showToast(error.message);
    }
    return;
  }

  if (button.dataset.action === "find-contact-from-gmail") {
    try {
      const result = await withButtonState(button, "Searching...", "Search Done", async () => (
        api(`/api/v1/leads/${button.dataset.leadId}/find-contact`, { method: "POST" })
      ));
      if (result.contact_email) {
        showToast(`Email found: ${result.contact_email}. Draft is now send-ready.`);
      } else {
        showToast("No public email found. Track as application-only unless a real email appears.");
      }
      await loadAll();
    } catch (error) {
      showToast(error.message);
    }
    return;
  }

  if (button.dataset.action === "open-sent-opportunity") {
    openOpportunityFromLeadId(button.dataset.leadId);
    return;
  }

  if (button.dataset.action !== "classify-sent-reply") return;
  showWorkspaceSection("replies");
  elements.replyForm.elements.draft_id.value = button.dataset.id;
  elements.replyForm.elements.from_email.value = button.dataset.email || "";
  elements.replyForm.elements.body.focus();
});

elements.repliesList.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button || button.dataset.action !== "open-reply-opportunity") return;
  openOpportunityFromLeadId(button.dataset.leadId);
});

elements.generateFollowups.addEventListener("click", async (event) => {
  try {
    const daysSinceSent = elements.followupDays.value === "" ? 3 : Number(elements.followupDays.value);
    const limit = elements.followupLimit.value === "" ? 10 : Number(elements.followupLimit.value);
    const result = await withButtonState(event.currentTarget, "Generating...", "Drafts Created", async () => (
      api("/api/v1/followups/generate", {
        method: "POST",
        body: JSON.stringify({
          days_since_sent: daysSinceSent,
          limit,
          call_to_action: elements.followupCta.value.trim() || "Would it be worth a quick conversation this week?",
          extra_context: "Follow-up draft for job-search outreach. Keep it concise and human-reviewable.",
        }),
      })
    ));
    const hint = result.created
      ? ""
      : ". Need a sent/dry-run draft with recipient email, no reply, and no active draft for that opportunity.";
    showToast(`Follow-ups: ${result.created} drafts created, ${result.skipped} skipped${hint}`);
    await loadAll();
    if (result.created) {
      showWorkspaceSection("drafts");
    }
  } catch (error) {
    showToast(error.message);
  }
});

elements.followupList.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button || button.dataset.action !== "open-followup-opportunity") return;
  openOpportunityFromLeadId(button.dataset.leadId);
});

elements.findDraftEmails.addEventListener("click", async (event) => {
  const targets = state.drafts
    .filter((draft) => draft.status === "approved")
    .map((draft) => state.leads.find((lead) => lead.id === draft.lead_id))
    .filter((lead) => lead && !lead.email);
  if (!targets.length) {
    showToast("No approved drafts need email discovery right now.");
    return;
  }
  let emailsFound = 0;
  let sourcesFound = 0;
  let failed = 0;
  try {
    await withButtonState(event.currentTarget, "Finding...", "Search Done", async () => {
      for (const lead of targets) {
        try {
          const result = await api(`/api/v1/leads/${lead.id}/find-contact`, { method: "POST" });
          if (result.contact_email) {
            emailsFound += 1;
          } else if (result.source_url) {
            sourcesFound += 1;
          }
        } catch (_error) {
          failed += 1;
        }
      }
    });
    showToast(`Email search complete: ${emailsFound} emails found, ${sourcesFound} source pages saved, ${failed} failed.`);
    await loadAll();
  } catch (error) {
    showToast(error.message);
  }
});

elements.draftsList.addEventListener("click", async (event) => {
  const button = event.target.closest("button");
  if (!button || button.disabled) return;

  const id = button.dataset.id;
  const action = button.dataset.action;
  if (action === "save-contact-email") {
    const card = button.closest(".draft-card");
    const email = card.querySelector(`[data-contact-email-for="${CSS.escape(id)}"]`).value.trim();
    if (!email) {
      showToast("Add a contact email first.");
      return;
    }
    if (!looksLikeEmail(email)) {
      showToast("That is not an email address. Use Auto Find Email or paste a real public email like careers@company.com.");
      return;
    }
    try {
      await withButtonState(button, "Saving...", "Saved", async () => {
        await api(`/api/v1/leads/${button.dataset.leadId}/contact`, {
          method: "PATCH",
          body: JSON.stringify({
            email,
            contact_name: "Hiring Team",
            contact_role: "Recruiting / Hiring",
            contact_source_url: card.querySelector("a[href]")?.href || null,
            note: "Added from draft approval queue before send.",
          }),
        });
      });
      showToast("Contact email saved. Send / Dry Run is now available.");
      await loadAll();
    } catch (error) {
      showToast(error.message);
    }
    return;
  }
  if (action === "auto-find-email") {
    try {
      const result = await withButtonState(button, "Searching...", "Search Done", async () => (
        api(`/api/v1/leads/${button.dataset.leadId}/find-contact`, { method: "POST" })
      ));
      if (result.contact_email) {
        showToast(`Email found: ${result.contact_email} (${result.confidence_score}/100)`);
      } else if (result.source_url) {
        showToast(`No email found yet. Best public source saved: ${result.source_url}`);
      } else {
        showToast("No public email found from the job/company sources.");
      }
      await loadAll();
    } catch (error) {
      showToast(error.message);
    }
    return;
  }
  if (action === "mark-applied-no-email") {
    try {
      await withButtonState(button, "Tracking...", "Tracked", async () => {
        await api(`/api/v1/leads/${button.dataset.leadId}/mark-applied`, { method: "POST" });
      });
      showToast("Application marked applied. Gmail outreach is skipped until a real public email is found.");
      await loadAll();
      showWorkspaceSection("applications");
    } catch (error) {
      showToast(error.message);
    }
    return;
  }
  if (action === "save") {
    const card = button.closest(".draft-card");
    const subject = card.querySelector(`[data-draft-field="subject"][data-id="${CSS.escape(id)}"]`).value.trim();
    const body = card.querySelector(`[data-draft-field="body"][data-id="${CSS.escape(id)}"]`).value.trim();
    try {
      await withButtonState(button, "Saving...", "Saved", async () => {
        await api(`/api/v1/drafts/${id}`, {
          method: "PATCH",
          body: JSON.stringify({
            subject,
            body,
            editor: "Prakriti",
            note: "Edited from dashboard before approval.",
          }),
        });
      });
      showToast("Draft edits saved");
      await loadAll();
    } catch (error) {
      showToast(error.message);
    }
    return;
  }

  const payloads = {
    approve: { reviewer: "Prakriti", note: "Approved from dashboard." },
    reject: { reviewer: "Prakriti", note: "Rejected from dashboard." },
    send: { sender: "Prakriti", note: "Sent or dry-run completed from dashboard." },
  };
  const paths = {
    approve: `/api/v1/drafts/${id}/approve`,
    reject: `/api/v1/drafts/${id}/reject`,
    send: `/api/v1/drafts/${id}/send`,
  };
  const labels = {
    approve: ["Approving...", "Approved"],
    reject: ["Rejecting...", "Rejected"],
    send: ["Sending...", "Send Complete"],
  };

  try {
    await withButtonState(button, labels[action][0], labels[action][1], async () => {
      await api(paths[action], {
        method: "POST",
        body: JSON.stringify(payloads[action]),
      });
    });
    showToast(`Draft ${action} completed`);
    await loadAll();
  } catch (error) {
    showToast(error.message);
  }
});

setupTagEditors();
setupJobSourceToggles();
showWorkspaceSection("dashboard");
loadAll();
