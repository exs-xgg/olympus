---
name: docs-update
description: Updates the documentation for the project. Use when you need to update the documentation for the project.
---
### Documentation Update Policy Skill

Ensure that **README.md always reflects the current state of the project**, especially for:

* setup
* installation
* project structure
* dependencies
* environment configuration

---

## 🧠 Core Rule (Non-Negotiable)

Any change that affects how the project is:

* installed
* configured
* structured
* or run

**MUST include a corresponding update to `README.md` in the same change.**

No exceptions.

---

## 📌 What Requires a README Update

You MUST update `README.md` if you:

### 1. Setup & Installation

* Add/remove dependencies
* Change install commands
* Introduce new required tools (e.g. Redis, Docker)
* Modify environment variables

---

### 2. Project Structure

* Add/remove/rename directories
* Change architecture (e.g. new `/agents`, `/orchestrator`)
* Introduce new services (queue, DB, etc.)

---

### 3. Execution / Usage

* Change how the app is started
* Add new scripts or commands
* Modify workflows (e.g. task execution flow)

---

### 4. Infrastructure Changes

* Add Redis, PostgreSQL, Celery, etc.
* Change ports, services, or configs
* Introduce background workers

---

## ❌ What Does NOT Require Updates

* Pure UI changes (styling only)
* Internal refactoring with no external impact
* Code comments or minor fixes

---

## 🔄 Required Workflow

Every PR or change must follow:

1. Make the change
2. Ask:

   > “Does this affect setup, structure, or usage?”
3. If YES → update `README.md`
4. Ensure:

   * Instructions are accurate
   * Commands actually work
   * No outdated steps remain

---

## ✅ Pull Request Requirement

All PRs MUST include:

* [ ] README.md updated (if applicable)
* [ ] Setup steps verified locally
* [ ] No stale or misleading documentation

PRs may be rejected if:

* README is outdated
* Setup instructions are broken
* New components are undocumented

---

## 🧪 Validation Standard

If someone clones the repo fresh:

They should be able to:

1. Install dependencies
2. Configure environment
3. Run the system

**Using ONLY the README.md**

---

## ⚠️ Enforcement

* Treat missing README updates as a **breaking issue**
* Reviewers must block merges if this policy is violated
* Prefer over-documenting vs under-documenting

---

## 🧩 Guiding Principle

> The README is not optional documentation.
> It is the **entry point to the system**.

If it’s wrong, the system is effectively broken.
